import json
import logging
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from litellm import stream_chunk_builder

from tandarunner.chat import generate_response_to

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.messages = []
        self.user = self.scope["user"]
        await super().connect()

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        logger.info(f"Received: {text_data_json}")

        if "reset" in text_data_json:
            await self.reset_chat()
            return

        message_text = text_data_json["message"]
        self.messages.append({"content": message_text, "role": "user"})

        user_message_html = render_to_string(
            "partials/message.html",
            {
                "message_text": message_text,
                "is_system": False,
            },
        )
        await self.send(text_data=user_message_html)

        self.message_id = f"message-{uuid.uuid4().hex}"
        system_message_html = render_to_string(
            "partials/message.html",
            {
                "message_text": "",
                "is_system": True,
                "message_id": self.message_id,
            },
        )

        await self.send(text_data=system_message_html)
        if self.user.is_anonymous:
            await self.not_authorized_response()
        else:
            await self.generate_ai_response()

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

    async def generate_ai_response(self):
        response = await generate_response_to(self.messages)
        chunks = []
        async for chunk in response:
            text = chunk.choices[0].delta.content or ""
            text = text.replace("\n", "<br>")
            await self.send(
                text_data=f"""<div id='{self.message_id}' hx-swap-oob="beforeend">{text}</div>"""
            )
            chunks.append(chunk)

        final_message = (
            stream_chunk_builder(chunks, messages=self.messages)
            .choices[0]
            .message.content
        )
        final_message_rendered = render_to_string(
            "partials/final_message.html",
            {
                "message_text": final_message,
                "message_id": self.message_id,
            },
        )

        await self.send(text_data=final_message_rendered)
        self.messages.append(
            {
                "content": final_message,
                "role": "system",
            }
        )
