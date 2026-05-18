"""Track Selector — 사용자 입력 → 전략가 ID 라우팅.

STRATEGY-TRACK-001 SPEC § Track Selector. 별도 페르소나 X — 각 전략가의
`manifest.yaml` `input_routing` 블록을 dispatcher 가 read 해 분기한다.

라우팅 우선순위:
  1. 명시 단축어 (long: / swing: / both: / ...) — manifest.input_routing.shortcuts.explicit
  2. `both:` 단축어 — fallback 외 모든 전략가 호출
  3. auto.conditions — target_meta 받아 평가 (v1 = placeholder, 분석가 v2 후 활성)
  4. fallback: true 인 전략가 (현재 = Track A 만)

plugin 확장 = `agents/strategists/<new_track>/manifest.yaml` 드롭 + input_routing
정의. `_scan_strategists()` 가 동적 인식 (코드 변경 0).

본 v1 시점 (2026-05-18) 호출처 = 인프라 + 테스트만. webapp/CLI 통합은
STRATEGY-TRACK-001 SPEC 세션 4 (후속 사이클).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGISTS_DIR = REPO_ROOT / "agents" / "strategists"

# `both:` 는 특별 단축어 — 어느 전략가 manifest 에도 explicit 으로 박지 않고
# selector 가 직접 처리한다 (모든 fallback 외 전략가 호출).
BOTH_SHORTCUT = "both:"


def _scan_strategists() -> dict[str, dict[str, Any]]:
    """agents/strategists/*/manifest.yaml glob → {strategist_id: input_routing dict}.

    manifest 없거나 input_routing 블록 없는 디렉토리는 skip (_template 같은 placeholder
    디렉토리 무시).

    Returns:
        {strategist_id: {
            "shortcuts": list[str],          # explicit 단축어 (lowercase)
            "auto_conditions": list[dict],   # auto.conditions
            "fallback": bool,                # fallback default 여부
        }}
    """
    if not STRATEGISTS_DIR.exists():
        return {}

    result: dict[str, dict[str, Any]] = {}
    for child in sorted(STRATEGISTS_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            # _template / _archive 같은 placeholder 디렉토리 skip
            continue
        manifest_path = child / "manifest.yaml"
        if not manifest_path.exists():
            continue

        try:
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception as e:  # noqa: BLE001
            log.warning("strategist_manifest_load_failed", path=str(manifest_path), error=str(e))
            continue

        routing = raw.get("input_routing") or {}
        shortcuts_cfg = (routing.get("shortcuts") or {}).get("explicit") or []
        shortcuts = [str(s).strip().lower() for s in shortcuts_cfg if str(s).strip()]
        auto_cfg = routing.get("auto") or {}
        auto_conditions = list(auto_cfg.get("conditions") or [])
        fallback = bool(routing.get("fallback", False))

        result[raw.get("id", child.name)] = {
            "shortcuts": shortcuts,
            "auto_conditions": auto_conditions,
            "fallback": fallback,
        }
    return result


@lru_cache(maxsize=1)
def _scan_strategists_cached() -> dict[str, dict[str, Any]]:
    """`_scan_strategists()` 결과 캐시. 테스트에서 새 전략가 디렉토리 추가 시
    `_scan_strategists_cached.cache_clear()` 호출."""
    return _scan_strategists()


def _normalize_input(text: str) -> str:
    """라우팅용 입력 정규화 — 앞 공백 제거 + lowercase."""
    return text.lstrip().lower()


def _match_explicit_shortcut(
    text_normalized: str, strategists: dict[str, dict[str, Any]]
) -> list[str]:
    """text 가 어느 전략가의 shortcuts.explicit 단축어로 시작하는지 매칭.

    매칭되면 해당 전략가 ID 들의 정렬된 리스트 반환 (보통 1개, 단축어가 여러 전략가에
    동시 등록되면 N개).
    """
    matched: list[str] = []
    for sid, routing in strategists.items():
        for sc in routing["shortcuts"]:
            if text_normalized.startswith(sc):
                matched.append(sid)
                break
    return sorted(matched)


def _match_auto_conditions(
    target_meta: dict[str, Any] | None, strategists: dict[str, dict[str, Any]]
) -> list[str]:
    """auto.conditions 기반 라우팅 — v1 placeholder.

    target_meta 가 None 또는 빈 dict 면 skip ([]). 분석가 v2 페르소나 작성 + team_outputs
    적재 후 본 함수가 target_meta 의 monthly_7ma_aligned / any_trigger_fired / market_cap
    등을 평가해 전략가 매칭.

    v1 = target_meta 가 있어도 conditions 평가 안 함 (placeholder 통과 검증용).
    """
    if not target_meta:
        return []
    # v1: placeholder. 분석가 v2 후 활성.
    # 향후 구현 예시:
    #   for sid, routing in strategists.items():
    #       if all(_eval_condition(target_meta, cond) for cond in routing["auto_conditions"]):
    #           matched.append(sid)
    return []


def _fallback_strategists(strategists: dict[str, dict[str, Any]]) -> list[str]:
    """input_routing.fallback == True 인 전략가 ID 들 (정렬)."""
    return sorted(sid for sid, routing in strategists.items() if routing["fallback"])


def select_tracks(
    user_input: str,
    *,
    target_meta: dict[str, Any] | None = None,
) -> list[str]:
    """사용자 입력 → 호출할 전략가 ID 들 (정렬된 리스트).

    Args:
        user_input: 사용자 메시지 텍스트 (예: "long: 삼성전자 어때", "swing: 카카오")
        target_meta: 종목 메타 (monthly_7ma_aligned / any_trigger_fired 등). v1 = placeholder

    Returns:
        호출할 전략가 ID 들 (정렬된 리스트). 항상 1개 이상 반환 (최후 fallback 보장).
        등록된 전략가가 0개면 빈 리스트.

    우선순위:
        1. `both:` 단축어 → fallback 외 모든 전략가 (현재 = Track A + Track B)
        2. 명시 단축어 (long:/swing:/...) → 매칭 전략가 ID 들
        3. auto.conditions (target_meta 필요) → 매칭 전략가들 (v1 = placeholder, 항상 skip)
        4. fallback: true 인 전략가 (현재 = Track A 만)

    Examples:
        >>> select_tracks("long: 삼성전자")     # ["track_a"]
        >>> select_tracks("swing: 카카오")      # ["track_b"]
        >>> select_tracks("both: 삼성전자")     # ["track_a", "track_b"]
        >>> select_tracks("삼성전자 어때")      # ["track_a"]  (fallback)
        >>> select_tracks("SWING: 카카오")      # ["track_b"]  (대소문자 무관)
    """
    strategists = _scan_strategists_cached()
    if not strategists:
        return []

    text = _normalize_input(user_input)

    # 1. both: 단축어 — 모든 fallback 외 전략가 호출
    if text.startswith(BOTH_SHORTCUT):
        # fallback 도 포함 — both: 는 명시적으로 "양쪽 평가" 요청이므로 fallback 여부 무관
        return sorted(strategists.keys())

    # 2. 명시 단축어 매칭
    explicit_matches = _match_explicit_shortcut(text, strategists)
    if explicit_matches:
        return explicit_matches

    # 3. auto.conditions (v1 = placeholder, 항상 [])
    auto_matches = _match_auto_conditions(target_meta, strategists)
    if auto_matches:
        return sorted(auto_matches)

    # 4. fallback
    return _fallback_strategists(strategists)
