import json
import logging
from typing import Any

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.template.loader import render_to_string
from pydantic_ai import (
    FunctionToolCallEvent,
    PartDeltaEvent,
    ThinkingPartDelta,
)
from pydantic_ai.messages import ModelMessage

from tandarunner.agents.deps import build_deps, close_deps
from tandarunner.agents.plan.agent import agent
from tandarunner.agents.plan.schemas import TrainingPlanResult
from tandarunner.models import TrainingPlan

logger = logging.getLogger(__name__)


class PlanConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.message_history: list[ModelMessage] = []
        self.user = self.scope["user"]
        self.session = await sync_to_async(self.scope["session"].load)()
        await super().connect()

    async def receive(self, text_data: str = None, bytes_data: str = None):  # type: ignore[override]
        data = json.loads(text_data)
        logger.info(f"Plan received: {data}")

        if self.user.is_anonymous:
            await self._send_status(
                "Please login to generate a training plan."
            )
            return

        self.session = await sync_to_async(self.scope["session"].load)()
        running_activities_json = self.session.get("running_activities")
        if not running_activities_json:
            await self._send_status(
                "Your data is still loading, please try again in a moment!"
            )
            return

        goal = data.get("goal", "")
        if not goal:
            return

        prompt = f"Create a training plan for: {goal}"

        await self._send_status("Starting...")
        await self._generate_plan(
            prompt=prompt, running_activities_json=running_activities_json
        )

    async def _generate_plan(
        self, *, prompt: str, running_activities_json: str
    ):
        athlete_name = self.session.get("athlete", {}).get("firstname", "")
        deps = build_deps(
            running_activities_json=running_activities_json,
            athlete_name=athlete_name,
        )

        try:
            async with agent.iter(
                user_prompt=prompt,
                message_history=self.message_history,
                deps=deps,
            ) as run:
                async for node in run:
                    if agent.is_model_request_node(node):
                        thinking_text = ""
                        async with node.stream(run.ctx) as request_stream:
                            async for event in request_stream:
                                if isinstance(
                                    event, PartDeltaEvent
                                ) and isinstance(
                                    event.delta, ThinkingPartDelta
                                ):
                                    thinking_text += event.delta.content_delta
                                    truncated = thinking_text[-200:]
                                    await self._send_status(truncated)

                    elif agent.is_call_tools_node(node):
                        async with node.stream(run.ctx) as tool_stream:
                            async for event in tool_stream:
                                if isinstance(event, FunctionToolCallEvent):
                                    tool_name = event.part.tool_name
                                    args = event.part.args_as_dict()
                                    if tool_name == "get_calendar":
                                        label = "Checking available dates..."
                                    else:
                                        label = args.get("reason", tool_name)
                                    await self._send_status(label)

                    elif agent.is_end_node(node):
                        output = node.data.output
                        if isinstance(output, TrainingPlanResult):
                            plan = await self._save_plan(result=output)
                            host = self.scope.get("headers", [])
                            origin = ""
                            for header_name, header_value in host:
                                if header_name == b"origin":
                                    origin = header_value.decode()
                                    break
                            if not origin:
                                for header_name, header_value in host:
                                    if header_name == b"host":
                                        origin = (
                                            f"https://{header_value.decode()}"
                                        )
                                        break
                            calendar_url = (
                                f"{origin}/plan/{plan.id}/calendar.ics"
                            )
                            sessions_by_week = self._group_sessions_by_week(
                                output.sessions
                            )
                            await self._send_html(
                                "partials/plan_result.html",
                                {
                                    "coach_message": output.coach_message,
                                    "achievability": output.achievability,
                                    "calendar_url": calendar_url,
                                    "sessions_by_week": sessions_by_week,
                                },
                            )

            self.message_history.extend(run.result.new_messages())
        finally:
            close_deps(deps=deps)

    @staticmethod
    def _group_sessions_by_week(sessions: list) -> list[dict]:
        from itertools import groupby

        grouped = []
        for week_num, week_sessions in groupby(
            sessions, key=lambda s: s.date.isocalendar()[1]
        ):
            items = list(week_sessions)
            start = items[0].date.strftime("%b %d")
            end = items[-1].date.strftime("%b %d")
            grouped.append({"label": f"{start} - {end}", "sessions": items})
        return grouped

    @sync_to_async
    def _save_plan(self, *, result: TrainingPlanResult) -> TrainingPlan:
        sessions_data = [s.model_dump(mode="json") for s in result.sessions]
        plan, _ = TrainingPlan.objects.update_or_create(
            user=self.user,
            defaults={
                "name": result.name,
                "achievability": result.achievability,
                "coach_message": result.coach_message,
                "sessions": sessions_data,
            },
        )
        logger.info(f"Saved training plan {plan.id} for user {self.user}.")
        return plan

    async def _send_status(self, text: str):
        html = f"""<div id="plan-status" class="bordered-block plan-status" hx-swap-oob="outerHTML">{text}</div>"""
        await self.send(text_data=html)

    async def _send_html(self, template: str, template_args: dict[str, Any]):
        message_html = render_to_string(template, template_args)
        await self.send(text_data=message_html)
