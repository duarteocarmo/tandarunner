import logging
from datetime import timedelta

import requests
from allauth.socialaccount.models import SocialToken
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def refresh_token(access_token):
    """Refreshes a user's Strava access token"""

    strava_client_id = settings.SOCIALACCOUNT_PROVIDERS["strava"]["APP"][
        "client_id"
    ]
    strava_secret = settings.SOCIALACCOUNT_PROVIDERS["strava"]["APP"]["secret"]

    params = {
        "client_id": strava_client_id,
        "client_secret": strava_secret,
        "grant_type": "refresh_token",
        "refresh_token": access_token.token_secret,
    }

    response = requests.post("https://www.strava.com/oauth/token", data=params)

    if response.status_code != 200:
        Exception(
            "Unexpected code while refreshing token: %d" % response.status_code
        )

    response = response.json()
    access_token.token = response["access_token"]
    access_token.expires_at = timezone.now() + timedelta(
        seconds=response["expires_in"]
    )
    access_token.token_secret = response["refresh_token"]
    access_token.save()
    logger.info("Refreshed token!")


def get_athlete(access_token) -> dict:
    url = f"{settings.STRAVA_BASE_URL}/athlete"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(
            f"There was an error requesting: {response.status_code}"
        )

    return response.json()


def get_access_token(user):
    account_provider = "strava"
    access_token = SocialToken.objects.filter(
        account__user=user, account__provider=account_provider
    ).last()

    if access_token.expires_at <= timezone.now():
        refresh_token(access_token)

    return access_token
