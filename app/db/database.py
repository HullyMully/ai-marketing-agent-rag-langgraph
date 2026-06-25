"""SQLAlchemy engine & session management."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# `check_same_thread` is required for SQLite when used by FastAPI workers.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables. Safe to call multiple times (idempotent)."""
    from app.db import models  # noqa: F401  (ensures models are registered)

    models.Base.metadata.create_all(bind=engine)
    _ensure_runtime_columns()


def _ensure_runtime_columns() -> None:
    """Small SQLite compatibility shim for demo DBs created before new columns.

    Production deployments should use real migrations; this keeps local
    workspaces from breaking when the prototype schema grows.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(tickets)").fetchall()
        existing = {row[1] for row in rows}
        if rows and "assignee" not in existing:
            conn.exec_driver_sql("ALTER TABLE tickets ADD COLUMN assignee VARCHAR(120)")
        if rows and "updated_at" not in existing:
            conn.exec_driver_sql("ALTER TABLE tickets ADD COLUMN updated_at DATETIME")


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for use outside of FastAPI (scripts, tools, bot)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
