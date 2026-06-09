"""가이던스 적중도 KPI 집계 view — GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) G2.

account_fills(청산된 가상매매)+team_outputs(권고 stop/RR)를 **read·계산**(복사 0,
진실 원천 하나 — CLAUDE.md 절대원칙 1). 청산된 권고만 채점("책임지는 데스크"=실제 한 매매).

핵심 KPI: 실현수익률 / 벤치마크 초과(알파) / 방향 적중률 / R/R 실현율 / 트랙 분리.
guidance-kpi-v1. 비목표(SLOT): 비체결(wait/hold) 채점·자가진단 정확도·MDD(가격시계열 필요).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Callable

from core.db import get_db
from core.guidance.benchmark import FetchCloses, compute_benchmark_return
from core.logging import get_logger

log = get_logger(__name__)


def _market_of(ticker: str) -> str:
    return "KR" if ticker.isdigit() and len(ticker) == 6 else "US"


def _load_rec_meta(rec_id: str) -> dict[str, Any]:
    """team_outputs 의 권고 data_json (stop_loss·risk_reward 용). 부재 시 빈 dict."""
    row = get_db().fetch_one(
        "SELECT data_json FROM team_outputs "
        "WHERE run_id = ? AND team_id IN ('track_a','track_b') LIMIT 1",
        (rec_id,),
    )
    if row is None:
        return {}
    try:
        return json.loads(row["data_json"])
    except (json.JSONDecodeError, TypeError):
        return {}


def _days_between(start: str, end: str) -> int:
    try:
        return max(0, (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days)
    except ValueError:
        return 0


def _closed_records(period_days: int, as_of: str | None) -> list[dict[str, Any]]:
    """account_fills 를 (권고×계좌)로 묶어 **청산된**(매수 수량≈매도 수량) 권고만 추출.

    period_days: 청산일이 (as_of − period_days) 이후인 것만.
    """
    rows = get_db().fetch_all("SELECT * FROM account_fills")
    groups: dict[tuple[str, str], list[Any]] = {}
    for r in rows:
        groups.setdefault((r["recommendation_id"], r["account_id"]), []).append(r)

    cutoff = None
    if as_of:
        try:
            cutoff = (date.fromisoformat(as_of[:10]) - timedelta(days=period_days)).isoformat()
        except ValueError:
            cutoff = None

    out: list[dict[str, Any]] = []
    for (rec_id, account_id), fills in groups.items():
        buys = [f for f in fills if f["side"] == "buy"]
        sells = [f for f in fills if f["side"] == "sell"]
        if not buys or not sells:
            continue
        buy_sh = sum(f["shares"] for f in buys)
        sell_sh = sum(f["shares"] for f in sells)
        if buy_sh <= 0 or abs(buy_sh - sell_sh) > 1e-6 * max(1.0, buy_sh):
            continue  # 미청산(부분 보유) → 채점 제외
        exit_date = max(f["filled_date"] for f in sells)
        if cutoff and exit_date < cutoff:
            continue
        out.append({
            "recommendation_id": rec_id,
            "account_id": account_id,
            "ticker": buys[0]["ticker"],
            "track": buys[0]["track"] or "",
            "invested": sum(f["value_krw"] for f in buys),
            "buy_shares": buy_sh,
            "sell_value": sum(f["value_krw"] for f in sells),
            "sell_shares": sell_sh,
            "realized_pnl": sum(f["realized_pnl_krw"] for f in sells),
            "entry_date": min(f["filled_date"] for f in buys),
            "exit_date": exit_date,
        })
    return out


def _compute_record_kpi(
    r: dict[str, Any], *, benchmark_fetch: FetchCloses | None, config: dict[str, Any] | None
) -> dict[str, Any]:
    invested = r["invested"]
    avg_buy = invested / r["buy_shares"] if r["buy_shares"] else 0.0
    avg_exit = r["sell_value"] / r["sell_shares"] if r["sell_shares"] else 0.0
    realized_return_pct = (r["realized_pnl"] / invested * 100.0) if invested else 0.0

    market = _market_of(r["ticker"])
    bench = compute_benchmark_return(
        market, r["entry_date"], r["exit_date"], config=config, fetch=benchmark_fetch
    )
    alpha = (realized_return_pct - bench) if bench is not None else None

    meta = _load_rec_meta(r["recommendation_id"])
    stop = meta.get("stop_loss")
    rr_target = meta.get("risk_reward")
    rr_realization = None
    if stop is not None and rr_target and avg_buy > float(stop):
        realized_rr = (avg_exit - avg_buy) / (avg_buy - float(stop))
        rr_realization = realized_rr / float(rr_target) * 100.0

    return {
        "recommendation_id": r["recommendation_id"],
        "ticker": r["ticker"],
        "track": r["track"],
        "entry_date": r["entry_date"],
        "exit_date": r["exit_date"],
        "holding_days": _days_between(r["entry_date"], r["exit_date"]),
        "invested_krw": invested,
        "realized_pnl_krw": r["realized_pnl"],
        "realized_return_pct": round(realized_return_pct, 2),
        "benchmark_return_pct": round(bench, 2) if bench is not None else None,
        "alpha_pct": round(alpha, 2) if alpha is not None else None,
        "direction_hit": r["realized_pnl"] > 0,
        "rr_realization_pct": round(rr_realization, 1) if rr_realization is not None else None,
    }


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    benches = [r["benchmark_return_pct"] for r in records if r["benchmark_return_pct"] is not None]
    alphas = [r["alpha_pct"] for r in records if r["alpha_pct"] is not None]
    rrs = [r["rr_realization_pct"] for r in records if r["rr_realization_pct"] is not None]
    return {
        "closed_count": n,
        "realized_return_avg_pct": _avg([r["realized_return_pct"] for r in records]),
        "benchmark_return_avg_pct": _avg(benches),
        "alpha_avg_pct": _avg(alphas),
        "win_rate_pct": round(sum(1 for r in records if r["direction_hit"]) / n * 100.0, 1) if n else None,
        "rr_realization_avg_pct": _avg(rrs),
        "avg_holding_days": _avg([float(r["holding_days"]) for r in records]),
        "realized_pnl_sum_krw": round(sum(r["realized_pnl_krw"] for r in records), 0) if n else 0.0,
    }


def get_kpi_summary(
    track: str | None = None,
    period_days: int = 90,
    *,
    as_of: str | None = None,
    benchmark_fetch: FetchCloses | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """청산된 권고 → KPI 집계 (guidance-kpi-v1). track=None → 전체 + by_track 분리.

    as_of 기본 = 오늘(KST). benchmark_fetch 주입 가능(테스트·백테스트).
    """
    as_of = as_of or date.today().isoformat()
    closed = _closed_records(period_days, as_of)
    computed = [_compute_record_kpi(r, benchmark_fetch=benchmark_fetch, config=config) for r in closed]

    selected = [c for c in computed if track is None or c["track"] == track]
    summary: dict[str, Any] = {
        "track": track or "all",
        "period_days": period_days,
        "as_of": as_of,
        **_aggregate(selected),
        "records": sorted(selected, key=lambda c: c["exit_date"], reverse=True),
    }
    if track is None:
        summary["by_track"] = {
            t: _aggregate([c for c in computed if c["track"] == t]) for t in ("A", "B")
        }
    return summary
