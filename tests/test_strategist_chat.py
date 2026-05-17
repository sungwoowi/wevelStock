"""server/api/strategist_chat.py — 3 endpoints + target field + 404 fallback.

대상:
- POST /api/strategists/{id}/chat        — 멀티턴 입력 → 응답 + target 전달
- POST /api/strategists/{id}/chat/stream — SSE 이벤트 흐름
- GET  /api/strategists/{id}             — 메타 정보 (실 track_a 디렉토리 read)

run_strategist / run_strategist_stream 은 monkeypatch 로 mock — 실 LLM 호출 X.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.strategist.run_strategist import StrategistResponse


@pytest.fixture
def client() -> TestClient:
    from server.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /chat — single-turn
# ---------------------------------------------------------------------------


def test_post_chat_happy_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_strategist mock → 200 + text/metadata 반환 + target 전달."""
    captured: dict[str, Any] = {}

    async def fake_run_strategist(
        strategist_id: str,
        messages: list[dict],
        *,
        target: str = "global",
        model: str | None = None,
        include_memory: bool = True,
        provider: str | None = None,
    ) -> StrategistResponse:
        captured["strategist_id"] = strategist_id
        captured["messages"] = messages
        captured["target"] = target
        captured["provider"] = provider
        return StrategistResponse(
            text="권고 본문 (mock)",
            metadata={
                "strategist_id": strategist_id,
                "track": "A",
                "target": target,
                "analyst_published_count": 0,
                "analyst_missing_count": 6,
                "tokens_in": 100,
                "tokens_out": 50,
                "model": "mock",
            },
        )

    from server.api import strategist_chat as mod
    monkeypatch.setattr(mod, "run_strategist", fake_run_strategist)

    resp = client.post(
        "/api/strategists/track_a/chat",
        json={
            "messages": [{"role": "user", "content": "long: 삼성전자 분석해줘"}],
            "target": "005930",
            "provider": "mock",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "권고 본문 (mock)"
    assert body["metadata"]["track"] == "A"
    assert body["metadata"]["target"] == "005930"

    # 호출 인자 전달 검증
    assert captured["strategist_id"] == "track_a"
    assert captured["target"] == "005930"
    assert captured["provider"] == "mock"
    assert captured["messages"][0]["content"] == "long: 삼성전자 분석해줘"


def test_post_chat_default_target_is_global(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """target 명시 안 하면 default = 'global'."""
    captured: dict[str, Any] = {}

    async def fake_run_strategist(strategist_id, messages, *, target="global", **_):
        captured["target"] = target
        return StrategistResponse(text="ok", metadata={"target": target})

    from server.api import strategist_chat as mod
    monkeypatch.setattr(mod, "run_strategist", fake_run_strategist)

    resp = client.post(
        "/api/strategists/track_a/chat",
        json={"messages": [{"role": "user", "content": "test"}]},
    )
    assert resp.status_code == 200
    assert captured["target"] == "global"


def test_post_chat_unknown_strategist_returns_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """StrategistNotFoundError → 404."""
    from server.api import strategist_chat as mod

    async def fake_run_strategist(*args, **kwargs):
        raise mod.StrategistNotFoundError("missing manifest")

    monkeypatch.setattr(mod, "run_strategist", fake_run_strategist)

    resp = client.post(
        "/api/strategists/non_existent/chat",
        json={"messages": [{"role": "user", "content": "test"}]},
    )
    assert resp.status_code == 404
    assert "missing manifest" in resp.json()["detail"]


def test_post_chat_inference_failure_returns_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM 호출 실패 → 500 + 에러 메시지 포함."""
    from server.api import strategist_chat as mod

    async def fake_run_strategist(*args, **kwargs):
        raise RuntimeError("upstream LLM crashed")

    monkeypatch.setattr(mod, "run_strategist", fake_run_strategist)

    resp = client.post(
        "/api/strategists/track_a/chat",
        json={"messages": [{"role": "user", "content": "test"}]},
    )
    assert resp.status_code == 500
    assert "upstream LLM crashed" in resp.json()["detail"]


def test_post_chat_empty_messages_returns_422(client: TestClient) -> None:
    """messages 배열 빔 → Pydantic 검증 422."""
    resp = client.post(
        "/api/strategists/track_a/chat",
        json={"messages": []},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /chat/stream — SSE
# ---------------------------------------------------------------------------


def test_post_chat_stream_emits_events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """text_delta + metadata + done 이벤트 흐름."""

    async def fake_stream(
        strategist_id: str,
        messages: list[dict],
        *,
        target: str = "global",
        model: str | None = None,
        include_memory: bool = True,
        provider: str | None = None,
    ):
        yield {"type": "text_delta", "text": "권고 "}
        yield {"type": "text_delta", "text": "본문"}
        yield {
            "type": "metadata",
            "strategist_id": strategist_id,
            "track": "A",
            "target": target,
            "tokens_in": 100,
            "tokens_out": 10,
        }
        yield {"type": "done"}

    from server.api import strategist_chat as mod
    monkeypatch.setattr(mod, "run_strategist_stream", fake_stream)

    resp = client.post(
        "/api/strategists/track_a/chat/stream",
        json={
            "messages": [{"role": "user", "content": "test"}],
            "target": "005930",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    # SSE 라인 파싱 — "data: {...}\n\n" 형식
    raw = resp.content.decode("utf-8")
    events: list[dict] = []
    for chunk in raw.split("\n\n"):
        chunk = chunk.strip()
        if chunk.startswith("data: "):
            payload = chunk[len("data: "):]
            events.append(json.loads(payload))

    # text_delta 2개 + metadata 1개 + done 1개
    types = [e["type"] for e in events]
    assert "text_delta" in types
    assert "metadata" in types
    assert "done" in types

    # metadata 에 target 전달됨
    meta = next(e for e in events if e["type"] == "metadata")
    assert meta["target"] == "005930"
    assert meta["track"] == "A"


def test_post_chat_stream_unknown_strategist_emits_404_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """StrategistNotFoundError → error 이벤트 (status=404) + done."""
    from server.api import strategist_chat as mod

    async def fake_stream(*args, **kwargs):
        raise mod.StrategistNotFoundError("missing manifest")
        yield  # pragma: no cover (unreachable; satisfies async gen)

    monkeypatch.setattr(mod, "run_strategist_stream", fake_stream)

    resp = client.post(
        "/api/strategists/non_existent/chat/stream",
        json={"messages": [{"role": "user", "content": "test"}]},
    )
    assert resp.status_code == 200  # SSE 자체는 200, 본문에 error event
    raw = resp.content.decode("utf-8")
    events: list[dict] = []
    for chunk in raw.split("\n\n"):
        chunk = chunk.strip()
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[len("data: "):]))

    error_event = next(e for e in events if e["type"] == "error")
    assert error_event["status"] == 404
    assert "missing manifest" in error_event["message"]
    assert events[-1]["type"] == "done"


# ---------------------------------------------------------------------------
# GET /strategists/{id} — meta
# ---------------------------------------------------------------------------


def test_get_strategist_meta_returns_real_track_a(client: TestClient) -> None:
    """실 track_a 디렉토리 read → 메타 정보 반환."""
    resp = client.get("/api/strategists/track_a")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "track_a"
    assert body["track"] == "A"
    assert isinstance(body["reads_analysts"], list)
    assert len(body["reads_analysts"]) >= 6  # 6 분석가 권한
    assert "stock_picker" in body["reads_analysts"]
    assert "stock_analyst" in body["reads_analysts"]
    assert isinstance(body["canon_categories"], list)
    assert body["temperature"] == 0.4  # 결정론 강화


def test_get_strategist_meta_unknown_returns_404(client: TestClient) -> None:
    resp = client.get("/api/strategists/non_existent")
    assert resp.status_code == 404
