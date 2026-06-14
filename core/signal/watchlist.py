"""watchlist 구성 + 결정론 스크리닝 게이트 (AUTO-SIGNAL-GENERATION-001, M1 — funnel Stage 0).

Stage 0 (LLM 0):
  1. build_watchlist — 거래대금 상위(universe) ∪ 보유(account_positions) ∪ 관심(watch_positions).
     국장(6자리)만. dedup(순서 보존).
  2. screen_watchlist — rank_candidates(RS+과열도, 결정론) → screening_score 임계 컷 + 상한.
     통과분만 Stage 1(전략가 직접 호출, M2) 대상.

순수 결정론 — 점수는 코드가 계산(분석가 LLM 호출 없음). cutoff_date 로 과거 시점 재현(백테스팅).
소스(universe/held/watch)·ranker 는 주입 가능(테스트 격리·데스크 패턴 mirror).
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from collectors.screening import (
    get_signal_max_candidates,
    get_signal_min_score,
    rank_candidates,
)
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

# ranker 시그니처 (rank_candidates mirror) — 테스트 주입용.
Ranker = Callable[..., list[dict[str, Any]]]


def is_kr_ticker(ticker: str) -> bool:
    """국장 = 6자리 숫자 코드 (desk._market_of 와 동일 규칙)."""
    return bool(ticker) and ticker.isdigit() and len(ticker) == 6


def _kr_only(tickers: list[str]) -> list[str]:
    return [t for t in tickers if is_kr_ticker(t)]


def load_held_tickers() -> list[str]:
    """보유 종목 — 4계좌 account_positions 의 distinct ticker (shares > 0)."""
    rows = get_db().fetch_all(
        "SELECT DISTINCT ticker FROM account_positions WHERE shares > 0"
    )
    return [r["ticker"] for r in rows if r["ticker"]]


def load_watch_tickers() -> list[str]:
    """사용자 관심종목 — watch_positions (status watching/holding)."""
    rows = get_db().fetch_all(
        "SELECT ticker FROM watch_positions WHERE status IN ('watching', 'holding')"
    )
    return [r["ticker"] for r in rows if r["ticker"]]


async def build_watchlist(
    *,
    universe_tickers: list[str] | None = None,
    held_tickers: list[str] | None = None,
    watch_tickers: list[str] | None = None,
    kis: Any | None = None,
    kr_only: bool = True,
    universe_fetcher: Callable[[Any], Awaitable[list[str]]] | None = None,
) -> list[str]:
    """watchlist 합집합 = universe ∪ 보유 ∪ 관심 (dedup, 순서 보존, 국장만).

    각 소스는 주입 가능 — 미주입 시 라이브(universe=KIS, held/watch=DB) 조회.
    universe_fetcher 미주입 시 collectors.screening.fetch_universe_tickers 사용.
    """
    if universe_tickers is not None:
        uni = list(universe_tickers)
    else:
        if universe_fetcher is None:
            from collectors.screening import fetch_universe_tickers

            universe_fetcher = fetch_universe_tickers
        try:
            uni = await universe_fetcher(kis)
        except Exception as e:  # noqa: BLE001 — universe 실패가 보유/관심 추적을 막지 않음
            log.warning("watchlist_universe_fetch_failed", error=str(e))
            uni = []

    held = held_tickers if held_tickers is not None else load_held_tickers()
    watch = watch_tickers if watch_tickers is not None else load_watch_tickers()

    merged = list(dict.fromkeys([*uni, *held, *watch]))  # dedup, 순서 보존
    if kr_only:
        merged = _kr_only(merged)
    log.info(
        "watchlist_built",
        total=len(merged), universe=len(uni), held=len(held), watch=len(watch),
    )
    return merged


def screen_watchlist(
    watchlist: list[str],
    regime: str | None,
    *,
    cutoff_date: str | None = None,
    min_score: float | None = None,
    max_candidates: int | None = None,
    ranker: Ranker | None = None,
) -> list[dict[str, Any]]:
    """결정론 스크리닝 컷 — rank_candidates → screening_score 임계 통과분만 (Stage 0).

    Args:
        watchlist: build_watchlist 결과.
        regime: 시장 체제 6단계 (screening_score 가중). None → 균등 가중 fallback.
        cutoff_date: 지정 시 그 시점까지 OHLCV (백테스팅 재현).
        min_score / max_candidates: 미지정 시 config(signal_gate). max ≤ 0 → 무제한.
        ranker: 미지정 시 rank_candidates (테스트 주입용).

    Returns:
        통과 종목 dict 리스트 (rank_candidates 형식 + screening_score 내림차순, 상한 적용).
        랭킹 불가(60일 데이터 부족) 종목은 screening_score=None 이라 자동 제외.
    """
    if not watchlist:
        return []
    ranker = ranker or rank_candidates
    if min_score is None:
        min_score = get_signal_min_score()
    if max_candidates is None:
        max_candidates = get_signal_max_candidates()

    ranked = ranker(watchlist, regime, cutoff_date=cutoff_date)
    passers = [
        r for r in ranked
        if r.get("screening_score") is not None and r["screening_score"] >= min_score
    ]
    passers.sort(key=lambda r: (-r["screening_score"], r["ticker"]))
    if max_candidates and max_candidates > 0:
        passers = passers[:max_candidates]
    log.info(
        "watchlist_screened",
        candidates=len(watchlist), passed=len(passers),
        min_score=min_score, regime=regime,
    )
    return passers


def get_current_regime(as_of: str, market: str = "KOSPI") -> str | None:
    """현재 시장 체제 (DB-first, MarketView.regime). 부재·실패 시 None (graceful)."""
    try:
        from collectors.market_view import get_today_view

        view = get_today_view(as_of, market)
        return view.regime if view is not None else None
    except Exception as e:  # noqa: BLE001
        log.warning("current_regime_unavailable", as_of=as_of, error=str(e))
        return None
