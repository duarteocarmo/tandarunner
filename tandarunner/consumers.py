import json
import logging
import uuid
from typing import Any, Dict, List

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from django.template.loader import render_to_string
from litellm import stream_chunk_builder

from tandarunner.chat import (
    generate_recommendation_prompt,
    generate_response_to,
)

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.messages: List[Dict[str, str]] = []
        self.user = self.scope["user"]
        self.session = await sync_to_async(self.scope["session"].load)()
        await super().connect()
        await self.send_first_message()

    async def receive(self, text_data: str):
        print(f"{self.messages=}")
        text_data_json = json.loads(text_data)
        logger.info(f"Received: {text_data_json}")

        if "reset" in text_data_json:
            await self.reset_chat()
            return

        message_text = text_data_json["message"]
        self.messages.append({"content": message_text, "role": "user"})

        await self.send_user_message(message_text)
        await self.send_ai_response()

    async def send_user_message(self, message_text: str):
        await self.send_html(
            "partials/message.html",
            {
                "message_text": message_text,
                "is_system": False,
            },
        )

    async def send_ai_response(self):
        self.message_id = f"message-{uuid.uuid4().hex}"
        await self.send_html(
            "partials/message.html",
            {
                "message_text": "",
                "is_system": True,
                "message_id": self.message_id,
            },
        )

        if self.user.is_anonymous:
            await self.not_authorized_response()
        else:
            await self.generate_ai_response()

    async def generate_ai_response(self):
        response = await generate_response_to(self.messages)
        chunks = []
        async for chunk in response:
            await self.send_chunk(chunk)
            chunks.append(chunk)

        final_message = self.get_final_message(chunks)
        await self.send_final_message(final_message)
        self.messages.append({"content": final_message, "role": "system"})

    async def send_chunk(self, chunk: Any):
        text = chunk.choices[0].delta.content or ""
        text = text.replace("\n", "<br>")
        await self.send(
            text_data=f"""<div id='{self.message_id}' hx-swap-oob="beforeend">{text}</div>"""
        )

    def get_final_message(self, chunks: List[Any]) -> str:
        return (
            stream_chunk_builder(chunks, messages=self.messages)
            .choices[0]
            .message.content
        )

    async def send_final_message(self, final_message: str):
        await self.send_html(
            "partials/final_message.html",
            {
                "message_text": final_message,
                "message_id": self.message_id,
            },
        )

    async def send_first_message(self):
        self.message_id = f"message-{uuid.uuid4().hex}"

        if self.user.is_anonymous:
            await self.send_anonymous_welcome_message()
        else:
            await self.send_authenticated_first_message()

    async def send_anonymous_welcome_message(self):
        text = "Please login to receive personalized recommendations from the Tanda agent!"
        await self.send_html(
            "partials/message.html",
            {
                "message_text": text,
                "is_system": True,
                "message_id": self.message_id,
            },
        )
        self.messages.append({"content": text, "role": "system"})

    async def send_authenticated_first_message(self):
        cache_key = f"recommendation_prompt_{self.user.id}"
        cached_prompt = cache.get(cache_key)

        await self.send_html(
            "partials/message.html",
            {
                "message_text": "",
                "is_system": True,
                "message_id": self.message_id,
            },
        )

        if cached_prompt:
            recommendation_prompt = cached_prompt
        else:
            try:
                recommendation_prompt = await generate_recommendation_prompt(
                    self.session
                )
                cache.set(
                    cache_key, recommendation_prompt, timeout=60 * 60 * 6
                )  # 6 hours
            except Exception as e:
                logger.error(e)
                recommendation_prompt = "Sorry, I am unable to generate a recommendation at this time."

        self.messages.append(
            {"content": recommendation_prompt, "role": "system"}
        )
        await self.generate_ai_response()

    async def send_html(self, template: str, template_args: Dict[str, Any]):
        message_html = render_to_string(template, template_args)
        await self.send(text_data=message_html)

    async def reset_chat(self):
        self.messages = []
        content = """<div class="chat-messages" id="message-list" hx-swap-oob="outerHTML"></div>"""
        await self.send(text_data=content)

    async def not_authorized_response(self):
        message = render_to_string(
            "partials/final_message.html",
            {
                "message_text": "Please login to use the chat feature :) ",
                "message_id": self.message_id,
            },
        )
        await self.send(text_data=message)
        await self.close()
