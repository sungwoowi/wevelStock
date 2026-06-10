"""시장 매크로 collector (INFRA-SNAPSHOT-EXTEND-001 A 카테고리).

market_state_analyzer 의 4축 (지수 위계 / 등락 추세 / breadth / Distribution Day)
결정론 산출을 위해 KOSPI·KOSDAQ 지수의 4축 통계를 일별 계산·적재한다.

흐름:
  1. `compute_market_macro(market)` — DB-first hybrid.
  2. `market_macro_snapshot` 의 오늘 row 존재 시 즉시 반환.
  3. 없으면 `chart_ohlcv` 의 지수 ticker (KOSPI=0001 / KOSDAQ=1001) 일봉 read
     → 월봉 36/60 MA (지수 위계) + 일봉 20/60 MA + slope (등락 추세)
     + Distribution Day 25 일 윈도우 카운트 계산.
  4. KIS `market_breadth(market)` (업종지수 등락종목수) 호출 → 상승·하락 종목 수 + ratio.
  5. 4축 종합 → `market_macro_snapshot` 에 upsert.

SLOT 보류:
- S1: Distribution Day 임계 (현재 change_pct ≤ -0.2% + volume > prev) — production 검증 시 정정.
- S5: KIS 지수 chart endpoint — connectors/kis/client.get_daily_chart 의 SLOT.

breadth source = **KIS inquire-index-price 의 `*_issu_cnt` (전체 시장 정확값, 2026-05-31)**.
구 KRX STAT breadth bld 는 Akamai 봇차단으로 폐기. 실패 시 KIS volume_rank top30 대용으로
강등 (breadth_source 메타데이터로 분석가에게 한계 노출).

본 collector 는 KIS 호출을 직접 사용. chart_ohlcv 에 적재된 지수 일봉도 read.
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


# ---------------------------------------------------------------------------
# 시장 체제 6단계 분류 (CAN SLIM Market Direction — buy_score M축 + rank_candidates regime)
# ---------------------------------------------------------------------------

Regime = str  # "parabolic"|"strong_bull"|"moderate_bull"|"sideways"|"moderate_bear"|"strong_bear"

# 임계 default (SLOT — config/screening.yaml regime_thresholds 로 외부화, production 튜닝).
_DEFAULT_REGIME_THRESHOLDS: dict[str, float] = {
    "parabolic_slope_pct": 3.0,   # ma20 5일 기울기 % 이 이상 = 폭주 후보
    "breadth_strong": 0.55,       # 상승종목 비율 이 이상 = 강한 폭 (parabolic 조건)
    "breadth_weak": 0.40,         # 이 미만 = 폭 좁은 상승 → moderate_bull 강등
    "distribution_ceiling": 5,    # 25일 분산일 이 이상 = 천장 경고 → parabolic 억제
}

# regime → M축 점수 (persona buy_score M 정의: parabolic·strong_bull=10 / moderate_bull=7 / sideways=4 / bear).
_REGIME_SCORE: dict[str, float] = {
    "parabolic": 10.0, "strong_bull": 10.0, "moderate_bull": 7.0,
    "sideways": 4.0, "moderate_bear": 2.0, "strong_bear": 0.0,
}


def _mget(macro: Any, key: str) -> Any:
    """MarketMacro dataclass 또는 dict 양쪽에서 필드 read."""
    if isinstance(macro, dict):
        return macro.get(key)
    return getattr(macro, key, None)


def classify_market_regime(
    macro: Any,
    *,
    thresholds: dict[str, float] | None = None,
) -> Regime:
    """시장 체제 6단계 결정론 분류 (예측 X — **현재 상태 라벨링**).

    3 계층 신호 조합 (오닐 CAN SLIM Market Direction):
        장기 골격 = position(월봉 36·60MA 대비) / 중기 방향 = trend(일봉 20·60 기울기) +
        ma20 기울기 강도 / 강도·천장 = breadth_ratio(상승종목 폭) + distribution_count(기관 분산일).

    Args:
        macro: MarketMacro 또는 snapshot.market_macro dict (position/trend/ma20_slope_pct_5d/
               breadth_ratio/distribution_count_25d).
        thresholds: 임계 DI (config/screening.yaml). None → _DEFAULT (SLOT).

    Returns:
        6 regime 중 하나. position/trend 부재(데이터 부족) → "sideways"(모름).
    """
    th = {**_DEFAULT_REGIME_THRESHOLDS, **(thresholds or {})}
    position = _mget(macro, "position")
    trend = _mget(macro, "trend")
    slope = _mget(macro, "ma20_slope_pct_5d")
    breadth = _mget(macro, "breadth_ratio")
    dist = _mget(macro, "distribution_count_25d") or 0

    if position is None or trend is None:
        return "sideways"

    if trend == "downtrend":
        return "strong_bear" if position == "below_both" else "moderate_bear"
    if trend == "sideways":
        return "sideways"

    # uptrend
    if position == "above_both":
        if breadth is not None and breadth < th["breadth_weak"]:
            return "moderate_bull"   # 폭 좁은 상승 = 약한 강세
        parabolic_ok = (
            slope is not None and slope >= th["parabolic_slope_pct"]
            and (breadth is None or breadth >= th["breadth_strong"])
            and dist < th["distribution_ceiling"]   # 분산일 多 → parabolic 억제
        )
        return "parabolic" if parabolic_ok else "strong_bull"
    # uptrend 이나 장기선 회복 중 (between/below_both) = 완만한 강세
    return "moderate_bull"


def regime_to_score(regime: Regime | None) -> float:
    """regime → M축 0~10 점수 (buy_score). 미지정/미정의 → 4.0(중립 sideways)."""
    return _REGIME_SCORE.get(regime or "", 4.0)


# 거시 변곡점 DD 임계 — 박종훈 frame (wealth_strategist) 게이팅 입력.
# 변곡점 3 케이스 중 결정론 판정 가능한 2개만: regime 전환 / DD 4건+.
# ("사이클 단계 변화" 는 LLM 영역 — 결정론 제외.)
_INFLECTION_DD_THRESHOLD = 4

_INFLECTION_ROW_COLUMNS = (
    "date, position, trend, ma20_slope_pct_5d, breadth_ratio, distribution_count_25d"
)


def is_macro_inflection(
    *, market: str = "KOSPI", date_str: str | None = None
) -> tuple[bool, str]:
    """거시 변곡점 결정론 판정 — 박종훈 frame 사용 게이팅의 입력.

    wealth_strategist 의 거시 frame 은 설계상 보수적이라 평상시 트레이딩 verdict 의
    직접 근거로 쓰면 매매 마비를 유발한다. 변곡점일 때만 frame 을 전면 반영하도록
    전략가 주입 블록에 사용 지침을 붙이는데, "지금이 변곡점인가" 가 이 함수다.

    변곡점 = (a) regime 전환 (기준일 스냅샷 regime ≠ 직전 영업일 스냅샷 regime)
           or (b) Distribution Day 25일 카운트 ≥ 4 (기관 분산 천장 경고).

    Args:
        market: "KOSPI" | "KOSDAQ".
        date_str: 기준일 "YYYY-MM-DD". None → 스냅샷 최신 행 (백테스팅 친화 cutoff).

    Returns:
        (변곡점 여부, 사유 문자열). 스냅샷 부재 → (False, ...) 보수적 평상시.
        직전 행 부재(첫날) → regime 전환 판정 skip, DD 만 본다.
    """
    db = get_db()
    if date_str is None:
        cur = db.fetch_one(
            f"SELECT {_INFLECTION_ROW_COLUMNS} FROM market_macro_snapshot "
            "WHERE market = ? ORDER BY date DESC LIMIT 1",
            (market,),
        )
    else:
        cur = db.fetch_one(
            f"SELECT {_INFLECTION_ROW_COLUMNS} FROM market_macro_snapshot "
            "WHERE market = ? AND date <= ? ORDER BY date DESC LIMIT 1",
            (market, date_str),
        )
    if cur is None:
        return False, "macro 스냅샷 없음 — 평상시 간주"

    cur_d = dict(cur)
    cur_regime = classify_market_regime(cur_d)
    dd = int(cur_d.get("distribution_count_25d") or 0)
    reasons: list[str] = []

    prev = db.fetch_one(
        f"SELECT {_INFLECTION_ROW_COLUMNS} FROM market_macro_snapshot "
        "WHERE market = ? AND date < ? ORDER BY date DESC LIMIT 1",
        (market, cur_d["date"]),
    )
    if prev is not None:
        prev_d = dict(prev)
        prev_regime = classify_market_regime(prev_d)
        if prev_regime != cur_regime:
            reasons.append(
                f"regime 전환 {prev_regime}→{cur_regime} "
                f"({prev_d['date']}→{cur_d['date']})"
            )
    if dd >= _INFLECTION_DD_THRESHOLD:
        reasons.append(
            f"Distribution Day {dd}건/25일 (임계 {_INFLECTION_DD_THRESHOLD}+)"
        )
    if reasons:
        return True, " + ".join(reasons)
    return False, f"평상시 (regime={cur_regime}, DD={dd}건)"


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
        # v9 — 영속된 분산일 카운트 + breadth 출처 복원 (computed run 과 일치).
        #   pre-v9 row 는 NULL → 0/None (이전 하드코드와 동일). recent_distribution_days(상세 리스트)는
        #   regime/scoring 미사용이라 캐시 복원 시 빈 리스트 유지.
        distribution_count_25d=int(row["distribution_count_25d"]) if row["distribution_count_25d"] is not None else 0,
        recent_distribution_days=[],
        source="db",
        breadth_source=row["breadth_source"],
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
            " is_distribution_day, change_pct, volume_change_pct, "
            " distribution_count_25d, breadth_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date, market) DO UPDATE SET "
            " index_close=excluded.index_close, "
            " ma_36m=excluded.ma_36m, ma_60m=excluded.ma_60m, position=excluded.position, "
            " ma_20d=excluded.ma_20d, ma_60d=excluded.ma_60d, "
            " ma20_slope_pct_5d=excluded.ma20_slope_pct_5d, "
            " ma60_slope_pct_20d=excluded.ma60_slope_pct_20d, trend=excluded.trend, "
            " advancing=excluded.advancing, declining=excluded.declining, "
            " unchanged=excluded.unchanged, breadth_ratio=excluded.breadth_ratio, "
            " is_distribution_day=excluded.is_distribution_day, "
            " change_pct=excluded.change_pct, volume_change_pct=excluded.volume_change_pct, "
            " distribution_count_25d=excluded.distribution_count_25d, "
            " breadth_source=excluded.breadth_source",
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
                macro.distribution_count_25d,
                macro.breadth_source,
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
    """Breadth fetch chain: KIS 업종지수 등락종목수(전체 시장·정확) → KIS volume_rank top30(대용).

    KRX STAT breadth bld 는 Akamai 봇차단(getJsonData STAT 전 카테고리 "LOGOUT")으로 폐기
    (2026-05-31). KIS inquire-index-price 의 `*_issu_cnt` 가 전체 시장 상승/하락/보합 종목수를
    직접 제공한다 (top30 대용 대비 정확). 응답 source 키로 호출자가 한계 식별:
    kis_index(정확) / kis_volrank_top30(대용) / unavailable.
    """
    try:
        async with KISClient() as kis:
            result = await kis.market_breadth(market)
        if (result.get("advancing") or 0) + (result.get("declining") or 0) > 0:
            return result
        log.info("breadth_kis_index_empty_fallback_to_volrank", market=market)
    except Exception as exc:  # noqa: BLE001
        log.info("breadth_kis_index_failed_fallback_to_volrank", market=market, error=str(exc))

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
