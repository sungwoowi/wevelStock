"""자산 곡선 추적 — WEALTH-COMPOUND-TRACKER-001 (RB-MS4, 오른쪽 뇌 마지막).

매일 자산 스냅샷(going-forward 마크투마켓) → 4계좌 통합 자산 곡선 + 성장 목표(연 18%) 진척.
`equity = seed + 누적 실현손익(account_fills) + 미실현(holdings 오늘 종가)`. account_fills/
holdings 재사용(복사 0). 데스크가 매일 도는 끝에 `snapshot_equity` 한 줄 저장(멱등).

워딩 주의: "복리" 는 지식부 자산복리부(박종훈 거시 frame) 용어 — 본 모듈은 성과 측정이라
사용자 노출 워딩은 "자산 곡선/자산 성장" (2026-06-10 정체성 분리. 함수명·테이블명은 불변).
판단·전략(언제 비중 늘릴지)은 왼쪽 뇌 wealth_strategist — 본 모듈은 *추적·곡선·목표 대비*.
SLOT(비쌈): 과거 매일 평가 소급(가격 시계열) / 일·주·월 고정 롤업.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from core.account import holdings as holdings_mod
from core.account.portfolio import load_accounts
from core.db import get_db
from core.guidance.benchmark import FetchCloses, compute_benchmark_return
from core.logging import get_logger

log = get_logger(__name__)

DEFAULT_ANNUAL_TARGET = 0.18   # 연 18% (5년 ≈ 2.3배) — GUIDANCE 목표 정렬
MDD_GUARD_PCT = 8.0            # 목표 MDD -8% 이하


def _days_between(start: str, end: str) -> int:
    try:
        return max(0, (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days)
    except ValueError:
        return 0


def _realized_cum(account_id: str, as_of: str) -> float:
    """as_of 까지 누적 실현손익 (account_fills sell)."""
    rows = get_db().fetch_all(
        "SELECT realized_pnl_krw, filled_date FROM account_fills "
        "WHERE account_id = ? AND side = 'sell'",
        (account_id,),
    )
    return sum(r["realized_pnl_krw"] or 0.0 for r in rows if (r["filled_date"] or "") <= as_of)


def snapshot_equity(
    as_of: str | None = None,
    *,
    price_lookup: Callable[[str], float | None] | None = None,
) -> list[dict[str, Any]]:
    """계좌별 총자산 한 줄을 account_equity_snapshot 에 저장 (멱등). equity-snapshot-v1.

    equity = seed + 누적 실현손익 + 미실현(holdings 오늘 종가). 데스크가 매일 호출.
    """
    as_of = as_of or date.today().isoformat()
    db = get_db()
    out: list[dict[str, Any]] = []
    for acct in load_accounts():
        realized = _realized_cum(acct.account_id, as_of)
        holds = holdings_mod.get_holdings(acct.account_id, as_of=as_of, price_lookup=price_lookup)
        unrealized = sum(h["unrealized_pnl_krw"] for h in holds)
        deployed = sum(h["weight"] for h in holds)
        equity = acct.seed_krw + realized + unrealized
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO account_equity_snapshot
                    (date, account_id, seed_krw, realized_cum_krw, unrealized_krw, equity_krw, deployed_weight)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, account_id) DO UPDATE SET
                    seed_krw=excluded.seed_krw, realized_cum_krw=excluded.realized_cum_krw,
                    unrealized_krw=excluded.unrealized_krw, equity_krw=excluded.equity_krw,
                    deployed_weight=excluded.deployed_weight
                """,
                (as_of, acct.account_id, acct.seed_krw, realized, unrealized, equity, deployed),
            )
        out.append({
            "date": as_of, "account_id": acct.account_id, "seed_krw": acct.seed_krw,
            "realized_cum_krw": realized, "unrealized_krw": unrealized,
            "equity_krw": equity, "deployed_weight": deployed,
        })
    return out


def get_equity_curve(account_id: str | None = None, *, as_of: str | None = None) -> dict[str, Any]:
    """자산 곡선 — account_equity_snapshot 시계열. account_id None → 4계좌 통합(날짜별 합산)."""
    db = get_db()
    # 두 시리즈: realized_equity = seed+누적실현(확정·보수) / equity = +미실현(마크투마켓).
    if account_id:
        rows = db.fetch_all(
            "SELECT date, equity_krw, (equity_krw - unrealized_krw) AS realized_eq "
            "FROM account_equity_snapshot WHERE account_id = ? ORDER BY date",
            (account_id,),
        )
        points = [
            {"date": r["date"], "equity_krw": r["equity_krw"], "realized_equity_krw": r["realized_eq"]}
            for r in rows
        ]
        total_seed = next((a.seed_krw for a in load_accounts() if a.account_id == account_id), 0.0)
    else:
        rows = db.fetch_all(
            "SELECT date, SUM(equity_krw) AS eq, SUM(equity_krw - unrealized_krw) AS realized_eq "
            "FROM account_equity_snapshot GROUP BY date ORDER BY date"
        )
        points = [
            {"date": r["date"], "equity_krw": r["eq"], "realized_equity_krw": r["realized_eq"]}
            for r in rows
        ]
        total_seed = sum(a.seed_krw for a in load_accounts())
    if as_of:
        points = [p for p in points if p["date"] <= as_of]
    return {"account_id": account_id or "all", "total_seed_krw": total_seed, "points": points}


def compute_mdd(equities: list[float]) -> float:
    """자산 곡선 최대낙폭(%). 고점 대비 최대 하락. 곡선 없으면 0."""
    peak = float("-inf")
    mdd = 0.0
    for e in equities:
        peak = max(peak, e)
        if peak > 0:
            mdd = max(mdd, (peak - e) / peak)
    return round(mdd * 100.0, 2)


def _won(v: float) -> str:
    if abs(v) >= 100_000_000:
        return f"{v / 100_000_000:.2f}억원"
    if abs(v) >= 10_000:
        return f"{v / 10_000:,.0f}만원"
    return f"{v:,.0f}원"


def render_compound_summary(progress: dict[str, Any], curve: dict[str, Any]) -> str:
    """성장 목표 진척 + 두 곡선(실현 vs 총자산) 최근값 → 사람 친화 텍스트 (`/wealth`)."""
    lines = ["📈 자산 곡선 추적 (가상)"]
    pts = curve.get("points") or []
    if not pts:
        lines.append("\n아직 자산 스냅샷이 없습니다. (데스크가 매일 돌며 총자산을 한 점씩 기록합니다)")
        return "\n".join(lines)

    last = pts[-1]
    lines.append(f"\n【현재 총자산】 {_won(last['equity_krw'])} (시드 {_won(progress['total_seed_krw'])})")
    lines.append(f"- 총 수익률: {progress['total_return_pct']:+.1f}% (마크투마켓 = 실현+평가)")
    lines.append(f"  · 실현만(확정): {_won(last['realized_equity_krw'])} / 평가 포함(총): {_won(last['equity_krw'])}")
    tgt = progress["target_return_pct"]
    prog = progress["progress_pct"]
    if prog is not None:
        verdict = "목표 앞섬" if prog >= 100 else "목표 뒤짐"
        lines.append(f"- 성장 목표(연 18%) 대비: {prog:.0f}% 진척 (목표 수익률 {tgt:+.1f}% — {verdict})")
    mdd = progress["mdd_pct"]
    guard = "⚠️ 가드 초과" if progress.get("mdd_breached") else "가드 내"
    lines.append(f"- 최대낙폭(MDD): -{mdd:.1f}% (목표 -{progress['mdd_guard_pct']:.0f}% 이하 — {guard})")
    if progress.get("alpha_pct") is not None:
        sign = "+" if progress["alpha_pct"] >= 0 else ""
        lines.append(f"- 시장(코스피) 대비: {sign}{progress['alpha_pct']:.1f}%p")
    lines.append(f"- 추적 {progress['elapsed_days']}일 / 스냅샷 {progress['points']}점")
    return "\n".join(lines)


def get_compound_progress(
    *,
    as_of: str | None = None,
    annual_target: float = DEFAULT_ANNUAL_TARGET,
    benchmark_fetch: FetchCloses | None = None,
) -> dict[str, Any]:
    """성장 목표 진척 — 목표곡선(seed×(1+연target)^경과) vs 실제 + MDD + 벤치마크 알파."""
    curve = get_equity_curve(as_of=as_of)
    points = curve["points"]
    total_seed = curve["total_seed_krw"]
    if not points or not total_seed:
        return {
            "total_equity_krw": total_seed, "total_seed_krw": total_seed,
            "total_return_pct": 0.0, "target_return_pct": 0.0, "progress_pct": None,
            "mdd_pct": 0.0, "mdd_guard_pct": MDD_GUARD_PCT, "benchmark_return_pct": None,
            "alpha_pct": None, "elapsed_days": 0, "points": 0,
        }

    start_date = points[0]["date"]
    end_date = as_of or points[-1]["date"]
    current = points[-1]["equity_krw"]
    elapsed_days = _days_between(start_date, end_date)
    years = elapsed_days / 365.25

    target_equity = total_seed * ((1.0 + annual_target) ** years)
    total_return_pct = (current / total_seed - 1.0) * 100.0
    target_return_pct = (target_equity / total_seed - 1.0) * 100.0
    progress_pct = (total_return_pct / target_return_pct * 100.0) if target_return_pct else None

    mdd = compute_mdd([p["equity_krw"] for p in points])
    bench = compute_benchmark_return("KR", start_date, end_date, fetch=benchmark_fetch)
    alpha = (total_return_pct - bench) if bench is not None else None

    return {
        "total_equity_krw": round(current, 0),
        "total_seed_krw": round(total_seed, 0),
        "total_return_pct": round(total_return_pct, 2),
        "target_return_pct": round(target_return_pct, 2),
        "progress_pct": round(progress_pct, 1) if progress_pct is not None else None,
        "mdd_pct": mdd,
        "mdd_guard_pct": MDD_GUARD_PCT,
        "mdd_breached": mdd > MDD_GUARD_PCT,
        "benchmark_return_pct": round(bench, 2) if bench is not None else None,
        "alpha_pct": round(alpha, 2) if alpha is not None else None,
        "elapsed_days": elapsed_days,
        "points": len(points),
    }
