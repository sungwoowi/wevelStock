"""GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) G1 — 벤치마크 지수 보유기간 수익률 테스트."""
from __future__ import annotations

import pytest

from core.guidance.benchmark import (
    benchmark_return_pct,
    compute_benchmark_return,
    index_symbol,
)


def test_benchmark_return_pct_pure():
    assert benchmark_return_pct(100.0, 110.0) == pytest.approx(10.0)
    assert benchmark_return_pct(100.0, 92.0) == pytest.approx(-8.0)


def test_benchmark_return_pct_guards_zero_start():
    assert benchmark_return_pct(0.0, 110.0) is None


def test_index_symbol_by_market():
    assert index_symbol("KR") == "^KS11"   # 코스피
    assert index_symbol("US") == "^GSPC"   # S&P500 (config 기본)


def test_compute_benchmark_return_with_injected_fetch():
    # 체결일~청산일 지수 100→112 → +12%
    fetch = lambda sym, s, e: (100.0, 112.0)
    out = compute_benchmark_return("KR", "2026-06-01", "2026-06-30", fetch=fetch)
    assert out == pytest.approx(12.0)


def test_compute_benchmark_return_graceful_when_no_data():
    # 지수 데이터 부재 → None (추정 X, 채점서 제외)
    assert compute_benchmark_return("KR", "2026-06-01", "2026-06-30", fetch=lambda s, a, b: None) is None
