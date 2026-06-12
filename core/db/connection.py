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
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _column_exists(conn, table: str, column: str) -> bool:
    """PRAGMA table_info 로 컬럼 존재 확인."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


class Database:
    """Lightweight SQLite facade (sync — okay for our IO volume)."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Apply schema.sql (new DB) + migrations/*.sql (existing DB upgrades)."""
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connect() as conn:
            # 기존 DB 에 schema.sql 의 신규 INDEX (예: idx_llm_call_cache_type) 가
            # 컬럼 부재로 실패하지 않도록 마이그레이션 먼저 적용 (멱등 — 가드 안에서).
            self._apply_migrations(conn)
            conn.executescript(schema_sql)

    @staticmethod
    def _apply_migrations(conn) -> None:
        """migrations/v*.sql 을 멱등하게 적용. 'duplicate column' 등 안전 흡수.

        SQLite 는 ALTER TABLE IF NOT EXISTS COLUMN 미지원 → 컬럼 존재 시 ALTER skip.
        새 DB 는 schema.sql 의 CREATE 정의가 처리하므로 마이그레이션이 추가로 적용돼도
        ON CONFLICT IGNORE / IF NOT EXISTS 가드로 안전.
        """
        # v8 — WAVE-ALPHA-001 = llm_call_cache.type + manual_anchors
        try:
            if not _column_exists(conn, "llm_call_cache", "type"):
                conn.execute(
                    "ALTER TABLE llm_call_cache ADD COLUMN type TEXT NOT NULL DEFAULT 'general'"
                )
        except Exception:  # noqa: BLE001 — 새 DB 등 컬럼 정의 안 된 경우 schema.sql 가 처리
            pass

        # v9 — macro DB 캐시 충실도 (2026-06-02): distribution_count_25d + breadth_source 영속.
        #   이전엔 _get_today_macro 복원 시 dist=0/source=None 하드코드 → computed run 과 불일치
        #   (regime 분류에 dist 영향). 두 컬럼을 round-trip 하도록 ALTER (멱등).
        for col, ddl in (
            ("distribution_count_25d", "INTEGER"),
            ("breadth_source", "TEXT"),
        ):
            try:
                if not _column_exists(conn, "market_macro_snapshot", col):
                    conn.execute(
                        f"ALTER TABLE market_macro_snapshot ADD COLUMN {col} {ddl}"
                    )
            except Exception:  # noqa: BLE001 — 새 DB 는 schema.sql 가 처리
                pass

        # v10 (market_view) / v11 (news_source_items + news_digest_snapshot) 는 신규 *테이블* 추가라
        # 별도 ALTER 불필요 — schema.sql 의 CREATE TABLE IF NOT EXISTS 가 새 DB·기존 DB 모두 처리.
        # v12 (us_macro_snapshot) / v13~v15 (account/paper/wealth) 도 신규 테이블 — schema.sql 처리.

        # v16 — INFRA-MARKET-ASSETS-002: 야간자산 컬럼 확장 + 알림 영속 (멱등 ALTER, v9 패턴).
        #   us_macro_snapshot: WTI·브렌트·NQ·ES 야간선물 change_pct (gold 와 동일 야간 카테고리).
        #   market_macro_snapshot: KOSPI200 야간선물 change_pct (KIS best-effort, graceful null).
        #   notifications_log: notification_type(분류) + is_read(미독 배지) — PAPER-DESK-UX 알림 탭.
        _v16_columns = (
            ("us_macro_snapshot", "wti_change_pct", "REAL"),
            ("us_macro_snapshot", "brent_change_pct", "REAL"),
            ("us_macro_snapshot", "nq_futures_change_pct", "REAL"),
            ("us_macro_snapshot", "es_futures_change_pct", "REAL"),
            ("market_macro_snapshot", "kospi200_night_change_pct", "REAL"),
            ("notifications_log", "notification_type", "TEXT"),
            ("notifications_log", "is_read", "INTEGER NOT NULL DEFAULT 0"),
        )
        for table, col, ddl in _v16_columns:
            try:
                if not _column_exists(conn, table, col):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            except Exception:  # noqa: BLE001 — 새 DB 는 schema.sql 가 처리
                pass

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
