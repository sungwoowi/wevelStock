"""INFRA-SNAPSHOT-EXTEND-001 — render_snapshot_md 9~11 섹션 정합 5 케이스.

market-snapshot-md-v1 contract 검증.

1. 9 섹션 (시장매크로) 정합 — KOSPI/KOSDAQ 4축 풀세트 출력
2. 10 섹션 (섹터 RS) 정합 — 14 섹터 표 + rs_score
3. 11 섹션 (5주체 60일) 정합 — 양 시장 + agreement_score
4. 신규 필드 빈 dict / 빈 list 시 graceful skip (해당 섹션 헤더 자체 없음)
5. 11 섹션 모두 정상 발행 시 본 분석가 사용 지침 + extend 섹션 누적
"""
from __future__ import annotations

import time

import pytest

from collectors.snapshot import MarketSnapshot, render_snapshot_md


def _empty_snapshot(**overrides) -> MarketSnapshot:
    base = dict(
        fetched_at=time.time(),
        fetched_at_iso="2026-05-21T18:00:00+09:00",
        overnight={}, fear_greed={}, kr_indices={}, kr_supply={},
        kr_futures_supply={}, kr_sectors={}, kr_leading={},
    )
    base.update(overrides)
    return MarketSnapshot(**base)


# ---------------------------------------------------------------------------
# 1. 9 섹션 (시장매크로 4축)
# ---------------------------------------------------------------------------


def test_section_9_market_macro_full() -> None:
    macro = {
        "KOSPI": {
            "date": "2026-05-21", "index_close": 2700.0,
            "ma_36m": 2500.0, "ma_60m": 2400.0, "position": "above_both",
            "ma_20d": 2680.0, "ma_60d": 2650.0,
            "ma20_slope_pct_5d": 1.2, "ma60_slope_pct_20d": 0.8, "trend": "uptrend",
            "advancing": 500, "declining": 350, "unchanged": 100, "breadth_ratio": 0.588,
            "is_distribution_day": False, "change_pct": 0.5, "volume_change_pct": 2.0,
            "distribution_count_25d": 2,
        },
        "KOSDAQ": {
            "date": "2026-05-21", "index_close": 850.0,
            "ma_36m": 840.0, "ma_60m": 820.0, "position": "above_both",
            "ma_20d": 845.0, "ma_60d": 835.0,
            "ma20_slope_pct_5d": 0.3, "ma60_slope_pct_20d": 0.1, "trend": "uptrend",
            "advancing": 800, "declining": 600, "unchanged": 200, "breadth_ratio": 0.571,
            "is_distribution_day": False, "change_pct": 0.2, "volume_change_pct": 1.5,
            "distribution_count_25d": 1,
        },
    }
    md = render_snapshot_md(_empty_snapshot(market_macro=macro))
    assert "### 시장 매크로 통계" in md
    assert "#### KOSPI" in md and "#### KOSDAQ" in md
    assert "above_both" in md
    assert "uptrend" in md
    assert "Distribution Day (25일): **2**" in md   # KOSPI
    assert "Distribution Day (25일): **1**" in md   # KOSDAQ
    # 4+ kill switch 임계 미발동 → ⚠ 라벨 없음
    assert "kill switch 임계" not in md


def test_section_9_distribution_kill_switch_warn() -> None:
    macro = {
        "KOSPI": {
            "index_close": 2500.0, "position": "below_both", "trend": "downtrend",
            "ma_20d": None, "ma_60d": None, "ma20_slope_pct_5d": None,
            "ma60_slope_pct_20d": None, "ma_36m": None, "ma_60m": None,
            "advancing": 200, "declining": 700, "unchanged": 100, "breadth_ratio": 0.22,
            "is_distribution_day": True, "change_pct": -0.8, "volume_change_pct": 15.0,
            "distribution_count_25d": 5,    # 4+ kill switch
        },
    }
    md = render_snapshot_md(_empty_snapshot(market_macro=macro))
    assert "Distribution Day (25일): **5**" in md
    assert "kill switch 임계" in md


# ---------------------------------------------------------------------------
# 2. 10 섹션 (섹터 RS)
# ---------------------------------------------------------------------------


def test_section_10_sector_rs() -> None:
    sector_rs = [
        {"sector": "AI반도체", "etf_ticker": "394670", "rs_score": 8.5,
         "return_60d": 12.0, "kospi_return_60d": 5.0, "rs_ratio": 7.0},
        {"sector": "조선TOP10", "etf_ticker": "466920", "rs_score": 7.2,
         "return_60d": 9.4, "kospi_return_60d": 5.0, "rs_ratio": 4.4},
    ]
    md = render_snapshot_md(_empty_snapshot(sector_rs=sector_rs))
    assert "### 섹터 RS" in md
    assert "AI반도체 (394670)" in md
    assert "8.50" in md            # rs_score
    assert "조선TOP10 (466920)" in md
    assert "+12.00%" in md         # 60일 수익률 형식


# ---------------------------------------------------------------------------
# 3. 11 섹션 (5주체 60일)
# ---------------------------------------------------------------------------


def test_section_11_supply_60d() -> None:
    supply_60d = {
        "KOSPI": {
            "actual_days": 60,
            "foreign_net_60d": 842_000, "institution_net_60d": -215_000,
            "individual_net_60d": -584_000, "financial_inv_net_60d": -120_000,
            "pension_net_60d": 77_000, "agreement_score_60d": 4.0,
        },
        "KOSDAQ": {
            "actual_days": 58,
            "foreign_net_60d": -183_000, "institution_net_60d": 42_000,
            "individual_net_60d": 184_000, "financial_inv_net_60d": -18_000,
            "pension_net_60d": -25_000, "agreement_score_60d": 3.0,
        },
    }
    md = render_snapshot_md(_empty_snapshot(kr_supply_60d=supply_60d))
    assert "### 5주체 수급 60일 누적" in md
    assert "KOSPI (실측 60일)" in md
    assert "KOSDAQ (실측 58일)" in md
    assert "부호 일치도 **4.0/10**" in md
    assert "부호 일치도 **3.0/10**" in md


# ---------------------------------------------------------------------------
# 4. 신규 필드 빈 시 graceful skip (섹션 헤더 자체 없음)
# ---------------------------------------------------------------------------


def test_empty_extend_fields_skip_sections() -> None:
    md = render_snapshot_md(_empty_snapshot())
    # 신규 3 섹션 헤더 자체 없음 (빈 dict / list 라 graceful skip)
    assert "### 시장 매크로 통계" not in md
    assert "### 섹터 RS" not in md
    assert "### 5주체 수급 60일" not in md
    assert "본 분석가 사용 지침" not in md
    # 기존 1~8 섹션은 (mocked snapshot 이라 데이터 없지만 헤더는 존재)
    assert "### 한국 지수" in md


# ---------------------------------------------------------------------------
# 5. 11 섹션 모두 정상 발행 시 사용 지침 누적
# ---------------------------------------------------------------------------


def test_full_extend_includes_guidelines() -> None:
    macro = {"KOSPI": {"index_close": 2700.0, "position": "above_both", "trend": "uptrend",
                       "ma_36m": 2500.0, "ma_60m": 2400.0, "ma_20d": 2680.0, "ma_60d": 2650.0,
                       "ma20_slope_pct_5d": 1.2, "ma60_slope_pct_20d": 0.8,
                       "advancing": 500, "declining": 350, "unchanged": 100, "breadth_ratio": 0.588,
                       "is_distribution_day": False, "distribution_count_25d": 2}}
    sector_rs = [{"sector": "AI반도체", "etf_ticker": "394670", "rs_score": 8.0,
                  "return_60d": 10.0, "kospi_return_60d": 4.0, "rs_ratio": 6.0}]
    supply_60d = {"KOSPI": {"actual_days": 60, "foreign_net_60d": 100, "institution_net_60d": -50,
                            "individual_net_60d": -40, "financial_inv_net_60d": -10,
                            "pension_net_60d": 0, "agreement_score_60d": 5.0}}
    md = render_snapshot_md(_empty_snapshot(
        market_macro=macro, sector_rs=sector_rs, kr_supply_60d=supply_60d,
    ))
    assert "본 분석가 사용 지침" in md
    assert "market_state_analyzer" in md
    assert "stock_picker" in md
    assert "flow_analyzer" in md
