"""관심종목 큐레이션 테스트 — 순수 floor 게이트(리스트별 차등) + curate_groups."""
from __future__ import annotations

import pytest

from collectors import universe_curation as uc
from collectors.universe_curation import CurationConfig, curation_config_from_dict, passes_quality_floor

_CFG = CurationConfig()


def _ok(**over):
    base = dict(
        list_type="trade_value", change_pct=3.0, trade_amount=5.0e11,
        market_cap=1.0e12, ma_aligned=True, cfg=_CFG,
    )
    base.update(over)
    return passes_quality_floor(**base)


def test_passes_clean_large_cap():
    assert _ok() is True


def test_limit_up_included_by_default():
    assert _ok(change_pct=29.9) is True  # 기본 max_change_pct=None → 상한가 포함(2026-06-16)


def test_max_change_pct_caps_when_set():
    cfg = CurationConfig(max_change_pct=20.0)
    assert _ok(change_pct=29.9, cfg=cfg) is False  # 캡 지정 시 상한가 제외


def test_rejects_below_trade_amount():
    assert _ok(trade_amount=5.0e9) is False  # 50억 < 100억


def test_rejects_below_market_cap_trade_value():
    assert _ok(market_cap=3.0e11) is False  # 3000억 < 5000억 (거래대금 리스트)


def test_volume_bull_allows_mid_cap():
    # 거래량 양봉은 시총 1000억이면 통과 (중소형 모멘텀 허용).
    assert passes_quality_floor(
        list_type="volume_bull", change_pct=8.0, trade_amount=2.0e10,
        market_cap=1.5e11, ma_aligned=True, cfg=_CFG,
    ) is True
    # 같은 종목이 거래대금 리스트 기준(5000억)으론 탈락.
    assert passes_quality_floor(
        list_type="trade_value", change_pct=8.0, trade_amount=2.0e10,
        market_cap=1.5e11, ma_aligned=True, cfg=_CFG,
    ) is False


def test_rejects_dead_chart_ma_not_aligned():
    assert _ok(ma_aligned=False) is False  # 정배열 깨짐(죽은 차트)


def test_none_market_cap_skips_floor():
    assert _ok(market_cap=None) is True  # 시총 결측 → best-effort skip


def test_none_ma_aligned_passes():
    assert _ok(ma_aligned=None) is True  # 미산출 → 과필터 회피(통과)


def test_config_from_dict_overrides():
    cfg = curation_config_from_dict({"vb_min_market_cap": 2.0e11, "enabled": False})
    assert cfg.vb_min_market_cap == 2.0e11
    assert cfg.enabled is False
    assert cfg.tv_min_market_cap == CurationConfig().tv_min_market_cap


def test_curate_groups_filters(monkeypatch):
    # load_ohlcv → 정배열 True·컨셉 leader 가정(_chart_summary monkeypatch). 거래대금 floor 로만 가른다.
    monkeypatch.setattr(uc, "_chart_summary", lambda ohlcv: (True, "leader"))
    monkeypatch.setattr("collectors.charts.load_ohlcv_from_db", lambda *a, **k: object())
    grouped = {
        "kospi": [
            {"ticker": "005930", "change_pct": 2.0, "trade_amount": 9.0e12},  # 통과
            {"ticker": "000001", "change_pct": 2.0, "trade_amount": 1.0e9},   # 거래대금 미달
        ],
        "kosdaq": [],
    }
    out = uc.curate_groups(grouped, list_type="trade_value")
    assert [i["ticker"] for i in out["kospi"]] == ["005930"]


def test_curate_groups_disabled_passthrough(monkeypatch):
    cfg = CurationConfig(enabled=False)
    grouped = {"kospi": [{"ticker": "x", "trade_amount": 1}], "kosdaq": []}
    assert uc.curate_groups(grouped, list_type="trade_value", cfg=cfg) == grouped
