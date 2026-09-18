# Data

The project creates a **synthetic** customer snapshot for a fictional subscription company; it contains no real company or customer records.

- `raw/customers_raw.csv` is reproducibly generated with seed `20260917`. It has intentional, controlled imperfections: exact duplicates, missing satisfaction values, malformed dates, invalid ages/charges, inconsistent labels, and a small number of outliers.
- `processed/customers_clean.csv` is recreated by the pipeline after validation, cleaning, business feature engineering, and model-based risk scoring.

Both CSV files are ignored by Git because they are generated locally. Run `python -m src.run_pipeline` from the repository root to recreate them.

The clean table is one row per customer. Its key engineered fields are:

- `tenure_bucket`, `charge_bucket`, `support_intensity`, and `engagement_level` for business analysis;
- `customer_value_segment`, based on whether monthly charges × tenure is at or above the dataset median;
- `risk_score`, the logistic model's predicted churn probability;
- `risk_segment`: Low ≤ 0.33, Medium ≤ 0.66, High > 0.66;
- `revenue_at_risk`, defined as `monthly_charges × risk_score`—expected monthly exposure, not booked loss.
