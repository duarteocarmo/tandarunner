import logging

from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods

from tandarunner.helpers import get_access_token, get_athlete
from tandarunner.visualizations import (
    get_dummy_visualizations,
    get_stats,
    get_visualizations,
)

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    user = request.user
    data = {"athlete": None}

    if user.is_authenticated:
        access_token = get_access_token(user)
        athlete = get_athlete(access_token)
        stats = get_stats(access_token.token, athlete["id"])
        data = {"athlete": athlete, "stats": stats}

    return TemplateResponse(request, "index.html", data)


@require_http_methods(["GET"])
def graphs_partial(request: HttpRequest) -> HttpResponse:
    user = request.user

    if not user.is_authenticated:
        data = {"visualizations": get_dummy_visualizations()}
        logger.info("Fetched dummy data for anonymous user.")
    else:
        access_token = get_access_token(user)
        logger.info("Got access token.")

        athlete = get_athlete(access_token)
        athlete_id = athlete["id"]
        visualizations = get_visualizations(access_token.token, athlete_id)
        running_activities = visualizations.pop("running_activities")
        logger.info("Got athlete data.")

        data = {"visualizations": visualizations}

        request.session.update(
            {"athlete": athlete, "running_activities": running_activities}
        )
        logger.info("Prepared graph data.")

    return TemplateResponse(request, "partials/graphs.html", data)


@require_http_methods(["GET"])
def chat_partial(request: HttpRequest) -> HttpResponse:
    return TemplateResponse(request, "partials/chat.html")
