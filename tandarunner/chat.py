import logging

import pandas as pd
from asgiref.sync import sync_to_async
from litellm import acompletion, litellm
from litellm.caching import Cache

from tandarunner.models import TrainingInsight

litellm.set_verbose = False
litellm.cache = Cache(ttl=60 * 5)

logger = logging.getLogger(__name__)


async def generate_response_to(list_of_messages: list[dict]):
    return await acompletion(
        model="gpt-4o",
        messages=list_of_messages,
        stream=True,
        caching=True,
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
                user_df=pd.read_json(running_activities),
                athlete_name=athlete_name,
            )
            return prompt
        except Exception as e:
            retries -= 1
            print(f"Error fetching recommendation prompt: {e}")

    return "I'm sorry, I'm having trouble generating a recommendation prompt right now."
