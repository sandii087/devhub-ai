"""Train and evaluate an interpretable logistic-regression churn model."""
from __future__ import annotations

import json
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import CLEAN_DATA_PATH, MODEL_METRICS_PATH, MODEL_PATH, RANDOM_SEED


NUMERIC_FEATURES = ["age", "tenure_months", "monthly_charges", "support_tickets", "last_login_days", "services_count", "discount_pct", "satisfaction_score", "monthly_usage"]
CATEGORICAL_FEATURES = ["gender", "region", "customer_segment", "subscription_plan", "contract_type", "payment_method", "internet_service", "acquisition_channel"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def _pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), NUMERIC_FEATURES),
            ("categorical", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("preprocessor", preprocessor), ("model", LogisticRegression(max_iter=1_500, class_weight="balanced", random_state=RANDOM_SEED))])


def attach_risk_scores(df: pd.DataFrame, model: Pipeline) -> pd.DataFrame:
    """Attach actual model probabilities; risk dollars are expected MRR exposure."""
    scored = df.copy()
    scored["risk_score"] = model.predict_proba(scored[FEATURES])[:, 1].round(6)
    scored["risk_segment"] = pd.cut(scored["risk_score"], bins=[-0.001, .33, .66, 1], labels=["Low Risk", "Medium Risk", "High Risk"]).astype(str)
    scored["revenue_at_risk"] = (scored["monthly_charges"] * scored["risk_score"]).round(2)
    scored["portfolio_segment"] = scored["customer_value_segment"] + " / " + scored["risk_segment"].replace({"Medium Risk": "Low Risk"})
    return scored


def train_and_score() -> tuple[pd.DataFrame, dict[str, Any]]:
    dataframe = pd.read_csv(CLEAN_DATA_PATH)
    target = dataframe["churn"].map({"Yes": 1, "No": 0})
    x_train, x_test, y_train, y_test = train_test_split(dataframe[FEATURES], target, test_size=.25, stratify=target, random_state=RANDOM_SEED)
    evaluation_model = _pipeline()
    evaluation_model.fit(x_train, y_train)
    predictions = evaluation_model.predict(x_test)
    probabilities = evaluation_model.predict_proba(x_test)[:, 1]
    matrix = confusion_matrix(y_test, predictions).tolist()
    metrics: dict[str, Any] = {
        "model": "Logistic Regression (class-balanced)",
        "target": "churn == Yes",
        "features": FEATURES,
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "test_split": "75% train / 25% stratified holdout",
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, predictions, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
        "confusion_matrix": matrix,
        "classification_report": classification_report(y_test, predictions, output_dict=True, zero_division=0),
        "methodology": "Numeric values are median-imputed and standardized; categorical values are mode-imputed and one-hot encoded. Churn label, churn reason, churn date, and post-model risk fields are excluded from model features.",
        "limitations": [
            "The records are synthetic and relationships were simulated, so model performance does not establish real-world predictive power.",
            "Scores are likelihood estimates from this snapshot, not retention decisions or causal explanations.",
            "A production model would need time-based validation, monitoring, fairness testing, calibration, and fresh behavioral data.",
        ],
    }
    final_model = _pipeline()
    final_model.fit(dataframe[FEATURES], target)
    scored = attach_risk_scores(dataframe, final_model)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, MODEL_PATH)
    MODEL_METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    scored.to_csv(CLEAN_DATA_PATH, index=False)
    return scored, metrics


if __name__ == "__main__":
    _, model_metrics = train_and_score()
    print(f"Trained {model_metrics['model']}; ROC-AUC: {model_metrics['roc_auc']:.4f}")
