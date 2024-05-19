import logging

from allauth.socialaccount.models import SocialToken
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from tandarunner.helpers import get_athlete, refresh_token

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def index(request: HttpRequest) -> HttpResponse:
    user = request.user

    if not user.is_authenticated:
        return TemplateResponse(request, "index.html")

    print("User is authenticated: ", user)

    access_token = SocialToken.objects.filter(
        account__user=user, account__provider="strava"
    ).last()
    if access_token.expires_at <= timezone.now():
        refresh_token(access_token)

    athlete = get_athlete(access_token)
    print("Athlete name: ", athlete.firstname, athlete.lastname)

    return TemplateResponse(request, "index.html")
