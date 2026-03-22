import json
import logging
import uuid
from typing import Any

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from pydantic_ai import (
    FinalResultEvent,
    FunctionToolCallEvent,
    PartDeltaEvent,
    ThinkingPartDelta,
)
from pydantic_ai.messages import ModelMessage

from tandarunner.agents.chat.agent import agent
from tandarunner.agents.deps import build_deps, close_deps

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.message_history: list[ModelMessage] = []
        self.user = self.scope["user"]
        self.session = await sync_to_async(self.scope["session"].load)()
        await super().connect()
        await self._send_welcome_message()

    async def receive(self, text_data: str = None, bytes_data: str = None):  # type: ignore[override]
        text_data_json = json.loads(text_data)
        logger.info(f"Received: {text_data_json}")

        if "reset" in text_data_json:
            await self.reset_chat()
            return

        message_text = text_data_json["message"]
        await self._send_user_message(message_text)

        if self.user.is_anonymous:
            await self._not_authorized_response()
        else:
            await self._generate_ai_response(message_text)

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

    async def _generate_ai_response(self, user_message: str):
        prompt = user_message

        self.session = await sync_to_async(self.scope["session"].load)()
        running_activities_json = self.session.get("running_activities")
        if not running_activities_json:
            logger.warning("Chat attempted before data was loaded.")
            bubble_id = await self._create_bubble(
                prefix="Your data is still loading, please try again in a moment!"
            )
            await self._finalize_bubble(
                bubble_id=bubble_id,
                text="Your data is still loading, please try again in a moment!",
            )
            return

        athlete_name = self.session.get("athlete", {}).get("firstname", "")
        deps = build_deps(
            running_activities_json=running_activities_json,
            athlete_name=athlete_name,
        )

        thinking_text = ""
        response_text = ""

        try:
            async with agent.iter(
                user_prompt=prompt,
                message_history=self.message_history,
                deps=deps,
            ) as run:
                thinking_bubble_id: str | None = None
                response_bubble_id: str | None = None

                async for node in run:
                    if agent.is_model_request_node(node):
                        async with node.stream(run.ctx) as request_stream:
                            async for event in request_stream:
                                if isinstance(
                                    event, PartDeltaEvent
                                ) and isinstance(
                                    event.delta, ThinkingPartDelta
                                ):
                                    if thinking_bubble_id is None:
                                        thinking_bubble_id = (
                                            await self._create_bubble(
                                                prefix="[thinking] ",
                                                css_class="chat-thinking",
                                            )
                                        )
                                    chunk = event.delta.content_delta
                                    thinking_text += chunk
                                    await self._stream_to_bubble(
                                        bubble_id=thinking_bubble_id,
                                        chunk=chunk,
                                    )
                                elif isinstance(event, FinalResultEvent):
                                    break

                            if thinking_bubble_id:
                                await self._finalize_bubble(
                                    bubble_id=thinking_bubble_id,
                                    text=f"[thinking] {thinking_text}",
                                    css_class="chat-thinking",
                                )
                                thinking_bubble_id = None
                                thinking_text = ""

                            async for text in request_stream.stream_text(
                                delta=True
                            ):
                                if response_bubble_id is None:
                                    response_bubble_id = (
                                        await self._create_bubble()
                                    )
                                response_text += text
                                await self._stream_to_bubble(
                                    bubble_id=response_bubble_id,
                                    chunk=text,
                                )

                    if agent.is_call_tools_node(node):
                        if response_bubble_id:
                            await self._finalize_bubble(
                                bubble_id=response_bubble_id,
                                text=response_text,
                            )
                            response_bubble_id = None
                            response_text = ""

                        async with node.stream(run.ctx) as tool_stream:
                            async for event in tool_stream:
                                if isinstance(event, FunctionToolCallEvent):
                                    call_args = event.part.args_as_dict()
                                    reason = call_args.get("reason", "")
                                    label = f"[{event.part.tool_name}]"
                                    if reason:
                                        label = f"{label} {reason}"
                                    tool_bubble_id = await self._create_bubble(
                                        prefix=label,
                                        css_class="chat-thinking",
                                    )
                                    await self._finalize_bubble(
                                        bubble_id=tool_bubble_id,
                                        text=label,
                                        css_class="chat-thinking",
                                    )

                if response_bubble_id:
                    await self._finalize_bubble(
                        bubble_id=response_bubble_id,
                        text=response_text,
                    )

            self.message_history.extend(run.result.new_messages())
        finally:
            close_deps(deps=deps)

    async def _create_bubble(
        self, prefix: str = "", css_class: str = ""
    ) -> str:
        bubble_id = f"message-{uuid.uuid4().hex}"
        await self._send_html(
            "partials/message.html",
            {
                "message_text": prefix,
                "is_system": True,
                "message_id": bubble_id,
                "css_class": css_class,
            },
        )
        return bubble_id

    async def _stream_to_bubble(self, *, bubble_id: str, chunk: str):
        await self.send(
            text_data=f"""<div id='{bubble_id}' hx-swap-oob="beforeend">{chunk}</div>"""
        )

    async def _finalize_bubble(
        self, *, bubble_id: str, text: str, css_class: str = ""
    ):
        await self._send_html(
            "partials/final_message.html",
            {
                "message_text": text,
                "message_id": bubble_id,
                "css_class": css_class,
            },
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
        bubble_id = await self._create_bubble(
            prefix="Please login to use the chat feature :)"
        )
        await self._finalize_bubble(
            bubble_id=bubble_id,
            text="Please login to use the chat feature :)",
        )
        await self.close()
