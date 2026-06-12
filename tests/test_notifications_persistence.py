"""INFRA-MARKET-ASSETS-002 (notification-persistence-v1) — 알림 영속 + read/mark-read.

1. _infer_notification_type 휴리스틱 (순수)
2. _log_to_db 가 notification_type·is_read=0 기록
3. GET /recent 가 두 컬럼 + unread_count 노출
4. POST /mark-read (ids / all) 멱등 갱신

외부 API 실호출 금지 — DB 직접 seed.
"""
from __future__ import annotations

import pytest

import core.notification.service as svc
from core.db.connection import Database, reset_db
from server.api import notifications as notif_api
from server.api.notifications import MarkReadRequest


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_notifications.sqlite")
    for mod in (svc, notif_api):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# _infer_notification_type — 순수 휴리스틱
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "team_id,explicit,expected",
    [
        ("market_briefing_now", None, "market_briefing"),
        ("market_briefing_pre", None, "market_briefing"),
        ("anything", "risk_alert", "risk_alert"),       # explicit 우선
        ("risk_monitor", None, "risk_alert"),
        ("account_manager", None, "account_safety"),
        ("flow_idea_feed", None, "flow_idea"),
        ("trade_signal_x", None, "trade_signal"),
        ("track_b", None, None),                          # 매칭 실패 → None
    ],
)
def test_infer_notification_type(team_id, explicit, expected):
    assert svc._infer_notification_type(team_id, explicit) == expected


# ---------------------------------------------------------------------------
# _log_to_db — notification_type·is_read 기록
# ---------------------------------------------------------------------------


def test_log_to_db_records_type_and_unread(isolated_db):
    svc._log_to_db(
        team_id="market_briefing_now",
        level="info",
        title="장중 브리핑",
        body="코스피 강세",
        channel="file",
        delivered=True,
        related_run_id=None,
        related_target=None,
        notification_type="market_briefing",
    )
    row = isolated_db.fetch_one("SELECT * FROM notifications_log")
    assert row["notification_type"] == "market_briefing"
    assert row["is_read"] == 0


# ---------------------------------------------------------------------------
# API — recent + mark-read
# ---------------------------------------------------------------------------


def _seed(db: Database, n: int = 3) -> None:
    for i in range(n):
        svc._log_to_db(
            team_id="market_briefing_now",
            level="info",
            title=f"브리핑 {i}",
            body="본문",
            channel="file",
            delivered=True,
            related_run_id=None,
            related_target=None,
            notification_type="market_briefing",
        )


@pytest.mark.asyncio
async def test_recent_exposes_type_and_unread_count(isolated_db):
    _seed(isolated_db, 3)
    out = await notif_api.recent_notifications(limit=10)
    assert out["unread_count"] == 3
    assert len(out["notifications"]) == 3
    assert out["notifications"][0]["notification_type"] == "market_briefing"
    assert out["notifications"][0]["is_read"] == 0


@pytest.mark.asyncio
async def test_mark_read_by_ids(isolated_db):
    _seed(isolated_db, 3)
    ids = [r["id"] for r in isolated_db.fetch_all("SELECT id FROM notifications_log")]
    out = await notif_api.mark_notifications_read(MarkReadRequest(ids=ids[:2]))
    assert out["updated"] == 2
    assert out["unread_count"] == 1


@pytest.mark.asyncio
async def test_mark_read_all_idempotent(isolated_db):
    _seed(isolated_db, 3)
    out1 = await notif_api.mark_notifications_read(MarkReadRequest(all=True))
    assert out1["updated"] == 3
    assert out1["unread_count"] == 0
    # 재호출 멱등 — 더 갱신할 미독 없음
    out2 = await notif_api.mark_notifications_read(MarkReadRequest(all=True))
    assert out2["updated"] == 0
    assert out2["unread_count"] == 0
