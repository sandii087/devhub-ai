# Power Query Specification

## Source

Primary source:

`data/processed/customers_clean.csv`

The file is produced by the existing Python pipeline. Do not create another fake Power BI dataset.

## Recommended query architecture

Create:

- `FactCustomerSnapshot`
- `DimCustomer`
- `DimPlan`
- `DimRegion`
- `DimContract`
- `DimDate`

Use **Reference** queries from the fact query for dimensions where practical.

---

## FactCustomerSnapshot transformation steps

1. Home → Get Data → Text/CSV.
2. Select `data/processed/customers_clean.csv`.
3. Choose **Transform Data**.
4. Rename the query `FactCustomerSnapshot`.
5. Inspect headers.
6. Replace empty-string `churn_date` values with `null`.
7. Set types:
   - customer_id → Text
   - gender → Text
   - age → Whole Number
   - region → Text
   - city → Text
   - customer_segment → Text
   - signup_date → Date
   - tenure_months → Whole Number
   - subscription_plan → Text
   - contract_type → Text
   - monthly_charges → Decimal Number
   - total_charges → Decimal Number
   - payment_method → Text
   - internet_service → Text
   - support_tickets → Whole Number
   - last_login_days → Whole Number
   - services_count → Whole Number
   - discount_pct → Decimal Number
   - satisfaction_score → Decimal Number
   - monthly_usage → Decimal Number
   - churn → Text
   - churn_reason → Text
   - churn_date → Date
   - acquisition_channel → Text
   - tenure_bucket → Text
   - charge_bucket → Text
   - support_intensity → Text
   - engagement_level → Text
   - customer_value_segment → Text
   - signup_cohort → Text
   - risk_score → Decimal Number
   - risk_segment → Text
   - revenue_at_risk → Decimal Number
   - portfolio_segment → Text

8. Validate that `customer_id` has no nulls.
9. Validate that customer IDs are unique at the fact grain.
10. Validate churn values are Yes/No.
11. Do not re-run the Python cleaning logic in Power Query unless a BI-specific data-type correction is required.

---

## Dimension creation

### DimCustomer

Right-click/reference `FactCustomerSnapshot`.

Keep:
- customer_id
- gender
- city
- customer_segment
- acquisition_channel

Remove duplicates.

`customer_id` is the key.

### DimPlan

Reference the fact query.

Keep:
- subscription_plan

Remove duplicates.

### DimRegion

Reference the fact query.

Keep:
- region

Remove duplicates.

### DimContract

Reference the fact query.

Keep:
- contract_type

Remove duplicates.

---

## DimDate

Create a dedicated date table.

At minimum include:
- Date
- Year
- Month Number
- Month
- Quarter
- Year-Month

Use a continuous calendar covering the minimum signup date through the maximum relevant date in the source.

Mark it as the model's Date table.

For signup-date analysis, create the active relationship:

`DimDate[Date] → FactCustomerSnapshot[signup_date]`

If churn-date analysis is required, create an inactive relationship:

`DimDate[Date] → FactCustomerSnapshot[churn_date]`

and activate it inside dedicated DAX measures with `USERELATIONSHIP`.

---

## Null handling

Do not turn missing churn dates into a fake date such as `1900-01-01`.

Blank churn date means there is no recorded churn date for that customer in the snapshot.

`churn_reason` may contain `Not churned` for retained customers. Preserve that value because it is already part of the processed dataset.

---

## What NOT to recreate

Do not unnecessarily recreate these Python-derived transformations:
- tenure bucket
- charge bucket
- support intensity
- engagement level
- customer value segment
- signup cohort
- risk score
- risk segment
- revenue at risk
- portfolio segment

Those are already present in `customers_clean.csv`.

Power BI should consume these fields rather than silently producing a second competing definition.

---

## Validation checks

After transformations:

### Row count
The fact table should retain the current processed dataset's customer-row count.

### Customer uniqueness
`customer_id` should be unique at fact grain.

### Numeric sanity
Check:
- monthly_charges is numeric
- total_charges is numeric
- risk_score is numeric
- revenue_at_risk is numeric

### Category sanity
Check:
- churn = Yes/No
- risk_segment uses the expected Low/Medium/High categories
- portfolio_segment uses the four documented value/risk combinations

### Date sanity
Check:
- signup_date is Date
- churn_date is Date or null

---

## Optional M template

The following is a starting point for the main import query. Update the file path to the location of the repository on the machine running Power BI.

```powerquery
let
    Source = Csv.Document(
        File.Contents("C:\PATH\TO\Customer Churn & Retention Intelligence\data\processed\customers_clean.csv"),
        [Delimiter=",", Columns=34, Encoding=65001, QuoteStyle=QuoteStyle.Csv]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    BlankChurnDatesToNull = Table.ReplaceValue(
        PromotedHeaders,
        "",
        null,
        Replacer.ReplaceValue,
        {"churn_date"}
    ),
    Typed = Table.TransformColumnTypes(
        BlankChurnDatesToNull,
        {
            {"customer_id", type text},
            {"gender", type text},
            {"age", Int64.Type},
            {"region", type text},
            {"city", type text},
            {"customer_segment", type text},
            {"signup_date", type date},
            {"tenure_months", Int64.Type},
            {"subscription_plan", type text},
            {"contract_type", type text},
            {"monthly_charges", type number},
            {"total_charges", type number},
            {"payment_method", type text},
            {"internet_service", type text},
            {"support_tickets", Int64.Type},
            {"last_login_days", Int64.Type},
            {"services_count", Int64.Type},
            {"discount_pct", type number},
            {"satisfaction_score", type number},
            {"monthly_usage", type number},
            {"churn", type text},
            {"churn_reason", type text},
            {"churn_date", type date},
            {"acquisition_channel", type text},
            {"tenure_bucket", type text},
            {"charge_bucket", type text},
            {"support_intensity", type text},
            {"engagement_level", type text},
            {"customer_value_segment", type text},
            {"signup_cohort", type text},
            {"risk_score", type number},
            {"risk_segment", type text},
            {"revenue_at_risk", type number},
            {"portfolio_segment", type text}
        }
    )
in
    Typed
```

The `Columns=34` setting should be changed if the upstream Python schema changes.

---

## Power Query design principle

Power Query should be the controlled boundary between the Python-produced analytical dataset and the Power BI semantic model.

Do not maintain two independent business definitions for churn risk, customer value or revenue at risk.
