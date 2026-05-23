"""LLM 3 계층 (FAST / BALANCED / DEEP) 영역별 모델 해석기.

PRODUCTION-UX-001 — Gemini-Anthropic 1:1 mirror tier 정책. 영역 이름 →
config.llm.areas → tier name → config.llm.tiers[tier][provider] → 모델 문자열.

호출처:
  - core/intent/classifier.py — area="intent_classifier"
  - core/intent/formatter.py (PROD-UX-2) — area="answer_formatter"
  - collectors/anchors.py (LLM-TIER-MIGRATION-001 후속) — area="anchors_stage2"

provider 분기: config.llm.provider 가 anthropic | gemini 중 하나면 그쪽 모델,
claude_code 면 anthropic 모델 (CLI 도 Anthropic 모델 호스팅) 을 사용.
mock 이면 모델 이름은 무관 (mock 응답).
"""
from __future__ import annotations

from typing import Literal

from core.config import get_config
from core.logging import get_logger

log = get_logger(__name__)

AreaName = Literal[
    "intent_classifier",
    "answer_formatter",
    "analyst",
    "strategist",
    "anchors_stage2",
    "retrospect",
]


def resolve_model_for_area(area: str) -> tuple[str, str]:
    """area 이름 → (provider, model) 반환.

    Args:
        area: config.llm.areas 의 필드명 ("intent_classifier" 등)

    Returns:
        (provider, model). provider 는 "gemini" | "anthropic" | "claude_code" | "mock".
        model 은 그 provider 의 모델 식별자 (예: "gemini-2.5-flash-lite").

    Fallback:
        - areas 에 area 없으면 → balanced
        - provider 가 claude_code → anthropic 의 모델 사용
        - provider 가 mock → ("mock", "mock") 반환 (실제 호출 시 mock 응답)
    """
    cfg = get_config().llm
    tier_name = getattr(cfg.areas, area, None) or "balanced"
    tier_models = getattr(cfg.tiers, tier_name, None)
    if tier_models is None:
        log.warning("llm_tier_unknown", area=area, tier=tier_name)
        return cfg.provider, cfg.gemini.model

    provider = cfg.provider
    if provider == "mock":
        return "mock", "mock"
    if provider == "claude_code":
        # claude_code CLI 는 Anthropic 모델 호스팅
        return "claude_code", tier_models.anthropic
    if provider == "gemini":
        return "gemini", tier_models.gemini
    # anthropic
    return "anthropic", tier_models.anthropic


def model_for_tier(tier: str) -> str:
    """tier 이름 직접 → 현재 provider 의 모델. area 우회용 (테스트/디버깅)."""
    cfg = get_config().llm
    tier_models = getattr(cfg.tiers, tier, None)
    if tier_models is None:
        return cfg.gemini.model
    if cfg.provider == "gemini":
        return tier_models.gemini
    return tier_models.anthropic
