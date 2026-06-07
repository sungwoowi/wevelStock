"""Stage: collect_overnight_us — 간밤 미국장 + 거시 지표 수집.

Uses collectors.us_markets.fetch_overnight() which returns a flat dict of:
  nasdaq / sp500 / sox / vix / dxy / us_10y / gold / wti
"""
from __future__ import annotations

from collectors.fear_greed import fetch_fear_greed
from collectors.us_markets import fetch_overnight
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


class CollectOvernightUsStage(Stage):
    stage_id = "collect_overnight_us"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        raw = await fetch_overnight()
        raw["fear_greed"] = await fetch_fear_greed()

        # Separate index-like from macro-like for downstream convenience.
        indices_keys = {"nasdaq", "sp500", "sox", "vix", "fear_greed"}
        overnight_us = {k: raw[k] for k in indices_keys if k in raw}
        macro = {k: raw[k] for k in ("dxy", "usdkrw", "us_10y", "gold", "wti") if k in raw}

        errors = [k for k, v in raw.items() if isinstance(v, dict) and "error" in v]
        status = "warning" if errors else "ok"

        # 장전 us_macro_snapshot 영속 (INFRA-US-MACRO-SNAPSHOT-001 U3 — 18:05 허브와 둘 다).
        #   compute_us_macro 는 DB-first 멱등 — 같은 KST 날짜면 18:05 적재와 동일값 갱신.
        #   double-fetch(이 stage fetch_overnight + compute_us_macro) dedupe 는 SLOT (SPEC 명시).
        #   graceful — 영속 실패가 브리핑을 막지 않음.
        try:
            from collectors.us_macro import compute_us_macro

            us_snap = await compute_us_macro(force_refresh=True)
            log.info("overnight_us_macro_persisted", risk_signal=us_snap.risk_signal, source=us_snap.source)
        except Exception as e:  # noqa: BLE001
            log.warning("overnight_us_macro_persist_failed", error=str(e))

        log.info(
            "overnight_us_collected",
            pipeline=ctx.pipeline_id,
            errors=errors,
            nasdaq_pct=overnight_us.get("nasdaq", {}).get("change_pct"),
            sox_pct=overnight_us.get("sox", {}).get("change_pct"),
        )

        return StageResult(
            stage_id=self.stage_id,
            status=status,
            data={
                "overnight_us": overnight_us,
                "macro": macro,
                "errors": errors,
            },
        )
