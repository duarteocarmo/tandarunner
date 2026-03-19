import logging

from django.conf import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a knowledgeable and friendly running coach. "
    "You help runners improve their training, understand their data, and prepare for races. "
    "You are familiar with Tanda's marathon prediction formula and general running science. "
    "Keep your responses concise and actionable. "
    "When given the athlete's running data, use it to give personalized advice."
)


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.OPENROUTER_API_KEY,
    )


async def generate_response_to(messages: list):
    client = _get_client()
    return await client.chat.completions.create(
        model=settings.MODEL_ID,
        messages=messages,
        stream=True,
    )
