"""분기 실적 + TTM 5 ratio fundamental collector (INFRA-FUNDAMENTAL-DATA-001).

stock_analyst 의 F5 (실적 모멘텀) + F2 (펀더멘털 양호도) 결정론 산출을 위해
yfinance Default 8 필드 (TTM 5 ratio + 분기 5분기 매출·영업이익·EPS) 를
markdown 표로 묶어 `compose.build_pipeline_prompt` 의 `[5] 펀더멘털 데이터`
블록으로 주입한다.

흐름:
  1. `get_fundamentals(ticker, market='KS')` async — 인메모리 60s 캐시 hit 면 즉시.
  2. DB `fundamentals` 의 fetched_at 24h TTL 안이면 그대로.
  3. Stale or 부재 시 `YFinanceClient.fetch_full()` → DB upsert.
  4. `render_fundamental_data_md` = TTM 5 ratio 표 + 분기 4분기 표 + QoQ/YoY 자동.

3-tier fallback:
  Tier 1: yfinance fetch 실패 + DB stale ≤ 7d → source="yfinance_stale"
  Tier 2: 일부 ratio None → 부분 발행 (해당 키 N/A)
  Tier 3: quarterly 빈 → "분기 데이터 없음" 명시
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from connectors.yfinance.client import (
    FundamentalNotAvailable,
    YFinanceClient,
)
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")

# DB-first 24h TTL (cron 주 1회 → 24h 안이면 fresh)
_FRESH_MAX_HOURS = 24
# Stale fallback 허용 (7일 = cron 1주기 + grace)
_STALE_MAX_HOURS = 168


# ---------------------------------------------------------------------------
# DataClass
# ---------------------------------------------------------------------------


@dataclass
class Fundamentals:
    """get_fundamentals 결과 묶음 — 5 ratio TTM + 분기 5분기."""

    ticker: str
    market: str
    fetched_at: float                              # unix epoch
    fetched_at_iso: str                            # ISO8601 (UTC)
    eps_ttm: float | None
    pe_ratio: float | None
    roe: float | None
    operating_margin: float | None
    debt_to_equity: float | None
    quarterly_revenue: list[float | None]           # 5분기 recent-first
    quarterly_operating_income: list[float | None]
    quarterly_eps: list[float | None]
    quarter_labels: list[str]                       # ["2026Q1", ..., "2025Q1"]
    source: str                                     # "db" | "yfinance" | "yfinance_stale" | "unknown"
    fetched_db_iso: str | None
    stale_hours: float
    failures: list[str] = field(default_factory=list)
    annual_eps: list[float | None] = field(default_factory=list)    # 연간 EPS 4년 recent-first (CAN SLIM A)
    annual_labels: list[str] = field(default_factory=list)          # ["2025", "2024", ...]


# ---------------------------------------------------------------------------
# 인메모리 캐시 (60s TTL, ticker 별)
# ---------------------------------------------------------------------------


_LAST_BY_TICKER: dict[str, Fundamentals] = {}
_LAST_AT_BY_TICKER: dict[str, float] = {}


def reset_cache() -> None:
    """테스트 전용."""
    _LAST_BY_TICKER.clear()
    _LAST_AT_BY_TICKER.clear()


# ---------------------------------------------------------------------------
# DB layer (fundamentals 테이블)
# ---------------------------------------------------------------------------


def load_fundamentals_from_db(ticker: str) -> Fundamentals | None:
    """fundamentals 테이블에서 단일 ticker 로드. 부재 시 None."""
    db = get_db()
    row = db.fetch_one(
        "SELECT ticker, market, fetched_at, eps_ttm, pe_ratio, roe, "
        "operating_margin, debt_to_equity, quarterly_data, source "
        "FROM fundamentals WHERE ticker = ?",
        (ticker,),
    )
    if row is None:
        return None
    fetched_iso = row["fetched_at"]
    try:
        fetched_dt = datetime.fromisoformat(fetched_iso.replace("Z", "+00:00"))
        if fetched_dt.tzinfo is None:
            fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
        fetched_epoch = fetched_dt.timestamp()
        stale_hours = (
            datetime.now(timezone.utc) - fetched_dt
        ).total_seconds() / 3600
    except (ValueError, TypeError):
        fetched_epoch = 0.0
        stale_hours = 9999.0

    try:
        qd = json.loads(row["quarterly_data"])
    except (TypeError, ValueError):
        qd = {}

    return Fundamentals(
        ticker=row["ticker"],
        market=row["market"],
        fetched_at=fetched_epoch,
        fetched_at_iso=fetched_iso,
        eps_ttm=row["eps_ttm"],
        pe_ratio=row["pe_ratio"],
        roe=row["roe"],
        operating_margin=row["operating_margin"],
        debt_to_equity=row["debt_to_equity"],
        quarterly_revenue=qd.get("revenue") or [],
        quarterly_operating_income=qd.get("operating_income") or [],
        quarterly_eps=qd.get("eps") or [],
        quarter_labels=qd.get("quarter_labels") or [],
        source=row["source"],
        fetched_db_iso=fetched_iso,
        stale_hours=stale_hours,
        annual_eps=qd.get("annual_eps") or [],
        annual_labels=qd.get("annual_labels") or [],
    )


def persist_fundamentals_to_db(f: Fundamentals) -> None:
    """ON CONFLICT REPLACE 멱등 upsert."""
    db = get_db()
    qd = {
        "revenue": f.quarterly_revenue,
        "operating_income": f.quarterly_operating_income,
        "eps": f.quarterly_eps,
        "quarter_labels": f.quarter_labels,
        "annual_eps": f.annual_eps,
        "annual_labels": f.annual_labels,
    }
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO fundamentals "
            "(ticker, market, fetched_at, eps_ttm, pe_ratio, roe, "
            " operating_margin, debt_to_equity, quarterly_data, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET "
            "  market=excluded.market, fetched_at=excluded.fetched_at, "
            "  eps_ttm=excluded.eps_ttm, pe_ratio=excluded.pe_ratio, "
            "  roe=excluded.roe, operating_margin=excluded.operating_margin, "
            "  debt_to_equity=excluded.debt_to_equity, "
            "  quarterly_data=excluded.quarterly_data, source=excluded.source",
            (
                f.ticker,
                f.market,
                f.fetched_at_iso,
                f.eps_ttm,
                f.pe_ratio,
                f.roe,
                f.operating_margin,
                f.debt_to_equity,
                json.dumps(qd, default=lambda x: None),
                f.source,
            ),
        )


# ---------------------------------------------------------------------------
# get_fundamentals — DB-first + yfinance fallback
# ---------------------------------------------------------------------------


async def get_fundamentals(
    ticker: str,
    market: str = "KS",
    *,
    yfinance_client: YFinanceClient | None = None,
    force_refresh: bool = False,
    max_age_seconds: int = 60,
) -> Fundamentals | None:
    """펀더멘털 데이터 묶음 (TTM 5 ratio + 분기 5분기) 산출.

    DB-first hybrid:
      1. 인메모리 캐시 hit (max_age_seconds) 면 즉시.
      2. DB hit + fetched_at 24h 안 + not force_refresh → DB 사용.
      3. Stale or 부재 or force_refresh → yfinance 호출 → DB upsert.
      4. yfinance 실패 + DB stale 7일 안 → stale fallback.
      5. yfinance 실패 + DB hit X → None.

    Args:
        ticker: 6자리 종목코드 (한국) 또는 영문 (미국)
        market: "KS" | "KQ" | "US"
        yfinance_client: 외부 client (None 이면 단명 생성)
        force_refresh: 24h TTL 무시
        max_age_seconds: 인메모리 캐시 TTL

    Returns:
        Fundamentals or None (모두 실패 시)
    """
    now = time.time()
    cached = _LAST_BY_TICKER.get(ticker)
    cached_at = _LAST_AT_BY_TICKER.get(ticker, 0.0)
    if (
        not force_refresh
        and cached is not None
        and (now - cached_at) < max_age_seconds
    ):
        return cached

    failures: list[str] = []

    # 1) DB-first 검사
    db_f = load_fundamentals_from_db(ticker)
    db_fresh = db_f is not None and db_f.stale_hours <= _FRESH_MAX_HOURS
    if db_fresh and not force_refresh:
        db_f.source = "db"
        _LAST_BY_TICKER[ticker] = db_f
        _LAST_AT_BY_TICKER[ticker] = now
        return db_f

    # 2) yfinance fetch
    client = yfinance_client or YFinanceClient()
    try:
        raw = await asyncio.wait_for(
            client.fetch_full(ticker, market), timeout=30.0
        )
    except FundamentalNotAvailable as e:
        failures.append(f"yfinance_empty:{e}")
        if db_f is not None and db_f.stale_hours <= _STALE_MAX_HOURS:
            db_f.source = "yfinance_stale"
            db_f.failures = failures
            _LAST_BY_TICKER[ticker] = db_f
            _LAST_AT_BY_TICKER[ticker] = now
            return db_f
        log.warning("fundamentals_unavailable", ticker=ticker, error=str(e))
        return None
    except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001
        failures.append(f"yfinance_fetch:{type(e).__name__}")
        log.warning("fundamentals_fetch_failed", ticker=ticker, error=str(e))
        if db_f is not None and db_f.stale_hours <= _STALE_MAX_HOURS:
            db_f.source = "yfinance_stale"
            db_f.failures = failures
            _LAST_BY_TICKER[ticker] = db_f
            _LAST_AT_BY_TICKER[ticker] = now
            return db_f
        return None

    fetched_at_iso_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    f = Fundamentals(
        ticker=ticker,
        market=market,
        fetched_at=now,
        fetched_at_iso=fetched_at_iso_utc,
        eps_ttm=raw.get("eps_ttm"),
        pe_ratio=raw.get("pe_ratio"),
        roe=raw.get("roe"),
        operating_margin=raw.get("operating_margin"),
        debt_to_equity=raw.get("debt_to_equity"),
        quarterly_revenue=raw.get("quarterly_revenue") or [],
        quarterly_operating_income=raw.get("quarterly_operating_income") or [],
        quarterly_eps=raw.get("quarterly_eps") or [],
        quarter_labels=raw.get("quarter_labels") or [],
        source="yfinance",
        fetched_db_iso=fetched_at_iso_utc,
        stale_hours=0.0,
        failures=failures,
        annual_eps=raw.get("annual_eps") or [],
        annual_labels=raw.get("annual_labels") or [],
    )
    persist_fundamentals_to_db(f)

    _LAST_BY_TICKER[ticker] = f
    _LAST_AT_BY_TICKER[ticker] = now

    ratios_count = sum(
        1 for v in (
            f.eps_ttm, f.pe_ratio, f.roe, f.operating_margin, f.debt_to_equity
        ) if v is not None
    )
    log.info(
        "fundamentals_built",
        ticker=ticker,
        market=market,
        source=f.source,
        quarter_count=len(f.quarter_labels),
        ratios_count=ratios_count,
    )
    return f


# ---------------------------------------------------------------------------
# Render — fundamental_data_md (fundamental-data-md-v1 contract)
# ---------------------------------------------------------------------------


def _fmt_ratio(v: Any, *, unit: str = "") -> str:
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.2f}{unit}" if unit else f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_pct(v: Any) -> str:
    """0~1 비율 → 백분율 (예: 0.142 → '14.2%')."""
    if v is None:
        return "N/A"
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_money(v: Any, *, market: str) -> str:
    if v is None:
        return "N/A"
    try:
        n = float(v)
    except (TypeError, ValueError):
        return "N/A"
    if market in ("KS", "KQ"):
        if abs(n) >= 1e12:
            return f"{n / 1e12:,.2f}조"
        if abs(n) >= 1e8:
            return f"{n / 1e8:,.0f}억"
        return f"{n:,.0f}"
    # USD
    if abs(n) >= 1e9:
        return f"${n / 1e9:,.2f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:,.2f}M"
    return f"${n:,.0f}"


def _pct_change(curr: Any, base: Any) -> str:
    if curr is None or base is None:
        return "N/A"
    try:
        c = float(curr)
        b = float(base)
    except (TypeError, ValueError):
        return "N/A"
    if b == 0:
        return "N/A"
    return f"{(c - b) / b * 100:+.1f}%"


def _trend_label(qoq: str, yoy: str) -> str:
    """QoQ/YoY 부호 조합 → 가속/둔화/정체 라벨."""
    def _sign(s: str) -> int | None:
        if s == "N/A":
            return None
        if s.startswith("+"):
            return 1
        if s.startswith("-"):
            return -1
        return 0
    q = _sign(qoq)
    y = _sign(yoy)
    if q is None or y is None:
        return "?"
    if q > 0 and y > 0:
        return "가속"
    if q < 0 and y < 0:
        return "둔화"
    return "정체"


def render_fundamental_data_md(
    f: Fundamentals, *, name: str | None = None
) -> str:
    """`fundamental-data-md-v1` 계약. markdown 표 풀세트.

    누락 ratio = "N/A". 5분기 미달 시 YoY = "N/A". 분기 데이터 0 시 명시.
    """
    lines: list[str] = []
    name_part = f" ({name})" if name else ""
    lines.append("## [5] 펀더멘털 데이터 (INFRA-FUNDAMENTAL-DATA-001)")
    lines.append("")
    lines.append(
        f"**Ticker**: {f.ticker}{name_part} | "
        f"**Market**: {f.market} | "
        f"**자료**: {f.source} (fetched {f.fetched_at_iso}, {f.stale_hours:.1f}h ago)"
    )
    if f.quarter_labels:
        latest = f.quarter_labels[0]
        rest = ", ".join(f.quarter_labels[1:5])
        lines.append(f"_분기 라벨: {latest} (최신) / {rest}_")
    lines.append("")

    # TTM 5 ratio (F2)
    lines.append("### TTM 5 ratio (F2 입력)")
    lines.append("| 지표 | 값 | 본 분석가 해석 가이드 |")
    lines.append("|---|---|---|")
    market_unit = "KRW" if f.market in ("KS", "KQ") else "USD"
    lines.append(
        f"| EPS TTM | {_fmt_ratio(f.eps_ttm)} {market_unit} | F2 base — 양수/음수 |"
    )
    lines.append(
        f"| PE (현재) | {_fmt_ratio(f.pe_ratio, unit='x')} | F2 밸류에이션 — 업종 평균 대비 |"
    )
    lines.append(
        f"| ROE | {_fmt_pct(f.roe)} | F2 펀더멘털 양호도 — 15%+ = 우수 |"
    )
    lines.append(
        f"| Operating Margin | {_fmt_pct(f.operating_margin)} | F2 수익성 — 업종 비교 |"
    )
    if f.debt_to_equity is not None:
        de_str = f"{float(f.debt_to_equity):.1f}%"
    else:
        de_str = "N/A"
    lines.append(
        f"| Debt/Equity | {de_str} | F2 안전성 — 100% 미만 안전 |"
    )
    lines.append("")

    # 분기 실적 (F5)
    lines.append("### 분기 실적 (F5 입력)")
    rev = f.quarterly_revenue
    op = f.quarterly_operating_income
    eps = f.quarterly_eps
    labels = f.quarter_labels
    if not labels:
        lines.append("_분기 데이터 없음 (신규 상장 가능 / yfinance 미제공)_")
        lines.append("")
    else:
        lines.append("| 분기 | 매출 | 영업이익 | EPS |")
        lines.append("|---|---|---|---|")
        n = min(len(labels), 4)  # 표는 최근 4분기만 노출
        for i in range(n):
            rev_v = rev[i] if i < len(rev) else None
            op_v = op[i] if i < len(op) else None
            eps_v = eps[i] if i < len(eps) else None
            lines.append(
                f"| {labels[i]} | "
                f"{_fmt_money(rev_v, market=f.market)} | "
                f"{_fmt_money(op_v, market=f.market)} | "
                f"{_fmt_ratio(eps_v)} |"
            )
        lines.append("")

        # QoQ·YoY 자동 계산 (5분기 저장 → YoY 가능)
        lines.append("### QoQ·YoY (F5 모멘텀 산출 base)")
        rev_qoq = _pct_change(
            rev[0] if rev else None, rev[1] if len(rev) > 1 else None
        )
        op_qoq = _pct_change(
            op[0] if op else None, op[1] if len(op) > 1 else None
        )
        eps_qoq = _pct_change(
            eps[0] if eps else None, eps[1] if len(eps) > 1 else None
        )
        rev_yoy = _pct_change(
            rev[0] if rev else None, rev[4] if len(rev) > 4 else None
        )
        op_yoy = _pct_change(
            op[0] if op else None, op[4] if len(op) > 4 else None
        )
        eps_yoy = _pct_change(
            eps[0] if eps else None, eps[4] if len(eps) > 4 else None
        )
        lines.append(
            f"- 매출 QoQ: **{rev_qoq}** / YoY: **{rev_yoy}** "
            f"({_trend_label(rev_qoq, rev_yoy)})"
        )
        lines.append(
            f"- 영업이익 QoQ: **{op_qoq}** / YoY: **{op_yoy}** "
            f"({_trend_label(op_qoq, op_yoy)})"
        )
        lines.append(
            f"- EPS QoQ: **{eps_qoq}** / YoY: **{eps_yoy}** "
            f"({_trend_label(eps_qoq, eps_yoy)})"
        )
        if len(labels) < 5:
            lines.append("_(5분기 미달 시 YoY = N/A. 정상 5분기 필요)_")
        lines.append("")

    # 본 분석가 사용 지침
    lines.append("### 본 분석가 사용 지침")
    lines.append(
        "- **F5 (실적 모멘텀)**: QoQ·YoY 양쪽 양수 = 가속 / 양수+음수 혼합 = "
        "정체 / 양쪽 음수 = 둔화. **2 분기 연속 둔화 시 청산 시그널**."
    )
    lines.append(
        "- **F2 (펀더멘털 양호도)**: 5 ratio 동시 평가. PE < 업종 평균 + ROE > 15% + "
        "Operating Margin > 10% + Debt/Equity < 100% = 양호 / 1 개라도 위반 = 경고 / "
        "다수 위반 = 약화."
    )
    lines.append(
        "- 학습 데이터 시점 수치 인용 X — 본 블록의 fetched_at 시점 수치만 인용."
    )

    if f.failures:
        lines.append("")
        lines.append(f"_누락: {', '.join(f.failures)}_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Refresh entrypoint (justfile + APScheduler cron)
# ---------------------------------------------------------------------------


async def refresh_all_tickers(
    *,
    tickers: list[str] | None = None,
    market_default: str = "KS",
) -> dict[str, Any]:
    """KR_NAME_TO_TICKER 35종 + DB distinct fundamental refresh.

    APScheduler cron `0 18 * * 0` (일요일 18:00 KST) + `just refresh-fundamentals`.

    Args:
        tickers: 명시 ticker 리스트 (None 이면 KR_NAME_TO_TICKER + DB distinct)
        market_default: 명시 ticker 에 market 미지정 시 fallback

    Returns:
        {"refreshed": [...], "failed": [...], "elapsed_s": float}
    """
    if tickers is None:
        from core.inference.run_analyst import KR_NAME_TO_TICKER

        kr_set = set(KR_NAME_TO_TICKER.values())
        db = get_db()
        rows = db.fetch_all(
            "SELECT DISTINCT ticker FROM fundamentals ORDER BY ticker"
        )
        db_set = {r["ticker"] for r in rows}
        tickers = sorted(kr_set | db_set)

    if not tickers:
        log.info("fundamentals_refresh_skipped", reason="no tickers")
        return {"refreshed": [], "failed": [], "elapsed_s": 0.0}

    started = time.monotonic()
    refreshed: list[str] = []
    failed: list[dict[str, Any]] = []
    client = YFinanceClient()
    for tk in tickers:
        try:
            _LAST_AT_BY_TICKER[tk] = 0.0
            f = await get_fundamentals(
                tk,
                market=market_default,
                yfinance_client=client,
                force_refresh=True,
                max_age_seconds=0,
            )
            if f is None:
                failed.append({"ticker": tk, "error": "unavailable"})
            elif f.failures:
                failed.append({"ticker": tk, "failures": f.failures})
            else:
                refreshed.append(tk)
        except Exception as e:  # noqa: BLE001
            failed.append(
                {"ticker": tk, "error": f"{type(e).__name__}: {e}"}
            )
            log.warning(
                "fundamentals_refresh_failed", ticker=tk, error=str(e)
            )
        # yfinance rate limit 안전 (분당 ~60)
        await asyncio.sleep(0.5)

    elapsed = time.monotonic() - started
    log.info(
        "fundamentals_refresh_done",
        refreshed=len(refreshed),
        failed=len(failed),
        elapsed_s=round(elapsed, 2),
    )
    return {
        "refreshed": refreshed,
        "failed": failed,
        "elapsed_s": round(elapsed, 2),
    }


def _main_cli() -> None:
    """`python -m collectors.fundamentals refresh` 진입점."""
    import argparse

    parser = argparse.ArgumentParser(description="fundamentals refresh utility")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser(
        "refresh",
        help="KR_NAME_TO_TICKER + DB distinct 모두 fundamental refresh",
    )
    fetch = sub.add_parser("fetch", help="단일 ticker fetch + 적재")
    fetch.add_argument("ticker")
    fetch.add_argument("--market", default="KS")
    args = parser.parse_args()

    if args.cmd == "refresh":
        result = asyncio.run(refresh_all_tickers())
        sys.stdout.write(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
    elif args.cmd == "fetch":
        async def _run() -> dict[str, Any]:
            f = await get_fundamentals(
                args.ticker,
                market=args.market,
                force_refresh=True,
                max_age_seconds=0,
            )
            if f is None:
                return {"ticker": args.ticker, "error": "unavailable"}
            return {
                "ticker": f.ticker,
                "market": f.market,
                "source": f.source,
                "eps_ttm": f.eps_ttm,
                "pe_ratio": f.pe_ratio,
                "roe": f.roe,
                "operating_margin": f.operating_margin,
                "debt_to_equity": f.debt_to_equity,
                "quarter_labels": f.quarter_labels,
                "failures": f.failures,
            }
        result = asyncio.run(_run())
        sys.stdout.write(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    _main_cli()
