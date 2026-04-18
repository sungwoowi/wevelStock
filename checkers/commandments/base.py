"""Base types and helpers for commandment checkers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["pass", "warning", "violation"]


@dataclass
class CommandmentResult:
    """Outcome of a single commandment check."""

    commandment_id: str
    title: str
    severity: Severity
    detail: str
    metrics: dict = field(default_factory=dict)

    @property
    def is_violation(self) -> bool:
        return self.severity == "violation"

    @property
    def is_warning(self) -> bool:
        return self.severity == "warning"
