# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pydantic-ai-slim[openrouter]",
#     "duckdb",
#     "numpy",
#     "pandas",
#     "icalendar",
# ]
# ///
"""
Strava data agent using PydanticAI + DuckDB.

Answers questions about your Strava data and can generate structured training plans
exported as .ics calendar files.

Usage:
    export OPENROUTER_API_KEY=your-key
    uv run scripts/strava_agent.py --data strava_dump.parquet
    uv run scripts/strava_agent.py --data strava_dump.parquet --question "How much did I run this week?"
    uv run scripts/strava_agent.py --data strava_dump.parquet --question "Make me a 12-week half marathon plan for June 15 targeting 1:30"
"""

import argparse
import asyncio
import sys
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

import duckdb
from icalendar import Calendar, Event
from pydantic import BaseModel
from pydantic_ai import (
    Agent,
    FinalResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    RunContext,
    ThinkingPartDelta,
)

MODEL = "openrouter:z-ai/glm-5"
MODEL_TEMPERATURE = 0.0
VIEW_NAME = "data"
MAX_RESULT_ROWS = 50
MAX_RESULT_COLS = 20
ICS_OUTPUT = "training_plan.ics"


class SessionCategory(StrEnum):
    easy_run = "easy_run"
    tempo = "tempo"
    intervals = "intervals"
    long_run = "long_run"
    recovery = "recovery"


class Session(BaseModel):
    date: date
    title: str
    description: str
    category: SessionCategory


class TrainingPlan(BaseModel):
    name: str
    goal: str
    goal_date: date
    coach_message: str
    sessions: list[Session]

    def pretty(self) -> str:
        lines = [f"{self.name} — {self.goal} (goal: {self.goal_date})", ""]
        lines.append(f"  💬 {self.coach_message}")
        lines.append("")
        for session in sorted(self.sessions, key=lambda s: s.date):
            day_str = session.date.strftime("%a %d %b")
            lines.append(
                f"  {day_str}  {session.title} [{session.category.value}]"
            )
            lines.append(f"           {session.description}")
        return "\n".join(lines)


def get_connection(file_path: str) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()
    suffix = Path(file_path).suffix.lower()
    if suffix == ".parquet":
        conn.execute(
            f"CREATE VIEW {VIEW_NAME} AS SELECT * FROM read_parquet('{file_path}')"
        )
    elif suffix in (".csv", ".tsv"):
        conn.execute(
            f"CREATE VIEW {VIEW_NAME} AS SELECT * FROM read_csv_auto('{file_path}')"
        )
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    return conn


REFERENCE_QUERIES = {
    f"DESCRIBE {VIEW_NAME}": "Schema of the dataset",
    f"SELECT COUNT(*) FROM {VIEW_NAME}": "Total number of rows",
    f"SELECT * FROM {VIEW_NAME} LIMIT 5": "Sample of first 5 rows",
    f"SELECT DISTINCT sport_type FROM {VIEW_NAME}": "Available sport types",
    f"SELECT sport_type, COUNT(*) as count FROM {VIEW_NAME} GROUP BY sport_type ORDER BY count DESC": "Activity counts by sport type",
    f"SELECT start_date_local FROM {VIEW_NAME} LIMIT 1": "Date format example — use strptime(start_date_local, '%Y-%m-%dT%H:%M:%SZ') to parse",
}


SYSTEM_PROMPT = (
    f"You are a running coach and data analyst. You have access to a runner's activity history exposed as a DuckDB view called `{VIEW_NAME}`.\n"
    "Use the `run_query` tool to execute SQL queries against it.\n"
    "Use the `clarify_with_user` tool to ask the user for missing information.\n"
    "\n"
    "DuckDB's SQL dialect closely follows PostgreSQL with these key differences:\n"
    "- Integer division: 1/2 returns 0.5 (use // for integer division)\n"
    "- String dates need explicit CAST(col AS TIMESTAMP) for date comparisons\n"
    "- Use strptime() instead of to_date() for date parsing\n"
    "- Use CURRENT_DATE - INTERVAL '30' DAY for date arithmetic\n"
    "- Supports extras like EXCLUDE, COLUMNS(*), GROUP BY ALL, list comprehensions\n"
    "\n"
    "You can answer general data questions (return text) or generate training plans (return TrainingPlan).\n"
    "\n"
    "When asked to create a training plan:\n"
    "1. Query the runner's history to assess current fitness: weekly mileage, average pace, running frequency, usual running days, longest recent runs\n"
    "2. Use clarify_with_user if the goal or goal date is unclear\n"
    "3. Use get_calendar to see the actual dates available for planning — call it BEFORE building the plan so you assign real dates to sessions\n"
    "4. Respect the runner's existing schedule patterns (which days they usually run)\n"
    "5. Each session description must be specific: include distance, pace, time, repeats, rest intervals as appropriate. "
    "e.g. '10km at 5:20/km' or '6x800m at 3:30/km with 90s jog recovery, 2km warm-up, 1km cool-down' or '90min long run at 5:40-5:50/km'\n"
    "6. Each session has an explicit date field — use the dates from get_calendar\n"
    "7. Include a coach_message explaining your reasoning: why this plan suits the runner's current fitness and how it progresses toward the goal\n"
    "\n"
    "For general questions, explain your findings clearly after running queries."
)

agent = Agent(
    MODEL,
    system_prompt=SYSTEM_PROMPT,
    output_type=[str, TrainingPlan],
    deps_type=duckdb.DuckDBPyConnection,
)


@agent.system_prompt
def add_current_time() -> str:
    now = datetime.now().astimezone()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M %Z')}"


@agent.system_prompt
def add_schema_context(ctx: RunContext[duckdb.DuckDBPyConnection]) -> str:
    sections = []
    for query, description in REFERENCE_QUERIES.items():
        result = ctx.deps.execute(query).fetchdf().to_string()
        sections.append(f"-- {description}\n-- {query}\n{result}")

    return "Reference queries and results:\n\n" + "\n\n".join(sections)


@agent.tool
def run_query(
    ctx: RunContext[duckdb.DuckDBPyConnection], sql: str, reason: str
) -> str:
    """Run a SQL query against the data view. Returns results as a formatted string. Provide a short reason explaining what this query is for."""
    print(f"[query] {reason}")
    try:
        result = ctx.deps.execute(sql)
        df = result.fetchdf()
        if df.empty:
            return "Query returned no results."
        return df.to_string(max_rows=MAX_RESULT_ROWS, max_cols=MAX_RESULT_COLS)
    except Exception as e:
        return f"Query error: {e}"


@agent.tool
def clarify_with_user(
    ctx: RunContext[duckdb.DuckDBPyConnection], question: str
) -> str:
    """Ask the user a clarifying question and return their answer."""
    print(f"[agent] {question}")
    return input("> ").strip()


@agent.tool
def get_calendar(
    ctx: RunContext[duckdb.DuckDBPyConnection], start_date: str, days: int
) -> str:
    """Get a compact calendar view showing day names and dates. Call this BEFORE building a training plan so you can assign real dates to each session. Pass the start_date (YYYY-MM-DD) and number of days ahead to display."""
    start = date.fromisoformat(start_date)
    lines = []
    current = start
    week: list[str] = []
    for _ in range(days):
        week.append(current.strftime("%a %d %b"))
        if current.weekday() == 6:  # sunday
            lines.append(" | ".join(week))
            week = []
        current += timedelta(days=1)
    if week:
        lines.append(" | ".join(week))
    return "\n".join(lines)


def export_ics(plan: TrainingPlan) -> Path:
    cal = Calendar()
    cal.add("prodid", "-//Strava Training Plan//tandarunner//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", plan.name)

    for session in plan.sessions:
        event = Event()
        event.add("summary", f"🏃 {session.title}")
        event.add(
            "description", f"[{session.category.value}] {session.description}"
        )
        event.add("dtstart", session.date)
        cal.add_component(event)

    output_path = Path.cwd() / ICS_OUTPUT
    output_path.write_bytes(cal.to_ical())
    return output_path


async def ask(question: str, conn: duckdb.DuckDBPyConnection):
    async with agent.iter(question, deps=conn) as run:
        async for node in run:
            if Agent.is_model_request_node(node):
                async with node.stream(run.ctx) as request_stream:
                    thinking = False
                    async for event in request_stream:
                        if isinstance(event, PartDeltaEvent) and isinstance(
                            event.delta, ThinkingPartDelta
                        ):
                            if not thinking:
                                print("[thinking] ", end="", flush=True)
                                thinking = True
                            print(
                                event.delta.content_delta, end="", flush=True
                            )
                        elif isinstance(event, FinalResultEvent):
                            break
                    if thinking:
                        print()

                    try:
                        async for text in request_stream.stream_text(
                            delta=True
                        ):
                            print(text, end="", flush=True)
                    except Exception:
                        pass  # structured output, no text to stream

            elif Agent.is_call_tools_node(node):
                async with node.stream(run.ctx) as handle_stream:
                    last_tool_name = None
                    async for event in handle_stream:
                        if isinstance(event, FunctionToolCallEvent):
                            last_tool_name = event.part.tool_name
                            if last_tool_name != "clarify_with_user":
                                print(f"[tool] {event.part.args}")
                        elif isinstance(event, FunctionToolResultEvent):
                            if last_tool_name != "clarify_with_user":
                                content = event.result.content
                                preview = (
                                    content[:200] + "..."
                                    if len(content) > 200
                                    else content
                                )
                                print(f"[result] {preview}")

            elif Agent.is_end_node(node):
                output = node.data.output
                if isinstance(output, TrainingPlan):
                    print(f"\n{output.pretty()}")
                    ics_path = export_ics(output)
                    print(f"\n📅 Exported to {ics_path}")

    print()


async def main():
    parser = argparse.ArgumentParser(description="Strava data agent")
    parser.add_argument(
        "--data", required=True, help="Path to parquet/csv file"
    )
    parser.add_argument(
        "--question", help="Question to ask (omit for interactive mode)"
    )
    args = parser.parse_args()

    if not Path(args.data).exists():
        print(f"File not found: {args.data}")
        sys.exit(1)

    conn = get_connection(args.data)
    row_count = conn.execute(f"SELECT COUNT(*) FROM {VIEW_NAME}").fetchone()[0]
    print(f"Loaded {args.data} ({row_count} activities)")

    if args.question:
        await ask(args.question, conn)
    else:
        print("Ask questions about your Strava data. Type 'quit' to exit.\n")
        while True:
            try:
                question = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not question:
                continue
            if question.lower() in ("quit", "exit", "q"):
                break

            await ask(question, conn)
            print()

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
