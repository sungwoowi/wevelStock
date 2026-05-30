"""score_inputs.yaml 로더 (INFRA-SCORE-INPUTS-001).

raw 지표 → 0~10 축 매핑 breakpoints + advisory 상수의 단일 소스.
label_dictionary 로더 패턴 mirror (모듈 캐시 + reload). watchdog hot reload 호환.

technicals.py / flow_inputs.py 가 `get_breakpoints(group, axis)` 로 소비.
순수 매핑(scoring.map_to_axis)에 DI 로 주입 → 테스트는 명시 breakpoints, 런타임은 config.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCORE_INPUTS_PATH = REPO_ROOT / "config" / "score_inputs.yaml"

_CONFIG_CACHE: dict[str, Any] | None = None

_EMPTY: dict[str, Any] = {"technicals": {}, "flow": {}, "advisory": {}}


def load_score_inputs_config() -> dict[str, Any]:
    """config/score_inputs.yaml 로드 (캐시). 부재·파싱 실패 시 빈 dict fallback."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        if not SCORE_INPUTS_PATH.exists():
            log.warning("score_inputs_config_missing", path=str(SCORE_INPUTS_PATH))
            _CONFIG_CACHE = dict(_EMPTY)
        else:
            try:
                _CONFIG_CACHE = yaml.safe_load(
                    SCORE_INPUTS_PATH.read_text(encoding="utf-8")
                ) or dict(_EMPTY)
            except Exception as e:  # noqa: BLE001
                log.warning("score_inputs_config_load_failed", error=str(e))
                _CONFIG_CACHE = dict(_EMPTY)
    return _CONFIG_CACHE


def reload_score_inputs_config() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def get_breakpoints(group: str, axis: str) -> list[tuple[float, float]]:
    """group(technicals|flow) 의 axis breakpoints → [(x, y), ...]. 부재 시 빈 리스트.

    빈 리스트 반환 시 호출부(map_to_axis)는 ValueError → collector 가 해당 축 None 처리.
    """
    cfg = load_score_inputs_config()
    raw = ((cfg.get(group) or {}).get(axis) or {}).get("breakpoints") or []
    return [(float(x), float(y)) for x, y in raw]


def get_advisory_constant(key: str, default: float) -> float:
    """advisory 상수 (예: theme_match_neutral). 부재 시 default."""
    cfg = load_score_inputs_config()
    val = (cfg.get("advisory") or {}).get(key)
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default
