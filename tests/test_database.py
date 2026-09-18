import sqlite3

from src.config import DATABASE_PATH
from src.database.create_database import validate_business_queries


def test_database_has_clean_customer_grain():
    with sqlite3.connect(DATABASE_PATH) as connection:
        count = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        duplicate_ids = connection.execute("SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM customers").fetchone()[0]
    assert count >= 5_000
    assert duplicate_ids == 0


def test_documented_business_queries_execute():
    assert validate_business_queries() == 16
