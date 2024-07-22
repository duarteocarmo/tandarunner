import contextlib
import io
from enum import Enum
from hashlib import md5

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from tandarunner.visualizations import get_dummy_activities

# THIS IS HACKY, BUT IT WORKS


class DataField(str, Enum):
    DISTANCE_METERS = "distance_meters"
    MOVING_TIME_SECONDS = "moving_time_seconds"
    DATE = "date"
    AVERAGE_SPEED_METERS_PER_SECOND = "average_speed_meters_per_second"
    MAX_HEARTRATE = "max_heartrate"
    AVERAGE_HEARTRATE = "average_heartrate"


class Insight(BaseModel):
    observation: str = Field(
        description="The metric observed in the data over a period of time"
    )
    outcome: str = Field(
        description="How the metric observed affects the performance of the athlete"
    )
    data_fields: list[DataField] = Field(
        description="The data fields required to compute the observation"
    )

    def generate_id(self):
        return md5(
            f"{self.observation}{self.outcome}{self.data_fields}".encode()
        ).hexdigest()


class ExtractedInsights(BaseModel):
    insights: list[Insight]


PROMPT_GET_INSIGHTS_SYSTEM = f"""
You are a very experienced running coach.
You are conducting research for your athletes so that they can improve their running performance.
Your goal is to give valuable feedback to an athlete when looking at their running data.
For each athlete you have a table with all their runs year-to-date. For each run, you have the following information: {[e.value for e in DataField]}

You will be given a piece of content related to running.
Your goal is to analyse the piece of content, and extract valuable insights that can help analyse the current running form of the athlete.
For each insight, you need to ensure it can be calculated with the data you have available.
The insights should be easy to compute and understand to your athletes.
Only extract insights that are relevant in the context of looking at the last year of running data of an athlete. (You don't know ANY other details)
For example, don't extract observations related to sickness, weather, food, etc. (You don't have data for these.)
""".strip()

PROMPT_GET_INSIGHTS_USER = """
Content:
===
{transcript}
===
""".strip()


class PandasDataFrameQA(BaseModel):
    code: str = Field(description="The code to execute")
    cannot_compute: bool = Field(default=False)

    def execute(self, df: pd.DataFrame):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(self.code, globals(), {"df": df.copy()})
        return output.getvalue()

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str):
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                exec(v, globals(), {"df": get_dummy_activities().copy()})
                return v
            except Exception as e:
                raise ValueError(f"Invalid code: {e}")


PROMPT_GETQA_SYSTEM = f"""
You are working with a pandas dataframe in Python.
The name of the dataframe is `df`.
This is the result of `print(df.head())`:
{get_dummy_activities().head()}

Follow these instructions:
1. Write some code that will help you answer the user question.
2. The code should include print statements where appropriate.
3. The code will be called with the exec() function.
4. Do not include any other imports other than the pandas library.
5. Do not include any plots, graphs, or other visualizations.
6. Print the necessary variables so that once read, we can answer the user question.
""".strip()

PROMPT_GET_QA_USER = """
I would like to understand if we are seeing the following: {observation}
My goal is to understand if it will lead to the following outcome: {outcome}
""".strip()

RECOMMENDATION_PROMPT = """
You are a very experienced running coach.
Your research has lead to the conclusion that the following observation:

'{observation}'

Leads to the following outcome:

'{outcome}'

When investigating this, you ran the following code on the athletes's data:

```python
{code}
```

Which, when executed, produced the following output:

```
{execution_output}
```
The athlete's name is {athlete_name}.
Imagine you are having a conversation with the athlete.
What recommendation would you give them based on this insight?
Format things like a conversation, not like a letter (e.g., no "Dear Athlete", or "Sincerely, Coach").
Make sure to mention the observation and outcome in your recommendation.
A good recommendation should be personal and actionable.
""".strip()
