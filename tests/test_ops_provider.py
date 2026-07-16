"""ops LLM provider 토글 + theme_match 누수 봉합 회귀 테스트.

배경: 2026-07-14~16 Gemini 지출한도 도달 시 theme_match 가 claude_code 로 무성 폴백하며
claude-haiku 를 22~41K 토큰으로 호출해 낭비. 원인 = provider 미지정(allow_fallback=True) +
claude 모델 하드코딩. 봉합 = resolve_model_for_area("theme_match") 경유 + provider 명시.
"""
from __future__ import annotations

import asyncio

import server.api.ops as ops
from core.llm.tiers import resolve_model_for_area


def test_theme_match_area_registered_fast():
    """theme_match 가 fast tier 로 등록돼 balanced 로 새지 않는다."""
    from core.config import get_config

    assert get_config().llm.areas.theme_match == "fast"


def test_theme_match_resolves_to_current_provider_model():
    """resolve_model_for_area 가 현재 provider 에 맞는 모델을 준다(claude 하드코딩 아님)."""
    provider, model = resolve_model_for_area("theme_match")
    assert provider in ("gemini", "claude_code", "anthropic", "mock")
    # provider=gemini 면 gemini 모델, claude_code 면 claude 모델 — 교차 하드코딩 없음.
    if provider == "gemini":
        assert model.startswith("gemini")
    if provider in ("claude_code", "anthropic"):
        assert "claude" in model


def test_get_llm_provider_shape():
    r = asyncio.run(ops.get_llm_provider())
    assert r["provider"] in ops._PROVIDERS
    assert set(r["options"]) == set(ops._PROVIDERS)
    assert "gemini" in r["availability"]


def test_set_llm_provider_rejects_bad():
    from fastapi import HTTPException

    try:
        asyncio.run(ops.set_llm_provider(provider="not_a_provider"))
        assert False, "잘못된 provider 는 400 이어야 함"
    except HTTPException as e:
        assert e.status_code == 400


def test_set_llm_provider_writes_runtime_yaml(tmp_path, monkeypatch):
    """POST 가 runtime.yaml 의 llm.provider 라인만 치환(주석·타 키 보존)."""
    rt = tmp_path / "runtime.yaml"
    rt.write_text(
        "# comment\nllm:\n  provider: gemini\n  tiers:\n    fast:\n"
        "      gemini: gemini-2.5-flash-lite\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ops, "RUNTIME_PATH", rt)
    monkeypatch.setattr(ops, "env", lambda k, d=None: None)  # .env 오버라이드 없음

    r = asyncio.run(ops.set_llm_provider(provider="claude_code"))
    assert r["provider"] == "claude_code"
    assert r["applied"] is True
    text = rt.read_text(encoding="utf-8")
    assert "  provider: claude_code" in text
    assert "# comment" in text  # 주석 보존
    assert "gemini-2.5-flash-lite" in text  # tiers 안 건드림
