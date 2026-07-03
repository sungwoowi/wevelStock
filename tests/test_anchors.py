"""WAVE-ALPHA-001 sub-cycle 14.3 — collectors/anchors.py 검증.

covers:
  - extract_swing_candidates (Stage 1 결정론 rolling local extrema + min_gap 필터)
  - select_anchors_via_llm (Stage 2 Haiku 4.5 직관 + JSON parse + 유효성 검증)
  - 3 단 캐싱 (llm_call_cache type='anchor_selection', cache_key)
  - load_manual_anchors (manual_anchors DB SELECT)
  - E6 fallback (Stage 2 실패 → deterministic_fallback)
  - compute_alpha_3tf 진입점 (cutoff_date 백테스팅, 3 timeframe)
  - render_alpha_3tf_md + alpha_3tf_metadata
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

os.environ.setdefault("TESTING", "1")

from collectors.anchors import (
    AlphaResult,
    _anchor_cache_key,
    _get_cached_anchor,
    _store_cached_anchor,
    alpha_3tf_metadata,
    compute_alpha_3tf,
    extract_swing_candidates,
    load_manual_anchors,
    render_alpha_3tf_md,
    select_anchors_via_llm,
)
from core.db import get_db, reset_db


# ---------------------------------------------------------------------------
# Fixture — in-memory test DB + chart_ohlcv seed
# ---------------------------------------------------------------------------


def _seed_ohlcv_synthetic(ticker: str, n: int = 600, *, start: date | None = None) -> pd.DataFrame:
    """결정론적 sin + drift 합성 OHLCV. swing high/low 가 분명히 생기도록."""
    import math as m
    base = start or date(2023, 1, 1)
    rows = []
    for i in range(n):
        d = base + timedelta(days=i)
        # 30봉 주기 sin + 0.5%/일 drift
        close = 100.0 + 50.0 * m.sin(i / 30 * 2 * m.pi) + i * 0.5
        if close <= 0:
            close = 1.0
        high = close * 1.02
        low = close * 0.98
        rows.append({
            "ticker": ticker, "date": d.isoformat(),
            "open": close, "high": high, "low": low, "close": close,
            "volume": 1_000_000 + i * 100,
            "change_rate": 0.0,
            "value": int(close * 1_000_000),
            "adjusted": 1,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })
    return pd.DataFrame(rows)


@pytest.fixture
def fresh_db(tmp_path):
    """tmp 디렉토리 + singleton 리셋 → 새 DB 인스턴스 (테스트 격리)."""
    db_path = tmp_path / "test.db"
    reset_db()
    db = get_db(db_path)
    yield db
    reset_db()


@pytest.fixture
def seeded_ohlcv(fresh_db):
    """fresh_db + 합성 OHLCV 1 ticker."""
    ticker = "TEST01"
    df = _seed_ohlcv_synthetic(ticker, n=800)
    with fresh_db.connect() as conn:
        conn.executemany(
            "INSERT INTO chart_ohlcv (ticker, date, open, high, low, close, volume, change_rate, value, adjusted, fetched_at) "
            "VALUES (:ticker, :date, :open, :high, :low, :close, :volume, :change_rate, :value, :adjusted, :fetched_at)",
            df.to_dict("records"),
        )
    return ticker


# ---------------------------------------------------------------------------
# 1. extract_swing_candidates — Stage 1 결정론
# ---------------------------------------------------------------------------


def _df_for_candidates(close_values: list[float], start: date | None = None) -> pd.DataFrame:
    base = start or date(2024, 1, 1)
    idx = pd.DatetimeIndex([pd.Timestamp(base + timedelta(days=i)) for i in range(len(close_values))])
    return pd.DataFrame({
        "open": close_values,
        "high": [c * 1.01 for c in close_values],
        "low": [c * 0.99 for c in close_values],
        "close": close_values,
        "volume": [1_000_000] * len(close_values),
    }, index=idx)


class TestExtractSwingCandidates:

    def test_invalid_timeframe_raises(self) -> None:
        with pytest.raises(ValueError, match="timeframe"):
            extract_swing_candidates(pd.DataFrame(), "hourly")

    def test_empty_returns_empty_list(self) -> None:
        assert extract_swing_candidates(pd.DataFrame(), "daily") == []

    def test_too_short_returns_empty_list(self) -> None:
        df = _df_for_candidates([100.0] * 5)
        assert extract_swing_candidates(df, "daily") == []

    def test_deterministic_same_input_same_output(self) -> None:
        """결정론 — 같은 OHLCV → 같은 candidate list."""
        import math as m
        closes = [100 + 30 * m.sin(i / 15) for i in range(200)]
        df = _df_for_candidates(closes)
        r1 = extract_swing_candidates(df, "daily")
        r2 = extract_swing_candidates(df, "daily")
        assert r1 == r2

    def test_finds_alternating_high_low(self) -> None:
        """sin 파동 → high + low candidate 모두 산출."""
        import math as m
        closes = [100 + 30 * m.sin(i / 20) for i in range(300)]
        df = _df_for_candidates(closes)
        cands = extract_swing_candidates(df, "daily")
        assert len(cands) >= 4
        kinds = {c[2] for c in cands}
        assert "high" in kinds
        assert "low" in kinds

    def test_candidates_sorted_by_date(self) -> None:
        import math as m
        closes = [100 + 30 * m.sin(i / 20) for i in range(300)]
        df = _df_for_candidates(closes)
        cands = extract_swing_candidates(df, "daily")
        dates = [c[0] for c in cands]
        assert dates == sorted(dates)

    def test_max_candidates_caps(self) -> None:
        import math as m
        closes = [100 + 30 * m.sin(i / 5) for i in range(500)]  # 짧은 주기 → 많은 candidate
        df = _df_for_candidates(closes)
        cands = extract_swing_candidates(df, "daily", max_candidates=5)
        assert len(cands) <= 5

    def test_weekly_resample(self) -> None:
        """weekly = W-FRI resample 후 동작."""
        import math as m
        closes = [100 + 30 * m.sin(i / 20) for i in range(500)]
        df = _df_for_candidates(closes)
        cands = extract_swing_candidates(df, "weekly")
        assert isinstance(cands, list)
        # weekly 면 candidate 사이 일수 ≥ 7 (1 bar = 7일)
        if len(cands) >= 2:
            gaps = [(cands[i + 1][0] - cands[i][0]).days for i in range(len(cands) - 1)]
            assert all(g >= 7 for g in gaps)

    def test_monthly_resample(self) -> None:
        import math as m
        closes = [100 + 30 * m.sin(i / 60) for i in range(2000)]
        df = _df_for_candidates(closes)
        cands = extract_swing_candidates(df, "monthly")
        assert isinstance(cands, list)


# ---------------------------------------------------------------------------
# 2. _anchor_cache_key + 3단 캐싱 (llm_call_cache type)
# ---------------------------------------------------------------------------


class TestAnchorCache:

    def test_cache_key_format(self) -> None:
        k = _anchor_cache_key("005930", "weekly", date(2026, 5, 22))
        assert k == "005930|weekly|2026-05-22"

    def test_cache_key_differs_per_ticker(self) -> None:
        a = _anchor_cache_key("AAA", "daily", date(2026, 5, 22))
        b = _anchor_cache_key("BBB", "daily", date(2026, 5, 22))
        assert a != b

    def test_cache_key_differs_per_cutoff(self) -> None:
        a = _anchor_cache_key("X", "daily", date(2026, 5, 22))
        b = _anchor_cache_key("X", "daily", date(2026, 5, 23))
        assert a != b

    def test_cache_miss_returns_none(self, fresh_db) -> None:
        assert _get_cached_anchor("nonexistent_hash_xyz") is None

    def test_cache_store_and_retrieve(self, fresh_db) -> None:
        payload = {"A_idx": 0, "B_idx": 2, "C_idx": 4, "reasoning": "test"}
        _store_cached_anchor("hash_abc", payload, model="claude-haiku-4-5")
        got = _get_cached_anchor("hash_abc")
        assert got == payload

    def test_cache_only_returns_anchor_type(self, fresh_db) -> None:
        """type='general' 인 row 는 anchor cache 조회 시 무시."""
        from core.memory.cache import store_cached_response
        # type='general' (default) 로 저장
        store_cached_response(
            input_hash="general_hash",
            model="claude-sonnet-4-5",
            response={"content": "general"},
        )
        # anchor cache 로 조회 → None (type 불일치)
        assert _get_cached_anchor("general_hash") is None

    def test_cache_expires_after_ttl(self, fresh_db) -> None:
        payload = {"A_idx": 0, "B_idx": 1, "C_idx": 2, "reasoning": "old"}
        # 직접 SQL 로 31일 전 row 박음
        with fresh_db.connect() as conn:
            old_iso = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
            conn.execute(
                "INSERT INTO llm_call_cache (input_hash, model, response_json, tokens_in, tokens_out, cost_usd, ttl_days, created_at, type) "
                "VALUES (?, ?, ?, 0, 0, 0, 30, ?, 'anchor_selection')",
                ("expired_hash", "claude-haiku-4-5", json.dumps(payload), old_iso),
            )
        assert _get_cached_anchor("expired_hash", ttl_days=30) is None


# ---------------------------------------------------------------------------
# 3. select_anchors_via_llm — Stage 2 mock
# ---------------------------------------------------------------------------


class TestSelectAnchorsViaLLM:

    @pytest.fixture
    def candidates(self) -> list:
        return [
            (date(2024, 1, 1), 100.0, "low"),
            (date(2024, 3, 1), 95.0, "low"),
            (date(2024, 6, 1), 200.0, "high"),
            (date(2024, 7, 1), 150.0, "low"),
            (date(2024, 9, 1), 250.0, "high"),
        ]

    @pytest.mark.asyncio
    async def test_too_few_candidates_returns_none(self) -> None:
        few = [(date(2024, 1, 1), 100.0, "low"), (date(2024, 6, 1), 200.0, "high")]
        result = await select_anchors_via_llm("X", "daily", few, skip_cache=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_llm_response_parsed(self, candidates, fresh_db) -> None:
        mock_resp = {
            "content": '{"A_idx": 0, "B_idx": 2, "C_idx": 3, "reasoning": "good"}',
            "tokens_in": 100, "tokens_out": 20, "cost_usd": 0.001, "model": "claude-haiku-4-5",
            "raw": {},
        }
        with patch("collectors.anchors.call_llm", return_value=mock_resp):
            result = await select_anchors_via_llm(
                "TEST", "weekly", candidates,
                cutoff_date=date(2024, 12, 1), skip_cache=True,
            )
        assert result is not None
        assert result["A_idx"] == 0
        assert result["B_idx"] == 2
        assert result["C_idx"] == 3
        assert "good" in result["reasoning"]

    @pytest.mark.asyncio
    async def test_invalid_order_rejected(self, candidates, fresh_db) -> None:
        """A < B < C 위반 시 None."""
        mock_resp = {
            "content": '{"A_idx": 3, "B_idx": 1, "C_idx": 4, "reasoning": "bad order"}',
            "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {},
        }
        with patch("collectors.anchors.call_llm", return_value=mock_resp):
            result = await select_anchors_via_llm("X", "daily", candidates, skip_cache=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_out_of_range_rejected(self, candidates, fresh_db) -> None:
        mock_resp = {
            "content": '{"A_idx": 0, "B_idx": 1, "C_idx": 99, "reasoning": "oor"}',
            "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {},
        }
        with patch("collectors.anchors.call_llm", return_value=mock_resp):
            result = await select_anchors_via_llm("X", "daily", candidates, skip_cache=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_exception_returns_none(self, candidates, fresh_db) -> None:
        """LLM 호출 자체 실패 시 None (run_analyst 가 fallback)."""
        async def _raise(**kwargs):
            raise RuntimeError("network")
        with patch("collectors.anchors.call_llm", side_effect=_raise):
            result = await select_anchors_via_llm("X", "daily", candidates, skip_cache=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_disables_gemini_thinking(self, candidates, fresh_db) -> None:
        """Stage 2 호출이 thinking_budget=0 으로 나가는지 (Gemini 잘림→fallback 회귀 방지)."""
        mock_resp = {
            "content": '{"A_idx": 0, "B_idx": 2, "C_idx": 3, "reasoning": "ok"}',
            "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {},
        }
        with patch("collectors.anchors.call_llm", return_value=mock_resp) as mock_llm:
            await select_anchors_via_llm("X", "daily", candidates, skip_cache=True)
        mock_llm.assert_called_once()
        assert mock_llm.call_args.kwargs["thinking_budget"] == 0

    @pytest.mark.asyncio
    async def test_malformed_json_returns_none(self, candidates, fresh_db) -> None:
        mock_resp = {
            "content": "not json at all", "tokens_in": 0, "tokens_out": 0,
            "cost_usd": 0.0, "model": "x", "raw": {},
        }
        with patch("collectors.anchors.call_llm", return_value=mock_resp):
            result = await select_anchors_via_llm("X", "daily", candidates, skip_cache=True)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, candidates, fresh_db) -> None:
        """캐시 hit 시 LLM 호출 X."""
        cutoff = date(2024, 12, 1)
        cache_key = _anchor_cache_key("CACHED", "weekly", cutoff)
        import hashlib
        h = hashlib.sha256(cache_key.encode()).hexdigest()
        payload = {"A_idx": 1, "B_idx": 2, "C_idx": 4, "reasoning": "from cache"}
        _store_cached_anchor(h, payload, model="claude-haiku-4-5")

        call_count = 0
        async def _track(**kwargs):
            nonlocal call_count
            call_count += 1
            return {"content": "{}", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {}}
        with patch("collectors.anchors.call_llm", side_effect=_track):
            result = await select_anchors_via_llm(
                "CACHED", "weekly", candidates, cutoff_date=cutoff, skip_cache=False,
            )
        assert call_count == 0
        assert result == payload

    @pytest.mark.asyncio
    async def test_skip_cache_bypasses_lookup(self, candidates, fresh_db) -> None:
        cutoff = date(2024, 12, 1)
        cache_key = _anchor_cache_key("SKIP", "weekly", cutoff)
        import hashlib
        h = hashlib.sha256(cache_key.encode()).hexdigest()
        _store_cached_anchor(h, {"A_idx": 0, "B_idx": 1, "C_idx": 2, "reasoning": "old"},
                              model="claude-haiku-4-5")

        mock_resp = {
            "content": '{"A_idx": 1, "B_idx": 3, "C_idx": 4, "reasoning": "fresh"}',
            "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {},
        }
        with patch("collectors.anchors.call_llm", return_value=mock_resp):
            result = await select_anchors_via_llm(
                "SKIP", "weekly", candidates, cutoff_date=cutoff, skip_cache=True,
            )
        assert result["reasoning"] == "fresh"


# ---------------------------------------------------------------------------
# 4. load_manual_anchors — manual_anchors DB
# ---------------------------------------------------------------------------


class TestManualAnchors:

    def test_returns_none_when_absent(self, fresh_db) -> None:
        assert load_manual_anchors("NONE", "weekly") is None

    def test_loads_after_insert(self, fresh_db) -> None:
        with fresh_db.connect() as conn:
            conn.execute(
                "INSERT INTO manual_anchors "
                "(ticker, timeframe, anchor_a_date, anchor_a_price, anchor_b_date, anchor_b_price, "
                "anchor_c_date, anchor_c_price, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("HE1", "weekly", "2023-01-01", 100.0, "2023-06-01", 200.0,
                 "2023-07-01", 150.0, "user-set"),
            )
        result = load_manual_anchors("HE1", "weekly")
        assert result is not None
        a, b, c = result
        assert a == (date(2023, 1, 1), 100.0)
        assert b == (date(2023, 6, 1), 200.0)
        assert c == (date(2023, 7, 1), 150.0)

    def test_timeframe_specific(self, fresh_db) -> None:
        with fresh_db.connect() as conn:
            conn.execute(
                "INSERT INTO manual_anchors (ticker, timeframe, anchor_a_date, anchor_a_price, "
                "anchor_b_date, anchor_b_price, anchor_c_date, anchor_c_price) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("X", "monthly", "2020-01-01", 50.0, "2022-01-01", 200.0, "2022-06-01", 120.0),
            )
        assert load_manual_anchors("X", "daily") is None
        assert load_manual_anchors("X", "weekly") is None
        assert load_manual_anchors("X", "monthly") is not None


# ---------------------------------------------------------------------------
# 5. compute_alpha_3tf — 진입점 + WE6 fallback
# ---------------------------------------------------------------------------


class TestComputeAlpha3TF:

    @pytest.mark.asyncio
    async def test_unavailable_when_no_ohlcv(self, fresh_db) -> None:
        results = await compute_alpha_3tf("NOTHING")
        assert set(results.keys()) == {"daily", "weekly", "monthly"}
        for r in results.values():
            assert r.source == "unavailable"
            assert r.value is None
            assert r.label is None

    @pytest.mark.asyncio
    async def test_manual_override_uses_manual(self, seeded_ohlcv, fresh_db) -> None:
        ticker = seeded_ohlcv
        # manual anchor 박음 (weekly)
        with fresh_db.connect() as conn:
            conn.execute(
                "INSERT INTO manual_anchors (ticker, timeframe, anchor_a_date, anchor_a_price, "
                "anchor_b_date, anchor_b_price, anchor_c_date, anchor_c_price) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ticker, "weekly", "2023-02-01", 80.0, "2023-08-01", 180.0, "2023-10-01", 130.0),
            )
        # LLM 호출 안 일어나야 함
        async def _fail(**kwargs):
            raise AssertionError("LLM should not be called when manual override exists")
        with patch("collectors.anchors.call_llm", side_effect=_fail):
            results = await compute_alpha_3tf(ticker, skip_cache=True)
        assert results["weekly"].source == "manual"
        assert results["weekly"].anchor_a == (date(2023, 2, 1), 80.0)

    @pytest.mark.asyncio
    async def test_deterministic_by_default_no_llm(self, seeded_ohlcv, fresh_db) -> None:
        """기본(anchor_llm_enabled=false): LLM 호출 없이 결정론 픽 → source='deterministic'."""
        ticker = seeded_ohlcv
        async def _fail(**kwargs):
            raise AssertionError("anchor_llm_enabled=false 기본에서 LLM 이 호출되면 안 됨")
        with patch("collectors.anchors.call_llm", side_effect=_fail):
            results = await compute_alpha_3tf(ticker, skip_cache=True)
        sources = [r.source for r in results.values()]
        assert "deterministic" in sources
        assert all(s in ("deterministic", "unavailable", "manual") for s in sources)

    @pytest.mark.asyncio
    async def test_e6_fallback_when_llm_fails(self, seeded_ohlcv, fresh_db) -> None:
        """anchor_llm_enabled=true + LLM 실패 시 결정론 candidate 마지막 3 개로 fallback."""
        ticker = seeded_ohlcv
        async def _raise(**kwargs):
            raise RuntimeError("llm down")
        cfg = SimpleNamespace(alpha=SimpleNamespace(anchor_llm_enabled=True))
        with patch("collectors.anchors.get_config", return_value=cfg), \
             patch("collectors.anchors.call_llm", side_effect=_raise):
            results = await compute_alpha_3tf(ticker, skip_cache=True)
        # 적어도 한 timeframe 은 deterministic_fallback 으로 떨어져야 함
        sources = [r.source for r in results.values()]
        assert "deterministic_fallback" in sources or "unavailable" in sources

    @pytest.mark.asyncio
    async def test_cutoff_date_filters_ohlcv(self, seeded_ohlcv, fresh_db) -> None:
        """cutoff_date 박으면 그 시점까지의 ohlcv 만 사용."""
        ticker = seeded_ohlcv
        cutoff = date(2024, 6, 1)
        async def _ok(**kwargs):
            return {"content": '{"A_idx": 0, "B_idx": 2, "C_idx": 4, "reasoning": "x"}',
                    "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {}}
        with patch("collectors.anchors.call_llm", side_effect=_ok):
            results = await compute_alpha_3tf(ticker, cutoff_date=cutoff, skip_cache=True)
        for tf in ("daily", "weekly", "monthly"):
            r = results[tf]
            if r.current is not None:
                assert r.current[0] <= cutoff

    @pytest.mark.asyncio
    async def test_returns_3_timeframe_keys(self, seeded_ohlcv, fresh_db) -> None:
        async def _ok(**kwargs):
            return {"content": '{"A_idx": 0, "B_idx": 2, "C_idx": 4, "reasoning": "x"}',
                    "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "model": "x", "raw": {}}
        with patch("collectors.anchors.call_llm", side_effect=_ok):
            results = await compute_alpha_3tf(seeded_ohlcv, skip_cache=True)
        assert set(results.keys()) == {"daily", "weekly", "monthly"}


# ---------------------------------------------------------------------------
# 6. render_alpha_3tf_md + alpha_3tf_metadata
# ---------------------------------------------------------------------------


def _make_result(tf: str, source: str = "llm_stage2", value: float | None = 1.5,
                 label: str | None = "sweet") -> AlphaResult:
    return AlphaResult(
        timeframe=tf,
        value=value,
        label=label,
        anchor_a=(date(2024, 1, 1), 100.0),
        anchor_b=(date(2024, 6, 1), 200.0),
        anchor_c=(date(2024, 7, 1), 150.0),
        current=(date(2024, 12, 1), 220.0),
        progress_to_b=1.1,
        duration_ratio=0.83,
        source=source,
        reason="test",
    )


class TestRenderAndMetadata:

    def test_render_has_block_header(self) -> None:
        results = {tf: _make_result(tf) for tf in ("daily", "weekly", "monthly")}
        md = render_alpha_3tf_md(results, "005930")
        assert "[5] α 3 timeframe (WAVE-ALPHA-001)" in md
        assert "005930" in md

    def test_render_lists_all_3_timeframes(self) -> None:
        results = {tf: _make_result(tf) for tf in ("daily", "weekly", "monthly")}
        md = render_alpha_3tf_md(results, "X")
        for tf in ("daily", "weekly", "monthly"):
            assert tf in md

    def test_render_cites_canon_ids(self) -> None:
        """WA·WF·WL·WE canon ID 가 header 에 박혀야 함 (환각 가드 3중 정합)."""
        results = {tf: _make_result(tf) for tf in ("daily", "weekly", "monthly")}
        md = render_alpha_3tf_md(results, "X")
        for prefix in ("WA1", "WA2", "WA3", "WF1", "WF2", "WF3", "WL1", "WL2", "WL3"):
            assert prefix in md

    def test_render_shows_source_column(self) -> None:
        results = {"daily": _make_result("daily", source="manual"),
                   "weekly": _make_result("weekly", source="llm_stage2"),
                   "monthly": _make_result("monthly", source="deterministic_fallback")}
        md = render_alpha_3tf_md(results, "X")
        assert "manual" in md
        assert "llm_stage2" in md
        assert "deterministic_fallback" in md

    def test_metadata_has_3_timeframe_keys(self) -> None:
        results = {tf: _make_result(tf) for tf in ("daily", "weekly", "monthly")}
        meta = alpha_3tf_metadata(results)
        assert "alpha_daily" in meta
        assert "alpha_weekly" in meta
        assert "alpha_monthly" in meta
        for tf in ("daily", "weekly", "monthly"):
            entry = meta[f"alpha_{tf}"]
            assert entry["source"] == "llm_stage2"
            assert entry["value"] == 1.5
            assert entry["label"] == "sweet"

    def test_metadata_unavailable_safe(self) -> None:
        results = {tf: _make_result(tf, source="unavailable", value=None, label=None)
                   for tf in ("daily", "weekly", "monthly")}
        # anchor_a/b/c 가 None 일 수 있도록 변경
        results["daily"].anchor_a = None  # type: ignore[misc]
        results["daily"].anchor_b = None  # type: ignore[misc]
        results["daily"].anchor_c = None  # type: ignore[misc]
        meta = alpha_3tf_metadata(results)
        assert meta["alpha_daily"]["anchor_a_date"] is None
        assert meta["alpha_daily"]["value"] is None
