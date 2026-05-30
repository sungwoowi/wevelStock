"""collectors/technicals.py 단위 테스트 (INFRA-SCORE-INPUTS-001 M3 / T-Score 원시 지표).

순수 compute 는 합성 indicators dict 로 테스트 (charts/DB 의존 없음).
같은 입력 → 같은 출력 ±0. 원시 지표 = 권위(LLM 주입), advisory t_score = 참고선.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from collectors.anchors import extract_swing_candidates
from collectors.technicals import (
    _atr,
    compute_rr,
    compute_technical_inputs,
    render_technicals_md,
)

# T-Score 매핑 breakpoints (테스트용 명시 — DI)
_BPS = {
    "divergence": [(-20.0, 2.0), (-2.0, 9.0), (3.0, 8.0), (25.0, 1.0)],
    "macd": [(-3.0, 2.0), (0.0, 5.0), (3.0, 9.0)],
    "volume": [(0.5, 3.0), (1.0, 5.0), (1.8, 8.0), (6.0, 4.0)],
    "rr": [(0.5, 1.0), (1.5, 6.0), (3.0, 9.0)],
}


def _indicators(*, ma20=100.0, hist=0.0, spike=1.0, close=100.0):
    return {
        "current_close": close,
        "daily_ma": {"ma20": ma20},
        "macd": {"macd": 1.0, "signal": 0.5, "histogram": hist},
        "volume": {"today": 1000, "ma20": 1000, "spike_ratio": spike},
    }


class TestComputeTechnicalInputs:
    def test_divergence_pct_from_ma20(self) -> None:
        # price 110, ma20 100 → 이격도 +10%
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=110.0), 110.0, breakpoints=_BPS
        )
        assert ti.divergence_pct == pytest.approx(10.0, abs=0.01)

    def test_volume_ratio_passthrough(self) -> None:
        ti = compute_technical_inputs(
            _indicators(spike=1.8), 100.0, breakpoints=_BPS
        )
        assert ti.volume_ratio == pytest.approx(1.8)
        assert ti.volume_score == 8.0  # breakpoint 정확

    def test_axes_mapped_to_0_10(self) -> None:
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=98.0, spike=1.8, hist=0.0),
            98.0, rr=1.5, breakpoints=_BPS,
        )
        for sc in (ti.divergence_score, ti.macd_score, ti.volume_score, ti.rr_score):
            assert sc is None or (0.0 <= sc <= 10.0 and (sc * 2) % 1 == 0)

    def test_advisory_t_score_present_when_all_axes(self) -> None:
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=99.0, spike=1.8),
            99.0, rr=2.0, alpha=0.0, breakpoints=_BPS,
        )
        assert ti.advisory_t_score is not None
        assert 0.0 <= ti.advisory_t_score <= 10.0

    def test_alpha_override_lifts_advisory(self) -> None:
        # α 1.6 (강발산) → t_score max(base, 7.0) (STRATEGY-TRACK-001)
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=99.0, spike=1.0, hist=0.0),
            99.0, rr=1.5, alpha=1.6, breakpoints=_BPS,
        )
        assert ti.advisory_t_score >= 7.0

    def test_missing_ma20_divergence_none(self) -> None:
        ind = _indicators()
        ind["daily_ma"]["ma20"] = None
        ti = compute_technical_inputs(ind, 100.0, breakpoints=_BPS)
        assert ti.divergence_pct is None
        assert ti.divergence_score is None
        assert any("이격도" in r or "ma20" in r.lower() for r in ti.reasons)

    def test_deterministic(self) -> None:
        a = compute_technical_inputs(_indicators(spike=1.8), 105.0, rr=2.0, breakpoints=_BPS)
        b = compute_technical_inputs(_indicators(spike=1.8), 105.0, rr=2.0, breakpoints=_BPS)
        assert a.advisory_t_score == b.advisory_t_score
        assert a.divergence_pct == b.divergence_pct


class TestRenderTechnicalsMd:
    def test_md_contains_raw_and_advisory(self) -> None:
        ti = compute_technical_inputs(
            _indicators(ma20=100.0, close=110.0, spike=1.8),
            110.0, rr=2.0, alpha=0.0, breakpoints=_BPS, ticker="005930",
        )
        md = render_technicals_md(ti)
        assert "005930" in md
        assert "이격도" in md
        # advisory 라벨 + override 가능 명시 (게이트키핑 아님)
        assert "advisory" in md.lower() or "참고선" in md
        # 원시 지표 값 노출
        assert "+10" in md or "10.0" in md

    def test_md_handles_none(self) -> None:
        ind = _indicators()
        ind["daily_ma"]["ma20"] = None
        ti = compute_technical_inputs(ind, 100.0, breakpoints=_BPS, ticker="000660")
        md = render_technicals_md(ti)
        assert isinstance(md, str)
        assert "000660" in md


# ---------------------------------------------------------------------------
# R/R 산출 (SLOT S3 — 스윙+ATR 하이브리드)
# ---------------------------------------------------------------------------


def _df(closes: list[float], *, start: date | None = None) -> pd.DataFrame:
    """합성 일봉 OHLCV — high/low 는 종가 ±1% (anchors 테스트 패턴 mirror)."""
    base = start or date(2024, 1, 1)
    idx = pd.DatetimeIndex([pd.Timestamp(base + timedelta(days=i)) for i in range(len(closes))])
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


def _zigzag_df() -> pd.DataFrame:
    """뚜렷한 골짜기(~90)·봉우리(~150) 가 중앙에 있는 지그재그 — 스윙 검출 보장."""
    down = [130 - i * 2 for i in range(21)]      # 130 → 90 (valley)
    up = [90 + i * 3 for i in range(1, 21)]      # 90 → 147 (peak)
    tail = [147 - i * 2 for i in range(1, 21)]   # 147 → 109 (current 영역)
    return _df([float(x) for x in down + up + tail])


class TestAtr:
    def test_atr_positive(self) -> None:
        atr = _atr(_df([100.0, 102.0, 99.0, 103.0, 101.0]), period=14)
        assert atr is not None and atr > 0

    def test_atr_too_short_none(self) -> None:
        assert _atr(_df([100.0]), period=14) is None
        assert _atr(pd.DataFrame(), period=14) is None


class TestComputeRr:
    def test_swing_clamped_into_atr_band(self) -> None:
        """스윙저점을 [floor, cap]×ATR risk 밴드로 clamp + 인근 스윙고점 → R/R. 로직 정합."""
        df = _zigzag_df()
        entry = 110.0
        swings = extract_swing_candidates(df, "daily")
        lows_below = [p for _, p, k in swings if k == "low" and p < entry]
        highs_above = [p for _, p, k in swings if k == "high" and p > entry]
        # 픽스처가 실제로 스윙을 제공하는지 보장 (테스트 유의미성)
        assert lows_below and highs_above
        atr = _atr(df, 14)
        lo, hi = entry - 3.0 * atr, entry - 1.5 * atr
        expected_stop = min(max(max(lows_below), lo), hi)  # clamp
        expected_target = min(highs_above)
        expected_rr = round((expected_target - entry) / (entry - expected_stop), 2)

        rr, meta = compute_rr(df, entry, atr_k_floor=1.5, atr_k_cap=3.0, atr_period=14)
        assert meta["stop"] == pytest.approx(expected_stop)
        assert meta["target"] == pytest.approx(expected_target)
        assert rr == expected_rr

    def test_far_swing_capped_to_atr_cap(self) -> None:
        """수직급등주 모사 — 스윙저점이 cap 보다 멀면 risk 가 cap×ATR 로 제한(폭발 방지)."""
        df = _zigzag_df()
        entry = 110.0
        atr = _atr(df, 14)
        # 스윙저점(~90)이 cap(110-3×ATR)보다 멀다고 가정 → stop 은 cap 가격으로 제한
        rr, meta = compute_rr(df, entry, atr_k_floor=1.5, atr_k_cap=3.0)
        # risk 는 절대 cap×ATR 를 넘지 않는다
        assert (entry - meta["stop"]) <= 3.0 * atr + 1e-6
        # 동시에 floor×ATR 미만으로 타이트하지도 않다
        assert (entry - meta["stop"]) >= 1.5 * atr - 1e-6

    def test_atr_band_when_no_swings(self) -> None:
        """짧은 df = 스윙 없음 → 손절은 floor risk, 목표는 52주 고가 fallback."""
        df = _df([100.0, 101.0, 99.0, 102.0, 100.0])
        entry = 100.0
        atr = _atr(df, 14)
        rr, meta = compute_rr(df, entry, fallback_high=130.0, atr_k_floor=1.5, atr_k_cap=3.0)
        assert meta["stop"] == pytest.approx(entry - 1.5 * atr)
        assert meta["target"] == 130.0
        assert rr == round((130.0 - entry) / (entry - (entry - 1.5 * atr)), 2)

    def test_new_high_no_target_none(self) -> None:
        """신고가권(목표 저항 부재) → rr None + 정직한 사유."""
        df = _df([100.0, 101.0, 99.0, 102.0, 100.0])
        rr, meta = compute_rr(df, 100.0, fallback_high=90.0)  # fallback 이 진입 아래
        assert rr is None
        assert "목표" in (meta["reason"] or "")

    def test_no_price_or_empty_none(self) -> None:
        assert compute_rr(_df([100.0, 101.0]), None)[0] is None
        assert compute_rr(pd.DataFrame(), 100.0)[0] is None

    def test_deterministic(self) -> None:
        df = _zigzag_df()
        a = compute_rr(df, 110.0)
        b = compute_rr(df, 110.0)
        assert a[0] == b[0]
        assert a[1]["stop"] == b[1]["stop"]
