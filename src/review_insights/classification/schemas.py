from typing import Literal

from pydantic import BaseModel, Field

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


class ClassificationResult(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    main_topic: MAIN_TOPICS
    subtopic: str | None = None
    urgency: Literal["low", "medium", "high"]
    is_actionable: bool
    classification_confidence: float = Field(ge=0.0, le=1.0)
