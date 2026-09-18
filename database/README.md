# SQLite analytics

`schema.sql` defines the local, one-row-per-customer snapshot table and useful indexes. `business_questions.sql` contains 16 executable business queries covering aggregates, `CASE`, `HAVING`, CTEs, subqueries, and a window function.

Run `python -m src.run_pipeline` to build `churn_intelligence.db` from the processed, model-scored synthetic data. The database file is intentionally ignored by Git because it is reproducible.
