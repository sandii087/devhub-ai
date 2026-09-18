from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DATA_PATH = DATA_DIR / "raw" / "customers_raw.csv"
CLEAN_DATA_PATH = DATA_DIR / "processed" / "customers_clean.csv"
DATABASE_PATH = ROOT / "database" / "churn_intelligence.db"
REPORTS_DIR = ROOT / "reports"
MODELS_DIR = ROOT / "models"
QUALITY_REPORT_PATH = REPORTS_DIR / "data_quality_report.json"
MODEL_METRICS_PATH = REPORTS_DIR / "model_metrics.json"
MODEL_PATH = MODELS_DIR / "churn_logistic_regression.joblib"
RANDOM_SEED = 20260917
