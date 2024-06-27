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


# Example activity
# {
#     "resource_state": 2,
#     "athlete": {"id": 44717295, "resource_state": 1},
#     "name": "Night Run",
#     "distance": 10140.7,
#     "moving_time": 3353,
#     "elapsed_time": 3353,
#     "total_elevation_gain": 85.0,
#     "type": "Run",
#     "sport_type": "Run",
#     "workout_type": None,
#     "id": 10464706155,
#     "start_date": "2023-12-30T21:35:08Z",
#     "start_date_local": "2023-12-30T21:35:08Z",
#     "timezone": "(GMT+00:00) Europe/Lisbon",
#     "utc_offset": 0.0,
#     "location_city": None,
#     "location_state": None,
#     "location_country": None,
#     "achievement_count": 0,
#     "kudos_count": 1,
#     "comment_count": 0,
#     "athlete_count": 224,
#     "photo_count": 0,
#     "map": {
#         "id": "a10464706155",
#         "summary_polyline": "qnhkF|hxv@PW`@qATk@LOh@WXGh@Sl@MdBg@\\ElBc@dA_@\\ErA_@PCtAe@VGLKNItA_@VGTI`BU`@Uh@Mb@Q`@K\\O~@]LAN?HJJ`@NxAVzA@V?Z@HJhAp@bD^jCRhANh@JNPHf@ELFHJT~AZnBRvADl@C~@WhCIvB?rMCbC?lDSnGAFIJSJyALq@BKDKNC`ADhDB\\Fb@BbADTFDJAn@Q|@K^@JFBFBXCjBEhBC|BFlB`@hDLp@Rl@Zr@Nh@^v@Ld@NVPh@Td@Nh@d@dAx@pClA|CZdA^`BNf@P~@^bDn@pEFl@@b@@FDDIoAKc@IcAMq@Q}Au@eF_@yAWq@WiAMW_BmEIOi@aBc@iA_@sAw@cBU{@Um@a@mBO_BJiAEwDH}E?iBE_@KcC@mACcAB}@P_BDiB?qADY@iAEo@ByCFcDAgCJaG?y@JwB?g@?]EYKUOi@k@kCKaABU\\]JEZKl@YTSDIPMHMCCBQ?i@Eq@G]E][}Ak@gDQy@KaAQeAUgAqAsJGk@GIG?oF~AgAb@_@Pk@Hg@P]FQHk@NgBj@q@NmAd@qAXm@Ry@Ly@`@i@Pc@FgA^gAVKNARFZNTJj@@REPOTi@ViD|@MFKJGJAV@x@KdA_@~AIVKJ_Av@UJu@Tq@f@a@`@s@l@]d@Sb@QVaChBcAdA{BdBUVMF_@\\OFg@d@OHsAlA_BrAMNcEbD[Zk@`@[Zo@f@k@n@uA~@aA|@sDxC{BtBe@ZYZE?m@j@_@ROBk@BWGYA[FULIJKVG^Fp@N^PTTJF?DEHDFA\\MHERe@T_BVe@vBcBd@c@~@s@",
#         "resource_state": 2,
#     },
#     "trainer": False,
#     "commute": False,
#     "manual": False,
#     "private": False,
#     "visibility": "followers_only",
#     "flagged": False,
#     "gear_id": None,
#     "start_latlng": [38.72, -9.14],
#     "end_latlng": [38.72, -9.14],
#     "average_speed": 3.024,
#     "max_speed": 4.736,
#     "average_cadence": 84.3,
#     "average_watts": 327.0,
#     "max_watts": 408,
#     "weighted_average_watts": 330,
#     "kilojoules": 1096.4,
#     "device_watts": True,
#     "has_heartrate": True,
#     "average_heartrate": 163.9,
#     "max_heartrate": 179.0,
#     "heartrate_opt_out": False,
#     "display_hide_heartrate_option": True,
#     "elev_high": 74.0,
#     "elev_low": 13.2,
#     "upload_id": 11198939401,
#     "upload_id_str": "11198939401",
#     "external_id": "garmin_ping_312524993028",
#     "from_accepted_tag": False,
#     "pr_count": 0,
#     "total_photo_count": 0,
#     "has_kudoed": False,
# }
