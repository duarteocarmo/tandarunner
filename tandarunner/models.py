import pandas as pd
from django.db import models

from tandarunner.tools.types_prompts import (
    RECOMMENDATION_PROMPT,
    Insight,
    PandasDataFrameQA,
)


class TrainingInsight(models.Model):
    insight_id = models.CharField(max_length=32, unique=True)
    source_id = models.CharField(max_length=32)
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Insight {self.insight_id}; Data: {self.data}"

    def generate_prompt(self, user_df: pd.DataFrame, athlete_name: str) -> str:
        qa = PandasDataFrameQA(**self.data.get("code", None))
        insight = Insight(**self.data.get("insight", None))

        return RECOMMENDATION_PROMPT.format_map(
            {
                "observation": insight.observation,
                "outcome": insight.outcome,
                "code": qa.code,
                "execution_output": qa.execute(user_df),
                "athlete_name": athlete_name,
            }
        )
