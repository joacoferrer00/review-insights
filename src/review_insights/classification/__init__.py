"""
Classification module — calls the LLM for each review with text, validates
the response with Pydantic, and returns the full DataFrame with classification
columns appended.

Public API
----------
    classify_reviews(df, provider) -> pd.DataFrame
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from review_insights.llm.base import LLMProvider, LLMRequest

from .schemas import ClassificationResult

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "classify_review.md"
_MAX_RETRIES = 3

# Classification columns added to the DataFrame.
_CLASSIFICATION_COLS = [
    "sentiment",
    "main_topic",
    "subtopic",
    "urgency",
    "is_actionable",
    "classification_confidence",
    "classified_at",
    "model_used",
]


def classify_reviews(df: pd.DataFrame, provider: LLMProvider) -> pd.DataFrame:
    """Classify all reviews with text using an LLM provider.

    Iterates over rows where has_text=True, calls the LLM for each,
    validates the response with Pydantic, and merges results back into
    the DataFrame. Rating-only rows (has_text=False) pass through with
    null classification fields.

    Already-classified rows (classified_at is not null) are skipped,
    making this safe to resume after an interruption.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned reviews from ``cleaning.clean_reviews``.
    provider : LLMProvider
        Configured LLM provider instance (e.g. GeminiProvider).

    Returns
    -------
    pd.DataFrame
        Input DataFrame with classification columns appended:
        sentiment, main_topic, subtopic, urgency, is_actionable,
        classification_confidence, classified_at, model_used.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    df = df.copy()

    for col in _CLASSIFICATION_COLS:
        if col not in df.columns:
            df[col] = None

    mask = df["has_text"] & df["classified_at"].isna()
    to_classify = df[mask]
    total = len(to_classify)
    skipped = df["has_text"].sum() - total
    logger.info(
        "Starting classification — %d to classify, %d already done, %d rating-only",
        total,
        skipped,
        int((~df["has_text"]).sum()),
    )

    for i, (idx, row) in enumerate(to_classify.iterrows(), 1):
        result = _classify_one(row["clean_text"], provider, system_prompt)

        if result is not None:
            for field, value in result.model_dump().items():
                df.at[idx, field] = value

        df.at[idx, "classified_at"] = datetime.now(timezone.utc).isoformat()
        df.at[idx, "model_used"] = provider.name()

        if i % 10 == 0 or i == total:
            logger.info("Classified %d / %d", i, total)

    failed = int(df["has_text"].sum() - df[df["has_text"]]["main_topic"].notna().sum())
    if failed:
        logger.warning("%d reviews could not be classified after retries", failed)
    logger.info("Classification complete")
    return df


def _classify_one(
    text: str,
    provider: LLMProvider,
    system_prompt: str,
) -> ClassificationResult | None:
    """Call the LLM and validate the result for a single review text.

    Parameters
    ----------
    text : str
        Cleaned review text to classify.
    provider : LLMProvider
        Configured LLM provider.
    system_prompt : str
        Classification system prompt loaded from prompts/classify_review.md.

    Returns
    -------
    ClassificationResult or None
        Parsed result, or None if all retries are exhausted.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = provider.complete(
                LLMRequest(system=system_prompt, user=text, temperature=0.0)
            )
            return ClassificationResult.model_validate_json(_extract_json(response.text))
        except Exception as exc:
            if attempt < _MAX_RETRIES:
                logger.warning("Retry %d/%d (error: %s)", attempt, _MAX_RETRIES, exc)
                time.sleep(2 ** attempt)  # 2s, 4s
            else:
                logger.error("Failed after %d attempts: %s", _MAX_RETRIES, exc)
    return None


def _extract_json(text: str) -> str:
    """Strip markdown code fences from LLM output if present.

    Some models wrap JSON in ```json ... ``` even when told not to.
    """
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()
