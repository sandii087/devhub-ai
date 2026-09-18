# Customer Churn & Retention Intelligence — Power BI

## 1. Purpose

This folder documents a Power BI Desktop deliverable that complements the existing Customer Churn & Retention Intelligence application.

The existing project already demonstrates:
- Python/Pandas/NumPy data preparation
- SQL/SQLite analytics
- Logistic Regression churn prediction
- FastAPI
- React + TypeScript

The Power BI layer is intentionally focused on:
- Power Query
- dimensional/star-schema thinking
- DAX measures
- interactive business reporting
- segmentation and retention analysis
- drill-through and report usability

**Important:** No `.pbix` file is claimed or included. This repository contains the source-data instructions, model design, Power Query guidance, DAX, report layout, and recreation steps needed to build the report in Power BI Desktop.

---

## 2. Data source

### Primary source

Import:

`data/processed/customers_clean.csv`

This is the processed customer dataset produced by the existing Python pipeline.

It contains 5,000 customer records in the currently inspected project output and includes the original customer/business fields plus engineered fields such as:

- `tenure_bucket`
- `charge_bucket`
- `support_intensity`
- `engagement_level`
- `customer_value_segment`
- `signup_cohort`
- `risk_score`
- `risk_segment`
- `revenue_at_risk`
- `portfolio_segment`

The dataset is synthetic/fictional. It must be labeled as synthetic in the Power BI report.

### Source-of-truth rule

Do not manually enter KPI values into Power BI.

Power BI measures must calculate from the imported processed dataset. If the Python pipeline is rerun, refresh Power BI so the report reflects the new output.

---

## 3. Python vs Power Query responsibilities

### Python pipeline — upstream responsibilities

The existing Python project is responsible for:
- synthetic-data generation
- controlled data-quality issues
- duplicate removal
- categorical normalization
- invalid-value repair
- missing-value treatment
- charge/date cleanup
- business feature engineering
- churn-model training
- model risk probability
- risk segmentation
- revenue-at-risk calculation

These existing transformations should **not be unnecessarily recreated in Power Query**.

### Power Query — BI responsibilities

Power Query should focus on:
- importing `customers_clean.csv`
- enforcing BI-friendly data types
- converting blank date values to null
- validating required fields
- removing columns that are genuinely unnecessary for the report
- creating/maintaining dimension reference queries
- creating a clean date dimension if required

This separation keeps Python as the analytical data pipeline and Power BI as the BI/reporting layer.

---

## 4. Recommended data model

Use a practical star-schema design rather than creating unnecessary tables.

### Fact table

**FactCustomerSnapshot**

Grain: **one row per customer in the analytical snapshot**.

Recommended columns retained:
- `customer_id`
- `gender`
- `age`
- `region`
- `city`
- `customer_segment`
- `signup_date`
- `tenure_months`
- `subscription_plan`
- `contract_type`
- `monthly_charges`
- `total_charges`
- `payment_method`
- `internet_service`
- `support_tickets`
- `last_login_days`
- `services_count`
- `discount_pct`
- `satisfaction_score`
- `monthly_usage`
- `churn`
- `churn_reason`
- `churn_date`
- `acquisition_channel`
- `tenure_bucket`
- `charge_bucket`
- `support_intensity`
- `engagement_level`
- `customer_value_segment`
- `signup_cohort`
- `risk_score`
- `risk_segment`
- `revenue_at_risk`
- `portfolio_segment`

### Dimensions

Create these dimensions as Power Query reference queries:

**DimCustomer**
- customer_id
- gender
- city
- customer_segment
- acquisition_channel

**DimPlan**
- subscription_plan

**DimRegion**
- region

**DimContract**
- contract_type

**DimDate**
- Date
- Year
- Month Number
- Month
- Year-Month
- Quarter

For this snapshot-style dataset, dimensions are primarily used to provide clean filtering and star-schema structure. Do not invent historical fact rows.

### Relationships

Recommended relationships:

| From | To | Cardinality | Filter direction |
|---|---|---|---|
| DimCustomer[customer_id] | FactCustomerSnapshot[customer_id] | 1:* | Single |
| DimPlan[subscription_plan] | FactCustomerSnapshot[subscription_plan] | 1:* | Single |
| DimRegion[region] | FactCustomerSnapshot[region] | 1:* | Single |
| DimContract[contract_type] | FactCustomerSnapshot[contract_type] | 1:* | Single |
| DimDate[Date] | FactCustomerSnapshot[signup_date] | 1:* | Single |

### Churn-date caveat

Do **not** create a second active relationship from `DimDate[Date]` to `FactCustomerSnapshot[churn_date]`.

If churn-date analysis is needed, use an inactive relationship and a dedicated measure with `USERELATIONSHIP`, or use a separate churn-event fact table if the project is later expanded into true event-level history.

The current dataset is a customer snapshot, not a full monthly transaction/event history.

---

## 5. Report pages

### Page 1 — Executive Overview

Purpose: executive-level view of customer health, churn exposure and revenue risk.

KPI cards:
- Total Customers
- Churn Rate
- Retention Rate
- Total Monthly Revenue / MRR
- Revenue at Risk
- High-Risk Customers

Visuals:
1. Churn trend by churn month
2. Churn rate by contract type
3. Churn rate by subscription plan
4. Revenue at risk by region
5. Customer count by customer segment
6. Optional compact risk distribution

Recommended slicers:
- Region
- Subscription Plan
- Contract Type
- Customer Segment
- Risk Segment

---

### Page 2 — Churn Analysis

Purpose: understand where observed churn is concentrated.

Visuals:
- Churn rate by subscription plan
- Churn rate by contract type
- Churn rate by region
- Churn rate by tenure bucket
- Churn rate by satisfaction score
- Churn rate by payment method
- Churn trend

Recommended slicers:
- Region
- Subscription Plan
- Contract Type
- Customer Segment
- Tenure Bucket
- Payment Method

Use bar/column charts rather than excessive pie charts.

---

### Page 3 — Customer Segmentation

Purpose: connect customer value with model risk.

Primary visual:
- Portfolio segment matrix/table

Segments:
- High Value / High Risk
- High Value / Low Risk
- Low Value / Low Risk
- Low Value / High Risk

Show:
- Customer count
- Churn rate
- Revenue
- Revenue at risk
- Average tenure
- Average satisfaction

Add a stacked/clustered visual for customer count or revenue by portfolio segment.

---

### Page 4 — Risk & Revenue

Purpose: translate model scores into business exposure.

Visuals:
- Risk distribution
- High-risk customer count
- Revenue at risk
- Risk by plan
- Risk by region
- Risk by customer segment

Use:
- `risk_score` for continuous model probability analysis
- `risk_segment` for Low/Medium/High grouping
- `revenue_at_risk` for expected monthly exposure

Do not describe `revenue_at_risk` as actual lost revenue. It is an expected monthly exposure derived from the model probability and monthly charges.

---

### Page 5 — Cohort / Retention

Purpose: understand retention by signup cohort and customer tenure.

Visuals:
- Cohort retention matrix/heatmap
- Signup cohort customer count
- Retention trend
- Cohort size

Important limitation:
The current dataset is a snapshot and does not contain a complete monthly customer-status history. The existing Python pipeline already calculates a tenure-period retention view from signup/churn dates. Power BI should not imply that it has true transaction-level historical activity unless the underlying data is expanded later.

---

## 6. Slicers

Recommended global slicers:
- Region
- Subscription Plan
- Contract Type
- Customer Segment
- Risk Segment
- Tenure Bucket
- Payment Method

Use synced slicers only where they improve navigation. Avoid forcing every slicer onto every page.

---

## 7. Drill-through

Create a **Customer Detail** drill-through page.

Drill-through field:
- `customer_id`

Show:
- Customer ID
- Customer segment
- Region/city
- Subscription plan
- Contract type
- Tenure
- Monthly charges
- Satisfaction
- Support tickets
- Recent login days
- Risk score
- Risk segment
- Revenue at risk
- Churn status
- Churn reason
- Acquisition channel

Add a clear "Back" button.

The drill-through page should answer:

> What does this customer's profile and model risk look like?

Do not present rule-based factors as causal explanations. The current backend has rule-based contextual risk factors; the Power BI report should distinguish those from the model's probability.

---

## 8. Tooltips

Useful tooltip pages:
- `tt_Risk`: risk score, risk segment, customer count, revenue at risk
- `tt_Churn`: customer count, churned customers, churn rate
- `tt_Revenue`: monthly revenue, revenue at risk, average monthly charge

Keep tooltips compact. They should add context rather than duplicate the entire report page.

---

## 9. Business questions answered

The report should allow an interviewer or business user to answer:

1. How large is the customer base?
2. What is the observed churn rate?
3. What is the retained customer rate?
4. What is current monthly recurring revenue represented by customer monthly charges?
5. How much expected monthly revenue exposure is associated with model risk?
6. Which plans have different observed churn rates?
7. How does contract type relate to churn?
8. Which regions have higher observed churn or revenue exposure?
9. Which customer segments have different churn patterns?
10. How does churn vary by tenure?
11. How does satisfaction relate to observed churn?
12. Which payment methods show different churn rates?
13. How is model risk distributed?
14. Which customer-value/risk portfolio groups contain the most customers or revenue?
15. How do signup cohorts differ in retention?

---

## 10. How to open/build in Power BI Desktop

1. Install/open Power BI Desktop.
2. Open the existing project folder:
   `Customer Churn & Retention Intelligence`
3. Select **Home → Get data → Text/CSV**.
4. Import:
   `data/processed/customers_clean.csv`
5. Select **Transform Data**.
6. Apply the Power Query steps documented in `powerbi/power_query.md` and the supplied `powerbi/power_query.m`.
7. Rename the main query to `FactCustomerSnapshot`.
8. Create the dimension queries from references of the fact query.
9. Create `DimDate`.
10. Close & Apply.
11. Open **Model view** and create the documented relationships.
12. Create the DAX measures from `dax_measures.md`.
13. Build the five report pages using `report_design.md`.
14. Add the recommended slicers.
15. Add the Customer Detail drill-through page.
16. Add tooltip pages where useful.
17. Test slicer propagation and drill-through.
18. Refresh after rerunning the Python pipeline.
19. Save the actual Power BI Desktop file as:
   `powerbi/Customer_Churn_Retention_Intelligence.pbix`

**Only after you personally save that file should the repository claim that a PBIX exists.**

---

## 11. Validation checklist

Before considering the report complete:

- [ ] Fact table contains one row per customer.
- [ ] Customer ID is unique at fact grain.
- [ ] Numeric columns have numeric types.
- [ ] Signup and churn dates are date types.
- [ ] Blank churn dates remain null.
- [ ] Churn contains only Yes/No.
- [ ] Risk segment contains the expected categories.
- [ ] No KPI values are manually typed into cards.
- [ ] DAX measures are used for KPI calculations.
- [ ] Dimension relationships are 1:* and single-direction where appropriate.
- [ ] Slicers change relevant visuals.
- [ ] Drill-through opens the intended customer context.
- [ ] Revenue at risk is treated as expected exposure, not realized loss.
- [ ] Synthetic-data disclosure is visible.
- [ ] Model performance is clearly identified as synthetic-data performance.
- [ ] No `.pbix` is claimed until an actual PBIX is saved.

---

## 12. Limitations

- The dataset is synthetic and fictional.
- The model was trained on a synthetic snapshot, so its performance does not establish production predictive power.
- The current fact table represents a customer snapshot rather than a complete longitudinal event history.
- Power BI does not replace the existing Python ML pipeline.
- `risk_score` is a model likelihood estimate, not a causal explanation.
- `revenue_at_risk` is expected monthly exposure based on model risk and monthly charges, not realized churned revenue.
- Production use would require time-based validation, model monitoring, calibration, fairness testing, and fresh behavioral data.
