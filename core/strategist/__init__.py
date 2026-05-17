"""core.strategist — Layer 3 전략가 호출 인프라.

STRATEGY-TRACK-001 SPEC 의 Track A·B (+ plugin) 전략가 호출 wrapper.
분석가 측 `core/inference/run_analyst.py` 와 1:1 대응. 차이점:
  - `reads_analysts` 의 team_outputs DB row 를 system prompt 의 ## Analyst Scores 블록에 주입
  - `canon_categories` 가 9 dept framework 멀티 dept (분석가는 단일 dept)
  - manifest 의 `input_routing` 룰은 Track Selector (별도 모듈, 후속) 가 read
"""
from core.strategist.run_strategist import (
    StrategistNotFoundError,
    StrategistResponse,
    StrategistSpec,
    gather_analyst_scores,
    load_strategist_spec,
    render_analyst_scores_block,
    run_strategist,
    run_strategist_stream,
)

__all__ = [
    "StrategistNotFoundError",
    "StrategistResponse",
    "StrategistSpec",
    "gather_analyst_scores",
    "load_strategist_spec",
    "render_analyst_scores_block",
    "run_strategist",
    "run_strategist_stream",
]
