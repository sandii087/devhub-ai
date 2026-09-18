# Power BI Report Design Specification

## Design language

The report should look like a restrained enterprise analytics product.

Recommended palette:
- Deep navy/charcoal for primary text and navigation
- Teal for positive/neutral analytical emphasis
- Amber for attention
- Coral/red only for churn/risk
- Off-white/light gray page background
- White visual containers

Avoid:
- 3D charts
- decorative gradients
- excessive card borders
- unnecessary pie charts
- dense visual walls
- rainbow color schemes

Use one typography family consistently and keep chart titles short.

---

# Page 1 — Executive Overview

### Layout

Top:
- Page title: **Customer Churn & Retention Intelligence**
- Subtitle: **Executive overview • synthetic subscription-company dataset**
- Last-refresh indicator if desired

KPI row:
1. Total Customers
2. Churn Rate
3. Retention Rate
4. Total Monthly Revenue
5. Revenue at Risk
6. High Risk Customers

Middle:
- Left 2/3: churn trend
- Right 1/3: customer segment distribution

Bottom:
- Churn by contract type
- Churn by subscription plan
- Revenue at risk by region

### Interaction

Global slicers:
- Region
- Subscription Plan
- Contract Type
- Customer Segment
- Risk Segment

Use report-level/synced slicers carefully so the page remains uncluttered.

---

# Page 2 — Churn Analysis

### Header

**Observed Churn Analysis**

Subtitle:
**Where is observed churn concentrated across the customer portfolio?**

Visual grid:
- Churn by subscription plan
- Churn by contract type
- Churn by region
- Churn by tenure bucket
- Churn by satisfaction
- Churn by payment method

Full-width lower visual:
- Churn trend by churn month

### Recommended visual types

- Horizontal bars for many categories
- Clustered columns for short category lists
- Line chart for time
- Matrix only where cross-tab comparison is valuable

Use a consistent churn color and keep axes readable.

---

# Page 3 — Customer Segmentation

### Header

**Customer Value × Risk**

Primary visual:
A table/matrix with:

| Portfolio Segment | Customers | Churn Rate | Revenue | Revenue at Risk | Avg Tenure | Avg Satisfaction |
|---|---:|---:|---:|---:|---:|---:|

Rows:
- High Value / High Risk
- High Value / Low Risk
- Low Value / High Risk
- Low Value / Low Risk

Supporting visuals:
- Customer count by portfolio segment
- Revenue at risk by portfolio segment
- Average risk score by portfolio segment

### Design intent

This page should make the relationship between **customer value** and **model risk** easy to understand.

Do not rank the segments as "best" or "worst"; simply show their measured business metrics.

---

# Page 4 — Risk & Revenue

### Header

**Risk & Revenue Exposure**

Top:
- High Risk Customers
- High Risk Revenue at Risk
- Average Risk Score
- Total Monthly Revenue

Visuals:
1. Risk-segment distribution
2. Revenue at risk by subscription plan
3. Revenue at risk by region
4. Revenue at risk by customer segment
5. Risk score distribution or risk-by-plan chart

### Key explanatory text

Add a small footnote:

> Risk score represents the logistic-regression model's estimated churn probability for this synthetic snapshot. Revenue at risk represents expected monthly exposure calculated from customer monthly charges and risk score; it is not realized revenue loss.

This prevents business users from confusing predicted exposure with actual lost revenue.

---

# Page 5 — Cohort / Retention

### Header

**Cohort & Retention Analysis**

Main visual:
- Cohort retention matrix/heatmap

Rows:
- Signup cohort

Columns:
- Tenure period/month

Values:
- Retention rate

Supporting visuals:
- Cohort size
- Retention trend
- Selected cohort detail

### Important caveat

The current source is a customer snapshot, not a complete historical event table. Therefore this page should not imply the existence of transaction-level monthly history.

If the project later receives monthly snapshots/events, this page can be upgraded to a true longitudinal cohort model.

---

# Drill-through Page — Customer Detail

Drill-through field:
- `customer_id`

Header:
**Customer Detail**

Identity:
- Customer ID
- Region
- City
- Customer Segment
- Acquisition Channel

Commercial:
- Plan
- Contract
- Monthly Charges
- Total Charges
- Tenure

Behavior:
- Monthly Usage
- Last Login Days
- Services Count
- Support Tickets
- Satisfaction

Risk:
- Risk Score
- Risk Segment
- Revenue at Risk
- Portfolio Segment

Outcome:
- Churn
- Churn Date
- Churn Reason

Add:
- Back button
- compact risk indicator
- tooltip where useful

---

# Tooltip Page — Risk

Show:
- Risk score
- Risk segment
- Customer count
- Revenue at risk
- Average monthly charge

Use when hovering over risk-related charts.

---

# Tooltip Page — Churn

Show:
- Customer count
- Churned customers
- Churn rate
- Retention rate

---

# Tooltip Page — Revenue

Show:
- Total monthly revenue
- Revenue at risk
- Average monthly charges

---

# Navigation

Use a compact left or top navigation:

1. Overview
2. Churn
3. Segmentation
4. Risk & Revenue
5. Cohorts

Keep Customer Detail as a drill-through destination rather than a primary dashboard page.

---

# Accessibility and usability

- Ensure sufficient text/background contrast.
- Don't encode meaning with color alone.
- Add data labels only where they improve readability.
- Use descriptive visual titles.
- Avoid overly small fonts.
- Keep slicers in a consistent position.
- Make the report usable at normal laptop resolution.
- Add alt text to important visuals if publishing through Power BI accessibility features.

---

# React vs Power BI differentiation

The React dashboard should remain the application-style experience.

Power BI should emphasize:
- slice-and-dice analysis
- dimensional filtering
- DAX measures
- business reporting
- cohort analysis
- executive reporting
- interactive exploration

Avoid copying every React card and chart one-for-one.

The two deliverables should demonstrate complementary skills.
