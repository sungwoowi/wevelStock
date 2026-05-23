"""mock_fallback_allowed gate 단위 검증.

PRODUCTION-UX-001 후속 fix: production-chat 사용자 경로에서 silent mock
fallback 으로 가짜 응답이 노출되는 문제 차단. core/llm/client.py 의
`call_llm(mock_fallback_allowed=False)` + `_resolve_provider(mock_fallback_allowed=False)`
가 real provider 미설정 또는 실패 시 RuntimeError 를 propagate 하는지.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

os.environ.setdefault("TESTING", "1")

from core.llm.client import _resolve_provider, call_llm


class _Cfg:
    """get_config().llm 의 최소 stub."""

    class _Sub:
        pass

    def __init__(self, provider: str, mock_if_no_key: bool = True) -> None:
        self.provider = provider
        self.mock_if_no_key = mock_if_no_key
        self.primary = "claude-sonnet-4-5"
        self.anthropic = _Cfg._Sub()
        self.anthropic.model = "claude-sonnet-4-5"
        self.anthropic.max_tokens = 2000
        self.anthropic.temperature = 0.3
        self.gemini = _Cfg._Sub()
        self.gemini.model = "gemini-2.5-flash"


class TestResolveProvider:
    """_resolve_provider 의 mock_fallback_allowed gate."""

    def test_anthropic_no_key_with_default_allows_mock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg = _Cfg(provider="anthropic", mock_if_no_key=True)
        assert _resolve_provider(cfg) == "mock"

    def test_anthropic_no_key_with_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        cfg = _Cfg(provider="anthropic", mock_if_no_key=True)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            _resolve_provider(cfg, mock_fallback_allowed=False)

    def test_gemini_no_key_with_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)
        cfg = _Cfg(provider="gemini", mock_if_no_key=True)
        with pytest.raises(RuntimeError, match="GOOGLE_AI_API_KEY"):
            _resolve_provider(cfg, mock_fallback_allowed=False)

    def test_anthropic_with_key_returns_anthropic_regardless(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        cfg = _Cfg(provider="anthropic")
        assert _resolve_provider(cfg) == "anthropic"
        assert _resolve_provider(cfg, mock_fallback_allowed=False) == "anthropic"


class TestCallLLMNoMockOnFailure:
    """call_llm(mock_fallback_allowed=False) 가 real provider 실패 시 RuntimeError 전파."""

    def test_no_keys_with_disabled_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API key 둘 다 없고 mock_fallback_allowed=False → RuntimeError."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)

        # provider 가 anthropic 으로 결정됐다고 가정 — _resolve_provider 가 RuntimeError 던짐
        from core.config import get_config

        cfg = get_config()
        # Force provider to anthropic for this test (runtime.yaml override 무시)
        monkeypatch.setattr(cfg.llm, "provider", "anthropic", raising=False)
        monkeypatch.setattr(cfg.llm, "mock_if_no_key", True, raising=False)

        async def _go() -> Any:
            return await call_llm(
                system="x",
                messages=[{"role": "user", "content": "ping"}],
                mock_fallback_allowed=False,
            )

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            asyncio.run(_go())

    def test_default_allows_mock_silently(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """mock_fallback_allowed 기본 True 면 mock 응답 반환 (legacy 동작 보존)."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_AI_API_KEY", raising=False)

        from core.config import get_config

        cfg = get_config()
        monkeypatch.setattr(cfg.llm, "provider", "anthropic", raising=False)
        monkeypatch.setattr(cfg.llm, "mock_if_no_key", True, raising=False)

        async def _go() -> dict:
            return await call_llm(
                system="x",
                messages=[{"role": "user", "content": "ping"}],
            )

        resp = asyncio.run(_go())
        # mock 응답 — content 는 mock json, model 에 "-mock" suffix
        assert "-mock" in resp.get("model", "")
        raw = resp.get("raw") or {}
        assert raw.get("mock") is True
