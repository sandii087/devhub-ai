"""Run every reproducible local data stage in dependency order."""
from src.data.clean import run_cleaning
from src.data.features import run_feature_engineering
from src.data.generate import write_raw_data
from src.database.create_database import build_database, validate_business_queries
from src.ml.train import train_and_score


def run() -> None:
    raw = write_raw_data()
    cleaned, report = run_cleaning()
    featured = run_feature_engineering()
    scored, metrics = train_and_score()
    build_database(scored)
    query_count = validate_business_queries()
    print(
        f"Pipeline complete: {len(raw):,} raw rows -> {len(cleaned):,} clean rows -> "
        f"{len(featured.columns)} engineered columns. Model ROC-AUC={metrics['roc_auc']:.4f}. "
        f"Validated {query_count} SQL queries."
    )


if __name__ == "__main__":
    run()
