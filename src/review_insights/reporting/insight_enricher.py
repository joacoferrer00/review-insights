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
_METRIC_COLS = ["mention_count", "pct_negative", "priority_score"]

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

    Incremental: if output_path already exists, only re-enriches rows whose
    mention_count, pct_negative, or priority_score changed since the last run.
    Rows with no changes keep their existing enrichment. New topics are enriched fresh.
    """
    system_prompt = prompt_path.read_text(encoding="utf-8")

    if output_path.exists():
        existing = pd.read_csv(output_path)
        to_enrich = _find_changed_rows(insights_df, existing)

        if to_enrich.empty:
            logger.info("enrichment SKIPPED — no metric changes since last run")
            return existing

        logger.info("Re-enriching %d/%d topics (metrics changed)", len(to_enrich), len(insights_df))
        new_enriched = _enrich_rows(to_enrich, classified_df, provider, system_prompt)

        changed_keys = set(zip(to_enrich["business_name"], to_enrich["main_topic"]))
        kept = existing[
            ~existing.apply(lambda r: (r["business_name"], r["main_topic"]) in changed_keys, axis=1)
        ]
        result = pd.concat([kept, new_enriched], ignore_index=True)
    else:
        logger.info("Enriching %d topics (first run)", len(insights_df))
        result = _enrich_rows(insights_df, classified_df, provider, system_prompt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    logger.info("insights_enriched.csv written — %d rows", len(result))
    return result


def _find_changed_rows(insights_df: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    """Return rows from insights_df that are new or have changed metric values vs existing."""
    existing_metrics = existing[["business_name", "main_topic"] + _METRIC_COLS].rename(
        columns={c: f"_old_{c}" for c in _METRIC_COLS}
    )
    merged = insights_df.merge(existing_metrics, on=["business_name", "main_topic"], how="left")

    changed = pd.Series(False, index=merged.index)
    for col in _METRIC_COLS:
        old_col = f"_old_{col}"
        is_new = merged[old_col].isna()
        is_changed = ~is_new & (merged[col].round(4) != merged[old_col].round(4))
        changed |= is_new | is_changed

    return insights_df[changed.values]


def _enrich_rows(
    insights_df: pd.DataFrame,
    classified_df: pd.DataFrame,
    provider: LLMProvider,
    system_prompt: str,
) -> pd.DataFrame:
    """Enrich a set of insight rows with LLM-generated fields. Returns df with enrichment columns."""
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

    return pd.DataFrame(results)


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
