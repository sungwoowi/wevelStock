"""Deterministic input-hash computation for idempotent LLM calls."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(obj: Any) -> str:
    """Produce a stable JSON string (sorted keys, no whitespace quirks)."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_input_hash(
    *,
    input_data: dict[str, Any],
    context_snapshot: dict[str, Any] | None = None,
    model: str = "rule-based",
    contract_version: str = "1.0",
    canon_version: int | None = None,
) -> str:
    payload = {
        "input": canonicalize(input_data),
        "context": canonicalize(context_snapshot or {}),
        "model": model,
        "contract_version": contract_version,
        "canon_version": canon_version,
    }
    serialized = canonicalize(payload).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    return f"sha256:{digest}"
