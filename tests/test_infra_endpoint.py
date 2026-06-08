"""server/api/infra.py — POST /api/infra/refresh-snapshots 수동 트리거.

run_daily_refresh 는 monkeypatch 로 mock — 실 적재/LLM 호출 X.
endpoint 가 잡으로 위임하고 집계 JSON 을 그대로 반환하는지만 검증(얇은 라우터).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import infra as infra_route


@pytest.fixture
def client() -> TestClient:
    from server.main import app

    return TestClient(app)


def test_refresh_snapshots_delegates_and_returns(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST → run_daily_refresh 호출 + 집계 dict 그대로 200 반환."""
    called = {"n": 0}

    async def fake_daily_refresh():
        called["n"] += 1
        return {
            "snapshot_macro": {"market_view": {"regime": "moderate_bull"}},
            "news": {"collected": 3, "classified": 2},
            "elapsed_s": 1.23,
        }

    monkeypatch.setattr(infra_route, "run_daily_refresh", fake_daily_refresh)

    resp = client.post("/api/infra/refresh-snapshots")

    assert resp.status_code == 200
    assert called["n"] == 1
    body = resp.json()
    assert body["snapshot_macro"]["market_view"]["regime"] == "moderate_bull"
    assert body["news"]["collected"] == 3
    assert body["elapsed_s"] == 1.23
