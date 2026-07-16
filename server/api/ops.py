"""Operator (운영자) API — LLM 비용 원장 조회. (LLM-COST-LEDGER-001)

말은 '운영자 모드'지만 현재는 webapp `/ops/llm-cost` 한 화면이 소비하는 REST.
향후 유저 비노출 URL 로 분리 예정. 얇게 — core.llm.ledger.cost_summary 로 위임.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Body, HTTPException, Query

from core.config import get_config
from core.config.loader import RUNTIME_PATH, env
from core.llm.ledger import cost_summary
from core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/ops")

_PROVIDERS = ("gemini", "claude_code", "anthropic", "mock")


@router.get("/llm-cost")
async def llm_cost(days: int = Query(7, ge=1, le=90)) -> dict:
    """최근 N일 LLM 비용 원장 집계 — 벤더(provider)·모델·질의영역(call_type)·일자별.

    벤더/모델을 바꿔도 같은 축으로 추적된다. 서버가 도는 동안 모든 call_llm 이
    llm_cost_ledger 에 1행씩 쌓이므로, 하루만 돌려도 어디서 비용이 나갔는지 드러난다.
    """
    return cost_summary(days=days)


@router.get("/llm-provider")
async def get_llm_provider() -> dict:
    """현재 LLM provider + 전환 가능 옵션 + 각 백엔드 사용 가능 여부(키/환경).

    - gemini: GOOGLE_AI_API_KEY 필요 (유료 티어면 지출 발생)
    - claude_code: 로컬 `claude` CLI 구독 OAuth (API 키 불필요, 구독 사용량 한도)
    - anthropic: ANTHROPIC_API_KEY 필요 (토큰당 과금)
    """
    env_forced = env("LLM_PROVIDER")  # .env 오버라이드가 걸려 있으면 웹UI 변경은 무시됨
    return {
        "provider": get_config().llm.provider,
        "options": list(_PROVIDERS),
        "availability": {
            "gemini": bool(env("GOOGLE_AI_API_KEY")),
            "claude_code": True,  # 로컬 CLI — 런타임 호출 시 인증 검증
            "anthropic": bool(env("ANTHROPIC_API_KEY")),
            "mock": True,
        },
        "env_override": env_forced if env_forced in _PROVIDERS else None,
    }


@router.post("/llm-provider")
async def set_llm_provider(provider: str = Body(..., embed=True)) -> dict:
    """LLM provider 전환 — runtime.yaml `llm.provider` 를 치환(주석 보존) → watchdog 핫리로드.

    재시작 불필요. .env `LLM_PROVIDER` 오버라이드가 걸린 경우엔 파일을 바꿔도 기동 시
    env 가 이겨서 효과 없음 → 그 사실을 응답에 알린다.
    """
    if provider not in _PROVIDERS:
        raise HTTPException(400, f"provider 는 {_PROVIDERS} 중 하나여야 함")

    text = RUNTIME_PATH.read_text(encoding="utf-8")
    # llm 직속(2칸 들여쓰기) provider 라인만 치환 — tiers/areas 의 깊은 provider 는 안 건드림.
    new_text, n = re.subn(
        r"(?m)^(  provider:)[^\n]*$", rf"\1 {provider}", text, count=1
    )
    if n == 0:
        raise HTTPException(500, "runtime.yaml 에서 llm.provider 라인을 찾지 못함")
    RUNTIME_PATH.write_text(new_text, encoding="utf-8")

    env_forced = env("LLM_PROVIDER")
    log.info("llm_provider_switched", provider=provider, env_override=env_forced)
    return {
        "provider": provider,
        "applied": env_forced not in _PROVIDERS,  # env 오버라이드 없으면 즉시 반영
        "env_override_wins": env_forced if env_forced in _PROVIDERS else None,
        "note": (
            f".env LLM_PROVIDER={env_forced} 가 걸려 있어 파일 변경은 재기동 시 무시됩니다."
            if env_forced in _PROVIDERS else "watchdog 핫리로드로 즉시 반영됩니다."
        ),
    }
