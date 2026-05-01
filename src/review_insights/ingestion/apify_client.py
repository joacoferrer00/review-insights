"""Fetches Google Maps reviews from Apify and saves raw JSON to data/0_input/."""

import json
import logging
import os
import re
from pathlib import Path

from apify_client import ApifyClient

logger = logging.getLogger(__name__)

_ACTOR_ID = "compass/crawler-google-places"
_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data" / "0_input"


def fetch_reviews(
    urls: list[str],
    max_reviews: int = 100,
    start_date: str | None = None,
) -> list[Path]:
    """Fetch Google Maps reviews for each URL and save as JSON files in data/0_input/.

    Args:
        urls: Google Maps place URLs. First URL = main client, rest = competitors.
        max_reviews: Max reviews to fetch per place.
        start_date: Optional ISO date (YYYY-MM-DD) — only fetch reviews from this date on.

    Returns:
        List of paths to saved JSON files, one per place.
    """
    api_key = os.environ["APIFY_API_KEY"]
    client = ApifyClient(api_key)
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    run_input = {
        "startUrls": [{"url": url} for url in urls],
        "maxReviews": max_reviews,
        "reviewsSort": "newest",
        "reviewsOrigin": "all",
        "maxImages": 0,
        "scrapeContacts": False,
        "scrapeSocialMediaProfiles": {
            "facebooks": False,
            "instagrams": False,
            "youtubes": False,
            "tiktoks": False,
            "twitters": False,
        },
    }
    if start_date:
        run_input["reviewsStartDate"] = start_date

    logger.info("Starting Apify run — %d URLs, max %d reviews each", len(urls), max_reviews)
    run = client.actor(_ACTOR_ID).call(run_input=run_input)
    logger.info("Apify run finished — dataset: %s", run["defaultDatasetId"])

    # The Actor returns one item per place with reviews nested inside.
    # We flatten to a list of review objects, each with the place's title injected,
    # so the ingestion module can process them as a flat array.
    saved_paths: list[Path] = []

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        place_name = item.get("title", "unknown")
        reviews: list[dict] = item.get("reviews", [])

        if not reviews:
            logger.warning("No reviews found for place: %s", place_name)
            continue

        # Inject business name into each review record
        for review in reviews:
            review["title"] = place_name

        slug = _slug(place_name)
        path = _OUTPUT_DIR / f"{slug}_reviews.json"
        path.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved %d reviews for '%s' → %s", len(reviews), place_name, path.name)
        saved_paths.append(path)

    return saved_paths


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
