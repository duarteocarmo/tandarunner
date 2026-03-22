import asyncio
import logging
from dataclasses import dataclass, field
from io import StringIO

import duckdb
import pandas
from django.conf import settings
from pydantic_ai import Agent, RunContext

from tandarunner.chat_agent.prompts import VIEW_NAME

logger = logging.getLogger(__name__)


@dataclass
class ChatAgentDeps:
    connection: duckdb.DuckDBPyConnection
    athlete_name: str = ""
    query_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def build_chat_deps(
    *, running_activities_json: str, athlete_name: str = ""
) -> ChatAgentDeps:
    connection = duckdb.connect(database=":memory:")
    running_activities = pandas.read_json(StringIO(running_activities_json))
    connection.register(view_name=VIEW_NAME, python_object=running_activities)
    return ChatAgentDeps(connection=connection, athlete_name=athlete_name)


def close_chat_deps(*, deps: ChatAgentDeps) -> None:
    deps.connection.close()


def register_chat_tools(*, agent: Agent[ChatAgentDeps, str]) -> None:
    @agent.tool
    async def run_sql_query(
        ctx: RunContext[ChatAgentDeps], sql: str, reason: str
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
