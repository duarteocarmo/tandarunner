import io
import logging

import pandas as pd
from asgiref.sync import sync_to_async
from django.conf import settings
from openai import AsyncOpenAI

from tandarunner.models import TrainingInsight

logger = logging.getLogger(__name__)


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
    )


async def generate_response_to(list_of_messages: list):
    client = _get_client()
    return await client.chat.completions.create(
        model=settings.MODEL_ID,
        messages=list_of_messages,
        stream=True,
    )


async def generate_recommendation_prompt(session: dict) -> str:
    return await sync_to_async(fetch_recommendation_prompt)(session)


def fetch_recommendation_prompt(session: dict, retries: int = 3) -> str:
    running_activities = session["running_activities"]
    athlete_name = session.get("athlete", {}).get("firstname", "UNKNOWN")

    while retries > 0:
        try:
            first_insight = TrainingInsight.objects.order_by("?").first()
            prompt = first_insight.generate_prompt(
                user_df=pd.read_json(io.StringIO(running_activities)),
                athlete_name=athlete_name,
            )
            return prompt
        except Exception as e:
            retries -= 1
            print(f"Error fetching recommendation prompt: {e}")

    return "I'm sorry, I'm having trouble generating a recommendation prompt right now."
