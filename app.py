"""Review Intelligence Dashboard — Streamlit entry point."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# Purge stale review_insights modules from Streamlit's module cache on each r
for _key in list(sys.modules.keys()):
    if "review_insights" in _key:
        del sys.modules[_key]

import copy
import io

import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Review Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Client config ────────────────────────────────────────────────────────────

from review_insights.config import load_client_config, load_topic_labels
from review_insights.i18n import load_strings
from review_insights.reporting.dashboard import (
    chart_rating_benchmark,
    chart_sentiment_benchmark,
    chart_sentiment_pie,
    chart_topic_heatmap,
    chart_topic_sentiment,
    chart_top_topics,
    chart_urgency,
    load_aggregated,
    load_classified,
    load_insights,
)

client_slug = st.query_params.get("client")
if not client_slug:
    st.error("Missing **?client=** parameter. Example: `?client=ida`")
    st.stop()

try:
    cfg = load_client_config(client_slug)
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()

strings = load_strings(cfg.language)
topic_labels = load_topic_labels(cfg.taxonomy_path, cfg.language)

# ── Design tokens — Editorial Intelligence ──────────────────────────────────

PAPER           = "#F5F1E8"
BEIGE           = "#ECE6D4"
INK             = "#0E1116"
INK_MUTED       = "#5C6470"
HAIRLINE        = "#D9D2C0"
HAIRLINE_STRONG = "#B8AE92"
ACCENT          = "#A14A3C"
OCHRE           = "#C49A3C"
FOREST          = "#3E6E55"

DISPLAY_FONT = "'Fraunces', 'IBM Plex Serif', Georgia, serif"
BODY_FONT    = "'Hanken Grotesk', system-ui, sans-serif"

# ── CSS injection ────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,700&family=Hanken+Grotesk:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@300;400;500&display=swap');

/* ── Page canvas ── */
.stApp,
[data-testid="stAppViewContainer"],
section.main,
.main {{
    background-color: {PAPER} !important;
}}
[data-testid="stHeader"] {{
    background-color: {PAPER} !important;
    border-bottom: 1px solid {HAIRLINE};
}}
.block-container {{
    background-color: {PAPER} !important;
    padding-top: 2.4rem !important;
    padding-bottom: 5rem !important;
    max-width: 1320px;
}}

/* ── Sidebar — beige tier of paper ── */
section[data-testid="stSidebar"],
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
    background-color: {BEIGE} !important;
    border-right: 1px solid {HAIRLINE_STRONG};
}}
[data-testid="stSidebar"] * {{
    color: {INK} !important;
    font-family: {BODY_FONT} !important;
}}
[data-testid="stSidebar"] h1 {{
    font-family: {DISPLAY_FONT} !important;
    font-weight: 300 !important;
    font-style: italic;
    letter-spacing: -0.015em;
    font-size: 1.9rem !important;
    line-height: 1.1;
    margin: 0.2rem 0 0.4rem 0 !important;
}}
[data-testid="stSidebar"] p {{
    color: rgba(14,17,22,0.7) !important;
    font-size: 0.84rem !important;
    line-height: 1.45;
}}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    font-weight: 600 !important;
    font-size: 0.66rem !important;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: rgba(14,17,22,0.5) !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(14,17,22,0.18) !important;
    margin: 1.2rem 0 !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background-color: rgba(14,17,22,0.04) !important;
    border: 1px solid rgba(14,17,22,0.22) !important;
    border-radius: 0 !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] svg {{
    color: {INK} !important;
    fill: {INK} !important;
}}

/* ── Global typography ── */
html, body {{
    font-family: {BODY_FONT} !important;
    color: {INK} !important;
    background-color: {PAPER} !important;
}}
h1, h2, h3, h4 {{
    font-family: {DISPLAY_FONT} !important;
    font-weight: 400 !important;
    color: {INK} !important;
    letter-spacing: -0.018em;
}}
h2 {{ font-size: 2.1rem !important; line-height: 1.12; }}
h3 {{ font-size: 1.5rem !important; }}
[data-testid="stMarkdownContainer"] p {{
    font-family: {BODY_FONT};
    color: {INK};
    line-height: 1.55;
}}

/* ── Eyebrow utility ── */
.ri-eyebrow {{
    font-family: {BODY_FONT};
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: {INK_MUTED};
    display: block;
}}

/* ── Section header ── */
.ri-section-eyebrow {{
    font-family: {BODY_FONT};
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: {ACCENT};
    margin-bottom: 0.45rem;
}}
.ri-section-title {{
    font-family: {DISPLAY_FONT};
    font-size: 2.1rem;
    font-weight: 400;
    color: {INK};
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin-bottom: 0.3rem;
}}
.ri-section-subtitle {{
    font-family: {DISPLAY_FONT};
    font-size: 1.3rem;
    font-style: italic;
    font-weight: 300;
    color: {INK_MUTED};
    margin-bottom: 1.6rem;
    line-height: 1.3;
}}

/* ── Tabs — underline only ── */
[data-baseweb="tab-list"] {{
    background-color: transparent !important;
    border-bottom: 1px solid {HAIRLINE} !important;
    gap: 0 !important;
    margin-top: 1.6rem !important;
    margin-bottom: 1rem !important;
}}
button[data-baseweb="tab"] {{
    font-family: {BODY_FONT} !important;
    font-weight: 600 !important;
    font-size: 0.74rem !important;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: {INK_MUTED} !important;
    padding: 0.9rem 1.4rem !important;
    background: transparent !important;
    border-radius: 0 !important;
}}
button[data-baseweb="tab"] span,
button[data-baseweb="tab"] div {{
    font-family: {BODY_FONT} !important;
    font-size: 0.74rem !important;
}}
button[data-baseweb="tab"]:hover {{
    color: {INK} !important;
    background-color: transparent !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {INK} !important;
}}
[data-baseweb="tab-highlight"] {{
    background-color: {INK} !important;
    height: 1.5px !important;
}}
[data-baseweb="tab-border"] {{ background-color: transparent !important; }}

/* ── Material Symbols — tonal icon treatment ── */
[data-testid="stIconMaterial"],
span[role="img"][translate="no"] {{
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;
    color: {OCHRE} !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    font-size: 1rem !important;
    line-height: 1 !important;
    opacity: 0.9;
}}
button[data-baseweb="tab"][aria-selected="true"] span[role="img"][translate="no"] {{
    opacity: 1;
}}
/* Flex container — aligns icon optical-center with uppercase label */
button[data-baseweb="tab"] [data-testid="stMarkdownContainer"] p,
button[data-testid="stDownloadButton"] p {{
    display: inline-flex !important;
    align-items: center !important;
    gap: 0.45rem !important;
    margin: 0 !important;
}}

/* ── Hairlines ── */
hr {{
    border-color: {HAIRLINE} !important;
    opacity: 1;
    margin: 2rem 0 !important;
}}

/* ── Metric — typographic stack ── */
.ri-metric {{
    padding: 0.2rem 0 1.1rem 0;
    border-bottom: 1px solid {HAIRLINE};
}}
.ri-metric-value {{
    font-family: {DISPLAY_FONT};
    font-size: 3.4rem;
    font-weight: 300;
    color: {INK};
    line-height: 1;
    letter-spacing: -0.035em;
    font-feature-settings: "tnum" 1, "lnum" 1;
}}
.ri-metric-value .ri-metric-unit {{
    font-size: 1.4rem;
    font-weight: 400;
    color: {INK_MUTED};
    margin-left: 0.18rem;
    letter-spacing: 0;
}}
.ri-metric-label {{
    font-family: {BODY_FONT};
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: {INK_MUTED};
    margin-top: 0.8rem;
}}

/* ── Chart frame: hairline border, deepens on hover ── */
.ri-chart-title {{
    font-family: {BODY_FONT};
    font-size: 0.66rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: {INK_MUTED};
    padding: 0.4rem 0 0.5rem 0;
}}
[data-testid="stPlotlyChart"] {{
    border: 1px solid {HAIRLINE};
    background: {PAPER};
    transition: border-color 220ms ease, box-shadow 220ms ease;
    padding: 0.3rem;
    overflow: hidden;
}}
/* Hover handled via the chartbox container — the chart itself has pointer-events:none
   (the overlay button captures clicks), so its own :hover never fires. */
[class*="st-key-chartbox_"]:hover [data-testid="stPlotlyChart"] {{
    border-color: {INK};
    box-shadow: 0 12px 32px -20px rgba(14,17,22,0.32);
}}
[role="dialog"] [data-testid="stPlotlyChart"],
[role="dialog"] [data-testid="stPlotlyChart"]:hover {{
    border: none !important;
    padding: 0 !important;
    box-shadow: none !important;
    overflow: visible !important;
}}

/* ── Chart click overlay: invisible button covers the inline chart so any click expands ── */
[class*="st-key-chartbox_"] {{
    position: relative;
    cursor: pointer;
}}
[class*="st-key-chartbox_"] [data-testid="stPlotlyChart"] {{
    pointer-events: none;
}}
/* The button lives inside an stElementContainer; position THAT element to span the chart.
   width/height: 100% are required because Streamlit's emotion-cache sets width: fit-content
   on element containers, which wins over `inset: 0` for absolutely-positioned elements. */
[class*="st-key-chartbox_"] [class*="st-key-expand_"] {{
    position: absolute !important;
    inset: 0 !important;
    margin: 0 !important;
    width: 100% !important;
    height: 100% !important;
    max-width: none !important;
    z-index: 5;
}}
[class*="st-key-chartbox_"] [class*="st-key-expand_"] [data-testid="stButton"],
[class*="st-key-chartbox_"] [class*="st-key-expand_"] [data-testid="stButton"] > div {{
    width: 100% !important;
    height: 100% !important;
}}
[class*="st-key-chartbox_"] [class*="st-key-expand_"] button {{
    width: 100% !important;
    height: 100% !important;
    min-height: 0 !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    opacity: 0 !important;
    cursor: pointer !important;
    padding: 0 !important;
}}

/* ── Dialog (chart fullscreen modal) ── */
[role="dialog"][aria-modal="true"] {{
    max-width: 94vw !important;
    width: 94vw !important;
    background: {PAPER} !important;
    border: 1px solid {HAIRLINE_STRONG} !important;
    border-radius: 0 !important;
    box-shadow: 0 40px 80px -20px rgba(14,17,22,0.45) !important;
}}

/* ── Dataframes ── */
[data-testid="stDataFrame"] {{
    border: 1px solid {HAIRLINE};
    border-radius: 0;
    overflow: hidden;
    background: {PAPER};
}}
[data-testid="stDataFrame"] [role="row"] {{ background: transparent !important; }}

/* ── Download button ── */
[data-testid="stDownloadButton"] button {{
    background: {INK} !important;
    color: {PAPER} !important;
    border: none !important;
    border-radius: 0 !important;
    font-family: {BODY_FONT} !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.7rem !important;
    padding: 0.75rem 1.5rem !important;
}}
[data-testid="stDownloadButton"] button:hover {{
    background: {ACCENT} !important;
    color: {PAPER} !important;
}}

/* ── Multiselect chips ── */
[data-baseweb="tag"] {{
    background-color: {INK} !important;
    border-radius: 0 !important;
}}
[data-baseweb="tag"] span {{ color: {PAPER} !important; }}

/* ── Bordered container becomes top-hairline action card ── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border: none !important;
    border-top: 1px solid {HAIRLINE} !important;
    border-radius: 0 !important;
    padding: 1.6rem 0 0.4rem 0 !important;
    margin: 0 !important;
    background: transparent !important;
}}

/* ── Action plan card typography ── */
.ri-action-topic {{
    font-family: {BODY_FONT};
    font-size: 0.66rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: {ACCENT};
    margin-bottom: 0.4rem;
}}
.ri-action-title {{
    font-family: {DISPLAY_FONT};
    font-size: 1.55rem;
    font-weight: 500;
    color: {INK};
    letter-spacing: -0.012em;
    line-height: 1.2;
}}
.ri-action-rank {{
    font-family: {DISPLAY_FONT};
    font-size: 1rem;
    font-style: italic;
    color: {INK_MUTED};
    margin-right: 0.45rem;
}}
.ri-action-priority {{ text-align: right; }}
.ri-action-priority-value {{
    font-family: {DISPLAY_FONT};
    font-size: 2.6rem;
    font-weight: 300;
    color: {ACCENT};
    line-height: 1;
    letter-spacing: -0.03em;
}}
.ri-action-priority-label {{
    font-family: {BODY_FONT};
    font-size: 0.6rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.2em;
    color: {INK_MUTED};
    margin-top: 0.5rem;
}}
.ri-action-rec {{
    border-left: 2px solid {OCHRE};
    padding: 0.1rem 0 0.1rem 0.9rem;
    margin-top: 0.4rem;
    font-family: {BODY_FONT};
    color: {INK};
    line-height: 1.55;
}}

/* ── Captions ── */
[data-testid="stCaptionContainer"], small {{
    font-family: {BODY_FONT} !important;
    color: {INK_MUTED} !important;
    font-size: 0.76rem !important;
}}

/* ── Material symbols restore ── */
.material-symbols-rounded,
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stSidebarCollapsedControl"] span {{
    font-family: 'Material Symbols Rounded' !important;
}}
</style>
""", unsafe_allow_html=True)

# ── Plotly config ────────────────────────────────────────────────────────────

_PLOTLY_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
}

_CHART_LAYOUT_EXTRAS = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "template": "plotly_white",
    "font": {"color": INK, "family": "Hanken Grotesk, sans-serif", "size": 12.5},
    "colorway": [INK, FOREST, ACCENT, OCHRE, INK_MUTED],
}

# ── Data ────────────────────────────────────────────────────────────────────

def get_data():
    return (
        load_aggregated(cfg.aggregated_path),
        load_insights(cfg.enriched_path, cfg.insights_path, topic_labels),
        load_classified(cfg.classified_path, topic_labels, strings),
    )

agg, insights, classified = get_data()
businesses = agg.business_name.tolist()

# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        f'<div style="font-family:{BODY_FONT};font-size:0.6rem;font-weight:600;'
        f'text-transform:uppercase;letter-spacing:0.24em;'
        f'color:{ACCENT};margin-bottom:0.55rem">'
        f'— Review Intelligence Audit</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"# {cfg.business_name}")
    st.caption(strings["sidebar_subtitle"])
    st.divider()
    default_idx = businesses.index(cfg.target) if cfg.target in businesses else 0
    selected = st.selectbox(strings["label_business_select"], businesses, index=default_idx)
    st.divider()
    last_date = classified["date_parsed"].dropna().max()
    last_date_fmt = last_date.strftime('%b %Y') if hasattr(last_date, 'strftime') else last_date
    st.caption(f"{strings['label_data_through']} **{last_date_fmt}**")
    st.caption(f"{strings['label_total_reviews']} **{len(classified.drop_duplicates('review_id'))}**")

row = agg[agg.business_name == selected].iloc[0]

# ── Metric card helper ───────────────────────────────────────────────────────

def metric(label: str, value: str, unit: str = "") -> str:
    unit_html = f'<span class="ri-metric-unit">{unit}</span>' if unit else ""
    return (
        f'<div class="ri-metric">'
        f'<div class="ri-metric-value">{value}{unit_html}</div>'
        f'<div class="ri-metric-label">{label}</div>'
        f'</div>'
    )


def section(eyebrow: str, title: str, subtitle: str | None = None) -> None:
    subtitle_html = f'<div class="ri-section-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="ri-section-eyebrow">{eyebrow}</div>'
        f'<div class="ri-section-title">{title}</div>'
        f'{subtitle_html}',
        unsafe_allow_html=True,
    )


# Single space: st.dialog requires a non-empty title; space suppresses the visible title bar
@st.dialog(" ", width="large")
def _chart_modal() -> None:
    payload = st.session_state.get("_chart_modal_payload")  # always written immediately before open; one dialog open at a time
    if not payload:
        return
    fig, title = payload
    st.markdown(
        f'<div class="ri-section-eyebrow">EXPANDED VIEW</div>'
        f'<div class="ri-section-title" style="font-size:1.55rem;margin-bottom:1rem">{title}</div>',
        unsafe_allow_html=True,
    )
    big = copy.deepcopy(fig)  # update_layout mutates in place; copy prevents height change leaking to the inline chart
    big.update_layout(height=620, margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(big, use_container_width=True, config=_PLOTLY_CONFIG)


def chart_frame(title: str, fig, key: str) -> None:
    st.markdown(f'<div class="ri-chart-title">{title}</div>', unsafe_allow_html=True)
    with st.container(key=f"chartbox_{key}"):
        st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_CONFIG)
        clicked = st.button(" ", key=f"expand_{key}")
    if clicked:
        st.session_state["_chart_modal_payload"] = (fig, title)
        _chart_modal()

# ── Tabs ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    strings["tab_summary"], strings["tab_issues"], strings["tab_benchmark"],
    strings["tab_action_plan"], strings["tab_data"],
])

# ── Tab 1: Resumen ejecutivo ─────────────────────────────────────────────────

with tab1:
    section(strings["header_summary"], selected)

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    c1.markdown(metric(strings["metric_avg_rating"], f"{row.avg_rating:.1f}", "★"), unsafe_allow_html=True)
    c2.markdown(metric(strings["metric_total_reviews"], f"{int(row.total_reviews):,}"), unsafe_allow_html=True)
    c3.markdown(metric(strings["metric_positive"], f"{row.pct_positive:.0f}", "%"), unsafe_allow_html=True)
    c4.markdown(metric(strings["metric_high_urgency"], str(int(row.high_urgency_count))), unsafe_allow_html=True)

    st.divider()
    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        chart_frame(strings["chart_sentiment_dist"],
                    chart_sentiment_pie(row, _CHART_LAYOUT_EXTRAS, strings),
                    key="sent_pie")
    with col_b:
        chart_frame(strings["chart_top_topics"],
                    chart_top_topics(insights, selected, _CHART_LAYOUT_EXTRAS, strings),
                    key="top_topics")

# ── Tab 2: Desglose de problemas ─────────────────────────────────────────────

with tab2:
    section(strings["header_issues"], selected)
    chart_frame(strings["chart_sentiment"],
                chart_topic_sentiment(classified, selected, _CHART_LAYOUT_EXTRAS, strings),
                key="topic_sent")

    st.divider()
    col_a, col_b = st.columns([1, 2], gap="medium")

    with col_a:
        chart_frame(strings["header_urgency_dist"],
                    chart_urgency(classified, selected, _CHART_LAYOUT_EXTRAS, strings),
                    key="urgency")

    with col_b:
        st.markdown(f'<div class="ri-chart-title">{strings["header_negative_quotes"]}</div>', unsafe_allow_html=True)
        neg = classified[
            (classified.business_name == selected)
            & (classified.sentiment == strings["label_negative"])
            & (classified.text_reference.notna())
        ][["main_topic", "urgency", "stars", "text_reference"]].copy()
        neg.columns = [strings["col_topic"], strings["filter_urgency"], "★", strings["col_quote"]]
        st.dataframe(neg.head(15), use_container_width=True, hide_index=True)

# ── Tab 3: Benchmark ─────────────────────────────────────────────────────────

with tab3:
    section(strings["header_benchmark"], selected, f"{strings['caption_benchmark']} {selected}")

    col_a, col_b = st.columns(2, gap="medium")
    with col_a:
        chart_frame(strings["chart_avg_rating_bench"],
                    chart_rating_benchmark(agg, _CHART_LAYOUT_EXTRAS, strings),
                    key="rating_bench")
    with col_b:
        chart_frame(strings["chart_sentiment_dist_bench"],
                    chart_sentiment_benchmark(agg, _CHART_LAYOUT_EXTRAS, strings),
                    key="sent_bench")

    st.divider()
    chart_frame(strings["header_topic_heatmap"],
                chart_topic_heatmap(insights, _CHART_LAYOUT_EXTRAS),
                key="heatmap")

# ── Tab 4: Plan de acción ─────────────────────────────────────────────────────

with tab4:
    section(strings["header_action_plan"], selected)

    biz_insights = (
        insights[insights.business_name == selected]
        .sort_values("priority_score", ascending=False)
        .reset_index(drop=True)
    )

    if "title" in biz_insights.columns:
        for i, ins in biz_insights.iterrows():
            with st.container(border=True):
                col_title, col_score = st.columns([5, 1])
                with col_title:
                    st.markdown(
                        f'<div class="ri-action-topic">{ins["main_topic"]}</div>'
                        f'<div class="ri-action-title">'
                        f'<span class="ri-action-rank">{i + 1:02d}</span>{ins["title"]}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with col_score:
                    st.markdown(
                        f'<div class="ri-action-priority">'
                        f'<div class="ri-action-priority-value">{round(ins["priority_score"], 1)}</div>'
                        f'<div class="ri-action-priority-label">{strings["label_priority"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(ins["description"])
                st.markdown(
                    f'<div class="ri-action-rec"><strong>{strings["label_recommendation_arrow"]}</strong> '
                    f'{ins["recommendation"]}</div>',
                    unsafe_allow_html=True,
                )
    else:
        cols_show = ["main_topic", "mention_count", "pct_negative", "avg_urgency_score", "priority_score"]
        rename = {
            "main_topic": strings["col_topic"],
            "mention_count": strings["chart_label_mentions"],
            "pct_negative": strings["col_pct_neg"],
            "avg_urgency_score": strings["col_urgency_avg"],
            "priority_score": strings["col_priority_score"],
        }
        display = biz_insights[cols_show].rename(columns=rename)
        display[strings["col_pct_neg"]] = display[strings["col_pct_neg"]].apply(lambda x: f"{x:.0f}%")
        display[strings["col_priority_score"]] = display[strings["col_priority_score"]].round(1)
        st.dataframe(display, use_container_width=True)

    st.caption(strings["caption_priority_score"])

# ── Tab 5: Datos / Descarga ───────────────────────────────────────────────────

with tab5:
    section("Data", strings["header_data"])

    sent_options = [strings["label_positive"], strings["label_neutral"], strings["label_negative"]]
    urg_options = [strings["label_high"], strings["label_medium"], strings["label_low"]]

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        biz_filter = st.multiselect(strings["filter_business"], businesses, default=[selected])
    with col_f2:
        sent_filter = st.multiselect(strings["filter_sentiment"], sent_options, default=sent_options)
    with col_f3:
        urg_filter = st.multiselect(strings["filter_urgency"], urg_options, default=urg_options)

    active_biz = biz_filter if biz_filter else businesses
    filtered = classified[
        classified.business_name.isin(active_biz)
        & (classified.sentiment.isin(sent_filter) | classified.sentiment.isna())
        & (classified.urgency.isin(urg_filter) | classified.urgency.isna())
    ]

    display_cols = [
        "business_name", "stars", "date_parsed", "main_topic",
        "sentiment", "urgency", "text_reference", "clean_text",
    ]
    rename_cols = {
        "business_name": strings["filter_business"],
        "stars": strings["col_rating"],
        "date_parsed": strings["col_date"],
        "main_topic": strings["col_topic"],
        "sentiment": strings["filter_sentiment"],
        "urgency": strings["filter_urgency"],
        "text_reference": strings["col_quote"],
        "clean_text": strings["col_full_review"],
    }

    st.dataframe(
        filtered[display_cols].rename(columns=rename_cols),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(strings["rows_caption"].format(n=len(filtered)))

    buffer = io.BytesIO()
    filtered[display_cols].rename(columns=rename_cols).to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        label=strings["download_button"],
        data=buffer.getvalue(),
        file_name=f"reviews_{selected.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
