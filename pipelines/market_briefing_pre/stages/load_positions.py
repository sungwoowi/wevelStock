"""Stage: load_positions — DB에서 watch_positions + sim_positions 로드.

Loads both:
  - watch_positions (status in {watching, holding}): 수동 등록 관심/보유 종목
  - sim_positions (status in {holding, partial_exit}): AI 시뮬 현재 포지션

Output shape passed downstream:
{
    "watch": [{ticker, name, market, status, watch_price, ...}, ...],
    "sim":   [{ticker, name, avg_price, total_quantity, buy_count, ...}, ...],
    "counts": {"watch": N, "sim": M}
}
"""
from __future__ import annotations

from core.db import get_db
from core.logging import get_logger
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


def _rows_to_dicts(rows: list) -> list[dict]:
    return [dict(r) for r in rows]


def _load_paper_holdings() -> list[dict]:
    """가상매매 정본(account_positions) 보유 로드 (2026-07-07 배선 구멍 수리).

    RB-MS2 이후 실제 보유는 account_positions 인데 본 스테이지가 레거시
    watch/sim_positions 만 읽어 브리핑이 항상 "보유 없음"이던 결함 — 실측으로
    삼성전자우·SK하이닉스·테스 보유 중에 발견. core/account/holdings.get_holdings
    재사용 (평가손익·보유일수 포함, 가드 #11). 실패는 빈 리스트 (graceful).
    """
    try:
        from core.account.holdings import get_holdings

        db = get_db()
        account_ids = [
            r["account_id"]
            for r in db.fetch_all("SELECT DISTINCT account_id FROM account_positions")
        ]
        out: list[dict] = []
        for aid in account_ids:
            for h in get_holdings(aid):
                out.append({
                    "account_id": h.get("account_id"),
                    "ticker": h.get("ticker"),
                    "name": h.get("display_name") or h.get("ticker"),
                    "track": h.get("track"),
                    "avg_price": h.get("avg_price"),
                    "eval_price": h.get("eval_price"),
                    "unrealized_pct": round(float(h.get("unrealized_pct") or 0.0), 2),
                    "weight": h.get("weight"),
                    "tranche_count": h.get("tranche_count"),
                    "opened_at": h.get("opened_at"),
                    "holding_days": h.get("holding_days"),
                })
        return out
    except Exception as e:  # noqa: BLE001 — 보유 로드 실패가 브리핑을 막지 않음
        log.warning("paper_holdings_load_failed", error=str(e))
        return []


class LoadPositionsStage(Stage):
    stage_id = "load_positions"
    stage_type = "collect"

    async def run(self, ctx: StageContext) -> StageResult:
        db = get_db()

        try:
            watch_rows = db.fetch_all(
                """
                SELECT id, ticker, name, market, status, watch_price,
                       buy_signal_cnt, sell_signal_cnt, hold_signal_cnt,
                       last_signal_at, last_signal_type, notes
                FROM watch_positions
                WHERE status IN ('watching', 'holding')
                ORDER BY updated_at DESC, created_at DESC
                """
            )
        except Exception as e:  # noqa: BLE001
            log.warning("watch_positions_load_failed", error=str(e))
            watch_rows = []

        try:
            sim_rows = db.fetch_all(
                """
                SELECT ticker, name, avg_price, total_quantity,
                       buy_count, sell_count, realized_pnl, unrealized_pnl,
                       status, first_entry_at, last_trade_at
                FROM sim_positions
                WHERE status IN ('holding', 'partial_exit')
                ORDER BY last_trade_at DESC
                """
            )
        except Exception as e:  # noqa: BLE001
            log.warning("sim_positions_load_failed", error=str(e))
            sim_rows = []

        watch = _rows_to_dicts(watch_rows)
        sim = _rows_to_dicts(sim_rows)
        paper = _load_paper_holdings()

        log.info(
            "positions_loaded",
            pipeline=ctx.pipeline_id,
            watch_count=len(watch),
            sim_count=len(sim),
            paper_count=len(paper),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "watch": watch,
                "sim": sim,
                # 가상매매 계좌 보유 (정본 account_positions — 평가손익·보유일수 포함)
                "paper": paper,
                "counts": {"watch": len(watch), "sim": len(sim), "paper": len(paper)},
            },
        )
