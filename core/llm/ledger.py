"""LLM 비용 원장 (LLM-COST-LEDGER-001).

`llm_call_cache` 는 멱등 캐시(unique input_hash 1행)라 실제 지출을 못 담는다.
본 원장은 `call_llm` 이 통과하는 모든 호출을 1행씩 기록해 벤더(provider)·모델(model)·
질의영역(call_type)별 일단위 지출을 추적한다. 벤더/모델을 갈아끼워도 같은 축으로 추적.

기록 지점: core/llm/client.py::call_llm (중앙 chokepoint) — served 응답 + cache hit.
소비 지점: server/api/ops.py → webapp /ops/llm-cost (운영자 화면).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_KST = timezone(timedelta(hours=9))


def record_llm_cost(
    *,
    provider: str,
    model: str,
    call_type: str = "general",
    target: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    cache_hit: bool = False,
    success: bool = True,
) -> None:
    """LLM 호출 1건을 원장에 append. 실패해도 본 흐름을 깨지 않는다(best-effort)."""
    try:
        now = datetime.now(_KST)
        get_db().execute(
            "INSERT INTO llm_cost_ledger "
            "(ts, day, provider, model, call_type, target, tokens_in, tokens_out, "
            " cost_usd, cache_hit, success) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                now.isoformat(),
                now.strftime("%Y-%m-%d"),
                provider or "unknown",
                model or "unknown",
                call_type or "general",
                target,
                int(tokens_in or 0),
                int(tokens_out or 0),
                float(cost_usd or 0.0),
                1 if cache_hit else 0,
                1 if success else 0,
            ),
        )
    except Exception as e:  # noqa: BLE001 — 원장 기록 실패가 LLM 응답을 막으면 안 됨
        log.warning("llm_cost_ledger_write_failed", error=str(e))


def _since_day(days: int) -> str:
    """오늘(KST) 포함 최근 N일의 시작일 'YYYY-MM-DD'."""
    start = datetime.now(_KST) - timedelta(days=max(1, days) - 1)
    return start.strftime("%Y-%m-%d")


def cost_summary(days: int = 7) -> dict[str, Any]:
    """운영자 화면용 집계 — 최근 N일.

    Returns dict:
      range: {days, since}
      totals: {cost_usd, calls, cache_hits, tokens_in, tokens_out}
      by_provider / by_model / by_call_type: list[{key.., cost_usd, calls, tokens_in, tokens_out}]
      by_day: list[{day, cost_usd, calls}]  (최신→과거)
      by_day_provider: list[{day, provider, cost_usd, calls}]  (누적 막대용)
    """
    db = get_db()
    since = _since_day(days)
    # 실 지출만(캐시 히트 제외) 비용 합산 — cache_hit=1 은 cost 0 이지만 별도 카운트.
    where = "WHERE day >= ?"
    args = (since,)

    def rows(sql: str) -> list[dict[str, Any]]:
        return [dict(r) for r in db.fetch_all(sql, args)]

    totals_row = db.fetch_one(
        f"SELECT ROUND(SUM(cost_usd),6) cost_usd, COUNT(*) calls, "
        f"SUM(cache_hit) cache_hits, SUM(tokens_in) tokens_in, SUM(tokens_out) tokens_out "
        f"FROM llm_cost_ledger {where}",
        args,
    )
    totals = dict(totals_row) if totals_row else {}

    by_provider = rows(
        f"SELECT provider, ROUND(SUM(cost_usd),6) cost_usd, COUNT(*) calls, "
        f"SUM(cache_hit) cache_hits, SUM(tokens_in) tokens_in, SUM(tokens_out) tokens_out "
        f"FROM llm_cost_ledger {where} GROUP BY provider ORDER BY cost_usd DESC"
    )
    by_model = rows(
        f"SELECT provider, model, ROUND(SUM(cost_usd),6) cost_usd, COUNT(*) calls, "
        f"SUM(tokens_in) tokens_in, SUM(tokens_out) tokens_out "
        f"FROM llm_cost_ledger {where} GROUP BY provider, model ORDER BY cost_usd DESC"
    )
    by_call_type = rows(
        f"SELECT call_type, ROUND(SUM(cost_usd),6) cost_usd, COUNT(*) calls, "
        f"SUM(cache_hit) cache_hits, SUM(tokens_in) tokens_in, SUM(tokens_out) tokens_out "
        f"FROM llm_cost_ledger {where} GROUP BY call_type ORDER BY cost_usd DESC"
    )
    by_day = rows(
        f"SELECT day, ROUND(SUM(cost_usd),6) cost_usd, COUNT(*) calls "
        f"FROM llm_cost_ledger {where} GROUP BY day ORDER BY day DESC"
    )
    by_day_provider = rows(
        f"SELECT day, provider, ROUND(SUM(cost_usd),6) cost_usd, COUNT(*) calls "
        f"FROM llm_cost_ledger {where} GROUP BY day, provider ORDER BY day DESC, cost_usd DESC"
    )

    return {
        "range": {"days": days, "since": since},
        "totals": {
            "cost_usd": totals.get("cost_usd") or 0.0,
            "calls": totals.get("calls") or 0,
            "cache_hits": totals.get("cache_hits") or 0,
            "tokens_in": totals.get("tokens_in") or 0,
            "tokens_out": totals.get("tokens_out") or 0,
        },
        "by_provider": by_provider,
        "by_model": by_model,
        "by_call_type": by_call_type,
        "by_day": by_day,
        "by_day_provider": by_day_provider,
    }
