"""Phase 1 (BRIEFING-TIMEBASED-002) — morning_pre 시간 기반 validation E2E.

test_briefings_on_demand.py 는 엔드포인트 contract 검증, 이 파일은 Phase 1
validation 규약 (09:00 분기 + M3.5 force 의미 재정의) 을 한 곳에 모은다.

SPEC Validation 요약표 기준:
  < 09:00        → 실시간 (force 무관)
  ≥ 09:00 + f=F  → 보관본 재전송 or 404
  ≥ 09:00 + f=T  → 분기 우회, 실시간 (복구 경로)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from core.briefing import upsert_parts
from core.contracts.briefing_part import BriefingPart
from pipelines._base import PipelineManifest, PipelineResult, StageResult

KST = ZoneInfo("Asia/Seoul")


def _sample_parts() -> list[BriefingPart]:
    return [
        BriefingPart(key="overnight", label="간밤시황", order=1, data={"v": 1}),
        BriefingPart(key="scenario", label="시나리오+뉴스", order=2, data={"v": 1}),
        BriefingPart(key="positions", label="포지션+신규", order=3, data={"v": 1}),
    ]


def _freeze_now_kst(
    monkeypatch: pytest.MonkeyPatch, *, hour: int, minute: int = 0
) -> None:
    from server.api import briefings_on_demand as mod

    monkeypatch.setattr(
        mod,
        "_now_kst",
        lambda: datetime(2026, 4, 24, hour, minute, 0, tzinfo=KST),
    )


def _insert_morning_snapshot(run_id: str, created_at_utc: str) -> None:
    """지정된 UTC 시각으로 보관본 하나 심는다."""
    from core.db import get_db

    upsert_parts("market_briefing_pre", run_id, _sample_parts())
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "UPDATE briefing_parts SET created_at=? WHERE run_id=?",
            (created_at_utc, run_id),
        )


def _install_fake_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    from pipelines._base import PipelineRunner

    async def fake_run(
        self: Any,
        manifest: PipelineManifest,
        *,
        input_data: dict | None = None,
        run_id: str | None = None,
    ) -> PipelineResult:
        assert run_id is not None
        upsert_parts(manifest.id, run_id, _sample_parts())
        result = PipelineResult(pipeline_id=manifest.id, run_id=run_id)
        result.stages["analyze"] = StageResult(
            stage_id="analyze",
            status="ok",
            data={"metadata": {"model": "gemini-2.5-pro"}},
        )
        return result

    monkeypatch.setattr(PipelineRunner, "run", fake_run)


@pytest.fixture(autouse=True)
def _reset_db_and_cache() -> None:
    from core.db import get_db
    from server.api import briefings_on_demand as mod

    db = get_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM briefing_parts")
    mod._run_cache.clear()
    mod._run_locks.clear()


@pytest.fixture
def client() -> TestClient:
    from server.main import app

    return TestClient(app)


# ----------------------------------------------------------------------------
# Case 1 — 09:00 이전: force 무관 실시간
# ----------------------------------------------------------------------------


def test_pre_9am_force_false_runs_realtime(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """08:30 + force=false (기본) → 실시간 새 run (09:00 분기 안 탐)."""
    _freeze_now_kst(monkeypatch, hour=8, minute=30)
    _install_fake_runner(monkeypatch)

    r = client.post("/api/briefings/market_briefing_pre/run")
    assert r.status_code == 200
    body = r.json()
    assert body["cache_hit"] is False
    assert body.get("note") is None
    assert "#manual-" in body["run_id"]


# ----------------------------------------------------------------------------
# Case 2 — 09:00 이후 + force=false + 보관본 있음
# ----------------------------------------------------------------------------


def test_post_9am_force_false_returns_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """10:00 + force=false + 당일 07:00 보관본 → note=before_market_open."""
    _freeze_now_kst(monkeypatch, hour=10)
    # 2026-04-24 07:00 KST = 2026-04-23 22:00 UTC (실제 현재 UTC 보다 과거)
    _insert_morning_snapshot("today_pre_run", "2026-04-23 22:00:00")

    r = client.post("/api/briefings/market_briefing_pre/run")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "today_pre_run"
    assert body["note"] == "before_market_open"
    assert body["cache_hit"] is True


# ----------------------------------------------------------------------------
# Case 3 — 09:00 이후 + force=false + 보관본 없음
# ----------------------------------------------------------------------------


def test_post_9am_force_false_no_snapshot_returns_404_with_hint(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """10:00 + force=false + 보관본 없음 → 404 + detail 에 force=true 안내."""
    _freeze_now_kst(monkeypatch, hour=10)

    r = client.post("/api/briefings/market_briefing_pre/run")
    assert r.status_code == 404
    assert "force=true" in r.json()["detail"]


# ----------------------------------------------------------------------------
# Case 4 — 09:00 이후 + force=true: 분기 우회
# ----------------------------------------------------------------------------


def test_post_9am_force_true_bypasses_branch_even_with_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """10:00 + force=true → 보관본 있어도 실시간 새 run."""
    _freeze_now_kst(monkeypatch, hour=10)
    _insert_morning_snapshot("today_pre_run", "2026-04-23 22:00:00")
    _install_fake_runner(monkeypatch)

    r = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] != "today_pre_run"
    assert body.get("note") is None
    assert body["cache_hit"] is False


# ----------------------------------------------------------------------------
# Case 5 — M3.5 핵심: cache 누수 방지
# ----------------------------------------------------------------------------


def test_force_true_post_9am_run_does_not_leak_to_force_false(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """force=true 로 방금 만든 post-9am run 이 60s cache 에 남아도
    force=false 다음 호출은 반드시 보관본 분기로 낙하해야 한다.

    분기를 cache 레이어 앞에 배치했기 때문에 여기서 보장된다.
    """
    _freeze_now_kst(monkeypatch, hour=10)
    _insert_morning_snapshot("today_pre_run", "2026-04-23 22:00:00")
    _install_fake_runner(monkeypatch)

    # 1) force=true 실시간 실행 — post-9am run 이 in-memory cache 에 박힘
    r1 = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r1.status_code == 200
    force_true_run_id = r1.json()["run_id"]
    assert force_true_run_id != "today_pre_run"

    # 2) 같은 시점 force=false — post-9am run 이 새면 안 된다
    r2 = client.post("/api/briefings/market_briefing_pre/run")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["run_id"] == "today_pre_run", (
        f"force=false 가 post-9am run 을 반환하면 안 됨. 실제: {body2['run_id']}"
    )
    assert body2["note"] == "before_market_open"
