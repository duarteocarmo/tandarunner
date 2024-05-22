import json

from channels.generic.websocket import WebsocketConsumer
from django.template.loader import render_to_string


class ChatConsumer(WebsocketConsumer):
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_text = text_data_json["message"]
        print("Received message: ", message_text)

        user_message_html = render_to_string(
            "partials/message.html",
            {
                "message_text": message_text,
            },
        )

        self.send(text_data=user_message_html)
        print("Sent message: ", user_message_html)
