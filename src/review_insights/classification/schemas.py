from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAIN_TOPICS = Literal[
    "Food Quality",
    "Service Speed",
    "Staff Attitude",
    "Price / Value",
    "Ambiance",
    "Hygiene & Cleanliness",
    "Menu & Options",
    "Booking & Reservations",
    "Delivery & Takeaway",
    "Overall Experience",
]


class TopicMention(BaseModel):
    main_topic: MAIN_TOPICS
    sentiment: Literal["positive", "neutral", "negative"]
    urgency: Literal["low", "medium", "high"]
    is_actionable: bool
    text_reference: str
    classification_confidence: float = Field(ge=0.0, le=1.0)


class ClassificationResult(BaseModel):
    mentions: list[TopicMention] = Field(min_length=1)

    @field_validator("mentions", mode="after")
    @classmethod
    def dedupe_and_cap(cls, v: list[TopicMention]) -> list[TopicMention]:
        """Keep at most 3 mentions, one per distinct main_topic.

        The prompt already instructs the model to return ≤3 distinct topics,
        so violations should be rare. When they happen we fix them here
        silently — no ValidationError, no retry — because a retry would cost
        tokens and the truncated output is still valid and useful.

        Deduplication keeps the first occurrence of each topic (the model tends
        to put the most relevant mention first). Capping happens as we iterate
        so we never process more items than needed.
        """
        seen: set[str] = set()
        result: list[TopicMention] = []
        for mention in v:
            if mention.main_topic not in seen:
                seen.add(mention.main_topic)
                result.append(mention)
            if len(result) == 3:
                break
        return result
