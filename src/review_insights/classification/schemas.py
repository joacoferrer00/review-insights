from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

# Populated at pipeline startup via set_taxonomy(); validated in TopicMention.
_VALID_TOPICS: frozenset[str] = frozenset()


def load_taxonomy(path: Path) -> frozenset[str]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return frozenset(t["name"] for t in raw["topics"])


def set_taxonomy(topics: frozenset[str]) -> None:
    global _VALID_TOPICS
    _VALID_TOPICS = topics


class TopicMention(BaseModel):
    main_topic: str
    sentiment: Literal["positive", "neutral", "negative"]
    urgency: Literal["low", "medium", "high"]
    is_actionable: bool
    text_reference: str
    classification_confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("main_topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        if _VALID_TOPICS and v not in _VALID_TOPICS:
            raise ValueError(f"Unknown topic: {v!r}. Valid: {sorted(_VALID_TOPICS)}")
        return v


def _dedupe_and_cap_mentions(v: list[TopicMention]) -> list[TopicMention]:
    seen: set[str] = set()
    result: list[TopicMention] = []
    for mention in v:
        if mention.main_topic not in seen:
            seen.add(mention.main_topic)
            result.append(mention)
        if len(result) == 3:
            break
    return result


class ClassificationResult(BaseModel):
    mentions: list[TopicMention] = Field(min_length=1)

    @field_validator("mentions", mode="after")
    @classmethod
    def dedupe_and_cap(cls, v: list[TopicMention]) -> list[TopicMention]:
        return _dedupe_and_cap_mentions(v)


class BatchReviewResult(BaseModel):
    review_idx: int
    mentions: list[TopicMention] = Field(min_length=1)

    @field_validator("mentions", mode="after")
    @classmethod
    def dedupe_and_cap(cls, v: list[TopicMention]) -> list[TopicMention]:
        return _dedupe_and_cap_mentions(v)


class BatchClassificationResult(BaseModel):
    results: list[BatchReviewResult]
