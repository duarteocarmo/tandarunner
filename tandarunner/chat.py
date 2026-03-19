import logging

from django.conf import settings
from pydantic_ai import Agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a knowledgeable and friendly running coach. "
    "You help runners improve their training, understand their data, and prepare for races. "
    "You are familiar with Tanda's marathon prediction formula and general running science. "
    "Keep your responses concise and actionable. "
    "When given the athlete's running data, use it to give personalized advice."
)

agent = Agent(
    f"openrouter:{settings.MODEL_ID}",
    system_prompt=SYSTEM_PROMPT,
)
