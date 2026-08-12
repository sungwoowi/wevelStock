"""시장 판세 cron 잡 (ADVISOR-CORE-001 M1-e).

하루 2회 — 18:00 장마감 / 07:05 아침. 시장 1건이라 종목 수와 무관하게 2콜.

  18:00 postclose : macro·섹터RS·수급 갱신 직후이자 18:05 자동 권고 **앞**.
                    판세가 종목 추천의 입력이 되도록 순서를 지킨다.
  07:05 premarket : 미장·야간선물·뉴스(06:40 ingest) 수집 후. 사람이 그날 판단에 쓴다.

실패는 잡 안에서 잡아 다른 잡을 막지 않는다. LLM 이 죽으면 **알림을 보내지 않는다** —
빈 판세를 보내느니 침묵이 낫다 (run_market_stance 가 담당).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")


async def run_market_stance_job(session: str = "postclose") -> dict[str, Any]:
    """판세 1회 발행 (cron entrypoint). 격리·graceful."""
    as_of = datetime.now(_KST).strftime("%Y-%m-%d")
    log.info("market_stance_job_start", session=session, as_of=as_of)
    try:
        from core.config import get_config
        from core.signal.market_stance import run_market_stance

        # provider 는 config(llm.provider) 를 따른다 — 웹UI/.env 토글과 정합.
        provider = get_config().llm.provider
        stance = await run_market_stance(as_of, session, provider=provider)
    except Exception as e:  # noqa: BLE001 — 판세 실패가 다른 잡을 막지 않음
        log.exception("market_stance_job_failed", session=session, error=str(e))
        return {"session": session, "as_of": as_of, "error": str(e)}

    if stance is None:
        log.warning("market_stance_job_no_output", session=session, as_of=as_of)
        return {"session": session, "as_of": as_of, "published": False}

    log.info(
        "market_stance_job_done",
        session=session, as_of=as_of, stance=stance.stance,
        scenarios=len(stance.scenarios),
    )
    return {
        "session": session, "as_of": as_of, "published": True,
        "stance": stance.stance, "headline": stance.headline,
    }
