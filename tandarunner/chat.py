import pandas as pd
from asgiref.sync import sync_to_async
from litellm import acompletion, litellm
from litellm.caching import Cache

from tandarunner.models import TrainingInsight

litellm.set_verbose = False
litellm.cache = Cache(ttl=60 * 5)


async def generate_response_to(list_of_messages: list[dict]):
    return await acompletion(
        model="gpt-3.5-turbo",
        messages=list_of_messages,
        stream=True,
        caching=True,
    )


async def generate_recommendation_prompt(session: dict) -> str:
    running_activities = session["running_activities"]
    athlete_name = session.get("athlete", {}).get("firstname", "UNKNOWN")

    first_insight = await sync_to_async(TrainingInsight.objects.first)()

    prompt = await sync_to_async(first_insight.generate_prompt)(
        user_df=pd.read_json(running_activities), athlete_name=athlete_name
    )

    return prompt
