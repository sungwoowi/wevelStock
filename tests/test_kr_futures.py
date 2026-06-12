"""INFRA-MARKET-ASSETS-002 — KOSPI200 야간선물 KIS 실선물 1순위 폴백 체인.

KIS 실선물(env 심볼) → CME KM=F → EWY ETF 대용. 외부 실호출 금지 — mock.
"""
from __future__ import annotations

import pytest

import collectors.kr_futures as krf


@pytest.mark.asyncio
async def test_kis_primary_when_symbol_set(monkeypatch):
    """env 심볼 설정 + KIS 성공 → KIS 실선물 우선 (yfinance 호출 안 함)."""
    monkeypatch.setenv("KIS_KOSPI200_FUTURES_SYMBOL", "101000")

    class _FakeKIS:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def index_futures_price(self, symbol):
            return {"symbol": symbol, "price": 1299.85, "change": 63.8,
                    "change_pct": 5.16, "source": "kis_futures"}

    monkeypatch.setattr("connectors.kis.KISClient", _FakeKIS)

    def _boom(symbol):
        raise AssertionError("yfinance should not be called when KIS succeeds")

    monkeypatch.setattr(krf, "_fetch_sync", _boom)

    out = await krf.fetch_night_futures()
    nf = out["kospi200_cme_night"]
    assert nf["source"] == "kis"
    assert nf["source_kr"] == "실선물"
    assert nf["change_pct"] == 5.16
    assert nf["label_kr"] == "코스피200 선물"


@pytest.mark.asyncio
async def test_fallback_to_ewy_when_no_symbol(monkeypatch):
    """env 심볼 미설정 → KIS skip → KM=F 실패 → EWY 대용 (대용임을 명시)."""
    monkeypatch.delenv("KIS_KOSPI200_FUTURES_SYMBOL", raising=False)

    def _fake_sync(symbol):
        if symbol == krf.PRIMARY_SYMBOL:  # KM=F → 미제공
            return {"symbol": symbol, "error": "no history"}
        return {"symbol": symbol, "price": 60.0, "previous_close": 59.0, "change_pct": 1.69}

    monkeypatch.setattr(krf, "_fetch_sync", _fake_sync)

    out = await krf.fetch_night_futures()
    nf = out["kospi200_cme_night"]
    assert nf["source"] == "EWY"
    assert "대용" in nf["source_kr"]
    assert "대용" in nf["label_kr"]


@pytest.mark.asyncio
async def test_kis_error_falls_through(monkeypatch):
    """KIS 가 error 반환 → 폴백 체인으로 강등 (막지 않음)."""
    monkeypatch.setenv("KIS_KOSPI200_FUTURES_SYMBOL", "101000")

    class _FakeKIS:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def index_futures_price(self, symbol):
            return {"error": "EGW00201 권한없음", "symbol": symbol}

    monkeypatch.setattr("connectors.kis.KISClient", _FakeKIS)
    monkeypatch.setattr(
        krf, "_fetch_sync",
        lambda s: {"symbol": s, "price": 60.0, "previous_close": 59.0, "change_pct": 1.69},
    )

    out = await krf.fetch_night_futures()
    # KM=F 가 성공 처리됨 (mock 이 error 없이 반환) → source=KM=F
    assert out["kospi200_cme_night"]["source"] in ("KM=F", "EWY")
