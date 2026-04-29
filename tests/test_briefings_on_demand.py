"""server/api/briefings_on_demand.py — 4 endpoints + 60s TTL cache + degraded."""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.briefing import upsert_parts
from core.contracts.briefing_part import BriefingPart
from pipelines._base import PipelineManifest, PipelineResult, StageResult


def _sample_parts() -> list[BriefingPart]:
    return [
        BriefingPart(
            key="overnight",
            label="간밤시황",
            order=1,
            data={
                "overnight_us": {
                    "nasdaq": {"price": 20000.0, "change_pct": 1.2}
                },
                "macro": {},
                "night_futures": {},
            },
        ),
        BriefingPart(
            key="scenario",
            label="시나리오+뉴스",
            order=2,
            data={
                "scenario": {"bias": "long", "confidence": 70, "narrative": "ok"},
                "news_items": [],
                "news_impact": [],
            },
        ),
        BriefingPart(
            key="positions",
            label="포지션+신규",
            order=3,
            data={
                "positions_advice": [],
                "new_candidates": [],
                "principles": {},
            },
        ),
    ]


@pytest.fixture(autouse=True)
def _reset_cache_and_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """각 테스트마다 briefing_parts 초기화 + in-memory 캐시 초기화.

    기본 KST 시각 08:00 고정 — morning_pre 09:00 보관본 분기 회피. 분기 검증
    테스트는 각자 `_now_kst` 를 재monkeypatch.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from core.db import get_db
    from server.api import briefings_on_demand as mod

    db = get_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM briefing_parts")
    mod._run_cache.clear()
    mod._run_locks.clear()
    monkeypatch.setattr(
        mod,
        "_now_kst",
        lambda: datetime(2026, 4, 24, 8, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )


@pytest.fixture
def client() -> TestClient:
    from server.main import app

    return TestClient(app)


# ----------------------------------------------------------------------------
# /latest
# ----------------------------------------------------------------------------

def test_latest_404_when_empty(client: TestClient) -> None:
    r = client.get("/api/briefings/market_briefing_pre/latest")
    assert r.status_code == 404


def test_latest_returns_parts(client: TestClient) -> None:
    upsert_parts("market_briefing_pre", "run_1", _sample_parts())
    r = client.get("/api/briefings/market_briefing_pre/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline_id"] == "market_briefing_pre"
    assert body["run_id"] == "run_1"
    assert body["status"] == "ok"
    assert body["cache_hit"] is False
    assert len(body["parts"]) == 3
    assert [p["key"] for p in body["parts"]] == ["overnight", "scenario", "positions"]
    assert body["parts"][0]["data"]["overnight_us"]["nasdaq"]["change_pct"] == 1.2


def test_latest_part_by_key(client: TestClient) -> None:
    upsert_parts("market_briefing_pre", "run_1", _sample_parts())
    r = client.get("/api/briefings/market_briefing_pre/latest/parts/scenario")
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "scenario"
    assert body["order"] == 2
    assert body["data"]["scenario"]["bias"] == "long"


def test_latest_part_404_on_unknown_key(client: TestClient) -> None:
    upsert_parts("market_briefing_pre", "run_1", _sample_parts())
    r = client.get("/api/briefings/market_briefing_pre/latest/parts/unknown")
    assert r.status_code == 404


# ----------------------------------------------------------------------------
# /run with cache=true
# ----------------------------------------------------------------------------

def test_run_with_cache_returns_latest(client: TestClient) -> None:
    upsert_parts("market_briefing_pre", "run_cached", _sample_parts())
    r = client.post("/api/briefings/market_briefing_pre/run?cache=true")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "run_cached"
    assert body["cache_hit"] is True


def test_run_with_cache_404_when_empty(client: TestClient) -> None:
    r = client.post("/api/briefings/market_briefing_pre/run?cache=true")
    assert r.status_code == 404


# ----------------------------------------------------------------------------
# /run with force=true (actually executes pipeline — monkeypatch runner)
# ----------------------------------------------------------------------------

def _install_fake_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    model_name: str = "gemini-2.5-pro",
    run_counter: dict[str, int] | None = None,
) -> None:
    """PipelineRunner.run 을 가짜로 대체 — briefing_parts 만 생성 + metadata 주입."""
    from pipelines._base import PipelineRunner

    async def fake_run(
        self: Any,
        manifest: PipelineManifest,
        *,
        input_data: dict | None = None,
        run_id: str | None = None,
    ) -> PipelineResult:
        if run_counter is not None:
            run_counter["n"] = run_counter.get("n", 0) + 1
        assert run_id is not None
        upsert_parts(manifest.id, run_id, _sample_parts())
        result = PipelineResult(pipeline_id=manifest.id, run_id=run_id)
        result.stages["analyze"] = StageResult(
            stage_id="analyze",
            status="ok",
            data={"metadata": {"model": model_name}},
        )
        return result

    monkeypatch.setattr(PipelineRunner, "run", fake_run)


def test_run_force_creates_new_run(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_runner(monkeypatch)
    r = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["cache_hit"] is False
    assert body["status"] == "ok"
    assert body["run_id"].endswith("")  # run_id exists
    assert len(body["parts"]) == 3


def test_run_force_ttl_cache_within_60s(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    counter = {"n": 0}
    _install_fake_runner(monkeypatch, run_counter=counter)

    # 시간을 0 에 고정해서 2번째 호출이 캐시 hit 이 되도록
    from server.api import briefings_on_demand as mod

    now = {"t": 0.0}
    monkeypatch.setattr(mod, "_time_source", lambda: now["t"])

    r1 = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r1.status_code == 200
    assert r1.json()["cache_hit"] is False

    now["t"] = 30.0  # 30 초 경과 < 60s TTL
    r2 = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r2.status_code == 200
    assert r2.json()["cache_hit"] is True
    assert r2.json()["run_id"] == r1.json()["run_id"]
    assert counter["n"] == 1, f"runner should run only once; ran {counter['n']}"


def test_run_force_ttl_cache_expires_after_60s(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """in-memory TTL + DB TTL 둘 다 만료 시 새 실행 트리거."""
    counter = {"n": 0}
    _install_fake_runner(monkeypatch, run_counter=counter)

    from core.db import get_db
    from server.api import briefings_on_demand as mod

    now = {"t": 0.0}
    monkeypatch.setattr(mod, "_time_source", lambda: now["t"])

    r1 = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r1.status_code == 200
    first_run_id = r1.json()["run_id"]

    # in-memory TTL 만료
    now["t"] = 61.0
    # DB 의 briefing_parts.created_at 도 과거로 밀어 DB 캐시도 만료되게
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE briefing_parts
            SET created_at = datetime('now', '-120 seconds')
            WHERE pipeline_id = 'market_briefing_pre'
            """
        )

    r2 = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r2.status_code == 200
    assert r2.json()["cache_hit"] is False
    assert r2.json()["run_id"] != first_run_id
    assert counter["n"] == 2


def test_run_force_degraded_when_mock_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_runner(monkeypatch, model_name="gemini-2.5-pro-mock")
    r = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"


def test_run_404_on_unknown_pipeline(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_runner(monkeypatch)
    r = client.post("/api/briefings/does_not_exist/run?force=true")
    assert r.status_code == 404


# ----------------------------------------------------------------------------
# /resend
# ----------------------------------------------------------------------------

def test_resend_latest_returns_delivered(client: TestClient) -> None:
    upsert_parts("market_briefing_pre", "run_r1", _sample_parts())
    r = client.post("/api/briefings/market_briefing_pre/resend")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "run_r1"
    assert body["delivered"] == ["telegram"]


def test_resend_specific_part_key(client: TestClient) -> None:
    upsert_parts("market_briefing_pre", "run_r1", _sample_parts())
    r = client.post(
        "/api/briefings/market_briefing_pre/resend?part_key=overnight"
    )
    assert r.status_code == 200


def test_resend_unknown_channel_400(client: TestClient) -> None:
    upsert_parts("market_briefing_pre", "run_r1", _sample_parts())
    r = client.post("/api/briefings/market_briefing_pre/resend?channel=slack")
    assert r.status_code == 400


def test_resend_unknown_run_id_404(client: TestClient) -> None:
    r = client.post("/api/briefings/market_briefing_pre/resend?run_id=nope")
    assert r.status_code == 404


# ----------------------------------------------------------------------------
# DB-level 중복 방지 (cross-process / post-restart 시나리오)
# ----------------------------------------------------------------------------

def test_run_force_uses_db_cache_when_fresh(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """이전 프로세스가 남긴 briefing_parts 가 60초 이내면 runner 건너뛰고 재사용."""
    # 다른 프로세스가 방금 저장했다고 가정 (in-memory 캐시는 비어있음)
    upsert_parts("market_briefing_pre", "from_prev_process", _sample_parts())

    counter = {"n": 0}
    _install_fake_runner(monkeypatch, run_counter=counter)

    r = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["cache_hit"] is True
    assert body["run_id"] == "from_prev_process"
    assert counter["n"] == 0, (
        "runner must NOT run when fresh DB row exists (cross-process dedup)"
    )


def test_run_force_db_cache_expires_after_ttl(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """briefing_parts 가 TTL(60초) 보다 오래됐으면 새 run 실행."""
    from core.db import get_db

    upsert_parts("market_briefing_pre", "stale_run", _sample_parts())
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE briefing_parts
            SET created_at = datetime('now', '-120 seconds')
            WHERE pipeline_id = 'market_briefing_pre' AND run_id = 'stale_run'
            """
        )

    counter = {"n": 0}
    _install_fake_runner(monkeypatch, run_counter=counter)

    r = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["cache_hit"] is False
    assert body["run_id"] != "stale_run"
    assert counter["n"] == 1


# ----------------------------------------------------------------------------
# Phase 1 (M3/M3.5): morning_pre 09:00 KST 이후 validation
# ----------------------------------------------------------------------------


def _freeze_now_kst(monkeypatch: pytest.MonkeyPatch, hour: int) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from server.api import briefings_on_demand as mod

    monkeypatch.setattr(
        mod,
        "_now_kst",
        lambda: datetime(
            2026, 4, 24, hour, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")
        ),
    )


def _insert_today_morning_snapshot(run_id: str) -> None:
    """당일 07:00 KST = 어제 22:00 UTC 에 보관본 하나 넣기."""
    from core.db import get_db

    upsert_parts("market_briefing_pre", run_id, _sample_parts())
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "UPDATE briefing_parts SET created_at='2026-04-23 22:00:00' "
            "WHERE run_id = ?",
            (run_id,),
        )


def test_run_without_force_after_9am_returns_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_now_kst(monkeypatch, hour=10)
    _insert_today_morning_snapshot("snap_run")

    r = client.post("/api/briefings/market_briefing_pre/run")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "snap_run"
    assert body["note"] == "before_market_open"
    assert body["cache_hit"] is True


def test_run_without_force_after_9am_no_snapshot_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_now_kst(monkeypatch, hour=10)

    r = client.post("/api/briefings/market_briefing_pre/run")
    assert r.status_code == 404
    assert "force=true" in r.json()["detail"]


def test_run_force_after_9am_bypasses_snapshot(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """보관본 있어도 force=true 면 실시간 새 run 실행."""
    _freeze_now_kst(monkeypatch, hour=10)
    _insert_today_morning_snapshot("snap_run")
    _install_fake_runner(monkeypatch)

    r = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] != "snap_run"
    assert body.get("note") is None
    assert body["cache_hit"] is False


# ----------------------------------------------------------------------------
# M6: 이중 발송 방지 — notify 쿼리 파라미터
# ----------------------------------------------------------------------------


def _install_capturing_runner(
    monkeypatch: pytest.MonkeyPatch, captured: dict
) -> None:
    from pipelines._base import PipelineRunner

    async def fake_run(
        self: Any,
        manifest: PipelineManifest,
        *,
        input_data: dict | None = None,
        run_id: str | None = None,
    ) -> PipelineResult:
        captured["input_data"] = input_data or {}
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


def test_run_notify_false_passes_skip_notify_true_to_runner(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """notify=false 쿼리 → runner input_data 에 skip_notify=True 전달."""
    captured: dict = {}
    _install_capturing_runner(monkeypatch, captured)

    r = client.post(
        "/api/briefings/market_briefing_pre/run?force=true&notify=false"
    )
    assert r.status_code == 200
    assert captured["input_data"].get("skip_notify") is True


def test_run_notify_default_passes_skip_notify_false(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """notify 기본 true → skip_notify=False (scheduled cron 경로 호환)."""
    captured: dict = {}
    _install_capturing_runner(monkeypatch, captured)

    r = client.post("/api/briefings/market_briefing_pre/run?force=true")
    assert r.status_code == 200
    assert captured["input_data"].get("skip_notify") is False


def test_notify_stage_skips_when_skip_notify_flag_set() -> None:
    """morning_pre notify stage 가 skip_notify=True 이면 early return."""
    import asyncio

    from pipelines._base import StageContext
    from pipelines.market_briefing_pre.stages.notify import NotifyStage

    stage = NotifyStage()
    ctx = StageContext(
        run_id="test_run",
        pipeline_id="market_briefing_pre",
        date="2026-04-25",
        data={"skip_notify": True},
    )
    result = asyncio.run(stage.run(ctx))
    assert result.status == "ok"
    assert result.data.get("skipped") is True


# ----------------------------------------------------------------------------
# Phase 2 (M3 + M3.5): market_briefing 09:00 분기 + fallback
# ----------------------------------------------------------------------------


def _market_sample_parts() -> list[BriefingPart]:
    """market_briefing 파트 키 (market_overview / supply_sectors / leading_stocks)."""
    return [
        BriefingPart(
            key="market_overview",
            label="시장개요",
            order=1,
            data={
                "indices": {
                    "kospi": {"value": 6690.9, "change_pct": 0.5},
                    "kosdaq": {"value": 1220, "change_pct": 0.3},
                },
                "fetched_at": "2026-04-30T09:30:00+09:00",
            },
        ),
        BriefingPart(
            key="supply_sectors",
            label="수급+강세섹터",
            order=2,
            data={"supply_demand": {}, "sectors": {"all": [], "strong": []}},
        ),
        BriefingPart(
            key="leading_stocks",
            label="주도주",
            order=3,
            data={"leading_stocks": {"kospi": [], "kosdaq": [], "stats": {}}},
        ),
    ]


def _install_market_fake_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    run_counter: dict[str, int] | None = None,
) -> None:
    """market_briefing 용 fake runner — market_overview 키로 parts upsert."""
    from pipelines._base import PipelineRunner

    async def fake_run(
        self: Any,
        manifest: PipelineManifest,
        *,
        input_data: dict | None = None,
        run_id: str | None = None,
    ) -> PipelineResult:
        if run_counter is not None:
            run_counter["n"] = run_counter.get("n", 0) + 1
        assert run_id is not None
        upsert_parts(manifest.id, run_id, _market_sample_parts())
        return PipelineResult(pipeline_id=manifest.id, run_id=run_id)

    monkeypatch.setattr(PipelineRunner, "run", fake_run)


def test_market_briefing_pre_9am_falls_back_to_db_latest(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """08:30 + force=False + DB 에 직전 run 있음 → cache_hit + note=market_closed."""
    _freeze_now_kst(monkeypatch, hour=8)
    upsert_parts("market_briefing_now", "prev_run", _market_sample_parts())

    counter = {"n": 0}
    _install_market_fake_runner(monkeypatch, run_counter=counter)

    r = client.post("/api/briefings/market_briefing_now/run?force=false")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "prev_run"
    assert body["note"] == "market_closed"
    assert body["cache_hit"] is True
    assert counter["n"] == 0, "DB latest 사용 시 runner 호출 0"


def test_market_briefing_pre_9am_force_true_bypasses_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """08:30 + force=True + DB 에 직전 run 있어도 → 새 run 강제 (fallback 우회).

    `prev_run` 의 created_at 을 60s 보다 과거로 밀어 db_cache TTL 도 만료시킴
    (force 가 우회하는 건 fallback 분기 + 09:00 보관본 분기. 60s db_cache 는 별개).
    """
    from core.db import get_db

    _freeze_now_kst(monkeypatch, hour=8)
    upsert_parts("market_briefing_now", "prev_run", _market_sample_parts())
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "UPDATE briefing_parts SET created_at = datetime('now', '-120 seconds') "
            "WHERE pipeline_id = 'market_briefing_now' AND run_id = 'prev_run'"
        )

    counter = {"n": 0}
    _install_market_fake_runner(monkeypatch, run_counter=counter)

    r = client.post("/api/briefings/market_briefing_now/run?force=true")
    assert r.status_code == 200
    body = r.json()
    # 새 run 이라 prev_run 가 아니어야 함
    assert body["run_id"] != "prev_run"
    # 09:00 이전이라 note=market_closed (build 시 부착, force 무관)
    assert body["note"] == "market_closed"
    assert body["cache_hit"] is False
    assert counter["n"] == 1, "force=True 면 runner 1회 실행"


def test_market_briefing_pre_9am_db_miss_creates_new_run_with_note(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """08:30 + DB 비어있음 → 새 run + note=market_closed."""
    _freeze_now_kst(monkeypatch, hour=8)
    counter = {"n": 0}
    _install_market_fake_runner(monkeypatch, run_counter=counter)

    r = client.post("/api/briefings/market_briefing_now/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["note"] == "market_closed"
    assert body["cache_hit"] is False
    assert counter["n"] == 1


def test_market_briefing_early_window_attaches_note(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """09:00 (00:20 미만) → 새 run + note=market_briefing_early."""
    _freeze_now_kst(monkeypatch, hour=9)  # minute=0 → 09:00 < 09:20
    _install_market_fake_runner(monkeypatch)

    r = client.post("/api/briefings/market_briefing_now/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["note"] == "market_briefing_early"
    assert body["cache_hit"] is False


def test_market_briefing_normal_hours_no_note(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """10:00 → 새 run + note=None."""
    _freeze_now_kst(monkeypatch, hour=10)
    _install_market_fake_runner(monkeypatch)

    r = client.post("/api/briefings/market_briefing_now/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body.get("note") is None
    assert body["cache_hit"] is False


def test_market_briefing_pre_9am_db_latest_uses_market_closed_not_early(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """08:30 + force=False + DB latest 있음 → note=market_closed (early 아님)."""
    _freeze_now_kst(monkeypatch, hour=8)
    upsert_parts("market_briefing_now", "yesterday_close", _market_sample_parts())

    r = client.post("/api/briefings/market_briefing_now/run?force=false")
    assert r.status_code == 200
    body = r.json()
    assert body["note"] == "market_closed"
    # 09:00 분기보다 < 9 분기가 먼저 발동해야 함
    assert body["note"] != "market_briefing_early"
