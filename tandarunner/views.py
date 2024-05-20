import logging

from allauth.socialaccount.models import SocialToken
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from tandarunner.helpers import get_athlete, refresh_token
from tandarunner.visualizations import get_visualizations

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    user = request.user

    if not user.is_authenticated:
        return TemplateResponse(request, "index.html")

    access_token = SocialToken.objects.filter(
        account__user=user, account__provider="strava"
    ).last()
    if access_token.expires_at <= timezone.now():
        refresh_token(access_token)

    return TemplateResponse(
        request,
        "index.html",
        {
            "athlete": get_athlete(access_token),
            "visualizations": get_visualizations(access_token.token),
        },
    )
