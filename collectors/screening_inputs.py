"""S-Score 원시 지표 collector (INFRA-SCORE-INPUTS-001 v2).

stock_picker 의 주도주(S-Score) 판단 입력 = 원시 지표(종목 상대강도·수급망 정합·정배열
위계)를 결정론 계산해 md 블록으로 주입한다. **점수를 기계가 매기지 않는다** — 원시 지표가
권위(LLM 주입), advisory S-Score 는 참고선(override 가능, 메모리 feedback_score_collapse_advisory).

3 축:
    rs           — 후보 풀 정규화 상대강도. SCREEN-RS-EXTENSION-001 rank_candidates **권위 지표**.
    supply_chain — 강세 산업 공급망 정합. MVP = 중립 (SLOT — theme/sector 매핑 후속).
    alignment    — 월·주·일봉 정배열 위계. charts.compute_indicators 로 결정론 산출.

flow_inputs.py 패턴 mirror. cutoff_date 지정 시 그 시점까지만 → 백테스팅 재현.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from collectors.charts import compute_indicators, load_ohlcv_from_db
from collectors.scoring import _clamp, _round_to_half, s_score
from collectors.screening import _slice_to_cutoff, rank_candidates
from core.logging import get_logger

log = get_logger(__name__)

_SUPPLY_CHAIN_NEUTRAL = 5.0


@dataclass
class ScreeningInputs:
    """S-Score 원시 지표 + advisory 점수. 원시 = 권위, advisory = 참고선."""

    ticker: str
    # 원시 지표 (LLM 주입 = 권위)
    rs_return_60d: float | None        # 종목 60일 수익률 (%)
    pool_size: int                     # rs 정규화에 쓰인 후보 풀 크기
    alignment_detail: dict[str, Any]   # {monthly_7ma, weekly_stack, daily_stack} bool/None
    # advisory 0~10 축 (참고선)
    rs_score: float | None
    supply_chain_score: float | None
    alignment_score: float | None
    advisory_s_score: float | None
    reasons: list[str] = field(default_factory=list)
    source: str = "db"
    cutoff_date: str | None = None
    rs_source: str = "screening"       # screening | neutral_fallback
    supply_chain_source: str = "neutral_fallback"  # theme_sector | neutral_fallback
    supply_chain_theme: str | None = None    # classify_theme 분류 결과 (md 표기)
    supply_chain_sector: str | None = None   # 채택된 최강 섹터명 (md 표기)


# 일봉 단기 추세 주도강도 위계 (사용자 추세추종 doctrine 2026-06-02):
#   빠른 이평을 "타고 오를"수록 강한 주도주. 4일선 타면 초강세(삼성·SK하이닉스),
#   7일선이면 강세, 20일 정배열은 정상 추세, 20일 위지만 정배열 아니면 약한 추세.
#   "타고 오른다" = 빠른 MA 스택(close>ma4>ma7>ma20) — MA 위계 순서가 곧 빠른 이평 상승 = 밀착 상승.
#   과열도(이격 거리)는 별도 축(scoring.extension_score)이 담당 → 여기선 구조(어느 MA 타나)만.
_DAILY_LEADERSHIP_POINTS = {
    "riding_ma4": 3.0,    # 초강세 주도주 (4일선 타고 상승)
    "riding_ma7": 2.5,    # 강세 (7일선 타고 상승)
    "uptrend": 2.0,       # 정상 정배열 (close>ma20>ma60)
    "above_ma20": 1.5,    # ma20 위지만 정배열/리딩 아님
    "below_ma20": 0.0,    # ma20 아래 (단기 추세 이탈)
}


def _daily_leadership(
    close: float | None,
    d4: float | None,
    d7: float | None,
    d20: float | None,
    d60: float | None,
) -> tuple[float | None, str | None]:
    """일봉 단기 주도강도 위계 → (0~3 점, label). d20 부재 시 (None, None) = 평가 불가.

    가장 빠른(타이트한) 이평을 탈수록 높은 점수. 위계 순서가 곧 추세 강도.
    """
    if close is None or d20 is None:
        return None, None
    if close <= d20:
        return _DAILY_LEADERSHIP_POINTS["below_ma20"], "below_ma20"
    if d4 is not None and d7 is not None and close > d4 > d7 > d20:
        return _DAILY_LEADERSHIP_POINTS["riding_ma4"], "riding_ma4"
    if d7 is not None and close > d7 > d20:
        return _DAILY_LEADERSHIP_POINTS["riding_ma7"], "riding_ma7"
    if d60 is not None and d20 > d60:
        return _DAILY_LEADERSHIP_POINTS["uptrend"], "uptrend"
    return _DAILY_LEADERSHIP_POINTS["above_ma20"], "above_ma20"


def compute_alignment(indicators: dict[str, Any]) -> tuple[float | None, dict[str, Any]]:
    """월·주·일봉 정배열 위계 → 0~10 + 컴포넌트 detail (순수).

    월봉 종가 7MA 위 = 4점 (시대적 중장기 주도) + 주봉 10MA>20MA(>60MA) 정배열 = 3점 (중기) +
    **일봉 단기 주도강도 위계 = 0~3점 (graded)** — 4일선 타고 오름=초강세(3) / 7일선=강세(2.5) /
    20일 정배열=정상(2) / 20일 위=약한 추세(1.5) / 20일 아래=이탈(0). (사용자 추세추종 doctrine 2026-06-02,
    이전엔 close>ma20>ma60 이진 3점 — 초강세 주도주를 정상 추세와 구분 못함.)
    **산출 가능 위계만 평가 → available_max 대비 비례 정규화** (결측 위계는 0 기여가 아니라 *평가 제외*).
    품질 측정(정배열 비율)이지 데이터 양 측정이 아니므로 정규화가 본질. 모든 컴포넌트 불가 → (None, detail).
    """
    monthly = indicators.get("monthly_ma") or {}
    weekly = indicators.get("weekly_ma") or {}
    daily = indicators.get("daily_ma") or {}
    close = indicators.get("current_close")
    detail: dict[str, Any] = {
        "monthly_7ma": None, "weekly_stack": None,
        "daily_stack": None, "daily_leadership": None,
    }
    if close is None:
        return None, detail

    points = 0.0
    available_max = 0.0

    m7 = monthly.get("ma7")
    if m7 is not None:
        ok = close > m7
        detail["monthly_7ma"] = ok
        available_max += 4.0
        points += 4.0 if ok else 0.0

    w10, w20, w60 = weekly.get("ma10"), weekly.get("ma20"), weekly.get("ma60")
    if w10 is not None and w20 is not None:
        ok = w10 > w20 and (w60 is None or w20 > w60)
        detail["weekly_stack"] = ok
        available_max += 3.0
        points += 3.0 if ok else 0.0

    d4, d7 = daily.get("ma4"), daily.get("ma7")
    d20, d60 = daily.get("ma20"), daily.get("ma60")
    dpts, dlabel = _daily_leadership(close, d4, d7, d20, d60)
    if dpts is not None:
        detail["daily_stack"] = bool(d60 is not None and close > d20 > d60)  # 기존 이진 (호환·렌더)
        detail["daily_leadership"] = dlabel
        available_max += 3.0
        points += dpts

    if available_max <= 0:
        return None, detail
    normalized = points / available_max * 10.0
    return _clamp(_round_to_half(normalized)), detail


def compute_supply_chain_score(
    theme: str | None,
    sector_rs_list: list[dict[str, Any]] | None,
    mapping: dict[str, list[str]] | None,
) -> tuple[float | None, str]:
    """종목 theme → 매핑 섹터의 최강 RS 강도 → supply_chain 0~10 (순수).

    "이 종목이 강세 산업 공급망 중심에 있는가". 여러 섹터 매핑 시 최강 rs_score 채택.
    theme None / 매핑 부재 / 일치 섹터 없음 / sector_rs 빈 경우 → (None, 'neutral_fallback').
    """
    if not theme or not sector_rs_list or not mapping:
        return None, "neutral_fallback"
    sector_names = mapping.get(theme) or []
    if not sector_names:
        return None, "neutral_fallback"
    wanted = set(sector_names)
    scores = [
        float(r["rs_score"])
        for r in sector_rs_list
        if isinstance(r, dict) and r.get("sector") in wanted and r.get("rs_score") is not None
    ]
    if not scores:
        return None, "neutral_fallback"
    return _clamp(_round_to_half(max(scores))), "theme_sector"


async def build_s_score_inputs(
    *,
    ticker: str,
    pool_tickers: list[str] | None = None,
    regime: str | None = None,
    cutoff_date: str | None = None,
    sector_rs: list[dict[str, Any]] | None = None,
) -> ScreeningInputs:
    """S-Score 원시 지표 — rs(SCREEN-RS 후보 풀 정규화) + supply_chain(theme→섹터 RS) + alignment.

    pool_tickers = rs 백분위 정규화에 쓸 후보 풀 (run_analyst 가 snapshot 주도주에서 추출).
    sector_rs = snapshot.sector_rs (섹터별 rs_score) — supply_chain 실측 입력. None → 중립.
    빈 풀이면 ticker 단독 → rs 중립 5.0. cutoff_date 지정 시 live X (백테스팅).
    """
    ticker_s = (ticker or "").strip()
    reasons: list[str] = []
    pool = list(dict.fromkeys([*(pool_tickers or []), ticker_s])) if ticker_s else []

    # 1) rs — SCREEN-RS rank_candidates (권위)
    rs_score: float | None = None
    rs_return: float | None = None
    rs_source = "neutral_fallback"
    pool_size = len(pool)
    if ticker_s and pool:
        try:
            ranked = rank_candidates(pool, regime, cutoff_date=cutoff_date)
            row = next((r for r in ranked if r["ticker"] == ticker_s), None)
            if row is not None and row.get("rs_score") is not None:
                rs_score = float(row["rs_score"])
                rs_source = "screening"
            else:
                reasons.append("rs 산출 불가 (60일 데이터 부족) → 중립")
        except Exception as e:  # noqa: BLE001
            log.warning("s_score_rs_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"rs 산출 실패 ({type(e).__name__}) → 중립")
    else:
        reasons.append("후보 풀 부재 → rs 중립")
    if rs_score is None:
        rs_score = 5.0

    # 2) supply_chain — theme(classify) → 매핑 섹터의 최강 RS 실측
    supply_chain_score: float = _SUPPLY_CHAIN_NEUTRAL
    supply_chain_source = "neutral_fallback"
    supply_chain_theme: str | None = None
    supply_chain_sector: str | None = None
    if ticker_s and sector_rs:
        try:
            from collectors.score_inputs_config import get_theme_sector_mapping
            from collectors.theme_match import classify_theme

            tr = await classify_theme(ticker_s, cutoff_date=cutoff_date)
            supply_chain_theme = tr.theme
            mapping = get_theme_sector_mapping()
            sc, sc_src = compute_supply_chain_score(tr.theme, sector_rs, mapping)
            if sc is not None:
                supply_chain_score = sc
                supply_chain_source = sc_src
                wanted = set(mapping.get(tr.theme or "", []))
                matched = [
                    r for r in sector_rs
                    if isinstance(r, dict) and r.get("sector") in wanted and r.get("rs_score") is not None
                ]
                if matched:
                    supply_chain_sector = max(matched, key=lambda r: r["rs_score"]).get("sector")
                reasons.append(
                    f"supply_chain: {supply_chain_theme}→{supply_chain_sector} 섹터 RS {supply_chain_score:.1f}"
                )
            else:
                reasons.append(
                    f"supply_chain 중립 5.0 (theme={supply_chain_theme or '미분류'} 섹터 매핑 없음)"
                )
        except Exception as e:  # noqa: BLE001
            log.warning("s_score_supply_chain_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"supply_chain 산출 실패 ({type(e).__name__}) → 중립")
    else:
        reasons.append("supply_chain 중립 5.0 (sector_rs/ticker 부재)")

    # 3) alignment — charts.compute_indicators (결정론)
    alignment_score: float | None = None
    alignment_detail: dict[str, Any] = {"monthly_7ma": None, "weekly_stack": None, "daily_stack": None}
    source = "db"
    if ticker_s:
        try:
            df = load_ohlcv_from_db(ticker_s, limit=400)
            df = _slice_to_cutoff(df, cutoff_date)
            if df is not None and not df.empty:
                rs_return = _return_60d(df)
                indicators = compute_indicators(df)
                alignment_score, alignment_detail = compute_alignment(indicators)
                source = f"db@{cutoff_date}" if cutoff_date else "db"
                if alignment_score is None:
                    reasons.append("정배열 위계 산출 불가 (데이터 부족)")
            else:
                reasons.append("일봉 부재 → 정배열 미산출")
        except Exception as e:  # noqa: BLE001
            log.warning("s_score_alignment_failed", ticker=ticker_s, error=str(e))
            reasons.append(f"정배열 산출 실패 ({type(e).__name__})")

    # 4) advisory s_score (참고선) — 균등 3축 (alignment 미산출 시 중립 5.0 대입)
    align_axis = alignment_score if alignment_score is not None else 5.0
    advisory = s_score(rs_score, supply_chain_score, align_axis)

    return ScreeningInputs(
        ticker=ticker_s,
        rs_return_60d=rs_return,
        pool_size=pool_size,
        alignment_detail=alignment_detail,
        rs_score=rs_score,
        supply_chain_score=supply_chain_score,
        alignment_score=alignment_score,
        advisory_s_score=advisory,
        reasons=reasons,
        source=source,
        cutoff_date=cutoff_date,
        rs_source=rs_source,
        supply_chain_source=supply_chain_source,
        supply_chain_theme=supply_chain_theme,
        supply_chain_sector=supply_chain_sector,
    )


def _return_60d(df: Any, window: int = 60) -> float | None:
    """최근 window 봉 close 수익률 % (md 표기용)."""
    if df is None or df.empty or "close" not in df.columns or len(df) < window:
        return None
    start = df["close"].iloc[-window]
    if start is None or start <= 0:
        return None
    return float((df["close"].iloc[-1] - start) / start * 100)


async def build_s_score_inputs_md(
    *,
    ticker: str,
    pool_tickers: list[str] | None = None,
    regime: str | None = None,
    cutoff_date: str | None = None,
    sector_rs: list[dict[str, Any]] | None = None,
) -> str | None:
    """stock_picker 프롬프트 주입용 md. 실패 시 None (크래시 금지)."""
    try:
        si = await build_s_score_inputs(
            ticker=ticker, pool_tickers=pool_tickers, regime=regime,
            cutoff_date=cutoff_date, sector_rs=sector_rs,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("s_score_inputs_build_failed", ticker=ticker, error=str(e))
        return None
    return render_s_score_inputs_md(si)


def _fmt(v: float | None, suffix: str = "") -> str:
    return "null" if v is None else f"{v:.1f}{suffix}"


def _align_cell(v: Any) -> str:
    if v is None:
        return "산출 불가"
    return "정배열 ✓" if v else "역배열 ✗"


_LEADERSHIP_LABEL_KO = {
    "riding_ma4": "4일선 타고 상승 — 초강세 주도주",
    "riding_ma7": "7일선 타고 상승 — 강세",
    "uptrend": "20일 정배열 — 정상 추세",
    "above_ma20": "20일 위 — 약한 추세",
    "below_ma20": "20일 아래 — 단기 추세 이탈",
}


def _leadership_cell(label: Any) -> str:
    if label is None:
        return "산출 불가"
    return _LEADERSHIP_LABEL_KO.get(label, str(label))


def render_s_score_inputs_md(si: ScreeningInputs, *, name: str | None = None) -> str:
    """`score-inputs-v1` md 블록 — 원시 주도주 지표(권위) + advisory S-Score(참고선)."""
    name_part = f" ({name})" if name else ""
    cutoff = f" | cutoff: {si.cutoff_date}" if si.cutoff_date else ""
    lines: list[str] = []
    lines.append("## [5d] 주도주 입력 지표 (INFRA-SCORE-INPUTS-001 · S-Score)")
    lines.append("")
    lines.append(
        f"**종목**: {si.ticker}{name_part} | **출처**: {si.source}{cutoff} | "
        f"**후보 풀**: {si.pool_size}종목"
    )
    lines.append("")
    lines.append("### 원시 주도주 지표 (이 값으로 직접 판단)")
    lines.append("| 축 | 값 |")
    lines.append("|---|---|")
    rs_v = _fmt(si.rs_score, " / 10")
    rs_ret = "null" if si.rs_return_60d is None else f"{si.rs_return_60d:+.1f}%"
    lines.append(f"| rs (상대강도, 풀 정규화) | {rs_v} ({si.rs_source}, 60일 {rs_ret}) |")
    if si.supply_chain_source == "theme_sector":
        sc_cell = (
            f"{_fmt(si.supply_chain_score, ' / 10')} "
            f"({si.supply_chain_theme}→{si.supply_chain_sector}, 섹터 RS)"
        )
    else:
        sc_cell = f"{_fmt(si.supply_chain_score, ' / 10')} (중립 — {si.supply_chain_theme or '미분류'})"
    lines.append(f"| supply_chain (수급망 정합) | {sc_cell} |")
    lines.append(f"| alignment (정배열 위계) | {_fmt(si.alignment_score, ' / 10')} |")
    lines.append("")
    lines.append("### 정배열 위계 컴포넌트")
    lines.append("| 위계 | 상태 |")
    lines.append("|---|---|")
    lines.append(f"| 월봉 종가 7MA 위 (4점) | {_align_cell(si.alignment_detail.get('monthly_7ma'))} |")
    lines.append(f"| 주봉 정배열 10>20(>60)MA (3점) | {_align_cell(si.alignment_detail.get('weekly_stack'))} |")
    lines.append(
        f"| 일봉 단기 주도강도 (0~3점) | "
        f"{_leadership_cell(si.alignment_detail.get('daily_leadership'))} |"
    )
    lines.append("")
    adv = "null" if si.advisory_s_score is None else f"{si.advisory_s_score:.1f}"
    lines.append(
        f"> **advisory S-Score: {adv}** — 참고선일 뿐이며 권위 아님. rs(권위) + 위 원시 지표로 "
        f"**본인이 직접 판단**하고 override 가능. supply_chain 은 MVP 중립(SLOT)."
    )
    if si.reasons:
        lines.append("")
        lines.append("_부분 산출: " + "; ".join(si.reasons) + "_")
    return "\n".join(lines)
