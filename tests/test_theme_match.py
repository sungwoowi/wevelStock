"""collectors/theme_match.py 단위 테스트 (INFRA-SCORE-INPUTS-001 SLOT S1).

theme_match 2-Stage 하이브리드 — classify_theme (manual/LLM-mock/fallback) +
score_theme_match (결정론) + 캐싱 + resolve 결합. **call_llm mock 필수 (실 API 금지), TESTING=1.**
anchors.py 테스트 패턴 mirror.
"""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

from collectors.theme_match import (
    ThemeResult,
    _store_cached_theme,
    _theme_cache_key,
    classify_theme,
    resolve_theme_match,
    score_theme_match,
)
from core.db import get_db, reset_db

_BPS = [(-1.0, 1.0), (0.0, 5.0), (1.0, 9.0)]
_TAXONOMY = {"AI_semiconductor": "AI·반도체", "cosmetics": "화장품"}
_AUTHORITY = {"AI_semiconductor": ["foreign", "institution"], "cosmetics": ["foreign"]}


def _llm(content: str) -> dict:
    return {"content": content, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {}}


@pytest.fixture
def fresh_db(tmp_path):
    db_path = tmp_path / "test.db"
    reset_db()
    db = get_db(db_path)
    yield db
    reset_db()


# ---------------------------------------------------------------------------
# 1. score_theme_match — 결정론 채점 (DB/LLM 무관)
# ---------------------------------------------------------------------------


class TestScoreThemeMatch:
    def test_authority_buying_high(self) -> None:
        net = {"foreign_net": 3000, "institution_net": 2000, "individual_net": -1000,
               "financial_inv_net": 0, "pension_net": 0}
        s = score_theme_match("AI_semiconductor", net, authority_map=_AUTHORITY, breakpoints=_BPS)
        assert s is not None and s > 5.0

    def test_authority_selling_low(self) -> None:
        net = {"foreign_net": -3000, "institution_net": -2000, "individual_net": 1000,
               "financial_inv_net": 0, "pension_net": 0}
        s = score_theme_match("AI_semiconductor", net, authority_map=_AUTHORITY, breakpoints=_BPS)
        assert s is not None and s < 5.0

    def test_subject_alias_maps_short_name(self) -> None:
        # cosmetics 권위 = [foreign] (짧은 이름) → foreign_net 으로 매핑되어야
        net = {"foreign_net": 5000, "institution_net": 0, "individual_net": 0,
               "financial_inv_net": 0, "pension_net": 0}
        s = score_theme_match("cosmetics", net, authority_map=_AUTHORITY, breakpoints=_BPS)
        assert s is not None and s > 5.0

    def test_unknown_theme_returns_none(self) -> None:
        net = {k: 0 for k in ("foreign_net", "institution_net", "individual_net",
                              "financial_inv_net", "pension_net")}
        assert score_theme_match("nonexistent", net, authority_map=_AUTHORITY, breakpoints=_BPS) is None

    def test_no_breakpoints_returns_none(self) -> None:
        net = {"foreign_net": 1000, "institution_net": 0, "individual_net": 0,
               "financial_inv_net": 0, "pension_net": 0}
        assert score_theme_match("cosmetics", net, authority_map=_AUTHORITY, breakpoints=[]) is None

    def test_deterministic(self) -> None:
        net = {"foreign_net": 1234, "institution_net": 567, "individual_net": -89,
               "financial_inv_net": 12, "pension_net": 0}
        a = score_theme_match("AI_semiconductor", net, authority_map=_AUTHORITY, breakpoints=_BPS)
        b = score_theme_match("AI_semiconductor", net, authority_map=_AUTHORITY, breakpoints=_BPS)
        assert a == b


# ---------------------------------------------------------------------------
# 2. classify_theme — Stage 1+2 (manual / LLM mock / fallback / 캐싱)
# ---------------------------------------------------------------------------


class TestClassifyTheme:
    @pytest.mark.asyncio
    async def test_manual_override_no_llm(self, fresh_db) -> None:
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={"005930": "AI_semiconductor"}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value=_TAXONOMY), \
             patch("collectors.theme_match.call_llm") as mock_llm:
            res = await classify_theme("005930")
        assert res.theme == "AI_semiconductor"
        assert res.source == "manual"
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_classifies(self, fresh_db) -> None:
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value=_TAXONOMY), \
             patch("collectors.theme_match.call_llm",
                   return_value=_llm('{"theme": "cosmetics", "reasoning": "화장품 대표주"}')):
            res = await classify_theme("X", skip_cache=True)
        assert res.theme == "cosmetics"
        assert res.source == "llm"

    @pytest.mark.asyncio
    async def test_llm_none_is_neutral_fallback(self, fresh_db) -> None:
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value=_TAXONOMY), \
             patch("collectors.theme_match.call_llm",
                   return_value=_llm('{"theme": "none", "reasoning": "해당 없음"}')):
            res = await classify_theme("X", skip_cache=True)
        assert res.theme is None
        assert res.source == "neutral_fallback"

    @pytest.mark.asyncio
    async def test_llm_out_of_taxonomy_rejected(self, fresh_db) -> None:
        # LLM 이 taxonomy 에 없는 key 반환 → 무효 → None
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value=_TAXONOMY), \
             patch("collectors.theme_match.call_llm",
                   return_value=_llm('{"theme": "crypto", "reasoning": "made up"}')):
            res = await classify_theme("X", skip_cache=True)
        assert res.theme is None
        assert res.source == "neutral_fallback"

    @pytest.mark.asyncio
    async def test_llm_exception_neutral_fallback(self, fresh_db) -> None:
        async def _raise(**kwargs):
            raise RuntimeError("network")
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value=_TAXONOMY), \
             patch("collectors.theme_match.call_llm", side_effect=_raise):
            res = await classify_theme("X", skip_cache=True)
        assert res.theme is None
        assert res.source == "neutral_fallback"

    @pytest.mark.asyncio
    async def test_empty_taxonomy_neutral_fallback(self, fresh_db) -> None:
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value={}), \
             patch("collectors.theme_match.call_llm") as mock_llm:
            res = await classify_theme("X")
        assert res.theme is None
        assert res.source == "neutral_fallback"
        mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_ticker_neutral_fallback(self, fresh_db) -> None:
        res = await classify_theme("   ")
        assert res.theme is None
        assert res.source == "neutral_fallback"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, fresh_db) -> None:
        cache_key = _theme_cache_key("CACHED", list(_TAXONOMY.keys()))
        h = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        _store_cached_theme(h, {"theme": "cosmetics", "reasoning": "from cache"},
                            model="claude-haiku-4-5")
        call_count = 0

        async def _track(**kwargs):
            nonlocal call_count
            call_count += 1
            return _llm("{}")

        with patch("collectors.score_inputs_config.get_manual_theme", return_value={}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value=_TAXONOMY), \
             patch("collectors.theme_match.call_llm", side_effect=_track):
            res = await classify_theme("CACHED", skip_cache=False)
        assert call_count == 0
        assert res.theme == "cosmetics"
        assert res.source == "llm"


# ---------------------------------------------------------------------------
# 3. resolve_theme_match — 결합 진입점
# ---------------------------------------------------------------------------


class TestResolveThemeMatch:
    @pytest.mark.asyncio
    async def test_resolve_manual_plus_score(self, fresh_db) -> None:
        net = {"foreign_net": 4000, "institution_net": 0, "individual_net": 0,
               "financial_inv_net": 0, "pension_net": 0}
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={"X": "cosmetics"}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value=_TAXONOMY):
            score, theme, source = await resolve_theme_match(
                "X", net, authority_map=_AUTHORITY, breakpoints=_BPS
            )
        assert theme == "cosmetics"
        assert source == "manual"
        assert score is not None and score > 5.0

    @pytest.mark.asyncio
    async def test_resolve_unknown_theme_none_score(self, fresh_db) -> None:
        net = {k: 0 for k in ("foreign_net", "institution_net", "individual_net",
                              "financial_inv_net", "pension_net")}
        with patch("collectors.score_inputs_config.get_manual_theme", return_value={}), \
             patch("collectors.score_inputs_config.get_theme_taxonomy", return_value={}):
            score, theme, source = await resolve_theme_match("X", net, breakpoints=_BPS)
        assert score is None
        assert theme is None
        assert source == "neutral_fallback"
