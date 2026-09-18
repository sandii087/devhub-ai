-- One customer snapshot per row. Data is generated locally and is synthetic.
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  gender TEXT NOT NULL,
  age INTEGER NOT NULL CHECK(age BETWEEN 18 AND 90),
  region TEXT NOT NULL,
  city TEXT NOT NULL,
  customer_segment TEXT NOT NULL,
  signup_date TEXT NOT NULL,
  tenure_months INTEGER NOT NULL,
  subscription_plan TEXT NOT NULL,
  contract_type TEXT NOT NULL,
  monthly_charges REAL NOT NULL,
  total_charges REAL NOT NULL,
  payment_method TEXT NOT NULL,
  internet_service TEXT NOT NULL,
  support_tickets INTEGER NOT NULL,
  last_login_days INTEGER NOT NULL,
  services_count INTEGER NOT NULL,
  discount_pct REAL NOT NULL,
  satisfaction_score REAL NOT NULL,
  monthly_usage REAL NOT NULL,
  churn TEXT NOT NULL CHECK(churn IN ('Yes', 'No')),
  churn_reason TEXT NOT NULL,
  churn_date TEXT,
  acquisition_channel TEXT NOT NULL,
  tenure_bucket TEXT NOT NULL,
  charge_bucket TEXT NOT NULL,
  support_intensity TEXT NOT NULL,
  engagement_level TEXT NOT NULL,
  customer_value_segment TEXT NOT NULL,
  signup_cohort TEXT NOT NULL,
  risk_score REAL NOT NULL CHECK(risk_score BETWEEN 0 AND 1),
  risk_segment TEXT NOT NULL,
  revenue_at_risk REAL NOT NULL,
  portfolio_segment TEXT NOT NULL
);

CREATE INDEX idx_customers_churn ON customers(churn);
CREATE INDEX idx_customers_region ON customers(region);
CREATE INDEX idx_customers_risk ON customers(risk_segment, risk_score DESC);
CREATE INDEX idx_customers_cohort ON customers(signup_cohort);
