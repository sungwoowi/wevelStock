"""회고 양식 렌더 — GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) G3.

get_kpi_summary(guidance-kpi-v1) → 사람 친화 회고 텍스트. 코드 라벨(track_b/verdict 등)
노출 X — 트랙은 중장기/단기 친화 라벨. `/회고` 단축어(production_chat·텔레그램) 소비.
"""
from __future__ import annotations

from typing import Any

_TRACK_LABEL = {"A": "중장기", "B": "단기", "all": "전체"}


def _pct(v: Any) -> str:
    return f"{v:.1f}%" if isinstance(v, (int, float)) else "—"


def _won(v: Any) -> str:
    if not isinstance(v, (int, float)):
        return "—"
    if abs(v) >= 100_000_000:
        return f"{v / 100_000_000:.1f}억원"
    if abs(v) >= 10_000:
        return f"{v / 10_000:.0f}만원"
    return f"{v:,.0f}원"


def render_retrospective(summary: dict[str, Any], *, top_n: int = 3) -> str:
    """KPI 집계 → 회고 markdown (가상매매 기준)."""
    period = summary.get("period_days", 90)
    lines = [f"📊 최근 {period}일 가이던스 회고 (가상매매 기준)"]

    n = summary.get("closed_count", 0)
    if not n:
        lines.append("\n청산된 권고가 아직 없습니다. (데스크가 매수→목표/손절로 청산하면 채점이 시작됩니다)")
        return "\n".join(lines)

    lines.append(f"\n【청산 권고】 {n}건 · 실현손익 합계 {_won(summary.get('realized_pnl_sum_krw'))}")
    lines.append(f"- 실현수익률 평균: {_pct(summary.get('realized_return_avg_pct'))}")
    alpha = summary.get("alpha_avg_pct")
    if alpha is not None:
        sign = "+" if alpha >= 0 else ""
        verdict = "시장보다 잘함" if alpha >= 0 else "시장보다 못함"
        lines.append(
            f"- 시장 대비 초과수익: {sign}{alpha:.1f}%p "
            f"(지수 {_pct(summary.get('benchmark_return_avg_pct'))} 대비 — {verdict})"
        )
    lines.append(f"- 방향 적중률: {_pct(summary.get('win_rate_pct'))}")
    if summary.get("rr_realization_avg_pct") is not None:
        lines.append(f"- 손익비 실현율: {_pct(summary.get('rr_realization_avg_pct'))}")
    lines.append(f"- 평균 보유: {summary.get('avg_holding_days') or 0:.0f}일")

    by_track = summary.get("by_track")
    if by_track:
        for t in ("A", "B"):
            bt = by_track.get(t, {})
            if bt.get("closed_count"):
                lines.append(
                    f"  · {_TRACK_LABEL[t]}: {bt['closed_count']}건 · 적중 {_pct(bt.get('win_rate_pct'))} "
                    f"· 실현 {_pct(bt.get('realized_return_avg_pct'))}"
                )

    records = summary.get("records") or []
    best = sorted(records, key=lambda r: r.get("realized_return_pct", 0), reverse=True)[:top_n]
    worst = [r for r in sorted(records, key=lambda r: r.get("realized_return_pct", 0))
             if r.get("realized_return_pct", 0) < 0][:top_n]
    if best:
        lines.append("\n【가장 잘된 권고】")
        for r in best:
            lines.append(
                f"- {r['ticker']} {r['entry_date'][5:]}~{r['exit_date'][5:]} "
                f"{r.get('realized_return_pct', 0):+.1f}%"
            )
    if worst:
        lines.append("\n【가장 빗나간 권고】")
        for r in worst:
            lines.append(
                f"- {r['ticker']} {r['entry_date'][5:]}~{r['exit_date'][5:]} "
                f"{r.get('realized_return_pct', 0):+.1f}%"
            )
    return "\n".join(lines)
