"""Commandment 2 — 단일 종목 비중 <= 15%."""
from __future__ import annotations

from checkers.commandments.base import CommandmentResult


def check(portfolio: dict, threshold_pct: float) -> CommandmentResult:
    positions = portfolio.get("positions", [])
    if not positions:
        return CommandmentResult(
            commandment_id="2",
            title="단일 종목 <= 15%",
            severity="pass",
            detail="포지션 없음",
        )
    max_pos = max(positions, key=lambda p: p.get("weight_pct", 0))
    max_pct = max_pos.get("weight_pct", 0)
    warn_floor = threshold_pct * 0.9

    if max_pct > threshold_pct:
        sev = "violation"
        detail = f"{max_pos.get('ticker')} 비중 {max_pct}% 가 제한 {threshold_pct}% 초과"
    elif warn_floor <= max_pct < threshold_pct:
        sev = "warning"
        detail = f"{max_pos.get('ticker')} 비중 {max_pct}% — 제한 {threshold_pct}% 근접"
    else:
        sev = "pass"
        detail = f"최대 단일 종목 비중 {max_pct}% (제한 {threshold_pct}% 이내)"
    return CommandmentResult(
        commandment_id="2",
        title="단일 종목 <= 15%",
        severity=sev,
        detail=detail,
        metrics={"max_single_stock_pct": max_pct, "ticker": max_pos.get("ticker")},
    )
