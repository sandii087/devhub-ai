"""Clean raw customer records and publish a transparent data-quality report."""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from src.config import CLEAN_DATA_PATH, QUALITY_REPORT_PATH, RAW_DATA_PATH
from src.data.validation import profile_data


SNAPSHOT_DATE = pd.Timestamp("2026-09-01")


def _canonicalize(series: pd.Series, mapping: dict[str, str], fallback: str) -> pd.Series:
    return series.astype(str).str.strip().str.lower().map(mapping).fillna(fallback)


def clean_customers(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Repair controlled raw-data issues using reproducible, documented business rules."""
    before = profile_data(raw)
    df = raw.drop_duplicates().copy()
    rows_after_deduplication = len(df)

    df["gender"] = _canonicalize(
        df["gender"], {"female": "Female", "f": "Female", "male": "Male", "m": "Male", "non-binary": "Non-binary"}, "Not specified"
    )
    df["region"] = _canonicalize(
        df["region"], {"north": "North", "south": "South", "east": "East", "west": "West", "central": "Central"}, "Central"
    )
    df["subscription_plan"] = _canonicalize(
        df["subscription_plan"], {"basic": "Basic", "standard": "Standard", "premium": "Premium", "enterprise": "Enterprise"}, "Standard"
    )
    df["internet_service"] = _canonicalize(
        df["internet_service"], {"fiber": "Fiber", "dsl": "DSL", "5g wireless": "5G Wireless", "none": "No service", "nan": "No service"}, "No service"
    )
    df["churn"] = _canonicalize(
        df["churn"], {"yes": "Yes", "1": "Yes", "churned": "Yes", "no": "No", "0": "No"}, "No"
    )
    for column in ["age", "tenure_months", "monthly_charges", "total_charges", "support_tickets", "last_login_days", "services_count", "discount_pct", "satisfaction_score", "monthly_usage"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    valid_age = df["age"].between(18, 90)
    df.loc[~valid_age, "age"] = np.nan
    df["age"] = df["age"].fillna(df["age"].median()).round().astype(int)
    df["tenure_months"] = df["tenure_months"].clip(lower=1, upper=72).fillna(1).round().astype(int)

    parsed_signup = pd.to_datetime(df["signup_date"], errors="coerce")
    inferred_signup = SNAPSHOT_DATE - pd.to_timedelta(df["tenure_months"] * 30.4, unit="D")
    df["signup_date"] = parsed_signup.fillna(inferred_signup).dt.date.astype(str)

    valid_charge = df["monthly_charges"].between(10, 400)
    plan_median = df.loc[valid_charge].groupby("subscription_plan")["monthly_charges"].median()
    df.loc[~valid_charge, "monthly_charges"] = df.loc[~valid_charge, "subscription_plan"].map(plan_median).fillna(df.loc[valid_charge, "monthly_charges"].median())
    df["monthly_charges"] = df["monthly_charges"].round(2)
    valid_total = df["total_charges"].gt(0)
    df.loc[~valid_total, "total_charges"] = df.loc[~valid_total, "monthly_charges"] * df.loc[~valid_total, "tenure_months"]
    df["total_charges"] = df["total_charges"].clip(upper=df["total_charges"].quantile(.995)).round(2)
    df["support_tickets"] = df["support_tickets"].fillna(0).clip(0, 12).round().astype(int)
    df["last_login_days"] = df["last_login_days"].fillna(df["last_login_days"].median()).clip(0, 120).round().astype(int)
    df["services_count"] = df["services_count"].fillna(1).clip(1, 10).round().astype(int)
    df["discount_pct"] = df["discount_pct"].fillna(0).clip(0, 50).round(1)
    df["satisfaction_score"] = df["satisfaction_score"].clip(1, 5).fillna(df.groupby("subscription_plan")["satisfaction_score"].transform("median")).fillna(3.5).round(1)
    usage_cap = df["monthly_usage"].quantile(.99)
    df["monthly_usage"] = df["monthly_usage"].fillna(df["monthly_usage"].median()).clip(lower=0, upper=usage_cap).round(1)

    parsed_churn_date = pd.to_datetime(df["churn_date"], errors="coerce")
    signup_dt = pd.to_datetime(df["signup_date"])
    fallback_churn_date = signup_dt + pd.to_timedelta((df["tenure_months"] * 15).clip(lower=1), unit="D")
    invalid_churn_date = parsed_churn_date.isna() | (parsed_churn_date < signup_dt) | (parsed_churn_date > SNAPSHOT_DATE)
    parsed_churn_date = parsed_churn_date.where(df["churn"].eq("Yes"), pd.NaT)
    parsed_churn_date = parsed_churn_date.mask(df["churn"].eq("Yes") & invalid_churn_date, fallback_churn_date)
    df["churn_date"] = parsed_churn_date.dt.date.astype("string").fillna("")
    df["churn_reason"] = df["churn_reason"].fillna("").astype(str).str.strip()
    df.loc[df["churn"].eq("No"), "churn_reason"] = "Not churned"
    df.loc[df["churn"].eq("Yes") & df["churn_reason"].eq(""), "churn_reason"] = "Unspecified"

    # One record per customer is the database grain; keep the first reproducible occurrence.
    df = df.drop_duplicates(subset=["customer_id"], keep="first").sort_values("customer_id").reset_index(drop=True)
    after = profile_data(df)
    report = {
        "source": "Synthetic fictional customer records generated with a fixed seed.",
        "before": before,
        "after": after,
        "rows_removed": int(before["rows"] - len(df)),
        "cleaning_actions": [
            "Removed exact duplicate rows and enforced one record per customer ID.",
            "Standardized categorical capitalization and mapped invalid plan, region, gender, and churn values.",
            "Replaced impossible or missing ages with the valid-data median.",
            "Reconstructed invalid signup dates from recorded tenure and a fixed analytical snapshot date.",
            "Replaced invalid monthly charges with the valid median for the customer's plan and rebuilt invalid total charges.",
            "Imputed missing satisfaction with the plan median and capped controlled support and usage outliers.",
            "Normalized churn reasons and churn dates for the retention analysis.",
        ],
        "rows_after_exact_deduplication": int(rows_after_deduplication),
        "final_clean_row_count": int(len(df)),
    }
    return df, report


def run_cleaning() -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_csv(RAW_DATA_PATH)
    clean, report = clean_customers(raw)
    CLEAN_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(CLEAN_DATA_PATH, index=False)
    QUALITY_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return clean, report


if __name__ == "__main__":
    cleaned, quality_report = run_cleaning()
    print(f"Cleaned {len(cleaned):,} customer rows; quality report: {QUALITY_REPORT_PATH}")
