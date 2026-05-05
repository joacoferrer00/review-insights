"""Generates the executive summary narrative and renders the PDF audit report."""

import json
import logging
import re
import time
from datetime import date
from pathlib import Path

import markdown as md
import pandas as pd
import qrcode
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, field_validator

from review_insights.llm.base import LLMProvider, LLMRequest
from review_insights.reporting.dashboard import (
    chart_sentiment_pie,
    chart_top_topics,
)

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3

_LIMITS = {
    "context": 600,
    "findings": 1200,
    "recommendations": 600,
    "competitive_position": 600,
    "next_step": 600,
}


class ExecutiveSummary(BaseModel):
    context: str
    findings: str
    recommendations: str
    competitive_position: str
    next_step: str

    @field_validator("context", "findings", "recommendations", "competitive_position", "next_step", mode="before")
    @classmethod
    def coerce_and_truncate(cls, v: object, info) -> str:
        if isinstance(v, list):
            v = "\n".join(str(item) for item in v)
        if not isinstance(v, str):
            raise ValueError(f"{info.field_name} must be a string")
        limit = _LIMITS[info.field_name]
        return v[:limit] if len(v) > limit else v


def generate_executive_summary(
    business: str,
    aggregated_df: pd.DataFrame,
    insights_enriched_df: pd.DataFrame,
    provider: LLMProvider,
    prompt_path: Path,
) -> ExecutiveSummary:
    """Call LLM once to produce the executive summary narrative for one business.

    Returns a validated ExecutiveSummary. Raises RuntimeError if all retries fail.
    """
    system_prompt = prompt_path.read_text(encoding="utf-8")
    user_msg = _build_user_message(business, aggregated_df, insights_enriched_df)

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = provider.complete(
                LLMRequest(system=system_prompt, user=user_msg, temperature=0.0)
            )
            return ExecutiveSummary.model_validate_json(_extract_json(response.text))
        except Exception as exc:
            if attempt < _MAX_RETRIES:
                logger.warning("Retry %d/%d — exec summary for %s (%s)", attempt, _MAX_RETRIES, business, exc)
                time.sleep(2 ** attempt)
            else:
                logger.error("Failed after %d attempts — exec summary for %s: %s", _MAX_RETRIES, business, exc)

    raise RuntimeError(f"generate_executive_summary failed for {business} after {_MAX_RETRIES} attempts")


def _build_user_message(
    business: str,
    aggregated_df: pd.DataFrame,
    insights_enriched_df: pd.DataFrame,
) -> str:
    row = aggregated_df[aggregated_df["business_name"] == business].iloc[0]

    top_insights = (
        insights_enriched_df[insights_enriched_df["business_name"] == business]
        .sort_values("priority_score", ascending=False)
        .head(5)[["title", "description", "evidence", "recommendation"]]
        .rename_axis(None)
        .reset_index(drop=True)
    )
    insights_list = [
        {
            "rank": i + 1,
            "title": r["title"],
            "description": r["description"],
            "evidence": r["evidence"],
            "recommendation": r["recommendation"],
        }
        for i, r in top_insights.iterrows()
    ]

    competitors = {
        r["business_name"]: {"avg_rating": r["avg_rating"]}
        for _, r in aggregated_df[aggregated_df["business_name"] != business].iterrows()
    }

    payload = {
        "business": business,
        "period": "últimos meses",
        "total_reviews": int(row["total_reviews"]),
        "avg_rating": float(row["avg_rating"]),
        "pct_positive": float(row["pct_positive"]),
        "pct_negative": float(row["pct_negative"]),
        "top_insights": insights_list,
        "competitors": competitors,
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


_TEMPLATES_DIR = Path(__file__).parent / "templates"


_DASHBOARD_BASE = "https://review-insights-audit.streamlit.app"


def _generate_qr_png(client_slug: str, tmp_dir: Path) -> Path:
    url = f"{_DASHBOARD_BASE}?client={client_slug}"
    img = qrcode.make(url)
    path = tmp_dir / "qr.png"
    img.save(str(path))
    return path


def render_pdf(
    business: str,
    client_slug: str,
    aggregated_df: pd.DataFrame,
    enriched_df: pd.DataFrame,
    provider: LLMProvider,
    prompt_path: Path,
    outputs_dir: Path,
    topic_labels: dict[str, str] | None = None,
) -> Path:
    """Render the full audit PDF for one business.

    Orchestrates: LLM exec summary → chart PNGs → Jinja2 HTML → Playwright PDF.
    Returns the path to the generated PDF.
    """
    tmp_dir = outputs_dir.parent / "tmp"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    if topic_labels:
        enriched_df = enriched_df.copy()
        enriched_df["main_topic"] = enriched_df["main_topic"].map(topic_labels).fillna(enriched_df["main_topic"])

    # ── 1. Executive summary (LLM) ───────────────────────────────────────────
    logger.info("Generating executive summary for %s", business)
    summary = generate_executive_summary(business, aggregated_df, enriched_df, provider, prompt_path)

    # ── 2. Export charts + QR to PNG ─────────────────────────────────────────
    logger.info("Exporting charts for %s", business)
    qr_path = _generate_qr_png(client_slug, tmp_dir)
    biz_row = aggregated_df[aggregated_df["business_name"] == business].iloc[0]

    pie_fig = chart_sentiment_pie(biz_row)
    pie_fig.update_layout(template="plotly_white")
    pie_path = tmp_dir / f"{_slug(business)}_pie.png"
    pie_fig.write_image(str(pie_path), width=700, height=380)

    topics_fig = chart_top_topics(enriched_df, business)
    topics_fig.update_layout(template="plotly_white")
    topics_path = tmp_dir / f"{_slug(business)}_topics.png"
    topics_fig.write_image(str(topics_path), width=700, height=380)

    # ── 3. Prepare template data ──────────────────────────────────────────────
    business_insights = (
        enriched_df[enriched_df["business_name"] == business]
        .sort_values("priority_score", ascending=False)
        .to_dict(orient="records")
    )
    benchmark_rows = aggregated_df.to_dict(orient="records")

    # ── 4. Render HTML with Jinja2 ────────────────────────────────────────────
    env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)))
    env.filters["markdown"] = lambda text: md.markdown(text, extensions=["nl2br"])
    template = env.get_template("audit_report.html")

    html = template.render(
        business=business,
        period="últimos meses",
        date=date.today().strftime("%d/%m/%Y"),
        total_reviews=int(biz_row["total_reviews"]),
        avg_rating=float(biz_row["avg_rating"]),
        pct_positive=float(biz_row["pct_positive"]),
        pct_negative=float(biz_row["pct_negative"]),
        summary=summary,
        insights=business_insights,
        benchmark=benchmark_rows,
        charts={"pie": pie_path.as_uri(), "topics": topics_path.as_uri(), "qr": qr_path.as_uri()},
        dashboard_url=f"{_DASHBOARD_BASE}?client={client_slug}",
        css_path=(_TEMPLATES_DIR / "styles.css").as_uri(),
    )

    # ── 5. HTML → PDF via Playwright ─────────────────────────────────────────
    from playwright.sync_api import sync_playwright

    html_tmp = tmp_dir / f"{_slug(business)}_report.html"
    html_tmp.write_text(html, encoding="utf-8")

    pdf_path = outputs_dir / f"{_slug(business)}_audit.pdf"
    logger.info("Rendering PDF for %s → %s", business, pdf_path)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_tmp.as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()

    logger.info("PDF ready: %s", pdf_path)
    return pdf_path


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
