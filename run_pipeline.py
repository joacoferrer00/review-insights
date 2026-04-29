"""End-to-end pipeline: ingestion → cleaning → classification → aggregation → enrichment.

Usage:
    python run_pipeline.py

Reads LLM_API_KEY and LLM_MODEL from .env (or environment).
Produces the canonical tables in data/interim/ and data/processed/.

Each step is skipped if its output file already exists.
Delete the relevant file(s) to force a re-run from that step.
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
from review_insights.reporting.insight_enricher import enrich_insights
from review_insights.llm.gemini_provider import GeminiProvider


def main() -> None:
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise EnvironmentError("LLM_API_KEY not set — add it to .env")

    model = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite-preview-06-17")

    raw_paths = [
        Path("data/sample/IDA_reviews_sample.json"),
        Path("data/sample/competitors_reviews_sample.json"),
    ]

    interim_dir = Path("data/interim")
    processed_dir = Path("data/processed")
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    raw_csv = interim_dir / "raw.csv"
    clean_csv = interim_dir / "reviews_clean.csv"
    classified_csv = processed_dir / "reviews_classified.csv"
    aggregated_csv = processed_dir / "aggregated.csv"
    insights_csv = processed_dir / "insights.csv"
    enriched_csv = processed_dir / "insights_enriched.csv"

    t0 = time.time()

    # — Step 1: ingestion —
    if raw_csv.exists():
        logger.info("Step 1/5 — ingestion SKIPPED (raw.csv exists)")
        import pandas as pd
        raw_df = pd.read_csv(raw_csv)
    else:
        logger.info("Step 1/5 — ingestion")
        t = time.time()
        raw_df = load_reviews(raw_paths)
        raw_df.to_csv(raw_csv, index=False)
        logger.info("ingestion done (%.1fs) — %d rows → raw.csv", time.time() - t, len(raw_df))

    # — Step 2: cleaning —
    if clean_csv.exists():
        logger.info("Step 2/5 — cleaning SKIPPED (reviews_clean.csv exists)")
        import pandas as pd
        clean_df = pd.read_csv(clean_csv)
    else:
        logger.info("Step 2/5 — cleaning")
        t = time.time()
        clean_df = clean_reviews(raw_df)
        clean_df.to_csv(clean_csv, index=False)
        logger.info(
            "cleaning done (%.1fs) — %d rows (%d with text) → reviews_clean.csv",
            time.time() - t, len(clean_df), clean_df["has_text"].sum(),
        )

    # — Step 3: classification —
    if classified_csv.exists():
        logger.info("Step 3/5 — classification SKIPPED (reviews_classified.csv exists)")
        import pandas as pd
        classified_df = pd.read_csv(classified_csv)
    else:
        logger.info("Step 3/5 — classification (LLM: %s)", model)
        t = time.time()
        provider = GeminiProvider(api_key=api_key, model=model)
        classified_df = classify_reviews(clean_df, provider)
        classified_df.to_csv(classified_csv, index=False)
        classified_count = classified_df["sentiment"].notna().sum()
        logger.info(
            "classification done (%.1fs) — %d rows classified → reviews_classified.csv",
            time.time() - t, classified_count,
        )

    # — Step 4: aggregation —
    if aggregated_csv.exists() and insights_csv.exists():
        logger.info("Step 4/5 — aggregation SKIPPED (aggregated.csv and insights.csv exist)")
        import pandas as pd
        aggregated_df = pd.read_csv(aggregated_csv)
        insights_df = pd.read_csv(insights_csv)
    else:
        logger.info("Step 4/5 — aggregation")
        t = time.time()
        aggregated_df, insights_df = aggregate(classified_df)
        aggregated_df.to_csv(aggregated_csv, index=False)
        insights_df.to_csv(insights_csv, index=False)
        logger.info("aggregation done (%.1fs)", time.time() - t)

    # — Step 5: insight enrichment —
    if enriched_csv.exists():
        logger.info("Step 5/5 — enrichment SKIPPED (insights_enriched.csv exists)")
    else:
        logger.info("Step 5/5 — insight enrichment (LLM: %s)", model)
        t = time.time()
        provider = GeminiProvider(api_key=api_key, model=model)
        enrich_insights(insights_df, classified_df, provider)
        logger.info("enrichment done (%.1fs)", time.time() - t)

    logger.info("Pipeline complete in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
