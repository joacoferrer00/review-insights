"""Aggregation module — pure pandas, zero LLM.

Takes reviews_classified.csv and produces:
- aggregated.csv: one row per business_name
- insights.csv: one row per (business_name, main_topic), ranked by priority_score
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_URGENCY_SCORE = {"high": 3, "medium": 2, "low": 1}


def aggregate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate classified reviews into the two summary canonical tables.

    Args:
        df: Full reviews_classified DataFrame (1 row per (review_id, mention_id),
            including rating-only rows with null mention_id).

    Returns:
        Tuple of (aggregated_df, insights_df).
        - aggregated_df: one row per business_name.
        - insights_df: one row per (business_name, main_topic), sorted by
          priority_score descending.
    """
    classified = df[df["sentiment"].notna()].copy()
    classified["urgency_score"] = classified["urgency"].map(_URGENCY_SCORE)

    aggregated = _build_aggregated(df, classified)
    insights = _build_insights(classified)

    logger.info(
        "aggregation complete — aggregated: %d rows, insights: %d rows",
        len(aggregated),
        len(insights),
    )
    return aggregated, insights


def _build_aggregated(df: pd.DataFrame, classified: pd.DataFrame) -> pd.DataFrame:
    # Each of these three metrics must deduplicate by review_id because the
    # multi-mention schema produces N rows per review. Without dedup, a review
    # mentioning 3 topics would count as 3 reviews.
    deduped = df.drop_duplicates(subset="review_id")

    total = (
        deduped.groupby("business_name")["review_id"]
        .nunique()
        .rename("total_reviews")
        .reset_index()
    )
    with_text = (
        deduped[deduped["has_text"]]
        .groupby("business_name")["review_id"]
        .nunique()
        .rename("reviews_with_text")
        .reset_index()
    )
    avg_rating = (
        deduped.groupby("business_name")["stars"]
        .mean()
        .round(1)
        .rename("avg_rating")
        .reset_index()
    )

    base = total.merge(with_text, on="business_name", how="left").merge(
        avg_rating, on="business_name", how="left"
    )

    sentiment_counts = (
        classified.groupby(["business_name", "sentiment"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["positive", "neutral", "negative"], fill_value=0)
    )
    sentiment_totals = sentiment_counts.sum(axis=1)
    sentiment_pct = sentiment_counts.div(sentiment_totals, axis=0).mul(100).round(1)
    sentiment_pct.columns = ["pct_positive", "pct_neutral", "pct_negative"]
    sentiment_pct = sentiment_pct.reset_index()

    top_topics = _top_topics_per_business(classified)

    urgency_actionable = (
        classified.groupby("business_name")
        .agg(
            high_urgency_count=("urgency", lambda s: (s == "high").sum()),
            actionable_count=("is_actionable", "sum"),
        )
        .reset_index()
    )

    result = (
        base.merge(sentiment_pct, on="business_name", how="left")
        .merge(top_topics, on="business_name", how="left")
        .merge(urgency_actionable, on="business_name", how="left")
    )

    col_order = [
        "business_name", "total_reviews", "reviews_with_text", "avg_rating",
        "pct_positive", "pct_neutral", "pct_negative",
        "top_topic_1", "top_topic_2", "top_topic_3",
        "high_urgency_count", "actionable_count",
    ]
    return result[col_order]


def _top_topics_per_business(classified: pd.DataFrame) -> pd.DataFrame:
    topic_counts = (
        classified.groupby(["business_name", "main_topic"])
        .size()
        .reset_index(name="n")
        .sort_values(["business_name", "n"], ascending=[True, False])
    )
    rows = []
    for biz, grp in topic_counts.groupby("business_name"):
        topics = grp["main_topic"].tolist()
        rows.append({
            "business_name": biz,
            "top_topic_1": topics[0] if len(topics) > 0 else None,
            "top_topic_2": topics[1] if len(topics) > 1 else None,
            "top_topic_3": topics[2] if len(topics) > 2 else None,
        })
    return pd.DataFrame(rows)


def _build_insights(classified: pd.DataFrame) -> pd.DataFrame:
    grp = classified.groupby(["business_name", "main_topic"])

    mention_count = grp.size().rename("mention_count")

    pct_negative = (
        grp["sentiment"]
        .apply(lambda s: round((s == "negative").sum() / len(s) * 100, 1))
        .rename("pct_negative")
    )

    avg_urgency_score = (
        grp["urgency_score"]
        .mean()
        .round(2)
        .rename("avg_urgency_score")
    )

    actionable_count = (
        grp["is_actionable"]
        .sum()
        .rename("actionable_count")
    )

    insights = (
        pd.concat([mention_count, pct_negative, avg_urgency_score, actionable_count], axis=1)
        .reset_index()
    )

    insights["priority_score"] = (
        insights["mention_count"]
        * insights["avg_urgency_score"]
        * insights["pct_negative"]
        / 100  # pct_negative is 0-100; normalize so score stays interpretable
    ).round(2)

    return insights.sort_values("priority_score", ascending=False).reset_index(drop=True)
