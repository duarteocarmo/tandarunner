import instructor
import pandas
from litellm import completion
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

client = instructor.from_litellm(completion)


def main():
    running_activities = get_data()

    video_id = "59aEpVvRXxI"
    transcript = fetch_transcript(video_id)


def get_data():
    running_activities = pandas.read_csv(
        "../static/dummy/running_activities.csv"
    )
    print(running_activities.shape)

    running_activities.rename(
        columns={
            "distance": "distance_meters",
            "moving_time": "moving_time_seconds",
            "start_date_local": "date",
            "average_speed": "average_speed_meters_per_second",
        },
        inplace=True,
    )
    return running_activities


def fetch_transcript(video_id: str, language_out: str = "en"):
    formatter = TextFormatter()
    available_languages = [
        t.language_code
        for t in YouTubeTranscriptApi.list_transcripts(video_id)
    ]
    if language_out in available_languages:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
    else:
        transcript = (
            YouTubeTranscriptApi.list_transcripts(video_id)
            .find_transcript(available_languages[0:1])
            .translate(language_out)
            .fetch()
        )

    return formatter.format_transcript(transcript)
