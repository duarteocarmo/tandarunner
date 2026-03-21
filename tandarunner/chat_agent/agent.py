from datetime import datetime

from django.conf import settings
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openrouter import OpenRouterModelSettings

from tandarunner.chat_agent.prompts import REFERENCE_QUERIES, SYSTEM_PROMPT
from tandarunner.chat_agent.tools import ChatAgentDeps, register_chat_tools

if settings.OPENROUTER_API_KEY is None:
    raise ValueError("OPENROUTER_API_KEY is not set")

agent = Agent(
    model=settings.AGENT_CONFIG["model"],
    system_prompt=SYSTEM_PROMPT,
    deps_type=ChatAgentDeps,
    model_settings=OpenRouterModelSettings(
        temperature=settings.AGENT_CONFIG["temperature"],
    ),
)


@agent.system_prompt
def add_current_time() -> str:
    now = datetime.now().astimezone()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M %Z')}"


@agent.system_prompt
def add_schema_context(ctx: RunContext[ChatAgentDeps]) -> str:
    sections: list[str] = []
    for query, description in REFERENCE_QUERIES.items():
        try:
            result = ctx.deps.connection.execute(query=query)
            dataframe = result.fetchdf().to_string()
        except Exception as error:
            dataframe = f"Query error: {error}"
        sections.append(f"-- {description}\n-- {query}\n{dataframe}")

    return "Reference queries and results:\n\n" + "\n\n".join(sections)


register_chat_tools(agent=agent)
