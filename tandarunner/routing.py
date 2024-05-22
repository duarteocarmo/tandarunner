from django.urls import path

from tandarunner.consumers import ChatConsumer

websocket_urlpatterns = [
    path(
        r"ws/chat/",
        ChatConsumer.as_asgi(),
        name="chat",
    ),
]
