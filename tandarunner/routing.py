from django.urls import path

from tandarunner.agents.chat.consumer import ChatConsumer
from tandarunner.agents.plan.consumer import PlanConsumer

websocket_urlpatterns = [
    path(
        r"ws/chat/",
        ChatConsumer.as_asgi(),
        name="chat",
    ),
    path(
        r"ws/plan/",
        PlanConsumer.as_asgi(),
        name="plan",
    ),
]
