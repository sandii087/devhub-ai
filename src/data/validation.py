"""Data-quality profiling for raw and clean customer records."""
from __future__ import annotations

from typing import Any

import pandas as pd


VALID_PLANS = {"Basic", "Standard", "Premium", "Enterprise"}
VALID_REGIONS = {"North", "South", "East", "West", "Central"}
VALID_CHURN = {"Yes", "No"}


def profile_data(df: pd.DataFrame) -> dict[str, Any]:
    """Return a serializable, before/after quality profile."""
    parsed_dates = pd.to_datetime(df["signup_date"], errors="coerce")
    churn = df["churn"].astype(str)
    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_values": {key: int(value) for key, value in df.isna().sum().items() if value},
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_customer_ids": int(df["customer_id"].duplicated().sum()),
        "invalid_ages": int(((pd.to_numeric(df["age"], errors="coerce") < 18) | (pd.to_numeric(df["age"], errors="coerce") > 90)).sum()),
        "invalid_dates": int(parsed_dates.isna().sum()),
        "invalid_monthly_charges": int((pd.to_numeric(df["monthly_charges"], errors="coerce") <= 0).sum()),
        "invalid_total_charges": int((pd.to_numeric(df["total_charges"], errors="coerce") < 0).sum()),
        "invalid_churn_labels": int((~churn.isin(VALID_CHURN)).sum()),
        "invalid_plans": int((~df["subscription_plan"].astype(str).isin(VALID_PLANS)).sum()),
        "invalid_regions": int((~df["region"].astype(str).isin(VALID_REGIONS)).sum()),
    }
