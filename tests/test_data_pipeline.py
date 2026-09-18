import pandas as pd

from src.data.clean import clean_customers
from src.data.features import add_business_features
from src.data.generate import generate_customers


def test_generator_creates_controlled_duplicate_rows():
    raw = generate_customers(n_customers=200, seed=7)
    assert len(raw) > 200
    assert raw["customer_id"].duplicated().any()
    assert {"customer_id", "churn", "monthly_charges", "satisfaction_score"}.issubset(raw.columns)


def test_cleaning_returns_one_valid_row_per_customer():
    raw = generate_customers(n_customers=250, seed=9)
    clean, report = clean_customers(raw)
    assert len(clean) == 250
    assert not clean["customer_id"].duplicated().any()
    assert clean["age"].between(18, 90).all()
    assert clean["monthly_charges"].gt(0).all()
    assert set(clean["churn"].unique()) <= {"Yes", "No"}
    assert report["rows_removed"] > 0


def test_feature_engineering_adds_interpretable_business_features():
    raw = generate_customers(n_customers=250, seed=11)
    clean, _ = clean_customers(raw)
    featured = add_business_features(clean)
    expected = {"tenure_bucket", "charge_bucket", "support_intensity", "engagement_level", "customer_value_segment", "signup_cohort"}
    assert expected.issubset(featured.columns)
    assert featured["support_intensity"].notna().all()
