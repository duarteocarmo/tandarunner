import logging
import os
import pickle
from datetime import datetime, timedelta

import altair as alt
import numpy
import pandas
from django.conf import settings
from django.core.cache import cache
from stravalib import Client

logger = logging.getLogger(__name__)

DAYS_BACK = 180


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


def prepare_data(access_token: str) -> dict:
    client = Client(access_token)
    five_months_ago = datetime.now() - timedelta(days=DAYS_BACK)
    activities = client.get_activities(after=five_months_ago.isoformat())
    running_activities = [act for act in activities if act.type == "Run"]

    data = {
        "start_date": [act.start_date for act in running_activities],
        "distance_meters": [float(act.distance) for act in running_activities],
        "time_seconds": [
            act.moving_time.total_seconds() for act in running_activities
        ],
    }

    df = pandas.DataFrame(data)
    df["start_date"] = pandas.to_datetime(df["start_date"])
    df.set_index("start_date", inplace=True)
    weekly_data = df.resample("W").sum()
    weekly_data["distance_km"] = round(
        weekly_data["distance_meters"] / 1000, 1
    )
    upper_limit = (
        weekly_data["distance_km"].mean()
        + 2 * weekly_data["distance_km"].std()
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
    daily_df["date_factor"] = daily_df.index.factorize()[0]
    daily_df["daily_pace_pretty"] = daily_df["pace_sec_per_km"].apply(
        lambda x: f"{int(x//60)}:{int(x%60):02d}"
    )
    daily_df["rolling_pace_pretty"] = daily_df[
        "rolling_pace_sec_per_km"
    ].apply(lambda x: f"{int(x//60)}:{int(x%60):02d}")

    daily_df["rolling_km_per_week_daily_distance"] = (
        daily_df["rolling_km_per_week"] / 7
    )
    daily_df["Latest run"] = "Latest run"

    return weekly_data, daily_df, upper_limit


def viz_weekly_chart(
    weekly_data: pandas.DataFrame, upper_limit: float
) -> dict:
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
    )

    # Text labels for each point
    text_labels = (
        alt.Chart(weekly_data.reset_index())
        .mark_text(dy=-10, color="black", align="center")
        .encode(
            x=x,
            y=y,
            text=alt.Text("distance_km:Q", format="d"),
        )
    )

    return (
        (line_chart + text_labels)
        .properties(
            width="container",
            height=150,
            title="Running distance per week (km)",
        )
        .interactive()
        .to_json()
    )


def viz_rolling_tanda(daily_df: pandas.DataFrame) -> dict:
    x = alt.X("date:T", title="Date", scale=alt.Scale(padding=20))
    legend = None

    daily_line = (
        alt.Chart(daily_df.reset_index())
        .mark_point(
            shape="triangle",
        )
        .encode(
            x=x,
            y=alt.Y("hoursminutes(tanda_day_pretty):O", title="Tanda day"),
            color=alt.Color(
                "type_daily:N",
                legend=legend,
            ),
            tooltip=[
                alt.Tooltip("tanda_day_pretty", timeUnit="hoursminutes"),
                alt.Tooltip("date", timeUnit="yearmonthdate"),
            ],
        )
    )
    rolling_line = (
        alt.Chart(daily_df.reset_index())
        .mark_line(interpolate="basis", color="#b95cf4")
        .encode(
            x=x,
            y=alt.Y(
                "hoursminutes(rolling_tanda_day_pretty):O",
                title="Tanda trend (8 weeks)",
            ),
            color=alt.Color(
                "type_rolling:N",
                legend=legend,
                scale=alt.Scale(range=["#b95cf4"]),
            ),
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
        .interactive()
        .configure_legend(orient="top")
    ).to_json()


def marathon_predictor(daily_df: pandas.DataFrame) -> dict:
    pace_ticks_values = list(range(240, 60 * 8, 15))

    daily_line = (
        alt.Chart(daily_df.reset_index().sort_values("date"))
        .mark_point(
            filled=True,
            shape="triangle",
            size=60,
        )
        .encode(
            x=alt.X(
                "distance_km:Q",
                title="Daily Distance (km)",
                axis=alt.Axis(
                    tickCount=int(daily_df["distance_km"].max() // 5)
                ),
            ),
            y=alt.Y(
                "pace_sec_per_km:Q",
                scale=alt.Scale(
                    reverse=True,
                    zero=False,
                    domain=(min(pace_ticks_values), max(pace_ticks_values)),
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
            color=alt.condition(
                alt.datum.date_factor == daily_df["date_factor"].max(),
                alt.value("black"),
                alt.Color(
                    "date_factor",
                    scale=alt.Scale(scheme="lightorange"),
                    legend=None,
                ),
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
            x=alt.X("km_day:Q", title="Daily Distance (km)"),
            y=alt.Y(
                "pace:Q",
                title="Pace (mm:ss)",
                scale=alt.Scale(
                    reverse=True,
                    zero=False,
                    domain=(min(pace_ticks_values), max(pace_ticks_values)),
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
                legend=alt.Legend(
                    labelExpr="floor(datum.value) + ':' + (floor((datum.value % 1) * 60) < 10 ? '0' : '') + floor((datum.value % 1) * 60)",
                    title=None,
                ),
            ),
            tooltip=[
                alt.Tooltip("km_day:Q", title="Distance (km)"),
                alt.Tooltip("formatted_pace:N", title="Pace (mm:ss)"),
                alt.Tooltip("marathon_time:Q", title="Marathon time (hours)"),
            ],
        )
    )

    daily_df["Legend"] = "Tanda Progression line"
    tanda_progression = (
        alt.Chart(daily_df.reset_index().sort_values("date")[-56:])
        .mark_trail(strokeCap="square")
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
                    domain=(min(pace_ticks_values), max(pace_ticks_values)),
                ),
                axis=alt.Axis(
                    values=pace_ticks_values,
                    labelExpr="datum.value > 0 ? timeFormat(datum.value * 1000, '%M:%S') : ''",
                ),
            ),
            tooltip=[
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
            ],
            order="date",
            size=alt.Size("date:T", legend=None),
            color=alt.Color(
                "Legend:N",
                legend=alt.Legend(title=None),
                scale=alt.Scale(
                    domain=["Tanda Progression line"], range=["#e739bd"]
                ),
            ),
        )
    )

    return (
        (daily_line + marathon_times + tanda_progression)
        .properties(
            width="container",
            height=300,
            title="Marathon Time Predictor",
        )
        .interactive()
        .configure_legend(orient="top")
    ).to_json()


def get_visualizations(access_token: str) -> dict:
    cache_id = f"viz-{access_token}"
    if cache_id in cache:
        logger.info("Found in cache")
        return cache.get(cache_id)

    weekly_data, daily_df, upper_limit = prepare_data(access_token)
    logger.info("Prepared data.")

    results = {
        "weekly_chart": viz_weekly_chart(weekly_data, upper_limit),
        "rolling_tanda": viz_rolling_tanda(daily_df=daily_df),
        "marathon_predictor": marathon_predictor(daily_df=daily_df),
    }

    logger.info("Ran computation for graphs.")
    cache.set(cache_id, results)

    return results


def get_dummy_visualizations() -> dict:
    file_path = os.path.join(
        f"{settings.STATICFILES_DIRS[0]}/dummy/", "temp_viz.pkl"
    )
    with open(file_path, "rb") as f:
        return pickle.load(f)
