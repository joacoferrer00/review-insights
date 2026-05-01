from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent.parent  # repo root: src/review_insights/ → src/ → review-insights/


@dataclass
class PlaceConfig:
    business_name: str
    url: str
    role: str  # "target" or "competitor"


@dataclass
class BrandingConfig:
    primary_color: str = "#1a1a2e"
    logo: str | None = None


@dataclass
class ClientConfig:
    slug: str
    business_name: str
    industry: str
    target: str
    places: list[PlaceConfig]
    branding: BrandingConfig

    # resolved paths
    client_dir: Path = field(init=False)
    data_dir: Path = field(init=False)
    input_dir: Path = field(init=False)
    raw_path: Path = field(init=False)
    clean_path: Path = field(init=False)
    classified_path: Path = field(init=False)
    aggregated_path: Path = field(init=False)
    insights_path: Path = field(init=False)
    enriched_path: Path = field(init=False)
    outputs_dir: Path = field(init=False)

    industry_dir: Path = field(init=False)
    classification_prompt_path: Path = field(init=False)
    enrichment_prompt_path: Path = field(init=False)
    exec_summary_prompt_path: Path = field(init=False)
    taxonomy_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.client_dir = ROOT / "clients" / self.slug
        self.data_dir = self.client_dir / "data"
        self.input_dir = self.data_dir / "0_input"
        self.raw_path = self.data_dir / "1_raw" / "raw.csv"
        self.clean_path = self.data_dir / "2_clean" / "reviews_clean.csv"
        self.classified_path = self.data_dir / "3_classified" / "reviews_classified.csv"
        self.aggregated_path = self.data_dir / "4_aggregated" / "aggregated.csv"
        self.insights_path = self.data_dir / "4_aggregated" / "insights.csv"
        self.enriched_path = self.data_dir / "5_enriched" / "insights_enriched.csv"
        self.outputs_dir = self.client_dir / "outputs"

        self.industry_dir = ROOT / "industries" / self.industry
        self.taxonomy_path = self.industry_dir / "taxonomy.yaml"
        self.classification_prompt_path = self.industry_dir / "prompts" / "classification.md"
        self.enrichment_prompt_path = self.industry_dir / "prompts" / "enrichment.md"
        self.exec_summary_prompt_path = self.industry_dir / "prompts" / "exec_summary.md"

        _ensure_dirs(self)


def _ensure_dirs(cfg: ClientConfig) -> None:
    for p in [
        cfg.input_dir,
        cfg.raw_path.parent,
        cfg.clean_path.parent,
        cfg.classified_path.parent,
        cfg.aggregated_path.parent,
        cfg.enriched_path.parent,
        cfg.outputs_dir,
    ]:
        p.mkdir(parents=True, exist_ok=True)


def load_client_config(slug: str) -> ClientConfig:
    config_path = ROOT / "clients" / slug / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Client config not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    places = [
        PlaceConfig(
            business_name=p["business_name"],
            url=p["url"],
            role=p["role"],
        )
        for p in raw["places"]
    ]

    branding_raw = raw.get("branding", {}) or {}
    branding = BrandingConfig(
        primary_color=branding_raw.get("primary_color", "#1a1a2e"),
        logo=branding_raw.get("logo"),
    )

    return ClientConfig(
        slug=raw["slug"],
        business_name=raw["business_name"],
        industry=raw["industry"],
        target=raw["target"],
        places=places,
        branding=branding,
    )


def load_taxonomy(taxonomy_path: Path) -> frozenset[str]:
    raw = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    return frozenset(t["name"] for t in raw["topics"])


def load_topic_labels(taxonomy_path: Path) -> dict[str, str]:
    """Return {topic_name: label_es} for dashboard display. Falls back to name if label_es absent."""
    raw = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    return {t["name"]: t.get("label_es", t["name"]) for t in raw["topics"]}
