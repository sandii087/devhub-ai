import pandas as pd

from src.analytics.metrics import cohort_retention, overview_metrics, segment_metrics


def sample_scored_data() -> pd.DataFrame:
    return pd.DataFrame({
        "customer_id": ["A", "B", "C", "D"],
        "churn": ["Yes", "No", "No", "Yes"],
        "monthly_charges": [100, 50, 80, 70],
        "risk_score": [.8, .1, .3, .7],
        "revenue_at_risk": [80, 5, 24, 49],
        "risk_segment": ["High Risk", "Low Risk", "Low Risk", "High Risk"],
        "portfolio_segment": ["High Value / High Risk", "Low Value / Low Risk", "High Value / Low Risk", "Low Value / High Risk"],
        "tenure_months": [3, 12, 20, 5],
        "satisfaction_score": [2.1, 4.5, 4.1, 2.8],
        "support_tickets": [4, 0, 1, 3],
        "signup_date": ["2026-01-01", "2025-01-01", "2025-06-01", "2026-02-01"],
        "churn_date": ["2026-02-01", "", "", "2026-04-01"],
    })


def test_overview_metrics_are_calculated_from_rows():
    metrics = overview_metrics(sample_scored_data())
    assert metrics["total_customers"] == 4
    assert metrics["churn_rate"] == 50.0
    assert metrics["mrr"] == 300.0
    assert metrics["revenue_at_risk"] == 158.0


def test_segment_and_cohort_analysis_return_real_aggregates():
    data = sample_scored_data()
    segments = segment_metrics(data)
    cohorts = cohort_retention(data, periods=2)
    assert len(segments) == 4
    assert cohorts["rows"]
    assert all(0 <= row["retention_rate"] <= 100 for row in cohorts["rows"])
