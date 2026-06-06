"""Intent Classifier — 2-Stage 하이브리드 (결정론 + LLM Flash-lite + 캐싱).

PRODUCTION-UX-001 § 7 freeze 결단 4 정합. cycle 14 `collectors/anchors.py`
패턴 1:1 mirror.

흐름:
  1. normalize_input(raw) → normalized text
  2. Stage 1: scenario_keywords.yaml 의 결정론 룰 매칭
     - shortcuts (long:/swing:/both:) → 우선 분기
     - per-scenario keywords any-match → scenario_id 후보
     - 단일 후보 + ticker 추출 성공 시 → confidence=0.85 통과
  3. cache lookup (llm_call_cache type='intent_classification', TTL 30일)
  4. Stage 2 (Stage 1 miss 또는 confidence < 0.6 시):
     - system_prompt.md + user 발화 → LLM (FAST tier = Flash-lite default)
     - parse_json_response 강건화
     - 검증: scenario_id 1~30, agent_route ∈ 6 enum, confidence 0~1
     - 캐시 적재
  5. ticker 정규화 (resolve_ticker)
  6. manual_fallback_required 판정 (confidence < 0.6 OR ticker 필요한 시나리오에서 ticker null)

stage 라벨:
  - "deterministic" = Stage 1 hit
  - "cache" = Stage 2 cache hit
  - "llm" = Stage 2 실호출
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from core.inference.run_analyst import KR_NAME_TO_TICKER, resolve_ticker
from core.intent.cache import (
    cache_key,
    get_cached_classification,
    normalize_input,
    store_cached_classification,
)
from core.llm.client import call_llm, parse_json_response
from core.llm.tiers import resolve_model_for_area
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_KEYWORDS_PATH = REPO_ROOT / "config" / "scenario_keywords.yaml"
SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"

AgentRoute = Literal[
    "track_a", "track_b", "both", "analyst_direct", "refuse_or_guide", "pending_ms5"
]

# 시나리오별 default agent_route + analyst_ids (Stage 1 결정론 분기용). SPEC § 30 시나리오 매핑.
SCENARIO_DEFAULTS: dict[int, dict[str, Any]] = {
    1: {"agent_route": "track_a", "analyst_ids": []},
    2: {"agent_route": "both", "analyst_ids": []},
    3: {"agent_route": "analyst_direct", "analyst_ids": ["market_state_analyzer"]},
    4: {"agent_route": "analyst_direct", "analyst_ids": ["stock_picker", "market_state_analyzer"]},
    5: {"agent_route": "both", "analyst_ids": []},
    6: {"agent_route": "track_a", "analyst_ids": []},
    7: {"agent_route": "track_a", "analyst_ids": ["principle_guardian"]},
    8: {"agent_route": "track_a", "analyst_ids": []},
    9: {"agent_route": "analyst_direct", "analyst_ids": ["market_state_analyzer", "principle_guardian"]},
    10: {"agent_route": "track_a", "analyst_ids": []},
    11: {"agent_route": "pending_ms5", "analyst_ids": []},
}

# ticker 필요 시나리오 — null 이면 manual_fallback_required = true
TICKER_REQUIRED_SCENARIOS = {1, 2, 6, 7, 8}

VALID_AGENT_ROUTES = {
    "track_a", "track_b", "both", "analyst_direct", "refuse_or_guide", "pending_ms5"
}


class IntentClassifierError(RuntimeError):
    """Stage 2 LLM 호출 실패 또는 결과 검증 실패."""


@dataclass
class IntentClassification:
    """사용자 발화 분류 결과 풀세트 — production-chat 호출처 (router) 가 read."""

    scenario_id: int
    ticker: str | None
    ticker_display: str | None
    agent_route: str
    analyst_ids: list[str]
    confidence: float
    manual_fallback_required: bool
    stage: Literal["deterministic", "cache", "llm"]
    latency_ms: int
    raw_input: str
    reasoning: str | None = None
    secondary_ticker: str | None = None            # 비교 질의(scenario 4) 2번째 종목
    secondary_ticker_display: str | None = None
    upstream_error: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# scenario_keywords.yaml 로드 (lazy + lru_cache 와 동일 효과)
# ---------------------------------------------------------------------------

_KEYWORDS_CACHE: dict | None = None


def _load_keywords() -> dict:
    global _KEYWORDS_CACHE
    if _KEYWORDS_CACHE is None:
        if not SCENARIO_KEYWORDS_PATH.exists():
            log.warning("scenario_keywords_missing", path=str(SCENARIO_KEYWORDS_PATH))
            _KEYWORDS_CACHE = {"shortcuts": {}, "scenarios": {}}
        else:
            try:
                _KEYWORDS_CACHE = (
                    yaml.safe_load(SCENARIO_KEYWORDS_PATH.read_text(encoding="utf-8")) or {}
                )
            except Exception as e:  # noqa: BLE001
                log.warning("scenario_keywords_load_failed", error=str(e))
                _KEYWORDS_CACHE = {"shortcuts": {}, "scenarios": {}}
    return _KEYWORDS_CACHE


def reload_keywords() -> None:
    """테스트/hot reload 용 — 캐시 클리어."""
    global _KEYWORDS_CACHE
    _KEYWORDS_CACHE = None


# ---------------------------------------------------------------------------
# Stage 1: 결정론 keyword 매칭
# ---------------------------------------------------------------------------


def _extract_ticker_from_text(text: str) -> tuple[str | None, str | None]:
    """발화에서 ticker 추출 — 6자리 숫자 OR KR_NAME_TO_TICKER 매핑.

    longest-name-first 탐색 (e.g. "삼성바이오로직스" 가 "삼성" 보다 먼저).

    Returns:
        (ticker_6digit, display_name) 또는 (None, None).
    """
    # 1) 6자리 숫자 직접 매칭
    m = re.search(r"\b(\d{6})\b", text)
    if m:
        ticker = m.group(1)
        from core.inference.run_analyst import KR_TICKER_TO_NAME

        return ticker, KR_TICKER_TO_NAME.get(ticker)

    # 2) 종목명 매칭 — 긴 이름 먼저 (substring 충돌 방지)
    names = sorted(KR_NAME_TO_TICKER.keys(), key=len, reverse=True)
    text_lower = text.lower()
    for name in names:
        if name.lower() in text_lower:
            ticker, display = resolve_ticker(name)
            if ticker is not None:
                return ticker, display
    return None, None


# 비교 질의 — 본문에 등장한 모든 종목을 등장 순서대로 (ANSWER-FIDELITY-001 F3)
COMPARISON_SCENARIO_ID = 4


def _extract_tickers_from_text(text: str, limit: int = 2) -> list[tuple[str, str | None]]:
    """발화에서 종목 여러 개를 **등장 위치 순서**로 추출 (중복·겹침 제거).

    "삼성전자랑 SK하이닉스 중에" → [(005930, 삼성전자), (000660, SK하이닉스)].
    비교 질의(scenario 4)에서 양 종목 prefetch 용. limit 개까지.
    """
    from core.inference.run_analyst import KR_TICKER_TO_NAME

    found: list[tuple[int, str, str | None]] = []
    seen: set[str] = set()

    # 6자리 코드
    for m in re.finditer(r"\b(\d{6})\b", text):
        t = m.group(1)
        if t not in seen:
            found.append((m.start(), t, KR_TICKER_TO_NAME.get(t)))
            seen.add(t)

    # 종목명 — 긴 이름 먼저로 매칭하되, 이미 매칭된 span 과 겹치면 skip (부분문자열 중복 방지)
    text_lower = text.lower()
    occupied: list[tuple[int, int]] = []
    for name in sorted(KR_NAME_TO_TICKER.keys(), key=len, reverse=True):
        idx = text_lower.find(name.lower())
        if idx == -1:
            continue
        span = (idx, idx + len(name))
        if any(not (span[1] <= s or span[0] >= e) for s, e in occupied):
            continue
        ticker, display = resolve_ticker(name)
        if ticker and ticker not in seen:
            found.append((idx, ticker, display))
            seen.add(ticker)
            occupied.append(span)

    found.sort(key=lambda x: x[0])
    return [(t, d) for _, t, d in found[:limit]]


def _stage1_classify(normalized: str) -> dict[str, Any] | None:
    """결정론 keyword 매칭 — match 없으면 None.

    Returns:
        dict (scenario_id, agent_route, analyst_ids, confidence, reasoning, ticker_from_text)
        또는 None (Stage 2 로 위임).
    """
    rules = _load_keywords()
    shortcuts = rules.get("shortcuts") or {}
    scenarios = rules.get("scenarios") or {}

    # 1) 단축어 (long:/swing:/both:) — 명시 분기
    for shortcut, route_info in shortcuts.items():
        sc = str(shortcut).lower()
        if normalized.startswith(sc):
            return {
                "scenario_id": int(route_info.get("scenario_id", 2)),
                "agent_route": route_info.get("agent_route", "track_a"),
                "analyst_ids": list(route_info.get("analyst_ids") or []),
                "confidence": 0.95,
                "reasoning": f"shortcut '{shortcut}' 명시 매칭",
            }

    # 2) 시나리오별 keyword any-match
    matched: list[tuple[int, int]] = []  # (scenario_id, match_count)
    for sid_str, scn in scenarios.items():
        try:
            sid = int(sid_str)
        except (TypeError, ValueError):
            continue
        kws = scn.get("keywords") or []
        count = sum(1 for kw in kws if str(kw).lower() in normalized)
        if count > 0:
            matched.append((sid, count))

    if not matched:
        return None

    # 가장 많이 매치된 단일 시나리오 → confidence 비례
    matched.sort(key=lambda x: (-x[1], x[0]))
    top_sid, top_count = matched[0]

    # 단일 후보면 confidence 0.85, 다중 후보면 0.65 (Stage 2 로 위임할만함)
    if len(matched) >= 2 and matched[1][1] == top_count:
        # 동률 → 모호함, Stage 2 로
        return None

    confidence = 0.90 if top_count >= 2 else 0.80
    defaults = SCENARIO_DEFAULTS.get(top_sid, {})
    return {
        "scenario_id": top_sid,
        "agent_route": defaults.get("agent_route", "track_a"),
        "analyst_ids": list(defaults.get("analyst_ids") or []),
        "confidence": confidence,
        "reasoning": f"Stage 1 keyword (match_count={top_count})",
    }


# ---------------------------------------------------------------------------
# Stage 2: LLM 분류
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_CACHE: str | None = None


def _load_system_prompt() -> str:
    global _SYSTEM_PROMPT_CACHE
    if _SYSTEM_PROMPT_CACHE is None:
        if SYSTEM_PROMPT_PATH.exists():
            _SYSTEM_PROMPT_CACHE = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        else:
            _SYSTEM_PROMPT_CACHE = "You are an intent classifier. Output JSON only."
    return _SYSTEM_PROMPT_CACHE


def _validate_llm_result(result: Any) -> dict[str, Any] | None:
    """LLM JSON 결과 검증 — 유효하면 정규화 dict, 무효면 None."""
    if not isinstance(result, dict):
        return None
    try:
        sid = int(result.get("scenario_id", 0))
    except (TypeError, ValueError):
        return None
    if not (1 <= sid <= 30):
        return None
    route = str(result.get("agent_route", "")).lower()
    if route not in VALID_AGENT_ROUTES:
        return None
    try:
        conf = float(result.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    conf = max(0.0, min(1.0, conf))
    analyst_ids = result.get("analyst_ids") or []
    if not isinstance(analyst_ids, list):
        analyst_ids = []
    analyst_ids = [str(a) for a in analyst_ids if a]
    ticker_raw = result.get("ticker")
    ticker_str = str(ticker_raw).strip() if ticker_raw else None
    reasoning = str(result.get("reasoning", ""))[:500] or None
    return {
        "scenario_id": sid,
        "ticker": ticker_str,
        "agent_route": route,
        "analyst_ids": analyst_ids,
        "confidence": conf,
        "reasoning": reasoning,
    }


async def _stage2_classify_via_llm(
    normalized: str, *, raw_input: str, skip_cache: bool = False, provider: str | None = None
) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    """Stage 2 LLM 분류 + 캐싱.

    Returns:
        (validated_result | None, stage_label, extras dict).
        stage_label = "cache" | "llm".
        extras = LLM 호출 메타 (model, tokens, cost, latency_ms, upstream_error).
    """
    extras: dict[str, Any] = {}
    provider_resolved, model = resolve_model_for_area("intent_classifier")
    if provider:
        provider_resolved = provider
    # mock provider 면 model 도 mock 으로 (cache key 분리)
    key = cache_key(normalized, model)

    if not skip_cache:
        cached = get_cached_classification(key)
        if cached is not None:
            return _validate_llm_result(cached), "cache", {"model": model, "cached": True}

    system_prompt = _load_system_prompt()
    user_msg = raw_input.strip()
    started = time.monotonic()
    try:
        resp = await call_llm(
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
            model=model,
            max_tokens=400,
            temperature=0.0,
            provider=provider_resolved if provider_resolved != "mock" else None,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "intent_stage2_call_failed",
            error_type=type(e).__name__,
            error=str(e),
        )
        return None, "llm", {
            "model": model,
            "upstream_error": str(e) or type(e).__name__,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    latency_ms = int((time.monotonic() - started) * 1000)
    content = resp.get("content", "")
    try:
        parsed = parse_json_response(content)
    except Exception as e:  # noqa: BLE001
        log.warning("intent_stage2_json_parse_failed", error=str(e), content=content[:200])
        return None, "llm", {
            "model": model,
            "upstream_error": f"json_parse:{type(e).__name__}",
            "latency_ms": latency_ms,
        }

    validated = _validate_llm_result(parsed)
    if validated is None:
        log.warning("intent_stage2_invalid_result", parsed=parsed)
        return None, "llm", {
            "model": model,
            "upstream_error": "validation_failed",
            "latency_ms": latency_ms,
        }

    raw_meta = resp.get("raw") or {}
    is_mock = bool(raw_meta.get("mock"))
    extras = {
        "model": model,
        "tokens_in": int(resp.get("tokens_in", 0)),
        "tokens_out": int(resp.get("tokens_out", 0)),
        "cost_usd": float(resp.get("cost_usd", 0.0)),
        "latency_ms": latency_ms,
        "is_mock": is_mock,
        "upstream_error": raw_meta.get("error"),
    }

    if not skip_cache and not is_mock:
        store_cached_classification(
            key,
            validated,
            model=model,
            tokens_in=extras["tokens_in"],
            tokens_out=extras["tokens_out"],
            cost_usd=extras["cost_usd"],
        )
    return validated, "llm", extras


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


async def classify_intent(
    raw_input: str,
    *,
    skip_cache: bool = False,
    skip_stage2: bool = False,
    provider: str | None = None,
) -> IntentClassification:
    """사용자 발화 → IntentClassification 풀세트.

    Args:
        raw_input: 사용자 자연어 메시지.
        skip_cache: True 면 캐시 bypass (테스트용).
        skip_stage2: True 면 Stage 2 LLM 호출 skip — Stage 1 hit 만 반환, miss 시 fallback.
        provider: 명시 backend (테스트용). None 이면 config + auto fallback.

    Returns:
        IntentClassification. stage="deterministic"/"cache"/"llm" 중 하나.
        Stage 2 도 실패하면 manual_fallback_required=True + agent_route="refuse_or_guide".
    """
    started = time.monotonic()
    raw = (raw_input or "").strip()
    if not raw:
        return IntentClassification(
            scenario_id=0,
            ticker=None,
            ticker_display=None,
            agent_route="refuse_or_guide",
            analyst_ids=[],
            confidence=0.0,
            manual_fallback_required=True,
            stage="deterministic",
            latency_ms=0,
            raw_input=raw,
            reasoning="empty_input",
        )

    normalized = normalize_input(raw)

    # ticker 추출은 Stage 와 무관하게 미리
    text_ticker, text_display = _extract_ticker_from_text(raw)

    # 비교 질의용 2번째 종목 (primary 와 다른 첫 종목) — scenario 4 return 에만 주입 (F3)
    sec_ticker: str | None = None
    sec_display: str | None = None
    for _t, _d in _extract_tickers_from_text(raw, limit=3):
        if _t != text_ticker:
            sec_ticker, sec_display = _t, _d
            break

    # Stage 1 — 결정론
    s1 = _stage1_classify(normalized)
    if s1 is not None and s1["confidence"] >= 0.80:
        sid = int(s1["scenario_id"])
        ticker_required = sid in TICKER_REQUIRED_SCENARIOS
        manual_fb = ticker_required and text_ticker is None
        return IntentClassification(
            scenario_id=sid,
            ticker=text_ticker,
            ticker_display=text_display,
            agent_route=s1["agent_route"],
            analyst_ids=list(s1.get("analyst_ids") or []),
            confidence=float(s1["confidence"]),
            manual_fallback_required=manual_fb,
            stage="deterministic",
            latency_ms=int((time.monotonic() - started) * 1000),
            raw_input=raw,
            reasoning=s1.get("reasoning"),
            secondary_ticker=sec_ticker if sid == COMPARISON_SCENARIO_ID else None,
            secondary_ticker_display=sec_display if sid == COMPARISON_SCENARIO_ID else None,
        )

    if skip_stage2:
        # Stage 1 miss + Stage 2 skip → refuse_or_guide
        return IntentClassification(
            scenario_id=0,
            ticker=text_ticker,
            ticker_display=text_display,
            agent_route="refuse_or_guide",
            analyst_ids=[],
            confidence=0.0,
            manual_fallback_required=True,
            stage="deterministic",
            latency_ms=int((time.monotonic() - started) * 1000),
            raw_input=raw,
            reasoning="stage1_miss_stage2_skipped",
        )

    # Stage 2 — LLM
    s2, stage_label, extras = await _stage2_classify_via_llm(
        normalized, raw_input=raw, skip_cache=skip_cache, provider=provider
    )

    if s2 is None:
        # 완전 실패 → manual fallback
        return IntentClassification(
            scenario_id=0,
            ticker=text_ticker,
            ticker_display=text_display,
            agent_route="refuse_or_guide",
            analyst_ids=[],
            confidence=0.0,
            manual_fallback_required=True,
            stage="llm",
            latency_ms=int((time.monotonic() - started) * 1000),
            raw_input=raw,
            reasoning=extras.get("upstream_error") or "stage2_failed",
            upstream_error=extras.get("upstream_error"),
            extras=extras,
        )

    # LLM 결과 후처리: ticker 는 text 매칭 우선 (LLM 환각 회피)
    ticker_final = text_ticker
    ticker_display_final = text_display
    if ticker_final is None and s2.get("ticker"):
        ticker_final, ticker_display_final = resolve_ticker(s2["ticker"])

    sid = int(s2["scenario_id"])
    conf = float(s2["confidence"])
    ticker_required = sid in TICKER_REQUIRED_SCENARIOS
    manual_fb = (conf < 0.6) or (ticker_required and ticker_final is None)

    return IntentClassification(
        scenario_id=sid,
        ticker=ticker_final,
        ticker_display=ticker_display_final,
        agent_route=s2["agent_route"],
        analyst_ids=list(s2.get("analyst_ids") or []),
        confidence=conf,
        manual_fallback_required=manual_fb,
        stage="cache" if stage_label == "cache" else "llm",
        latency_ms=int((time.monotonic() - started) * 1000),
        raw_input=raw,
        reasoning=s2.get("reasoning"),
        secondary_ticker=sec_ticker if sid == COMPARISON_SCENARIO_ID else None,
        secondary_ticker_display=sec_display if sid == COMPARISON_SCENARIO_ID else None,
        upstream_error=extras.get("upstream_error"),
        extras=extras,
    )
