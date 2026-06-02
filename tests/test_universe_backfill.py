"""universe 백필 (2026-06-02) — leading 종목 일봉 상시 적재 선정 로직 검증.

A. fetch_universe_tickers — 거래대금 상위 평탄화 + 중복 제거.
B. _select_refresh_tickers — seed + 당일 universe 항상 포함, 누적 DB 는 fetched_at 최신순 cap,
   universe fetch 실패 시 graceful (seed/DB refresh 는 진행).
"""
from __future__ import annotations

import pytest


class _FakeDB:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def fetch_all(self, sql: str, *args) -> list[dict]:  # noqa: ANN002
        return self._rows


# ============================================================
# A. fetch_universe_tickers
# ============================================================


async def test_fetch_universe_flattens_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    from collectors import screening as sc

    sc.reload_screening_config()

    async def fake_leading(kis, *, kospi_limit, kosdaq_limit):  # noqa: ANN001, ANN202
        assert kospi_limit == 30 and kosdaq_limit == 20  # config universe 값
        return {
            "kospi": [{"ticker": "005930"}, {"ticker": "000660"}],
            "kosdaq": [{"ticker": "247540"}, {"ticker": "005930"}],  # 중복
        }

    monkeypatch.setattr(
        "collectors.kr_leading_stocks.fetch_kr_leading_stocks", fake_leading
    )
    result = await sc.fetch_universe_tickers(kis=None)
    # 순서 보존 중복 제거 (005930 두 번째 제거)
    assert result == ["005930", "000660", "247540"]


async def test_fetch_universe_drops_empty_tickers(monkeypatch: pytest.MonkeyPatch) -> None:
    from collectors import screening as sc

    sc.reload_screening_config()

    async def fake_leading(kis, *, kospi_limit, kosdaq_limit):  # noqa: ANN001, ANN202
        return {"kospi": [{"ticker": ""}, {"ticker": "005930"}], "kosdaq": [{}]}

    monkeypatch.setattr(
        "collectors.kr_leading_stocks.fetch_kr_leading_stocks", fake_leading
    )
    assert await sc.fetch_universe_tickers(kis=None) == ["005930"]


# ============================================================
# B. _select_refresh_tickers
# ============================================================


async def test_select_caps_optional_by_fetched_at(monkeypatch: pytest.MonkeyPatch) -> None:
    from collectors import charts as ch
    from collectors import screening as sc

    monkeypatch.setattr(ch, "_seed_tickers", lambda: ["SEED1"])

    async def fake_uni(kis=None):  # noqa: ANN001, ANN202
        return ["UNI1", "UNI2"]

    monkeypatch.setattr(sc, "fetch_universe_tickers", fake_uni)
    monkeypatch.setattr(sc, "get_universe_max_tickers", lambda: 4)

    db = _FakeDB([
        {"ticker": "OLD", "last_fetched": "2026-01-01T18:00:00"},
        {"ticker": "NEW", "last_fetched": "2026-06-01T18:00:00"},
        {"ticker": "MID", "last_fetched": "2026-03-01T18:00:00"},
    ])
    tickers, meta = await ch._select_refresh_tickers(db, kis=None)

    # must = SEED1 + UNI1 + UNI2 (3). max 4 → room 1 → 최신 optional(NEW) 1개만 유지
    assert {"SEED1", "UNI1", "UNI2", "NEW"} == set(tickers)
    assert "OLD" not in tickers and "MID" not in tickers
    assert meta["dropped_optional"] == 2
    assert meta["kept_optional"] == 1
    assert meta["universe"] == 2
    assert meta["universe_error"] is None


async def test_select_universe_fetch_error_is_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    from collectors import charts as ch
    from collectors import screening as sc

    monkeypatch.setattr(ch, "_seed_tickers", lambda: ["SEED1"])

    async def fake_uni_err(kis=None):  # noqa: ANN001, ANN202
        raise RuntimeError("kis down")

    monkeypatch.setattr(sc, "fetch_universe_tickers", fake_uni_err)
    monkeypatch.setattr(sc, "get_universe_max_tickers", lambda: 100)

    db = _FakeDB([{"ticker": "ACC", "last_fetched": "2026-06-01T18:00:00"}])
    tickers, meta = await ch._select_refresh_tickers(db, kis=None)

    # leading 실패해도 seed + 누적 DB 는 refresh 대상
    assert "SEED1" in tickers and "ACC" in tickers
    assert meta["universe"] == 0
    assert meta["universe_error"] is not None and "kis down" in meta["universe_error"]


async def test_select_seed_always_included_even_over_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    from collectors import charts as ch
    from collectors import screening as sc

    monkeypatch.setattr(ch, "_seed_tickers", lambda: ["S1", "S2", "S3"])

    async def fake_uni(kis=None):  # noqa: ANN001, ANN202
        return ["U1", "U2"]

    monkeypatch.setattr(sc, "fetch_universe_tickers", fake_uni)
    monkeypatch.setattr(sc, "get_universe_max_tickers", lambda: 2)  # must(5) > cap

    db = _FakeDB([{"ticker": "ACC", "last_fetched": "2026-06-01T18:00:00"}])
    tickers, meta = await ch._select_refresh_tickers(db, kis=None)

    # seed + universe 는 cap 보다 많아도 전부 포함 (room=0 → optional 전부 제외)
    assert {"S1", "S2", "S3", "U1", "U2"} == set(tickers)
    assert "ACC" not in tickers
    assert meta["kept_optional"] == 0
