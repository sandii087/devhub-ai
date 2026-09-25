from alembic import context
from sqlalchemy import create_engine, pool
from devhub.config import settings
from devhub.db import Base
from devhub import models, auth_models, github_models, ai  # noqa: F401

if context.is_offline_mode():
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(
        settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1), poolclass=pool.NullPool
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
