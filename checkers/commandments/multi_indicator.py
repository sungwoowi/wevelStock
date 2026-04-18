"""Commandment 5 — 최소 3개 지표/근거 교차 검증."""
from __future__ import annotations

from checkers.commandments.base import CommandmentResult


def check(portfolio: dict, min_reasons: int = 3) -> CommandmentResult:
    positions = portfolio.get("positions", [])
    shallow = [
        p.get("ticker")
        for p in positions
        if len(p.get("rationale_at_entry") or []) < min_reasons
    ]
    if shallow:
        return CommandmentResult(
            commandment_id="5",
            title=f"진입 근거 >= {min_reasons}개",
            severity="warning",
            detail=f"근거가 {min_reasons}개 미만인 종목: {', '.join(shallow)}",
            metrics={"shallow_tickers": shallow, "min_reasons": min_reasons},
        )
    return CommandmentResult(
        commandment_id="5",
        title=f"진입 근거 >= {min_reasons}개",
        severity="pass",
        detail=f"모든 포지션이 최소 {min_reasons}개 근거 제시",
    )
