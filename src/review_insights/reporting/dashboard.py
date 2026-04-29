"""Chart and data loading functions for the Streamlit dashboard."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data" / "processed"

# ── Color palette ────────────────────────────────────────────────────────────

SENTIMENT_COLORS = {"Positivo": "#008450", "Neutral": "#7a8499", "Negativo": "#B81D13"}
URGENCY_COLORS = {"Alta": "#B81D13", "Media": "#c49a3c", "Baja": "#008450"}
HIGHLIGHT_COLOR = "#4a90d9"
HEATMAP_SCALE = ["#131929", "#1a2f52", "#25467a", "#3666a8", "#4a90d9"]

# ── Translation maps ─────────────────────────────────────────────────────────

TOPIC_ES = {
    "Food Quality": "Calidad de comida",
    "Service Speed": "Velocidad del servicio",
    "Staff Attitude": "Actitud del personal",
    "Price / Value": "Precio / Valor",
    "Ambiance": "Ambiente",
    "Hygiene & Cleanliness": "Higiene y limpieza",
    "Menu & Options": "Menú y opciones",
    "Booking & Reservations": "Reservas",
    "Delivery & Takeaway": "Delivery / Para llevar",
    "Overall Experience": "Experiencia general",
}

SENTIMENT_ES = {"positive": "Positivo", "neutral": "Neutral", "negative": "Negativo"}
URGENCY_ES = {"high": "Alta", "medium": "Media", "low": "Baja"}

# ── Data loaders ─────────────────────────────────────────────────────────────


def load_aggregated() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "aggregated.csv")


def load_insights() -> pd.DataFrame:
    enriched = DATA_DIR / "insights_enriched.csv"
    path = enriched if enriched.exists() else DATA_DIR / "insights.csv"
    df = pd.read_csv(path)
    if "main_topic" in df.columns:
        df["main_topic"] = df["main_topic"].map(TOPIC_ES).fillna(df["main_topic"])
    return df


def load_classified() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "reviews_classified.csv")
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    df["is_actionable"] = df["is_actionable"].astype(str).str.lower().map({"true": True, "false": False})
    df["main_topic"] = df["main_topic"].map(TOPIC_ES).fillna(df["main_topic"])
    df["sentiment"] = df["sentiment"].map(SENTIMENT_ES).fillna(df["sentiment"])
    df["urgency"] = df["urgency"].map(URGENCY_ES).fillna(df["urgency"])
    return df


# ── Tab 1: Resumen ───────────────────────────────────────────────────────────


def chart_sentiment_pie(row: pd.Series) -> go.Figure:
    labels = list(SENTIMENT_COLORS.keys())
    values = [row.pct_positive, row.pct_neutral, row.pct_negative]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker_colors=list(SENTIMENT_COLORS.values()),
        hole=0.45,
        textinfo="label+percent",
    ))
    fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=270)
    return fig


def chart_top_topics(insights_df: pd.DataFrame, business: str) -> go.Figure:
    df = (
        insights_df[insights_df.business_name == business]
        .nlargest(6, "mention_count")
        .sort_values("mention_count")
    )
    fig = px.bar(
        df,
        x="mention_count",
        y="main_topic",
        orientation="h",
        color="pct_negative",
        color_continuous_scale=["#008450", "#c49a3c", "#B81D13"],
        labels={"mention_count": "Menciones", "main_topic": "", "pct_negative": "% Neg."},
    )
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        coloraxis_showscale=True,
        coloraxis_colorbar=dict(thickness=12, len=0.8),
    )
    return fig


# ── Tab 2: Desglose de problemas ─────────────────────────────────────────────


def chart_topic_sentiment(classified_df: pd.DataFrame, business: str) -> go.Figure:
    df = classified_df[
        (classified_df.business_name == business)
        & (classified_df.main_topic.notna())
        & (classified_df.sentiment.notna())
    ]
    counts = df.groupby(["main_topic", "sentiment"]).size().reset_index(name="count")
    fig = px.bar(
        counts,
        x="main_topic",
        y="count",
        color="sentiment",
        color_discrete_map=SENTIMENT_COLORS,
        barmode="stack",
        labels={"count": "Menciones", "main_topic": "", "sentiment": "Sentiment"},
        category_orders={"sentiment": list(SENTIMENT_COLORS.keys())},
    )
    fig.update_layout(
        margin=dict(t=10, b=50, l=10, r=10),
        height=320,
        xaxis_tickangle=-30,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def chart_urgency(classified_df: pd.DataFrame, business: str) -> go.Figure:
    df = classified_df[
        (classified_df.business_name == business) & (classified_df.urgency.notna())
    ]
    order = list(URGENCY_COLORS.keys())
    counts = (
        df.groupby("urgency").size().reindex(order, fill_value=0).reset_index(name="count")
    )
    counts.columns = ["urgency", "count"]
    fig = px.bar(
        counts,
        x="urgency",
        y="count",
        color="urgency",
        color_discrete_map=URGENCY_COLORS,
        labels={"count": "Menciones", "urgency": "Urgencia"},
        category_orders={"urgency": order},
    )
    fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=260)
    return fig


# ── Tab 3: Benchmark ─────────────────────────────────────────────────────────


def chart_rating_benchmark(aggregated_df: pd.DataFrame) -> go.Figure:
    df = aggregated_df.sort_values("avg_rating", ascending=True)
    fig = go.Figure(go.Bar(
        x=df.avg_rating,
        y=df.business_name,
        orientation="h",
        marker_color=HIGHLIGHT_COLOR,
        text=df.avg_rating.round(1),
        textposition="outside",
    ))
    fig.update_layout(
        xaxis=dict(range=[0, 5.8], title="Rating promedio"),
        margin=dict(t=10, b=10, l=10, r=50),
        height=230,
    )
    return fig


def chart_sentiment_benchmark(aggregated_df: pd.DataFrame) -> go.Figure:
    df = aggregated_df.sort_values("pct_positive", ascending=True)
    fig = go.Figure()
    for label, col in [("Positivo", "pct_positive"), ("Neutral", "pct_neutral"), ("Negativo", "pct_negative")]:
        fig.add_trace(go.Bar(
            name=label, x=df[col], y=df.business_name,
            orientation="h", marker_color=SENTIMENT_COLORS[label],
        ))
    fig.update_layout(
        barmode="stack",
        margin=dict(t=10, b=10, l=10, r=10),
        height=230,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title="% menciones",
    )
    return fig


def chart_topic_heatmap(insights_df: pd.DataFrame) -> go.Figure:
    pivot = (
        insights_df.groupby(["business_name", "main_topic"])["mention_count"]
        .sum()
        .reset_index()
        .pivot(index="main_topic", columns="business_name", values="mention_count")
        .fillna(0)
        .astype(int)
    )
    # Sort ascending so most-mentioned appears at top in Plotly's bottom-to-top y-axis
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=True).index]

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns.tolist(),
        y=pivot.index.tolist(),
        colorscale=HEATMAP_SCALE,
        showscale=True,
        text=pivot.values,
        texttemplate="%{text}",
        textfont={"size": 12},
        colorbar=dict(thickness=12, len=0.8),
    ))
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=360,
        xaxis=dict(side="top"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
