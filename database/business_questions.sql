-- Q01: Overall churn and retention rate
SELECT COUNT(*) AS customers, SUM(churn = 'Yes') AS churned_customers,
       ROUND(100.0 * SUM(churn = 'Yes') / COUNT(*), 2) AS churn_rate_pct,
       ROUND(100.0 * SUM(churn = 'No') / COUNT(*), 2) AS retention_rate_pct
FROM customers;

-- Q02: Churn by subscription plan
SELECT subscription_plan, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
FROM customers GROUP BY subscription_plan ORDER BY churn_rate_pct DESC;

-- Q03: Churn by contract type
SELECT contract_type, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
FROM customers GROUP BY contract_type ORDER BY churn_rate_pct DESC;

-- Q04: Churn and expected revenue exposure by region
SELECT region, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct,
       ROUND(SUM(revenue_at_risk), 2) AS expected_mrr_at_risk
FROM customers GROUP BY region ORDER BY churn_rate_pct DESC;

-- Q05: Churn by original customer segment
SELECT customer_segment, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
FROM customers GROUP BY customer_segment ORDER BY churn_rate_pct DESC;

-- Q06: Average charges by churn status
SELECT churn, ROUND(AVG(monthly_charges), 2) AS average_monthly_charges,
       ROUND(AVG(total_charges), 2) AS average_lifetime_charges
FROM customers GROUP BY churn;

-- Q07: Customers with the highest expected MRR exposure
SELECT customer_id, subscription_plan, region, monthly_charges, risk_score, revenue_at_risk
FROM customers ORDER BY revenue_at_risk DESC LIMIT 20;

-- Q08: High-value customers whose predicted risk is high
SELECT customer_id, customer_segment, subscription_plan, tenure_months, monthly_charges, risk_score, revenue_at_risk
FROM customers WHERE portfolio_segment = 'High Value / High Risk'
ORDER BY revenue_at_risk DESC;

-- Q09: Churn by tenure bucket with a HAVING threshold
SELECT tenure_bucket, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
FROM customers GROUP BY tenure_bucket HAVING COUNT(*) >= 25 ORDER BY churn_rate_pct DESC;

-- Q10: Churn by payment method
SELECT payment_method, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
FROM customers GROUP BY payment_method ORDER BY churn_rate_pct DESC;

-- Q11: Satisfaction bands and churn
SELECT CASE WHEN satisfaction_score < 3 THEN 'Below 3' WHEN satisfaction_score < 4 THEN '3 to <4' ELSE '4+' END AS satisfaction_band,
       COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
FROM customers GROUP BY satisfaction_band ORDER BY churn_rate_pct DESC;

-- Q12: Support intensity and churn
SELECT support_intensity, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct,
       ROUND(AVG(satisfaction_score), 2) AS average_satisfaction
FROM customers GROUP BY support_intensity ORDER BY churn_rate_pct DESC;

-- Q13: Monthly churn trend using a CTE
WITH monthly_churn AS (
  SELECT substr(churn_date, 1, 7) AS churn_month, COUNT(*) AS churned_customers
  FROM customers WHERE churn = 'Yes' AND churn_date <> '' GROUP BY substr(churn_date, 1, 7)
)
SELECT churn_month, churned_customers, ROUND(100.0 * churned_customers / (SELECT COUNT(*) FROM customers), 2) AS share_of_customer_base_pct
FROM monthly_churn ORDER BY churn_month;

-- Q14: Revenue exposure by region and plan
SELECT region, subscription_plan, ROUND(SUM(revenue_at_risk), 2) AS expected_mrr_at_risk,
       ROUND(AVG(risk_score), 3) AS average_risk_score
FROM customers GROUP BY region, subscription_plan ORDER BY expected_mrr_at_risk DESC;

-- Q15: Rank segments by churn using a window function
WITH segment_rates AS (
  SELECT customer_segment, COUNT(*) AS customers, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
  FROM customers GROUP BY customer_segment
)
SELECT customer_segment, customers, churn_rate_pct,
       RANK() OVER (ORDER BY churn_rate_pct DESC) AS churn_rank
FROM segment_rates ORDER BY churn_rank;

-- Q16: Plans whose churn rate is above the overall rate (subquery)
SELECT subscription_plan, ROUND(100.0 * AVG(churn = 'Yes'), 2) AS churn_rate_pct
FROM customers GROUP BY subscription_plan
HAVING AVG(churn = 'Yes') > (SELECT AVG(churn = 'Yes') FROM customers)
ORDER BY churn_rate_pct DESC;
