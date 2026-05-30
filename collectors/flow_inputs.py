"""F-Score 원시 지표 collector (INFRA-SCORE-INPUTS-001).

flow_analyzer 의 수급(F-Score) 판단 입력 = 원시 수급 지표(60일 모멘텀·자금 유입 속도·
5주체 부호 일치도)를 결정론 계산해 md 블록으로 주입한다. **점수를 기계가 매기지 않는다** —
원시 지표가 권위(LLM 주입), advisory F-Score 는 참고선(override 가능).

MVP = 시장 레벨 5주체 60일 수급(`supply_demand_history`) 프록시. 종목 레벨 수급은 후속 gap.
theme_match(종목 테마 ↔ 권위 주체) 직관축 = SLOT S1 (2-Stage 하이브리드) → MVP 중립.
agreement 는 `supply_demand_history.agreement_score` 재사용 (신설 X).

cutoff_date: 지정 시 그 시점까지 수급만 사용 → 백테스팅 재현.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from collectors.scoring import f_score, map_to_axis
from collectors.supply_demand_history import agreement_score
from core.logging import get_logger

log = get_logger(__name__)

_NET_KEYS = (
    "foreign_net",
    "institution_net",
    "individual_net",
    "financial_inv_net",
    "pension_net",
)
# 권위 주체 (모멘텀 turnaround 의 핵심 = 외인·기관)
_AUTHORITY_KEYS = ("foreign_net", "institution_net")


@dataclass
class FlowInputs:
    """F-Score 원시 수급 지표 + advisory 점수. 원시 = 권위, advisory = 참고선."""

    ticker: str
    market: str
    actual_days: int
    # 원시 지표 (LLM 주입 = 권위)
    net_sums: dict[str, int]              # 5주체 60일 net 합 (백만원)
    momentum_raw: float | None            # -1.0~+1.0 (외인·기관 turnaround)
    inflow_speed_raw: float | None        # 시총 정규화 자금 유입 (bp)
    agreement: float                      # 5주체 부호 일치도 0~10 (재사용)
    # advisory 0~10 축 (참고선)
    momentum_score: float | None
    inflow_score: float | None
    theme_match_score: float | None
    advisory_f_score: float | None
    reasons: list[str] = field(default_factory=list)
    source: str = "db"
    cutoff_date: str | None = None


def _bps(
    breakpoints: dict[str, list[tuple[float, float]]] | None,
    axis: str,
) -> list[tuple[float, float]]:
    if breakpoints is not None and axis in breakpoints:
        return breakpoints[axis]
    from collectors.score_inputs_config import get_breakpoints

    return get_breakpoints("flow", axis)


def _map(value: float | None, bps: list[tuple[float, float]]) -> float | None:
    if value is None or not bps:
        return None
    return map_to_axis(value, bps)


def _row_get(row: Any, key: str) -> int:
    """dict 또는 SupplyRow 양쪽 지원."""
    if isinstance(row, dict):
        return int(row.get(key, 0))
    return int(getattr(row, key, 0))


def compute_flow_inputs(
    rows: list[Any],
    *,
    market_cap: float | None = None,
    breakpoints: dict[str, list[tuple[float, float]]] | None = None,
    theme_match_neutral: float = 5.0,
    ticker: str = "",
    market: str = "KOSPI",
    source: str = "db",
    cutoff_date: str | None = None,
) -> FlowInputs:
    """순수 — 60일 5주체 수급 rows(정순) → F-Score 원시 지표 + advisory.

    Args:
        rows: SupplyRow 또는 dict 리스트 (과거→최신 정순). 5주체 net (백만원).
        market_cap: 시가총액 (백만원). None → inflow_speed 미산출.
        breakpoints: 축 매핑 DI. None → config.
        theme_match_neutral: theme_match 직관축 미배선 시 중립값 (SLOT S1).
    """
    reasons: list[str] = []
    n = len(rows)
    sums = {k: 0 for k in _NET_KEYS}
    for r in rows:
        for k in _NET_KEYS:
            sums[k] += _row_get(r, k)

    if n == 0:
        reasons.append("수급 60일 데이터 부재")
        return FlowInputs(
            ticker=ticker, market=market, actual_days=0, net_sums=sums,
            momentum_raw=None, inflow_speed_raw=None, agreement=0.0,
            momentum_score=None, inflow_score=None, theme_match_score=None,
            advisory_f_score=None, reasons=reasons, source=source, cutoff_date=cutoff_date,
        )

    # 1) agreement (재사용)
    agreement = agreement_score(sums)

    # 2) momentum — 외인·기관 최근 절반 vs 직전 절반 turnaround → -1..+1
    half = n // 2
    if half >= 1:
        prior = sum(_row_get(r, k) for r in rows[:half] for k in _AUTHORITY_KEYS)
        recent = sum(_row_get(r, k) for r in rows[half:] for k in _AUTHORITY_KEYS)
        denom = abs(recent) + abs(prior) + 1
        momentum_raw = max(-1.0, min(1.0, (recent - prior) / denom))
    else:
        momentum_raw = None
        reasons.append("수급 모멘텀 미산출 (구간 부족)")

    # 3) inflow_speed — (외인+기관 60d) / 시총 * 10000 (bp)
    if market_cap and market_cap > 0:
        authority_60d = sums["foreign_net"] + sums["institution_net"]
        inflow_speed_raw = authority_60d / market_cap * 10000
    else:
        inflow_speed_raw = None
        reasons.append("자금 유입 속도 미산출 (시총/market_cap 부재)")

    # 4) 축 매핑
    momentum_score = _map(momentum_raw, _bps(breakpoints, "momentum"))
    inflow_score = _map(inflow_speed_raw, _bps(breakpoints, "inflow_speed"))
    theme_match_score = theme_match_neutral
    reasons.append("theme_match 직관축 미배선 → 중립 (SLOT S1, 2-Stage 하이브리드)")

    # 5) advisory f_score (참고선) — SPEC v2 가중 (theme 0.4 + mom 0.3 + inflow 0.2 + agree 0.1)
    mom_axis = momentum_score if momentum_score is not None else 5.0
    inflow_axis = inflow_score if inflow_score is not None else 5.0
    advisory_f_score = f_score(theme_match_score, mom_axis, inflow_axis, agreement)

    return FlowInputs(
        ticker=ticker, market=market, actual_days=n, net_sums=sums,
        momentum_raw=momentum_raw, inflow_speed_raw=inflow_speed_raw, agreement=agreement,
        momentum_score=momentum_score, inflow_score=inflow_score,
        theme_match_score=theme_match_score, advisory_f_score=advisory_f_score,
        reasons=reasons, source=source, cutoff_date=cutoff_date,
    )


# ---------------------------------------------------------------------------
# Async builder — supply_demand_history 재사용 (+ cutoff_date)
# ---------------------------------------------------------------------------


async def build_flow_inputs(
    *,
    market: str = "KOSPI",
    market_cap: float | None = None,
    cutoff_date: str | None = None,
    ticker: str = "",
) -> FlowInputs:
    """supply_demand_history 60일 로드 → F-Score 원시 지표.

    MVP = 시장 레벨. cutoff_date 지정 시 그 시점까지만 (백테스팅).
    """
    from collectors.supply_demand_history import load_supply_window

    rows = load_supply_window(market, days=60)
    if cutoff_date:
        rows = [r for r in rows if r.date <= cutoff_date]
    return compute_flow_inputs(
        rows, market_cap=market_cap, ticker=ticker, market=market,
        source=f"db@{cutoff_date}" if cutoff_date else "db", cutoff_date=cutoff_date,
    )


async def build_flow_inputs_md(
    *,
    market: str = "KOSPI",
    market_cap: float | None = None,
    cutoff_date: str | None = None,
    ticker: str = "",
) -> str | None:
    """flow_analyzer 프롬프트 주입용 md. 실패 시 None (크래시 금지)."""
    try:
        fi = await build_flow_inputs(
            market=market, market_cap=market_cap, cutoff_date=cutoff_date, ticker=ticker,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("flow_inputs_build_failed", market=market, error=str(e))
        return None
    return render_flow_inputs_md(fi)


def _fmt(v: float | None, suffix: str = "", *, plus: bool = False) -> str:
    if v is None:
        return "null"
    fmt = f"{v:+.2f}" if plus else f"{v:.2f}"
    return f"{fmt}{suffix}"


def _fmt_won_m(value: int) -> str:
    """백만원 단위 → 억/조."""
    won = value * 1_000_000
    if abs(won) >= 1e12:
        return f"{won / 1e12:+,.2f}조"
    if abs(won) >= 1e8:
        return f"{won / 1e8:+,.0f}억"
    return f"{value:+,}백만"


def render_flow_inputs_md(fi: FlowInputs, *, name: str | None = None) -> str:
    """`score-inputs-v1` md 블록 — 원시 수급 지표(권위) + advisory F-Score(참고선)."""
    name_part = f" ({name})" if name else ""
    cutoff = f" | cutoff: {fi.cutoff_date}" if fi.cutoff_date else ""
    lines: list[str] = []
    lines.append("## [5c] 수급 입력 지표 (INFRA-SCORE-INPUTS-001 · F-Score, 시장 레벨)")
    lines.append("")
    lines.append(
        f"**시장**: {fi.market}{name_part} | **출처**: {fi.source}{cutoff} | "
        f"**실 일수**: {fi.actual_days}"
    )
    lines.append("")
    lines.append("### 원시 수급 지표 (이 값으로 직접 판단)")
    lines.append("| 지표 | 값 |")
    lines.append("|---|---|")
    lines.append(
        f"| 60일 모멘텀 (외인·기관 turnaround) | {_fmt(fi.momentum_raw, plus=True)} (−1~+1) |"
    )
    lines.append(
        f"| 자금 유입 속도 (시총 정규화 bp) | {_fmt(fi.inflow_speed_raw, 'bp', plus=True) if fi.inflow_speed_raw is not None else 'null'} |"
    )
    lines.append(f"| 5주체 부호 일치도 (agreement) | {fi.agreement:.1f} / 10 |")
    lines.append("")
    lines.append("### 60일 누적 5주체 net")
    lines.append("| 주체 | 60일 누적 |")
    lines.append("|---|---|")
    for k, label in (
        ("foreign_net", "외국인"), ("institution_net", "기관"),
        ("individual_net", "개인"), ("financial_inv_net", "금융투자"),
        ("pension_net", "연기금"),
    ):
        lines.append(f"| {label} | {_fmt_won_m(fi.net_sums.get(k, 0))} |")
    lines.append("")
    adv = "null" if fi.advisory_f_score is None else f"{fi.advisory_f_score:.1f}"
    lines.append(
        f"> **advisory F-Score: {adv}** — 참고선일 뿐이며 권위 아님 "
        f"(theme_match 직관축 미배선=중립). 위 원시 수급 지표로 **본인이 직접 판단**하고 override 가능."
    )
    if fi.reasons:
        lines.append("")
        lines.append("_부분 산출: " + "; ".join(fi.reasons) + "_")
    return "\n".join(lines)
