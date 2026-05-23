"""Intent Classifier — PRODUCTION-UX-001.

자연어 발화 → scenario_id (1~30) + ticker + agent_route. 2-Stage 하이브리드
(결정론 keyword + LLM Flash-lite + 캐싱) + manual fallback.

진입점:
    from core.intent import classify_intent, route_intent

    classification = await classify_intent("삼성전자 살까")
    response = await route_intent(classification, messages, provider=None)
"""
from core.intent.classifier import (
    IntentClassification,
    IntentClassifierError,
    classify_intent,
)
from core.intent.router import (
    RouteResponse,
    route_intent,
    route_intent_stream,
)

__all__ = [
    "IntentClassification",
    "IntentClassifierError",
    "classify_intent",
    "RouteResponse",
    "route_intent",
    "route_intent_stream",
]
