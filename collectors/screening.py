"""종목 스크리닝 RS + 과열도 orchestrator (SCREEN-RS-EXTENSION-001).

stock_picker 의 S-Score `rs` 축 + buy_score `L`(Leader) 축의 결정론 base.
후보 풀 각 종목의 일봉(chart_ohlcv)에서 60일 수익률·MA20·ADR 을 계산하고,
오닐식 상대강도(풀 내 백분위) + 과열도(ADR 정규화) + regime 가중 합성으로 랭킹한다.

패턴 = collectors/sector_rs.py 1:1 mirror (lazy compute, DB 저장 X — 호출 시점 read 만).
config = config/screening.yaml (하드코딩 금지, watchdog hot reload). 로더는 본 모듈 내부.

cutoff_date 지정 시 그 시점까지 OHLCV 만 read → 과거 임의 시점 스크리닝 재현 (백테스팅 친화,
feedback_backtest_essence). 모든 scoring 함수는 순수 (collectors.scoring).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from collectors.charts import load_ohlcv_from_db
from collectors.scoring import extension_score, screening_score, stock_rs_score
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENING_PATH = REPO_ROOT / "config" / "screening.yaml"

_CONFIG_CACHE: dict[str, Any] | None = None

_DEFAULTS: dict[str, Any] = {
    "rs_window": 60,
    "k": 1.0,
    "adr_window": 14,
    "regime_weights": {},
}


# ---------------------------------------------------------------------------
# config 로더 (score_inputs_config.py 패턴 mirror — 모듈 캐시 + reload)
# ---------------------------------------------------------------------------


def _load_screening_config() -> dict[str, Any]:
    """config/screening.yaml 로드 (캐시). 부재·파싱 실패 시 default fallback."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        if not SCREENING_PATH.exists():
            log.warning("screening_config_missing", path=str(SCREENING_PATH))
            _CONFIG_CACHE = dict(_DEFAULTS)
        else:
            try:
                loaded = yaml.safe_load(SCREENING_PATH.read_text(encoding="utf-8")) or {}
                _CONFIG_CACHE = {**_DEFAULTS, **loaded}
            except Exception as e:  # noqa: BLE001
                log.warning("screening_config_load_failed", error=str(e))
                _CONFIG_CACHE = dict(_DEFAULTS)
    return _CONFIG_CACHE


def reload_screening_config() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def get_rs_window() -> int:
    try:
        return int(_load_screening_config().get("rs_window", 60))
    except (TypeError, ValueError):
        return 60


def get_k() -> float:
    try:
        return float(_load_screening_config().get("k", 1.0))
    except (TypeError, ValueError):
        return 1.0


def get_adr_window() -> int:
    try:
        return int(_load_screening_config().get("adr_window", 14))
    except (TypeError, ValueError):
        return 14


def get_regime_thresholds() -> dict[str, float]:
    """시장 체제 분류 임계 (market_macro.classify_market_regime DI). 부재 시 빈 dict→함수 default."""
    raw = _load_screening_config().get("regime_thresholds") or {}
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    return out


def get_regime_weights() -> dict[str, dict[str, float]]:
    raw = _load_screening_config().get("regime_weights") or {}
    out: dict[str, dict[str, float]] = {}
    if isinstance(raw, dict):
        for regime, w in raw.items():
            if isinstance(w, dict):
                try:
                    out[str(regime)] = {
                        "w_rs": float(w.get("w_rs", 0.5)),
                        "w_ext": float(w.get("w_ext", 0.5)),
                    }
                except (TypeError, ValueError):
                    continue
    return out


# ---------------------------------------------------------------------------
# 종목 지표 산출 (순수 — df → return_60d / price / ma20 / adr)
# ---------------------------------------------------------------------------


def _slice_to_cutoff(df: pd.DataFrame, cutoff_date: str | None) -> pd.DataFrame:
    """cutoff_date(YYYY-MM-DD) 이하 봉만. 빈/미지정 시 원본."""
    if df is None or df.empty or not cutoff_date:
        return df
    try:
        return df[df.index <= pd.Timestamp(cutoff_date)]
    except Exception:  # noqa: BLE001
        return df


def compute_stock_metrics(
    df: pd.DataFrame,
    *,
    rs_window: int = 60,
    adr_window: int = 14,
) -> dict[str, float | None]:
    """일봉 df → {return_60d, price, ma20, adr}. 데이터 부족 시 해당 키 None.

    순수 (df 입력만). return_60d 는 최근 rs_window 봉 close 수익률 %,
    ma20 = 최근 20봉 close 평균, adr = 최근 adr_window 봉 (high-low)/close 평균.
    """
    out: dict[str, float | None] = {
        "return_60d": None,
        "price": None,
        "ma20": None,
        "adr": None,
    }
    if df is None or df.empty or "close" not in df.columns:
        return out

    close = df["close"]
    out["price"] = float(close.iloc[-1])

    # 60일 수익률 (%)
    if len(close) >= rs_window:
        start = close.iloc[-rs_window]
        if start is not None and start > 0:
            out["return_60d"] = float((close.iloc[-1] - start) / start * 100)

    # MA20
    if len(close) >= 20:
        out["ma20"] = float(close.iloc[-20:].mean())

    # ADR = mean((high - low) / close) 최근 adr_window 봉
    if {"high", "low"}.issubset(df.columns) and len(df) >= 1:
        tail = df.iloc[-adr_window:]
        rng = (tail["high"] - tail["low"]) / tail["close"]
        rng = rng.replace([float("inf"), float("-inf")], pd.NA).dropna()
        if len(rng) > 0:
            out["adr"] = float(rng.mean())

    return out


# ---------------------------------------------------------------------------
# orchestrator — rank_candidates (screening-rank-v1)
# ---------------------------------------------------------------------------


def rank_candidates(
    tickers: list[str],
    regime: str | None,
    *,
    cutoff_date: str | None = None,
) -> list[dict[str, Any]]:
    """후보 풀 종목별 RS + 과열도 + regime 가중 합성 → 랭킹 (screening-rank-v1).

    Args:
        tickers: 스크리닝 대상 universe (호출부 제공).
        regime: 시장 체제 6단계 중 하나. None/미정의 → 균등 가중 fallback.
        cutoff_date: 지정 시 그 시점까지 OHLCV 만 (백테스팅 재현).

    Returns:
        종목별 dict 리스트. 각 = {ticker, rs_score, extension_score, screening_score,
        rank, reason}. screening_score 내림차순 정렬 (산출 가능 종목 우선), 랭킹 불가
        종목(60일 데이터 부족)은 rank=None + reason 으로 뒤에. DB 저장 X.
    """
    rs_window = get_rs_window()
    adr_window = get_adr_window()
    k = get_k()
    weights = get_regime_weights()
    regime_key = regime or ""

    # 1) 각 종목 지표 산출
    metrics: dict[str, dict[str, float | None]] = {}
    for ticker in tickers:
        df = load_ohlcv_from_db(ticker, limit=rs_window + 10)
        df = _slice_to_cutoff(df, cutoff_date)
        metrics[ticker] = compute_stock_metrics(
            df, rs_window=rs_window, adr_window=adr_window
        )

    # 2) 후보 풀 60일 수익률 (rs 백분위 정규화 입력 — 자신 포함)
    pool_returns = [
        m["return_60d"] for m in metrics.values() if m["return_60d"] is not None
    ]

    ranked: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for ticker in tickers:
        m = metrics[ticker]
        ret = m["return_60d"]
        if ret is None:
            excluded.append({
                "ticker": ticker,
                "rs_score": None,
                "extension_score": None,
                "screening_score": None,
                "rank": None,
                "reason": "60일 데이터 부족 (랭킹 제외)",
            })
            continue

        rs = stock_rs_score(ret, pool_returns)
        ext = extension_score(m["price"], m["ma20"], m["adr"], k=k)
        ext_axis = ext if ext is not None else 5.0
        score = screening_score(rs, ext_axis, regime_key, weights)
        reason = "" if ext is not None else "과열도 미산출 → 중립 5.0"
        ranked.append({
            "ticker": ticker,
            "rs_score": rs,
            "extension_score": ext,
            "screening_score": score,
            "rank": None,  # 정렬 후 부여
            "reason": reason,
        })

    # 3) screening_score 내림차순 정렬 + rank 부여 (동점 시 ticker 안정 정렬)
    ranked.sort(key=lambda r: (-r["screening_score"], r["ticker"]))
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx

    return ranked + excluded
