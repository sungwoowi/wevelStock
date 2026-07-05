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
    # 차등 변조 입력 (BRAIN-ALPHA-FLEXIBILITY-001 M3a + AUTO-SIGNAL-INTEGRITY-001 T0-b).
    # rs/ext 는 screen_watchlist 행에서 주입(재계산·LLM 0). sector_rs = S-Score supply_chain
    # 실측(theme→섹터 RS) 재사용. wave 는 결정론 anchor α(트랙별 timeframe)에서 파생.
    rs_score: float | None = None
    extension_score: float | None = None
    sector_rs_score: float | None = None
    wave_alive_daily: bool | None = None   # Track B (일봉 α)
    wave_alive_weekly: bool | None = None  # Track A (주봉 α)
    entry_posture: str | None = None       # 시장 진입 자세 (market_view_snapshot DB read)
    # 복합 위험 게이트 입력 (시장 전체 — 폭락 회피). change_pct·breadth 는 macro dict 무료, vix 는 us_macro DB-first.
    index_change_pct: float | None = None
    breadth_ratio: float | None = None
    vix_panic: bool | None = None
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
    if not name:  # 30종 매핑 밖 → 거래대금 상위 멤버십에 기록된 종목명 사용(코드 노출 방지).
        try:
            from collectors.universe_membership import get_stock_name

            name = get_stock_name(ticker)
        except Exception:  # noqa: BLE001 — 이름 조회 실패가 점수표를 막지 않음
            name = None
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
        # 복합 위험 게이트 입력 — macro dict 에 이미 있어 추가 비용 0 (당일 급락·breadth).
        cp = macro.get("change_pct")
        sc.index_change_pct = float(cp) if isinstance(cp, (int, float)) else None
        br = macro.get("breadth_ratio")
        sc.breadth_ratio = float(br) if isinstance(br, (int, float)) else None
    # VIX 패닉 (us_macro DB-first, 시장 전체값·graceful). 폭락 갭다운 방어.
    try:
        from collectors.us_macro import _get_today_us_macro

        usm = _get_today_us_macro(date.today().isoformat())
        sc.vix_panic = (getattr(usm, "extreme", "none") == "vix_panic") if usm else None
    except Exception as e:  # noqa: BLE001 — us_macro 부재가 점수표를 막지 않음
        sc.errors.append(f"us_macro:{type(e).__name__}")

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

    # S-Score (stock_picker) — 주도주 RS·정배열. supply_chain 실측 = 종목 섹터 RS 로 재사용(T0-b).
    try:
        si = await build_s_score_inputs(
            ticker=resolved, pool_tickers=pool, sector_rs=sector_rs, regime=sc.regime
        )
        sc.s_score = si.advisory_s_score
        sc.sector_rs_score = _sector_rs_from_s_inputs(si)
        sc.md["stock_picker_s"] = render_s_score_inputs_md(si, name=sc.display_name)
    except Exception as e:  # noqa: BLE001
        sc.errors.append(f"s_score_inputs:{type(e).__name__}")

    # 파동 생존 (T0-b) — 결정론 anchor α (anchor_llm_enabled=false 기본, 캐시). 트랙별 timeframe.
    try:
        from collectors.anchors import compute_alpha_3tf
        from core.signal.alpha_posture import derive_wave_alive

        alpha_res = await compute_alpha_3tf(resolved)
        sc.wave_alive_daily = derive_wave_alive(alpha_res, "B")
        sc.wave_alive_weekly = derive_wave_alive(alpha_res, "A")
    except Exception as e:  # noqa: BLE001 — α 부재가 점수표를 막지 않음
        sc.errors.append(f"alpha_wave:{type(e).__name__}")

    # 시장 진입 자세 (T0-a) — market_view_snapshot DB read only (빌드 트리거 X, 비용 0).
    try:
        from collectors.market_view import get_today_view

        view = get_today_view(date.today().isoformat(), market)
        sc.entry_posture = view.entry_posture if view else None
    except Exception as e:  # noqa: BLE001 — 스냅샷 부재가 점수표를 막지 않음
        sc.errors.append(f"market_view:{type(e).__name__}")

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


def _sector_rs_from_s_inputs(si: Any) -> float | None:
    """S-Score supply_chain 축 → 종목 섹터 RS (T0-b). 실측(theme_sector)일 때만 채택.

    중립 fallback(5.0)은 섹터 RS 로 오인되면 안 되므로 None — AlphaPosture 가 미상으로 보수 처리.
    """
    if si is None or getattr(si, "supply_chain_source", None) != "theme_sector":
        return None
    return getattr(si, "supply_chain_score", None)


def _market_news_digest_md(as_of: str) -> str | None:
    """뉴스 종합+격상 이벤트 해석 md — DB-first(LLM 0)·lookback 폴백 (M1-c). graceful."""
    try:
        from collectors.news_source import render_market_news_digest_md

        return render_market_news_digest_md(as_of)
    except Exception as e:  # noqa: BLE001 — 뉴스 층 실패가 권고 생성을 막지 않음
        log.warning("news_digest_md_failed", as_of=as_of, error=str(e))
        return None


def _market_state_md(sc: Scorecard) -> str:
    """결정론 시장상태 entry — regime + 시장 위험 원시지표 (market_state_analyzer LLM 우회).

    위험 판정(폭락/천장 차단)은 아래 'AlphaPosture 후보' 의 복합 위험 게이트가 소유한다 —
    여기서 개별 임계(예: DD≥4)를 재적용하지 말 것(2026-06-15 라이브: stale ≥4 하드코딩이 buy 후보를
    blanket wait 시킨 누수 정정). 이 블록은 원시 신호 보고만.
    """
    lines = ["## [결정론 시장 상태] (자동 스크리닝 — LLM 우회, 원시 신호 보고)"]
    lines.append(f"- 시장 체제(regime): {sc.regime or '미상'}")
    lines.append(f"- 진입 자세(entry_posture): {sc.entry_posture or '미상'}")
    if sc.distribution_day_count is not None:
        lines.append(f"- Distribution Day(25일): {sc.distribution_day_count}건")
    if sc.index_change_pct is not None:
        lines.append(f"- 당일 지수 등락률: {sc.index_change_pct:+.1f}%")
    if sc.breadth_ratio is not None:
        lines.append(f"- 상승종목 비율(breadth): {sc.breadth_ratio:.2f}")
    lines.append(
        "- ※ 폭락/천장 위험 차단 판정은 아래 'AlphaPosture 후보' 의 **위험 게이트**가 소유 "
        "(여기서 DD·등락률에 개별 임계 재적용 금지)."
    )
    return "\n".join(lines)


# 트랙별 전략가가 읽는 score-bearing 분석가 entry (배치 우회 — 나머지는 Stage 2/채팅).
_TRACK_ENTRY_IDS = {
    "A": ("stock_picker", "flow_analyzer", "market_state_analyzer"),
    "B": ("stock_picker", "trader", "flow_analyzer", "market_state_analyzer"),
}

# 배치 경로에서 의도적으로 우회하는 분석가 (점수=코드·AlphaPosture 후보가 대체).
# 이들을 "누락" 이 아니라 "의도적 우회" entry 로 주입해야 LLM 이 미발행으로 세어 wait 강등하는 걸 막는다
# (2026-06-15 라이브: persona text 예외로는 LLM 이 안전핀 규칙으로 회귀 → 구조로 해결).
_TRACK_BYPASSED_IDS = {
    "A": ("stock_analyst", "wealth_strategist", "principle_guardian"),
    "B": ("stock_analyst", "wealth_strategist", "principle_guardian"),
}
_BYPASS_NOTE = (
    "(자동 스크리닝 배치 경로 — 이 분석가는 **의도적으로 우회**되었다. 점수=코드 + 아래 "
    "AlphaPosture 후보가 이 영역을 대체한다. **미발행/누락/호출 실패가 아니며, 이를 근거로 "
    "verdict 를 wait 로 강등하지 말 것.** 단 원칙수호자 영역 중 결정론 검증 가능한 계명"
    "(손절선·지표 교차·데이터 기반)은 신호 발행 전 코드가 별도 체크한다.)"
)


def _signal_commandment_gate(rec: Any, sc: Scorecard) -> None:
    """buy 신호 발행 전 결정론 7계명 체크 (AUTO-SIGNAL-INTEGRITY-001 T0-c).

    자동 경로가 principle_guardian LLM 을 우회하므로, 위치에서 검증 가능한 계명만 기존
    checkers/commandments 를 **그대로 재사용**해 체크한다 (신규 규칙 0):
      계명 4 손절선 — rec.stop_loss / 계명 5 최소 3개 지표 교차 — 산출된 결정론 지표 축 /
      계명 6 데이터 기반 — 지표 축 존재.
    비중 계명(1·2·3)은 계좌관리자 sizing(deployment_cap)이 소유 — 여기서 중복 구현 금지.
    violation → wait 강등 + 기록 / warning → 기록만 (체커 severity 의미 준수). in-place.
    """
    if rec.verdict != "buy":
        return
    from checkers.commandments import data_based, multi_indicator, stop_loss

    indicators = [
        name for name, v in (
            ("s_score", sc.s_score), ("t_score", sc.t_score), ("f_score", sc.f_score),
            ("buy_score", sc.buy_score), ("rs_score", sc.rs_score),
            ("extension_score", sc.extension_score), ("sector_rs", sc.sector_rs_score),
        ) if v is not None
    ]
    portfolio = {"positions": [{
        "ticker": rec.ticker,
        "stop_loss": rec.stop_loss,
        "rationale_at_entry": indicators,
    }]}
    results = [
        stop_loss.check(portfolio),
        multi_indicator.check(portfolio),
        data_based.check(portfolio),
    ]
    to_entry = lambda r: {"commandment": r.commandment_id, "title": r.title, "detail": r.detail}  # noqa: E731
    violations = [to_entry(r) for r in results if r.is_violation]
    warnings = [to_entry(r) for r in results if r.is_warning]
    if warnings:
        rec.data["commandment_warnings"] = warnings
    if not violations:
        return
    rec.data["commandment_violations"] = violations
    rec.data.setdefault("posture_blocked", "buy")  # 원판단 기록 (채점 재료)
    rec.verdict = "wait"
    rec.reasons.insert(
        0,
        "결정론 7계명 체크 위반 — 관망 강등 ("
        + "; ".join(v["detail"] for v in violations) + ")",
    )
    log.info("commandment_gate_demote", ticker=rec.ticker, track=rec.track,
             violations=[v["commandment"] for v in violations])


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
    # 우회 분석가 = "의도적 우회" entry 로 명시 주입 (미발행으로 안 세이게 — 구조적 누수 차단).
    for aid in _TRACK_BYPASSED_IDS.get(track, ()):
        entries.append({
            "id": aid,
            "text": _BYPASS_NOTE,
            "metadata": {"batch_bypassed": True},
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


def posture_inputs_from_scorecard(sc: Scorecard, track: str) -> "PostureInputs":
    """Scorecard → AlphaPosture 입력 (BRAIN-ALPHA-FLEXIBILITY-001 M3a + INTEGRITY T0-a/b).

    rs/ext 는 screen_watchlist 행에서 주입된 값(없으면 None — graceful). sector_rs = supply_chain
    실측 재사용, wave = 트랙별 timeframe(A=주봉/B=일봉) α 파생, entry_posture = market_view DB read.
    """
    from core.signal.alpha_posture import PostureInputs

    return PostureInputs(
        track=track,
        regime=sc.regime,
        s_score=sc.s_score,
        t_score=sc.t_score,
        f_score=sc.f_score,
        buy_score=sc.buy_score,
        rs_score=sc.rs_score,
        extension_score=sc.extension_score,
        sector_rs_score=sc.sector_rs_score,
        distribution_day_count=sc.distribution_day_count,
        wave_alive=sc.wave_alive_weekly if track == "A" else sc.wave_alive_daily,
        index_change_pct=sc.index_change_pct,
        breadth_ratio=sc.breadth_ratio,
        vix_panic=sc.vix_panic,
        entry_posture=sc.entry_posture,
    )


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
    from collectors.universe_membership import resolve_stock_name

    name = resolve_stock_name(rec.ticker, rec.display_name)
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
            title=f"🟢 {action} 신호 — {name}", body=body,
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


def _apply_trade_plan_guardrails(rec: Any, menu: Any, cfg: Any) -> None:
    """절대 가드레일 (TRADE-PLAN-LIFECYCLE-001 B-MS1) — LLM 권고에 결정론 강제.

    ① 오닐 −7% floor: buy 손절이 −7% 초과(가격이 더 낮음)면 floor 로 clamp(+로그).
    ② menu-bound 감사: entry/stop/target 이 메뉴 후보와 모두 멀면 pl=false 플래그(환각 의심).
    rec.data['trade_plan'] 에 가산(파서가 채운 다단 필드와 병합). 순수·graceful.
    """
    from core.signal.trade_plan_menu import clamp_stop_to_oneill, is_menu_bound

    if cfg is None or rec.verdict != "buy":
        return
    plan = dict(rec.data.get("trade_plan") or {})

    # ① 오닐 −7% floor clamp (entry·stop 둘 다 있을 때만).
    if rec.entry_price and rec.stop_loss:
        clamped, was = clamp_stop_to_oneill(rec.entry_price, rec.stop_loss, cfg)
        if was:
            plan["oneill_clamped"] = {"from": round(rec.stop_loss, 2), "to": round(clamped, 2)}
            rec.stop_loss = clamped
            log.info("trade_plan_oneill_clamp", ticker=rec.ticker,
                     frm=plan["oneill_clamped"]["from"], to=plan["oneill_clamped"]["to"])

    # ② menu-bound 감사 — LLM 가격이 결정론 메뉴 후보에 근거하는지(환각 차단).
    candidates: list[float] = [c.price for c in menu.stop_candidates]
    candidates += [leg.price for leg in menu.buy_ladder]
    candidates += [c.price for c in menu.target_candidates]
    prices = [p for p in (rec.entry_price, rec.stop_loss, *rec.target_prices) if p]
    if candidates and prices:
        bound = all(is_menu_bound(p, candidates, cfg.menu_bound_tol_pct) for p in prices)
        plan["menu_bound"] = bound
        if not bound:
            log.warning("trade_plan_menu_unbound", ticker=rec.ticker, track=rec.track)

    if plan:
        rec.data["trade_plan"] = plan


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
    # 결정론 차등 변조 후보 (M3a) — regime baseline × 섹터RS × 주도주 × 파동 × 과열도.
    # 전략가에 권위 베이스라인으로 주입(가드레일 있는 C) + 권고에 항상 영속(설명가능성).
    from core.signal.alpha_posture import derive_alpha_posture, render_alpha_posture_md

    posture, posture_md, posture_inputs, posture_cfg = None, None, None, None
    try:
        from collectors.screening import load_posture_config

        posture_inputs = posture_inputs_from_scorecard(sc, track)
        posture_cfg = load_posture_config()
        posture = derive_alpha_posture(posture_inputs, posture_cfg)
        posture_md = render_alpha_posture_md(posture)
    except Exception as e:  # noqa: BLE001 — 변조 실패가 권고 생성을 막지 않음(graceful)
        log.warning("alpha_posture_failed", ticker=ticker, track=track, error=str(e))
        posture, posture_md, posture_inputs, posture_cfg = None, None, None, None

    # 결정론 가격대 메뉴 (TRADE-PLAN-LIFECYCLE-001 B-MS1) — 다단 손절/분할매수/목표 *후보*를
    # 사실로 주입(숫자 환각 차단). LLM 이 이 중에서 선택·조합. 영속(설명가능성) + 절대 가드레일.
    trade_plan_menu, trade_plan_menu_md, tp_cfg = None, None, None
    try:
        from collectors.charts import load_ohlcv_from_db
        from collectors.screening import load_trade_plan_config
        from core.inference.run_analyst import resolve_ticker as _resolve_tp
        from core.signal.trade_plan_menu import (
            build_trade_plan_menu, render_trade_plan_menu_md, trade_plan_inputs_from_ohlcv,
        )

        resolved_code, _ = _resolve_tp(ticker)
        if resolved_code:
            tp_cfg = load_trade_plan_config()
            tp_inputs = trade_plan_inputs_from_ohlcv(
                load_ohlcv_from_db(resolved_code), ticker=ticker,
                extension=sc.extension_score, config=tp_cfg,
            )
            trade_plan_menu = build_trade_plan_menu(tp_inputs, tp_cfg)
            trade_plan_menu_md = render_trade_plan_menu_md(trade_plan_menu)
    except Exception as e:  # noqa: BLE001 — 메뉴 실패가 권고 생성을 막지 않음(graceful)
        log.warning("trade_plan_menu_failed", ticker=ticker, track=track, error=str(e))

    # 진입존(팩트) 보강 (TRADE-PLAN-LIFECYCLE-001 2단계) — 관망 종목 conditional_entry 에
    # 메뉴 지지 후보 zone 부착 후 posture_md 재렌더(zone 반영). 메뉴 있을 때만(중복 렌더 회피).
    if posture is not None and posture.conditional_entry is not None and trade_plan_menu is not None:
        from core.signal.alpha_posture import enrich_conditional_entry

        posture.conditional_entry = enrich_conditional_entry(posture.conditional_entry, trade_plan_menu)
        posture_md = render_alpha_posture_md(posture)

    # 뉴스 종합 + 격상 이벤트 해석 (NEWS-EVENT-INTERPRETATION-001 M1-c) — DB-first
    # read(LLM 0) + lookback 폴백(장전·주말 stale 시점 표기). as_of 기준 = point-in-time
    # 보존(리플레이 재현). 실패는 격리 — 뉴스 층이 권고 생성을 막지 않음 (advisory).
    news_digest_md = _market_news_digest_md(as_of)

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
                alpha_posture_md=posture_md,
                trade_plan_menu_md=trade_plan_menu_md,
                news_digest_md=news_digest_md,
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

    # 방어 태세 차등 게이트 — 코드 안전핀 (AUTO-SIGNAL-INTEGRITY-001 T0-a).
    # persona 지시만으로 LLM 분기를 강제할 수 없음(2026-06-15 교훈) → 후보가 defensive 강등인데
    # LLM 이 사실 근거(llm_deviation_reason) 없이 buy 를 내면 코드가 wait 강등 + 원판단 기록.
    if (
        posture is not None
        and posture.modulation.get("defensive_demote")
        and rec.verdict == "buy"
        and not rec.data.get("llm_deviation_reason")
    ):
        rec.data["posture_blocked"] = "buy"
        rec.verdict = "wait"
        rec.reasons.insert(0, "시장 방어 태세 차등 게이트 — 사실 근거 없는 매수를 관망으로 강등")
        log.info("defensive_gate_demote", ticker=ticker, track=track)

    # 결정론 7계명 체크 (T0-c) — 손절선·지표 교차·데이터 기반. violation 시 wait 강등.
    _signal_commandment_gate(rec, sc)

    # cadence-keyed 멱등 id + source/cadence 태그 (point-in-time 보존, SLOT4).
    new_id = f"REC-{as_of}-{cadence}-{ticker}-{track}"
    rec.recommendation_id = new_id
    rec.data = {
        **rec.data, "source": "auto", "cadence": cadence,
        "recommendation_id": new_id, "band_fingerprint": fingerprint,
    }
    # 결정론 후보 영속 — LLM verdict 와 무관하게 항상(설명가능성·deviation 감사 기준).
    # alpha_posture 는 보강된 conditional_entry(진입존 zone)를 포함해 영속.
    if posture is not None:
        rec.data["alpha_posture"] = posture.to_dict()
        # 단계 라벨 파생(결정론 룰) — 관심/매수대기/진입. LLM verdict + 점수근접 + 진입존 조립.
        if posture_inputs is not None:
            from core.signal.alpha_posture import derive_funnel_stage

            stage = derive_funnel_stage(
                rec.verdict, posture_inputs, posture.conditional_entry, posture_cfg
            )
            rec.data["funnel_stage"] = stage.stage
            rec.data["stage_reason"] = stage.reason
    if trade_plan_menu is not None:
        rec.data["trade_plan_menu"] = trade_plan_menu.to_dict()
        _apply_trade_plan_guardrails(rec, trade_plan_menu, tp_cfg)
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

    watchlist = await build_watchlist()  # universe(거래대금 상위) 멤버십도 여기서 영속(list_type=trade_value)
    # 거래량 양봉 상위 리스트 영속 (관심종목 페이지) — 장중=실시간 시가 / postclose=EOD 일봉. graceful.
    try:
        from collectors.screening import load_curation_config
        from collectors.universe_curation import curate_groups
        from collectors.universe_membership import persist_universe_membership
        from collectors.volume_bull import fetch_kr_volume_bull

        vb = await fetch_kr_volume_bull(intraday=(cadence != "postclose"))
        vb = curate_groups(vb, list_type="volume_bull", cfg=load_curation_config())  # 잡주 floor+정배열
        persist_universe_membership(vb, list_type="volume_bull")
    except Exception as e:  # noqa: BLE001 — 리스트 갱신 실패가 권고 생성을 막지 않음
        log.warning("volume_bull_refresh_failed", cadence=cadence, error=str(e))
    regime = get_current_regime(as_of)
    passers = screen_watchlist(watchlist, regime)

    # 종목 병렬 처리 (bounded — asyncio 코루틴, KIS rate-limit·저사양 보호 동시성 상한).
    from collectors.screening import get_signal_concurrency

    sem = asyncio.Semaphore(max(1, get_signal_concurrency()))

    async def _process_ticker(row: dict[str, Any]) -> list[dict[str, Any]]:
        ticker = row["ticker"]
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
            # 차등 변조 입력 — screen_watchlist 행의 결정론 RS·과열도 주입(재계산·LLM 0).
            if sc.rs_score is None:
                sc.rs_score = row.get("rs_score")
            if sc.extension_score is None:
                sc.extension_score = row.get("extension_score")
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

    nested = await asyncio.gather(*[_process_ticker(row) for row in passers])
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
