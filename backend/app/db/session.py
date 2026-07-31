"""Engine and session factory (SQLite by default)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings

_settings = get_settings()
_connect_args = (
    # timeout: SQLite-Busy-Timeout in Sekunden. Der sqlite3-Default (5 s) ist
    # kürzer als lange Hintergrund-Schreibläufe (A2/A3, Markt-Vergleich) und
    # liess parallele Requests mit «database is locked» (HTTP 500) scheitern.
    {"check_same_thread": False, "timeout": 30}
    if _settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    _settings.database_url, connect_args=_connect_args, future=True
)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, class_=Session
)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
