"""
Ingestion module — reads raw Apify Google Maps JSON exports and returns
a normalized flat DataFrame ready for the cleaning stage.

Public API
----------
    load_reviews(paths, source="google_maps") -> pd.DataFrame
"""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Fields required in every record. Missing any raises ValueError at ingestion boundary.
_REQUIRED_FIELDS: frozenset[str] = frozenset({"reviewId", "stars", "publishedAtDate"})

# Maps raw Apify field names to canonical column names. Only these fields are kept.
_COLUMN_MAP: dict[str, str] = {
    "reviewId": "review_id",
    "title": "business_name",
    "stars": "stars",
    "publishedAtDate": "date",
    "text": "text",
    "reviewerNumberOfReviews": "reviewer_reviews_count",
    "isLocalGuide": "is_local_guide",
    "likesCount": "likes_count",
}


def load_reviews(paths: list[Path], source: str = "google_maps") -> pd.DataFrame:
    """Load and normalize reviews from one or more Apify JSON export files.

    Each file must be a JSON array of review objects as exported by the
    Apify Google Maps Reviews scraper. Records from all files are normalized
    to a flat schema and concatenated into a single DataFrame.

    Parameters
    ----------
    paths : list[Path]
        Paths to JSON files to load. Multiple files are concatenated in order.
    source : str
        Label written into the ``source`` column for every row.
        Defaults to ``"google_maps"``. Change this when adding other platforms.

    Returns
    -------
    pd.DataFrame
        Normalized reviews. Columns: review_id, business_name, source, stars,
        date, text, reviewer_reviews_count, is_local_guide, likes_count,
        review_context_raw.

    Raises
    ------
    FileNotFoundError
        If any path does not exist.
    ValueError
        If any record is missing a required field (reviewId, stars, publishedAtDate).
    """
    records: list[dict] = []

    for path in map(Path, paths):
        if not path.exists():
            raise FileNotFoundError(f"Review file not found: {path}")

        raw: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        logger.info("Loaded %d records from %s", len(raw), path.name)

        for record in raw:
            records.append(_normalize_record(record, source))

    df = pd.DataFrame(records)
    logger.info(
        "Ingestion complete — %d rows, %d businesses: %s",
        len(df),
        df["business_name"].nunique(),
        sorted(df["business_name"].unique()),
    )
    return df


def _normalize_record(record: dict, source: str) -> dict:
    """Extract and rename fields from a single raw Apify review record.

    Validates required fields, maps to canonical column names, and
    serializes reviewContext as a JSON string so it survives CSV round-trips.
    All other fields (reviewDetailedRating, textTranslated, reviewUrl, etc.)
    are intentionally discarded.

    Parameters
    ----------
    record : dict
        Raw review object from the Apify JSON export.
    source : str
        Source label to attach to the row.

    Returns
    -------
    dict
        Flat dict with canonical column names, ready for DataFrame construction.

    Raises
    ------
    ValueError
        If any required field is absent or None.
    """
    missing = {f for f in _REQUIRED_FIELDS if record.get(f) is None}
    if missing:
        raise ValueError(
            f"Record missing required fields {missing}: "
            f"reviewId={record.get('reviewId', '<absent>')!r}"
        )

    row = {canonical: record.get(raw_key) for raw_key, canonical in _COLUMN_MAP.items()}
    row["source"] = source
    row["review_context_raw"] = json.dumps(
        record.get("reviewContext") or {}, ensure_ascii=False
    )
    return row
