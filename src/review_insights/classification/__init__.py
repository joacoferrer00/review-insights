"""
Classification module — calls the LLM for each review with text, validates
the response with Pydantic, and returns a DataFrame with classification columns
appended. Each review with text produces 1–3 rows (one per topic mention);
rating-only reviews produce one row with null classification fields.

Public API
----------
    classify_reviews(df, provider) -> pd.DataFrame
"""

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

# Classification columns produced by this module.
# These are excluded from the base row dict when building mention rows,
# so stale values from a previous partial run never bleed into new output.
_CLASSIFICATION_COLS = [
    "mention_id",
    "sentiment",
    "main_topic",
    "text_reference",
    "urgency",
    "is_actionable",
    "classification_confidence",
    "classified_at",
    "model_used",
]


def classify_reviews(df: pd.DataFrame, provider: LLMProvider) -> pd.DataFrame:
    """Classify all reviews with text using an LLM provider.

    For each review where has_text=True and not yet classified, calls the LLM
    and expands the result into 1–3 rows — one per distinct topic mention.
    Rating-only reviews (has_text=False) pass through unchanged with null
    classification fields.

    Idempotent: reviews whose review_id already has a classified_at value are
    skipped. Safe to call again after an interruption.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned reviews from ``cleaning.clean_reviews``.
    provider : LLMProvider
        Configured LLM provider instance (e.g. GeminiProvider).

    Returns
    -------
    pd.DataFrame
        One row per (review_id, mention_id). Reviews that mention multiple
        distinct topics produce more rows than they contributed to the input.
        Added columns: mention_id, sentiment, main_topic, text_reference,
        urgency, is_actionable, classification_confidence, classified_at,
        model_used.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    df = df.copy()

    for col in _CLASSIFICATION_COLS:
        if col not in df.columns:
            df[col] = None

    # Skip any review_id that has at least one classified_at set from a prior run.
    done_ids = set(df.loc[df["has_text"] & df["classified_at"].notna(), "review_id"])

    done_rows = df[df["review_id"].isin(done_ids)]
    rating_only = df[~df["has_text"]]
    # One row per unique review_id — drop_duplicates guards against partially-
    # exploded rows left behind by a previous interrupted run.
    to_classify = (
        df[df["has_text"] & ~df["review_id"].isin(done_ids)]
        .drop_duplicates(subset="review_id")
    )

    total = len(to_classify)
    logger.info(
        "Starting classification — %d to classify, %d already done, %d rating-only",
        total,
        len(done_ids),
        len(rating_only),
    )

    new_rows: list[dict] = []
    for i, (_, row) in enumerate(to_classify.iterrows(), 1):
        result = _classify_one(row["clean_text"], provider, system_prompt)

        # Strip any stale classification values so they don't carry into new rows.
        base = {k: v for k, v in row.to_dict().items() if k not in _CLASSIFICATION_COLS}
        classified_at = datetime.now(timezone.utc).isoformat()

        if result is not None:
            for mention_id, mention in enumerate(result.mentions, start=1):
                mention_row = base.copy()
                mention_row["mention_id"] = mention_id
                mention_row.update(mention.model_dump())
                mention_row["classified_at"] = classified_at
                mention_row["model_used"] = provider.name()
                _check_text_reference(mention.text_reference, row["clean_text"], row["review_id"])
                new_rows.append(mention_row)
        else:
            # All retries exhausted. Keep one row with null classification fields
            # but set classified_at so this review is not retried on the next run.
            failed_row = base.copy()
            for col in _CLASSIFICATION_COLS:
                failed_row.setdefault(col, None)
            failed_row["classified_at"] = classified_at
            failed_row["model_used"] = provider.name()
            new_rows.append(failed_row)

        if i % 10 == 0 or i == total:
            logger.info("Classified %d / %d", i, total)

    parts = [done_rows, rating_only]
    if new_rows:
        parts.append(pd.DataFrame(new_rows))

    result_df = pd.concat(parts, ignore_index=True)

    failed = sum(1 for r in new_rows if r.get("main_topic") is None)
    if failed:
        logger.warning("%d reviews could not be classified after retries", failed)
    logger.info("Classification complete — %d total rows", len(result_df))

    return result_df


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
        Parsed and validated result, or None if all retries are exhausted.
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
                time.sleep(2**attempt)  # 2s, 4s
            else:
                logger.error("Failed after %d attempts: %s", _MAX_RETRIES, exc)
    return None


def _check_text_reference(text_reference: str, clean_text: str, review_id: str) -> None:
    """Warn if text_reference looks like a paraphrase rather than a verbatim quote.

    Checks word-level overlap: if fewer than 80% of the words in text_reference
    appear in clean_text (case-insensitive), the model likely didn't quote literally.
    Soft check only — the mention is never discarded.
    """
    ref_words = text_reference.lower().split()
    if not ref_words:
        return
    text_words = set(clean_text.lower().split())
    overlap = sum(1 for w in ref_words if w in text_words) / len(ref_words)
    if overlap < 0.8:
        logger.warning(
            "text_reference may not be verbatim (review_id=%s): %r",
            review_id,
            text_reference,
        )


def _extract_json(text: str) -> str:
    """Strip markdown code fences from LLM output if present."""
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()
