"""Commandment 3 — 트레이딩 비중 <= 20%."""
from __future__ import annotations

from checkers.commandments.base import CommandmentResult

TRADING_STRATEGIES = {"daytrade", "swing"}


def check(portfolio: dict, threshold_pct: float) -> CommandmentResult:
    positions = portfolio.get("positions", [])
    trading_total = sum(
        p.get("weight_pct", 0)
        for p in positions
        if p.get("strategy") in TRADING_STRATEGIES
    )
    warn_floor = threshold_pct * 0.9
    if trading_total > threshold_pct:
        sev = "violation"
        detail = f"트레이딩 비중 {trading_total}% 가 제한 {threshold_pct}% 초과"
    elif warn_floor <= trading_total < threshold_pct:
        sev = "warning"
        detail = f"트레이딩 비중 {trading_total}% — 제한 근접"
    else:
        sev = "pass"
        detail = f"트레이딩 비중 {trading_total}% (제한 {threshold_pct}% 이내)"
    return CommandmentResult(
        commandment_id="3",
        title="트레이딩 비중 <= 20%",
        severity=sev,
        detail=detail,
        metrics={"trading_weight_pct": trading_total, "threshold": threshold_pct},
    )
