"""
Cleaning module — normalizes raw ingestion output and prepares reviews
for the classification stage.

Public API
----------
    clean_reviews(df) -> pd.DataFrame
"""

import json
import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 1500

# Apify reviewContext keys we extract → canonical column names.
# All other context keys are intentionally ignored.
_CONTEXT_FIELDS: dict[str, str] = {
    "Tipo de comida": "meal_type",
    "Precio por persona": "price_range",
}


def clean_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and clean raw review data for classification.

    Applies deduplication, date parsing, text normalization, and context
    field extraction. Returns a clean copy — the input DataFrame is not modified.

    Parameters
    ----------
    df : pd.DataFrame
        Raw reviews as returned by ``ingestion.load_reviews``.

    Returns
    -------
    pd.DataFrame
        Cleaned reviews. Adds columns: date_parsed, clean_text,
        has_text, text_length, meal_type, price_range.
        Drops: review_context_raw.

    Notes
    -----
    - Duplicates are removed by review_id (first occurrence kept).
    - Text is stripped, whitespace-collapsed, and truncated to 1500 chars.
    - Rating-only rows (text=null) are kept; has_text=False flags them.
    - English reviews are classified as-is — no translation applied.
    """
    df = df.copy()
    n_in = len(df)

    # --- Dedup ---
    df = df.drop_duplicates(subset="review_id", keep="first")
    n_dupes = n_in - len(df)
    if n_dupes:
        logger.warning("Dropped %d duplicate review_id(s)", n_dupes)

    # --- Date ---
    df["date_parsed"] = (
        pd.to_datetime(df["date"], utc=True).dt.date.astype(str)
    )

    # --- Text ---
    df["clean_text"] = df["text"].apply(_clean_text)
    df["has_text"] = df["clean_text"].str.len() > 0
    df["text_length"] = df["clean_text"].str.len()

    # --- Context fields ---
    context_df = pd.DataFrame(
        df["review_context_raw"].apply(_parse_context).tolist(),
        index=df.index,
    )
    df = pd.concat([df, context_df], axis=1)
    df = df.drop(columns=["review_context_raw"])

    n_with_text = int(df["has_text"].sum())
    logger.info(
        "Cleaning complete — %d rows in, %d dupes dropped, %d with text, %d rating-only",
        n_in,
        n_dupes,
        n_with_text,
        len(df) - n_with_text,
    )
    return df


def _clean_text(text: str | None) -> str:
    """Strip, normalize whitespace, and truncate review text.

    Parameters
    ----------
    text : str or None
        Raw review text from the JSON export.

    Returns
    -------
    str
        Cleaned text, max 1500 characters. Empty string if input is None.
    """
    if not isinstance(text, str):
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text[:_MAX_TEXT_CHARS]


def _parse_context(raw: str) -> dict:
    """Extract meal_type and price_range from a serialized reviewContext string.

    Parameters
    ----------
    raw : str
        JSON string as stored in the review_context_raw column.

    Returns
    -------
    dict
        Always returns keys meal_type and price_range. Values are str or None.
    """
    try:
        ctx = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        ctx = {}

    return {
        canonical: ctx.get(apify_key)
        for apify_key, canonical in _CONTEXT_FIELDS.items()
    }
