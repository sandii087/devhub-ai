# Customer Churn & Retention Intelligence

A full-stack portfolio project for exploring churn, retention, customer risk, and revenue exposure in a fictional subscription business. It is a runnable local analytics platform—not a static dashboard: Python creates and cleans data, SQLite stores the scored snapshot, FastAPI serves calculated responses, and React renders those live responses.

> **Data disclaimer:** every customer record in this repository is synthetic, generated locally with a fixed seed. The project makes no claim about a real company, client, or production deployment.

## What it answers

- Which plans, contracts, regions, payment methods, and customer segments experience the most churn?
- How do tenure, satisfaction, support activity, and engagement relate to churn in this snapshot?
- How many customers are predicted to be at high risk, and what is the probability-weighted monthly revenue exposure?
- Which high-value customers need retention review first?
- How does active-customer retention change by signup cohort?

## Built features

- Reproducible synthetic-data generator with 5,000 unique customers and controlled real-world-style quality problems.
- Validation, cleaning, outlier handling, feature engineering, and a machine-readable quality report.
- Local SQLite database plus 16 executable, business-focused SQL questions.
- Reusable Pandas/NumPy analytics for KPIs, churn cuts, segments, risk, cohorts, and computed business insights.
- Leakage-aware, class-balanced Logistic Regression churn baseline, real holdout metrics, serialized model, and model-derived customer risk scores.
- FastAPI endpoints that query the local database/report/model artifacts—no dashboard KPI JSON is hard-coded.
- Vite, React, TypeScript, Tailwind dashboard with eight responsive analysis pages, empty/loading/error states, filters, and a customer risk-detail modal.
- Pytest coverage for cleaning, feature engineering, analytics, SQL validation, and API endpoints.

## Architecture

```text
synthetic raw CSV
      ↓ validation + cleaning report
clean CSV + business features
      ↓ train / evaluate Logistic Regression
scored customer CSV + model artifacts
      ↓ SQLite load + SQL validation
FastAPI analytics endpoints
      ↓
React / TypeScript dashboard
```

## Technology

Python 3.9+, Pandas, NumPy, scikit-learn, SQLite, FastAPI, Uvicorn, pytest, React, TypeScript, Vite, Tailwind CSS, and Recharts.

## Project layout

```text
customer-churn-retention-intelligence/
├── data/                 # generated raw and processed synthetic CSVs (Git-ignored)
├── database/             # schema + 16 analysis queries
├── src/
│   ├── data/             # generator, validation, cleaning, feature engineering
│   ├── analytics/        # reusable KPI, churn, segment, cohort insights
│   ├── ml/               # preprocessing, training, evaluation, risk scoring
│   └── database/         # SQLite creation and query validation
├── backend/app/          # FastAPI routes and database-backed services
├── backend/tests/        # API tests
├── frontend/             # React dashboard
├── tests/                # pipeline, analytics, database tests
├── reports/              # reproducible JSON reports (Git-ignored)
├── models/               # serialized model (Git-ignored)
└── docs/interview_guide.md
```

## Data pipeline and quality controls

`src.data.generate` creates 5,045 raw rows: 5,000 customers plus exact duplicate records. The generator deliberately introduces missing satisfaction, malformed signup dates, impossible ages, invalid charges, inconsistent category capitalization, invalid labels, and controlled support/usage outliers.

The cleaning stage removes duplicates, canonicalizes categories, repairs invalid dates from tenure and the fixed analytical snapshot, imputes valid-group/median values, rebuilds invalid charges, caps controlled outliers, and creates consistent churn-date/reason fields. A before/after report is written to `reports/data_quality_report.json`.

Feature rules are documented in [data/README.md](data/README.md). The analytical grain is one clean row per customer.

## SQL analysis

[database/business_questions.sql](database/business_questions.sql) has 16 executable queries. They cover overall churn/retention, plan/contract/region/segment cuts, charges, high-exposure customers, high-value high-risk customers, tenure, payment, satisfaction, support, monthly churn, revenue exposure, ranking with a window function, and an above-average plan subquery. The validation step executes every query after the database is built.

## Machine learning and risk scoring

The target is `churn == Yes`. The model uses only pre-outcome customer profile, subscription, engagement, support, satisfaction, and usage attributes. It explicitly excludes churn, churn reason/date, risk fields, and other outcome-derived values. Numeric features are median-imputed and standardized; categorical features are mode-imputed and one-hot encoded. A stratified 75/25 train/test split evaluates a class-balanced Logistic Regression model; a final model is then fitted on all cleaned records strictly for the dashboard's current risk scores.

Risk score is the fitted model's predicted churn probability:

- Low Risk: ≤ 0.33
- Medium Risk: > 0.33 to ≤ 0.66
- High Risk: > 0.66
- Revenue at risk: `monthly_charges × risk_score` (expected monthly revenue exposure)

The four portfolio segments combine a median lifetime-value rule (`monthly_charges × tenure_months`) with high-risk versus non-high-risk model bands. This is transparent for analysis, not a production retention policy.

Accuracy is not sufficient for churn work because churn is a minority class: a model can look accurate while missing many likely churners. The dashboard therefore also shows precision, recall, F1, ROC-AUC, and a confusion matrix.

## API

Start the pipeline first, then FastAPI exposes:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | basic health check |
| `GET /api/overview` | KPI cards, trends, segments, calculated insights |
| `GET /api/churn?plan=&region=` | filterable churn cuts |
| `GET /api/segments` | portfolio-segment metrics |
| `GET /api/risk` | risk distribution and revenue exposure |
| `GET /api/customers?search=&risk_segment=&page=&page_size=` | paginated risk queue |
| `GET /api/customer/{customer_id}` | customer context and transparent elevated-risk factors |
| `GET /api/cohorts` | cohort retention matrix data |
| `GET /api/model` | actual model methodology and metrics |
| `GET /api/data-quality` | before/after quality report |
| `GET /api/insights` | calculated business statements |

## Power BI

A Power BI business-intelligence report is included alongside the React dashboard.

The report contains five analysis pages:

1. Churn Dashboard
2. Customer Churn Analysis
3. Churn by Contract
4. Customer Risk Analysis
5. Customer Segmentation & Insights

Power BI deliverables and documentation are available in `powerbi/`:

- `Cusstomer_Churn_Retention_Intelligence.pbix`
- `README.md`
- `dax_measures.md`
- `model_schema.md`
- `power_query.md`
- `report_design.md`
- `portfolio_and_interview.md`

The Power BI report uses the processed customer dataset and complements the React/FastAPI application with a business-intelligence reporting layer.

## Dashboard pages

Overview, Churn Analytics, Customer Segments, Risk Explorer, Cohort Analysis, Model Performance, Insights, and Data Quality. The UI intentionally uses a restrained analytics visual system: responsive tables/charts, a collapsible mobile sidebar, accessible labels, loading and error states, and a searchable risk-customer panel.

## Run locally

```bash
# 1. Python environment and dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Generate raw data, clean it, train/evaluate the model, build SQLite, validate 16 SQL queries
.venv/bin/python -m src.run_pipeline

# 3. Run API in terminal one
.venv/bin/uvicorn backend.app.main:app --reload --port 8000

# 4. Run dashboard in terminal two
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). The frontend expects the API at `http://localhost:8000/api`; set `VITE_API_BASE_URL` if you use a different API host or port.

## Test and build

```bash
# Run after the data pipeline, from project root
.venv/bin/python -m pytest -q

# Compile the frontend
cd frontend && npm run build
```

## Reproducible snapshot results

With seed `20260917`, the latest validated run produced 5,045 raw rows and 5,000 clean unique customer records. Observed churn is **32.96%**, current MRR is **$296,027**, expected monthly revenue at risk is **$134,797**, and 891 customers are in the High Risk band. The Logistic Regression holdout metrics were Accuracy **0.6192**, Precision **0.4489**, Recall **0.6820**, F1 **0.5414**, and ROC-AUC **0.6968**.

These figures are deterministic for the current code/seed but should always be reproduced by running the pipeline rather than copied into another system.

## Limitations and next steps

- The dataset and its relationships are synthetic; model metrics do not demonstrate real-world performance.
- The snapshot lacks real event-level product telemetry and intervention outcomes; it cannot establish causality.
- A production model would require time-based validation, calibration, drift monitoring, fairness evaluation, secure data governance, and human review of retention decisions.
- Useful extensions include a warehouse-backed ingestion layer, authenticated roles, scheduled refresh, experiment tracking, event cohorts, and treatment-effect analysis.

See [docs/interview_guide.md](docs/interview_guide.md) for an interview-ready walkthrough that stays within these limitations.
