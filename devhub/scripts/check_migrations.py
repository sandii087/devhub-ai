"""Fail CI if ORM metadata and the migrated PostgreSQL schema disagree."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from devhub.db import Base, engine
from devhub import models, auth_models, github_models, ai  # noqa: F401

with engine.connect() as connection:
    differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
if differences:
    raise SystemExit(f"Schema drift detected: {differences}")
print("Migrated schema matches application metadata")
