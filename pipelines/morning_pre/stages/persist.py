"""Stage: persist — analyze 결과를 DB에 분해 저장.

Writes:
  - predictions      : scenario + per-ticker verdicts + new_candidates + sector
  - news_items       : news + impact tagging
  - sim_trades       : AI가 BUY_ADD / SELL_PART / SELL_ALL 발령한 종목 (가상 체결)
  - sim_positions    : sim_trades 누적 집계 (avg_price, total_quantity) 갱신
  - watch_positions  : signal counter 증가 (last_signal_at/type)

Pure code (no LLM). Uses a single DB connection per write group.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from core.briefing import upsert_parts
from core.contracts.briefing_part import BriefingPart
from core.db import get_db
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)

# Default quantity for simulated trades when LLM doesn't specify one.
DEFAULT_SIM_QTY = 10

# briefing_parts 메타 선언 (manifest.yaml 의 parts 와 일치해야 함).
# 파이프라인 전용 상수 — 다른 파이프라인은 고유 PARTS_META 를 가짐.
_PARTS_META: list[tuple[str, str, int]] = [
    ("overnight", "간밤시황", 1),
    ("scenario", "시나리오+뉴스", 2),
    ("positions", "포지션+신규", 3),
]


def _build_overnight_data(ctx: StageContext) -> dict:
    overnight = ctx.get_stage_data("collect_overnight_us") or {}
    futures = ctx.get_stage_data("collect_night_futures") or {}
    return {
        "overnight_us": overnight.get("overnight_us") or {},
        "macro": overnight.get("macro") or {},
        "night_futures": futures.get("night_futures") or {},
    }


def _build_scenario_data(ctx: StageContext, briefing: dict) -> dict:
    news = ctx.get_stage_data("collect_news") or {}
    return {
        "scenario": briefing.get("scenario") or {},
        "news_impact": briefing.get("news_impact") or [],
        "news_items": news.get("items") or [],
    }


def _build_positions_data(ctx: StageContext, briefing: dict) -> dict:
    principles = ctx.get_stage_data("check_principles") or {}
    return {
        "positions_advice": briefing.get("positions_advice") or [],
        "new_candidates": briefing.get("new_candidates") or [],
        "principles": principles,
    }


def _persist_briefing_parts(ctx: StageContext, briefing: dict) -> int:
    """analyze 결과를 briefing_parts 테이블에 upsert. 저장된 파트 수 반환."""
    parts = [
        BriefingPart(
            key="overnight",
            label=_PARTS_META[0][1],
            order=_PARTS_META[0][2],
            data=_build_overnight_data(ctx),
        ),
        BriefingPart(
            key="scenario",
            label=_PARTS_META[1][1],
            order=_PARTS_META[1][2],
            data=_build_scenario_data(ctx, briefing),
        ),
        BriefingPart(
            key="positions",
            label=_PARTS_META[2][1],
            order=_PARTS_META[2][2],
            data=_build_positions_data(ctx, briefing),
        ),
    ]
    upsert_parts(ctx.pipeline_id, ctx.run_id, parts)
    return len(parts)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _safe_int(v, default: int | None = None) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_float(v, default: float | None = None) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class PersistStage(Stage):
    stage_id = "persist"
    stage_type = "act"

    async def run(self, ctx: StageContext) -> StageResult:
        analyze_data = ctx.get_stage_data("analyze") or {}
        briefing = analyze_data.get("briefing") or {}

        news_input = (ctx.get_stage_data("collect_news") or {}).get("items", [])
        news_impact = briefing.get("news_impact") or []
        positions_advice = briefing.get("positions_advice") or []
        new_candidates = briefing.get("new_candidates") or []
        scenario = briefing.get("scenario") or {}
        sector_watch = briefing.get("sector_watch") or {}

        db = get_db()
        counts = {
            "predictions": 0,
            "news_items": 0,
            "sim_trades": 0,
            "watch_updates": 0,
            "briefing_parts": 0,
        }

        try:
            with db.connect() as conn:
                # -- news_items (join input news with LLM impact by url) --
                impact_by_url = {e.get("url"): e for e in news_impact if e.get("url")}
                for item in news_input:
                    url = item.get("url")
                    if not url:
                        continue
                    imp = impact_by_url.get(url, {})
                    try:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO news_items
                                (run_id, pipeline_id, published_at, source,
                                 title, url, impact_direction, impact_magnitude,
                                 impact_note)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ctx.run_id,
                                ctx.pipeline_id,
                                item.get("published_at"),
                                item.get("source"),
                                item.get("title"),
                                url,
                                imp.get("impact_direction"),
                                _safe_int(imp.get("impact_magnitude")),
                                imp.get("impact_note"),
                            ),
                        )
                        counts["news_items"] += 1
                    except Exception as e:  # noqa: BLE001
                        log.warning("news_item_insert_failed", url=url, error=str(e))

                # -- predictions: scenario --
                if scenario:
                    conn.execute(
                        """
                        INSERT INTO predictions
                            (pipeline_id, run_id, date_predicted, target_date,
                             ticker, prediction_type, prediction, confidence,
                             reason, metadata_json)
                        VALUES (?, ?, ?, ?, NULL, 'scenario', ?, ?, ?, ?)
                        """,
                        (
                            ctx.pipeline_id,
                            ctx.run_id,
                            _today(),
                            _today(),
                            scenario.get("expected_open") or "unknown",
                            _safe_int(scenario.get("confidence"), 50),
                            scenario.get("narrative", "")[:500],
                            json.dumps(
                                {"bias": scenario.get("bias")},
                                ensure_ascii=False,
                            ),
                        ),
                    )
                    counts["predictions"] += 1

                # -- predictions: sector_watch --
                for direction in ("bullish", "bearish"):
                    for sector in sector_watch.get(direction, []) or []:
                        conn.execute(
                            """
                            INSERT INTO predictions
                                (pipeline_id, run_id, date_predicted, target_date,
                                 ticker, prediction_type, prediction, confidence,
                                 reason)
                            VALUES (?, ?, ?, ?, NULL, 'sector', ?, NULL, ?)
                            """,
                            (
                                ctx.pipeline_id,
                                ctx.run_id,
                                _today(),
                                _today(),
                                f"{direction}:{sector}",
                                f"sector_watch {direction}",
                            ),
                        )
                        counts["predictions"] += 1

                # -- predictions + sim_trades for each positions_advice --
                for advice in positions_advice:
                    ticker = advice.get("ticker")
                    name = advice.get("name")
                    verdict_raw = str(advice.get("verdict") or "").upper()
                    reason = advice.get("reason") or ""

                    related_trade_id: int | None = None
                    if verdict_raw in ("BUY_ADD", "SELL_PART", "SELL_ALL") and ticker:
                        side = "buy" if verdict_raw == "BUY_ADD" else "sell"
                        # Use a placeholder price (0.0) — real price feed is out of scope.
                        try:
                            # Count existing trades for this ticker to set trade_no
                            row = conn.execute(
                                "SELECT COUNT(*) AS c FROM sim_trades WHERE ticker = ?",
                                (ticker,),
                            ).fetchone()
                            trade_no = (row["c"] if row else 0) + 1

                            cur = conn.execute(
                                """
                                INSERT INTO sim_trades
                                    (ticker, name, side, price, quantity,
                                     trade_no, run_id, pipeline_id, reason)
                                VALUES (?, ?, ?, 0.0, ?, ?, ?, ?, ?)
                                """,
                                (
                                    ticker, name, side, DEFAULT_SIM_QTY,
                                    trade_no, ctx.run_id, ctx.pipeline_id, reason,
                                ),
                            )
                            related_trade_id = cur.lastrowid
                            counts["sim_trades"] += 1

                            # Update sim_positions crude aggregate (avg_price=0 acceptable placeholder)
                            if side == "buy":
                                conn.execute(
                                    """
                                    INSERT INTO sim_positions
                                        (ticker, name, avg_price, total_quantity,
                                         buy_count, sell_count, status,
                                         first_entry_at, last_trade_at, updated_at)
                                    VALUES (?, ?, 0.0, ?, 1, 0, 'holding', ?, ?, ?)
                                    ON CONFLICT(ticker) DO UPDATE SET
                                        total_quantity = total_quantity + excluded.total_quantity,
                                        buy_count = buy_count + 1,
                                        last_trade_at = excluded.last_trade_at,
                                        updated_at = excluded.updated_at,
                                        status = 'holding'
                                    """,
                                    (
                                        ticker, name, DEFAULT_SIM_QTY,
                                        _now_iso(), _now_iso(), _now_iso(),
                                    ),
                                )
                            else:  # sell
                                conn.execute(
                                    """
                                    UPDATE sim_positions
                                    SET total_quantity = MAX(0, total_quantity - ?),
                                        sell_count = sell_count + 1,
                                        last_trade_at = ?,
                                        updated_at = ?,
                                        status = CASE
                                            WHEN total_quantity - ? <= 0 THEN 'closed'
                                            WHEN ? = 'SELL_PART' THEN 'partial_exit'
                                            ELSE 'closed'
                                        END
                                    WHERE ticker = ?
                                    """,
                                    (
                                        DEFAULT_SIM_QTY, _now_iso(), _now_iso(),
                                        DEFAULT_SIM_QTY, verdict_raw, ticker,
                                    ),
                                )
                        except Exception as e:  # noqa: BLE001
                            log.warning("sim_trade_insert_failed", ticker=ticker, error=str(e))

                    # predictions entry for this action
                    if ticker:
                        conn.execute(
                            """
                            INSERT INTO predictions
                                (pipeline_id, run_id, date_predicted, target_date,
                                 ticker, prediction_type, prediction, confidence,
                                 reason, related_trade_id)
                            VALUES (?, ?, ?, ?, ?, 'action', ?, NULL, ?, ?)
                            """,
                            (
                                ctx.pipeline_id, ctx.run_id,
                                _today(), _today(),
                                ticker, verdict_raw or "HOLD",
                                reason, related_trade_id,
                            ),
                        )
                        counts["predictions"] += 1

                    # watch_positions signal counter update
                    if ticker:
                        col = {
                            "BUY_ADD": "buy_signal_cnt",
                            "SELL_PART": "sell_signal_cnt",
                            "SELL_ALL": "sell_signal_cnt",
                            "HOLD": "hold_signal_cnt",
                        }.get(verdict_raw)
                        if col:
                            cur = conn.execute(
                                f"""
                                UPDATE watch_positions
                                SET {col} = {col} + 1,
                                    last_signal_at = ?,
                                    last_signal_type = ?,
                                    updated_at = ?
                                WHERE ticker = ?
                                  AND status IN ('watching', 'holding')
                                """,
                                (_now_iso(), verdict_raw, _now_iso(), ticker),
                            )
                            if cur.rowcount:
                                counts["watch_updates"] += cur.rowcount

                # -- predictions: new_candidates --
                for cand in new_candidates:
                    ticker = cand.get("ticker")
                    if not ticker:
                        continue
                    conn.execute(
                        """
                        INSERT INTO predictions
                            (pipeline_id, run_id, date_predicted, target_date,
                             ticker, prediction_type, prediction, confidence,
                             reason, metadata_json)
                        VALUES (?, ?, ?, ?, ?, 'action', 'NEW_CANDIDATE', NULL, ?, ?)
                        """,
                        (
                            ctx.pipeline_id, ctx.run_id,
                            _today(), _today(),
                            ticker,
                            cand.get("reason") or "",
                            json.dumps(
                                {"sector": cand.get("sector"), "name": cand.get("name")},
                                ensure_ascii=False,
                            ),
                        ),
                    )
                    counts["predictions"] += 1
        except Exception as e:  # noqa: BLE001
            log.error("persist_failed", error=str(e))
            return StageResult(
                stage_id=self.stage_id,
                status="error",
                error=str(e),
                data={"counts": counts},
            )

        # briefing_parts upsert — 기존 DB 쓰기와 독립 트랜잭션.
        # 실패해도 persist 는 warning 으로 격하하고 나머지 데이터는 유지.
        status = "ok"
        briefing_parts_error: str | None = None
        try:
            counts["briefing_parts"] = _persist_briefing_parts(ctx, briefing)
        except Exception as e:  # noqa: BLE001
            log.warning("briefing_parts_upsert_failed", error=str(e))
            status = "warning"
            briefing_parts_error = str(e)

        log.info("persist_complete", pipeline=ctx.pipeline_id, **counts)
        return StageResult(
            stage_id=self.stage_id,
            status=status,
            data={"counts": counts, "briefing_parts_error": briefing_parts_error},
        )
