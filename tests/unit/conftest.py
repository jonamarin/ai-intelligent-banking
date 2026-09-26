"""Shared fixtures for model-constraint unit tests.

These use an in-memory SQLite engine, not the project's real PostgreSQL
target — fast and fully offline (.claude/rules/testing.md: tests must not
require external infrastructure). This is deliberately a different kind of
verification than the Alembic migration check in docs/project-status.md
(which was run directly against a live Postgres): SQLite proves the ORM
model constraints (nullable, unique, defaults, foreign keys) behave as
declared; it does not prove the actual migration applies to Postgres — that
was verified separately and manually, and must be re-verified the same way
if the models change again.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.models import Base


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
