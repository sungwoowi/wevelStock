"""권고 데이터 정리 — 종목명 백필 (TRADE-PLAN-LIFECYCLE 2단계 후속).

문제: team_outputs(track_a/b) 권고의 display_name 이 종목코드(예 "298040")로 저장된 행이 많다
(resolve_ticker 의 30종목 매핑 밖). 데스크 "지금 지켜보는 권고" 가 코드로 보인다.
중복은 read-time dedup(load_active_recommendations (track,ticker) 최신)으로 이미 해소 — 행 삭제 안 함
(점인-타임 이력 보존). 이 스크립트는 **종목명만** 안전하게 백필한다.

소스: fetch_kr_leading_stocks(KIS 거래대금 상위, hts_kor_isnm) ∪ KR_TICKER_TO_NAME(정적 30종).
안전: 실행 전 전체 행을 data/backups/ 에 JSONL 백업(되돌리기 가능). 코드→이름 변환 가능한 행만 수정.

usage: uv run python scripts/cleanup_recommendations.py [--apply]   (--apply 없으면 dry-run)
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.db import get_db


def _is_code_like(name: str, ticker: str) -> bool:
    """display_name 이 종목명이 아니라 코드(빈값·숫자·ticker 동일)인가."""
    n = (name or "").strip()
    return (not n) or n == ticker or n.isdigit()


async def _build_name_map() -> dict[str, str]:
    """ticker → 종목명. KIS 거래대금 상위(이름 포함) ∪ 정적 매핑."""
    from core.inference.run_analyst import KR_TICKER_TO_NAME

    names: dict[str, str] = dict(KR_TICKER_TO_NAME)
    try:
        from collectors.kr_leading_stocks import fetch_kr_leading_stocks

        data = await fetch_kr_leading_stocks(None, kospi_limit=200, kosdaq_limit=200)
        for grp in ("kospi", "kosdaq"):
            for item in data.get(grp, []):
                tk, nm = item.get("ticker", ""), item.get("name", "")
                if tk and nm and not nm.isdigit():
                    names[tk] = nm
    except Exception as e:  # noqa: BLE001 — KIS 실패해도 정적 매핑으로 부분 백필
        print(f"[경고] KIS 거래대금 상위 조회 실패 — 정적 매핑만 사용: {str(e)[:80]}")
    return names


async def main() -> None:
    apply = "--apply" in sys.argv[1:]
    db = get_db()
    rows = db.fetch_all(
        "SELECT run_id, team_id, target, data_json FROM team_outputs "
        "WHERE team_id IN ('track_a','track_b') AND target != 'global'"
    )
    print(f"=== 권고 종목명 정리 ({'APPLY' if apply else 'DRY-RUN'}) — 대상 {len(rows)}행 ===")

    name_map = await _build_name_map()
    print(f"종목명 매핑 확보: {len(name_map)}종")

    # 백업 (apply 시에만 — 되돌리기 가능).
    if apply:
        backup_dir = Path("data/backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = backup_dir / f"recommendations_backup_{stamp}.jsonl"
        with backup.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(dict(r), ensure_ascii=False) + "\n")
        print(f"백업 저장: {backup} ({len(rows)}행)")

    fixed = 0
    unresolved: set[str] = set()
    for r in rows:
        try:
            d = json.loads(r["data_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        ticker = d.get("ticker", "")
        if not _is_code_like(d.get("display_name", ""), ticker):
            continue  # 이미 이름 있음
        nm = name_map.get(ticker)
        if not nm:
            unresolved.add(ticker)
            continue
        d["display_name"] = nm
        fixed += 1
        if apply:
            db.execute(
                "UPDATE team_outputs SET data_json = ? WHERE run_id = ? AND team_id = ? AND target = ?",
                (json.dumps(d, ensure_ascii=False), r["run_id"], r["team_id"], r["target"]),
            )

    print(f"\n종목명 백필: {fixed}행 ({'적용됨' if apply else 'dry-run — --apply 로 반영'})")
    if unresolved:
        print(f"이름 못 찾은 종목 {len(unresolved)}개(코드 유지): {sorted(unresolved)}")


if __name__ == "__main__":
    asyncio.run(main())
