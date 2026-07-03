"""Operator (운영자) API — LLM 비용 원장 조회. (LLM-COST-LEDGER-001)

말은 '운영자 모드'지만 현재는 webapp `/ops/llm-cost` 한 화면이 소비하는 REST.
향후 유저 비노출 URL 로 분리 예정. 얇게 — core.llm.ledger.cost_summary 로 위임.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from core.llm.ledger import cost_summary
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/ops")


@router.get("/llm-cost")
async def llm_cost(days: int = Query(7, ge=1, le=90)) -> dict:
    """최근 N일 LLM 비용 원장 집계 — 벤더(provider)·모델·질의영역(call_type)·일자별.

    벤더/모델을 바꿔도 같은 축으로 추적된다. 서버가 도는 동안 모든 call_llm 이
    llm_cost_ledger 에 1행씩 쌓이므로, 하루만 돌려도 어디서 비용이 나갔는지 드러난다.
    """
    return cost_summary(days=days)
