"""Commandment 4 — 모든 포지션에 손절선 설정."""
from __future__ import annotations

from checkers.commandments.base import CommandmentResult


def check(portfolio: dict) -> CommandmentResult:
    positions = portfolio.get("positions", [])
    missing = [p.get("ticker") for p in positions if p.get("stop_loss") is None]
    if missing:
        return CommandmentResult(
            commandment_id="4",
            title="손절선 없이 진입 금지",
            severity="violation",
            detail=f"손절선 미설정 종목: {', '.join(missing)}",
            metrics={"missing_tickers": missing, "missing_count": len(missing)},
        )
    return CommandmentResult(
        commandment_id="4",
        title="손절선 없이 진입 금지",
        severity="pass",
        detail="모든 포지션에 손절선 설정됨",
        metrics={"missing_count": 0},
    )
