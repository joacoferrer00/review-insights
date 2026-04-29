"""Generates the executive summary narrative and renders the PDF audit report."""

import json
import logging
import re
import time
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, field_validator

from review_insights.llm.base import LLMProvider, LLMRequest

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "executive_summary_prompt.md"
_MAX_RETRIES = 3

_LIMITS = {
    "context": 600,
    "findings": 600,
    "recommendations": 600,
    "competitive_position": 600,
    "next_step": 600,
}


class ExecutiveSummary(BaseModel):
    context: str
    findings: str
    recommendations: str
    competitive_position: str
    next_step: str

    @field_validator("context", "findings", "recommendations", "competitive_position", "next_step", mode="before")
    @classmethod
    def truncate(cls, v: object, info) -> str:
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        limit = _LIMITS[info.field_name]
        return v[:limit] if len(v) > limit else v


def generate_executive_summary(
    business: str,
    aggregated_df: pd.DataFrame,
    insights_enriched_df: pd.DataFrame,
    provider: LLMProvider,
) -> ExecutiveSummary:
    """Call LLM once to produce the executive summary narrative for one business.

    Returns a validated ExecutiveSummary. Raises RuntimeError if all retries fail.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    user_msg = _build_user_message(business, aggregated_df, insights_enriched_df)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = provider.complete(
                LLMRequest(system=system_prompt, user=user_msg, temperature=0.0)
            )
            return ExecutiveSummary.model_validate_json(_extract_json(response.text))
        except Exception as exc:
            if attempt < _MAX_RETRIES:
                logger.warning("Retry %d/%d — exec summary for %s (%s)", attempt, _MAX_RETRIES, business, exc)
                time.sleep(2 ** attempt)
            else:
                logger.error("Failed after %d attempts — exec summary for %s: %s", _MAX_RETRIES, business, exc)

    raise RuntimeError(f"generate_executive_summary failed for {business} after {_MAX_RETRIES} attempts")


def _build_user_message(
    business: str,
    aggregated_df: pd.DataFrame,
    insights_enriched_df: pd.DataFrame,
) -> str:
    row = aggregated_df[aggregated_df["business_name"] == business].iloc[0]

    top_insights = (
        insights_enriched_df[insights_enriched_df["business_name"] == business]
        .sort_values("priority_score", ascending=False)
        .head(5)[["title", "description", "evidence", "recommendation"]]
        .rename_axis(None)
        .reset_index(drop=True)
    )
    insights_list = [
        {
            "rank": i + 1,
            "title": r["title"],
            "description": r["description"],
            "evidence": r["evidence"],
            "recommendation": r["recommendation"],
        }
        for i, r in top_insights.iterrows()
    ]

    competitors = {
        r["business_name"]: {"avg_rating": r["avg_rating"]}
        for _, r in aggregated_df[aggregated_df["business_name"] != business].iterrows()
    }

    payload = {
        "business": business,
        "period": "últimos meses",
        "total_reviews": int(row["total_reviews"]),
        "avg_rating": float(row["avg_rating"]),
        "pct_positive": float(row["pct_positive"]),
        "pct_negative": float(row["pct_negative"]),
        "top_insights": insights_list,
        "competitors": competitors,
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()
