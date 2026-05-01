"""End-to-end pipeline: ingestion → cleaning → classification → aggregation → enrichment.

Usage:
    python run_pipeline.py --client ida --skip-fetch
    python run_pipeline.py --client ida --limit 20
    python run_pipeline.py --client ida --from-date 2025-01-01

All output paths are resolved from the client config (clients/<slug>/config.yaml).
"""

import argparse
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

import pandas as pd

from review_insights.config import load_client_config, load_taxonomy
from review_insights.classification.schemas import set_taxonomy
from review_insights.ingestion import load_reviews
from review_insights.cleaning import clean_reviews
from review_insights.classification import classify_reviews
from review_insights.aggregation import aggregate
from review_insights.reporting.insight_enricher import enrich_insights
from review_insights.llm.gemini_provider import GeminiProvider


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review Insights pipeline")
    parser.add_argument("--client", required=True, help="Client slug (e.g. ida)")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip Apify fetch, use existing JSONs")
    parser.add_argument("--limit", type=int, default=None, help="Max reviews per place (Apify only)")
    parser.add_argument("--from-date", default=None, help="Fetch reviews from this date (YYYY-MM-DD)")
    parser.add_argument("--to-date", default=None, help="Fetch reviews up to this date (YYYY-MM-DD)")
    parser.add_argument("--backfill", action="store_true", help="Fetch older reviews (backward from min date in raw.csv)")
    parser.add_argument("--no-date-filter", action="store_true", help="Fetch all reviews with no date filter")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        raise EnvironmentError("LLM_API_KEY not set — add it to .env")

    model = os.environ.get("LLM_MODEL", "gemini-2.5-flash-lite-preview-06-17")

    cfg = load_client_config(args.client)
    topics = load_taxonomy(cfg.taxonomy_path)
    set_taxonomy(topics)

    logger.info("Client: %s | Industry: %s | Target: %s", cfg.slug, cfg.industry, cfg.target)
    logger.info("Paths: %s", cfg.data_dir)

    t0 = time.time()

    # — Step 0: fetch (Apify) —
    if args.skip_fetch:
        logger.info("Step 0/5 — fetch SKIPPED (--skip-fetch)")
    else:
        logger.info("Step 0/5 — fetch (Apify) — not yet implemented; use --skip-fetch")
        raise NotImplementedError("Apify fetch not wired yet — use --skip-fetch to run from existing JSONs")

    # — Step 1: ingestion —
    if cfg.raw_path.exists():
        logger.info("Step 1/5 — ingestion SKIPPED (raw.csv exists)")
        raw_df = pd.read_csv(cfg.raw_path)
    else:
        json_files = sorted(cfg.input_dir.glob("*.json"))
        if not json_files:
            raise FileNotFoundError(
                f"No JSON files found in {cfg.input_dir}. "
                "Copy your Apify exports there or run without --skip-fetch."
            )
        logger.info("Step 1/5 — ingestion (%d JSON files)", len(json_files))
        t = time.time()
        raw_df = load_reviews(json_files)
        cfg.raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_df.to_csv(cfg.raw_path, index=False)
        logger.info("ingestion done (%.1fs) — %d rows → raw.csv", time.time() - t, len(raw_df))

    # — Step 2: cleaning —
    if cfg.clean_path.exists():
        logger.info("Step 2/5 — cleaning SKIPPED (reviews_clean.csv exists)")
        clean_df = pd.read_csv(cfg.clean_path)
    else:
        logger.info("Step 2/5 — cleaning")
        t = time.time()
        clean_df = clean_reviews(raw_df)
        cfg.clean_path.parent.mkdir(parents=True, exist_ok=True)
        clean_df.to_csv(cfg.clean_path, index=False)
        logger.info(
            "cleaning done (%.1fs) — %d rows (%d with text) → reviews_clean.csv",
            time.time() - t, len(clean_df), clean_df["has_text"].sum(),
        )

    # — Step 3: classification —
    if cfg.classified_path.exists():
        logger.info("Step 3/5 — classification SKIPPED (reviews_classified.csv exists)")
        classified_df = pd.read_csv(cfg.classified_path)
    else:
        logger.info("Step 3/5 — classification (LLM: %s)", model)
        t = time.time()
        provider = GeminiProvider(api_key=api_key, model=model)
        classified_df = classify_reviews(clean_df, provider, cfg.classification_prompt_path, topics)
        cfg.classified_path.parent.mkdir(parents=True, exist_ok=True)
        classified_df.to_csv(cfg.classified_path, index=False)
        classified_count = classified_df["sentiment"].notna().sum()
        logger.info(
            "classification done (%.1fs) — %d rows classified → reviews_classified.csv",
            time.time() - t, classified_count,
        )

    # — Step 4: aggregation —
    if cfg.aggregated_path.exists() and cfg.insights_path.exists():
        logger.info("Step 4/5 — aggregation SKIPPED (aggregated.csv and insights.csv exist)")
        aggregated_df = pd.read_csv(cfg.aggregated_path)
        insights_df = pd.read_csv(cfg.insights_path)
    else:
        logger.info("Step 4/5 — aggregation")
        t = time.time()
        aggregated_df, insights_df = aggregate(classified_df)
        cfg.aggregated_path.parent.mkdir(parents=True, exist_ok=True)
        aggregated_df.to_csv(cfg.aggregated_path, index=False)
        insights_df.to_csv(cfg.insights_path, index=False)
        logger.info("aggregation done (%.1fs)", time.time() - t)

    # — Step 5: insight enrichment —
    if cfg.enriched_path.exists():
        logger.info("Step 5/5 — enrichment SKIPPED (insights_enriched.csv exists)")
    else:
        logger.info("Step 5/5 — insight enrichment (LLM: %s)", model)
        t = time.time()
        provider = GeminiProvider(api_key=api_key, model=model)
        enrich_insights(
            insights_df,
            classified_df,
            provider,
            cfg.enrichment_prompt_path,
            cfg.enriched_path,
        )
        logger.info("enrichment done (%.1fs)", time.time() - t)

    logger.info("Pipeline complete in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
