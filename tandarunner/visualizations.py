import logging
import os
import pickle
from datetime import datetime, timedelta

import altair as alt
import numpy
import pandas
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

DAYS_BACK = 180


def get_athlete(access_token) -> dict:
    url = f"{settings.STRAVA_BASE_URL}/athlete"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        raise Exception(
            f"There was an error requesting: {response.status_code}"
        )

    return response.json()


def get_stats(
    access_token: str,
    athlete_id: int,
    base_url: str = settings.STRAVA_BASE_URL,
) -> dict:
    url = f"{base_url}/athletes/{athlete_id}/stats"
    headers = {"Authorization": f"Bearer {access_token}"}
    stats = requests.get(url, headers=headers).json()

    logger.info("Got athlete stats.")
    ytd_total_meters = stats["ytd_run_totals"]["distance"]
    stats["pretty_total_kms"] = ytd_total_meters / 1000

    ytd_total_days = stats["ytd_run_totals"]["moving_time"] / 3600 / 24
    stats["pretty_total_time"] = f"{ytd_total_days:.2f} days"

    return stats


def get_tanda_value(km_per_week: int, pace_sec_per_km: int) -> float:
    marathon_distance = 42.195
    marathon_pace_sec_per_km = (
        17.1
        + 140.0 * numpy.exp(-0.0053 * km_per_week)
        + 0.55 * pace_sec_per_km
    )
    total_marathon_time_secs = marathon_distance * marathon_pace_sec_per_km
    total_marathon_time_hours = total_marathon_time_secs / 3600
    return total_marathon_time_hours


def get_pace_for_distance(
    km_per_week: int, total_marathon_time_hours: float
) -> float:
    marathon_distance = 42.195
    marathon_pace_sec_per_km = (
        total_marathon_time_hours * 3600 / marathon_distance
    )
    pace_sec_per_km = (
        marathon_pace_sec_per_km
        - 17.1
        - 140.0 * numpy.exp(-0.0053 * km_per_week)
    ) / 0.55
    return pace_sec_per_km


def pretty_marathon_time(total_marathon_time_hours: float) -> str:
    hours = int(total_marathon_time_hours)
    minutes = int((total_marathon_time_hours - hours) * 60)
    seconds = int(((total_marathon_time_hours - hours) * 60 - minutes) * 60)
    if seconds >= 30:
        minutes += 1

    return f"{hours} hours {minutes} minutes"


def pace_tick_formatter(value):
    minutes = int(value // 60)
    seconds = int(value % 60)
    return f"{minutes}:{seconds:02d}"


def fetch_activities(access_token: str) -> list:
    url = f"{settings.STRAVA_BASE_URL}/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    after_timestamp = int(
        (datetime.now() - timedelta(days=DAYS_BACK)).timestamp()
    )

    per_page = 200
    page = 1
    all_activities = []

    while True:
        params = {"after": after_timestamp, "page": page, "per_page": per_page}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
        activities = response.json()

        if not activities:
            break

        all_activities.extend(activities)
        if len(activities) < per_page:
            break

        page += 1

    return all_activities


def prepare_data(access_token: str) -> tuple:
    activities = fetch_activities(access_token)

    running_activities = [act for act in activities if act["type"] == "Run"]

    data = {
        "start_date": [act["start_date"] for act in running_activities],
        "distance_meters": [
            float(act["distance"]) for act in running_activities
        ],
        "time_seconds": [act["moving_time"] for act in running_activities],
    }

    df = pandas.DataFrame(data)
    df["start_date"] = pandas.to_datetime(df["start_date"])
    df.set_index("start_date", inplace=True)
    weekly_data = df.resample("W").sum()
    weekly_data["distance_km"] = round(
        weekly_data["distance_meters"] / 1000, 1
    )

    daily_df = df.groupby(df.index.date).sum()
    daily_df.index = pandas.to_datetime(daily_df.index)
    daily_df.index.name = "date"

    daily_df["tanda_day"] = get_tanda_value(
        daily_df["distance_meters"] / 1000 * 7,
        daily_df["time_seconds"] / (daily_df["distance_meters"] / 1000),
    )
    daily_df["tanda_day_pretty"] = pandas.to_datetime(
        daily_df["tanda_day"], unit="h"
    )

    daily_df = daily_df.reset_index()
    daily_df["date"] = pandas.to_datetime(daily_df["date"])
    daily_df.set_index("date", inplace=True)

    num_weeks = 8
    num_days = num_weeks * 7
    rolling = f"{num_days}d"

    daily_df["rolling_distance_meters"] = (
        daily_df["distance_meters"].rolling(window=rolling).sum()
    )
    daily_df["rolling_time_seconds"] = (
        daily_df["time_seconds"].rolling(window=rolling).sum()
    )

    daily_df["rolling_km_per_week"] = (
        daily_df["rolling_distance_meters"] / 1000 / num_weeks
    )
    daily_df["rolling_pace_sec_per_km"] = (
        daily_df["rolling_time_seconds"]
        / daily_df["rolling_distance_meters"]
        * 1000
    )

    daily_df["rolling_tanda_day"] = get_tanda_value(
        daily_df["rolling_km_per_week"], daily_df["rolling_pace_sec_per_km"]
    )

    daily_df["rolling_tanda_day_pretty"] = pandas.to_datetime(
        daily_df["rolling_tanda_day"], unit="h"
    )

    daily_df["type_rolling"] = "Tanda (8 weeks)"
    daily_df["type_daily"] = "Tanda (daily)"

    daily_df["pace_sec_per_km"] = daily_df["time_seconds"] / (
        daily_df["distance_meters"] / 1000
    )
    daily_df["distance_km"] = daily_df["distance_meters"] / 1000

    daily_df = daily_df.sort_values(by="date", ascending=True)
    daily_df["date_factor"] = numpy.exp(numpy.linspace(0, 15, len(daily_df)))

    daily_df["daily_pace_pretty"] = daily_df["pace_sec_per_km"].apply(
        lambda x: f"{int(x//60)}:{int(x%60):02d}"
    )
    daily_df["rolling_pace_pretty"] = daily_df[
        "rolling_pace_sec_per_km"
    ].apply(lambda x: f"{int(x//60)}:{int(x%60):02d}")

    daily_df["rolling_km_per_week_daily_distance"] = (
        daily_df["rolling_km_per_week"] / 7
    )

    daily_df["pretty_rolling_tanda_day"] = daily_df["rolling_tanda_day"].apply(
        pretty_marathon_time
    )
    daily_df["Latest run"] = "Latest run"

    return weekly_data, daily_df, pandas.DataFrame(running_activities)


def viz_weekly_chart(
    weekly_data: pandas.DataFrame,
) -> dict:
    upper_limit = weekly_data["distance_km"].max()

    x = alt.X("start_date:T", scale=alt.Scale(padding=20), title="Week")
    y = alt.Y(
        "distance_km:Q",
        axis=alt.Axis(title="Kilometers"),
        scale=alt.Scale(domain=[0, upper_limit]),
    )

    line_chart = (
        alt.Chart(weekly_data.reset_index())
        .mark_area(
            line={"color": "#ff561b"},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="white", offset=0),
                    alt.GradientStop(color="#ff561b", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
        )
        .encode(
            x=x,
            y=y,
            tooltip=["start_date:T", "distance_km:Q"],
        )
        .properties(
            width=800, height=500, title="Running distance per week (km)"
        )
    )

    points = (
        alt.Chart(weekly_data.reset_index())
        .mark_point(
            filled=True,
            fill="white",
            stroke="#ff561b",
            strokeWidth=2,
            size=50,
            shape="circle",
        )
        .encode(
            x=x,
            y=y,
            tooltip=["start_date:T", "distance_km:Q"],
        )
    )

    return (
        (line_chart + points)
        .properties(
            width="container",
            height=150,
            title="Running distance per week (km)",
        )
        .to_json()
    )


def viz_rolling_tanda(daily_df: pandas.DataFrame) -> dict:
    x = alt.X("date:T", title="Date", scale=alt.Scale(padding=20))
    color = "#d65de0"

    daily_line = (
        alt.Chart(daily_df.reset_index())
        .mark_point(shape="square", filled=True, opacity=0.3)
        .encode(
            x=x,
            y=alt.Y("hoursminutes(tanda_day_pretty):O", title="Tanda day"),
            color=alt.value(color),
            tooltip=[
                alt.Tooltip("tanda_day_pretty", timeUnit="hoursminutes"),
                alt.Tooltip("date", timeUnit="yearmonthdate"),
            ],
        )
    )
    rolling_line = (
        alt.Chart(daily_df.reset_index())
        .mark_line(interpolate="basis")
        .encode(
            x=x,
            y=alt.Y(
                "hoursminutes(rolling_tanda_day_pretty):O",
                title="Tanda trend (8 weeks)",
            ),
            color=alt.value(color),
            tooltip=[
                alt.Tooltip(
                    "rolling_tanda_day_pretty", timeUnit="hoursminutes"
                ),
                alt.Tooltip("date", timeUnit="yearmonthdate"),
            ],
        )
    )

    return (
        (daily_line + rolling_line)
        .properties(
            width="container",
            height=250,
            title="Tanda day vs. 8-week rolling Tanda day",
        )
        .configure_legend(orient="top")
    ).to_json()


def running_heatmap(daily_df: pandas.DataFrame) -> dict:
    daily_df["week_number"] = daily_df.index.isocalendar().week
    daily_df["day_of_the_week_name"] = daily_df.index.strftime("%a")
    heatmap_data = daily_df[
        [
            "week_number",
            "day_of_the_week_name",
            "distance_km",
        ]
    ].sort_values(["week_number"])

    all_days = pandas.date_range(
        heatmap_data.index.min(), heatmap_data.index.max(), freq="D"
    )
    heatmap_data = heatmap_data.reindex(all_days).fillna(0.0)
    heatmap_data["week_number"] = heatmap_data.index.isocalendar().week
    heatmap_data["day_of_the_week_name"] = heatmap_data.index.strftime("%a")
    heatmap_data["month"] = heatmap_data.index.strftime("%b")
    heatmap_data["day_of_the_month"] = heatmap_data.index.day

    upper_limit = (
        heatmap_data["distance_km"].mean()
        + heatmap_data["distance_km"].std() * 1.5
    )

    day_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    heatmap = (
        alt.Chart(heatmap_data)
        .mark_rect(cornerRadius=2)
        .encode(
            x=alt.X(
                "week_number:O",
                axis=alt.Axis(
                    title=None, domain=False, ticks=False, labels=False
                ),
            ),
            y=alt.Y(
                "day_of_the_week_name:O",
                sort=day_order,
                axis=alt.Axis(
                    title=None,
                    domain=False,
                    ticks=False,
                ),
            ),
            color=alt.Color(
                "distance_km:Q",
                scale=alt.Scale(
                    domain=[0, upper_limit],
                    scheme="lightorange",
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip(
                    "distance_km:Q", title="Distance (km)", format=".1f"
                ),
                alt.Tooltip("month:O", title="Month"),
                alt.Tooltip("day_of_the_month:O", title="Day of the month"),
            ],
        )
        .configure_scale(bandPaddingInner=0.20)
        .configure_view(stroke=None)
    )

    return (
        heatmap.properties(
            width="container",
            height=150,
            title="Running heatmap",
        ).interactive()
    ).to_json()


def marathon_predictor(daily_df: pandas.DataFrame) -> dict:
    pace_ticks_values = list(range(240, 60 * 8, 15))

    last_date = max(daily_df.index)
    start_date = last_date - timedelta(days=56)
    daily_df["shape"] = daily_df.index.to_series().apply(
        lambda x: "square" if x == last_date else "circle"
    )
    min_pace, max_pace = (
        daily_df["pace_sec_per_km"].min(),
        daily_df["pace_sec_per_km"].max(),
    )

    daily_line = (
        alt.Chart(
            daily_df.loc[start_date:last_date]
            .reset_index()
            .sort_values("date")
        )
        .mark_point(
            filled=True,
            size=70,
        )
        .encode(
            x=alt.X(
                "distance_km:Q",
                title="Daily Distance (km)",
                axis=alt.Axis(tickCount=int(25 // 5)),
            ),
            y=alt.Y(
                "pace_sec_per_km:Q",
                scale=alt.Scale(
                    reverse=True,
                    zero=False,
                    domain=(min_pace, max_pace),
                ),
                title="Pace (mm:ss)",
                axis=alt.Axis(
                    values=pace_ticks_values,
                    labelExpr="datum.value > 0 ? timeFormat(datum.value * 1000, '%M:%S') : ''",
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "distance_km:Q", title="Distance (km)", format=".1f"
                ),
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("daily_pace_pretty:N", title="Pace (mm:ss/km)"),
            ],
            color=alt.Color(
                "date_factor:Q",
                scale=alt.Scale(scheme="lightgreyred"),
                legend=None,
            ),
        )
    )

    marathon_times = []

    for marathon_time in numpy.arange(2.5, 4.5, 0.25):
        for km_day in range(0, 50, 1):
            km_week = km_day * 7
            pace = get_pace_for_distance(km_week, marathon_time)
            formatted_pace = pace_tick_formatter(pace)
            marathon_times.append(
                {
                    "marathon_time": marathon_time,
                    "km_day": km_day,
                    "km_week": km_week,
                    "pace": pace,
                    "formatted_pace": formatted_pace,
                }
            )

    times_df = pandas.DataFrame(marathon_times)

    marathon_times = (
        alt.Chart(times_df)
        .mark_line(interpolate="basis")
        .encode(
            x=alt.X(
                "km_day:Q",
                title="Daily Distance (km)",
                scale=alt.Scale(
                    domain=[
                        0,
                        daily_df.loc[start_date:last_date].distance_km.max(),
                    ]
                ),
            ),
            y=alt.Y(
                "pace:Q",
                title="Pace (mm:ss)",
                scale=alt.Scale(
                    reverse=True,
                    zero=False,
                    domain=(min_pace, max_pace),
                ),
                axis=alt.Axis(
                    values=pace_ticks_values,
                    labelExpr="datum.value > 0 ? timeFormat(datum.value * 1000, '%M:%S') : ''",
                ),
            ),
            color=alt.Color(
                "marathon_time:N",
                title="Marathon Time",
                scale=alt.Scale(scheme="turbo"),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("km_day:Q", title="Distance (km)"),
                alt.Tooltip("formatted_pace:N", title="Pace (mm:ss)"),
                alt.Tooltip("marathon_time:Q", title="Marathon time (hours)"),
            ],
        )
    )

    daily_df["Legend"] = "Tanda Progression line"

    tooltip = [
        alt.Tooltip(
            "rolling_km_per_week_daily_distance:Q",
            title="Distance (km)",
            format=".1f",
        ),
        alt.Tooltip(
            "rolling_pace_pretty:N",
            title="Pace (s/km)",
        ),
        alt.Tooltip("date:T", title="Date"),
        alt.Tooltip("pretty_rolling_tanda_day:N", title="Marathon Form"),
    ]

    tanda_progression = (
        alt.Chart(
            daily_df.loc[start_date:last_date]
            .reset_index()
            .sort_values("date")
        )
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X(
                "rolling_km_per_week_daily_distance:Q",
                title="Daily Distance (km)",
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                "rolling_pace_sec_per_km:Q",
                title="Pace (mm:ss)",
                scale=alt.Scale(
                    reverse=True,
                    zero=False,
                    domain=(min_pace, max_pace),
                ),
                axis=alt.Axis(
                    values=pace_ticks_values,
                    labelExpr="datum.value > 0 ? timeFormat(datum.value * 1000, '%M:%S') : ''",
                ),
            ),
            tooltip=tooltip,
            order="date",
            color=alt.Color(
                "Legend:N",
                legend=alt.Legend(title=None),
                scale=alt.Scale(
                    domain=["Tanda Progression line"], range=["#87f94c"]
                ),
            ),
        )
    )

    daily_df["Legend"] = "Current form"
    current_form = (
        alt.Chart(
            daily_df.loc[start_date:last_date]
            .reset_index()
            .sort_values("date")
            .tail(1)
        )
        .mark_point(filled=True, size=70, color="#FFAA00")
        .encode(
            x=alt.X(
                "rolling_km_per_week_daily_distance:Q",
                title="Daily Distance (km)",
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(
                "rolling_pace_sec_per_km:Q",
                title="Pace (mm:ss)",
                scale=alt.Scale(
                    reverse=True,
                    zero=False,
                    domain=(min_pace, max_pace),
                ),
                axis=alt.Axis(
                    values=pace_ticks_values,
                    labelExpr="datum.value > 0 ? timeFormat(datum.value * 1000, '%M:%S') : ''",
                ),
            ),
            color=alt.Color(
                "Legend:N",
                legend=alt.Legend(title=None),
                scale=alt.Scale(domain=["Current form"], range=["#142ef5"]),
            ),
            tooltip=tooltip,
        )
    )

    # Create a dataset for the labels
    label_data = times_df[times_df["km_day"] == 10].copy()
    label_data["label"] = label_data["marathon_time"].apply(
        lambda x: f"{int(x)}:{int((x % 1) * 60):02d}"
    )

    # Add text labels
    text_labels = (
        alt.Chart(label_data)
        .mark_text(
            align="center",
            baseline="middle",
            fontSize=15,
            angle=20,
            dy=-10,
        )
        .encode(
            x=alt.X("km_day:Q"),
            y=alt.Y("pace:Q"),
            text="label:N",
            color=alt.Color(
                "marathon_time:N",
                scale=alt.Scale(scheme="turbo"),
                legend=None,
            ),
        )
    )

    return (
        (
            marathon_times
            + daily_line
            + tanda_progression
            + current_form
            + text_labels
        )
        .properties(
            width="container",
            height=400,
            title="Marathon Time Predictor",
        )
        .interactive()
        .configure_legend(orient="top")
    ).to_json()


def get_visualizations(access_token: str, athlete_id: int) -> dict:
    cache_id = f"viz-{access_token}"
    if cache_id in cache:
        logger.info("Found viz data in cache.")
        return cache.get(cache_id)

    weekly_data, daily_df, running_activities = prepare_data(access_token)
    logger.info("Prepared data.")

    results = {
        "weekly_chart": viz_weekly_chart(weekly_data),
        "rolling_tanda": viz_rolling_tanda(daily_df=daily_df),
        "marathon_predictor": marathon_predictor(daily_df=daily_df),
        "running_heatmap": running_heatmap(daily_df=daily_df),
        "running_activities": clean_df(running_activities).to_json(),
    }

    if athlete_id == settings.DUARTE_ATHLETE_ID:
        file_path = os.path.join(
            f"{settings.STATICFILES_DIRS[0]}/dummy/", "temp_viz.pkl"
        )

        with open(file_path, "wb") as f:
            pickle.dump(results, f)
        logger.info("Saved dummy data from Duarte.")

    cache.set(cache_id, results)
    logger.info("Ran computation for graphs and set cache.")

    return results


def get_dummy_visualizations() -> dict:
    file_path = os.path.join(
        f"{settings.STATICFILES_DIRS[0]}/dummy/", "temp_viz.pkl"
    )
    with open(file_path, "rb") as f:
        return pickle.load(f)


def clean_df(df: pandas.DataFrame) -> pandas.DataFrame:
    df = df.copy()
    columns = {
        "name": "name",
        "sport_type": "sport_type",
        "distance": "distance_meters",
        "moving_time": "moving_time_seconds",
        "start_date_local": "date",
        "average_speed": "average_speed_meters_per_second",
        "average_heartrate": "average_heartrate",
        "max_heartrate": "max_heartrate",
    }

    for col in columns.keys():
        if col not in df.columns:
            df[col] = numpy.nan
            logger.warning(f"Column {col} not found in DataFrame.")

    return df[columns.keys()].rename(columns=columns, inplace=False)


def get_dummy_activities() -> pandas.DataFrame:
    return clean_df(pandas.read_csv("./static/dummy/running_activities.csv"))
