"""Generates the executive summary narrative and renders the PDF audit report."""

import json
import logging
import re
import time
from datetime import date
from pathlib import Path

import markdown as md
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, field_validator

from review_insights.llm.base import LLMProvider, LLMRequest
from review_insights.reporting.dashboard import (
    chart_sentiment_pie,
    chart_top_topics,
    load_aggregated,
    load_insights,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "executive_summary_prompt.md"
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
) -> ExecutiveSummary:
    """Call LLM once to produce the executive summary narrative for one business.

    Returns a validated ExecutiveSummary. Raises RuntimeError if all retries fail.
    """
    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
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
_OUTPUTS_DIR = Path(__file__).resolve().parents[3] / "outputs" / "reports"
_TMP_DIR = Path(__file__).resolve().parents[3] / "outputs" / "tmp"


def render_pdf(business: str, provider: LLMProvider) -> Path:
    """Render the full audit PDF for one business.

    Orchestrates: LLM exec summary → chart PNGs → Jinja2 HTML → Playwright PDF.
    Returns the path to the generated PDF.
    """
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _TMP_DIR.mkdir(parents=True, exist_ok=True)

    aggregated_df = load_aggregated()
    insights_df = load_insights()

    # ── 1. Executive summary (LLM) ───────────────────────────────────────────
    logger.info("Generating executive summary for %s", business)
    summary = generate_executive_summary(business, aggregated_df, insights_df, provider)

    # ── 2. Export charts to PNG ───────────────────────────────────────────────
    logger.info("Exporting charts for %s", business)
    biz_row = aggregated_df[aggregated_df["business_name"] == business].iloc[0]

    pie_fig = chart_sentiment_pie(biz_row)
    pie_fig.update_layout(template="plotly_white")
    pie_path = _TMP_DIR / f"{_slug(business)}_pie.png"
    pie_fig.write_image(str(pie_path), width=700, height=380)

    topics_fig = chart_top_topics(insights_df, business)
    topics_fig.update_layout(template="plotly_white")
    topics_path = _TMP_DIR / f"{_slug(business)}_topics.png"
    topics_fig.write_image(str(topics_path), width=700, height=380)

    # ── 3. Prepare template data ──────────────────────────────────────────────
    business_insights = (
        insights_df[insights_df["business_name"] == business]
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
        charts={"pie": pie_path.as_uri(), "topics": topics_path.as_uri()},
        css_path=(_TEMPLATES_DIR / "styles.css").as_uri(),
    )

    # ── 5. HTML → PDF via Playwright ─────────────────────────────────────────
    from playwright.sync_api import sync_playwright

    html_tmp = _TMP_DIR / f"{_slug(business)}_report.html"
    html_tmp.write_text(html, encoding="utf-8")

    pdf_path = _OUTPUTS_DIR / f"{_slug(business)}_audit.pdf"
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
