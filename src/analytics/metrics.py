"""Reusable analytics derived from the cleaned, scored customer table."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.replace({np.nan: None}).to_dict(orient="records")


def overview_metrics(df: pd.DataFrame) -> dict[str, Any]:
    customers = len(df)
    churned = int((df["churn"] == "Yes").sum())
    risk = df.get("risk_score", pd.Series(0, index=df.index))
    return {
        "total_customers": int(customers),
        "churned_customers": churned,
        "retained_customers": int(customers - churned),
        "churn_rate": round(churned / customers * 100, 2) if customers else 0,
        "retention_rate": round((customers - churned) / customers * 100, 2) if customers else 0,
        "average_monthly_charges": round(float(df["monthly_charges"].mean()), 2),
        "mrr": round(float(df["monthly_charges"].sum()), 2),
        "total_recurring_revenue": round(float(df["monthly_charges"].sum()), 2),
        "revenue_at_risk": round(float(df.get("revenue_at_risk", df["monthly_charges"] * risk).sum()), 2),
        "at_risk_customers": int((df.get("risk_segment", pd.Series("", index=df.index)) == "High Risk").sum()),
        "average_tenure": round(float(df["tenure_months"].mean()), 1),
        "average_satisfaction": round(float(df["satisfaction_score"].mean()), 2),
        "average_support_tickets": round(float(df["support_tickets"].mean()), 2),
    }


def churn_by(df: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    grouped = (
        df.groupby(column, dropna=False)
        .agg(customers=("customer_id", "count"), churned=("churn", lambda values: (values == "Yes").sum()), average_monthly_charges=("monthly_charges", "mean"), revenue_at_risk=("revenue_at_risk", "sum"))
        .reset_index()
    )
    grouped["churn_rate"] = (grouped["churned"] / grouped["customers"] * 100).round(2)
    grouped["average_monthly_charges"] = grouped["average_monthly_charges"].round(2)
    grouped["revenue_at_risk"] = grouped["revenue_at_risk"].round(2)
    return _records(grouped.sort_values("churn_rate", ascending=False))


def churn_trend(df: pd.DataFrame) -> list[dict[str, Any]]:
    churn_dates = pd.to_datetime(df.loc[df["churn"] == "Yes", "churn_date"], errors="coerce")
    trend = churn_dates.dropna().dt.to_period("M").astype(str).value_counts().sort_index().rename_axis("month").reset_index(name="churned_customers")
    total = len(df)
    trend["churn_rate_of_customer_base"] = (trend["churned_customers"] / total * 100).round(2)
    return _records(trend)


def segment_metrics(df: pd.DataFrame) -> list[dict[str, Any]]:
    grouped = (
        df.groupby("portfolio_segment")
        .agg(
            customers=("customer_id", "count"),
            churned=("churn", lambda values: (values == "Yes").sum()),
            average_monthly_charges=("monthly_charges", "mean"),
            revenue=("monthly_charges", "sum"),
            revenue_at_risk=("revenue_at_risk", "sum"),
            average_tenure=("tenure_months", "mean"),
            average_satisfaction=("satisfaction_score", "mean"),
        )
        .reset_index()
    )
    grouped["churn_rate"] = (grouped["churned"] / grouped["customers"] * 100).round(2)
    for column in ["average_monthly_charges", "revenue", "revenue_at_risk", "average_tenure", "average_satisfaction"]:
        grouped[column] = grouped[column].round(2)
    ordering = {"High Value / High Risk": 0, "High Value / Low Risk": 1, "Low Value / High Risk": 2, "Low Value / Low Risk": 3}
    grouped["_order"] = grouped["portfolio_segment"].map(ordering)
    return _records(grouped.sort_values("_order").drop(columns="_order"))


def risk_metrics(df: pd.DataFrame) -> dict[str, Any]:
    distribution = df.groupby("risk_segment").agg(customers=("customer_id", "count"), revenue_at_risk=("revenue_at_risk", "sum"), average_score=("risk_score", "mean")).reset_index()
    distribution["revenue_at_risk"] = distribution["revenue_at_risk"].round(2)
    distribution["average_score"] = distribution["average_score"].round(4)
    return {
        "distribution": _records(distribution),
        "by_plan": churn_by(df, "subscription_plan"),
        "by_region": churn_by(df, "region"),
        "by_customer_segment": churn_by(df, "customer_segment"),
    }


def cohort_retention(df: pd.DataFrame, periods: int = 12) -> dict[str, Any]:
    """Calculate actual active-customer retention at each tenure month from signup/churn dates."""
    work = df.copy()
    work["signup"] = pd.to_datetime(work["signup_date"])
    work["churned_at"] = pd.to_datetime(work["churn_date"], errors="coerce")
    work["cohort"] = work["signup"].dt.to_period("M").astype(str)
    snapshot = pd.Timestamp("2026-09-01")
    rows: list[dict[str, Any]] = []
    for cohort, group in work.groupby("cohort"):
        cohort_size = len(group)
        for period in range(periods + 1):
            observed = ((snapshot - group["signup"]).dt.days >= period * 30).sum()
            if not observed:
                continue
            elapsed_to_churn = (group["churned_at"] - group["signup"]).dt.days
            active = ((snapshot - group["signup"]).dt.days >= period * 30) & (group["churned_at"].isna() | (elapsed_to_churn >= period * 30))
            retained = int(active.sum())
            rows.append({"cohort": cohort, "period": period, "cohort_size": int(cohort_size), "retained_customers": retained, "retention_rate": round(retained / cohort_size * 100, 2)})
    matrix = pd.DataFrame(rows)
    return {"rows": _records(matrix), "cohorts": sorted(matrix["cohort"].unique().tolist()) if not matrix.empty else [], "periods": list(range(periods + 1))}


def build_insights(df: pd.DataFrame) -> list[dict[str, str]]:
    plan = pd.DataFrame(churn_by(df, "subscription_plan")).iloc[0]
    region = pd.DataFrame(churn_by(df, "region")).iloc[0]
    segment = pd.DataFrame(churn_by(df, "customer_segment")).iloc[0]
    tenure = pd.DataFrame(churn_by(df, "tenure_bucket")).iloc[0]
    high_value_risk = df[df["portfolio_segment"] == "High Value / High Risk"]
    return [
        {"title": "Highest plan churn", "detail": f"{plan['subscription_plan']} has the highest observed churn rate at {plan['churn_rate']:.2f}% across {int(plan['customers']):,} customers."},
        {"title": "Regional exposure", "detail": f"{region['region']} has the highest observed churn rate at {region['churn_rate']:.2f}% and ${region['revenue_at_risk']:,.0f} expected monthly revenue exposure."},
        {"title": "Segment to investigate", "detail": f"{segment['customer_segment']} leads customer-segment churn at {segment['churn_rate']:.2f}%."},
        {"title": "Tenure pattern", "detail": f"The {tenure['tenure_bucket']} tenure group has the highest churn rate at {tenure['churn_rate']:.2f}% in this synthetic snapshot."},
        {"title": "High-value risk", "detail": f"{len(high_value_risk):,} high-value customers are high risk, representing ${high_value_risk['revenue_at_risk'].sum():,.0f} in expected monthly revenue exposure."},
    ]
