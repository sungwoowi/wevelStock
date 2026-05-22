"""시장 매크로 collector (INFRA-SNAPSHOT-EXTEND-001 A 카테고리).

market_state_analyzer 의 4축 (지수 위계 / 등락 추세 / breadth / Distribution Day)
결정론 산출을 위해 KOSPI·KOSDAQ 지수의 4축 통계를 일별 계산·적재한다.

흐름:
  1. `compute_market_macro(market)` — DB-first hybrid.
  2. `market_macro_snapshot` 의 오늘 row 존재 시 즉시 반환.
  3. 없으면 `chart_ohlcv` 의 지수 ticker (KOSPI=0001 / KOSDAQ=1001) 일봉 read
     → 월봉 36/60 MA (지수 위계) + 일봉 20/60 MA + slope (등락 추세)
     + Distribution Day 25 일 윈도우 카운트 계산.
  4. KRX backend `market_breadth(market)` 호출 → 상승·하락 종목 수 + ratio.
  5. 4축 종합 → `market_macro_snapshot` 에 upsert.

SLOT 보류:
- S1: Distribution Day 임계 (현재 change_pct ≤ -0.2% + volume > prev) — production 검증 시 정정.
- S5: KIS 지수 chart endpoint — connectors/kis/client.get_daily_chart 의 SLOT.

S4 (KRX breadth bld) = cycle 14.0 KIS volume_rank fallback 으로 봉합 (KRX 400 응답 시
거래대금 상위 30 종목 등락 분포로 대용). breadth_source 메타데이터로 분석가에게 한계 노출.

본 collector 는 KIS 호출을 직접 사용 (S4 fallback). chart_ohlcv 에 적재된 지수 일봉도 read.
지수 적재는 별도 cron (`charts.refresh_all_tickers`) 의 ticker list 확장으로 처리.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from collectors.charts import load_ohlcv_from_db
from connectors.kis import KISClient
from connectors.krx.client import KRXClient
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")

INDEX_TICKER_MAP: dict[str, str] = {
    "KOSPI": "0001",
    "KOSDAQ": "1001",
}

# Distribution Day 임계 — SPEC SLOT S1, production 검증 시 정정.
_DD_CHANGE_PCT_THRESHOLD = -0.2  # 지수 등락률 ≤ -0.2%
_DD_WINDOW_DAYS = 25


# ---------------------------------------------------------------------------
# DataClass
# ---------------------------------------------------------------------------


@dataclass
class MarketMacro:
    """compute_market_macro 결과 — A 카테고리 4축 풀세트."""

    date: str               # "2026-05-21" KST
    market: str             # "KOSPI" | "KOSDAQ"
    # 지수 위계
    index_close: float
    ma_36m: float | None
    ma_60m: float | None
    position: str           # "above_both" | "between" | "below_both"
    # 등락 추세
    ma_20d: float | None
    ma_60d: float | None
    ma20_slope_pct_5d: float | None
    ma60_slope_pct_20d: float | None
    trend: str              # "uptrend" | "sideways" | "downtrend"
    # breadth
    advancing: int | None
    declining: int | None
    unchanged: int | None
    breadth_ratio: float | None
    # Distribution Day
    is_distribution_day: bool
    change_pct: float | None
    volume_change_pct: float | None
    distribution_count_25d: int
    recent_distribution_days: list[dict[str, Any]] = field(default_factory=list)
    source: str = "computed"   # "db" | "computed" | "stale"
    breadth_source: str | None = None  # "krx" | "kis_volrank_top30" | "unavailable" (SLOT S4 fallback)


# ---------------------------------------------------------------------------
# Pure helpers — testable in isolation
# ---------------------------------------------------------------------------


def _position_from_close(close: float, ma36: float | None, ma60: float | None) -> str:
    """지수 위계 분류. 둘 다 None 이면 'between' (모름)."""
    if ma36 is None or ma60 is None:
        return "between"
    lo, hi = (ma60, ma36) if ma60 <= ma36 else (ma36, ma60)
    if close > hi:
        return "above_both"
    if close < lo:
        return "below_both"
    return "between"


def _trend_from_slopes(slope_5d_20: float | None, slope_20d_60: float | None) -> str:
    """등락 추세 분류. 둘 다 양수 = uptrend, 둘 다 음수 = downtrend, 그 외 sideways."""
    if slope_5d_20 is None or slope_20d_60 is None:
        return "sideways"
    if slope_5d_20 > 0 and slope_20d_60 > 0:
        return "uptrend"
    if slope_5d_20 < 0 and slope_20d_60 < 0:
        return "downtrend"
    return "sideways"


def compute_index_hierarchy(daily_df: pd.DataFrame) -> dict[str, Any]:
    """월봉 36·60 MA + 현재가 위계.

    daily_df: index=date(datetime), columns=['close', ...] 정순.
    """
    if daily_df is None or daily_df.empty or "close" not in daily_df.columns:
        return {"index_close": 0.0, "ma_36m": None, "ma_60m": None, "position": "between"}

    # 월말 종가로 리샘플 (월봉 1개 = 그 달 마지막 close)
    monthly = daily_df["close"].resample("ME").last().dropna()
    ma36 = float(monthly.rolling(36).mean().iloc[-1]) if len(monthly) >= 36 else None
    ma60 = float(monthly.rolling(60).mean().iloc[-1]) if len(monthly) >= 60 else None
    current_close = float(daily_df["close"].iloc[-1])
    position = _position_from_close(current_close, ma36, ma60)
    return {
        "index_close": current_close,
        "ma_36m": ma36,
        "ma_60m": ma60,
        "position": position,
    }


def compute_ma_trend(daily_df: pd.DataFrame) -> dict[str, Any]:
    """일봉 20·60 MA + 5일·20일 기울기 % + trend 분류."""
    if daily_df is None or daily_df.empty or "close" not in daily_df.columns:
        return {
            "ma_20d": None, "ma_60d": None,
            "ma20_slope_pct_5d": None, "ma60_slope_pct_20d": None,
            "trend": "sideways",
        }
    close = daily_df["close"]
    ma20_series = close.rolling(20).mean()
    ma60_series = close.rolling(60).mean()
    ma20 = float(ma20_series.iloc[-1]) if not pd.isna(ma20_series.iloc[-1]) else None
    ma60 = float(ma60_series.iloc[-1]) if not pd.isna(ma60_series.iloc[-1]) else None

    # 5일 전 MA20 → 현재 MA20 기울기 %
    slope_5 = None
    if len(ma20_series) >= 6 and not pd.isna(ma20_series.iloc[-6]) and ma20_series.iloc[-6] > 0:
        slope_5 = float((ma20_series.iloc[-1] - ma20_series.iloc[-6]) / ma20_series.iloc[-6] * 100)

    # 20일 전 MA60 → 현재 MA60 기울기 %
    slope_20 = None
    if len(ma60_series) >= 21 and not pd.isna(ma60_series.iloc[-21]) and ma60_series.iloc[-21] > 0:
        slope_20 = float((ma60_series.iloc[-1] - ma60_series.iloc[-21]) / ma60_series.iloc[-21] * 100)

    return {
        "ma_20d": ma20,
        "ma_60d": ma60,
        "ma20_slope_pct_5d": slope_5,
        "ma60_slope_pct_20d": slope_20,
        "trend": _trend_from_slopes(slope_5, slope_20),
    }


def compute_distribution_days(
    daily_df: pd.DataFrame,
    *,
    window: int = _DD_WINDOW_DAYS,
    change_pct_threshold: float = _DD_CHANGE_PCT_THRESHOLD,
) -> dict[str, Any]:
    """최근 window 거래일 Distribution Day 카운트.

    DD 조건 = 지수 change_pct ≤ threshold (-0.2%) AND 거래량 > 전일.
    """
    if daily_df is None or daily_df.empty:
        return {
            "is_distribution_day": False,
            "change_pct": None,
            "volume_change_pct": None,
            "distribution_count_25d": 0,
            "recent_distribution_days": [],
        }

    df = daily_df.tail(window + 1).copy()  # +1 = volume 전일 비교용
    if "change_rate" not in df.columns or "volume" not in df.columns:
        return {
            "is_distribution_day": False,
            "change_pct": None,
            "volume_change_pct": None,
            "distribution_count_25d": 0,
            "recent_distribution_days": [],
        }

    df["prev_volume"] = df["volume"].shift(1)
    df["volume_change_pct"] = (df["volume"] - df["prev_volume"]) / df["prev_volume"] * 100
    df["is_dd"] = (df["change_rate"] <= change_pct_threshold) & (df["volume"] > df["prev_volume"])

    recent = df.iloc[-window:]  # 윈도우 마지막 25개
    dd_count = int(recent["is_dd"].sum())
    recent_dd_rows = recent[recent["is_dd"]].tail(5)
    recent_dd_list = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "change_pct": float(row["change_rate"]),
            "volume_change_pct": float(row["volume_change_pct"]) if not pd.isna(row["volume_change_pct"]) else 0.0,
        }
        for idx, row in recent_dd_rows.iterrows()
    ]

    today_row = recent.iloc[-1]
    is_today_dd = bool(today_row["is_dd"])
    change_pct_today = float(today_row["change_rate"]) if "change_rate" in today_row else None
    vol_chg_today = float(today_row["volume_change_pct"]) if not pd.isna(today_row.get("volume_change_pct")) else None

    return {
        "is_distribution_day": is_today_dd,
        "change_pct": change_pct_today,
        "volume_change_pct": vol_chg_today,
        "distribution_count_25d": dd_count,
        "recent_distribution_days": recent_dd_list,
    }


# ---------------------------------------------------------------------------
# DB layer (market_macro_snapshot 테이블)
# ---------------------------------------------------------------------------


def _get_today_macro(date_str: str, market: str) -> MarketMacro | None:
    """오늘 row 가 있으면 MarketMacro 로 복원, 없으면 None."""
    db = get_db()
    row = db.fetch_one(
        "SELECT * FROM market_macro_snapshot WHERE date = ? AND market = ?",
        (date_str, market),
    )
    if row is None:
        return None
    return MarketMacro(
        date=row["date"],
        market=row["market"],
        index_close=float(row["index_close"]),
        ma_36m=float(row["ma_36m"]) if row["ma_36m"] is not None else None,
        ma_60m=float(row["ma_60m"]) if row["ma_60m"] is not None else None,
        position=row["position"] or "between",
        ma_20d=float(row["ma_20d"]) if row["ma_20d"] is not None else None,
        ma_60d=float(row["ma_60d"]) if row["ma_60d"] is not None else None,
        ma20_slope_pct_5d=float(row["ma20_slope_pct_5d"]) if row["ma20_slope_pct_5d"] is not None else None,
        ma60_slope_pct_20d=float(row["ma60_slope_pct_20d"]) if row["ma60_slope_pct_20d"] is not None else None,
        trend=row["trend"] or "sideways",
        advancing=int(row["advancing"]) if row["advancing"] is not None else None,
        declining=int(row["declining"]) if row["declining"] is not None else None,
        unchanged=int(row["unchanged"]) if row["unchanged"] is not None else None,
        breadth_ratio=float(row["breadth_ratio"]) if row["breadth_ratio"] is not None else None,
        is_distribution_day=bool(row["is_distribution_day"]),
        change_pct=float(row["change_pct"]) if row["change_pct"] is not None else None,
        volume_change_pct=float(row["volume_change_pct"]) if row["volume_change_pct"] is not None else None,
        distribution_count_25d=0,           # DB에 따로 적재 안 함 — 호출 시 compute
        recent_distribution_days=[],
        source="db",
    )


def upsert_market_macro(macro: MarketMacro) -> None:
    """market_macro_snapshot ON CONFLICT REPLACE 멱등 upsert."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO market_macro_snapshot "
            "(date, market, index_close, ma_36m, ma_60m, position, "
            " ma_20d, ma_60d, ma20_slope_pct_5d, ma60_slope_pct_20d, trend, "
            " advancing, declining, unchanged, breadth_ratio, "
            " is_distribution_day, change_pct, volume_change_pct) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date, market) DO UPDATE SET "
            " index_close=excluded.index_close, "
            " ma_36m=excluded.ma_36m, ma_60m=excluded.ma_60m, position=excluded.position, "
            " ma_20d=excluded.ma_20d, ma_60d=excluded.ma_60d, "
            " ma20_slope_pct_5d=excluded.ma20_slope_pct_5d, "
            " ma60_slope_pct_20d=excluded.ma60_slope_pct_20d, trend=excluded.trend, "
            " advancing=excluded.advancing, declining=excluded.declining, "
            " unchanged=excluded.unchanged, breadth_ratio=excluded.breadth_ratio, "
            " is_distribution_day=excluded.is_distribution_day, "
            " change_pct=excluded.change_pct, volume_change_pct=excluded.volume_change_pct",
            (
                macro.date,
                macro.market,
                macro.index_close,
                macro.ma_36m,
                macro.ma_60m,
                macro.position,
                macro.ma_20d,
                macro.ma_60d,
                macro.ma20_slope_pct_5d,
                macro.ma60_slope_pct_20d,
                macro.trend,
                macro.advancing,
                macro.declining,
                macro.unchanged,
                macro.breadth_ratio,
                1 if macro.is_distribution_day else 0,
                macro.change_pct,
                macro.volume_change_pct,
            ),
        )


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------


async def _fetch_breadth_kis_fallback(market: str) -> dict[str, Any]:
    """SLOT S4 fallback — KIS volume_rank top30 의 change_pct 분포로 breadth 대용.

    KRX breadth bld 400 응답 시 사용. 거래대금 상위 30 종목만 본다는 한계 있음
    (전체 시장 breadth 아님). breadth_source="kis_volrank_top30" 메타데이터로
    분석가에게 한계 노출.
    """
    market_upper = market.upper()
    scope = "kospi" if market_upper == "KOSPI" else "kosdaq"
    try:
        async with KISClient() as kis:
            rows = await kis.volume_rank(limit=30, rank_type="amount", market_scope=scope)
    except Exception as exc:
        log.warning("breadth_kis_fallback_failed", market=market_upper, error=str(exc))
        return {
            "advancing": None,
            "declining": None,
            "unchanged": None,
            "breadth_ratio": None,
            "source": "unavailable",
        }

    advancing = sum(1 for r in rows if r.get("change_pct", 0) > 0)
    declining = sum(1 for r in rows if r.get("change_pct", 0) < 0)
    unchanged = sum(1 for r in rows if r.get("change_pct", 0) == 0)
    denom = advancing + declining
    ratio = round(advancing / denom, 4) if denom > 0 else 0.0
    return {
        "advancing": advancing,
        "declining": declining,
        "unchanged": unchanged,
        "breadth_ratio": ratio,
        "source": "kis_volrank_top30",
    }


async def _fetch_breadth(market: str) -> dict[str, Any]:
    """Breadth fetch chain: KRX bld → KIS volume_rank fallback (SLOT S4).

    KRX 성공 시 전체 시장 breadth (정확). 실패 시 KIS 거래대금 상위 30 대용 (한계).
    응답에 source 키 포함하여 호출자가 한계 식별 가능.
    """
    try:
        async with KRXClient() as krx:
            result = await krx.market_breadth(market)
        # KRX 응답이 0 카운트만 돌려주면 (bld 미해소 휴리스틱 실패) fallback.
        if (result.get("advancing", 0) + result.get("declining", 0)) > 0:
            return result
        log.info("breadth_krx_empty_fallback_to_kis", market=market)
    except Exception as exc:
        log.info("breadth_krx_failed_fallback_to_kis", market=market, error=str(exc))

    return await _fetch_breadth_kis_fallback(market)


def _today_kst_str() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


async def compute_market_macro(
    market: str,
    *,
    force_refresh: bool = False,
) -> MarketMacro:
    """A 카테고리 4축 종합 — DB-first hybrid.

    Args:
        market: "KOSPI" | "KOSDAQ"
        force_refresh: True 면 DB hit 무시하고 재계산.

    Returns:
        MarketMacro. chart_ohlcv 부재 시도 부분 발행 (None 필드 + position="between").
    """
    market = market.upper()
    if market not in INDEX_TICKER_MAP:
        raise ValueError(f"market must be 'KOSPI' or 'KOSDAQ', got {market!r}")

    today_str = _today_kst_str()

    if not force_refresh:
        cached = _get_today_macro(today_str, market)
        if cached is not None:
            return cached

    # chart_ohlcv 에서 지수 일봉 read (5년 = 1825 봉)
    ticker = INDEX_TICKER_MAP[market]
    daily_df = load_ohlcv_from_db(ticker, limit=1825)

    hier = compute_index_hierarchy(daily_df)
    trend = compute_ma_trend(daily_df)
    dd = compute_distribution_days(daily_df)
    breadth = await _fetch_breadth(market)

    macro = MarketMacro(
        date=today_str,
        market=market,
        index_close=hier["index_close"],
        ma_36m=hier["ma_36m"],
        ma_60m=hier["ma_60m"],
        position=hier["position"],
        ma_20d=trend["ma_20d"],
        ma_60d=trend["ma_60d"],
        ma20_slope_pct_5d=trend["ma20_slope_pct_5d"],
        ma60_slope_pct_20d=trend["ma60_slope_pct_20d"],
        trend=trend["trend"],
        advancing=breadth.get("advancing") if breadth else None,
        declining=breadth.get("declining") if breadth else None,
        unchanged=breadth.get("unchanged") if breadth else None,
        breadth_ratio=breadth.get("breadth_ratio") if breadth else None,
        breadth_source=breadth.get("source") if breadth else "unavailable",
        is_distribution_day=dd["is_distribution_day"],
        change_pct=dd["change_pct"],
        volume_change_pct=dd["volume_change_pct"],
        distribution_count_25d=dd["distribution_count_25d"],
        recent_distribution_days=dd["recent_distribution_days"],
        source="computed",
    )

    # DB upsert — 부분 발행도 적재 (다음 호출 DB hit)
    try:
        upsert_market_macro(macro)
    except Exception as exc:  # pragma: no cover
        log.warning("market_macro_upsert_failed", market=market, error=str(exc))

    return macro


async def refresh_market_macro_all() -> dict[str, Any]:
    """KOSPI + KOSDAQ 양 시장 compute_market_macro 호출. cron 진입점.

    Returns:
        {"refreshed": ["KOSPI", "KOSDAQ"], "failures": [...]}
    """
    refreshed: list[str] = []
    failures: list[dict[str, str]] = []

    for market in ("KOSPI", "KOSDAQ"):
        try:
            await compute_market_macro(market, force_refresh=True)
            refreshed.append(market)
        except Exception as exc:
            log.warning("refresh_market_macro_failed", market=market, error=str(exc))
            failures.append({"market": market, "error": str(exc)})

    return {
        "refreshed": refreshed,
        "failures": failures,
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
