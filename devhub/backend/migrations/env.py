from alembic import context
from sqlalchemy import create_engine, pool, text
from devhub.config import settings
from devhub.db import Base
from devhub import models, auth_models, github_models, ai  # noqa: F401

import os


migration_database_url = os.environ.get("MIGRATION_DATABASE_URL", settings.database_url)

if context.is_offline_mode():
    context.configure(
        url=migration_database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(
        migration_database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        ),
        poolclass=pool.NullPool,
    )

    with engine.begin() as connection:
        # Serialize concurrent container startups in the same migration transaction.
        connection.execute(text("SET LOCAL lock_timeout = '60s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(731904230118)"))
        context.configure(connection=connection, target_metadata=Base.metadata)

        with context.begin_transaction():
            context.run_migrations()
