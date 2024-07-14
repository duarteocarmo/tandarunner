import json
import logging
import uuid

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from litellm import stream_chunk_builder

from tandarunner.chat import generate_insight_for, generate_response_to

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.messages = []
        self.user = self.scope["user"]
        self.session = await sync_to_async(self.scope["session"].load)()

        await super().connect()

        await self.send_first_message()

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        logger.info(f"Received: {text_data_json}")

        if "reset" in text_data_json:
            await self.reset_chat()
            return

        message_text = text_data_json["message"]
        self.messages.append({"content": message_text, "role": "user"})

        await self.send_html(
            "partials/message.html",
            {
                "message_text": message_text,
                "is_system": False,
            },
        )

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

        await self.send_html(
            "partials/final_message.html",
            {
                "message_text": final_message,
                "message_id": self.message_id,
            },
        )

        self.messages.append(
            {
                "content": final_message,
                "role": "system",
            }
        )

    async def send_first_message(self):
        self.message_id = f"message-{uuid.uuid4().hex}"

        if self.user.is_anonymous:
            text = "Welcome to the chat! Please login to use the chat feature."
        else:
            text = await generate_insight_for(self.session)

        await self.send_html(
            "partials/message.html",
            {
                "message_text": text,
                "is_system": True,
                "message_id": self.message_id,
            },
        )

        self.messages.append(
            {
                "content": text,
                "role": "system",
            }
        )

    async def send_html(self, template, template_args):
        message_html = render_to_string(
            template,
            template_args,
        )
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
