import json
import logging
import uuid
from typing import Any

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from pydantic_ai.messages import ModelMessage

from tandarunner.chat import agent

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.message_history: list[ModelMessage] = []
        self.user = self.scope["user"]
        self.session = await sync_to_async(self.scope["session"].load)()
        self.system_context = self._build_system_context()
        await super().connect()
        await self._send_welcome_message()

    def _build_system_context(self) -> str:
        context = ""
        if not self.user.is_anonymous:
            athlete_name = self.session.get("athlete", {}).get("firstname", "")
            if athlete_name:
                context += f"\n\nThe athlete's name is {athlete_name}."
        return context

    async def receive(self, text_data: str = None, bytes_data: str = None):  # type: ignore[override]
        text_data_json = json.loads(text_data)
        logger.info(f"Received: {text_data_json}")

        if "reset" in text_data_json:
            await self.reset_chat()
            return

        message_text = text_data_json["message"]
        await self._send_user_message(message_text)
        await self._send_ai_response(message_text)

    async def _send_welcome_message(self):
        if self.user.is_anonymous:
            welcome = "Please login to receive personalized advice from your running coach!"
        else:
            athlete_name = self.session.get("athlete", {}).get("firstname", "")
            name_part = f", {athlete_name}" if athlete_name else ""
            welcome = f"Hey{name_part}! I'm your running coach. Ask me anything about your training, race prep, or data."

        await self._send_html(
            "partials/message.html",
            {"message_text": welcome, "is_system": True},
        )

    async def _send_user_message(self, message_text: str):
        await self._send_html(
            "partials/message.html",
            {"message_text": message_text, "is_system": False},
        )

    async def _send_ai_response(self, user_message: str):
        self.message_id = f"message-{uuid.uuid4().hex}"
        await self._send_html(
            "partials/message.html",
            {
                "message_text": "",
                "is_system": True,
                "message_id": self.message_id,
            },
        )

        if self.user.is_anonymous:
            await self._not_authorized_response()
        else:
            await self._generate_ai_response(user_message)

    async def _generate_ai_response(self, user_message: str):
        prompt = (
            f"{self.system_context}\n\n{user_message}"
            if self.system_context and not self.message_history
            else user_message
        )

        full_text = ""
        async with agent.iter(
            prompt, message_history=self.message_history
        ) as run:
            async for node in run:
                if agent.is_model_request_node(node):
                    async with node.stream(run.ctx) as request_stream:
                        async for text in request_stream.stream_text(
                            delta=True
                        ):
                            full_text += text
                            escaped = text.replace("\n", "<br>")
                            await self.send(
                                text_data=f"""<div id='{self.message_id}' hx-swap-oob="beforeend">{escaped}</div>"""
                            )

        self.message_history = run.result.new_messages()
        await self._send_final_message(full_text)

    async def _send_final_message(self, final_message: str):
        await self._send_html(
            "partials/final_message.html",
            {"message_text": final_message, "message_id": self.message_id},
        )

    async def _send_html(self, template: str, template_args: dict[str, Any]):
        message_html = render_to_string(template, template_args)
        await self.send(text_data=message_html)

    async def reset_chat(self):
        self.message_history = []
        content = """<div class="chat-messages" id="message-list" hx-swap-oob="outerHTML"></div>"""
        await self.send(text_data=content)
        await self._send_welcome_message()

    async def _not_authorized_response(self):
        message = render_to_string(
            "partials/final_message.html",
            {
                "message_text": "Please login to use the chat feature :)",
                "message_id": self.message_id,
            },
        )
        await self.send(text_data=message)
        await self.close()
