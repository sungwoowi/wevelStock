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


_RR_RULE_DEFAULTS: dict[str, Any] = {
    "atr_period": 14,
    "atr_k_floor": 1.5,
    "atr_k_cap": 3.0,
    "swing_timeframe": "daily",
}


def get_rr_rule() -> dict[str, Any]:
    """R/R 산출 규칙 파라미터 (SLOT S3). technicals.rr_rule 블록 + 결측 키 default 병합.

    하드코딩 금지(CLAUDE.md #9) — atr_period/atr_k/swing_timeframe 는 config 가 권위.
    부재·타입 오류 키는 default 로 메움 (collector 가 항상 완전한 dict 수용).
    """
    cfg = load_score_inputs_config()
    raw = (cfg.get("technicals") or {}).get("rr_rule") or {}
    rule = dict(_RR_RULE_DEFAULTS)
    for key, default in _RR_RULE_DEFAULTS.items():
        val = raw.get(key)
        if val is None:
            continue
        if isinstance(default, str):
            rule[key] = str(val)
        else:
            try:
                rule[key] = type(default)(val)
            except (TypeError, ValueError):
                rule[key] = default
    return rule


def get_theme_authority() -> dict[str, list[str]]:
    """테마 → 권위 주체 매핑 (SLOT S1/S8). flow.theme_authority 블록. 부재 시 빈 dict."""
    cfg = load_score_inputs_config()
    raw = (cfg.get("flow") or {}).get("theme_authority") or {}
    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        if isinstance(v, list):
            out[str(k)] = [str(x) for x in v]
    return out


def get_theme_taxonomy() -> dict[str, str]:
    """테마 key → 한국어 라벨 (LLM Stage 2 분류 후보). flow.theme_taxonomy. 부재 시 빈 dict."""
    cfg = load_score_inputs_config()
    raw = (cfg.get("flow") or {}).get("theme_taxonomy") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


_S_WEIGHTS_DEFAULTS: dict[str, float] = {"momentum": 0.45, "inflow": 0.30, "volume": 0.25}


def get_buyscore_s_weights() -> dict[str, float]:
    """buy_score S(수급) demand 블렌드 가중 (momentum/inflow/volume). 부재 키는 default."""
    cfg = load_score_inputs_config()
    raw = (cfg.get("buyscore") or {}).get("s_weights") or {}
    out = dict(_S_WEIGHTS_DEFAULTS)
    for k in _S_WEIGHTS_DEFAULTS:
        v = raw.get(k)
        if v is not None:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                pass
    return out


def get_theme_sector_mapping() -> dict[str, list[str]]:
    """테마 key → 섹터 ETF 이름 리스트 (S-Score supply_chain 실측). flow.theme_sector_mapping. 부재 시 빈 dict."""
    cfg = load_score_inputs_config()
    raw = (cfg.get("flow") or {}).get("theme_sector_mapping") or {}
    out: dict[str, list[str]] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, list):
                out[str(k)] = [str(x) for x in v]
    return out


def get_manual_theme() -> dict[str, str]:
    """수동 override (ticker → theme key). flow.manual_theme. 부재 시 빈 dict."""
    cfg = load_score_inputs_config()
    raw = (cfg.get("flow") or {}).get("manual_theme") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def get_advisory_constant(key: str, default: float) -> float:
    """advisory 상수 (예: theme_match_neutral). 부재 시 default."""
    cfg = load_score_inputs_config()
    val = (cfg.get("advisory") or {}).get(key)
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default
