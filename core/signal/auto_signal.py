"""자동 권고 생성 funnel 지휘자 (AUTO-SIGNAL-GENERATION-001, M2 — Stage 1).

funnel:
  Stage 0 (watchlist.py, LLM 0) — watchlist 합집합 → 결정론 스크리닝 컷.
  Stage 1 (본 모듈)            — 컷 통과분 종목별 결정론 점수표(분석가 LLM 우회) →
                                 전략가 A/B 직접 호출(종목당 ~1콜) → 권고 persist.
  Stage 2 (후속)               — 매수/매도 뜬 top-K 만 9분석가 풀 fan-out(감사급).

"분석가 우회" = 결정론 점수(F/T/S/buy)는 collectors 직접 호출로 계산(분석가 LLM 호출 0),
전략가 prefetch entries 의 metadata 에 구조 주입 → 전략가 1콜이 verdict 종합.
오늘 코드 검증 결론(점수=코드·분석가=해설자) 그대로: 배치 routine 은 해설 없이 점수만으로 충분.

track="A"→국장 중장기 / "B"→국장 단기 계좌 (desk._accounts_for 가 라우팅). 가상 전용.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable

from core.db import get_db
from core.logging import get_logger
from core.notification.service import notify
from core.signal.watchlist import build_watchlist, get_current_regime, screen_watchlist
from core.strategist.recommendation import (
    StrategistRecommendation,
    parse_recommendation,
    persist_recommendation,
)
from core.strategist.run_strategist import run_strategist

log = get_logger(__name__)

# run_strategist 시그니처 (테스트 주입용 stub).
StrategistRunner = Callable[..., Awaitable[Any]]

_TRACK_ID = {"A": "track_a", "B": "track_b"}
_TRACK_LABEL = {"A": "중장기(Track A)", "B": "단기(Track B)"}

# 전략가 transient 실패 패턴 (재시도 대상). 503/과부하/타임아웃/rate-limit.
_TRANSIENT_MARKERS = ("503", "unavailable", "overloaded", "timeout", "timed out",
                      "rate", "temporarily", "deadline")
_RETRY_BACKOFF_S = 2.0


def _is_transient(err: Exception | str) -> bool:
    """일시적 오류인가 (재시도 가치). 메시지 패턴 매칭 (보수적 — 모르면 False)."""
    s = str(err).lower()
    return any(m in s for m in _TRANSIENT_MARKERS)


@dataclass
class Scorecard:
    """종목 결정론 점수표 — 분석가 LLM 우회로 collectors 직접 계산한 advisory 점수 + 원시지표 md."""

    ticker: str
    display_name: str = ""
    market: str = "KOSPI"
    regime: str | None = None
    s_score: float | None = None
    t_score: float | None = None
    f_score: float | None = None
    buy_score: float | None = None
    distribution_day_count: int | None = None
    md: dict[str, str] = field(default_factory=dict)  # analyst_id → 원시지표 md
    errors: list[str] = field(default_factory=list)


async def compute_scorecard(ticker: str, snapshot: Any) -> Scorecard:
    """종목 결정론 점수표 계산 — build_* collectors 직접 호출(분석가 LLM 0). 각 축 graceful.

    snapshot(MarketSnapshot)은 cadence당 1회 build 후 전 종목 공유(pool·sector_rs·macro 출처).
    """
    # 무거운 모듈은 호출 시 lazy import (스케줄러 import 가벼움 유지).
    from collectors.buy_score_inputs import build_buy_score_inputs, render_buy_score_inputs_md
    from collectors.flow_inputs import build_flow_inputs, render_flow_inputs_md
    from collectors.screening import get_regime_thresholds
    from collectors.screening_inputs import build_s_score_inputs, render_s_score_inputs_md
    from collectors.technicals import build_technicals, render_technicals_md
    from core.inference.run_analyst import (
        _leading_pool_tickers,
        _regime_from_snapshot,
        market_for_ticker,
        resolve_ticker,
    )

    resolved, name = resolve_ticker(ticker)
    sc = Scorecard(ticker=ticker, display_name=name or ticker)
    if resolved is None:
        sc.errors.append(f"ticker_resolve_failed:{ticker}")
        return sc

    market = "KOSDAQ" if market_for_ticker(resolved) == "KQ" else "KOSPI"
    sc.market = market
    pool = _leading_pool_tickers(snapshot)
    sector_rs = snapshot.sector_rs if isinstance(snapshot.sector_rs, list) else None
    macro_map = snapshot.market_macro if isinstance(snapshot.market_macro, dict) else {}
    macro = macro_map.get(market) or macro_map.get("KOSPI")
    sc.regime = _regime_from_snapshot(snapshot, resolved)
    if isinstance(macro, dict):
        dd = macro.get("distribution_count_25d")
        sc.distribution_day_count = int(dd) if isinstance(dd, (int, float)) else None

    # T-Score (trader) — 일봉 기술적
    try:
        ti = await build_technicals(resolved)
        sc.t_score = ti.advisory_t_score
        sc.md["trader"] = render_technicals_md(ti, name=sc.display_name)
    except Exception as e:  # noqa: BLE001 — 한 축 실패가 전체를 막지 않음
        sc.errors.append(f"technicals:{type(e).__name__}")

    # F-Score (flow_analyzer) — 5주체 수급
    try:
        fi = await build_flow_inputs(market=market, ticker=ticker)
        sc.f_score = fi.advisory_f_score
        sc.md["flow_analyzer"] = render_flow_inputs_md(fi)
    except Exception as e:  # noqa: BLE001
        sc.errors.append(f"flow_inputs:{type(e).__name__}")

    # S-Score (stock_picker) — 주도주 RS·정배열
    try:
        si = await build_s_score_inputs(
            ticker=resolved, pool_tickers=pool, sector_rs=sector_rs, regime=sc.regime
        )
        sc.s_score = si.advisory_s_score
        sc.md["stock_picker_s"] = render_s_score_inputs_md(si, name=sc.display_name)
    except Exception as e:  # noqa: BLE001
        sc.errors.append(f"s_score_inputs:{type(e).__name__}")

    # buy_score (stock_picker) — CAN SLIM 7축
    try:
        bi = await build_buy_score_inputs(
            ticker=resolved, pool_tickers=pool,
            market_macro=macro, regime_thresholds=get_regime_thresholds(),
        )
        sc.buy_score = bi.advisory_buy_score
        sc.md["stock_picker_buy"] = render_buy_score_inputs_md(bi, name=sc.display_name)
    except Exception as e:  # noqa: BLE001
        sc.errors.append(f"buy_score_inputs:{type(e).__name__}")

    return sc


def _market_state_md(sc: Scorecard) -> str:
    """결정론 시장상태 entry — regime + 분산일(kill-switch). market_state_analyzer LLM 우회."""
    lines = ["## [결정론 시장 상태] (자동 스크리닝 — LLM 우회)"]
    lines.append(f"- 시장 체제(regime): {sc.regime or '미상'}")
    if sc.distribution_day_count is not None:
        kill = " ⚠️ kill-switch 임계(≥4)" if sc.distribution_day_count >= 4 else ""
        lines.append(f"- Distribution Day(25일): {sc.distribution_day_count}건{kill}")
    return "\n".join(lines)


# 트랙별 전략가가 읽는 score-bearing 분석가 entry (배치 우회 — 나머지는 Stage 2/채팅).
_TRACK_ENTRY_IDS = {
    "A": ("stock_picker", "flow_analyzer", "market_state_analyzer"),
    "B": ("stock_picker", "trader", "flow_analyzer", "market_state_analyzer"),
}


def build_prefetched_entries(sc: Scorecard, track: str) -> list[dict[str, Any]]:
    """결정론 점수표 → 전략가 prefetch entries (분석가 LLM 우회).

    metadata 에 advisory 점수 구조 주입(render_prefetched_analyst_outputs 가 권위값으로 인용),
    text = 원시지표 md. 트랙이 읽는 score-bearing 분석가만 포함.
    stock_analyst(alpha)·wealth_strategist(거시)·principle_guardian 은 배치 MVP 에서 생략
    (Stage 2 풀 fan-out / 채팅에서 보강).
    """
    want = _TRACK_ENTRY_IDS.get(track, ())
    entries: list[dict[str, Any]] = []

    if "stock_picker" in want:
        md = "\n\n".join(
            sc.md[k] for k in ("stock_picker_s", "stock_picker_buy") if k in sc.md
        )
        entries.append({
            "id": "stock_picker",
            "text": md,
            "metadata": {
                "advisory_s_score": sc.s_score,
                "advisory_buy_score": sc.buy_score,
            },
            "error": None,
        })
    if "trader" in want:
        entries.append({
            "id": "trader",
            "text": sc.md.get("trader", ""),
            "metadata": {"advisory_t_score": sc.t_score},
            "error": None,
        })
    if "flow_analyzer" in want:
        entries.append({
            "id": "flow_analyzer",
            "text": sc.md.get("flow_analyzer", ""),
            "metadata": {"advisory_f_score": sc.f_score},
            "error": None,
        })
    if "market_state_analyzer" in want:
        entries.append({
            "id": "market_state_analyzer",
            "text": _market_state_md(sc),
            "metadata": {},
            "error": None,
        })
    return entries


# ---------------------------------------------------------------------------
# 의사결정 밴드 게이트 (M2.5) — 장중 다중 cadence 비용 제어
# ---------------------------------------------------------------------------


def _band(value: float | None, width: float) -> int | None:
    """점수 → 밴드 버킷 (floor). 같은 버킷 = 판단 안 바뀜. None → None."""
    if value is None:
        return None
    return int(value // width)


def band_fingerprint(sc: Scorecard, track: str, *, score_width: float = 1.0) -> str:
    """결정론 밴드 지문 — "verdict 가 바뀔 수 없는 구간". 같으면 전략가 재호출 스킵.

    경계 = 전략가 의사결정 임계(regime 카테고리·점수 티어 버킷·kill-switch). 새 magic number X.
    가격 ADR 버킷·entry/stop 교차는 후속 SLOT (현 MVP = 점수·regime·kill).
    """
    parts = [
        track,
        sc.regime or "?",
        _band(sc.s_score, score_width),
        _band(sc.t_score, score_width),
        _band(sc.f_score, score_width),
        _band(sc.buy_score, score_width),
        1 if (sc.distribution_day_count or 0) >= 4 else 0,
    ]
    return "|".join(str(p) for p in parts)


def _last_band_fingerprint(ticker: str, track: str) -> str | None:
    """직전 persist 된 (ticker, track) 권고의 밴드 지문 (없으면 None)."""
    team_id = _TRACK_ID.get(track)
    if team_id is None:
        return None
    row = get_db().fetch_one(
        "SELECT data_json FROM team_outputs "
        "WHERE team_id = ? AND target = ? ORDER BY timestamp DESC LIMIT 1",
        (team_id, ticker),
    )
    if row is None:
        return None
    try:
        return json.loads(row["data_json"]).get("band_fingerprint")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None


def _signal_directive(sc: Scorecard, track: str, cadence: str) -> str:
    """전략가에게 자동 스크리닝 권고를 요청하는 합성 user 메시지."""
    label = _TRACK_LABEL.get(track, track)
    return (
        f"[자동 스크리닝 · cadence={cadence}] {sc.display_name}({sc.ticker}) 에 대해 "
        f"{label} 권고를 판단하라. 위 Analyst Direct Outputs 의 결정론 점수·원시지표를 근거로 "
        "strategist-recommendation-v1 YAML 을 발행하라. 진입 부적합이면 verdict=wait "
        "(관망도 판단이다 — 매일 발행)."
    )


# ---------------------------------------------------------------------------
# 알림 (M4) — 🟢 매수/매도 개별 · 🔵 일일 요약 (SLOT5)
# ---------------------------------------------------------------------------

_VERDICT_KR = {"buy": "매수", "sell": "매도"}


async def _emit_trade_signal(rec: StrategistRecommendation, cadence: str) -> None:
    """🟢 매수/매도 개별 알림 (trade_signal). buy/sell verdict 만. graceful."""
    action = _VERDICT_KR.get(rec.verdict)
    if action is None:
        return
    name = rec.display_name or rec.ticker
    track_label = _TRACK_LABEL.get(rec.track, rec.track)
    parts = [f"{track_label} · cadence {cadence}"]
    if rec.entry_price is not None:
        parts.append(f"진입 {rec.entry_price:,.0f}")
    if rec.stop_loss is not None:
        parts.append(f"손절 {rec.stop_loss:,.0f}")
    if rec.target_prices:
        parts.append("목표 " + "/".join(f"{p:,.0f}" for p in rec.target_prices))
    body = f"{' · '.join(parts)}\n사유: {'; '.join(rec.reasons[:2]) or '—'}"
    try:
        await notify(
            team_id="auto_signal", level="info",
            title=f"🟢 {action} 신호 — {name}({rec.ticker})", body=body,
            related_run_id=rec.recommendation_id, related_target=rec.ticker,
            notification_type="trade_signal",
        )
    except Exception as e:  # noqa: BLE001 — 알림 실패가 권고 생성을 막지 않음
        log.warning("trade_signal_notify_failed", ticker=rec.ticker, error=str(e))


async def _emit_daily_summary(summary: dict[str, Any]) -> None:
    """🔵 일일 요약 1건 (market_briefing tab=시장/하루 정량). postclose cadence 후 1회."""
    body = (
        f"관심종목 {summary.get('screened', 0)}종 평가 → "
        f"매수 {summary.get('buys', 0)} · 매도 {summary.get('sells', 0)} · "
        f"관망 {summary.get('waits', 0)} · 밴드 스킵 {summary.get('skipped_band', 0)}\n"
        f"시장 체제: {summary.get('regime') or '미상'}"
    )
    try:
        await notify(
            team_id="auto_signal", level="info",
            title=f"🔵 자동 권고 일일 요약 ({summary.get('as_of', '')})", body=body,
            notification_type="market_briefing",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("daily_summary_notify_failed", error=str(e))


async def run_signal_for_ticker(
    *,
    ticker: str,
    track: str,
    snapshot: Any,
    cadence: str,
    as_of: str,
    scorecard: Scorecard | None = None,
    provider: str | None = "gemini",
    mock_fallback_allowed: bool = False,
    strategist_runner: StrategistRunner | None = None,
    band_gate: bool | None = None,
    last_fingerprint_reader: Callable[[str, str], str | None] | None = None,
    notify_signals: bool = True,
    retries: int | None = None,
) -> dict[str, Any]:
    """종목×트랙 1건 — 결정론 점수표 → (밴드 게이트) → 전략가 직접 호출 → persist(source=auto).

    멱등 키 = REC-<as_of>-<cadence>-<ticker>-<track>. 권고 YAML 미발행 시 persist skip.
    밴드 게이트: 지문이 직전 cadence 와 같으면 전략가 호출 스킵(직전 verdict 유지, 비용 0).
    재시도: 전략가 transient 실패(503) + no_yaml 시 retries 회 재호출 (config 기본).
    """
    track_id = _TRACK_ID.get(track)
    if track_id is None:
        return {"ticker": ticker, "track": track, "persisted": False, "reason": "bad_track"}

    sc = scorecard or await compute_scorecard(ticker, snapshot)

    # 밴드 게이트 — 지문 동일 시 LLM 우회(직전 verdict 유지). 비용 ∝ 밴드 넘은 종목 수.
    from collectors.screening import get_band_gate_enabled, get_band_score_width

    enabled = get_band_gate_enabled() if band_gate is None else band_gate
    fingerprint = band_fingerprint(sc, track, score_width=get_band_score_width())
    if enabled:
        reader = last_fingerprint_reader or _last_band_fingerprint
        if reader(ticker, track) == fingerprint:
            return {
                "ticker": ticker, "track": track, "persisted": False,
                "skipped": True, "reason": "band_unchanged",
            }

    entries = build_prefetched_entries(sc, track)
    runner = strategist_runner or run_strategist
    if retries is None:
        from collectors.screening import get_signal_strategist_retries

        retries = get_signal_strategist_retries()
    messages = [{"role": "user", "content": _signal_directive(sc, track, cadence)}]

    rec = None
    last_reason = "no_yaml"
    for attempt in range(retries + 1):
        try:
            resp = await runner(
                track_id, messages, target=ticker,
                prefetched_analyst_outputs=entries,
                provider=provider, mock_fallback_allowed=mock_fallback_allowed,
            )
        except Exception as e:  # noqa: BLE001 — transient 면 재시도, 아니면 그 종목만 skip
            last_reason = str(e)
            if attempt < retries and _is_transient(e):
                await asyncio.sleep(_RETRY_BACKOFF_S * (attempt + 1))
                continue
            return {"ticker": ticker, "track": track, "persisted": False, "reason": last_reason}

        rec = parse_recommendation(getattr(resp, "text", "") or "")
        if rec is not None:
            break
        last_reason = "no_yaml"  # YAML 미발행 → 재시도(LLM 비결정성)
        if attempt < retries:
            await asyncio.sleep(_RETRY_BACKOFF_S * (attempt + 1))

    if rec is None:
        return {"ticker": ticker, "track": track, "persisted": False, "reason": last_reason}

    # cadence-keyed 멱등 id + source/cadence 태그 (point-in-time 보존, SLOT4).
    new_id = f"REC-{as_of}-{cadence}-{ticker}-{track}"
    rec.recommendation_id = new_id
    rec.data = {
        **rec.data, "source": "auto", "cadence": cadence,
        "recommendation_id": new_id, "band_fingerprint": fingerprint,
    }
    ok = persist_recommendation(rec)
    # 🟢 매수/매도 개별 알림 (어느 cadence든 buy/sell 뜨면 즉시 — 출근 중 포착).
    if ok and notify_signals and rec.verdict in ("buy", "sell"):
        await _emit_trade_signal(rec, cadence)
    return {
        "ticker": ticker, "track": track, "verdict": rec.verdict,
        "persisted": ok, "recommendation_id": new_id,
    }


async def run_signal_cadence(
    *,
    cadence: str,
    as_of: str | None = None,
    tracks: tuple[str, ...] = ("A", "B"),
    provider: str | None = "gemini",
    mock_fallback_allowed: bool = False,
    snapshot: Any | None = None,
    strategist_runner: StrategistRunner | None = None,
    band_gate: bool | None = None,
    last_fingerprint_reader: Callable[[str, str], str | None] | None = None,
    notify_signals: bool = True,
) -> dict[str, Any]:
    """한 cadence(09:35/12:35/14:35/18:05) 자동 권고 생성 한 바퀴.

    watchlist 합집합 → 결정론 스크리닝 컷 → 통과 종목×트랙 전략가 직접 호출 → persist.
    종목별 점수표는 1회 계산 후 트랙 간 공유. 가상 전용 — 사용자 개입 0.
    """
    as_of = as_of or date.today().isoformat()
    if snapshot is None:
        from collectors.snapshot import build_market_snapshot

        snapshot, _ = await build_market_snapshot()

    watchlist = await build_watchlist()
    regime = get_current_regime(as_of)
    passers = screen_watchlist(watchlist, regime)

    # 종목 병렬 처리 (bounded — asyncio 코루틴, KIS rate-limit·저사양 보호 동시성 상한).
    from collectors.screening import get_signal_concurrency

    sem = asyncio.Semaphore(max(1, get_signal_concurrency()))

    async def _process_ticker(ticker: str) -> list[dict[str, Any]]:
        async with sem:
            try:
                sc = await compute_scorecard(ticker, snapshot)
            except Exception as e:  # noqa: BLE001 — 점수표 실패 종목만 skip
                log.warning("signal_scorecard_failed", ticker=ticker, error=str(e))
                return [
                    {"ticker": ticker, "track": t, "persisted": False,
                     "reason": f"scorecard:{type(e).__name__}"}
                    for t in tracks
                ]
            out: list[dict[str, Any]] = []
            for track in tracks:  # 트랙은 종목 내 순차 (점수표 공유·Gemini 동시성 절제)
                try:
                    r = await run_signal_for_ticker(
                        ticker=ticker, track=track, snapshot=snapshot, cadence=cadence,
                        as_of=as_of, scorecard=sc, provider=provider,
                        mock_fallback_allowed=mock_fallback_allowed,
                        strategist_runner=strategist_runner,
                        band_gate=band_gate, last_fingerprint_reader=last_fingerprint_reader,
                        notify_signals=notify_signals,
                    )
                except Exception as e:  # noqa: BLE001 — 한 종목 실패가 cadence 를 막지 않음
                    log.warning("signal_ticker_failed", ticker=ticker, track=track, error=str(e))
                    r = {"ticker": ticker, "track": track, "persisted": False, "reason": str(e)}
                out.append(r)
            return out

    nested = await asyncio.gather(*[_process_ticker(row["ticker"]) for row in passers])
    results: list[dict[str, Any]] = [r for sub in nested for r in sub]

    persisted = [r for r in results if r.get("persisted")]
    buys = [r for r in persisted if r.get("verdict") == "buy"]
    sells = [r for r in persisted if r.get("verdict") == "sell"]
    waits = [r for r in persisted if r.get("verdict") not in ("buy", "sell")]
    skipped = [r for r in results if r.get("skipped")]
    summary = {
        "cadence": cadence, "as_of": as_of,
        "watchlist": len(watchlist), "screened": len(passers),
        "evaluated": len(results), "persisted": len(persisted),
        "buys": len(buys), "sells": len(sells), "waits": len(waits),
        "skipped_band": len(skipped),
        "regime": regime, "results": results,
    }
    # 🔵 일일 요약 1건 — postclose cadence 후에만 (장중 cadence 는 요약 push 안 함, 스팸 방지).
    if notify_signals and cadence == "postclose":
        await _emit_daily_summary(summary)
    log.info(
        "signal_cadence_done",
        cadence=cadence, as_of=as_of, watchlist=len(watchlist),
        screened=len(passers), persisted=len(persisted),
        buys=len(buys), sells=len(sells), skipped_band=len(skipped),
    )
    return summary
