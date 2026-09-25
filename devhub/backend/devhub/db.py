"""Database sessions and transaction-scoped tenant context."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from devhub.config import settings


class Base(DeclarativeBase):
    pass


database_url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(database_url, pool_pre_ping=True, pool_size=10, max_overflow=10, pool_timeout=10)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def set_tenant(session: Session, org_id: str) -> None:
    """Call only after the caller's organization membership is checked."""
    session.execute(text("SELECT set_config('devhub.org_id', :org_id, true)"), {"org_id": org_id})
