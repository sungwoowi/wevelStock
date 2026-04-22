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
    """각 테스트마다 briefing_parts 초기화 + in-memory 캐시 초기화."""
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
# /latest
# ----------------------------------------------------------------------------

def test_latest_404_when_empty(client: TestClient) -> None:
    r = client.get("/api/briefings/morning_pre/latest")
    assert r.status_code == 404


def test_latest_returns_parts(client: TestClient) -> None:
    upsert_parts("morning_pre", "run_1", _sample_parts())
    r = client.get("/api/briefings/morning_pre/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline_id"] == "morning_pre"
    assert body["run_id"] == "run_1"
    assert body["status"] == "ok"
    assert body["cache_hit"] is False
    assert len(body["parts"]) == 3
    assert [p["key"] for p in body["parts"]] == ["overnight", "scenario", "positions"]
    assert body["parts"][0]["data"]["overnight_us"]["nasdaq"]["change_pct"] == 1.2


def test_latest_part_by_key(client: TestClient) -> None:
    upsert_parts("morning_pre", "run_1", _sample_parts())
    r = client.get("/api/briefings/morning_pre/latest/parts/scenario")
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "scenario"
    assert body["order"] == 2
    assert body["data"]["scenario"]["bias"] == "long"


def test_latest_part_404_on_unknown_key(client: TestClient) -> None:
    upsert_parts("morning_pre", "run_1", _sample_parts())
    r = client.get("/api/briefings/morning_pre/latest/parts/unknown")
    assert r.status_code == 404


# ----------------------------------------------------------------------------
# /run with cache=true
# ----------------------------------------------------------------------------

def test_run_with_cache_returns_latest(client: TestClient) -> None:
    upsert_parts("morning_pre", "run_cached", _sample_parts())
    r = client.post("/api/briefings/morning_pre/run?cache=true")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "run_cached"
    assert body["cache_hit"] is True


def test_run_with_cache_404_when_empty(client: TestClient) -> None:
    r = client.post("/api/briefings/morning_pre/run?cache=true")
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
    r = client.post("/api/briefings/morning_pre/run?force=true")
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

    r1 = client.post("/api/briefings/morning_pre/run?force=true")
    assert r1.status_code == 200
    assert r1.json()["cache_hit"] is False

    now["t"] = 30.0  # 30 초 경과 < 60s TTL
    r2 = client.post("/api/briefings/morning_pre/run?force=true")
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

    r1 = client.post("/api/briefings/morning_pre/run?force=true")
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
            WHERE pipeline_id = 'morning_pre'
            """
        )

    r2 = client.post("/api/briefings/morning_pre/run?force=true")
    assert r2.status_code == 200
    assert r2.json()["cache_hit"] is False
    assert r2.json()["run_id"] != first_run_id
    assert counter["n"] == 2


def test_run_force_degraded_when_mock_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_runner(monkeypatch, model_name="gemini-2.5-pro-mock")
    r = client.post("/api/briefings/morning_pre/run?force=true")
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
    upsert_parts("morning_pre", "run_r1", _sample_parts())
    r = client.post("/api/briefings/morning_pre/resend")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "run_r1"
    assert body["delivered"] == ["telegram"]


def test_resend_specific_part_key(client: TestClient) -> None:
    upsert_parts("morning_pre", "run_r1", _sample_parts())
    r = client.post(
        "/api/briefings/morning_pre/resend?part_key=overnight"
    )
    assert r.status_code == 200


def test_resend_unknown_channel_400(client: TestClient) -> None:
    upsert_parts("morning_pre", "run_r1", _sample_parts())
    r = client.post("/api/briefings/morning_pre/resend?channel=slack")
    assert r.status_code == 400


def test_resend_unknown_run_id_404(client: TestClient) -> None:
    r = client.post("/api/briefings/morning_pre/resend?run_id=nope")
    assert r.status_code == 404


# ----------------------------------------------------------------------------
# DB-level 중복 방지 (cross-process / post-restart 시나리오)
# ----------------------------------------------------------------------------

def test_run_force_uses_db_cache_when_fresh(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """이전 프로세스가 남긴 briefing_parts 가 60초 이내면 runner 건너뛰고 재사용."""
    # 다른 프로세스가 방금 저장했다고 가정 (in-memory 캐시는 비어있음)
    upsert_parts("morning_pre", "from_prev_process", _sample_parts())

    counter = {"n": 0}
    _install_fake_runner(monkeypatch, run_counter=counter)

    r = client.post("/api/briefings/morning_pre/run?force=true")
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

    upsert_parts("morning_pre", "stale_run", _sample_parts())
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE briefing_parts
            SET created_at = datetime('now', '-120 seconds')
            WHERE pipeline_id = 'morning_pre' AND run_id = 'stale_run'
            """
        )

    counter = {"n": 0}
    _install_fake_runner(monkeypatch, run_counter=counter)

    r = client.post("/api/briefings/morning_pre/run?force=true")
    assert r.status_code == 200
    body = r.json()
    assert body["cache_hit"] is False
    assert body["run_id"] != "stale_run"
    assert counter["n"] == 1
