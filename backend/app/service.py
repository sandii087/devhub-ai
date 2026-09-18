"""Database-backed API service functions; no dashboard values are hard-coded."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

import pandas as pd

from src.analytics.metrics import build_insights, churn_by, churn_trend, cohort_retention, overview_metrics, risk_metrics, segment_metrics
from src.config import DATABASE_PATH, MODEL_METRICS_PATH, QUALITY_REPORT_PATH


def load_customers(plan: str | None = None, region: str | None = None) -> pd.DataFrame:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError("Analytics database is not available. Run `python -m src.run_pipeline` first.")
    conditions: list[str] = []
    params: list[str] = []
    if plan:
        conditions.append("subscription_plan = ?")
        params.append(plan)
    if region:
        conditions.append("region = ?")
        params.append(region)
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    with sqlite3.connect(DATABASE_PATH) as connection:
        return pd.read_sql_query(f"SELECT * FROM customers{where_clause}", connection, params=params)


def customer_rows(search: str | None = None, risk_segment: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError("Analytics database is not available. Run `python -m src.run_pipeline` first.")
    conditions: list[str] = []
    params: list[Any] = []
    if search:
        conditions.append("(customer_id LIKE ? OR city LIKE ? OR customer_segment LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    if risk_segment:
        conditions.append("risk_segment = ?")
        params.append(risk_segment)
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size
    with sqlite3.connect(DATABASE_PATH) as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM customers{where_clause}", params).fetchone()[0]
        rows = pd.read_sql_query(
            f"SELECT customer_id, customer_segment, subscription_plan, contract_type, tenure_months, monthly_charges, satisfaction_score, support_tickets, risk_score, risk_segment, revenue_at_risk, region FROM customers{where_clause} ORDER BY risk_score DESC LIMIT ? OFFSET ?",
            connection,
            params=[*params, page_size, offset],
        )
    return {"total": int(total), "page": page, "page_size": page_size, "items": rows.to_dict(orient="records")}


def customer_detail(customer_id: str) -> dict[str, Any] | None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError("Analytics database is not available. Run `python -m src.run_pipeline` first.")
    with sqlite3.connect(DATABASE_PATH) as connection:
        row = pd.read_sql_query("SELECT * FROM customers WHERE customer_id = ?", connection, params=[customer_id])
    if row.empty:
        return None
    customer = row.iloc[0].to_dict()
    factors: list[str] = []
    if customer["contract_type"] == "Month-to-month":
        factors.append("Month-to-month contract")
    if customer["last_login_days"] > 21:
        factors.append("Low recent engagement")
    if customer["support_tickets"] >= 3:
        factors.append("High support activity")
    if customer["satisfaction_score"] < 3:
        factors.append("Below-target satisfaction")
    if customer["tenure_months"] <= 6:
        factors.append("Early tenure")
    return {"customer": customer, "risk_factors": factors or ["No rule-based elevated factor; review the model score alongside customer context."]}


def model_metrics() -> dict[str, Any]:
    if not MODEL_METRICS_PATH.exists():
        raise FileNotFoundError("Model metrics are not available. Run `python -m src.run_pipeline` first.")
    return json.loads(MODEL_METRICS_PATH.read_text(encoding="utf-8"))


def quality_report() -> dict[str, Any]:
    if not QUALITY_REPORT_PATH.exists():
        raise FileNotFoundError("Data-quality report is not available. Run `python -m src.run_pipeline` first.")
    return json.loads(QUALITY_REPORT_PATH.read_text(encoding="utf-8"))


def overview() -> dict[str, Any]:
    df = load_customers()
    return {"metrics": overview_metrics(df), "churn_trend": churn_trend(df), "plan_churn": churn_by(df, "subscription_plan"), "contract_churn": churn_by(df, "contract_type"), "portfolio_segments": segment_metrics(df), "insights": build_insights(df)}


def churn(plan: str | None = None, region: str | None = None) -> dict[str, Any]:
    df = load_customers(plan, region)
    return {"metrics": overview_metrics(df), "trend": churn_trend(df), "by_plan": churn_by(df, "subscription_plan"), "by_contract": churn_by(df, "contract_type"), "by_region": churn_by(df, "region"), "by_customer_segment": churn_by(df, "customer_segment"), "by_tenure": churn_by(df, "tenure_bucket"), "by_payment_method": churn_by(df, "payment_method"), "by_satisfaction": churn_by(df, "satisfaction_score"), "by_support": churn_by(df, "support_intensity"), "by_engagement": churn_by(df, "engagement_level")}


def segments() -> dict[str, Any]:
    df = load_customers()
    return {"segments": segment_metrics(df), "distribution": churn_by(df, "portfolio_segment")}


def risk() -> dict[str, Any]:
    df = load_customers()
    return {"metrics": overview_metrics(df), **risk_metrics(df)}


def cohorts() -> dict[str, Any]:
    return cohort_retention(load_customers())


def insights() -> dict[str, Any]:
    return {"insights": build_insights(load_customers())}
