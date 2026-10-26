"""SQLite connection helper.

Keeps the schema portable: swap `sqlite:///...` for a Postgres DSN
and the rest of the code stays the same.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from src.utils.config import get_db_path


def get_engine(db_path: Path | None = None) -> Engine:
    """Return a SQLAlchemy engine for the SQLite database."""
    db_path = db_path or get_db_path(writable=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False, poolclass=NullPool)


@contextmanager
def get_connection(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Yield a raw sqlite3 connection (useful for executescript / PRAGMA)."""
    db_path = db_path or get_db_path(writable=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_trigger() -> str:
    """Return 'github_actions' if running in CI/GitHub Actions, else 'local'."""
    return os.getenv(
        "PIPELINE_TRIGGER", "github_actions" if os.getenv("GITHUB_ACTIONS") == "true" else "local"
    )


def init_db(db_path: Path | None = None) -> None:
    """Create the pipeline_runs audit table if it does not exist."""
    engine = get_engine(db_path)
    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at        TEXT    NOT NULL,           -- ISO-8601 UTC
                stage         TEXT    NOT NULL,           -- ingest|clean|model|viz
                source        TEXT,                       -- grid_india|mendeley|open_meteo|cea
                rows_fetched  INTEGER,
                rows_inserted INTEGER,
                rows_skipped  INTEGER,
                duration_s    REAL,
                status        TEXT    NOT NULL,           -- ok|error
                trigger       TEXT    NOT NULL DEFAULT 'local', -- local|github_actions
                message       TEXT
            )
        """)
        )
        # Check if trigger column exists in existing table
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(pipeline_runs)")).fetchall()]
        if "trigger" not in cols:
            conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN trigger TEXT NOT NULL DEFAULT 'local'"))
        conn.commit()
