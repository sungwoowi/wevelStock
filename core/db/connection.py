"""SQLite connection helper.

Provides a thin wrapper that:
- Creates the DB file and runs schema.sql on first use.
- Enables WAL mode and foreign keys.
- Yields a dict-row cursor context manager.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    """Lightweight SQLite facade (sync — okay for our IO volume)."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create tables if the DB doesn't exist yet."""
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema_sql)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple | dict | None = None) -> sqlite3.Cursor:
        with self.connect() as conn:
            return conn.execute(sql, params or ())

    def executemany(self, sql: str, seq: list[tuple] | list[dict]) -> sqlite3.Cursor:
        with self.connect() as conn:
            return conn.executemany(sql, seq)

    def fetch_all(self, sql: str, params: tuple | dict | None = None) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cur = conn.execute(sql, params or ())
            return cur.fetchall()

    def fetch_one(self, sql: str, params: tuple | dict | None = None) -> sqlite3.Row | None:
        with self.connect() as conn:
            cur = conn.execute(sql, params or ())
            return cur.fetchone()


_instance: Database | None = None


def get_db(db_path: str | Path | None = None) -> Database:
    """Process-wide singleton. Call with path on first access."""
    global _instance
    if _instance is None:
        if db_path is None:
            from core.config import get_config

            db_path = get_config().database.path
        _instance = Database(db_path)
    return _instance


def reset_db() -> None:
    """Force re-initialization (used in tests)."""
    global _instance
    _instance = None
