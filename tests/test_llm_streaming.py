"""LLM streaming (INFRA-LLM-STREAM-001) 단위 테스트.

대상:
- core.llm.client.call_llm_stream — provider 분기 + fallback chain + 이벤트 계약
- core.inference.run_analyst.run_analyst_stream — 분석가 streaming + metadata

실 API (Anthropic / Gemini / claude_code CLI) 호출 0. 모두 mock.
"""
from __future__ import annotations

import time
from typing import Any, AsyncIterator

import pytest

from core.llm import client as llm_client


async def _collect(it: AsyncIterator[dict]) -> list[dict]:
    out: list[dict] = []
    async for ev in it:
        out.append(ev)
    return out


# ---------------------------------------------------------------------------
# 1. Mock provider stream — 이벤트 시퀀스 + 계약 키
# ---------------------------------------------------------------------------


async def test_mock_stream_emits_text_then_metadata_then_done() -> None:
    events = await _collect(
        llm_client.call_llm_stream(
            system="sys", messages=[{"role": "user", "content": "test"}],
            model="claude-sonnet-4", provider="mock",
        )
    )
    types_seq = [e["type"] for e in events]
    # text_delta 1회 이상 → metadata 1회 → done 1회
    assert types_seq[-1] == "done"
    assert types_seq[-2] == "metadata"
    assert "text_delta" in types_seq
    # metadata 키 계약
    md = events[-2]
    assert "tokens_in" in md and "tokens_out" in md
    assert "cost_usd" in md and "model" in md
    assert "content" in md  # 누적 텍스트


async def test_mock_stream_concatenated_text_matches_metadata_content() -> None:
    events = await _collect(
        llm_client.call_llm_stream(
            system=[{"text": "sys"}], messages=[{"role": "user", "content": "test"}],
            model="claude-sonnet-4", provider="mock",
        )
    )
    text_parts = [e["text"] for e in events if e["type"] == "text_delta"]
    md = next(e for e in events if e["type"] == "metadata")
    assert "".join(text_parts) == md["content"]


# ---------------------------------------------------------------------------
# 2. Fallback chain — 첫 청크 전 실패 → 다음 provider
# ---------------------------------------------------------------------------


async def test_stream_falls_back_to_mock_when_all_providers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """auto chain 에서 첫 provider 첫 청크 전 실패 → claude_code 도 실패 → mock fallback."""
    # 환경 env (GOOGLE_AI_API_KEY 등) 의존성 끊고 anthropic 시작점 강제
    monkeypatch.setattr(
        llm_client, "_resolve_provider",
        lambda cfg, **_kwargs: "anthropic",
    )

    async def _broken_anthropic(*args, **kwargs):
        raise RuntimeError("ANTHROPIC_API_KEY missing")
        # noinspection PyUnreachableCode
        yield  # 마커

    async def _broken_claude_code(*args, **kwargs):
        raise RuntimeError("not authenticated")
        yield

    monkeypatch.setattr(llm_client, "_stream_anthropic", _broken_anthropic)
    from core.llm import claude_code_backend
    monkeypatch.setattr(
        claude_code_backend, "call_claude_code_stream", _broken_claude_code,
    )

    events = await _collect(
        llm_client.call_llm_stream(
            system="sys", messages=[{"role": "user", "content": "test"}],
            model="claude-sonnet-4", provider=None,  # auto chain
        )
    )
    md = next(e for e in events if e["type"] == "metadata")
    # mock fallback 도달 표지
    assert "-mock" in md["model"] or md.get("raw", {}).get("fallback_used") == "mock"
    assert events[-1]["type"] == "done"


async def test_stream_partial_failure_after_first_chunk_emits_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """첫 청크 후 실패 → fallback X, error event + done."""

    async def _half_then_fail(*args, **kwargs):
        yield {"type": "text_delta", "text": "first chunk"}
        raise RuntimeError("network broke mid-stream")

    monkeypatch.setattr(llm_client, "_stream_anthropic", _half_then_fail)

    events = await _collect(
        llm_client.call_llm_stream(
            system="sys", messages=[{"role": "user", "content": "test"}],
            model="claude-sonnet-4", provider="anthropic",  # 명시 → fallback X
        )
    )
    types_seq = [e["type"] for e in events]
    assert "text_delta" in types_seq
    assert "error" in types_seq
    assert types_seq[-1] == "done"
    err = next(e for e in events if e["type"] == "error")
    assert "network broke" in err["message"]
    assert err["fatal"] is True


async def test_stream_explicit_provider_no_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provider 명시 시 fallback X — 에러는 error event 로."""

    async def _broken(*args, **kwargs):
        raise RuntimeError("upstream down")
        yield

    monkeypatch.setattr(llm_client, "_stream_gemini", _broken)

    events = await _collect(
        llm_client.call_llm_stream(
            system="sys", messages=[{"role": "user", "content": "test"}],
            model="gemini-2.5-flash", provider="gemini",
        )
    )
    types_seq = [e["type"] for e in events]
    assert "error" in types_seq
    # mock fallback 안 됐는지 — text_delta 없음 (mock 이라면 청크 emit)
    assert "text_delta" not in types_seq
    assert types_seq[-1] == "done"


# ---------------------------------------------------------------------------
# 3. run_analyst_stream — 분석가 streaming + metadata
# ---------------------------------------------------------------------------


async def test_run_analyst_stream_yields_text_then_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_analyst_stream — call_llm_stream 을 mock 으로 시뮬 + metadata 키 확인."""
    import sys
    import core.inference.run_analyst  # noqa: F401
    ra_mod = sys.modules["core.inference.run_analyst"]
    from core.inference.run_analyst import run_analyst_stream

    # call_llm_stream mock — 청크 3개 + metadata
    async def _fake_stream(**kwargs):
        yield {"type": "text_delta", "text": "안녕"}
        yield {"type": "text_delta", "text": "하세요"}
        yield {"type": "text_delta", "text": " 분석가입니다"}
        yield {
            "type": "metadata",
            "content": "안녕하세요 분석가입니다",
            "tokens_in": 1234, "tokens_out": 56,
            "model": "claude-sonnet-4", "cost_usd": 0.01,
            "raw": {"provider": "anthropic", "usage": {}},
        }
        yield {"type": "done"}

    monkeypatch.setattr(ra_mod, "call_llm_stream", _fake_stream)

    # market snapshot 도 mock
    from collectors.snapshot import MarketSnapshot
    fake_snap = MarketSnapshot(
        fetched_at=time.time(),
        fetched_at_iso="2026-05-09T00:00:00+09:00",
        overnight={}, fear_greed={}, kr_indices={}, kr_supply={},
        kr_futures_supply={}, kr_sectors={}, kr_leading={},
        failures=[], source_map={"kr": "fetch", "us": "fetch"}, db_run_ids={},
    )

    async def _fake_snap():
        return fake_snap, False

    monkeypatch.setattr(ra_mod, "build_market_snapshot", _fake_snap)
    monkeypatch.setattr(ra_mod, "render_snapshot_md", lambda s: "## stub")

    events = await _collect(
        run_analyst_stream("wealth_strategist", [{"role": "user", "content": "test"}])
    )
    types_seq = [e["type"] for e in events]
    assert types_seq.count("text_delta") == 3
    assert types_seq[-1] == "done"
    assert types_seq[-2] == "metadata"

    md = events[-2]
    # run_analyst 와 동일한 분석가 metadata 키 모두
    for key in (
        "analyst_id", "display_name", "rag_dept", "system_prompt_chars",
        "tokens_in", "tokens_out", "cost_usd", "latency_s",
        "first_token_ms", "snapshot_source_map", "snapshot_db_run_ids",
        "provider_used",
    ):
        assert key in md, f"missing metadata key: {key}"
    # streaming 특유 — first_token_ms
    assert md["first_token_ms"] is not None
    assert md["tokens_in"] == 1234


async def test_run_analyst_stream_first_token_ms_is_lower_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """첫 text_delta 까지 측정한 ms 가 latency_s 의 ms 변환보다 작거나 같음."""
    import sys
    import core.inference.run_analyst  # noqa: F401
    ra_mod = sys.modules["core.inference.run_analyst"]
    from core.inference.run_analyst import run_analyst_stream

    import asyncio as _asyncio

    async def _fake_stream(**kwargs):
        await _asyncio.sleep(0.05)
        yield {"type": "text_delta", "text": "hi"}
        await _asyncio.sleep(0.05)
        yield {"type": "metadata", "content": "hi", "tokens_in": 1,
               "tokens_out": 1, "model": "x", "cost_usd": 0, "raw": {}}
        yield {"type": "done"}

    monkeypatch.setattr(ra_mod, "call_llm_stream", _fake_stream)

    from collectors.snapshot import MarketSnapshot
    fake_snap = MarketSnapshot(
        fetched_at=time.time(), fetched_at_iso="2026-05-09T00:00:00+09:00",
        overnight={}, fear_greed={}, kr_indices={}, kr_supply={},
        kr_futures_supply={}, kr_sectors={}, kr_leading={}, failures=[],
        source_map={}, db_run_ids={},
    )

    async def _fake_snap():
        return fake_snap, False

    monkeypatch.setattr(ra_mod, "build_market_snapshot", _fake_snap)
    monkeypatch.setattr(ra_mod, "render_snapshot_md", lambda s: "")

    events = await _collect(
        run_analyst_stream("wealth_strategist", [{"role": "user", "content": "test"}])
    )
    md = next(e for e in events if e["type"] == "metadata"
              and "first_token_ms" in e)
    assert md["first_token_ms"] >= 50  # 0.05s 슬립 후 첫 토큰
    assert md["first_token_ms"] <= md["latency_s"] * 1000 + 10  # 살짝 여유
