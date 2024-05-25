import json
import uuid

from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.messages = []
        await super().connect()

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_text = text_data_json["message"]
        self.messages.append({"message": message_text, "role": "user"})

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
        response = f"User said: {message_text}"

        for chunk in response.split(" "):
            chunk += " "
            await self.send(
                text_data=f'<div id="{message_id}" hx-swap-oob="beforeend">{chunk}</div>'
            )

        self.messages.append({"message": response, "role": "system"})
        print(self.messages)
