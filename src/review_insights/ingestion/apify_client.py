"""Fetches Google Maps reviews from Apify and saves raw JSON to the client's input dir."""

import json
import logging
import os
import re
from pathlib import Path

from apify_client import ApifyClient

from review_insights.config import PlaceConfig

logger = logging.getLogger(__name__)

_ACTOR_ID = "compass/crawler-google-places"


def fetch_reviews(
    places: list[PlaceConfig],
    output_dir: Path,
    max_reviews: int = 100,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[Path]:
    """Fetch Google Maps reviews for each place and save as JSON files.

    Args:
        places: Place configs from the client config (business_name + url + role).
        output_dir: Directory where JSON files will be saved (client's data/0_input/).
        max_reviews: Max reviews to fetch per place.
        start_date: Optional ISO date (YYYY-MM-DD) — only fetch reviews from this date on.
        end_date: Optional ISO date (YYYY-MM-DD) — only fetch reviews up to this date.

    Returns:
        List of paths to saved JSON files, one per place.
    """
    api_key = os.environ["APIFY_API_KEY"]
    client = ApifyClient(api_key)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_input = {
        "startUrls": [
            {"url": p.url, "userData": {"canonical_name": p.business_name}}
            for p in places
        ],
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
    if end_date:
        run_input["reviewsEndDate"] = end_date

    logger.info("Starting Apify run — %d URLs, max %d reviews each", len(places), max_reviews)
    run = client.actor(_ACTOR_ID).call(run_input=run_input)
    logger.info("Apify run finished — dataset: %s", run["defaultDatasetId"])

    # The Actor returns one item per place with reviews nested inside.
    # We flatten to a list of review objects, each with the place's title injected,
    # so the ingestion module can process them as a flat array.
    saved_paths: list[Path] = []

    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        place_name = (item.get("userData") or {}).get("canonical_name") or item.get("title", "unknown")
        reviews: list[dict] = item.get("reviews", [])

        if not reviews:
            logger.warning("No reviews found for place: %s", place_name)
            continue

        # Inject business name into each review record
        for review in reviews:
            review["title"] = place_name

        slug = _slug(place_name)
        path = output_dir / f"{slug}_reviews.json"
        path.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved %d reviews for '%s' → %s", len(reviews), place_name, path.name)
        saved_paths.append(path)

    return saved_paths


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
