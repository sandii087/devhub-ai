# Power BI Portfolio & Interview Preparation

## 5 resume bullets

Use these only after the Power BI report has actually been recreated and validated in Power BI Desktop.

1. Built an interview-ready Power BI customer-retention report using a Python-generated synthetic subscription dataset, translating customer, churn, risk and revenue-exposure outputs into interactive business intelligence dashboards.

2. Designed a practical star-schema semantic model with a customer snapshot fact table plus customer, plan, region, contract and date dimensions, using one-to-many relationships and controlled filter directions.

3. Developed reusable DAX measures for customer counts, churn/retention rates, monthly revenue, revenue at risk, customer value and model-risk segments instead of hardcoding dashboard KPIs.

4. Used Power Query to import, type, validate and model the Python-produced analytical dataset while deliberately avoiding duplicate business logic already implemented in the upstream data pipeline.

5. Created interactive Power BI reporting with slicers, cohort/retention analysis, risk-and-revenue views, tooltips and customer-level drill-through, complementing the project's React/FastAPI application with a dedicated BI layer.

---

# 10 interview questions and answers

## 1. Why did you add Power BI when the project already has a React dashboard?

**Answer:**  
The two interfaces demonstrate different skills. React/FastAPI demonstrates full-stack application development and API integration. Power BI demonstrates business intelligence skills such as Power Query, semantic modeling, DAX, interactive filtering, drill-through and executive reporting. I intentionally avoided making Power BI a direct copy of the React dashboard.

## 2. What is the grain of your fact table?

**Answer:**  
The fact table is one row per customer for the analytical snapshot. It is not a transaction table and does not represent every customer-month. That distinction is important when interpreting cohort and trend analysis.

## 3. Why did you use a star schema?

**Answer:**  
I separated descriptive dimensions such as customer, plan, region, contract and date from the customer snapshot fact. This gives cleaner filter propagation and makes reusable DAX measures easier to reason about without creating unnecessary model complexity.

## 4. Why use DAX measures instead of calculated columns for KPIs?

**Answer:**  
Measures respond dynamically to filter context. For example, the same Churn Rate measure can calculate overall churn, churn by plan, churn by region or churn for a selected slicer context. Hardcoded columns or separate measures for every category would be less reusable.

## 5. How did you calculate churn rate?

**Answer:**  
I calculate it as churned customers divided by total customers using DAX's `DIVIDE` function. The measure responds to the current report filter context.

## 6. What does Revenue at Risk mean in this project?

**Answer:**  
It is expected monthly revenue exposure derived upstream from monthly charges multiplied by the model's churn-risk probability. It is not realized revenue loss and should not be presented as actual lost revenue.

## 7. Did you recreate your Python data-cleaning logic in Power Query?

**Answer:**  
No. The Python pipeline is the upstream data-quality and feature-engineering layer. Power Query mainly handles BI import, data types, null/date handling and semantic-model preparation. This avoids maintaining two competing definitions of the same business logic.

## 8. How did you handle signup date versus churn date?

**Answer:**  
I use the date dimension with signup date as the active relationship. Churn date can use an inactive relationship and `USERELATIONSHIP` in a dedicated measure. This avoids having two active relationships from one date dimension to the same fact table.

## 9. What is a limitation of the cohort page?

**Answer:**  
The current dataset is a customer snapshot rather than complete monthly historical activity. Therefore the report should not claim to contain true transaction-level longitudinal history. A future monthly-snapshot or event fact table would make cohort and retention analysis more robust.

## 10. What would you improve for production?

**Answer:**  
I would introduce fresh behavioral/event data, time-based model validation, model calibration, monitoring, fairness testing, automated refresh, stronger data-quality checks and a longitudinal fact model. I would also monitor drift and validate whether risk scores remain useful on future customer populations.
