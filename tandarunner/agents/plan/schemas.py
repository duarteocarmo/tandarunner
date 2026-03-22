from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


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
    name: str = Field(
        description="Calendar name, format: 'Athlete Name: Goal (DD/MM/YYYY)'"
    )
    achievability: Literal["stretch", "realistic", "conservative"] = Field(
        description="How achievable this plan is given the athlete's current fitness"
    )
    coach_message: str = Field(
        description="Markdown-formatted message explaining reasoning, plan structure, and progression toward the goal"
    )
    sessions: list[Session]
