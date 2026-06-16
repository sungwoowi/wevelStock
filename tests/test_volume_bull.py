"""거래량 양봉 상위 선별 테스트 — 순수 _select_volume_bull (등락률·양봉·cap)."""
from __future__ import annotations

from collectors.volume_bull import _select_volume_bull


def _c(ticker: str, change_pct: float, rank: int) -> dict:
    return {"ticker": ticker, "change_pct": change_pct, "rank": rank, "name": ticker}


def test_select_keeps_bullish_above_threshold():
    cand = [_c("A", 5.0, 1), _c("B", 4.0, 2)]
    oc = {"A": (100.0, 105.0), "B": (100.0, 104.0)}  # 둘 다 양봉
    out = _select_volume_bull(cand, oc)
    assert {c["ticker"] for c in out} == {"A", "B"}


def test_select_excludes_below_change_pct():
    cand = [_c("A", 2.5, 1)]  # 3% 미만
    out = _select_volume_bull(cand, {"A": (100.0, 103.0)}, min_change_pct=3.0)
    assert out == []


def test_select_excludes_non_bullish():
    # 등락률은 ≥3 이나 종가<시가(음봉) → 제외 (전일 종가 대비 +3% 갭하락 후 밀린 형태).
    cand = [_c("A", 3.5, 1)]
    out = _select_volume_bull(cand, {"A": (110.0, 105.0)})
    assert out == []


def test_select_excludes_missing_open_close():
    cand = [_c("A", 5.0, 1), _c("B", 5.0, 2)]
    out = _select_volume_bull(cand, {"A": (100.0, 105.0)})  # B 시가/종가 결측
    assert {c["ticker"] for c in out} == {"A"}


def test_select_respects_limit_and_order():
    cand = [_c("A", 5.0, 1), _c("B", 6.0, 2), _c("C", 4.0, 3)]
    oc = {t: (100.0, 106.0) for t in ("A", "B", "C")}
    out = _select_volume_bull(cand, oc, limit=2)
    assert [c["ticker"] for c in out] == ["A", "B"]  # 거래량(원순서=rank) 유지, 상위 2
