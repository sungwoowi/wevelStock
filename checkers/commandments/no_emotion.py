"""Commandment 7 — 감정(FOMO/공포)로 매매하지 않음."""
from __future__ import annotations

from checkers.commandments.base import CommandmentResult

EMOTIONAL_FLAGS = {"fomo", "chase", "news-chase", "no-analysis", "panic"}


def check(portfolio: dict) -> CommandmentResult:
    positions = portfolio.get("positions", [])
    flagged = []
    for p in positions:
        pf = set(p.get("flags") or [])
        hits = pf & EMOTIONAL_FLAGS
        if hits:
            flagged.append({"ticker": p.get("ticker"), "flags": sorted(hits)})
    if flagged:
        tickers = ", ".join(f"{f['ticker']}({','.join(f['flags'])})" for f in flagged)
        return CommandmentResult(
            commandment_id="7",
            title="감정(FOMO/공포) 매매 금지",
            severity="violation",
            detail=f"감정 매매 의심 포지션: {tickers}",
            metrics={"flagged": flagged},
        )
    return CommandmentResult(
        commandment_id="7",
        title="감정(FOMO/공포) 매매 금지",
        severity="pass",
        detail="감정 매매 플래그 없음",
    )
