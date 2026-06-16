"""TRADE-PLAN-LIFECYCLE-001 B-MS1 — 결정론 가격대 메뉴 (순수 함수) 테스트.

핵심 원칙: 결정론 = 객관 가격대 *계산기*(후보 메뉴), 결정자 아님. LLM 이 선택·조합.
이 모듈은 I/O·LLM 0 — 입력만으로 결정. 절대 가드레일(오닐 −7%·종가기준)만 결정론 강제.
"""
from __future__ import annotations

import pandas as pd
import pytest

from core.signal.trade_plan_menu import (
    TradePlanConfig,
    TradePlanInputs,
    build_trade_plan_menu,
    clamp_stop_to_oneill,
    is_menu_bound,
    render_trade_plan_menu_md,
    trade_plan_config_from_dict,
    trade_plan_inputs_from_ohlcv,
)


# ---------------------------------------------------------------------------
# build_trade_plan_menu — 후보 메뉴 산출
# ---------------------------------------------------------------------------


def _full_inputs() -> TradePlanInputs:
    # entry=10,000. 스윙저점 9,500(가까움)·9,000(멈). 고점 11,000·12,000. ATR=200.
    return TradePlanInputs(
        ticker="000660",
        current_close=10_000.0,
        swing_lows=[9_500.0, 9_000.0],
        swing_highs=[11_000.0, 12_000.0],
        ma20=9_800.0,
        ma60=9_300.0,
        ma120=8_700.0,
        atr=200.0,
        wk52_high=13_000.0,
        wk52_low=7_000.0,
        anchor_b=12_500.0,
        extension_score=8.0,  # 저과열 → front-load 분할
    )


def test_stop_candidates_labeled_menu():
    """손절 후보가 라벨된 메뉴로 다단 산출 (선택 안 함 — 메뉴)."""
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig())
    labels = {c.label for c in menu.stop_candidates}
    # 스윙저점·ATR·ma60·ma120·오닐 −7% 후보 모두 존재 (entry 아래).
    assert any("스윙" in l for l in labels)
    assert any("ATR" in l for l in labels)
    assert any("60" in l for l in labels)
    assert any("7%" in l or "오닐" in l for l in labels)
    # 모든 손절 후보는 진입가 아래.
    assert all(c.price < 10_000.0 for c in menu.stop_candidates)


def test_default_stop_within_atr_band():
    """기본 손절 = 스윙저점을 [1.5, 3.0]×ATR 밴드로 clamp (compute_rr 정합)."""
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig())
    # entry=10000, atr=200 → hi(tight)=9700, lo(wide)=9400. swing_low(가까움)=9500 ∈ [9400,9700].
    assert menu.default_stop == pytest.approx(9_500.0)


def test_oneill_floor_clamps_loose_stop():
    """손절이 −7%보다 느슨하면(스윙·ATR 손절이 너무 멈) 오닐 floor(entry×0.93)로 끌어올림."""
    inp = _full_inputs()
    inp.swing_lows = [8_000.0]   # 20% 아래 — 너무 멈
    inp.atr = 1_500.0            # 큰 변동성 → ATR 밴드도 −7% 초과
    menu = build_trade_plan_menu(inp, TradePlanConfig())
    # 오닐 floor = 10000 × 0.93 = 9300. default_stop 은 그보다 낮을 수 없음.
    assert menu.oneill_floor == pytest.approx(9_300.0)
    assert menu.default_stop >= 9_300.0 - 1e-6


def test_buy_ladder_below_entry_and_above_stop():
    """분할매수 사다리 = entry→stop 보간 (1차=entry, 깊은 차수도 stop 위 — 물타기 차단)."""
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig())
    assert len(menu.buy_ladder) == 3
    assert menu.buy_ladder[0].price == pytest.approx(10_000.0)  # 1차 = 진입가
    # 모든 차수 > default_stop.
    assert all(leg.price > menu.default_stop for leg in menu.buy_ladder)
    # 차수 가격 단조 감소.
    prices = [leg.price for leg in menu.buy_ladder]
    assert prices == sorted(prices, reverse=True)


def test_buy_ladder_ratios_from_extension():
    """분할 비중 = 과열도 기반 (저과열 8.0 → front-load 0.6/0.3/0.1)."""
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig())
    ratios = [leg.ratio for leg in menu.buy_ladder]
    assert ratios[0] > ratios[-1]  # front-load
    assert sum(ratios) == pytest.approx(1.0)


def test_support_resistance_multi_level_sorted():
    """다단 지지/저항 — 지지는 가까운(높은)順, 저항은 가까운(낮은)順."""
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig())
    sup = [lv.price for lv in menu.support_levels]
    res = [lv.price for lv in menu.resistance_levels]
    assert sup == sorted(sup, reverse=True)   # 가까운 지지 먼저
    assert res == sorted(res)                  # 가까운 저항 먼저
    assert all(p < 10_000 for p in sup)
    assert all(p > 10_000 for p in res)


def test_target_candidates_include_wave_and_52w():
    """목표 후보 = 인근 고점 + 파동 목표(anchor B) + 52주 고가 (단일 아님 = 메뉴)."""
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig())
    prices = [t.price for t in menu.target_candidates]
    assert 12_500.0 in prices or any(abs(p - 12_500.0) < 1e-6 for p in prices)  # anchor B
    assert any(abs(p - 13_000.0) < 1e-6 for p in prices)  # 52w high
    assert all(p > 10_000 for p in prices)


def test_sell_ladder_ratios_sum_to_one():
    """분할매도 사다리 = 목표 후보 기반, 비중 합 = 1."""
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig())
    assert len(menu.sell_ladder) >= 1
    assert sum(leg.ratio for leg in menu.sell_ladder) == pytest.approx(1.0)
    # 매도 사다리는 모두 진입 위.
    assert all(leg.price > 10_000 for leg in menu.sell_ladder)


def test_stale_swing_low_excluded():
    """수년전 스윙저점(진입 대비 25% 초과)은 손절·지지 메뉴에서 제외 (라이브 808K vs 2.36M 버그)."""
    inp = _full_inputs()
    inp.swing_lows = [808_000.0]  # entry 10,000 대비 92% 아래 = stale
    menu = build_trade_plan_menu(inp, TradePlanConfig())
    # stale 저점은 손절 후보·지지에 없음.
    assert all(c.price != 808_000.0 for c in menu.stop_candidates)
    assert all(lv.price != 808_000.0 for lv in menu.support_levels)
    # 인근 스윙저점 부재 → 기본 손절은 ATR/오닐로 폴백(크래시 없음).
    assert menu.default_stop is not None


def test_duplicate_levels_deduped():
    """스윙고점 == 52주 고가면 저항·목표·분할매도가 동일가 중복을 dedup (라이브 2,407,000 중복 버그)."""
    inp = _full_inputs()
    inp.swing_highs = [11_000.0]
    inp.wk52_high = 11_000.0   # 스윙고점과 동일가
    menu = build_trade_plan_menu(inp, TradePlanConfig())
    res_prices = [lv.price for lv in menu.resistance_levels]
    assert res_prices.count(11_000.0) == 1  # 중복 제거
    # 분할매도 사다리에 동일가 두 leg 없음.
    sell_prices = [leg.price for leg in menu.sell_ladder]
    assert len(sell_prices) == len(set(sell_prices))


def test_graceful_empty_inputs():
    """current_close 부재 → 크래시 없이 빈 메뉴 + reasons (결측 graceful)."""
    menu = build_trade_plan_menu(TradePlanInputs(ticker="X"), TradePlanConfig())
    assert menu.default_stop is None
    assert menu.buy_ladder == []
    assert menu.reasons  # 사유 기록
    # 직렬화 가능.
    d = menu.to_dict()
    assert d["ticker"] == "X"
    assert d["default_stop"] is None


def test_disabled_config_returns_empty():
    menu = build_trade_plan_menu(_full_inputs(), TradePlanConfig(enabled=False))
    assert menu.buy_ladder == []
    assert "disabled" in " ".join(menu.reasons).lower()


# ---------------------------------------------------------------------------
# 절대 가드레일 — clamp_stop_to_oneill / is_menu_bound
# ---------------------------------------------------------------------------


def test_clamp_stop_to_oneill():
    cfg = TradePlanConfig()
    # 손절이 −10%(9000) → −7% floor(9300)로 끌어올림 + clamped=True.
    clamped, was = clamp_stop_to_oneill(10_000.0, 9_000.0, cfg)
    assert clamped == pytest.approx(9_300.0)
    assert was is True
    # 손절이 −5%(9500) → 그대로 (오닐 위반 아님).
    clamped2, was2 = clamp_stop_to_oneill(10_000.0, 9_500.0, cfg)
    assert clamped2 == pytest.approx(9_500.0)
    assert was2 is False


def test_is_menu_bound():
    cfg = TradePlanConfig(menu_bound_tol_pct=0.03)
    candidates = [9_500.0, 9_300.0, 11_000.0]
    assert is_menu_bound(9_480.0, candidates, cfg.menu_bound_tol_pct) is True   # 9500 인근
    assert is_menu_bound(8_000.0, candidates, cfg.menu_bound_tol_pct) is False  # 메뉴 밖 = 환각 의심


# ---------------------------------------------------------------------------
# 어댑터 — trade_plan_inputs_from_ohlcv (extract_swing/compute_indicators/_atr)
# ---------------------------------------------------------------------------


def _synthetic_ohlcv(n: int = 300) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    # 완만한 우상향 + 잔진동 (스윙·MA 산출 가능하도록).
    base = [10_000 + i * 5 + (300 if i % 20 < 10 else -300) for i in range(n)]
    close = pd.Series(base, index=idx, dtype=float)
    high = close + 150
    low = close - 150
    vol = pd.Series([1_000_000] * n, index=idx, dtype=float)
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close, "volume": vol})


def test_adapter_populates_facts_from_ohlcv():
    df = _synthetic_ohlcv()
    inp = trade_plan_inputs_from_ohlcv(df, ticker="TST", extension=6.0)
    assert inp.current_close is not None
    assert inp.ma20 is not None and inp.ma60 is not None and inp.ma120 is not None
    assert inp.atr is not None and inp.atr > 0
    assert inp.wk52_high is not None and inp.wk52_low is not None
    # 어댑터→메뉴 end-to-end 크래시 없음.
    menu = build_trade_plan_menu(inp, TradePlanConfig())
    assert menu.entry_hint == pytest.approx(inp.current_close)


def test_adapter_graceful_empty_df():
    inp = trade_plan_inputs_from_ohlcv(pd.DataFrame(), ticker="EMPTY")
    assert inp.current_close is None
    menu = build_trade_plan_menu(inp, TradePlanConfig())
    assert menu.default_stop is None  # 크래시 없음


# ---------------------------------------------------------------------------
# render — LLM 프롬프트용 마크다운
# ---------------------------------------------------------------------------


def test_render_contains_key_facts():
    md = render_trade_plan_menu_md(build_trade_plan_menu(_full_inputs(), TradePlanConfig()))
    assert "메뉴" in md
    assert "9,500" in md or "9500" in md  # 스윙저점 후보 노출
    assert "7%" in md                       # 오닐 절대 룰
    assert "종가" in md                      # 종가 기준 명시
    # 선택·조합 지시 (결정자 아님).
    assert "선택" in md or "조합" in md


def test_render_empty_menu_safe():
    md = render_trade_plan_menu_md(build_trade_plan_menu(TradePlanInputs(ticker="X"), TradePlanConfig()))
    assert isinstance(md, str)  # 빈 메뉴도 크래시 없는 문자열


# ---------------------------------------------------------------------------
# config — graceful 매퍼
# ---------------------------------------------------------------------------


def test_config_from_dict_graceful():
    cfg = trade_plan_config_from_dict({"oneill_max_loss_pct": 0.05, "bogus": "x", "atr_period": "9"})
    assert cfg.oneill_max_loss_pct == pytest.approx(0.05)
    assert cfg.atr_period == 9          # 문자열 → int 변환
    assert cfg.enabled is True          # 미지정 default
    # None → 전부 default.
    assert trade_plan_config_from_dict(None).oneill_max_loss_pct == pytest.approx(0.07)
