"""Commandment 6 — 데이터/근거 기반 진입."""
from __future__ import annotations

from checkers.commandments.base import CommandmentResult


def check(portfolio: dict) -> CommandmentResult:
    positions = portfolio.get("positions", [])
    without_rationale = [
        p.get("ticker")
        for p in positions
        if not (p.get("rationale_at_entry") or [])
    ]
    if without_rationale:
        return CommandmentResult(
            commandment_id="6",
            title="데이터 없이 추측 금지",
            severity="violation",
            detail=f"진입 근거 미기록: {', '.join(without_rationale)}",
            metrics={"missing_rationale": without_rationale},
        )
    return CommandmentResult(
        commandment_id="6",
        title="데이터 없이 추측 금지",
        severity="pass",
        detail="모든 포지션에 진입 근거 기록됨",
    )
