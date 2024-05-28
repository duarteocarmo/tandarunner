import json
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from litellm import acompletion, stream_chunk_builder


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.messages = []
        await super().connect()

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_text = text_data_json["message"]
        self.messages.append({"content": message_text, "role": "user"})

        user_message_html = render_to_string(
            "partials/message.html",
            {"message_text": message_text, "is_system": False},
        )
        await self.send(text_data=user_message_html)

        message_id = f"message-{uuid.uuid4().hex}"
        system_message_html = render_to_string(
            "partials/message.html",
            {
                "message_text": "",
                "is_system": True,
                "message_id": message_id,
            },
        )
        await self.send(text_data=system_message_html)

        response = await acompletion(
            model="gpt-3.5-turbo",
            messages=self.messages,
            stream=True,
        )

        chunks = []
        async for chunk in response:
            text = chunk.choices[0].delta.content or ""
            text = text.replace("\n", "<br>")
            await self.send(
                text_data=f"""<div id='{message_id}' hx-swap-oob="beforeend">{text}</div>"""
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
                "message_id": message_id,
            },
        )

        await self.send(text_data=final_message_rendered)

        self.messages.append(
            {
                "content": final_message,
                "role": "system",
            }
        )
