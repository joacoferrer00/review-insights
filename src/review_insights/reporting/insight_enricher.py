"""Enriches insights.csv rows with LLM-generated text fields."""

import json
import logging
import re
import time
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, field_validator

from review_insights.llm.base import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)

_TOP_QUOTES = 5
_MAX_RETRIES = 3


_LIMITS = {"title": 80, "description": 400, "evidence": 200, "recommendation": 200}


class InsightEnrichment(BaseModel):
    title: str
    description: str
    evidence: str
    recommendation: str

    @field_validator("title", "description", "evidence", "recommendation", mode="before")
    @classmethod
    def truncate(cls, v: object, info) -> str:
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        limit = _LIMITS[info.field_name]
        return v[:limit] if len(v) > limit else v


def enrich_insights(
    insights_df: pd.DataFrame,
    classified_df: pd.DataFrame,
    provider: LLMProvider,
    prompt_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    """Enrich each row in insights_df with title, description, evidence, recommendation.

    Idempotent: skips if output_path already exists.
    Rows without available quotes get null enrichment fields and are not retried.
    """
    if output_path.exists():
        logger.info("insights_enriched.csv already exists — skipping enrichment")
        return pd.read_csv(output_path)

    system_prompt = prompt_path.read_text(encoding="utf-8")
    results = []
    total = len(insights_df)

    for i, (_, row) in enumerate(insights_df.iterrows(), 1):
        quotes = _get_top_quotes(classified_df, row["business_name"], row["main_topic"])
        enriched = _enrich_one(row, quotes, provider, system_prompt)
        result = row.to_dict()
        if enriched:
            result.update(enriched.model_dump())
        else:
            result.update({"title": None, "description": None, "evidence": None, "recommendation": None})
        results.append(result)
        logger.info("Enriched %d/%d — %s / %s", i, total, row["business_name"], row["main_topic"])

    enriched_df = pd.DataFrame(results)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    enriched_df.to_csv(output_path, index=False)
    logger.info("insights_enriched.csv written — %d rows", len(enriched_df))
    return enriched_df


def _get_top_quotes(classified_df: pd.DataFrame, business: str, topic: str) -> list[str]:
    mask = (
        (classified_df["business_name"] == business)
        & (classified_df["main_topic"] == topic)
        & classified_df["text_reference"].notna()
        & (classified_df["text_reference"].str.strip() != "")
    )
    return (
        classified_df[mask]
        .assign(_len=classified_df[mask]["text_reference"].str.len())
        .nlargest(_TOP_QUOTES, "_len")["text_reference"]
        .tolist()
    )


def _enrich_one(
    row: pd.Series,
    quotes: list[str],
    provider: LLMProvider,
    system_prompt: str,
) -> InsightEnrichment | None:
    if not quotes:
        logger.warning("No quotes for %s / %s — skipping", row["business_name"], row["main_topic"])
        return None

    user_msg = json.dumps(
        {
            "business": row["business_name"],
            "topic": row["main_topic"],
            "mentions": int(row["mention_count"]),
            "pct_negative": round(float(row["pct_negative"]), 1),
            "priority_score": round(float(row["priority_score"]), 2),
            "quotes": quotes,
        },
        ensure_ascii=False,
    )

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = provider.complete(
                LLMRequest(system=system_prompt, user=user_msg, temperature=0.0)
            )
            return InsightEnrichment.model_validate_json(_extract_json(response.text))
        except Exception as exc:
            if attempt < _MAX_RETRIES:
                logger.warning(
                    "Retry %d/%d — %s/%s (%s)",
                    attempt, _MAX_RETRIES, row["business_name"], row["main_topic"], exc,
                )
                time.sleep(2**attempt)
            else:
                logger.error(
                    "Failed after %d attempts — %s/%s: %s",
                    _MAX_RETRIES, row["business_name"], row["main_topic"], exc,
                )
    return None


def _extract_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()
