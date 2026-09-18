# DAX Measures — Customer Churn & Retention Intelligence

All measures below are designed for the `FactCustomerSnapshot` fact table and the dimensions described in `README.md`.

## Core customer measures

### Total Customers

```DAX
Total Customers =
DISTINCTCOUNT ( FactCustomerSnapshot[customer_id] )
```

Counts unique customers at the customer-snapshot grain.

### Churned Customers

```DAX
Churned Customers =
CALCULATE (
    [Total Customers],
    FactCustomerSnapshot[churn] = "Yes"
)
```

Counts customers whose observed churn label is `Yes`.

### Retained Customers

```DAX
Retained Customers =
CALCULATE (
    [Total Customers],
    FactCustomerSnapshot[churn] = "No"
)
```

Counts customers whose observed churn label is `No`.

### Churn Rate

```DAX
Churn Rate =
DIVIDE (
    [Churned Customers],
    [Total Customers],
    0
)
```

Format as Percentage.

### Retention Rate

```DAX
Retention Rate =
DIVIDE (
    [Retained Customers],
    [Total Customers],
    0
)
```

Format as Percentage.

---

## Revenue measures

### Average Monthly Charges

```DAX
Average Monthly Charges =
AVERAGE ( FactCustomerSnapshot[monthly_charges] )
```

Average customer monthly charge in the current filter context.

### Total Monthly Revenue

```DAX
Total Monthly Revenue =
SUM ( FactCustomerSnapshot[monthly_charges] )
```

The sum of customer monthly charges represented by the current snapshot.

Use this as the report's MRR-style measure and label it clearly as monthly recurring revenue represented by the snapshot.

### Revenue at Risk

```DAX
Revenue at Risk =
SUM ( FactCustomerSnapshot[revenue_at_risk] )
```

Expected monthly revenue exposure represented by the model risk output.

Do not describe this as realized revenue loss.

### Average Tenure

```DAX
Average Tenure =
AVERAGE ( FactCustomerSnapshot[tenure_months] )
```

Format as a number with one decimal place and label as months.

### Average Satisfaction

```DAX
Average Satisfaction =
AVERAGE ( FactCustomerSnapshot[satisfaction_score] )
```

### Average Support Tickets

```DAX
Average Support Tickets =
AVERAGE ( FactCustomerSnapshot[support_tickets] )
```

---

## Risk and value measures

### High Risk Customers

```DAX
High Risk Customers =
CALCULATE (
    [Total Customers],
    FactCustomerSnapshot[risk_segment] = "High Risk"
)
```

### High Value Customers

```DAX
High Value Customers =
CALCULATE (
    [Total Customers],
    FactCustomerSnapshot[customer_value_segment] = "High Value"
)
```

### High Value High Risk Customers

```DAX
High Value High Risk Customers =
CALCULATE (
    [Total Customers],
    FactCustomerSnapshot[portfolio_segment] = "High Value / High Risk"
)
```

### Average Risk Score

```DAX
Average Risk Score =
AVERAGE ( FactCustomerSnapshot[risk_score] )
```

Format as Percentage if displaying the probability as a percentage.

---

## Churn analysis measures

These are reusable measures; put dimensions such as Plan, Region, Contract Type or Tenure Bucket on the chart axis.

### Churned Customer %

```DAX
Churned Customer % =
[Churn Rate]
```

This alias can make chart field selection clearer.

### Churned Revenue Exposure

```DAX
Revenue at Risk per Customer =
DIVIDE (
    [Revenue at Risk],
    [Total Customers],
    0
)
```

Useful in tooltip contexts.

---

## Portfolio measures

### Portfolio Revenue

```DAX
Portfolio Revenue =
[Total Monthly Revenue]
```

Use `portfolio_segment` as the visual axis.

### Portfolio Revenue at Risk

```DAX
Portfolio Revenue at Risk =
[Revenue at Risk]
```

Use `portfolio_segment` as the visual axis.

### Portfolio Churn Rate

```DAX
Portfolio Churn Rate =
[Churn Rate]
```

Use `portfolio_segment` as the visual axis.

---

## Optional model-risk measure

### High Risk Revenue at Risk

```DAX
High Risk Revenue at Risk =
CALCULATE (
    [Revenue at Risk],
    FactCustomerSnapshot[risk_segment] = "High Risk"
)
```

This isolates expected monthly exposure associated with customers classified as High Risk.

---

## Optional churn-date measures

The current dataset contains `churn_date`, but it is a snapshot rather than a full event fact table.

If `DimDate[Date]` has an **inactive** relationship to `FactCustomerSnapshot[churn_date]`, the following measure can be used for churn-date analysis:

```DAX
Churned Customers by Churn Date =
CALCULATE (
    [Churned Customers],
    USERELATIONSHIP (
        DimDate[Date],
        FactCustomerSnapshot[churn_date]
    )
)
```

Do not make both signup date and churn date active relationships to the same date dimension.

---

## Suggested formatting

| Measure | Format |
|---|---|
| Total Customers | Whole number |
| Churned Customers | Whole number |
| Retained Customers | Whole number |
| Churn Rate | Percentage, 1–2 decimals |
| Retention Rate | Percentage, 1–2 decimals |
| Average Monthly Charges | Currency, 2 decimals |
| Total Monthly Revenue | Currency, 2 decimals |
| Revenue at Risk | Currency, 2 decimals |
| Average Tenure | Number, 1 decimal |
| Average Satisfaction | Number, 2 decimals |
| Average Support Tickets | Number, 2 decimals |
| High Risk Customers | Whole number |
| High Value Customers | Whole number |
| High Value High Risk Customers | Whole number |
| Average Risk Score | Percentage, 1–2 decimals |

## Measure design principle

Do not create separate hardcoded measures such as `North Revenue = ...` or `Premium Churn = ...`.

Use generic measures and let the dimension on the visual/slicer establish filter context. This keeps the report interactive and scalable.
