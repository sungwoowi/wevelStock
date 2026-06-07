"""buy_score 원시 지표 collector (INFRA-SCORE-INPUTS-001 v3 / CAN SLIM 7축).

stock_picker 의 매수(buy_score, Track B) 판단 입력 = CAN SLIM 7축 원시 지표를 결정론 계산해
md 블록으로 주입한다. **점수를 기계가 collapse 하지 않는다** — 원시 지표가 권위(LLM 주입),
advisory buy_score 는 참고선(override 가능, 메모리 feedback_score_collapse_advisory).

7축 (C·A·N·S·L·I·M) 소싱 (사용자 결정 = collector 직접 호출 + regime 분류기):
    C(현재 분기 EPS YoY) — fundamentals.quarterly_eps[0] vs [4] (실측)
    A(연간 EPS 3년) — fundamentals.annual_eps YoY (yfinance income_stmt, ≥3년) — 실측, <3년 중립
    N(52주 신고가)       — charts.compute_indicators fifty_two_week.pct_from_high (실측, 뉴스부 0시드)
    S(수급)              — flow_inputs.inflow_score (외인·기관 자금 유입, collector 직접 호출)
    L(주도주)            — screening.rank_candidates screening_score (RS+과열도)
    I(기관)              — flow_inputs.net_sums institution 비중 (collector 직접 호출)
    M(시장 방향)         — market_macro.classify_market_regime → regime_to_score

cross-agent 축(S/I/M) = collector 직접 호출(분석가 import 아님 → 절대원칙 1 준수).
narrow breadth(시총 상위 쏠림) regime 은 moderate_bull 보수 라벨 + breadth/분산일 원시값 노출
→ "구조적 성장 vs 천장 디버전스" 판단은 LLM (사용자 결정).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from collectors.market_macro import classify_market_regime, regime_to_score
from collectors.scoring import buy_score, map_to_axis
from core.logging import get_logger

log = get_logger(__name__)

_NEUTRAL = 5.0


@dataclass
class BuyScoreInputs:
    """buy_score CAN SLIM 7축 원시 지표 + advisory 점수. 원시 = 권위, advisory = 참고선."""

    ticker: str
    # 원시 지표 (LLM 주입 = 권위)
    eps_yoy_pct: float | None        # C: 분기 EPS YoY %
    annual_eps_yoy_pct: float | None  # A: 연간 EPS YoY %
    annual_eps: list[float | None]    # A: 연간 EPS 4년 recent-first (가속/일관성 raw)
    high_proximity_pct: float | None  # N: 52주 고가 대비 이격 % (0=신고가)
    inflow_speed_raw: float | None    # S: 외인+기관 자금 유입 bp (누적 level)
    demand_momentum: float | None     # S: 최근 수급 turnaround 점수 (이벤트 포착)
    volume_spike: float | None        # S: 거래량 동반 (오늘/20일평균)
    institution_ratio: float | None   # I: 기관 net 비중 -1..+1
    regime: str | None                # M: 시장 체제 6단계 라벨
    breadth_ratio: float | None       # M 맥락: 시장 폭 (narrow breadth 노출)
    distribution_count: int | None    # M 맥락: 25일 기관 분산일 (천장 경고 노출)
    screening_score: float | None     # L: RS+과열도 합성 (rank_candidates)
    # 7축 0~10 점수
    c: float
    a: float
    n: float
    s: float
    l: float
    i: float
    m: float
    advisory_buy_score: float | None
    reasons: list[str] = field(default_factory=list)
    source: str = "db"
    cutoff_date: str | None = None
    # 축별 산출 출처 (실측 vs 중립)
    axis_source: dict[str, str] = field(default_factory=dict)


def _bps(group: str, axis: str) -> list[tuple[float, float]]:
    from collectors.score_inputs_config import get_breakpoints

    return get_breakpoints(group, axis)


def compute_eps_yoy(quarterly_eps: list[float | None] | None) -> float | None:
    """분기 EPS YoY % — 최근 분기[0] vs 전년 동기[4]. 데이터 부족 시 None.

    yoy = (eps[0] - eps[4]) / |eps[4]| × 100. eps[4]=0 또는 부재 → None.
    """
    if not quarterly_eps or len(quarterly_eps) < 5:
        return None
    cur, base = quarterly_eps[0], quarterly_eps[4]
    if cur is None or base is None or base == 0:
        return None
    return (cur - base) / abs(base) * 100.0


def compute_annual_eps_yoy(annual_eps: list[float | None] | None) -> float | None:
    """연간 EPS YoY % — 최근 회계연도[0] vs 전년[1]. CAN SLIM A (≥3년 시계열 요구).

    yoy = (eps[0] - eps[1]) / |eps[1]| × 100. **≥3년** 데이터(다년 추세 확인 가능)와
    [0]·[1] 유효성 필수 — 부족 시 None(중립). 가속/3년 일관성 판단은 md 원시 시계열로 LLM.
    """
    if not annual_eps or len(annual_eps) < 3:
        return None
    cur, base = annual_eps[0], annual_eps[1]
    if cur is None or base is None or base == 0:
        return None
    return (cur - base) / abs(base) * 100.0


def compute_demand_score(
    momentum_score: float | None,
    inflow_score: float | None,
    volume_confirm_score: float | None,
    weights: dict[str, float],
) -> float | None:
    """S(수급) demand composite — 최근 momentum + 누적 inflow + 거래량 동반 가중 블렌드 (순수).

    누적 level(inflow)만 보면 하루짜리 대량 수급 전환(이벤트)을 놓침 → momentum 이 이벤트 포착,
    volume 이 수요 진위 확증. 결측 컴포넌트는 평가 제외 후 재정규화(비례). 전부 결측 → None.
    """
    pairs = [
        (momentum_score, weights.get("momentum", 0.45)),
        (inflow_score, weights.get("inflow", 0.30)),
        (volume_confirm_score, weights.get("volume", 0.25)),
    ]
    num = 0.0
    wsum = 0.0
    for val, w in pairs:
        if val is not None:
            num += w * val
            wsum += w
    if wsum <= 0:
        return None
    from collectors.scoring import _clamp, _round_to_half

    return _clamp(_round_to_half(num / wsum))


def _news_catalyst_to_score(tilt: dict | None, blend_cfg: dict) -> float | None:
    """catalyst_tilt {direction, strength} → 0~10 (config tilt_scores). neutral→5, 미매핑→None."""
    if not tilt:
        return None
    table = blend_cfg.get("tilt_scores") or {}
    direction = tilt.get("direction", "neutral")
    if direction == "neutral":
        return float(table.get("neutral", 5.0))
    band = table.get(direction)
    if not isinstance(band, dict):
        return None
    return float(band.get(tilt.get("strength", "weak"), 5.0))


def _blend_news_catalyst(
    n_high: float,
    ticker_s: str,
    cutoff_date: str | None,
    axis_source: dict[str, str],
    reasons: list[str],
) -> float:
    """N축 = 52주 신고가(n_high) + 종목 scope 뉴스 catalyst_tilt 가중 블렌드 (NEWS-SOURCE-001 M7).

    뉴스 없으면(미수집/중립/실패) n_high 그대로 반환(현 동작 보존, graceful).
    가중 합은 정규화(÷(w_high+w_news)) — config 가중이 1 합 아니어도 안전.
    """
    try:
        from collectors.market_view import _today_kst_str
        from collectors.news_source import build_news_digest, load_news_source_config
        from collectors.scoring import _clamp, _round_to_half

        blend_cfg = (load_news_source_config().get("digest") or {}).get("n_axis_blend") or {}
        nd = build_news_digest(cutoff_date or _today_kst_str(), ticker=ticker_s, persist=False)
        if nd.source == "empty":
            reasons.append("N 뉴스 촉매 없음 — 52주 신고가만 (오늘 종목 뉴스 미분류)")
            return n_high
        n_news = _news_catalyst_to_score(nd.catalyst_tilt, blend_cfg)
        if n_news is None:
            reasons.append("N 뉴스 촉매 중립 — 52주 신고가만")
            return n_high
        w_high = float(blend_cfg.get("high_weight", 0.6))
        w_news = float(blend_cfg.get("news_weight", 0.4))
        wsum = w_high + w_news if (w_high + w_news) > 0 else 1.0
        blended = _clamp(_round_to_half((w_high * n_high + w_news * n_news) / wsum))
        axis_source["n"] = (
            axis_source["n"] + "+news_tilt"
            if axis_source["n"] != "neutral_fallback"
            else "news_tilt"
        )
        tilt = nd.catalyst_tilt
        reasons.append(
            f"N 뉴스 촉매 블렌드: 신고가 {n_high:.1f}×{w_high} + "
            f"촉매({tilt.get('direction')}/{tilt.get('strength')}={n_news:.1f})×{w_news} → {blended:.1f}"
        )
        return blended
    except Exception as e:  # noqa: BLE001
        log.warning("buyscore_news_blend_failed", ticker=ticker_s, error=str(e))
        reasons.append("N 뉴스 촉매 블렌드 실패 — 52주 신고가만")
        return n_high


def compute_institution_ratio(net_sums: dict[str, int] | None) -> float | None:
    """기관 net 비중 = institution_net / (|foreign|+|institution|+1) → -1..+1. 부재 시 None."""
    if not net_sums:
        return None
    inst = net_sums.get("institution_net")
    foreign = net_sums.get("foreign_net")
    if inst is None and foreign is None:
        return None
    inst_v = float(inst or 0)
    denom = abs(float(foreign or 0)) + abs(inst_v) + 1.0
    return max(-1.0, min(1.0, inst_v / denom))


async def build_buy_score_inputs(
    *,
    ticker: str,
    pool_tickers: list[str] | None = None,
    market_macro: Any = None,
    regime_thresholds: dict[str, float] | None = None,
    cutoff_date: str | None = None,
) -> BuyScoreInputs:
    """buy_score CAN SLIM 7축 원시 지표. 각 축 graceful fallback(공백 → 중립 + reason).

    cross-agent 축(S/I/M)은 collector 직접 호출(절대원칙 1 준수):
        S/I = build_flow_inputs(ticker) / M = classify_market_regime(market_macro).
    """
    ticker_s = (ticker or "").strip()
    reasons: list[str] = []
    axis_source: dict[str, str] = {}
    source = "db"

    # ---- C / A — fundamentals (EPS 분기 + 연간) ----
    eps_yoy: float | None = None
    annual_yoy: float | None = None
    annual_eps_series: list[float | None] = []
    c = a = _NEUTRAL
    axis_source["c"] = axis_source["a"] = "neutral_fallback"
    if ticker_s:
        try:
            from collectors.fundamentals import get_fundamentals

            f = await get_fundamentals(ticker_s)
            eps_yoy = compute_eps_yoy(f.quarterly_eps)
            if eps_yoy is not None:
                c = map_to_axis(eps_yoy, _bps("buyscore", "c_eps_yoy")) or _NEUTRAL
                axis_source["c"] = f"fundamentals({f.source})"
            else:
                reasons.append("C(분기 EPS YoY) 중립 — EPS 5분기 미만/부재")
            # A — 연간 EPS YoY (≥3년 시계열). 가속/일관성은 원시 시계열로 LLM 판단.
            annual_eps_series = list(f.annual_eps or [])
            annual_yoy = compute_annual_eps_yoy(f.annual_eps)
            if annual_yoy is not None:
                a = map_to_axis(annual_yoy, _bps("buyscore", "a_annual_eps_yoy")) or _NEUTRAL
                axis_source["a"] = f"fundamentals({f.source})"
            else:
                reasons.append("A(연간 EPS) 중립 — 연간 EPS 3년 미만/부재")
        except Exception as e:  # noqa: BLE001
            log.warning("buyscore_fundamentals_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"C/A 산출 실패 ({type(e).__name__}) → 중립")

    # ---- N — 52주 신고가 (charts) + 거래량 spike(S 거래량 동반 입력) ----
    high_prox: float | None = None
    vol_spike: float | None = None
    vol_confirm: float | None = None
    n = _NEUTRAL
    axis_source["n"] = "neutral_fallback"
    if ticker_s:
        try:
            from collectors.charts import compute_indicators, load_ohlcv_from_db

            df = load_ohlcv_from_db(ticker_s, limit=400)
            if cutoff_date and df is not None and not df.empty:
                import pandas as pd

                df = df[df.index <= pd.Timestamp(cutoff_date)]
            if df is not None and not df.empty:
                ind = compute_indicators(df)
                high_prox = (ind.get("fifty_two_week") or {}).get("pct_from_high")
                if high_prox is not None:
                    n = map_to_axis(high_prox, _bps("buyscore", "n_high_proximity")) or _NEUTRAL
                    axis_source["n"] = "charts_52w"
                else:
                    reasons.append("N(52주 신고가) 중립 — pct_from_high 부재")
                vol_spike = (ind.get("volume") or {}).get("spike_ratio")
                if vol_spike is not None:
                    vol_confirm = map_to_axis(vol_spike, _bps("buyscore", "s_volume_confirm"))
            else:
                reasons.append("N(52주) 중립 — 일봉 부재")
        except Exception as e:  # noqa: BLE001
            log.warning("buyscore_chart_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"N 산출 실패 ({type(e).__name__}) → 중립")

        # C3 — 종목 scope 뉴스 catalyst_tilt 블렌드 (NEWS-SOURCE-001 MS-C, M7).
        # N = New(신고가 + 신제품/뉴스 촉매). 뉴스 없으면 52주 신고가만(보존).
        n = _blend_news_catalyst(n, ticker_s, cutoff_date, axis_source, reasons)
    else:
        reasons.append("N 중립 — ticker 부재")

    # ---- S / I — flow_inputs (collector 직접 호출). S = demand composite(momentum+inflow+거래량) ----
    inflow_raw: float | None = None
    demand_momentum: float | None = None
    inst_ratio: float | None = None
    s = i = _NEUTRAL
    axis_source["s"] = axis_source["i"] = "neutral_fallback"
    if ticker_s:
        try:
            from collectors.flow_inputs import build_flow_inputs
            from collectors.score_inputs_config import get_buyscore_s_weights

            fi = await build_flow_inputs(ticker=ticker_s, cutoff_date=cutoff_date)
            inflow_raw = fi.inflow_speed_raw
            demand_momentum = fi.momentum_score
            # S = 최근 momentum(이벤트) + 누적 inflow + 거래량 동반 블렌드 (누적 level 단독의 이벤트 누락 해소)
            demand = compute_demand_score(
                fi.momentum_score, fi.inflow_score, vol_confirm, get_buyscore_s_weights()
            )
            if demand is not None:
                s = demand
                axis_source["s"] = f"demand(flow {fi.source}+vol)"
            else:
                reasons.append("S(수급) 중립 — momentum/inflow/거래량 전부 미산출")
            inst_ratio = compute_institution_ratio(fi.net_sums)
            if inst_ratio is not None:
                i = map_to_axis(inst_ratio, _bps("buyscore", "i_institution_ratio")) or _NEUTRAL
                axis_source["i"] = f"flow({fi.source})"
            else:
                reasons.append("I(기관) 중립 — 5주체 net 부재")
        except Exception as e:  # noqa: BLE001
            log.warning("buyscore_flow_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"S/I 산출 실패 ({type(e).__name__}) → 중립")

    # ---- L — screening_score (rank_candidates) ----
    screening_sc: float | None = None
    l = _NEUTRAL
    axis_source["l"] = "neutral_fallback"
    pool = list(dict.fromkeys([*(pool_tickers or []), ticker_s])) if ticker_s else []
    if ticker_s and pool:
        try:
            from collectors.market_macro import classify_market_regime as _clf
            from collectors.screening import rank_candidates

            _regime_for_rank = _clf(market_macro, thresholds=regime_thresholds) if market_macro else None
            ranked = rank_candidates(pool, _regime_for_rank, cutoff_date=cutoff_date)
            row = next((r for r in ranked if r["ticker"] == ticker_s), None)
            if row is not None and row.get("screening_score") is not None:
                screening_sc = float(row["screening_score"])
                l = screening_sc
                axis_source["l"] = "screening"
            else:
                reasons.append("L(주도주) 중립 — 60일 데이터 부족")
        except Exception as e:  # noqa: BLE001
            log.warning("buyscore_screening_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"L 산출 실패 ({type(e).__name__}) → 중립")
    else:
        reasons.append("L(주도주) 중립 — 후보 풀 부재")

    # ---- M — regime (classify_market_regime) ----
    regime: str | None = None
    breadth: float | None = None
    dist: int | None = None
    m = 4.0  # sideways 중립
    axis_source["m"] = "neutral_fallback"
    if market_macro is not None:
        try:
            regime = classify_market_regime(market_macro, thresholds=regime_thresholds)
            m = regime_to_score(regime)
            axis_source["m"] = "regime"
            breadth = market_macro.get("breadth_ratio") if isinstance(market_macro, dict) else getattr(market_macro, "breadth_ratio", None)
            dist = market_macro.get("distribution_count_25d") if isinstance(market_macro, dict) else getattr(market_macro, "distribution_count_25d", None)
        except Exception as e:  # noqa: BLE001
            log.warning("buyscore_regime_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"M 산출 실패 ({type(e).__name__}) → 중립")
    else:
        reasons.append("M(시장 방향) 중립 — market_macro 부재")

    advisory = buy_score(c, a, n, s, l, i, m)

    return BuyScoreInputs(
        ticker=ticker_s,
        eps_yoy_pct=eps_yoy, annual_eps_yoy_pct=annual_yoy, annual_eps=annual_eps_series,
        high_proximity_pct=high_prox,
        inflow_speed_raw=inflow_raw, demand_momentum=demand_momentum, volume_spike=vol_spike,
        institution_ratio=inst_ratio,
        regime=regime, breadth_ratio=breadth, distribution_count=dist,
        screening_score=screening_sc,
        c=c, a=a, n=n, s=s, l=l, i=i, m=m,
        advisory_buy_score=advisory, reasons=reasons,
        source=source, cutoff_date=cutoff_date, axis_source=axis_source,
    )


async def build_buy_score_inputs_md(
    *,
    ticker: str,
    pool_tickers: list[str] | None = None,
    market_macro: Any = None,
    regime_thresholds: dict[str, float] | None = None,
    cutoff_date: str | None = None,
) -> str | None:
    """stock_picker 프롬프트 주입용 md. 실패 시 None (크래시 금지)."""
    try:
        bi = await build_buy_score_inputs(
            ticker=ticker, pool_tickers=pool_tickers, market_macro=market_macro,
            regime_thresholds=regime_thresholds, cutoff_date=cutoff_date,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("buy_score_inputs_build_failed", ticker=ticker, error=str(e))
        return None
    return render_buy_score_inputs_md(bi)


def _fmt(v: float | None, suffix: str = "", *, plus: bool = False) -> str:
    if v is None:
        return "null"
    return f"{v:+.1f}{suffix}" if plus else f"{v:.1f}{suffix}"


def render_buy_score_inputs_md(bi: BuyScoreInputs, *, name: str | None = None) -> str:
    """`score-inputs-v1` md 블록 — buy_score 7축 원시 지표(권위) + advisory(참고선)."""
    name_part = f" ({name})" if name else ""
    cutoff = f" | cutoff: {bi.cutoff_date}" if bi.cutoff_date else ""
    lines: list[str] = []
    lines.append("## [5e] 매수 입력 지표 (INFRA-SCORE-INPUTS-001 · buy_score, CAN SLIM 7축)")
    lines.append("")
    lines.append(f"**종목**: {bi.ticker}{name_part}{cutoff}")
    lines.append("")
    lines.append("### CAN SLIM 원시 지표 (이 값으로 직접 판단)")
    lines.append("| 축 | 의미 | 원시값 | 점수 | 출처 |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| C | 분기 EPS YoY | {_fmt(bi.eps_yoy_pct, '%', plus=True)} | {bi.c:.1f} | {bi.axis_source.get('c','')} |")
    if bi.annual_eps:
        series = "/".join("null" if v is None else f"{v:.0f}" for v in bi.annual_eps[:4])
        a_raw = f"YoY {_fmt(bi.annual_eps_yoy_pct, '%', plus=True)} (연간 {series})"
    else:
        a_raw = "(공백)"
    lines.append(f"| A | 연간 EPS YoY (3년) | {a_raw} | {bi.a:.1f} | {bi.axis_source.get('a','')} |")
    lines.append(f"| N | 52주 신고가 이격 | {_fmt(bi.high_proximity_pct, '%')} | {bi.n:.1f} | {bi.axis_source.get('n','')} |")
    vol_s = "null" if bi.volume_spike is None else f"{bi.volume_spike:.1f}배"
    mom_s = "null" if bi.demand_momentum is None else f"{bi.demand_momentum:.1f}"
    lines.append(
        f"| S | 수급(최근모멘텀+누적+거래량) | 누적 {_fmt(bi.inflow_speed_raw, 'bp', plus=True)}·모멘텀 {mom_s}·거래량 {vol_s} | {bi.s:.1f} | {bi.axis_source.get('s','')} |"
    )
    lines.append(f"| L | 주도주(RS+과열도) | {_fmt(bi.screening_score)} | {bi.l:.1f} | {bi.axis_source.get('l','')} |")
    lines.append(f"| I | 기관 비중 | {_fmt(bi.institution_ratio, plus=True)} | {bi.i:.1f} | {bi.axis_source.get('i','')} |")
    # M — narrow breadth 맥락 노출 (구조적 성장 vs 천장 디버전스 판단은 LLM)
    breadth_s = "null" if bi.breadth_ratio is None else f"{bi.breadth_ratio:.2f}"
    dist_s = "null" if bi.distribution_count is None else str(bi.distribution_count)
    lines.append(
        f"| M | 시장 방향 | {bi.regime or 'null'} (폭 {breadth_s}·분산일 {dist_s}) | {bi.m:.1f} | {bi.axis_source.get('m','')} |"
    )
    lines.append("")
    lines.append(
        "> **M축 주의**: 시장 폭이 좁은데(breadth 낮음) 지수만 강하면 regime 은 보수적으로 moderate_bull. "
        "이게 **시총 상위 구조적 주도**(정당)인지 **천장 디버전스**(경고)인지는 위 폭·분산일로 **본인이 판단**."
    )
    adv = "null" if bi.advisory_buy_score is None else f"{bi.advisory_buy_score:.1f}"
    lines.append(
        f"> **advisory buy_score: {adv}** — 참고선일 뿐이며 권위 아님. 위 원시 지표로 **직접 판단**·override 가능. "
        f"N 뉴스부(신제품)는 데이터 공백 중립. A(연간 EPS)는 3년 미만 시 중립."
    )
    if bi.reasons:
        lines.append("")
        lines.append("_부분 산출: " + "; ".join(bi.reasons) + "_")
    return "\n".join(lines)
