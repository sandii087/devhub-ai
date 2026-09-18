"""Business feature engineering performed before machine learning."""
from __future__ import annotations

import pandas as pd

from src.config import CLEAN_DATA_PATH


def add_business_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add documented, interpretable customer features without using model predictions."""
    result = df.copy()
    result["tenure_bucket"] = pd.cut(result["tenure_months"], bins=[0, 6, 12, 24, 48, float("inf")], labels=["0-6m", "7-12m", "13-24m", "25-48m", "49m+"]).astype(str)
    result["charge_bucket"] = pd.cut(result["monthly_charges"], bins=[0, 40, 75, 120, float("inf")], labels=["Under $40", "$40-$75", "$76-$120", "$120+"]).astype(str)
    # Avoid the literal string "None": pandas treats it as a missing sentinel when the CSV is read back.
    result["support_intensity"] = pd.cut(result["support_tickets"], bins=[-1, 0, 2, float("inf")], labels=["No tickets", "Moderate", "High"]).astype(str)
    result["engagement_level"] = pd.cut(result["last_login_days"], bins=[-1, 7, 21, float("inf")], labels=["High", "Medium", "Low"]).astype(str)
    lifetime_value = result["monthly_charges"] * result["tenure_months"]
    result["customer_value_segment"] = pd.Series("Low Value", index=result.index)
    result.loc[lifetime_value >= lifetime_value.median(), "customer_value_segment"] = "High Value"
    result["signup_cohort"] = pd.to_datetime(result["signup_date"]).dt.to_period("M").astype(str)
    return result


def run_feature_engineering() -> pd.DataFrame:
    dataframe = pd.read_csv(CLEAN_DATA_PATH)
    featured = add_business_features(dataframe)
    featured.to_csv(CLEAN_DATA_PATH, index=False)
    return featured


if __name__ == "__main__":
    result = run_feature_engineering()
    print(f"Engineered {len(result.columns)} columns for {len(result):,} customers")
