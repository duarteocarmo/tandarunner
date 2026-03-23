import logging
from datetime import date

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods
from icalendar import Calendar, Event

from tandarunner.helpers import get_athlete_data
from tandarunner.models import TrainingPlan
from tandarunner.visualizations import (
    get_dummy_visualizations,
    get_stats,
    get_visualizations,
)

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return TemplateResponse(request, "index.html", {"athlete": None})

    ad = get_athlete_data(request.user)
    return TemplateResponse(request, "index.html", {"athlete": ad["athlete"]})


@require_http_methods(["GET"])
def graphs_partial(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        logger.info("Fetched dummy data for anonymous user.")
        return TemplateResponse(
            request,
            "partials/graphs.html",
            {"visualizations": get_dummy_visualizations()},
        )

    ad = get_athlete_data(request.user)
    results = get_visualizations(ad["token"], ad["athlete_id"])
    logger.info("Got athlete data.")

    chart_keys = {
        "weekly_chart",
        "rolling_tanda",
        "marathon_predictor",
        "running_heatmap",
        "cumulative_yearly",
    }
    data = {
        "visualizations": {
            k: v for k, v in results.items() if k in chart_keys
        },
    }

    request.session.update(
        {
            "athlete": ad["athlete"],
            "running_activities": results["running_activities"],
        }
    )
    logger.info("Prepared graph data.")

    return TemplateResponse(request, "partials/graphs.html", data)


@require_http_methods(["GET"])
def stats_partial(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return TemplateResponse(request, "partials/stats.html", {})

    ad = get_athlete_data(request.user)
    results = get_visualizations(ad["token"], ad["athlete_id"])
    stats = get_stats(ad["token"], ad["athlete_id"])
    data = {
        "stats": stats,
        "current_tanda": results["current_tanda"],
        "current_tanda_pace": results["current_tanda_pace"],
        "avg_hr_per_km": results["avg_hr_per_km"],
    }
    logger.info("Prepared stats data.")
    return TemplateResponse(request, "partials/stats.html", data)


@require_http_methods(["GET"])
def chat_partial(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(request, "partials/chat.html")


@require_http_methods(["GET"])
def plan_partial(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(request, "partials/plan.html")


@require_http_methods(["GET"])
def plan_calendar(request: HttpRequest, plan_id: str) -> HttpResponse:
    plan = get_object_or_404(TrainingPlan, id=plan_id)

    cal = Calendar()
    cal.add("prodid", "-//Tanda Runner//tandarunner//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", plan.name)

    for session in plan.sessions:
        event = Event()
        event.add("summary", session["title"])
        category = session.get("category", "")
        event.add("description", f"[{category}] {session['description']}")
        event.add("dtstart", date.fromisoformat(session["date"]))
        cal.add_component(event)

    response = HttpResponse(
        cal.to_ical(),
        content_type="text/calendar; charset=utf-8",
    )
    if "download" in request.GET:
        response["Content-Disposition"] = (
            f'attachment; filename="{plan.name}.ics"'
        )
    return response
