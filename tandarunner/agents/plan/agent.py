from datetime import datetime

from django.conf import settings
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openrouter import (
    OpenRouterModelSettings,
    OpenRouterReasoning,
)

from tandarunner.agents.deps import AgentDeps
from tandarunner.agents.plan.prompts import REFERENCE_QUERIES, SYSTEM_PROMPT
from tandarunner.agents.plan.schemas import TrainingPlanResult
from tandarunner.agents.tools import register_calendar_tool, register_sql_tool

if settings.OPENROUTER_API_KEY is None:
    raise ValueError("OPENROUTER_API_KEY is not set")

agent = Agent(
    model=settings.PLAN_AGENT_CONFIG["model"],
    system_prompt=SYSTEM_PROMPT,
    output_type=TrainingPlanResult,
    deps_type=AgentDeps,
    model_settings=OpenRouterModelSettings(
        temperature=settings.PLAN_AGENT_CONFIG["temperature"],
        openrouter_reasoning=OpenRouterReasoning(
            effort=settings.PLAN_AGENT_CONFIG["reasoning_effort"],
        ),
    ),
)


@agent.system_prompt
def add_athlete_name(ctx: RunContext[AgentDeps]) -> str:
    if ctx.deps.athlete_name:
        return f"The athlete's name is {ctx.deps.athlete_name}."
    return ""


@agent.system_prompt
def add_current_time() -> str:
    now = datetime.now().astimezone()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M %Z')}"


@agent.system_prompt
def add_schema_context(ctx: RunContext[AgentDeps]) -> str:
    sections: list[str] = []
    for query, description in REFERENCE_QUERIES.items():
        try:
            result = ctx.deps.connection.execute(query=query)
            dataframe = result.fetchdf().to_string()
        except Exception as error:
            dataframe = f"Query error: {error}"
        sections.append(f"-- {description}\n-- {query}\n{dataframe}")

    return "Reference queries and results:\n\n" + "\n\n".join(sections)


register_sql_tool(agent=agent)
register_calendar_tool(agent=agent)
