"""Generate a reproducible, deliberately imperfect synthetic churn dataset.

The data models a fictional subscription company.  It is not real customer data.
"""
from __future__ import annotations

import argparse
from datetime import date

import numpy as np
import pandas as pd

from src.config import RANDOM_SEED, RAW_DATA_PATH


SNAPSHOT_DATE = pd.Timestamp("2026-09-01")


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-values))


def generate_customers(n_customers: int = 5_000, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Return deterministic synthetic customer records, including controlled quality issues."""
    rng = np.random.default_rng(seed)
    customer_id = [f"CUS-{number:05d}" for number in range(1, n_customers + 1)]
    regions = rng.choice(["North", "South", "East", "West", "Central"], n_customers, p=[.22, .20, .19, .22, .17])
    city_map = {
        "North": ["Delhi", "Chandigarh", "Jaipur"],
        "South": ["Bengaluru", "Chennai", "Hyderabad"],
        "East": ["Kolkata", "Bhubaneswar", "Guwahati"],
        "West": ["Mumbai", "Pune", "Ahmedabad"],
        "Central": ["Indore", "Bhopal", "Nagpur"],
    }
    cities = [rng.choice(city_map[region]) for region in regions]
    plans = rng.choice(["Basic", "Standard", "Premium", "Enterprise"], n_customers, p=[.31, .36, .24, .09])
    plan_price = pd.Series(plans).map({"Basic": 29, "Standard": 55, "Premium": 89, "Enterprise": 159}).to_numpy()
    contracts = rng.choice(["Month-to-month", "One year", "Two year"], n_customers, p=[.52, .30, .18])
    segments = rng.choice(["Consumer", "Small Business", "Mid-Market", "Enterprise"], n_customers, p=[.48, .27, .18, .07])
    signup_offsets = rng.integers(30, 2_050, n_customers)
    signup_dates = SNAPSHOT_DATE - pd.to_timedelta(signup_offsets, unit="D")
    tenure = np.maximum(1, np.rint(signup_offsets / 30.4).astype(int))
    age = np.clip(rng.normal(38, 11, n_customers).round().astype(int), 18, 79)
    discounts = np.clip(rng.normal(8, 7, n_customers), 0, 30).round(1)
    monthly_charges = np.round(plan_price * (1 - discounts / 100) + rng.normal(0, 4, n_customers), 2)
    monthly_charges = np.maximum(monthly_charges, 12)
    services = np.clip((plan_price / 27 + rng.normal(0, 0.8, n_customers)).round(), 1, 8).astype(int)
    support_tickets = rng.poisson(np.where(plans == "Enterprise", 1.8, 1.15), n_customers)
    last_login = np.clip(rng.gamma(2.0, 5.0, n_customers).round(), 0, 80).astype(int)
    usage = np.clip(plan_price * rng.normal(5.8, 1.7, n_customers), 15, 1_600).round(1)
    satisfaction = np.clip(4.5 - support_tickets * .19 - last_login * .012 + rng.normal(0, .55, n_customers), 1, 5).round(1)
    internet = rng.choice(["Fiber", "DSL", "5G Wireless", "None"], n_customers, p=[.47, .24, .22, .07])
    payment = rng.choice(["Credit Card", "Bank Transfer", "Digital Wallet", "Mailed Check"], n_customers, p=[.40, .25, .25, .10])

    logit = (
        -2.35
        + 1.18 * (contracts == "Month-to-month")
        + .55 * (plans == "Basic")
        + .35 * (plans == "Standard")
        + .44 * (support_tickets >= 3)
        + .055 * last_login
        + .72 * (satisfaction <= 2.6)
        + .34 * (tenure <= 6)
        + .25 * (payment == "Mailed Check")
        + .20 * (regions == "East")
        - .52 * (contracts == "Two year")
    )
    churn_probability = _sigmoid(logit)
    churn_binary = rng.binomial(1, churn_probability)
    churn = np.where(churn_binary == 1, "Yes", "No")
    reasons = np.array(["" for _ in range(n_customers)], dtype=object)
    reason_options = np.array(["Price sensitivity", "Low engagement", "Support experience", "Competitor switch", "Product fit"])
    churn_idx = np.where(churn_binary == 1)[0]
    reasons[churn_idx] = rng.choice(reason_options, len(churn_idx), p=[.25, .23, .20, .18, .14])
    churn_date = np.full(n_customers, None, dtype=object)
    for idx in churn_idx:
        max_days = max(1, (SNAPSHOT_DATE - signup_dates[idx]).days - 5)
        churn_date[idx] = (signup_dates[idx] + pd.Timedelta(days=int(rng.integers(1, max_days)))).date().isoformat()

    df = pd.DataFrame(
        {
            "customer_id": customer_id,
            "gender": rng.choice(["Female", "Male", "Non-binary"], n_customers, p=[.48, .48, .04]),
            "age": age,
            "region": regions,
            "city": cities,
            "customer_segment": segments,
            "signup_date": pd.Series(signup_dates).dt.date.astype(str),
            "tenure_months": tenure,
            "subscription_plan": plans,
            "contract_type": contracts,
            "monthly_charges": monthly_charges,
            "total_charges": np.round(monthly_charges * tenure * rng.normal(1, .05, n_customers), 2),
            "payment_method": payment,
            "internet_service": internet,
            "support_tickets": support_tickets,
            "last_login_days": last_login,
            "services_count": services,
            "discount_pct": discounts,
            "satisfaction_score": satisfaction,
            "monthly_usage": usage,
            "churn": churn,
            "churn_reason": reasons,
            "churn_date": churn_date,
            "acquisition_channel": rng.choice(["Organic", "Referral", "Partner", "Paid Search"], n_customers, p=[.32, .24, .18, .26]),
        }
    )

    # Controlled imperfections: they are documented and repaired by the cleaning stage.
    df.loc[rng.choice(df.index, 38, replace=False), "satisfaction_score"] = np.nan
    df.loc[rng.choice(df.index, 22, replace=False), "age"] = rng.choice([-5, 0, 111, 130], 22)
    df.loc[rng.choice(df.index, 16, replace=False), "signup_date"] = "not-a-date"
    df.loc[rng.choice(df.index, 13, replace=False), "monthly_charges"] = rng.choice([-40, 0, 5_000], 13)
    df.loc[rng.choice(df.index, 9, replace=False), "total_charges"] = rng.choice([-100, 0], 9)
    df.loc[rng.choice(df.index, 18, replace=False), "churn"] = rng.choice(["YES", "no", "1", "0", "Churned"], 18)
    df.loc[rng.choice(df.index, 16, replace=False), "subscription_plan"] = rng.choice(["basic", "PREMIUM", "Platinum"], 16)
    df.loc[rng.choice(df.index, 12, replace=False), "region"] = rng.choice(["north", "WEST", "Unknown"], 12)
    df.loc[rng.choice(df.index, 8, replace=False), "support_tickets"] = rng.choice([30, 45], 8)
    df.loc[rng.choice(df.index, 6, replace=False), "monthly_usage"] = 10_000
    df.loc[rng.choice(df.index, 10, replace=False), "gender"] = rng.choice(["F", "M", "Unknown"], 10)
    duplicates = df.sample(45, random_state=seed).copy()
    raw = pd.concat([df, duplicates], ignore_index=True)
    return raw


def write_raw_data(n_customers: int = 5_000, seed: int = RANDOM_SEED) -> pd.DataFrame:
    RAW_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = generate_customers(n_customers=n_customers, seed=seed)
    df.to_csv(RAW_DATA_PATH, index=False)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate fictional churn customers.")
    parser.add_argument("--customers", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()
    created = write_raw_data(args.customers, args.seed)
    print(f"Created {len(created):,} raw rows at {RAW_DATA_PATH}")
