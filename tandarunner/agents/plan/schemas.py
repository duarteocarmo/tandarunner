from datetime import date
from enum import StrEnum

from pydantic import BaseModel


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


class TrainingPlanResult(BaseModel):
    name: str
    goal: str
    goal_date: date
    coach_message: str
    sessions: list[Session]
