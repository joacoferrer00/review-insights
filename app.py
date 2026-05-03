"""Review Intelligence Dashboard — Streamlit entry point."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

# Purge stale review_insights modules from Streamlit's module cache on each rerun
for _key in list(sys.modules.keys()):
    if "review_insights" in _key:
        del sys.modules[_key]

import io
from pathlib import Path

import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Review Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Client config ────────────────────────────────────────────────────────────

from review_insights.config import load_client_config, load_topic_labels
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

topic_labels = load_topic_labels(cfg.taxonomy_path)

# ── Brand color derivation ───────────────────────────────────────────────────

brand_hex = cfg.branding.primary_color.lstrip("#")
_br, _bg_c, _bb = int(brand_hex[0:2], 16), int(brand_hex[2:4], 16), int(brand_hex[4:6], 16)
brand_rgba_hover = f"rgba({_br},{_bg_c},{_bb},0.25)"

# ── Design tokens ────────────────────────────────────────────────────────────

BG      = "#0d1117"
SURFACE = "#161b22"
BORDER  = "#30363d"
TEXT    = "#e6edf3"
MUTED   = "#8b949e"
ACCENT  = "#4a90d9"
BRAND   = cfg.branding.primary_color

# ── CSS injection ────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;600&family=DM+Sans:wght@400;600;700&display=swap');

/* ── Fondo general ── */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > section,
section.main,
.main {{
    background-color: {BG} !important;
}}
[data-testid="stHeader"] {{
    background-color: {BG} !important;
    border-bottom: 1px solid {BORDER};
}}
.block-container {{
    background-color: {BG} !important;
    padding-top: 2rem !important;
}}

/* ── Sidebar ── */
[data-testid="stSidebar"],
[data-testid="stSidebarContent"] {{
    background-color: {BRAND} !important;
}}
[data-testid="stSidebar"] * {{
    color: #e6edf3 !important;
    font-family: 'DM Sans', sans-serif !important;
}}
[data-testid="stSidebar"] .stCaption p,
[data-testid="stSidebar"] p {{
    color: rgba(230,237,243,0.65) !important;
}}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: rgba(230,237,243,0.5) !important;
}}
[data-testid="stSidebar"] hr {{
    border-color: rgba(230,237,243,0.15) !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{
    background-color: {brand_rgba_hover} !important;
    border-color: rgba(230,237,243,0.2) !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] svg {{
    color: #e6edf3 !important;
    fill: #e6edf3 !important;
}}

/* ── Tipografía global ── */
html, body {{
    font-family: 'DM Sans', sans-serif !important;
    color: {TEXT} !important;
    background-color: {BG} !important;
}}
h1, h2, h3, h4 {{
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 700 !important;
    color: {TEXT} !important;
}}

/* ── Tabs ── */
[data-baseweb="tab-list"] {{
    background-color: {BG} !important;
    border-bottom: 1px solid {BORDER} !important;
    gap: 0 !important;
    margin-top: 1.5rem !important;
}}
button[data-baseweb="tab"] {{
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    color: {MUTED} !important;
    padding: 0.6rem 1.4rem !important;
    background: transparent !important;
    border-radius: 0 !important;
}}
button[data-baseweb="tab"] span,
button[data-baseweb="tab"] div {{
    font-size: 1.2rem !important;
    font-family: 'DM Sans', sans-serif !important;
}}
button[data-baseweb="tab"]:hover {{
    color: {TEXT} !important;
    background-color: {SURFACE} !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {TEXT} !important;
    background: transparent !important;
}}
[data-baseweb="tab-highlight"] {{
    background-color: {ACCENT} !important;
    height: 2px !important;
}}
[data-baseweb="tab-border"] {{
    background-color: transparent !important;
}}

/* ── Divider ── */
hr {{
    border-color: {BORDER} !important;
    opacity: 0.6;
}}

/* ── Metric cards ── */
.ri-metric-card {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 1rem 1.25rem;
}}
.ri-metric-value {{
    font-family: 'DM Mono', monospace;
    font-size: 1.9rem;
    font-weight: 600;
    color: {ACCENT};
    line-height: 1.1;
}}
.ri-metric-label {{
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {MUTED};
    margin-top: 5px;
}}

/* ── Dataframes ── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    overflow: hidden;
}}
</style>
""", unsafe_allow_html=True)

# ── Plotly config ────────────────────────────────────────────────────────────

_PLOTLY_CONFIG = {
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
        "hoverClosestCartesian", "hoverCompareCartesian", "toggleSpikelines",
    ],
    "displaylogo": False,
}

_CHART_LAYOUT_EXTRAS = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "template": "plotly_dark",
    "font": {"color": TEXT, "family": "DM Sans"},
}

# ── Data ────────────────────────────────────────────────────────────────────

def get_data():
    return (
        load_aggregated(cfg.aggregated_path),
        load_insights(cfg.enriched_path, cfg.insights_path, topic_labels),
        load_classified(cfg.classified_path, topic_labels),
    )

agg, insights, classified = get_data()
businesses = agg.business_name.tolist()

# ── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📊 Review Intelligence")
    st.caption(f"Análisis de reseñas — {cfg.business_name}")
    st.divider()
    default_idx = businesses.index(cfg.target) if cfg.target in businesses else 0
    selected = st.selectbox("Negocio analizado", businesses, index=default_idx)
    st.divider()
    last_date = classified["date_parsed"].dropna().max()
    st.caption(f"Datos hasta: **{last_date.strftime('%b %Y') if hasattr(last_date, 'strftime') else last_date}**")
    st.caption(f"Total reseñas: **{len(classified.drop_duplicates('review_id'))}**")

row = agg[agg.business_name == selected].iloc[0]

# ── Metric card helper ───────────────────────────────────────────────────────

def metric_card(label: str, value: str) -> str:
    return (
        f'<div class="ri-metric-card">'
        f'<div class="ri-metric-value">{value}</div>'
        f'<div class="ri-metric-label">{label}</div>'
        f'</div>'
    )

# ── Tabs ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Resumen", "🔍 Problemas", "⚖️ Benchmark", "🎯 Plan de acción", "📥 Datos"
])

# ── Tab 1: Resumen ejecutivo ─────────────────────────────────────────────────

with tab1:
    st.subheader(f"Resumen ejecutivo — {selected}")

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card("Rating promedio", f"{row.avg_rating:.1f} ⭐"), unsafe_allow_html=True)
    c2.markdown(metric_card("Total reseñas", str(int(row.total_reviews))), unsafe_allow_html=True)
    c3.markdown(metric_card("Sentiment positivo", f"{row.pct_positive:.0f}%"), unsafe_allow_html=True)
    c4.markdown(metric_card("Urgencias altas", str(int(row.high_urgency_count))), unsafe_allow_html=True)

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Distribución de sentiment**")
        st.plotly_chart(chart_sentiment_pie(row, _CHART_LAYOUT_EXTRAS), use_container_width=True, config=_PLOTLY_CONFIG)
    with col_b:
        st.markdown("**Temas más mencionados**")
        st.plotly_chart(chart_top_topics(insights, selected, _CHART_LAYOUT_EXTRAS), use_container_width=True, config=_PLOTLY_CONFIG)

# ── Tab 2: Desglose de problemas ─────────────────────────────────────────────

with tab2:
    st.subheader(f"Desglose por tema — {selected}")
    st.plotly_chart(chart_topic_sentiment(classified, selected, _CHART_LAYOUT_EXTRAS), use_container_width=True, config=_PLOTLY_CONFIG)

    st.divider()
    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.markdown("**Distribución de urgencia**")
        st.plotly_chart(chart_urgency(classified, selected, _CHART_LAYOUT_EXTRAS), use_container_width=True, config=_PLOTLY_CONFIG)

    with col_b:
        st.markdown("**Citas negativas destacadas**")
        neg = classified[
            (classified.business_name == selected)
            & (classified.sentiment == "Negativo")
            & (classified.text_reference.notna())
        ][["main_topic", "urgency", "stars", "text_reference"]].copy()
        neg.columns = ["Tema", "Urgencia", "⭐", "Cita"]
        st.dataframe(neg.head(15), use_container_width=True, hide_index=True)

# ── Tab 3: Benchmark ─────────────────────────────────────────────────────────

with tab3:
    st.subheader("Benchmark entre negocios")
    st.caption(f"Negocio destacado en azul: {selected}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Rating promedio**")
        st.plotly_chart(chart_rating_benchmark(agg, _CHART_LAYOUT_EXTRAS), use_container_width=True, config=_PLOTLY_CONFIG)
    with col_b:
        st.markdown("**Distribución de sentiment**")
        st.plotly_chart(chart_sentiment_benchmark(agg, _CHART_LAYOUT_EXTRAS), use_container_width=True, config=_PLOTLY_CONFIG)

    st.divider()
    st.markdown("**Frecuencia de temas por negocio** (menciones)")
    st.plotly_chart(chart_topic_heatmap(insights, _CHART_LAYOUT_EXTRAS), use_container_width=True, config=_PLOTLY_CONFIG)

# ── Tab 4: Plan de acción ─────────────────────────────────────────────────────

with tab4:
    st.subheader(f"Plan de acción — {selected}")

    biz_insights = (
        insights[insights.business_name == selected]
        .sort_values("priority_score", ascending=False)
        .reset_index(drop=True)
    )

    if "title" in biz_insights.columns:
        for i, row in biz_insights.iterrows():
            with st.container(border=True):
                col_title, col_score = st.columns([5, 1])
                with col_title:
                    st.markdown(
                        f'<span style="color:{ACCENT};font-size:1.05rem;font-weight:700">'
                        f'{i + 1}. {row["title"]}</span>',
                        unsafe_allow_html=True,
                    )
                    st.caption(row["main_topic"])
                with col_score:
                    st.markdown(
                        f'<div style="text-align:center">'
                        f'<div style="color:#c49a3c;font-family:\'DM Mono\',monospace;font-size:1.6rem;font-weight:600;line-height:1.1">'
                        f'{round(row["priority_score"], 1)}</div>'
                        f'<div style="color:#c49a3c;font-size:0.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.08em">'
                        f'Prioridad</div></div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(row["description"])
                st.markdown(f"**→ Recomendación:** {row['recommendation']}")
    else:
        cols_show = ["main_topic", "mention_count", "pct_negative", "avg_urgency_score", "priority_score"]
        rename = {
            "main_topic": "Tema",
            "mention_count": "Menciones",
            "pct_negative": "% Negativo",
            "avg_urgency_score": "Urgencia prom.",
            "priority_score": "Score prioridad",
        }
        display = biz_insights[cols_show].rename(columns=rename)
        display["% Negativo"] = display["% Negativo"].apply(lambda x: f"{x:.0f}%")
        display["Score prioridad"] = display["Score prioridad"].round(1)
        st.dataframe(display, use_container_width=True)

    st.caption("Score prioridad = menciones × urgencia × % negativo. Cuanto más alto, más impacto tiene resolver ese issue.")

# ── Tab 5: Datos / Descarga ───────────────────────────────────────────────────

with tab5:
    st.subheader("Reseñas clasificadas")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        biz_filter = st.multiselect("Negocio", businesses, default=[selected])
    with col_f2:
        sent_filter = st.multiselect(
            "Sentiment", ["Positivo", "Neutral", "Negativo"],
            default=["Positivo", "Neutral", "Negativo"],
        )
    with col_f3:
        urg_filter = st.multiselect(
            "Urgencia", ["Alta", "Media", "Baja"],
            default=["Alta", "Media", "Baja"],
        )

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
        "business_name": "Negocio", "stars": "Rating", "date_parsed": "Fecha",
        "main_topic": "Tema", "sentiment": "Sentiment", "urgency": "Urgencia",
        "text_reference": "Cita", "clean_text": "Reseña completa",
    }

    st.dataframe(
        filtered[display_cols].rename(columns=rename_cols),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"{len(filtered):,} filas")

    buffer = io.BytesIO()
    filtered[display_cols].rename(columns=rename_cols).to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        label="⬇️ Descargar como Excel",
        data=buffer.getvalue(),
        file_name=f"reviews_{selected.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
