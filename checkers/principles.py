"""7 Commandments checker — pure function wrapper.

Usage:
    from checkers.principles import run_all_checks, aggregate
    results = run_all_checks(portfolio, thresholds)
    verdict, reasons, data = aggregate(results)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from checkers.commandments import CommandmentResult
from checkers.commandments import (
    data_based,
    multi_indicator,
    no_emotion,
    single_stock,
    stop_loss,
    trading_ratio,
    weight_limit,
)


@dataclass
class Thresholds:
    """Configurable thresholds for commandment checks."""

    total_weight_pct: float = 80.0
    single_stock_pct: float = 15.0
    trading_weight_pct: float = 20.0


def run_all_checks(
    portfolio: dict,
    thresholds: Thresholds | None = None,
) -> list[CommandmentResult]:
    """Run all 7 commandment checks and return individual results."""
    t = thresholds or Thresholds()
    return [
        weight_limit.check(portfolio, t.total_weight_pct),
        single_stock.check(portfolio, t.single_stock_pct),
        trading_ratio.check(portfolio, t.trading_weight_pct),
        stop_loss.check(portfolio),
        multi_indicator.check(portfolio),
        data_based.check(portfolio),
        no_emotion.check(portfolio),
    ]


def aggregate(
    results: list[CommandmentResult],
) -> tuple[str, int, list[str], dict[str, Any]]:
    """Aggregate commandment results into verdict, confidence, reasons, data.

    Returns:
        (verdict, confidence, reasons, data)
    """
    violations = [r for r in results if r.is_violation]
    warnings = [r for r in results if r.is_warning]

    if violations:
        verdict = "violation"
        confidence = 95
    elif warnings:
        verdict = "warning"
        confidence = 85
    else:
        verdict = "compliant"
        confidence = 100

    reasons = [f"[계명 {r.commandment_id}] {r.detail}" for r in results]

    metrics: dict[str, Any] = {}
    for r in results:
        metrics.update(r.metrics)

    data = {
        **metrics,
        "violations": [
            {
                "commandment": r.commandment_id,
                "title": r.title,
                "detail": r.detail,
                "severity": r.severity,
            }
            for r in violations
        ],
        "warnings": [
            {
                "commandment": r.commandment_id,
                "title": r.title,
                "detail": r.detail,
                "severity": r.severity,
            }
            for r in warnings
        ],
        "passes": [
            {"commandment": r.commandment_id, "title": r.title}
            for r in results
            if r.severity == "pass"
        ],
    }
    return verdict, confidence, reasons, data
