"""Commandment 1 — 총 투자비중 <= 80%."""
from __future__ import annotations

from checkers.commandments.base import CommandmentResult


def check(portfolio: dict, threshold_pct: float) -> CommandmentResult:
    """Verify total portfolio weight stays under the threshold."""
    positions = portfolio.get("positions", [])
    total = sum(p.get("weight_pct", 0) for p in positions)
    warn_floor = threshold_pct * 0.9
    if total > threshold_pct:
        sev = "violation"
        detail = f"총 비중 {total}% 가 제한 {threshold_pct}% 초과"
    elif warn_floor <= total < threshold_pct:
        sev = "warning"
        detail = f"총 비중 {total}% — 제한 {threshold_pct}% 근접"
    else:
        sev = "pass"
        detail = f"총 비중 {total}% 로 제한 {threshold_pct}% 이내"
    return CommandmentResult(
        commandment_id="1",
        title="총 투자비중 <= 80%",
        severity=sev,
        detail=detail,
        metrics={"total_weight_pct": total, "threshold": threshold_pct},
    )
