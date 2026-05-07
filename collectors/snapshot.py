"""Market snapshot for analyst system prompt — 7 collector 병렬 + 5분 인메모리 캐시.

목적: 분석가 LLM 호출 직전에 user_want_spec Task 2/3 의 시장 raw 를 모아
      `compose.build_pipeline_prompt` 의 RAG 직전 블록으로 자동 주입한다.
      framework 명제만 인용하던 응답이 실제 환율·VIX·수급 수치와 결합되도록.

7 collector (병렬):
  1) us_markets.fetch_overnight       — 나스닥/S&P500/SOX/VIX/DXY/USD-KRW/US10Y/금/WTI
  2) fear_greed.fetch_fear_greed      — CNN F&G 0~100
  3) kr_indices.fetch_kr_indices      — KOSPI/KOSDAQ/KOSPI200
  4) kr_supply_demand                 — KOSPI/KOSDAQ 5주체 수급 (백만원)
  5) kr_sectors                       — 강세 섹터 ETF (+1% 이상)
  6) kr_leading_stocks                — 코스피 10 + 코스닥 7 주도주
  7) kr_futures_supply_demand         — KOSPI200 선물 3주체 (십억원, KRX)

캐시: 모듈 수준 _LAST 인메모리. max_age_seconds (기본 300s) 안이면 재사용.
      서버 1 프로세스 가정 — 분산 환경 시 별도 backend 필요.

Partial failure: asyncio.gather(return_exceptions=True) — 일부 실패해도 나머지
                  진행, 실패 collector 키는 snapshot.failures 에 기록.
"""
from __future__ import annotations

import asyncio
import sys
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from collectors.fear_greed import fetch_fear_greed
from collectors.kr_futures_supply_demand import fetch_kr_futures_supply_demand
from collectors.kr_indices import fetch_kr_indices
from collectors.kr_leading_stocks import fetch_kr_leading_stocks
from collectors.kr_sectors import fetch_kr_sectors
from collectors.kr_supply_demand import fetch_kr_supply_demand
from collectors.us_markets import fetch_overnight
from connectors.kis import KISClient
from connectors.krx import KRXClient
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")


@dataclass
class MarketSnapshot:
    fetched_at: float                       # epoch seconds
    fetched_at_iso: str                     # KST ISO-8601
    overnight: dict[str, Any]
    fear_greed: dict[str, Any]
    kr_indices: dict[str, Any]
    kr_supply: dict[str, Any]
    kr_futures_supply: dict[str, Any]
    kr_sectors: dict[str, Any]
    kr_leading: dict[str, Any]
    failures: list[str] = field(default_factory=list)


_LAST: MarketSnapshot | None = None
_LAST_AT: float = 0.0


async def build_market_snapshot(
    *,
    kis: KISClient | None = None,
    krx: KRXClient | None = None,
    max_age_seconds: int = 300,
) -> tuple[MarketSnapshot, bool]:
    """7 collector 병렬 fetch + 5분 인메모리 캐시.

    Returns:
        (snapshot, cache_hit). cache_hit=True 면 max_age_seconds 안 캐시 재사용.

    Note:
        - cold call 시 stderr 에 진행 표시 (CLI/REPL 만 직접 보임).
        - 동시 호출 시 두 번 fetch 될 수 있음 (last-writer-wins) — 정합성은 유지.
        - kis/krx 가 None 이면 자체 context manager 로 단명 client 생성.
    """
    global _LAST, _LAST_AT

    now = time.time()
    if _LAST is not None and (now - _LAST_AT) < max_age_seconds:
        return _LAST, True

    sys.stderr.write("[market snapshot fetching... ~30s]\n")
    sys.stderr.flush()
    started = time.monotonic()

    async with AsyncExitStack() as stack:
        if kis is None:
            kis = await stack.enter_async_context(KISClient())
        if krx is None:
            krx = await stack.enter_async_context(KRXClient())

        results = await asyncio.gather(
            fetch_overnight(),
            fetch_fear_greed(),
            fetch_kr_indices(kis),
            fetch_kr_supply_demand(kis),
            fetch_kr_sectors(kis),
            fetch_kr_leading_stocks(kis),
            fetch_kr_futures_supply_demand(krx),
            return_exceptions=True,
        )

    labels = [
        "overnight", "fear_greed", "kr_indices", "kr_supply",
        "kr_sectors", "kr_leading", "kr_futures_supply",
    ]
    bucket: dict[str, Any] = {}
    failures: list[str] = []
    for label, res in zip(labels, results):
        if isinstance(res, Exception):
            bucket[label] = {"error": f"{type(res).__name__}: {res}"}
            failures.append(label)
        else:
            bucket[label] = res

    elapsed = time.monotonic() - started
    snapshot = MarketSnapshot(
        fetched_at=now,
        fetched_at_iso=datetime.fromtimestamp(now, _KST).isoformat(timespec="seconds"),
        overnight=bucket["overnight"],
        fear_greed=bucket["fear_greed"],
        kr_indices=bucket["kr_indices"],
        kr_supply=bucket["kr_supply"],
        kr_futures_supply=bucket["kr_futures_supply"],
        kr_sectors=bucket["kr_sectors"],
        kr_leading=bucket["kr_leading"],
        failures=failures,
    )
    _LAST = snapshot
    _LAST_AT = now

    sys.stderr.write(
        f"[market snapshot ready in {elapsed:.1f}s · {len(failures)} failed]\n"
    )
    sys.stderr.flush()
    log.info(
        "market_snapshot_built",
        elapsed_s=round(elapsed, 2),
        failures=failures,
    )
    return snapshot, False


def reset_cache() -> None:
    """테스트 전용 — 모듈 캐시 초기화."""
    global _LAST, _LAST_AT
    _LAST = None
    _LAST_AT = 0.0


# ---------------------------------------------------------------------------
# Render — analyst system prompt 용 마크다운
# ---------------------------------------------------------------------------


def _pct(v: Any) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "?"


def _num(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return "?"


def _won_m(million: Any) -> str:
    """백만원 → 한국식 억/조 (부호 포함)."""
    if million is None:
        return "?"
    try:
        eok = float(million) / 100.0
    except (TypeError, ValueError):
        return "?"
    sign = "+" if eok >= 0 else ""
    if abs(eok) >= 10000:
        return f"{sign}{eok / 10000:,.2f}조"
    return f"{sign}{eok:,.0f}억"


def _won_b(billion: Any) -> str:
    """십억원 → 억 (부호 포함). 1 십억원 = 10 억."""
    if billion is None:
        return "?"
    try:
        eok = float(billion) * 10.0
    except (TypeError, ValueError):
        return "?"
    sign = "+" if eok >= 0 else ""
    if abs(eok) >= 10000:
        return f"{sign}{eok / 10000:,.2f}조"
    return f"{sign}{eok:,.0f}억"


def _trade_amount_jo(million_won: Any) -> str:
    if million_won is None:
        return "?"
    try:
        jo = float(million_won) / 1_000_000.0
    except (TypeError, ValueError):
        return "?"
    return f"{jo:,.2f}조"


def _err_msg(d: Any) -> str:
    return d.get("error") if isinstance(d, dict) else "수집 실패"


def render_snapshot_md(snapshot: MarketSnapshot) -> str:
    """분석가 system prompt 용 마크다운.

    실패 항목은 `[수집 실패 - 사유]` 로 표기 — 7계명 #6 (데이터 없이 추측 X) 정합.
    """
    lines: list[str] = []
    age = max(0, int(time.time() - snapshot.fetched_at))
    lines.append(f"_생성: {snapshot.fetched_at_iso} · age {age}s_")
    lines.append("")

    # 1. 미국 지수
    lines.append("### 미국 지수 (전일 종가 대비)")
    overnight = snapshot.overnight if isinstance(snapshot.overnight, dict) else {}
    for key, label in [
        ("nasdaq", "나스닥"),
        ("sp500", "S&P500"),
        ("sox", "필반(SOX)"),
        ("vix", "VIX"),
    ]:
        v = overnight.get(key)
        if isinstance(v, dict) and "error" not in v:
            lines.append(f"- {label} {_num(v.get('price'))} ({_pct(v.get('change_pct'))})")
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(v)}]")
    lines.append("")

    # 2. 환율·금리·원자재
    lines.append("### 환율·금리·원자재 (전일 종가 대비)")
    for key, label in [
        ("dxy", "DXY (달러인덱스)"),
        ("usdkrw", "USD/KRW (원달러)"),
        ("us_10y", "US10Y (10년 국채금리)"),
        ("gold", "금 GC=F"),
        ("wti", "WTI CL=F"),
    ]:
        v = overnight.get(key)
        if isinstance(v, dict) and "error" not in v:
            lines.append(f"- {label} {_num(v.get('price'))} ({_pct(v.get('change_pct'))})")
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(v)}]")
    lines.append("")

    # 3. 공포·탐욕
    lines.append("### 공포·탐욕 (CNN F&G)")
    fg = snapshot.fear_greed if isinstance(snapshot.fear_greed, dict) else {}
    if "error" not in fg and fg.get("score") is not None:
        prev = fg.get("previous_close")
        rating_kr = fg.get("rating_kr") or fg.get("rating") or ""
        prev_str = f" (전일 {prev})" if prev is not None else ""
        lines.append(f"- score {fg['score']} [{rating_kr}]{prev_str}")
    else:
        lines.append(f"- [수집 실패 - {_err_msg(fg)}]")
    lines.append("")

    # 4. 한국 지수
    lines.append("### 한국 지수 (KRX 정규장 전일 종가 대비)")
    indices = snapshot.kr_indices if isinstance(snapshot.kr_indices, dict) else {}
    for key, label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
        v = indices.get(key)
        if isinstance(v, dict) and "error" not in v:
            lines.append(
                f"- {label} {_num(v.get('value'))} ({_pct(v.get('change_pct'))}) · "
                f"거래대금 {_trade_amount_jo(v.get('trade_amount'))}"
            )
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(v)}]")
    k200 = indices.get("kospi200")
    if isinstance(k200, dict) and "error" not in k200:
        lines.append(
            f"- KOSPI200 (선물 기초) {_num(k200.get('value'))} "
            f"({_pct(k200.get('change_pct'))})"
        )
    lines.append("")

    # 5. 5주체 수급
    lines.append("### 시장 전체 수급 (시장 합계 누적)")
    supply = snapshot.kr_supply if isinstance(snapshot.kr_supply, dict) else {}
    for key, label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
        s = supply.get(key)
        if isinstance(s, dict) and "error" not in s:
            lines.append(
                f"- {label}: 개인 {_won_m(s.get('individual_net_amount_m'))} / "
                f"외인 {_won_m(s.get('foreign_net_amount_m'))} / "
                f"기관 {_won_m(s.get('institution_net_amount_m'))} "
                f"(금투 {_won_m(s.get('fin_invest_net_amount_m'))} / "
                f"연기금 {_won_m(s.get('pension_net_amount_m'))})"
            )
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(s)}]")
    lines.append("")

    # 6. 선물 수급
    lines.append("### KOSPI200 선물 수급 (3주체)")
    fut = snapshot.kr_futures_supply if isinstance(snapshot.kr_futures_supply, dict) else {}
    if "error" not in fut and fut.get("trade_date"):
        lines.append(
            f"- {fut.get('trade_date')}: 개인 {_won_b(fut.get('individual_net_amount_b'))} / "
            f"외인 {_won_b(fut.get('foreign_net_amount_b'))} / "
            f"기관 {_won_b(fut.get('institution_net_amount_b'))}"
        )
    else:
        lines.append(f"- [수집 실패 - {_err_msg(fut)}]")
    lines.append("")

    # 7. 강세 섹터
    lines.append("### 강세 섹터 (+1% 이상, 상승률 순)")
    sectors = snapshot.kr_sectors if isinstance(snapshot.kr_sectors, dict) else {}
    if "error" not in sectors:
        strong = sectors.get("strong") or []
        if strong:
            for r in strong:
                lines.append(
                    f"- {r.get('name', '?')} ({r.get('ticker', '?')}) "
                    f"{_pct(r.get('change_pct'))}"
                )
        else:
            lines.append("- (조건 충족 ETF 없음)")
    else:
        lines.append(f"- [수집 실패 - {_err_msg(sectors)}]")
    lines.append("")

    # 8. 주도주
    lines.append("### 주도주 (KOSPI 10 + KOSDAQ 7, match 우선 + 거래대금 보충)")
    leading = snapshot.kr_leading if isinstance(snapshot.kr_leading, dict) else {}
    if "error" not in leading:
        for market_key, market_label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
            rows = leading.get(market_key) or []
            if not rows:
                lines.append(f"- {market_label}: (없음)")
                continue
            lines.append(f"- {market_label}:")
            for r in rows:
                tier = r.get("cap_tier", "")
                match = r.get("match", "")
                tag = f"[{tier}·{match}]" if tier else f"[{match}]"
                lines.append(
                    f"  · {r.get('name', '?')} ({r.get('ticker', '?')}) "
                    f"{_pct(r.get('change_pct'))} {tag}"
                )
    else:
        lines.append(f"- [수집 실패 - {_err_msg(leading)}]")

    if snapshot.failures:
        lines.append("")
        lines.append(f"_누락 collector: {', '.join(snapshot.failures)}_")

    return "\n".join(lines)
