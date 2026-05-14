"""Chart and data loading functions for the Streamlit dashboard."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ── Color palette ────────────────────────────────────────────────────────────

SENTIMENT_COLORS = {"positive": "#3E6E55", "neutral": "#9C8E6A", "negative": "#A14A3C"}
URGENCY_COLORS = {"high": "#A14A3C", "medium": "#C49A3C", "low": "#3E6E55"}
HIGHLIGHT_COLOR = "#0E1116"
HEATMAP_SCALE = ["#F5F1E8", "#E8D9B0", "#D9B677", "#C49A3C", "#A14A3C"]


def sentiment_display_map(strings: dict) -> dict[str, str]:
    return {
        "positive": strings["label_positive"],
        "neutral": strings["label_neutral"],
        "negative": strings["label_negative"],
    }


def urgency_display_map(strings: dict) -> dict[str, str]:
    return {
        "high": strings["label_high"],
        "medium": strings["label_medium"],
        "low": strings["label_low"],
    }

# ── Data loaders ─────────────────────────────────────────────────────────────


def load_aggregated(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def load_insights(enriched_path: Path, base_path: Path, topic_labels: dict[str, str]) -> pd.DataFrame:
    path = enriched_path if enriched_path.exists() else base_path
    df = pd.read_csv(path)
    if "main_topic" in df.columns:
        df["main_topic"] = df["main_topic"].map(topic_labels).fillna(df["main_topic"])
    return df


def load_classified(path: Path, topic_labels: dict[str, str], strings: dict | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")
    df["is_actionable"] = df["is_actionable"].astype(str).str.lower().map({"true": True, "false": False})
    df["main_topic"] = df["main_topic"].map(topic_labels).fillna(df["main_topic"])
    if strings:
        df["sentiment"] = df["sentiment"].map(sentiment_display_map(strings)).fillna(df["sentiment"])
        df["urgency"] = df["urgency"].map(urgency_display_map(strings)).fillna(df["urgency"])
    return df


# ── Tab 1: Resumen ───────────────────────────────────────────────────────────


def chart_sentiment_pie(row: pd.Series, layout_extras: dict | None = None, strings: dict | None = None) -> go.Figure:
    display = sentiment_display_map(strings) if strings else {"positive": "positive", "neutral": "neutral", "negative": "negative"}
    labels = [display["positive"], display["neutral"], display["negative"]]
    values = [row.pct_positive, row.pct_neutral, row.pct_negative]
    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker_colors=list(SENTIMENT_COLORS.values()),
        hole=0.45,
        textinfo="label+percent",
    ))
    fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=270)
    if layout_extras:
        fig.update_layout(**layout_extras)
    return fig


def chart_top_topics(insights_df: pd.DataFrame, business: str, layout_extras: dict | None = None, strings: dict | None = None) -> go.Figure:
    df = (
        insights_df[insights_df.business_name == business]
        .nlargest(6, "mention_count")
        .sort_values("mention_count")
    )
    mentions_label = strings["chart_label_mentions"] if strings else "Menciones"
    pct_neg_label = strings["chart_label_pct_neg"] if strings else "% Neg."
    fig = px.bar(
        df,
        x="mention_count",
        y="main_topic",
        orientation="h",
        color="pct_negative",
        color_continuous_scale=["#3E6E55", "#C49A3C", "#A14A3C"],
        labels={"mention_count": mentions_label, "main_topic": "", "pct_negative": pct_neg_label},
    )
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        height=280,
        coloraxis_showscale=True,
        coloraxis_colorbar=dict(thickness=12, len=0.8),
    )
    if layout_extras:
        fig.update_layout(**layout_extras)
    return fig


# ── Tab 2: Desglose de problemas ─────────────────────────────────────────────


def chart_topic_sentiment(classified_df: pd.DataFrame, business: str, layout_extras: dict | None = None, strings: dict | None = None) -> go.Figure:
    df = classified_df[
        (classified_df.business_name == business)
        & (classified_df.main_topic.notna())
        & (classified_df.sentiment.notna())
    ]
    counts = df.groupby(["main_topic", "sentiment"]).size().reset_index(name="count")
    display = sentiment_display_map(strings) if strings else {"positive": "positive", "neutral": "neutral", "negative": "negative"}
    display_color_map = {display[k]: v for k, v in SENTIMENT_COLORS.items()}
    mentions_label = strings["chart_label_mentions"] if strings else "Menciones"
    fig = px.bar(
        counts,
        x="main_topic",
        y="count",
        color="sentiment",
        color_discrete_map=display_color_map,
        barmode="stack",
        labels={"count": mentions_label, "main_topic": "", "sentiment": "Sentiment"},
        category_orders={"sentiment": list(display.values())},
    )
    fig.update_layout(
        margin=dict(t=10, b=50, l=10, r=10),
        height=320,
        xaxis_tickangle=-30,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    if layout_extras:
        fig.update_layout(**layout_extras)
    return fig


def chart_urgency(classified_df: pd.DataFrame, business: str, layout_extras: dict | None = None, strings: dict | None = None) -> go.Figure:
    df = classified_df[
        (classified_df.business_name == business) & (classified_df.urgency.notna())
    ]
    display = urgency_display_map(strings) if strings else {"high": "high", "medium": "medium", "low": "low"}
    display_order = [display["high"], display["medium"], display["low"]]
    display_color_map = {display[k]: v for k, v in URGENCY_COLORS.items()}
    counts = (
        df.groupby("urgency").size().reindex(display_order, fill_value=0).reset_index(name="count")
    )
    counts.columns = ["urgency", "count"]
    mentions_label = strings["chart_label_mentions"] if strings else "Menciones"
    urgency_label = strings["chart_label_urgency"] if strings else "Urgencia"
    fig = px.bar(
        counts,
        x="urgency",
        y="count",
        color="urgency",
        color_discrete_map=display_color_map,
        labels={"count": mentions_label, "urgency": urgency_label},
        category_orders={"urgency": display_order},
    )
    fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=260)
    if layout_extras:
        fig.update_layout(**layout_extras)
    return fig


# ── Tab 3: Benchmark ─────────────────────────────────────────────────────────


def chart_rating_benchmark(aggregated_df: pd.DataFrame, layout_extras: dict | None = None, strings: dict | None = None) -> go.Figure:
    df = aggregated_df.sort_values("avg_rating", ascending=True)
    avg_rating_label = strings["chart_label_avg_rating"] if strings else "Rating promedio"
    fig = go.Figure(go.Bar(
        x=df.avg_rating,
        y=df.business_name,
        orientation="h",
        marker_color=HIGHLIGHT_COLOR,
        text=df.avg_rating.round(1),
        textposition="outside",
    ))
    fig.update_layout(
        xaxis=dict(range=[0, 5.8], title=avg_rating_label),
        margin=dict(t=10, b=10, l=10, r=50),
        height=230,
    )
    if layout_extras:
        fig.update_layout(**layout_extras)
    return fig


def chart_sentiment_benchmark(aggregated_df: pd.DataFrame, layout_extras: dict | None = None, strings: dict | None = None) -> go.Figure:
    df = aggregated_df.sort_values("pct_positive", ascending=True)
    display = sentiment_display_map(strings) if strings else {"positive": "positive", "neutral": "neutral", "negative": "negative"}
    pct_label = strings["chart_label_pct_mentions"] if strings else "% menciones"
    fig = go.Figure()
    for key, col in [("positive", "pct_positive"), ("neutral", "pct_neutral"), ("negative", "pct_negative")]:
        fig.add_trace(go.Bar(
            name=display[key], x=df[col], y=df.business_name,
            orientation="h", marker_color=SENTIMENT_COLORS[key],
        ))
    fig.update_layout(
        barmode="stack",
        margin=dict(t=10, b=10, l=10, r=10),
        height=230,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_title=pct_label,
    )
    if layout_extras:
        fig.update_layout(**layout_extras)
    return fig


def chart_topic_heatmap(insights_df: pd.DataFrame, layout_extras: dict | None = None) -> go.Figure:
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
    if layout_extras:
        fig.update_layout(**layout_extras)
    return fig
