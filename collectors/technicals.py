"""T-Score 원시 지표 collector (INFRA-SCORE-INPUTS-001).

trader 의 타점(T-Score) 판단 입력 = 원시 기술 지표(이격도·MACD·거래량비·R/R)를
결정론 계산해 md 블록으로 주입한다. **점수를 기계가 매기지 않는다** — 원시 지표가 권위,
advisory T-Score 는 참고선(LLM override 가능). (메모리 feedback_score_collapse_advisory)

원시 지표는 `collectors/charts.py::compute_indicators` 가 이미 산출하는 값을 재사용
(MA20·MACD·거래량 spike) → 본 모듈은 T-Score 프레이밍 + advisory collapse 만 얇게 더한다.

흐름:
  1. `build_technicals_md(ticker, cutoff_date=None)` async — charts DB-first 로 OHLCV 확보
     → compute_indicators → compute_technical_inputs(순수) → render_technicals_md.
  2. run_analyst `_maybe_build_technicals_md` (trader) 가 호출, α 패턴 mirror.

cutoff_date: 지정 시 그 시점까지 OHLCV 만 사용 → 백테스팅 재현 (feedback_backtest_essence).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from collectors.scoring import map_to_axis, t_score
from core.logging import get_logger

log = get_logger(__name__)

_AXES = ("divergence", "macd", "volume", "rr")


@dataclass
class TechnicalInputs:
    """T-Score 원시 지표 + advisory 점수 묶음. 원시 = 권위, advisory = 참고선."""

    ticker: str
    # 원시 지표 (LLM 주입 = 권위)
    divergence_pct: float | None          # 이격도 % = (close-ma20)/ma20*100
    macd: dict[str, Any]                   # {macd, signal, histogram, norm}
    volume_ratio: float | None            # today / ma20
    rr: float | None                      # R/R 비율 (SLOT S3)
    alpha: float | None                   # 가속계수 (WAVE-ALPHA, override 입력)
    # advisory 0~10 축 (참고선, override 가능)
    divergence_score: float | None
    macd_score: float | None
    volume_score: float | None
    rr_score: float | None
    advisory_t_score: float | None
    reasons: list[str] = field(default_factory=list)
    source: str = "db"
    cutoff_date: str | None = None


def _bps(
    breakpoints: dict[str, list[tuple[float, float]]] | None,
    axis: str,
) -> list[tuple[float, float]]:
    """축 breakpoints 해결 — 명시 DI 우선, 없으면 config."""
    if breakpoints is not None and axis in breakpoints:
        return breakpoints[axis]
    from collectors.score_inputs_config import get_breakpoints

    return get_breakpoints("technicals", axis)


def _map(value: float | None, bps: list[tuple[float, float]]) -> float | None:
    if value is None or not bps:
        return None
    return map_to_axis(value, bps)


def compute_technical_inputs(
    indicators: dict[str, Any],
    current_price: float | None,
    *,
    alpha: float | None = None,
    rr: float | None = None,
    breakpoints: dict[str, list[tuple[float, float]]] | None = None,
    ticker: str = "",
    source: str = "db",
    cutoff_date: str | None = None,
) -> TechnicalInputs:
    """순수 — charts.compute_indicators 결과 + 현재가 → T-Score 원시 지표 + advisory.

    Args:
        indicators: charts.compute_indicators 출력 (daily_ma.ma20 / macd / volume).
        current_price: 현재가 (이격도 산출 기준). None 이면 indicators.current_close.
        alpha: 가속계수 (advisory t_score α override, STRATEGY-TRACK-001). None → 0(override 없음).
        rr: R/R 비율 (SLOT S3, 호출부 산출). None → advisory 에서 중립 처리.
        breakpoints: 축 매핑 DI ({axis: [(x,y)...]}). None → config.
    """
    reasons: list[str] = []
    price = current_price if current_price is not None else indicators.get("current_close")

    # 1) 이격도 % = (close - ma20) / ma20 * 100
    ma20 = (indicators.get("daily_ma") or {}).get("ma20")
    if price is not None and ma20:
        divergence_pct = (price - ma20) / ma20 * 100
    else:
        divergence_pct = None
        reasons.append("이격도 미산출 (ma20 또는 현재가 부재)")

    # 2) MACD — histogram 정규화 = hist / price * 1000 (per-mille, 가격 스케일 흡수)
    macd_raw = dict(indicators.get("macd") or {})
    hist = macd_raw.get("histogram")
    if hist is not None and price:
        macd_norm = hist / price * 1000
    else:
        macd_norm = None
        if hist is None:
            reasons.append("MACD 미산출 (데이터 부족)")
    macd_raw["norm"] = macd_norm

    # 3) 거래량 배율
    volume_ratio = (indicators.get("volume") or {}).get("spike_ratio")
    if volume_ratio is None:
        reasons.append("거래량 배율 미산출 (20일 이평 부족)")

    # 4) 축 매핑 (advisory 입력)
    divergence_score = _map(divergence_pct, _bps(breakpoints, "divergence"))
    macd_score = _map(macd_norm, _bps(breakpoints, "macd"))
    volume_score = _map(volume_ratio, _bps(breakpoints, "volume"))
    rr_score = _map(rr, _bps(breakpoints, "rr"))

    # 5) advisory t_score (참고선) — 핵심 3축(이격도·MACD·거래량) 있을 때만
    advisory_t_score: float | None = None
    if None not in (divergence_score, macd_score, volume_score):
        rr_axis = rr_score
        if rr_axis is None:
            rr_axis = 5.0  # R/R 미산출 → 중립 (advisory 참고선이라 허용)
            reasons.append("R/R 미산출 → advisory 중립 5.0 (SLOT S3)")
        advisory_t_score = t_score(
            divergence_score, macd_score, volume_score, rr_axis, alpha or 0.0,
        )

    return TechnicalInputs(
        ticker=ticker,
        divergence_pct=divergence_pct,
        macd=macd_raw,
        volume_ratio=volume_ratio,
        rr=rr,
        alpha=alpha,
        divergence_score=divergence_score,
        macd_score=macd_score,
        volume_score=volume_score,
        rr_score=rr_score,
        advisory_t_score=advisory_t_score,
        reasons=reasons,
        source=source,
        cutoff_date=cutoff_date,
    )


# ---------------------------------------------------------------------------
# Async builder — charts DB-first 재사용 (+ cutoff_date 백테스팅)
# ---------------------------------------------------------------------------


async def build_technicals(
    ticker: str,
    *,
    cutoff_date: str | None = None,
    alpha: float | None = None,
    kis: Any | None = None,
) -> TechnicalInputs:
    """OHLCV 확보(charts DB-first) → 지표 계산 → T-Score 원시 지표.

    cutoff_date(YYYY-MM-DD) 지정 시 그 시점까지 DB OHLCV 만 사용 (백테스팅 재현).
    미지정 시 charts.build_chart_data (DB-first + KIS fallback + on-demand snapshot).
    R/R 은 SLOT S3 미배선 → None (advisory 중립). α 는 호출부가 주입 (override 입력).
    """
    from collectors import charts

    if cutoff_date:
        df = charts.load_ohlcv_from_db(ticker)
        if len(df):
            df = df[df.index <= pd.Timestamp(cutoff_date)]
        indicators = charts.compute_indicators(df) if len(df) else {"reasons": ["ohlcv 부재"]}
        price = indicators.get("current_close")
        source = f"db@{cutoff_date}"
    else:
        chart, _ = await charts.build_chart_data(ticker, kis=kis)
        indicators = chart.indicators
        price = (chart.snapshot or {}).get("current_price") or indicators.get("current_close")
        source = chart.source

    return compute_technical_inputs(
        indicators, price, alpha=alpha, ticker=ticker, source=source, cutoff_date=cutoff_date,
    )


async def build_technicals_md(
    ticker: str,
    *,
    cutoff_date: str | None = None,
    alpha: float | None = None,
    kis: Any | None = None,
) -> str | None:
    """trader 프롬프트 주입용 md. 실패 시 None (크래시 금지, α 패턴 mirror)."""
    try:
        ti = await build_technicals(ticker, cutoff_date=cutoff_date, alpha=alpha, kis=kis)
    except Exception as e:  # noqa: BLE001
        log.warning("technicals_build_failed", ticker=ticker, error=str(e))
        return None
    return render_technicals_md(ti)


def _fmt(v: float | None, suffix: str = "", *, plus: bool = False) -> str:
    if v is None:
        return "null"
    fmt = f"{v:+.2f}" if plus else f"{v:.2f}"
    return f"{fmt}{suffix}"


def render_technicals_md(ti: TechnicalInputs, *, name: str | None = None) -> str:
    """`score-inputs-v1` md 블록 — 원시 지표 표(권위) + advisory T-Score(참고선).

    LLM(trader)이 원시 지표로 직접 타점을 판단한다. advisory 는 참고선일 뿐 override 가능.
    """
    name_part = f" ({name})" if name else ""
    cutoff = f" | cutoff: {ti.cutoff_date}" if ti.cutoff_date else ""
    lines: list[str] = []
    lines.append("## [5b] 타점 입력 지표 (INFRA-SCORE-INPUTS-001 · T-Score)")
    lines.append("")
    lines.append(f"**Ticker**: {ti.ticker}{name_part} | **출처**: {ti.source}{cutoff}")
    lines.append("")
    lines.append("### 원시 기술 지표 (이 값으로 직접 판단)")
    lines.append("| 지표 | 값 |")
    lines.append("|---|---|")
    lines.append(f"| 이격도 (MA20 대비) | {_fmt(ti.divergence_pct, '%', plus=True)} |")
    lines.append(
        f"| MACD (hist / signal) | {_fmt(ti.macd.get('histogram'))} / {_fmt(ti.macd.get('signal'))} |"
    )
    lines.append(
        f"| 거래량 배율 (20일 이평) | {_fmt(ti.volume_ratio, '×') if ti.volume_ratio is not None else 'null'} |"
    )
    lines.append(f"| R/R 비율 | {_fmt(ti.rr) if ti.rr is not None else 'null (SLOT S3)'} |")
    if ti.alpha is not None:
        lines.append(f"| α 가속계수 | {_fmt(ti.alpha)} |")
    lines.append("")
    adv = "null" if ti.advisory_t_score is None else f"{ti.advisory_t_score:.1f}"
    lines.append(
        f"> **advisory T-Score: {adv}** — 참고선일 뿐이며 권위 아님. "
        f"위 원시 지표 + α + 시장 맥락으로 **본인이 직접 타점을 판단**하고 advisory 와 다르면 override 하라."
    )
    if ti.reasons:
        lines.append("")
        lines.append("_부분 산출: " + "; ".join(ti.reasons) + "_")
    return "\n".join(lines)
