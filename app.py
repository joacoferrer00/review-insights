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

st.set_page_config(
    page_title="Review Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Tabs ── */
button[data-baseweb="tab"] p,
button[data-baseweb="tab"] span,
button[data-baseweb="tab"] {
    font-size: 1.15rem !important;
    font-weight: 600 !important;
}
button[data-baseweb="tab"] {
    padding: 0.65rem 1.5rem !important;
}

/* ── Sidebar: todo el texto ── */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-size: 1.55rem !important;
    font-weight: 700 !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
    font-size: 1.05rem !important;
}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Client config ────────────────────────────────────────────────────────────

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

# ── Tabs ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📈 Resumen", "🔍 Problemas", "⚖️ Benchmark", "🎯 Plan de acción", "📥 Datos"
])

# ── Tab 1: Resumen ejecutivo ─────────────────────────────────────────────────

with tab1:
    st.subheader(f"Resumen ejecutivo — {selected}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rating promedio", f"{row.avg_rating:.1f} ⭐")
    c2.metric("Total reseñas", int(row.total_reviews))
    c3.metric("Sentiment positivo", f"{row.pct_positive:.0f}%")
    c4.metric("Urgencias altas", int(row.high_urgency_count))

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Distribución de sentiment**")
        st.plotly_chart(chart_sentiment_pie(row), use_container_width=True)
    with col_b:
        st.markdown("**Temas más mencionados**")
        st.plotly_chart(chart_top_topics(insights, selected), use_container_width=True)

# ── Tab 2: Desglose de problemas ─────────────────────────────────────────────

with tab2:
    st.subheader(f"Desglose por tema — {selected}")
    st.plotly_chart(chart_topic_sentiment(classified, selected), use_container_width=True)

    st.divider()
    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.markdown("**Distribución de urgencia**")
        st.plotly_chart(chart_urgency(classified, selected), use_container_width=True)

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
        st.plotly_chart(chart_rating_benchmark(agg), use_container_width=True)
    with col_b:
        st.markdown("**Distribución de sentiment**")
        st.plotly_chart(chart_sentiment_benchmark(agg), use_container_width=True)

    st.divider()
    st.markdown("**Frecuencia de temas por negocio** (menciones)")
    st.plotly_chart(chart_topic_heatmap(insights), use_container_width=True)

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
                        f'<span style="color:#4a90d9;font-size:1.05rem;font-weight:700">'
                        f'{i + 1}. {row["title"]}</span>',
                        unsafe_allow_html=True,
                    )
                    st.caption(row["main_topic"])
                with col_score:
                    st.markdown(
                        f'<div style="text-align:center">'
                        f'<div style="color:#c49a3c;font-size:1.6rem;font-weight:700;line-height:1.1">'
                        f'{round(row["priority_score"], 1)}</div>'
                        f'<div style="color:#c49a3c;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em">'
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
