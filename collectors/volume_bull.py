"""거래량 양봉 상위 리스트 — 거래량 상위 ∩ 등락률≥3% ∩ 양봉(종가>시가).

관심종목 두 번째 큐레이션 리스트. `volume_rank(rank_type="volume")` 응답엔 시가가 없어
양봉(종가>시가) 판정에 시가 결합이 필요 → **하이브리드 신선도**:
  intraday=True  → KIS `stock_price` (당일 시가+현재가 실시간) — 장중 cadence(09:35/12:35/14:35).
  intraday=False → `chart_ohlcv` 최신 확정 일봉(close>open) — 18:05 EOD(네트워크 0, DB-first).

산출 형태 = {"kospi": [...], "kosdaq": [...]} (kr_leading_stocks 와 동일 → persist_universe_membership
(list_type='volume_bull') 직접 호환). 신규 테이블 0. 순수 선별부(_select_volume_bull)는 단위 테스트.
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger

log = get_logger(__name__)

_MIN_CHANGE_PCT = 3.0
_SCAN_LIMIT = 60  # 시장별 거래량 상위 스캔 폭 (등락률·양봉 필터 전)


def _select_volume_bull(
    candidates: list[dict[str, Any]],
    open_close: dict[str, tuple[float | None, float | None]],
    *,
    min_change_pct: float = _MIN_CHANGE_PCT,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """순수 — 등락률≥min AND 양봉(close>open) 후보만 거래량(원순서=rank) 상위 limit.

    open_close: {ticker: (open, close)}. 시가/종가 결측·0 이하 → 양봉 판정 불가로 제외(보수).
    candidates 는 거래량 순(volume_rank 반환 순서) 가정 — 그 순서 유지.
    """
    out: list[dict[str, Any]] = []
    for c in candidates:
        tk = (c.get("ticker") or "").strip()
        if not tk or (c.get("change_pct") or 0) < min_change_pct:
            continue
        oc = open_close.get(tk)
        if not oc:
            continue
        o, cl = oc
        if o and cl and o > 0 and cl > o:  # 양봉
            out.append(c)
            if len(out) >= limit:
                break
    return out


async def _open_close_intraday(
    kis: Any, tickers: list[str]
) -> dict[str, tuple[float | None, float | None, float | None]]:
    """장중 실시간 — stock_price 로 (시가, 현재가, 시총). rate-limit 은 KIS client 내부 throttle.

    시총(market_cap, 억 단위) 은 큐레이션 잡주 floor 용으로 함께 캡처.
    """
    out: dict[str, tuple[float | None, float | None, float | None]] = {}
    for tk in tickers:
        try:
            s = await kis.stock_price(tk)
            if not s.get("error"):
                # market_cap 은 KIS 가 억 단위 → 원 단위로 환산(floor 가 원 기준).
                cap = s.get("market_cap")
                cap_won = float(cap) * 1.0e8 if cap else None
                out[tk] = (float(s.get("open") or 0), float(s.get("price") or 0), cap_won)
        except Exception:  # noqa: BLE001 — 한 종목 실패가 리스트를 막지 않음
            continue
    return out


def _open_close_eod(tickers: list[str]) -> dict[str, tuple[float | None, float | None]]:
    """EOD — chart_ohlcv 최신 확정 일봉 (시가, 종가). 네트워크 0(DB-first)."""
    from collectors.charts import load_ohlcv_from_db

    out: dict[str, tuple[float | None, float | None]] = {}
    for tk in tickers:
        try:
            df = load_ohlcv_from_db(tk, limit=2)
            if df is not None and len(df):
                last = df.iloc[-1]
                out[tk] = (float(last["open"]), float(last["close"]))
        except Exception:  # noqa: BLE001
            continue
    return out


async def _fetch_inner(
    kis: Any, intraday: bool, limit: int, min_change_pct: float
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for scope in ("kospi", "kosdaq"):
        rows = await kis.volume_rank(limit=_SCAN_LIMIT, rank_type="volume", market_scope=scope)
        cand = [r for r in rows if (r.get("change_pct") or 0) >= min_change_pct]
        tickers = [(r.get("ticker") or "").strip() for r in cand if r.get("ticker")]
        if intraday:
            raw = await _open_close_intraday(kis, tickers)
            oc = {tk: (v[0], v[1]) for tk, v in raw.items()}
            caps = {tk: v[2] for tk, v in raw.items() if len(v) > 2}
        else:
            oc = _open_close_eod(tickers)
            caps = {}
        selected = _select_volume_bull(cand, oc, min_change_pct=min_change_pct, limit=limit)
        for it in selected:  # 시총 부착(큐레이션 floor용, 장중만 — EOD 는 None→skip)
            cap = caps.get(it.get("ticker"))
            if cap is not None:
                it["market_cap"] = cap
        result[scope] = selected
    return result


async def fetch_kr_volume_bull(
    kis: Any | None = None,
    *,
    intraday: bool,
    limit: int = 50,
    min_change_pct: float = _MIN_CHANGE_PCT,
) -> dict[str, Any]:
    """거래량 양봉 상위 리스트 → {"kospi": [...], "kosdaq": [...]}.

    각 항목 = volume_rank 항목(rank·ticker·name·change_pct·volume·trade_amount). intraday 플래그로
    양봉 시가 출처 분기. persist_universe_membership(list_type='volume_bull') 에 그대로 전달 가능.
    """
    if kis is None:
        from connectors.kis.client import KISClient

        async with KISClient() as own:
            res = await _fetch_inner(own, intraday, limit, min_change_pct)
    else:
        res = await _fetch_inner(kis, intraday, limit, min_change_pct)
    log.info(
        "kr_volume_bull_collected",
        kospi=len(res.get("kospi", [])), kosdaq=len(res.get("kosdaq", [])), intraday=intraday,
    )
    return res
