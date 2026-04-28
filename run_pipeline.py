"""End-to-end pipeline: ingestion → cleaning → classification → aggregation.

Usage:
    python run_pipeline.py

Reads GOOGLE_API_KEY and LLM_MODEL from .env (or environment).
Produces the 3 canonical tables in data/processed/.
"""

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")

import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from review_insights.ingestion import load_reviews
from review_insights.cleaning import clean_reviews
from review_insights.classification import classify_reviews
from review_insights.aggregation import aggregate
from review_insights.llm.gemini_provider import GeminiProvider


def main() -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError("GOOGLE_API_KEY not set — add it to .env")

    model = os.environ.get("LLM_MODEL", "gemini-2.5-flash-preview-04-17")

    raw_paths = [
        Path("data/sample/IDA_reviews_sample.json"),
        Path("data/sample/competitors_reviews_sample.json"),
    ]

    interim_dir = Path("data/interim")
    processed_dir = Path("data/processed")
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # — ingestion —
    t0 = time.time()
    logger.info("Step 1/4 — ingestion")
    raw_df = load_reviews(raw_paths)
    raw_df.to_csv(interim_dir / "raw.csv", index=False)
    logger.info("ingestion done (%.1fs) — %d rows → raw.csv", time.time() - t0, len(raw_df))

    # — cleaning —
    t1 = time.time()
    logger.info("Step 2/4 — cleaning")
    clean_df = clean_reviews(raw_df)
    clean_df.to_csv(interim_dir / "reviews_clean.csv", index=False)
    logger.info(
        "cleaning done (%.1fs) — %d rows (%d with text) → reviews_clean.csv",
        time.time() - t1, len(clean_df), clean_df["has_text"].sum(),
    )

    # — classification —
    t2 = time.time()
    logger.info("Step 3/4 — classification (LLM: %s)", model)
    provider = GeminiProvider(api_key=api_key, model=model)
    classified_df = classify_reviews(clean_df, provider)
    classified_df.to_csv(processed_dir / "reviews_classified.csv", index=False)
    classified_count = classified_df["sentiment"].notna().sum()
    logger.info(
        "classification done (%.1fs) — %d rows classified → reviews_classified.csv",
        time.time() - t2, classified_count,
    )

    # — aggregation —
    t3 = time.time()
    logger.info("Step 4/4 — aggregation")
    aggregated_df, insights_df = aggregate(classified_df)
    aggregated_df.to_csv(processed_dir / "aggregated.csv", index=False)
    insights_df.to_csv(processed_dir / "insights.csv", index=False)
    logger.info("aggregation done (%.1fs)", time.time() - t3)

    total = time.time() - t0
    logger.info(
        "Pipeline complete in %.1fs — %d reviews | %d classified | "
        "aggregated: %d businesses | insights: %d rows",
        total, len(classified_df), classified_count,
        len(aggregated_df), len(insights_df),
    )


if __name__ == "__main__":
    main()
