import logging
from datetime import date, timedelta

from django.conf import settings
from pydantic_ai import Agent, RunContext

from tandarunner.agents.deps import AgentDeps

logger = logging.getLogger(__name__)


def register_sql_tool(*, agent: Agent[AgentDeps, ...]) -> None:
    @agent.tool
    async def run_sql_query(
        ctx: RunContext[AgentDeps], sql: str, reason: str
    ) -> str:
        """Run a SQL query against running activities. Provide a short reason for why the query is needed."""
        try:
            async with ctx.deps.query_lock:
                result = ctx.deps.connection.execute(query=sql)
                dataframe = result.fetchdf()

            if dataframe.empty:
                logger.info("SQL query returned no rows.")
                return "Query returned no results."

            logger.info("SQL query completed.")
            return dataframe.to_string(
                max_rows=settings.AGENT_CONFIG["max_result_rows"],
                max_cols=settings.AGENT_CONFIG["max_result_cols"],
            )
        except Exception as error:
            logger.info("SQL query failed.")
            return f"Query error: {error}"


def register_calendar_tool(*, agent: Agent[AgentDeps, ...]) -> None:
    @agent.tool
    def get_calendar(
        ctx: RunContext[AgentDeps], start_date: str, days: int
    ) -> str:
        """Get a compact calendar view showing day names and dates. Call this BEFORE building a training plan so you can assign real dates to each session. Pass the start_date (YYYY-MM-DD) and number of days ahead to display."""
        start = date.fromisoformat(start_date)
        lines = []
        current = start
        week: list[str] = []
        for _ in range(days):
            week.append(current.strftime("%a %d %b"))
            if current.weekday() == 6:
                lines.append(" | ".join(week))
                week = []
            current += timedelta(days=1)
        if week:
            lines.append(" | ".join(week))
        return "\n".join(lines)
