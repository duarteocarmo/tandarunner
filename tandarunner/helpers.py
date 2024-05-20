from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone
from stravalib import Client


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


def get_athlete(access_token):
    client = Client(access_token=access_token.token)
    return client.get_athlete()
