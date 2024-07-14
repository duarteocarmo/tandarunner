import logging
from types import SimpleNamespace

import instructor
from django.db import transaction
from litellm import completion
from pydantic import ValidationError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

import tandarunner.tools.types_prompts as TandaTypes
from tandarunner.models import TrainingInsight

client = instructor.from_litellm(completion)


CONFIG = SimpleNamespace(
    **{
        "TEMP": 0.0,
        "MODEL": "gpt-4o",
    }
)


def fetch_transcript(video_id: str, language_out: str = "en") -> str:
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


def get_insights_from_transcript(
    transcript: str,
) -> TandaTypes.ExtractedInsights:
    return client.chat.completions.create(
        model=CONFIG.MODEL,
        response_model=TandaTypes.ExtractedInsights,
        messages=[
            {
                "role": "system",
                "content": TandaTypes.PROMPT_GET_INSIGHTS_SYSTEM,
            },
            {
                "role": "user",
                "content": TandaTypes.PROMPT_GET_INSIGHTS_USER.format(
                    transcript=transcript
                ),
            },
        ],
        temperature=CONFIG.TEMP,
    )


def get_code_for_insight(
    insights: TandaTypes.Insight,
) -> TandaTypes.PandasDataFrameQA:
    try:
        qa = client.chat.completions.create(
            model=CONFIG.MODEL,
            response_model=TandaTypes.PandasDataFrameQA,
            messages=[
                {
                    "role": "system",
                    "content": TandaTypes.PROMPT_GETQA_SYSTEM,
                },
                {
                    "role": "user",
                    "content": TandaTypes.PROMPT_GET_QA_USER.format(
                        observation=insights.observation,
                        outcome=insights.outcome,
                    ),
                },
            ],
            temperature=CONFIG.TEMP,
        )
    except ValidationError as e:
        logging.error(e)
        qa = TandaTypes.PandasDataFrameQA(code="", cannot_compute=True)

    return qa


def inspect_data():
    existing_insights = TrainingInsight.objects.all()
    for i in existing_insights:
        print("ID: ", i.insight_id)
        print("Source ID: ", i.source_id)
        print("Observation: ", i.data["insight"]["observation"])
        print("Outcome: ", i.data["insight"]["outcome"])
        print("======")


def get_insights_from_video(video_id: str):
    transcript = fetch_transcript(video_id=video_id)
    logging.info("Fetched transcript")

    extracted_insights = get_insights_from_transcript(transcript)
    logging.info("Got insights")

    new_insights = []
    for insight in extracted_insights.insights:
        insight_id = insight.generate_id()

        pandas_qa = get_code_for_insight(insight)

        if pandas_qa.cannot_compute:
            logging.error("Cannot compute insight")
            continue

        new_insight = TrainingInsight(
            insight_id=insight_id,
            source_id=video_id,
            data={
                "insight": insight.model_dump(),
                "code": pandas_qa.model_dump(),
            },
        )
        new_insights.append(new_insight)

    if new_insights:
        with transaction.atomic():
            TrainingInsight.objects.bulk_create(new_insights)


def fetch():
    # video_id = "59aEpVvRXxI"
    # video_id = "4YaDXw3-iws"
    # video_id = "ryEUjCyGvBo"
    # video_id = "FhOr5RLt5HI"
    # video_id = "zpfxSz9ehAo"
    # video_id = "Rhd8xsoOlnU"
    # video_id = "p9LW22WvJug"
    video_id = "ismGjyk7AsU"

    get_insights_from_video(video_id)


def run():
    # fetch()
    inspect_data()
