"""브리핑 공용 플랫폼 (BRIEFING-ON-DEMAND-001).

- `render` : 파이프라인별 JSON → 텔레그램/웹앱 공용 텍스트
- `parts_store` : briefing_parts 테이블 upsert/조회
"""
from core.briefing.parts_store import (
    get_last_run_before,
    get_latest_parts,
    get_latest_parts_with_age,
    get_part,
    get_parts_by_run,
    upsert_parts,
)
from core.briefing.render import (
    render_market_briefing,
    render_morning_pre,
    render_overnight,
    render_positions,
    render_scenario,
)

__all__ = [
    "render_morning_pre",
    "render_market_briefing",
    "render_overnight",
    "render_scenario",
    "render_positions",
    "upsert_parts",
    "get_latest_parts",
    "get_latest_parts_with_age",
    "get_last_run_before",
    "get_parts_by_run",
    "get_part",
]
