"""End-to-end pipeline: fetch → ingestion → cleaning → classification → aggregation → enrichment → PDF.

Usage:
    python run_pipeline.py --client ida --skip-fetch
    python run_pipeline.py --client ida --limit 20
    python run_pipeline.py --client ida --from-date 2025-01-01

All output paths are resolved from the client config (clients/<slug>/config.yaml).
"""

import argparse
import logging
import os
import re
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

for _noisy in ["httpx", "google_genai", "choreographer", "kaleido"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

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
from review_insights.reporting.report_generator import render_pdf
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
    had_new_data = False  # set to True when new reviews are classified

    # — Step 0: fetch (Apify) —
    if args.skip_fetch:
        logger.info("Step 0/6 — fetch SKIPPED (--skip-fetch)")
    else:
        from review_insights.ingestion.apify_client import fetch_reviews

        start_date: str | None = None
        end_date: str | None = None

        if args.from_date or args.to_date:
            start_date = args.from_date
            end_date = args.to_date
            logger.info("Step 0/6 — fetch (Apify) — date range: %s → %s", start_date or "any", end_date or "any")
        elif args.no_date_filter or not cfg.raw_path.exists():
            logger.info("Step 0/6 — fetch (Apify) — no date filter")
        elif args.backfill:
            existing_dates = pd.read_csv(cfg.raw_path, usecols=["date"])["date"]
            end_date = str(existing_dates.min())[:10]
            logger.info("Step 0/6 — fetch (Apify) — backfill until %s", end_date)
        else:
            existing_dates = pd.read_csv(cfg.raw_path, usecols=["date"])["date"]
            start_date = str(existing_dates.max())[:10]
            logger.info("Step 0/6 — fetch (Apify) — forward from %s", start_date)

        fetch_reviews(
            places=cfg.places,
            output_dir=cfg.input_dir,
            max_reviews=args.limit or 100,
            start_date=start_date,
            end_date=end_date,
        )

    # — Step 1: ingestion —
    json_files = sorted(cfg.input_dir.glob("*.json"))
    if not json_files:
        if cfg.raw_path.exists():
            logger.info("Step 1/6 — ingestion SKIPPED (no JSONs in input_dir, using existing raw.csv)")
            raw_df = pd.read_csv(cfg.raw_path)
        else:
            raise FileNotFoundError(
                f"No JSON files found in {cfg.input_dir}. "
                "Copy your Apify exports there or run without --skip-fetch."
            )
    else:
        logger.info("Step 1/6 — ingestion (%d JSON files)", len(json_files))
        t = time.time()
        new_df = load_reviews(json_files)
        if cfg.raw_path.exists():
            existing = pd.read_csv(cfg.raw_path)
            raw_df = pd.concat([existing, new_df], ignore_index=True)
            raw_df = raw_df.drop_duplicates(subset="review_id", keep="first")
            n_new = len(raw_df) - len(existing)
            logger.info("ingestion — %d new reviews merged (total: %d)", n_new, len(raw_df))
        else:
            raw_df = new_df
            logger.info("ingestion — %d rows loaded", len(raw_df))
        cfg.raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_df.to_csv(cfg.raw_path, index=False)
        logger.info("ingestion done (%.1fs)", time.time() - t)

    # — Step 2: cleaning —
    if cfg.clean_path.exists():
        existing_clean = pd.read_csv(cfg.clean_path)
        existing_ids = set(existing_clean["review_id"])
        new_raw = raw_df[~raw_df["review_id"].isin(existing_ids)]
        if new_raw.empty:
            logger.info("Step 2/6 — cleaning SKIPPED (no new reviews)")
            clean_df = existing_clean
        else:
            logger.info("Step 2/6 — cleaning %d new reviews", len(new_raw))
            t = time.time()
            new_clean = clean_reviews(new_raw)
            clean_df = pd.concat([existing_clean, new_clean], ignore_index=True)
            cfg.clean_path.parent.mkdir(parents=True, exist_ok=True)
            clean_df.to_csv(cfg.clean_path, index=False)
            logger.info("cleaning done (%.1fs) — %d rows total", time.time() - t, len(clean_df))
    else:
        logger.info("Step 2/6 — cleaning")
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
        existing_classified = pd.read_csv(cfg.classified_path)
        done_ids = set(existing_classified["review_id"])
        new_clean = clean_df[~clean_df["review_id"].isin(done_ids)]
        if new_clean.empty:
            logger.info("Step 3/6 — classification SKIPPED (no new reviews)")
            classified_df = existing_classified
        else:
            logger.info("Step 3/6 — classification (%d new reviews, LLM: %s)", len(new_clean), model)
            t = time.time()
            provider = GeminiProvider(api_key=api_key, model=model)
            new_classified = classify_reviews(new_clean, provider, cfg.classification_prompt_path, topics)
            classified_df = pd.concat([existing_classified, new_classified], ignore_index=True)
            cfg.classified_path.parent.mkdir(parents=True, exist_ok=True)
            classified_df.to_csv(cfg.classified_path, index=False)
            had_new_data = True
            logger.info("classification done (%.1fs) — %d new rows", time.time() - t, len(new_classified))
    else:
        logger.info("Step 3/6 — classification (LLM: %s)", model)
        t = time.time()
        provider = GeminiProvider(api_key=api_key, model=model)
        classified_df = classify_reviews(clean_df, provider, cfg.classification_prompt_path, topics)
        cfg.classified_path.parent.mkdir(parents=True, exist_ok=True)
        classified_df.to_csv(cfg.classified_path, index=False)
        had_new_data = True
        classified_count = classified_df["sentiment"].notna().sum()
        logger.info(
            "classification done (%.1fs) — %d rows classified → reviews_classified.csv",
            time.time() - t, classified_count,
        )

    # — Step 4: aggregation (always recomputes — pure pandas, ~50ms) —
    logger.info("Step 4/6 — aggregation")
    t = time.time()
    aggregated_df, insights_df = aggregate(classified_df)
    cfg.aggregated_path.parent.mkdir(parents=True, exist_ok=True)
    aggregated_df.to_csv(cfg.aggregated_path, index=False)
    insights_df.to_csv(cfg.insights_path, index=False)
    logger.info("aggregation done (%.1fs)", time.time() - t)

    # — Step 5: insight enrichment —
    logger.info("Step 5/6 — insight enrichment (LLM: %s)", model)
    t = time.time()
    provider = GeminiProvider(api_key=api_key, model=model)
    enriched_df = enrich_insights(
        insights_df,
        classified_df,
        provider,
        cfg.enrichment_prompt_path,
        cfg.enriched_path,
    )
    logger.info("enrichment done (%.1fs)", time.time() - t)

    # — Step 6: executive summary + PDF —
    _pdf_slug = re.sub(r"[^a-zA-Z0-9]+", "_", cfg.target).strip("_")
    pdf_path = cfg.outputs_dir / "reports" / f"{_pdf_slug}_audit.pdf"
    if not had_new_data and pdf_path.exists():
        logger.info("Step 6/6 — PDF SKIPPED (no new data)")
    else:
        logger.info("Step 6/6 — executive summary + PDF (LLM: %s)", model)
        t = time.time()
        provider = GeminiProvider(api_key=api_key, model=model)
        pdf_path = render_pdf(
            business=cfg.target,
            aggregated_df=aggregated_df,
            enriched_df=enriched_df,
            provider=provider,
            prompt_path=cfg.exec_summary_prompt_path,
            outputs_dir=cfg.outputs_dir / "reports",
        )
        logger.info("PDF done (%.1fs)", time.time() - t)

    logger.info("Pipeline complete in %.1fs", time.time() - t0)
    logger.info("-" * 50)
    streamlit_base = os.environ.get("STREAMLIT_URL", "").rstrip("/")
    if streamlit_base:
        logger.info("Dashboard: %s?client=%s", streamlit_base, cfg.slug)
    else:
        logger.info("Dashboard: (set STREAMLIT_URL in .env)")
    logger.info("Report:    %s", pdf_path)
    logger.info("-" * 50)


if __name__ == "__main__":
    main()
