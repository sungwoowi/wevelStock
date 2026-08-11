"""숏 압력 수집 — 공매도 · 융자/대주 잔고 · 프로그램매매 (ADVISOR-CORE-001 M1-b).

사용자 요청: *"코스닥 호가가 얇아서 숏커버링이나 기관 매수세 나오면 강한 반등이 예상된다던지"*.
그 판단의 재료 중 **잔고·거래량 쪽**을 여기서 채운다(호가 두께는 장중 시계열이라 M1-d).

- **공매도**(일별 체결량·비중) = 숏 압력의 흐름
- **대주 잔고** = 빌려서 판 물량 → 되사야 할 물량 = **숏커버링 연료**
- **융자 잔고** = 빚내서 산 물량 → 하락 시 반대매매 압력
- **프로그램매매** = 지수 왜곡 요인 (차익 거래가 지수를 끌 때 종목 신호와 어긋남)

KRX STAT 계열은 Akamai 봇차단(2026-05-31 확인)이라 **KIS 로 받는다** — 2026-08-11 실호출
probe 로 4 엔드포인트 확인 후 배선. 저장은 `stock_supply_history` 컬럼 확장(가드 #11).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

# 공매도 시계열 조회 창 (일). 판세는 최근 추이만 보면 되고, 넓히면 콜 비용만 늘어난다.
_SHORT_WINDOW_DAYS = 14


def _yyyymmdd(iso: str) -> str:
    return iso.replace("-", "")


def _upsert_columns(ticker: str, day: str, values: dict[str, Any]) -> None:
    """(ticker, date) 행에 확장 컬럼만 병합. 기존 5주체 값은 건드리지 않는다.

    행이 없으면 NOT NULL 5주체는 0 으로 만들어 둔다 — 나중에 stock_supply collector 가
    같은 PK 로 채운다(ON CONFLICT REPLACE 라 충돌 없음).
    """
    if not values:
        return
    cols = list(values)
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO stock_supply_history "
            "(ticker, date, foreign_net, institution_net, individual_net, "
            " financial_inv_net, pension_net, source) VALUES (?,?,0,0,0,0,0,'kis') "
            "ON CONFLICT(ticker, date) DO NOTHING",
            (ticker, day),
        )
        conn.execute(
            f"UPDATE stock_supply_history SET {', '.join(f'{c} = ?' for c in cols)} "
            "WHERE ticker = ? AND date = ?",
            (*[values[c] for c in cols], ticker, day),
        )


async def collect_short_pressure(
    ticker: str,
    *,
    as_of: str,
    kis: Any | None = None,
) -> int:
    """종목 숏 압력 3축 수집 → `stock_supply_history` 확장 컬럼 upsert. 적재 행 수 반환.

    **축별 독립 graceful** — 하나가 죽어도 나머지는 적재된다(판세가 안 나가는 것보다 낫다).
    """
    if kis is None:
        from connectors.kis import KISClient

        async with KISClient() as own:
            return await collect_short_pressure(ticker, as_of=as_of, kis=own)

    start = _yyyymmdd(
        (date.fromisoformat(as_of) - timedelta(days=_SHORT_WINDOW_DAYS)).isoformat()
    )
    end = _yyyymmdd(as_of)

    async def _safe(coro: Any, axis: str) -> Any:
        try:
            return await coro
        except Exception as e:  # noqa: BLE001 — 한 축 실패가 나머지를 막지 않음
            log.warning("short_pressure_axis_failed", ticker=ticker, axis=axis, error=str(e))
            return None

    shorts, credits, program = await asyncio.gather(
        _safe(kis.daily_short_sale(ticker, start, end), "short"),
        _safe(kis.daily_credit_balance(ticker, end), "credit"),
        _safe(kis.program_trade_by_stock(ticker), "program"),
    )

    # 날짜별로 모은 뒤 한 번에 병합 — 같은 행에 여러 축이 붙을 때 UPDATE 중복 회피.
    by_day: dict[str, dict[str, Any]] = {}
    for r in shorts or []:
        d = r.get("date")
        if d:
            by_day.setdefault(d, {}).update({
                "short_volume": r.get("short_volume"),
                "short_ratio": r.get("short_ratio"),
                "short_cum_ratio": r.get("short_cum_ratio"),
            })
    for r in credits or []:
        d = r.get("date")
        if d:
            by_day.setdefault(d, {}).update({
                "loan_balance_qty": r.get("loan_balance_qty"),
                "short_balance_qty": r.get("short_balance_qty"),
            })
    if program:
        by_day.setdefault(as_of, {}).update({
            "program_net_qty": program.get("net_qty"),
            "program_net_amount": program.get("net_amount"),
        })

    count = 0
    for day, values in by_day.items():
        clean = {k: v for k, v in values.items() if v is not None}
        if not clean:
            continue
        _upsert_columns(ticker, day, clean)
        count += 1
    if count:
        log.info("short_pressure_collected", ticker=ticker, as_of=as_of, rows=count)
    return count


async def collect_short_pressure_many(
    tickers: list[str],
    *,
    as_of: str,
    concurrency: int = 3,
    kis: Any | None = None,
) -> int:
    """여러 종목 순회 수집 (bounded). KIS rate-limit 보호는 클라이언트가 담당."""
    if not tickers:
        return 0
    sem = asyncio.Semaphore(max(1, concurrency))

    async def _one(t: str) -> int:
        async with sem:
            try:
                return await collect_short_pressure(t, as_of=as_of, kis=kis)
            except Exception as e:  # noqa: BLE001 — 한 종목 실패가 배치를 막지 않음
                log.warning("short_pressure_ticker_failed", ticker=t, error=str(e))
                return 0

    if kis is None:
        from connectors.kis import KISClient

        async with KISClient() as own:
            return await collect_short_pressure_many(
                tickers, as_of=as_of, concurrency=concurrency, kis=own
            )
    return sum(await asyncio.gather(*[_one(t) for t in tickers]))


# ---------------------------------------------------------------------------
# 시장 집계 — 판세 입력 (종목별이 아니라 시장 전체 압력)
# ---------------------------------------------------------------------------


@dataclass
class ShortPressureSummary:
    """시장 단위 숏 압력 요약 — 판세 LLM 이 읽는 형태."""

    as_of: str
    covered_tickers: int = 0
    avg_short_ratio: float | None = None      # 평균 공매도 비중(%)
    max_short_ratio: float | None = None
    top_short_ticker: str | None = None
    total_short_balance: int | None = None    # 대주 잔고 합 — 숏커버링 연료
    short_balance_date: str | None = None     # 잔고 기준일 (T+2 결제라 거래일보다 뒤짐)
    short_balance_change: int | None = None   # 직전 잔고일 대비 증감 (음수 = 커버링 진행)
    total_program_net_amount: int | None = None  # 프로그램 순매수 합(백만원)


def _balance_snapshot(as_of: str) -> tuple[str | None, int | None, int | None]:
    """as_of 이하 **가장 최근 잔고일**의 대주 잔고 합 + 직전 잔고일 대비 증감.

    신용·대주 잔고는 T+2 결제 기준이라 거래일보다 며칠 뒤진다. 당일치를 요구하면 항상
    비어 보이므로 "최근 잔고"를 쓴다. 그리고 **수준보다 증감**이 신호다 —
    잔고가 줄면 숏커버링 진행, 늘면 숏 압력 축적.
    """
    db = get_db()
    days = db.fetch_all(
        "SELECT DISTINCT date FROM stock_supply_history "
        "WHERE date <= ? AND short_balance_qty IS NOT NULL ORDER BY date DESC LIMIT 2",
        (as_of,),
    )
    if not days:
        return None, None, None

    def _sum(day: str) -> int | None:
        r = db.fetch_one(
            "SELECT sum(short_balance_qty) AS s FROM stock_supply_history WHERE date = ?",
            (day,),
        )
        return int(r["s"]) if r and r["s"] is not None else None

    latest_day = str(days[0]["date"])
    latest = _sum(latest_day)
    prev = _sum(str(days[1]["date"])) if len(days) > 1 else None
    change = (latest - prev) if (latest is not None and prev is not None) else None
    return latest_day, latest, change


def summarize_short_pressure(as_of: str) -> ShortPressureSummary:
    """시장 집계 — 공매도는 당일, 잔고는 최근 결제일. 없으면 빈 요약(판세는 그래도 발행)."""
    row = get_db().fetch_one(
        "SELECT count(*) AS n, avg(short_ratio) AS avg_r, max(short_ratio) AS max_r, "
        "       sum(program_net_amount) AS sum_pg "
        "FROM stock_supply_history WHERE date = ? AND short_ratio IS NOT NULL",
        (as_of,),
    )
    s = ShortPressureSummary(as_of=as_of)
    s.short_balance_date, s.total_short_balance, s.short_balance_change = _balance_snapshot(as_of)
    if row is None or not row["n"]:
        return s
    s.covered_tickers = int(row["n"])
    s.avg_short_ratio = round(row["avg_r"], 2) if row["avg_r"] is not None else None
    s.max_short_ratio = round(row["max_r"], 2) if row["max_r"] is not None else None
    s.total_program_net_amount = int(row["sum_pg"]) if row["sum_pg"] is not None else None

    top = get_db().fetch_one(
        "SELECT ticker FROM stock_supply_history WHERE date = ? AND short_ratio IS NOT NULL "
        "ORDER BY short_ratio DESC LIMIT 1", (as_of,),
    )
    if top:
        s.top_short_ticker = top["ticker"]
    return s
