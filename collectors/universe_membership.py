"""거래대금 상위(universe) 일자별 멤버십 — 종목명 소스 + "며칠 전 상위였나" 추적.

거래대금 상위(`fetch_kr_leading_stocks`)는 매 cadence·daily refresh 마다 호출되지만 ticker 만
남기고 name·날짜를 버렸다(resolve_ticker 30종 하드코딩 매핑 밖 종목은 데스크에 코드로 노출).
이 모듈이 (date, market, ticker, name, rank, 거래대금)으로 영속하여:
  ① get_stock_name — 최신 종목명 DB 조회 (소스 픽스, 매 권고가 이름을 가짐).
  ② last_universe_date / days_since — "며칠 전 거래대금 상위였나" 추적.

신규 테이블 `universe_membership` — 멤버십 시계열을 담는 기존 테이블 없음(가드 #11, DATA-MAP 등재).
순수 영속/조회 (KIS 호출은 호출부가 함 — 이 모듈은 결과 dict 만 받아 upsert).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_KST = timezone(timedelta(hours=9))

# fetch_kr_leading_stocks 결과 그룹 → 시장 라벨.
_GROUPS = (("kospi", "KOSPI"), ("kosdaq", "KOSDAQ"))


def _today_kst() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


def persist_universe_membership(
    leading: dict[str, Any], *, list_type: str = "trade_value", date: str | None = None
) -> int:
    """리스트 결과(kospi/kosdaq 항목)를 그 날짜·list_type 멤버십으로 upsert.

    list_type = 'trade_value'(거래대금 상위) | 'volume_bull'(거래량 양봉 +3%).
    멱등(ON CONFLICT REPLACE, PK=(date,market,ticker,list_type)). 같은 날 여러 cadence 재호출 → 재upsert.
    반환 = 영속 행 수. 빈 ticker·잘못된 항목은 skip.
    """
    if not isinstance(leading, dict):
        return 0
    db = get_db()
    d = date or _today_kst()
    n = 0
    for grp, market in _GROUPS:
        for item in leading.get(grp) or []:
            tk = (item.get("ticker") or "").strip()
            if not tk:
                continue
            db.execute(
                "INSERT INTO universe_membership "
                "(date, market, ticker, list_type, name, rank, trade_amount, volume, change_pct, concept, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(date, market, ticker, list_type) DO UPDATE SET "
                "name=excluded.name, rank=excluded.rank, trade_amount=excluded.trade_amount, "
                "volume=excluded.volume, change_pct=excluded.change_pct, concept=excluded.concept",
                (
                    d, market, tk, list_type, (item.get("name") or None), item.get("rank"),
                    item.get("trade_amount"), item.get("volume"), item.get("change_pct"),
                    item.get("concept"), item.get("source") or "kis",
                ),
            )
            n += 1
    return n


def get_list_members(
    list_type: str, *, date: str | None = None, within_days: int | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    """해당 list_type 의 멤버 — 관심종목 페이지용.

    - within_days 지정: **최근 N일 rolling union** — 종목별 최신행 1개(중복 제거, 최신 일자 우선).
      "관심 = 최근 10일 누적" 모델(날짜 누적은 리스트 멤버십, 단계는 별개).
    - within_days None + date 지정: 그 일자.
    - 둘 다 None: 가장 최근 일자.
    멤버 없으면 빈 리스트.
    """
    db = get_db()
    if within_days is not None:
        cutoff = (datetime.now(_KST) - timedelta(days=within_days)).strftime("%Y-%m-%d")
        rows = db.fetch_all(
            "SELECT date, market, ticker, name, rank, trade_amount, volume, change_pct, concept "
            "FROM universe_membership WHERE list_type = ? AND date >= ? "
            "ORDER BY date DESC, rank ASC",
            (list_type, cutoff),
        )
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for r in rows:
            tk = r["ticker"]
            if tk in seen:
                continue
            seen.add(tk)
            out.append(dict(r))
            if len(out) >= limit:
                break
        return out
    d = date
    if d is None:
        row = db.fetch_one(
            "SELECT MAX(date) AS d FROM universe_membership WHERE list_type = ?", (list_type,)
        )
        d = row["d"] if row and row["d"] else None
    if not d:
        return []
    rows = db.fetch_all(
        "SELECT date, market, ticker, name, rank, trade_amount, volume, change_pct, concept "
        "FROM universe_membership WHERE list_type = ? AND date = ? "
        "ORDER BY rank ASC LIMIT ?",
        (list_type, d, limit),
    )
    return [dict(r) for r in rows]


def get_stock_name(ticker: str) -> str | None:
    """가장 최근 기록된 종목명 (universe_membership). 없으면 None — 코드 폴백은 호출부."""
    if not ticker:
        return None
    row = get_db().fetch_one(
        "SELECT name FROM universe_membership "
        "WHERE ticker = ? AND name IS NOT NULL AND name != '' "
        "ORDER BY date DESC LIMIT 1",
        (ticker,),
    )
    return row["name"] if row else None


def resolve_stock_name(ticker: str, hint: str | None = None) -> str:
    """노출용 종목명 — 알림·화면 단의 단일 진입점. 코드 노출 방지.

    우선순위: hint(이미 사람이 읽을 이름) → universe_membership(최근 거래대금 상위) →
    정적 매핑(KR_TICKER_TO_NAME) → 최후 폴백으로 코드 자체.
    hint 가 코드(숫자)거나 ticker 와 같으면 무시하고 재해석한다.
    """
    name = (hint or "").strip()
    if name and name != ticker and not name.isdigit():
        return name
    resolved = get_stock_name(ticker)
    if resolved:
        return resolved
    try:
        from core.inference.run_analyst import KR_TICKER_TO_NAME

        return KR_TICKER_TO_NAME.get(ticker, ticker)
    except Exception:  # noqa: BLE001 — 매핑 모듈 부재 시 코드 폴백
        return ticker


def last_universe_date(ticker: str) -> str | None:
    """가장 최근 거래대금 상위 일자 (YYYY-MM-DD). 한 번도 없으면 None."""
    if not ticker:
        return None
    row = get_db().fetch_one(
        "SELECT date FROM universe_membership WHERE ticker = ? ORDER BY date DESC LIMIT 1",
        (ticker,),
    )
    return row["date"] if row else None


def days_since_universe(ticker: str, *, as_of: str | None = None) -> int | None:
    """마지막 거래대금 상위로부터 경과 일수 (0 = 오늘). 기록 없으면 None."""
    last = last_universe_date(ticker)
    if not last:
        return None
    base = as_of or _today_kst()
    try:
        d0 = datetime.strptime(last, "%Y-%m-%d").date()
        d1 = datetime.strptime(base, "%Y-%m-%d").date()
    except ValueError:
        return None
    return max(0, (d1 - d0).days)
