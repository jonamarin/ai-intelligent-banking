"""SQLAlchemy declarative base and session management.

docs/domain-model.md § 3 defines the entities modeled under this package.
Everything here is a table/column definition — business logic (evidence
extraction, policy evaluation) belongs in src/evidence/ and src/policies/,
not in these model classes (.claude/rules/database.md, .claude/rules/backend.md).
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config.settings import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for every model in src/models/."""


def get_engine() -> Engine:
    """Create the SQLAlchemy engine from the current settings.

    Not memoized at import time — tests override DATABASE_URL per-test via
    environment variables / a dedicated test engine, so this must re-read
    settings each time it's called rather than binding an engine at import.
    """
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session.

    Not yet wired into any endpoint (docs/api-contracts.md § 1 domain endpoints
    are Phase 6-7) — provided now so Phase 2 model tests and later phases share
    one session-management convention instead of each reinventing it.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
