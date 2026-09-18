# Power BI Model — Star Schema

## Model grain

`FactCustomerSnapshot` contains one record per customer for the analytical snapshot.

This is not a monthly transaction fact table.

## Tables

### FactCustomerSnapshot

Business purpose:
Customer-level analytical snapshot containing observed churn outcome, commercial attributes, behavior, engineered features and model-risk output.

Key:
`customer_id`

### DimCustomer

Customer descriptive attributes:
- customer_id
- gender
- city
- customer_segment
- acquisition_channel

Key:
`customer_id`

### DimPlan

Plan lookup:
- subscription_plan

Key:
`subscription_plan`

### DimRegion

Geographic lookup:
- region

Key:
`region`

### DimContract

Contract lookup:
- contract_type

Key:
`contract_type`

### DimDate

Calendar attributes:
- Date
- Year
- Month Number
- Month
- Quarter
- Year-Month

Key:
`Date`

---

## Relationship diagram

```text
                 DimCustomer
                     |
                     | 1 : *
                     v
DimPlan ------> FactCustomerSnapshot <------ DimRegion
   1 : *                 |                     1 : *
                        |
                        | 1 : *
                        v
                 DimContract

                     ^
                     |
                  1 : *
                     |
                  DimDate
```

All dimensions filter toward the fact table.

Preferred filter direction:
**Single**

Avoid unnecessary bidirectional relationships because they can introduce ambiguous filter paths.

---

## Date relationships

Active:

`DimDate[Date] 1 → * FactCustomerSnapshot[signup_date]`

Optional inactive:

`DimDate[Date] 1 → * FactCustomerSnapshot[churn_date]`

The churn-date relationship should be inactive if signup date is the model's active date relationship.

---

## Why this model is appropriate

A star schema separates:
- descriptive/filtering attributes in dimensions
- measurable customer observations in the fact

This makes DAX filter context easier to reason about and prevents a report from becoming a collection of duplicated tables.

The model remains intentionally small because the source itself is a single customer snapshot.

A much larger constellation of artificial dimensions would add complexity without adding analytical value.

---

## Future extension

If the project later gains monthly customer snapshots or event-level data, the model can evolve toward:

- FactCustomerMonthlySnapshot
- FactChurnEvent
- FactSupportEvent
- DimCustomer
- DimDate
- DimPlan
- DimRegion
- DimContract

That would support true longitudinal retention, survival and event analysis.
