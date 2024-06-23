import logging

from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods

from tandarunner.helpers import get_access_token, get_athlete
from tandarunner.visualizations import (
    get_dummy_visualizations,
    get_visualizations,
)

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    user = request.user

    if not user.is_authenticated:
        data = {"athlete": None, "visualizations": get_dummy_visualizations()}
        logger.info("Fetched dummy data for anonymous user.")
    else:
        access_token = get_access_token(user)
        logger.info("Got access token.")
        data = {
            "athlete": get_athlete(access_token),
            "visualizations": get_visualizations(access_token.token),
        }
        logger.info("Fetched viz data for authenticated user.")

    return TemplateResponse(request, "index.html", data)
