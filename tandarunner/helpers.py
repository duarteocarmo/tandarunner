import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from allauth.socialaccount.models import SocialToken
from django.conf import settings
from django.core.cache import cache
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
        raise Exception(
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
    cache_key = f"athlete-{access_token.account.uid}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.info("Found athlete in cache.")
        return cached

    url = f"{settings.STRAVA_BASE_URL}/athlete"
    headers = {"Authorization": f"Bearer {access_token.token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(
            f"There was an error requesting: {response.status_code}"
        )

    result = response.json()
    cache.set(cache_key, result, timeout=settings.CACHE_TTL_ATHLETE)
    logger.info("Fetched and cached athlete profile.")
    return result


def get_access_token(user):
    account_provider = "strava"
    access_token = SocialToken.objects.filter(
        account__user=user, account__provider=account_provider
    ).last()

    if access_token.expires_at <= timezone.now():
        refresh_token(access_token)

    return access_token


def get_athlete_data(user) -> dict:
    """Single entry point for all authenticated athlete data.

    Returns a dict with keys: access_token, athlete, athlete_id, token.
    Reuses existing caches under the hood.
    """
    access_token = get_access_token(user)
    athlete = get_athlete(access_token)
    return {
        "access_token": access_token,
        "athlete": athlete,
        "athlete_id": athlete["id"],
        "token": access_token.token,
    }


def _fetch_activity_chunk(access_token: str, after: int, before: int) -> list:
    url = f"{settings.STRAVA_BASE_URL}/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    per_page = 200
    page = 1
    activities = []

    while True:
        params = {
            "after": after,
            "before": before,
            "page": page,
            "per_page": per_page,
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        batch = response.json()

        if not batch:
            break

        activities.extend(batch)
        if len(batch) < per_page:
            break

        page += 1

    return activities


def _fetch_historical_activities(access_token: str, year_start: int) -> list:
    now = datetime.now()
    chunks = []
    for i in range(1, settings.YEARS_OF_HISTORY):
        start = int(
            (now - timedelta(days=settings.DAYS_PER_YEAR * i)).timestamp()
        )
        end = min(
            int(
                (
                    now - timedelta(days=settings.DAYS_PER_YEAR * (i - 1))
                ).timestamp()
            ),
            year_start,
        )
        if start < end:
            chunks.append((start, end))

    activities = []
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(_fetch_activity_chunk, access_token, after, before)
            for after, before in chunks
        ]
        for future in as_completed(futures):
            activities.extend(future.result())

    logger.info(f"Fetched {len(activities)} historical activities.")
    return activities


def fetch_all_activities(access_token: str, athlete_id: int) -> list:
    now = datetime.now()
    year_start = int(datetime(now.year, 1, 1).timestamp())

    historical_key = f"activities-historical-{athlete_id}"
    historical = cache.get(historical_key)
    if historical is None:
        historical = _fetch_historical_activities(
            access_token, year_start=year_start
        )
        cache.set(
            historical_key,
            historical,
            timeout=settings.CACHE_TTL_ACTIVITIES_HISTORICAL,
        )

    recent_key = f"activities-recent-{athlete_id}"
    recent = cache.get(recent_key)
    if recent is None:
        recent = _fetch_activity_chunk(
            access_token, after=year_start, before=int(now.timestamp())
        )
        cache.set(
            recent_key, recent, timeout=settings.CACHE_TTL_ACTIVITIES_RECENT
        )
        logger.info(f"Fetched {len(recent)} recent activities.")

    return historical + recent
