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


def _table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


# v21 recreate 용 DDL — schema.sql 의 market_view_snapshot 정의와 **반드시 동일**하게 유지.
_MARKET_VIEW_V21_DDL = """
CREATE TABLE IF NOT EXISTS market_view_snapshot (
    date            TEXT NOT NULL,
    market          TEXT NOT NULL,
    regime          TEXT,
    leading_json    TEXT,
    fading_json     TEXT,
    rotation_json   TEXT,
    entry_posture   TEXT,
    one_liner       TEXT,
    confidence      INTEGER,
    reasons_json    TEXT,
    source          TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    session         TEXT NOT NULL DEFAULT 'postclose',
    narrative       TEXT,
    rotation_read   TEXT,
    risk_read       TEXT,
    stance          TEXT,
    facts_json      TEXT,
    PRIMARY KEY (date, market, session)
);
CREATE INDEX IF NOT EXISTS idx_market_view_date ON market_view_snapshot(date);
"""


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

        # v17 — universe_membership list_type (PK 확장: 거래대금/거래량양봉 두 리스트).
        #   이번 세션 신규 테이블이라 list_type 컬럼 없으면 DROP → schema.sql 이 새 PK 로 재생성(데이터 무해).
        #   list_type 있으면 skip(멱등). SQLite 는 PK ALTER 미지원이라 recreate.
        try:
            if not _column_exists(conn, "universe_membership", "list_type"):
                conn.execute("DROP TABLE IF EXISTS universe_membership")
        except Exception:  # noqa: BLE001
            pass

        # v18 — universe_membership.concept (차트 컨셉 분류: 주도주/눌림/바닥). 멱등 ALTER(PK 불변).
        try:
            if not _column_exists(conn, "universe_membership", "concept"):
                conn.execute("ALTER TABLE universe_membership ADD COLUMN concept TEXT")
        except Exception:  # noqa: BLE001 — 새 DB 는 schema.sql 가 처리
            pass

        # v19 — universe_membership.volume (거래량 상위 리스트 거래량 표기). 멱등 ALTER.
        try:
            if not _column_exists(conn, "universe_membership", "volume"):
                conn.execute("ALTER TABLE universe_membership ADD COLUMN volume INTEGER")
        except Exception:  # noqa: BLE001
            pass

        # v22 — stock_supply_history 숏 압력·프로그램 확장 (ADVISOR-CORE-001 M1-b).
        #   공매도/융자·대주 잔고/프로그램매매 = 같은 "종목×일자 수급 지표" 도메인 → 컬럼 확장.
        #   nullable 유지 = 미수집과 0 을 구분(숏 잔고 0 은 실제 정보).
        _v22_columns = (
            ("stock_supply_history", "short_volume", "INTEGER"),
            ("stock_supply_history", "short_ratio", "REAL"),
            ("stock_supply_history", "short_cum_ratio", "REAL"),
            ("stock_supply_history", "loan_balance_qty", "INTEGER"),
            ("stock_supply_history", "short_balance_qty", "INTEGER"),
            ("stock_supply_history", "program_net_qty", "INTEGER"),
            ("stock_supply_history", "program_net_amount", "INTEGER"),
        )
        for table, col, ddl in _v22_columns:
            try:
                if not _column_exists(conn, table, col):
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            except Exception:  # noqa: BLE001 — 새 DB 는 schema.sql 가 처리
                pass

        # v21 — market_view_snapshot 판세 확장 (ADVISOR-CORE-001 M1-a).
        #   하루 2회(장마감 18:00 / 아침 07:05) 발행이라 PK 에 session 이 필요하다.
        #   SQLite 는 PK ALTER 미지원 → 신규 테이블 생성 후 데이터 이관(기존 행 = postclose).
        #   컬럼만 있고 PK 가 옛것이면 여전히 recreate 대상이므로 PK 자체를 확인한다.
        try:
            if _table_exists(conn, "market_view_snapshot"):
                pk = [r["name"] for r in conn.execute(
                    "PRAGMA table_info(market_view_snapshot)"
                ).fetchall() if r["pk"]]
                if "session" not in pk:
                    conn.execute("ALTER TABLE market_view_snapshot RENAME TO _mvs_v20")
                    conn.executescript(_MARKET_VIEW_V21_DDL)
                    old_cols = [r["name"] for r in conn.execute(
                        "PRAGMA table_info(_mvs_v20)"
                    ).fetchall()]
                    carry = [c for c in (
                        "date", "market", "regime", "leading_json", "fading_json",
                        "rotation_json", "entry_posture", "one_liner", "confidence",
                        "reasons_json", "source", "created_at",
                    ) if c in old_cols]
                    cols = ", ".join(carry)
                    conn.execute(
                        f"INSERT INTO market_view_snapshot ({cols}, session) "
                        f"SELECT {cols}, 'postclose' FROM _mvs_v20"
                    )
                    conn.execute("DROP TABLE _mvs_v20")
        except Exception:  # noqa: BLE001 — 새 DB 는 schema.sql 가 처리
            pass

        # v20 — news_digest_snapshot.elevated_events_json (NEWS-EVENT-INTERPRETATION-001).
        #   격상 이벤트 + LLM 해석 내장 (D2: 컬럼 확장, 신규 테이블 0). 멱등 ALTER.
        try:
            if not _column_exists(conn, "news_digest_snapshot", "elevated_events_json"):
                conn.execute(
                    "ALTER TABLE news_digest_snapshot ADD COLUMN elevated_events_json TEXT"
                )
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
