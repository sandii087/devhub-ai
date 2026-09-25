"""Run with the migration credential after migrations; never inside API startup.

Creates narrow runtime roles in this application's dedicated PostgreSQL database.
Passwords are required environment inputs and are never printed.
"""

import os
import psycopg
from psycopg import sql

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
with psycopg.connect(url, autocommit=True) as db:
    for role, password_var in (("devhub_app", "DB_APP_PASSWORD"), ("devhub_worker", "DB_WORKER_PASSWORD")):
        password = os.environ[password_var]
        if len(password) < 12:
            raise SystemExit(f"{password_var} must contain at least 12 characters")
        if not db.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
            db.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE").format(
                    sql.Identifier(role)
                )
            )
        db.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
        db.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
    db.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO devhub_app")
    db.execute("REVOKE UPDATE, DELETE ON audit_events FROM devhub_app")
    db.execute("REVOKE ALL ON alembic_version FROM devhub_app")
    db.execute("GRANT SELECT ON alembic_version TO devhub_app")
    db.execute("GRANT SELECT ON organizations, github_installations TO devhub_worker")
    db.execute("GRANT SELECT, UPDATE ON github_repositories TO devhub_worker")
    db.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON outbox_events TO devhub_worker")
    db.execute("GRANT SELECT, DELETE ON github_deliveries TO devhub_worker")
print("Runtime role privileges applied")
