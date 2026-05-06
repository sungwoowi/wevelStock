"""Analyst inference layer — 분석가 단일 호출 인터페이스.

`run_analyst(analyst_id, messages)` 가 핵심. CLI(chat/ask), 텔레그램, FastAPI,
MCP 등 모든 추론부 조회 인터페이스가 이 함수를 wrap 한다.
"""
from core.inference.run_analyst import (
    AnalystNotFoundError,
    AnalystResponse,
    AnalystSpec,
    load_analyst_spec,
    run_analyst,
)

__all__ = [
    "AnalystNotFoundError",
    "AnalystResponse",
    "AnalystSpec",
    "load_analyst_spec",
    "run_analyst",
]
