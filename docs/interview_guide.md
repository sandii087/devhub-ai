# Customer Churn & Retention Intelligence — interview guide

## 1. Explain your project.

I built a local end-to-end churn analytics platform for a fictional subscription business. Python generates reproducible synthetic customer data, then validates, cleans, engineers features, trains a churn baseline, and loads a scored customer snapshot into SQLite. FastAPI exposes computed analytics and React displays them in an interactive dashboard.

## 2. Why did you choose churn analysis?

Churn connects customer behavior, service quality, revenue, segmentation, SQL, and predictive analytics. It is a practical Data Analyst case because a business can use it to decide which customer groups to investigate or prioritize for retention—not because a prediction alone solves churn.

## 3. How did you clean the data?

I intentionally generated duplicate rows, missing satisfaction scores, invalid dates, impossible ages, invalid charges, inconsistent labels, and a few outliers. The cleaning module profiles those issues, removes duplicate customers, standardizes labels, replaces impossible values with valid medians or business-derived values, caps controlled outliers, and writes a before/after JSON report.

## 4. What SQL queries did you use?

I wrote 16 business queries: overall churn, plan/contract/region/segment churn, charges by status, high-exposure customers, tenure, payment, satisfaction, support, monthly trend, revenue exposure, ranking, and an above-average comparison. They demonstrate joins are not necessary for this one-table snapshot, but use `GROUP BY`, `HAVING`, `CASE`, CTEs, a subquery, aggregates, ordering, and a window function.

## 5. Why SQLite?

SQLite makes the portfolio project easy to run locally with no server or credentials. It still demonstrates a schema, indexes, parameterized queries, and SQL analysis. For a multi-user production workload I would use a managed relational database or warehouse.

## 6. What is churn rate?

In this project it is `number of customers with churn = Yes / total customers × 100`. It is an observed historical/snapshot outcome, which is different from the model's predicted future-like churn probability.

## 7. How did you calculate revenue at risk?

For each customer, I multiply current monthly charges by their model probability: `monthly_charges × risk_score`. Summing it gives probability-weighted expected monthly exposure. It is not a guarantee of lost revenue and I label it that way in the dashboard.

## 8. How did you segment customers?

I calculate lifetime-value proxy as monthly charges times tenure. Customers at or above its dataset median are High Value. I combine that with the model's High Risk band (>0.66) versus non-high-risk bands to create High Value/High Risk, High Value/Low Risk, Low Value/High Risk, and Low Value/Low Risk.

## 9. How did you avoid data leakage?

I define features separately from the target. Churn, churn reason, churn date, risk score, revenue at risk, and portfolio segment are excluded from training. I split data before fitting preprocessing or evaluating it, then only fit a separate final model on all clean records after reporting holdout metrics so the dashboard can score the current snapshot.

## 10. Why Logistic Regression?

It is a strong, transparent baseline for binary classification. It trains quickly, works with encoded categorical data, produces probabilities for the risk score, and is easier to explain than more complex models. It is not assumed to be the best production model.

## 11. Why use ROC-AUC?

ROC-AUC measures how well probabilities rank churners ahead of non-churners across thresholds. It gives a threshold-independent view that complements accuracy, precision, recall, and F1.

## 12. Why isn't accuracy enough?

When churn is less common, a model can predict mostly non-churn and still look accurate. That can hide a poor ability to identify customers who need attention. Precision and recall make that trade-off visible.

## 13. What does precision mean here?

Precision is the share of customers predicted as churners who actually churned in the holdout set. Higher precision means fewer wasted retention interventions among flagged customers.

## 14. What does recall mean here?

Recall is the share of actual churners the model successfully flags. Higher recall means fewer likely churners are missed, although it can also increase false positives.

## 15. How does the dashboard get its data?

React calls FastAPI endpoints. The API reads the locally built SQLite customer table or generated report/model JSON, runs reusable analytics functions, and returns calculated response objects. Charts and cards use those responses rather than hard-coded metrics.

## 16. Why FastAPI?

FastAPI provides type-friendly route definitions, validation for query parameters, automatic OpenAPI docs, clear error handling, and a simple bridge between Python analytics and the web UI.

## 17. Why React?

React makes it straightforward to make reusable cards, charts, tables, filters, and a customer detail panel. TypeScript helps catch frontend data-shape errors before build time.

## 18. What were the biggest challenges?

Designing the project so that the dashboard did not fake results was the key challenge. I handled it by building the data pipeline and API first, keeping calculations reusable, and making the frontend a consumer of API data. A second challenge was keeping risk scoring useful while avoiding target leakage.

## 19. What are the limitations?

The data is synthetic, so patterns and model metrics cannot be generalized to a company. The dataset is a snapshot without detailed event timelines or retention campaign outcomes. The model has not had time-based validation, calibration, monitoring, or fairness assessment.

## 20. What would you improve with more time?

I would ingest real consented data into a warehouse, add event-level behavior and time-aware cohorts, compare calibrated models using temporal validation, introduce role-based access and scheduled refreshes, track retention experiments, and add monitoring for data quality and model drift.
