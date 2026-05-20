"""INFRA-RUNTIME-EFFICIENCY-001 v3 patch (cycle 7) — scripts.ask_strategist 가
in-process run_strategist 가 아니라 server HTTP endpoint 를 호출하는지 검증.

핵심 본질 = test_ask_analyst_http 와 동일: CLI 매 실행 = 새 Python 프로세스 =
BGE-m3 재로딩. server 경유로 바꿔 프로세스 1 개 안에서 lru_cache reuse 가능.
본 테스트는 httpx AsyncClient 를 mock 으로 가로채 정상·연결실패·404·500
응답 시 exit code 와 stdout/stderr 가 의도대로인지 확인.

ask_strategist 특수성: `target` 필드 + analyst_published/missing metadata 노출 +
strategist endpoint URL prefix (`/api/strategists/{id}/chat`).
"""
from __future__ import annotations

import asyncio
import importlib
from typing import Any
from unittest.mock import patch

import httpx

ask_mod = importlib.import_module("scripts.ask_strategist")


class _MockResponse:
    def __init__(self, status_code: int, payload: dict | str) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = payload if isinstance(payload, str) else ""

    def json(self) -> Any:
        if isinstance(self._payload, dict):
            return self._payload
        raise ValueError("not json")


class _MockClient:
    """httpx.AsyncClient stand-in for tests.

    `behaviour` 가 callable → request 받아 _MockResponse 반환 또는 raise.
    """

    def __init__(self, behaviour) -> None:
        self._behaviour = behaviour
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self) -> "_MockClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def post(self, url: str, *, json: dict | None = None) -> _MockResponse:  # type: ignore[override]
        self.calls.append((url, json or {}))
        out = self._behaviour(url, json or {})
        if isinstance(out, Exception):
            raise out
        return out


def _run(coro):
    return asyncio.run(coro)


def _strategist_meta(track: str = "A", target: str = "global", published: int = 0, missing: int = 0) -> dict:
    """strategist endpoint metadata 의 잠정 풀세트 (cycle 4 검증 시점 기준)."""
    return {
        "system_prompt_chars": 12_345,
        "rag_chunks_returned": 3,
        "tokens_in": 100,
        "tokens_out": 50,
        "cost_usd": 0.0042,
        "latency_s": 1.5,
        "model": "claude-sonnet-4-6",
        "provider_used": "anthropic",
        "track": track,
        "target": target,
        "analyst_published_count": published,
        "analyst_missing_count": missing,
        "analyst_missing_ids": [],
    }


def test_success_prints_text_and_metadata(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WEVELSTOCK_SERVER_URL", "http://test-server:9999")
    monkeypatch.setattr(ask_mod, "QUERIES_DIR", tmp_path / "queries")

    def _ok(url, payload):
        return _MockResponse(
            200,
            {
                "text": "Track A 권고 본문 (cited_scores 풍부)",
                "metadata": _strategist_meta(
                    track="A", target="005930", published=5, missing=1
                ) | {"analyst_missing_ids": ["news_curator"]},
            },
        )

    captured_client: dict[str, _MockClient] = {}

    def _factory(*_a, **_kw):
        c = _MockClient(_ok)
        captured_client["c"] = c
        return c

    with patch("httpx.AsyncClient", _factory):
        rc = _run(ask_mod._ask("track_a", "오늘 시장 어떤가?", target="005930"))

    assert rc == 0
    assert captured_client["c"].calls[0][0] == (
        "http://test-server:9999/api/strategists/track_a/chat"
    )
    out = capsys.readouterr().out
    assert "Track A 권고 본문" in out
    assert "track A" in out
    assert "target 005930" in out
    assert "scores 5/6" in out
    assert "missing: news_curator" in out
    assert "12,345 chars" in out


def test_connect_error_returns_exit_3_with_clear_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WEVELSTOCK_SERVER_URL", "http://test-server:9999")
    monkeypatch.setattr(ask_mod, "QUERIES_DIR", tmp_path / "queries")

    def _conn_err(url, payload):
        return httpx.ConnectError("conn refused")

    with patch("httpx.AsyncClient", lambda *a, **kw: _MockClient(_conn_err)):
        rc = _run(ask_mod._ask("track_a", "q"))

    assert rc == 3
    err = capsys.readouterr().err
    assert "WevelStock 서버에 연결할 수 없습니다" in err
    assert "just server" in err


def test_404_returns_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ask_mod, "QUERIES_DIR", tmp_path / "queries")

    def _not_found(url, payload):
        return _MockResponse(
            404, {"detail": "strategist 'track_zzz' 가 등록되지 않았습니다"}
        )

    with patch("httpx.AsyncClient", lambda *a, **kw: _MockClient(_not_found)):
        rc = _run(ask_mod._ask("track_zzz", "q"))

    assert rc == 2
    err = capsys.readouterr().err
    assert "등록되지 않았습니다" in err


def test_500_returns_exit_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ask_mod, "QUERIES_DIR", tmp_path / "queries")

    def _server_err(url, payload):
        return _MockResponse(500, {"detail": "inference failed: rate limited"})

    with patch("httpx.AsyncClient", lambda *a, **kw: _MockClient(_server_err)):
        rc = _run(ask_mod._ask("track_a", "q"))

    assert rc == 1
    err = capsys.readouterr().err
    assert "LLM 호출 실패" in err
    assert "status 500" in err


def test_target_and_provider_forwarded_to_server(tmp_path, monkeypatch):
    monkeypatch.setattr(ask_mod, "QUERIES_DIR", tmp_path / "queries")

    def _ok(url, payload):
        return _MockResponse(
            200,
            {
                "text": "x",
                "metadata": _strategist_meta(track="B", target="035720"),
            },
        )

    captured: dict[str, _MockClient] = {}

    def _factory(*_a, **_kw):
        c = _MockClient(_ok)
        captured["c"] = c
        return c

    with patch("httpx.AsyncClient", _factory):
        _run(
            ask_mod._ask(
                "track_b", "q", target="035720", provider="claude_code"
            )
        )

    body = captured["c"].calls[0][1]
    assert body["target"] == "035720"
    assert body["provider"] == "claude_code"
    assert body["messages"] == [{"role": "user", "content": "q"}]


def test_no_provider_when_unspecified_and_default_target_global(tmp_path, monkeypatch):
    """provider 미지정 시 payload 에서 키 자체가 빠져야 함 (auto fallback chain).
    target 미지정 시 'global' 기본값 박힘."""
    monkeypatch.setattr(ask_mod, "QUERIES_DIR", tmp_path / "queries")

    def _ok(url, payload):
        return _MockResponse(
            200,
            {
                "text": "x",
                "metadata": _strategist_meta(track="A", target="global"),
            },
        )

    captured: dict[str, _MockClient] = {}

    def _factory(*_a, **_kw):
        c = _MockClient(_ok)
        captured["c"] = c
        return c

    with patch("httpx.AsyncClient", _factory):
        _run(ask_mod._ask("track_a", "q"))

    body = captured["c"].calls[0][1]
    assert "provider" not in body  # auto fallback chain
    assert body["target"] == "global"  # 기본값
