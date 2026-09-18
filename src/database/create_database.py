"""Create and validate the reproducible SQLite analytics database."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.config import CLEAN_DATA_PATH, DATABASE_PATH, ROOT


SCHEMA_PATH = ROOT / "database" / "schema.sql"
QUERIES_PATH = ROOT / "database" / "business_questions.sql"


def build_database(dataframe: pd.DataFrame | None = None) -> Path:
    """Load the scored customer snapshot into a fresh SQLite database."""
    df = dataframe.copy() if dataframe is not None else pd.read_csv(CLEAN_DATA_PATH)
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        columns = list(df.columns)
        placeholders = ", ".join("?" for _ in columns)
        statement = f"INSERT INTO customers ({', '.join(columns)}) VALUES ({placeholders})"
        values = [tuple(None if pd.isna(value) else value.item() if hasattr(value, "item") else value for value in row) for row in df.itertuples(index=False, name=None)]
        connection.executemany(statement, values)
        connection.commit()
    return DATABASE_PATH


def validate_business_queries() -> int:
    """Execute every documented analysis query to detect SQL drift."""
    script = QUERIES_PATH.read_text(encoding="utf-8")
    statements = [part.strip() for part in script.split(";") if "SELECT" in part.upper()]
    with sqlite3.connect(DATABASE_PATH) as connection:
        for statement in statements:
            connection.execute(statement).fetchall()
    return len(statements)


if __name__ == "__main__":
    path = build_database()
    print(f"Built {path}; validated {validate_business_queries()} business queries")
