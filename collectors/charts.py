"""차트 데이터 collector (INFRA-CHART-DATA-001).

stock_analyst 의 α·F1·F4·목표가 3 단 결정론 산출을 위해 KIS daily OHLCV 5 년 +
on-demand snapshot + Default 6 지표 (월봉 7·20MA / 주봉 10·20·60MA / 일봉 4·7·20·60·120MA /
MACD 12-26-9 / 거래량 20일 spike / 52주 고저) 를 markdown 표로 묶어
`compose.build_pipeline_prompt` 의 `[4] 차트 데이터` 블록으로 주입한다.

흐름:
  1. `build_chart_data(ticker, max_age_seconds=60)` async — 인메모리 캐시 hit 면 즉시.
  2. DB `chart_ohlcv` 에서 historical OHLCV 로드. fetched_at 이 평일 18:00 cron 이후면 fresh.
  3. Stale 또는 부재 시 KIS `get_daily_chart()` 호출 → DB upsert.
  4. on-demand snapshot = `get_current_price()` (별도 60s TTL).
  5. `compute_indicators` = pandas 기본 함수 (rolling / ewm) 로 6 지표.
  6. `render_chart_data_md` = markdown 표 풀세트.

3-tier fallback:
  Tier 1: KIS fetch 실패 → DB last cache 사용 (stale 5 영업일 허용)
  Tier 2: 지표 계산 NaN → 부분 발행 (null + reasons)
  Tier 3: snapshot 60s TTL 만료 + API 실패 → last cache 사용

pandas-ta 미사용 (numpy 호환성 위험 회피). RSI·볼린저 (SLOT 2, WAVE-ALPHA-001 후) 진입 시 재검토.
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from connectors.kis import KISClient
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")

# DB-first fresh 임계 (다음 daily cron 18:00 KST 까지 = 약 1 영업일 + grace)
_FRESH_MAX_HOURS = 26
# Stale fallback 허용 임계 (SPEC § 8 Tier 1, 5 영업일 + 주말 = 168h)
_STALE_MAX_HOURS = 168


# ---------------------------------------------------------------------------
# DataClass
# ---------------------------------------------------------------------------


@dataclass
class ChartData:
    """build_chart_data 결과 묶음 — snapshot + ohlcv + indicators + 메타."""

    ticker: str
    fetched_at: float
    fetched_at_iso: str
    snapshot: dict[str, Any]            # current_price/open/high/low/change_rate/volume/value
    indicators: dict[str, Any]          # Default 6 지표
    ohlcv_count: int                    # historical 봉 수
    source: str                         # "db" | "kis" | "stale_cache"
    db_last_date: str | None            # YYYY-MM-DD
    stale_hours: float                  # DB last_date 와 현재 시각 차
    failures: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 인메모리 캐시 (60s TTL, ticker 별)
# ---------------------------------------------------------------------------


_LAST_BY_TICKER: dict[str, ChartData] = {}
_LAST_AT_BY_TICKER: dict[str, float] = {}


def reset_cache() -> None:
    """테스트 전용."""
    _LAST_BY_TICKER.clear()
    _LAST_AT_BY_TICKER.clear()


# ---------------------------------------------------------------------------
# DB layer (chart_ohlcv 테이블)
# ---------------------------------------------------------------------------


def load_ohlcv_from_db(ticker: str, *, limit: int = 1825) -> pd.DataFrame:
    """`chart_ohlcv` 테이블에서 최근 limit 일 historical OHLCV 로드.

    Returns:
        pd.DataFrame (index=date, 8 컬럼). 데이터 없으면 빈 DataFrame.
    """
    db = get_db()
    rows = db.fetch_all(
        "SELECT date, open, high, low, close, volume, change_rate, value "
        "FROM chart_ohlcv WHERE ticker = ? ORDER BY date DESC LIMIT ?",
        (ticker, limit),
    )
    if not rows:
        return pd.DataFrame()
    data = [dict(r) for r in rows]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    return df


def persist_ohlcv_to_db(ticker: str, bars: list[dict[str, Any]], *, adjusted: bool = True) -> int:
    """ON CONFLICT REPLACE 멱등 upsert. 반환 = 적재한 row 수."""
    if not bars:
        return 0
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = get_db()
    seq = [
        (
            ticker,
            b["date"],
            float(b.get("open", 0)),
            float(b.get("high", 0)),
            float(b.get("low", 0)),
            float(b.get("close", 0)),
            int(b.get("volume", 0)),
            float(b.get("change_rate", 0)),
            int(b.get("value", 0)),
            1 if adjusted else 0,
            now_iso,
        )
        for b in bars
    ]
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO chart_ohlcv "
            "(ticker, date, open, high, low, close, volume, change_rate, value, adjusted, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(ticker, date) DO UPDATE SET "
            "  open=excluded.open, high=excluded.high, low=excluded.low, "
            "  close=excluded.close, volume=excluded.volume, "
            "  change_rate=excluded.change_rate, value=excluded.value, "
            "  adjusted=excluded.adjusted, fetched_at=excluded.fetched_at",
            seq,
        )
    return len(seq)


def get_db_last_fetched_at(ticker: str) -> tuple[str | None, float | None]:
    """가장 최근 적재 시각 (fetched_at, last_date) → (iso, hours_ago)."""
    db = get_db()
    row = db.fetch_one(
        "SELECT MAX(date) AS last_date, MAX(fetched_at) AS fetched FROM chart_ohlcv WHERE ticker = ?",
        (ticker,),
    )
    if row is None or row["fetched"] is None:
        return None, None
    last_date = row["last_date"]
    fetched_iso = row["fetched"]
    try:
        fetched_dt = datetime.fromisoformat(fetched_iso.replace("Z", "+00:00"))
        if fetched_dt.tzinfo is None:
            fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
        hours_ago = (datetime.now(timezone.utc) - fetched_dt).total_seconds() / 3600
    except (ValueError, TypeError):
        hours_ago = None
    return last_date, hours_ago


# ---------------------------------------------------------------------------
# Default 6 지표 — pandas 기본 함수 (rolling / ewm)
# ---------------------------------------------------------------------------


def _safe_last(s: pd.Series) -> float | None:
    """마지막 값 반환. NaN/빈 시리즈 → None."""
    if s is None or len(s) == 0:
        return None
    v = s.iloc[-1]
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return float(v)


def compute_indicators(ohlcv: pd.DataFrame) -> dict[str, Any]:
    """Default 6 지표 dict. NaN/데이터 부족 케이스 → 해당 키 null + reasons.

    Default 6:
      1. 월봉 7MA / 20MA
      2. 주봉 10MA / 20MA / 60MA
      3. 일봉 4MA / 7MA / 20MA / 60MA / 120MA
      4. MACD 12-26-9 (daily)
      5. 거래량 20일 이평 + 오늘 거래량 / 20일 이평 (spike 비율)
      6. 52주 (252 영업일) 고저 + 현재가 위치
    """
    out: dict[str, Any] = {
        "daily_ma": {},
        "weekly_ma": {},
        "monthly_ma": {},
        "macd": {},
        "volume": {},
        "fifty_two_week": {},
        "current_close": None,
        "reasons": [],
    }
    if ohlcv is None or len(ohlcv) == 0:
        out["reasons"].append("ohlcv 빈 DataFrame")
        return out

    close = ohlcv["close"]
    out["current_close"] = _safe_last(close)

    # 1) 일봉 MA
    for n in (4, 7, 20, 60, 120):
        if len(close) >= n:
            out["daily_ma"][f"ma{n}"] = _safe_last(close.rolling(window=n).mean())
        else:
            out["daily_ma"][f"ma{n}"] = None
            out["reasons"].append(f"일봉 {n}MA 데이터 부족 ({len(close)}봉)")

    # 2) 주봉 MA — resample('W-FRI') 금요일 종가 기준
    try:
        weekly = ohlcv.resample("W-FRI").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna(subset=["close"])
    except Exception as e:  # noqa: BLE001
        weekly = pd.DataFrame()
        out["reasons"].append(f"weekly resample 실패: {e}")
    if len(weekly):
        wclose = weekly["close"]
        for n in (10, 20, 60):
            if len(wclose) >= n:
                out["weekly_ma"][f"ma{n}"] = _safe_last(wclose.rolling(window=n).mean())
            else:
                out["weekly_ma"][f"ma{n}"] = None
                out["reasons"].append(f"주봉 {n}MA 데이터 부족 ({len(wclose)}봉)")
    else:
        for n in (10, 20, 60):
            out["weekly_ma"][f"ma{n}"] = None

    # 3) 월봉 MA — resample('ME') 월말 종가 기준
    try:
        monthly = ohlcv.resample("ME").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna(subset=["close"])
    except Exception as e:  # noqa: BLE001
        monthly = pd.DataFrame()
        out["reasons"].append(f"monthly resample 실패: {e}")
    if len(monthly):
        mclose = monthly["close"]
        for n in (7, 20):
            if len(mclose) >= n:
                out["monthly_ma"][f"ma{n}"] = _safe_last(mclose.rolling(window=n).mean())
            else:
                out["monthly_ma"][f"ma{n}"] = None
                out["reasons"].append(f"월봉 {n}MA 데이터 부족 ({len(mclose)}봉)")
    else:
        for n in (7, 20):
            out["monthly_ma"][f"ma{n}"] = None

    # 4) MACD 12-26-9 (daily) — ewm(span)
    if len(close) >= 26:
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        out["macd"] = {
            "macd": _safe_last(macd),
            "signal": _safe_last(signal),
            "histogram": _safe_last(hist),
        }
    else:
        out["macd"] = {"macd": None, "signal": None, "histogram": None}
        out["reasons"].append(f"MACD 데이터 부족 ({len(close)}봉)")

    # 5) 거래량 spike
    volume = ohlcv["volume"]
    if len(volume) >= 20:
        vol_ma20 = volume.rolling(window=20).mean()
        today_vol = _safe_last(volume)
        ma20_val = _safe_last(vol_ma20)
        ratio = None
        if today_vol is not None and ma20_val and ma20_val > 0:
            ratio = today_vol / ma20_val
        out["volume"] = {
            "today": today_vol,
            "ma20": ma20_val,
            "spike_ratio": ratio,
        }
    else:
        out["volume"] = {"today": _safe_last(volume), "ma20": None, "spike_ratio": None}
        out["reasons"].append(f"거래량 20MA 데이터 부족 ({len(volume)}봉)")

    # 6) 52주 (252 영업일) 고저
    if len(close) >= 1:
        window = min(252, len(close))
        recent = ohlcv.tail(window)
        high_52w = float(recent["high"].max())
        low_52w = float(recent["low"].min())
        high_date_idx = recent["high"].idxmax()
        low_date_idx = recent["low"].idxmin()
        cur = out["current_close"] or 0
        out["fifty_two_week"] = {
            "high": high_52w,
            "high_date": high_date_idx.strftime("%Y-%m-%d") if hasattr(high_date_idx, "strftime") else str(high_date_idx),
            "low": low_52w,
            "low_date": low_date_idx.strftime("%Y-%m-%d") if hasattr(low_date_idx, "strftime") else str(low_date_idx),
            "pct_from_high": ((cur - high_52w) / high_52w * 100) if cur and high_52w else None,
            "pct_from_low": ((cur - low_52w) / low_52w * 100) if cur and low_52w else None,
            "window_days": window,
        }
        if window < 252:
            out["reasons"].append(f"52주 윈도우 부족 ({window}봉, 상장 직후)")
    return out


# ---------------------------------------------------------------------------
# build_chart_data — DB-first + KIS fallback
# ---------------------------------------------------------------------------


async def build_chart_data(
    ticker: str,
    *,
    kis: KISClient | None = None,
    max_age_seconds: int = 60,
    period_days: int = 1825,
    adjust: bool = True,
) -> tuple[ChartData, bool]:
    """차트 데이터 묶음 (snapshot + indicators) 산출.

    DB-first hybrid:
      1. 인메모리 캐시 hit (max_age_seconds) 면 즉시.
      2. DB chart_ohlcv 의 last fetched_at 가 stale 임계 안이면 DB 사용.
      3. Stale 또는 부재 시 KIS get_daily_chart() → DB upsert → 재로드.
      4. snapshot = KIS get_current_price() 매 호출 (단명).

    Args:
        ticker: 6자리 종목코드 (예: "005930")
        kis: 외부 KISClient (None 이면 단명 client 생성)
        max_age_seconds: 인메모리 캐시 TTL
        period_days: historical 봉 수 (기본 1825 = 5년)
        adjust: 수정주가 여부

    Returns:
        (ChartData, cache_hit). cache_hit=True 면 max_age_seconds 안 인메모리 재사용.
    """
    now = time.time()
    cached = _LAST_BY_TICKER.get(ticker)
    cached_at = _LAST_AT_BY_TICKER.get(ticker, 0.0)
    if cached is not None and (now - cached_at) < max_age_seconds:
        return cached, True

    failures: list[str] = []
    started = time.monotonic()

    # 1) DB fresh 검사 (다음 cron 까지 신선)
    last_date, stale_hours = get_db_last_fetched_at(ticker)
    db_fresh = stale_hours is not None and stale_hours <= _FRESH_MAX_HOURS
    source = "db" if db_fresh else "kis"

    # 2) DB stale or 부재 시 KIS fetch
    snapshot: dict[str, Any] = {}
    async with AsyncExitStack() as stack:
        kis_client = kis
        if kis_client is None:
            kis_client = await stack.enter_async_context(KISClient())

        if not db_fresh:
            try:
                bars = await kis_client.get_daily_chart(
                    ticker, period_days=period_days, adjust=adjust,
                )
                if bars:
                    persist_ohlcv_to_db(ticker, bars, adjusted=adjust)
                else:
                    failures.append("kis_chart_empty")
            except Exception as e:  # noqa: BLE001
                failures.append(f"kis_chart_fetch:{type(e).__name__}")
                log.warning("chart_ohlcv_fetch_failed", ticker=ticker, error=str(e))
                # DB last cache fallback (stale 5 영업일 허용)
                if last_date is not None and (stale_hours or 0) <= _STALE_MAX_HOURS:
                    source = "stale_cache"
                else:
                    source = "unknown"

        # 3) snapshot 호출
        try:
            snapshot = await kis_client.get_current_price(ticker)
            if "error" in snapshot:
                failures.append(f"kis_snapshot:{snapshot.get('error')}")
                snapshot = {}
        except Exception as e:  # noqa: BLE001
            failures.append(f"kis_snapshot:{type(e).__name__}")
            log.warning("chart_snapshot_fetch_failed", ticker=ticker, error=str(e))
            snapshot = {}

    # 4) DB 재로드 + 지표 계산
    df = load_ohlcv_from_db(ticker, limit=period_days)
    indicators = compute_indicators(df) if len(df) else {"reasons": ["ohlcv 부재"]}
    last_date_final, stale_hours_final = get_db_last_fetched_at(ticker)

    elapsed = time.monotonic() - started
    fetched_at_iso = datetime.fromtimestamp(now, _KST).isoformat(timespec="seconds")

    chart = ChartData(
        ticker=ticker,
        fetched_at=now,
        fetched_at_iso=fetched_at_iso,
        snapshot=snapshot,
        indicators=indicators,
        ohlcv_count=int(len(df)),
        source=source,
        db_last_date=last_date_final,
        stale_hours=stale_hours_final or 0.0,
        failures=failures,
    )
    _LAST_BY_TICKER[ticker] = chart
    _LAST_AT_BY_TICKER[ticker] = now

    log.info(
        "chart_data_built",
        ticker=ticker,
        ohlcv_count=int(len(df)),
        source=source,
        failures=failures,
        elapsed_s=round(elapsed, 2),
    )
    return chart, False


# ---------------------------------------------------------------------------
# Render — chart_data_md (chart-data-md-v1 contract)
# ---------------------------------------------------------------------------


def _fmt_price(v: Any) -> str:
    if v is None:
        return "null"
    try:
        return f"{float(v):,.0f}" if abs(float(v)) >= 1000 else f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "null"


def _fmt_pct(cur: Any, base: Any) -> str:
    if cur is None or base is None:
        return "?"
    try:
        c = float(cur)
        b = float(base)
        if b == 0:
            return "?"
        return f"{(c - b) / b * 100:+.2f}%"
    except (TypeError, ValueError):
        return "?"


def _fmt_won(value: Any) -> str:
    """원 → 한국식 억/조."""
    if value is None:
        return "null"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "null"
    if abs(v) >= 1e12:
        return f"{v / 1e12:,.2f}조"
    if abs(v) >= 1e8:
        return f"{v / 1e8:,.0f}억"
    return f"{v:,.0f}"


def render_chart_data_md(chart: ChartData, *, name: str | None = None) -> str:
    """`chart-data-md-v1` 계약. markdown 표 풀세트.

    LLM 이 직접 인용할 수 있도록 모든 지표 + 현재가 대비 % 명시.
    누락 지표는 `null` 표기. 환각 가드 정합 (출처 명시 강제).
    """
    lines: list[str] = []
    name_part = f" ({name})" if name else ""
    lines.append(f"## [4] 차트 데이터 (INFRA-CHART-DATA-001)")
    lines.append("")
    lines.append(
        f"**Ticker**: {chart.ticker}{name_part} | "
        f"**As of**: {chart.fetched_at_iso} | "
        f"**수정주가 기준** | **출처**: {chart.source}"
    )
    if chart.db_last_date:
        lines.append(
            f"_DB last_date: {chart.db_last_date} · stale_hours: {chart.stale_hours:.1f}h · ohlcv_count: {chart.ohlcv_count}_"
        )
    lines.append("")

    # 현재 시점 snapshot
    snap = chart.snapshot or {}
    lines.append("### 현재 시점 snapshot")
    lines.append("| 필드 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| current_price | {_fmt_price(snap.get('current_price'))} |")
    lines.append(f"| open_price | {_fmt_price(snap.get('open_price'))} |")
    lines.append(f"| high_price | {_fmt_price(snap.get('high_price'))} |")
    lines.append(f"| low_price | {_fmt_price(snap.get('low_price'))} |")
    cr = snap.get("change_rate")
    lines.append(f"| change_rate | {f'{float(cr):+.2f}%' if isinstance(cr, (int, float)) else 'null'} |")
    lines.append(f"| volume_today | {_fmt_price(snap.get('volume_today'))} |")
    lines.append(f"| value_today | {_fmt_won(snap.get('value_today'))} |")
    lines.append("")

    cur = snap.get("current_price") or chart.indicators.get("current_close")
    ind = chart.indicators or {}

    # 월봉 추세
    mma = ind.get("monthly_ma") or {}
    lines.append("### 월봉 추세")
    lines.append("| 지표 | 값 | 현재가 대비 |")
    lines.append("|---|---|---|")
    for k, label in (("ma7", "월봉 7MA"), ("ma20", "월봉 20MA")):
        v = mma.get(k)
        lines.append(f"| {label} | {_fmt_price(v)} | {_fmt_pct(cur, v)} |")
    lines.append("")

    # 주봉 추세
    wma = ind.get("weekly_ma") or {}
    lines.append("### 주봉 추세")
    lines.append("| 지표 | 값 | 현재가 대비 |")
    lines.append("|---|---|---|")
    for k, label in (("ma10", "주봉 10MA"), ("ma20", "주봉 20MA"), ("ma60", "주봉 60MA")):
        v = wma.get(k)
        lines.append(f"| {label} | {_fmt_price(v)} | {_fmt_pct(cur, v)} |")
    lines.append("")

    # 일봉 추세
    dma = ind.get("daily_ma") or {}
    lines.append("### 일봉 추세")
    lines.append("| 지표 | 값 | 현재가 대비 |")
    lines.append("|---|---|---|")
    for k, label in (
        ("ma4", "일봉 4MA"), ("ma7", "일봉 7MA"), ("ma20", "일봉 20MA"),
        ("ma60", "일봉 60MA"), ("ma120", "일봉 120MA"),
    ):
        v = dma.get(k)
        lines.append(f"| {label} | {_fmt_price(v)} | {_fmt_pct(cur, v)} |")
    lines.append("")

    # MACD
    macd = ind.get("macd") or {}
    lines.append("### MACD (12-26-9, daily)")
    lines.append("| 컴포넌트 | 값 |")
    lines.append("|---|---|")
    for k, label in (("macd", "MACD"), ("signal", "Signal"), ("histogram", "Histogram")):
        v = macd.get(k)
        sign = ""
        if v is not None and label == "Histogram":
            sign = " (양선)" if v > 0 else (" (음선)" if v < 0 else "")
        lines.append(f"| {label} | {_fmt_price(v)}{sign} |")
    lines.append("")

    # 거래량
    vol = ind.get("volume") or {}
    lines.append("### 거래량 패턴")
    lines.append("| 지표 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| 20일 이평 거래량 | {_fmt_price(vol.get('ma20'))} |")
    spike = vol.get("spike_ratio")
    if spike is not None:
        spike_label = f"{spike:.2f}× (spike {(spike - 1) * 100:+.0f}%)"
    else:
        spike_label = "null"
    lines.append(f"| 오늘 거래량 / 20일 이평 | {spike_label} |")
    lines.append("")

    # 52주 고저
    ftw = ind.get("fifty_two_week") or {}
    lines.append("### 52주 고저")
    lines.append("| 지표 | 값 | 현재가 위치 |")
    lines.append("|---|---|---|")
    high = ftw.get("high")
    high_date = ftw.get("high_date") or ""
    low = ftw.get("low")
    low_date = ftw.get("low_date") or ""
    pct_high = ftw.get("pct_from_high")
    pct_low = ftw.get("pct_from_low")
    lines.append(
        f"| 52주 고가 | {_fmt_price(high)}{f' ({high_date})' if high_date else ''} | "
        f"{f'{pct_high:+.2f}%' if pct_high is not None else '?'} |"
    )
    lines.append(
        f"| 52주 저가 | {_fmt_price(low)}{f' ({low_date})' if low_date else ''} | "
        f"{f'{pct_low:+.2f}%' if pct_low is not None else '?'} |"
    )
    if ftw.get("window_days") and ftw["window_days"] < 252:
        lines.append(f"_(상장 후 {ftw['window_days']}봉만 사용 — 52주 미만)_")
    lines.append("")

    # 부분 발행 사유
    reasons = ind.get("reasons") or []
    if reasons:
        lines.append("### 부분 발행 사유")
        for r in reasons:
            lines.append(f"- {r}")
        lines.append("")

    if chart.failures:
        lines.append(f"_누락: {', '.join(chart.failures)}_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Refresh entrypoint (justfile + APScheduler cron)
# ---------------------------------------------------------------------------


def _seed_tickers() -> list[str]:
    """`chart_ohlcv` 에 항상 적재되어야 하는 seed ticker list.

    INFRA-SNAPSHOT-EXTEND-001 R1 결단: 지수 (KOSPI 0001 / KOSDAQ 1001) +
    14 섹터 ETF (kr_sectors.DEFAULT_TRACKED_ETFS) 가 chart_ohlcv 적재 필요.
    market_macro / sector_rs collector 가 chart_ohlcv 직접 read 위임.
    """
    from collectors.kr_sectors import DEFAULT_TRACKED_ETFS

    return ["0001", "1001"] + [t for t, _ in DEFAULT_TRACKED_ETFS]


async def _select_refresh_tickers(
    db: Any, kis: KISClient
) -> tuple[list[str], dict[str, Any]]:
    """daily refresh 대상 선정 = seed + 당일 leading universe(항상) + 누적 DB(fetched_at 최신순, cap).

    universe-backfill 2026-06-02: 거래대금 상위 종목 일봉을 상시 적재해 캘리브레이션 다일 누적의
    데이터 공백을 메운다. KIS rate limit 보호를 위해 일일 refresh 종목 수를 max_tickers 로 상한:
    seed + 당일 leading 은 무조건 포함, 남는 자리는 가장 최근 적재(fetched_at)된 누적 종목으로 채우고
    오래된 종목은 daily refresh 에서만 제외(chart_ohlcv 데이터는 삭제 안 함).
    """
    from collectors.screening import fetch_universe_tickers, get_universe_max_tickers

    rows = db.fetch_all(
        "SELECT ticker, MAX(fetched_at) AS last_fetched FROM chart_ohlcv GROUP BY ticker"
    )
    last_fetched = {r["ticker"]: (r["last_fetched"] or "") for r in rows}
    seed = _seed_tickers()

    universe: list[str] = []
    universe_error: str | None = None
    try:
        universe = await fetch_universe_tickers(kis=kis)
    except Exception as e:  # noqa: BLE001 — leading fetch 실패해도 seed+DB refresh 는 진행
        universe_error = f"{type(e).__name__}: {e}"
        log.warning("chart_refresh_universe_fetch_failed", error=universe_error)

    must = set(seed) | set(universe)            # 항상 refresh
    optional = [t for t in last_fetched if t not in must]
    optional.sort(key=lambda t: last_fetched.get(t, ""), reverse=True)  # 최신 fetched 우선
    max_tickers = get_universe_max_tickers()
    room = max(0, max_tickers - len(must))
    kept = optional[:room]
    dropped = len(optional) - len(kept)
    tickers = sorted(must | set(kept))
    meta = {
        "seed": len(seed),
        "universe": len(universe),
        "universe_error": universe_error,
        "db_total": len(last_fetched),
        "kept_optional": len(kept),
        "dropped_optional": dropped,
        "max_tickers": max_tickers,
        "selected": len(tickers),
    }
    if dropped:
        log.info("chart_refresh_universe_capped", **{k: meta[k] for k in
                 ("max_tickers", "selected", "dropped_optional")})
    return tickers, meta


async def refresh_all_tickers(*, period_days: int = 1825) -> dict[str, Any]:
    """`chart_ohlcv` ticker (seed + 당일 leading universe + 누적 DB cap) daily refresh.

    APScheduler cron `0 18 * * 1-5` + `just refresh-charts` 진입점.
    rate limit 자체는 KISClient 의 _CALL_INTERVAL=1.1s 가 보장.

    대상 선정 = `_select_refresh_tickers` (seed 지수 0001/1001 + 14 섹터 ETF + 당일 거래대금
    상위 universe + 누적 DB 종목을 max_tickers 상한 내에서 fetched_at 최신순). 첫 발동 시 새 종목은
    KIS get_daily_chart 로 백필됨.

    Returns:
        {"refreshed": [...], "failed": [...], "elapsed_s": float, "universe": {...}}
    """
    db = get_db()
    started = time.monotonic()
    refreshed: list[str] = []
    failed: list[dict[str, Any]] = []
    async with KISClient() as kis:
        tickers, uni_meta = await _select_refresh_tickers(db, kis)
        if not tickers:
            log.info("chart_refresh_skipped", reason="no tickers (DB + seed + universe empty)")
            return {"refreshed": [], "failed": [], "elapsed_s": 0.0, "universe": uni_meta}
        for tk in tickers:
            try:
                # 캐시 우회 강제 (cron 은 새로 받아오는 게 목적)
                _LAST_AT_BY_TICKER[tk] = 0.0
                chart, _ = await build_chart_data(
                    tk, kis=kis, max_age_seconds=0, period_days=period_days,
                )
                if chart.failures:
                    failed.append({"ticker": tk, "failures": chart.failures})
                else:
                    refreshed.append(tk)
            except Exception as e:  # noqa: BLE001
                failed.append({"ticker": tk, "error": f"{type(e).__name__}: {e}"})
                log.warning("chart_refresh_failed", ticker=tk, error=str(e))
    elapsed = time.monotonic() - started
    log.info(
        "chart_refresh_done",
        refreshed=len(refreshed),
        failed=len(failed),
        elapsed_s=round(elapsed, 2),
        universe=uni_meta.get("universe"),
        selected=uni_meta.get("selected"),
    )
    return {
        "refreshed": refreshed,
        "failed": failed,
        "elapsed_s": round(elapsed, 2),
        "universe": uni_meta,
    }


def _main_cli() -> None:
    """`python -m collectors.charts refresh` 진입점."""
    import argparse

    parser = argparse.ArgumentParser(description="chart_ohlcv refresh utility")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("refresh", help="DB 적재된 모든 ticker daily refresh")
    fetch = sub.add_parser("fetch", help="단일 ticker fetch + 적재")
    fetch.add_argument("ticker")
    fetch.add_argument("--days", type=int, default=1825)
    args = parser.parse_args()

    if args.cmd == "refresh":
        result = asyncio.run(refresh_all_tickers())
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif args.cmd == "fetch":
        async def _run() -> dict[str, Any]:
            chart, _ = await build_chart_data(args.ticker, period_days=args.days, max_age_seconds=0)
            return {
                "ticker": chart.ticker,
                "ohlcv_count": chart.ohlcv_count,
                "source": chart.source,
                "snapshot": chart.snapshot,
                "failures": chart.failures,
            }
        result = asyncio.run(_run())
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        parser.print_help()


if __name__ == "__main__":
    _main_cli()
