import asyncio
import logging
from dataclasses import dataclass, field
from io import StringIO

import duckdb
import pandas

logger = logging.getLogger(__name__)

VIEW_NAME = "data"


@dataclass
class AgentDeps:
    connection: duckdb.DuckDBPyConnection
    athlete_name: str = ""
    query_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def build_deps(
    *, running_activities_json: str, athlete_name: str = ""
) -> AgentDeps:
    connection = duckdb.connect(database=":memory:")
    running_activities = pandas.read_json(StringIO(running_activities_json))
    connection.register(view_name=VIEW_NAME, python_object=running_activities)
    return AgentDeps(connection=connection, athlete_name=athlete_name)


def close_deps(*, deps: AgentDeps) -> None:
    deps.connection.close()
