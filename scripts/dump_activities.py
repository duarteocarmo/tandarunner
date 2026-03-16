# /// script
# requires-python = ">=3.12"
# dependencies = ["requests", "polars"]
# ///

import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import polars as pl
import requests

STRAVA_BASE_URL = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
REDIRECT_PORT = 8099
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"

CLIENT_ID = "125463"
CLIENT_SECRET = "eaf68d5ec4c082ee6e700a6c05cffcf29b018952"

OUTPUT_PATH = Path.cwd() / "strava_dump.parquet"


def get_access_token() -> str:
    code = None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal code
            qs = parse_qs(urlparse(self.path).query)
            code = qs.get("code", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Done! You can close this tab.</h1>")

        def log_message(self, *args):
            pass

    auth_url = (
        f"{STRAVA_AUTH_URL}?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=read,activity:read_all"
    )
    print("Opening browser for Strava authorization...")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", REDIRECT_PORT), Handler)
    server.handle_request()
    server.server_close()

    if not code:
        raise RuntimeError("Failed to capture authorization code.")

    resp = requests.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _fetch_activity_chunk(
    access_token: str, after: int, before: int
) -> list[dict]:
    url = f"{STRAVA_BASE_URL}/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    per_page = 200
    page = 1
    activities: list[dict] = []

    while True:
        resp = requests.get(
            url,
            headers=headers,
            params={
                "after": after,
                "before": before,
                "page": page,
                "per_page": per_page,
            },
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        activities.extend(batch)
        if len(batch) < per_page:
            break
        page += 1

    return activities


def fetch_all_activities(access_token: str, years_back: int = 3) -> list[dict]:
    now = datetime.now()
    chunks = []
    for i in range(years_back):
        start = int((now - timedelta(days=365 * (i + 1))).timestamp())
        end = int((now - timedelta(days=365 * i)).timestamp())
        chunks.append((start, end))

    all_activities: list[dict] = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(_fetch_activity_chunk, access_token, after, before)
            for after, before in chunks
        ]
        for future in as_completed(futures):
            all_activities.extend(future.result())

    return all_activities


def main():
    access_token = get_access_token()
    raw = fetch_all_activities(access_token)
    print(f"Fetched {len(raw)} activities total.")

    for act in raw:
        act.pop("map", None)
        act.pop("athlete", None)
        act.pop("resource_state", None)

    df = pl.DataFrame(raw)
    df.write_parquet(OUTPUT_PATH)

    print(f"✅ {len(df)} activities → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
