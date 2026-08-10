"""자동 권고 일일 요약 알림 본문 렌더 (AUTO-SIGNAL-DIGEST-001).

`run_signal_cadence` 가 만든 summary dict → 텔레그램/웹앱 알림 본문 문자열.
**순수 함수** — LLM 0, DB 0, 외부 호출 0. 새 판단을 만들지 않고, 이미 만들어 영속한
판단(종목명·신뢰도·사유·점수·진입 조건)을 알림에서 버리지 않을 뿐이다.

이전 버전은 카운트만 렌더해 "뭐가 매수고 뭐가 관망인지" 알 수 없었고, 무엇보다
**버킷 합이 평가 총건수와 안 맞는 것을 숨겨** Track A 미산출이 두 달 가까이 안 보였다.
그래서 이 모듈의 불변식은 하나다 — **모든 결과는 반드시 어느 버킷엔가 표시된다.**
"""
from __future__ import annotations

import re
from typing import Any

from collectors.market_view import POSTURE_KR, REGIME_KR

# 트랙 짧은 라벨 — auto_signal._TRACK_LABEL("중장기(Track A)")은 LLM 지시문용 정식 명칭이라
# 사용자 알림에는 괄호 코드명을 뺀 짧은 형태를 쓴다.
_TRACK_SHORT = {"A": "중장기", "B": "단기"}

_VERDICT_KR = {"buy": "매수", "sell": "매도", "wait": "관망"}

# funnel_stage (TRADE-PLAN-LIFECYCLE-001 2단계) → 사용자 라벨.
_STAGE_KR = {"interest": "관심", "watching": "매수대기", "entering": "진입"}

# 점수 → 한국어 라벨. 코드 라벨(t_score/F-Score …) 사용자 노출 금지
# (feedback_production_answer_brevity). 렌더 순서 = 이 dict 순서.
_SCORE_KR = {
    "t_score": "타점",
    "buy_score": "매수",
    "f_score": "수급",
    "s_score": "주도주",
}

_NO_NAME = "이름 미상"

# 사유 문장 안에 새어나오는 내부 용어 → 한국어. 사유는 전략가 LLM 이 쓴 자유 텍스트라
# 우리가 주입한 md 의 코드 용어(AlphaPosture·kill switch·regime 코드·*_score)를 그대로
# 따라 적는다. 사용자 노출 단에서는 코드 라벨을 쓰지 않는다
# (feedback_production_answer_brevity / feedback_term_accuracy).
# **순서 의존**: 점수 라벨(buy_score)을 verdict(buy)보다 먼저 치환해야 깨지지 않는다.
_TERM_SUBS: list[tuple[re.Pattern[str], str]] = [
    # 이미 한국어 병기가 있으면 영문 괄호만 제거 — "분산일(Distribution Day) 7건" → "분산일 7건"
    (re.compile(r"\s*\(\s*Distribution Day\s*\)"), ""),
    (re.compile(r"Distribution\s+Day", re.IGNORECASE), "분산일"),
    (re.compile(r"kill[\s_-]?switch", re.IGNORECASE), "강제 차단"),
    (re.compile(r"AlphaPosture"), "시장 진입 판단"),
    (re.compile(r"\bt[_-]?score\b", re.IGNORECASE), "타점 점수"),
    (re.compile(r"\bbuy[_-]?score\b", re.IGNORECASE), "매수 점수"),
    (re.compile(r"\bf[_-]?score\b", re.IGNORECASE), "수급 점수"),
    (re.compile(r"\bs[_-]?score\b", re.IGNORECASE), "주도주 점수"),
    (re.compile(r"\bregime\b", re.IGNORECASE), "시장 체제"),
    (re.compile(r"\bbreadth\b", re.IGNORECASE), "상승종목 비율"),
]


def _humanize(text: str) -> str:
    """사유·조건 문장의 내부 용어를 한국어로. 값(숫자)은 건드리지 않는다."""
    out = text
    for pattern, repl in _TERM_SUBS:
        out = pattern.sub(repl, out)
    for code, kr in REGIME_KR.items():          # moderate_bear → 약세
        out = re.sub(rf"\b{code}\b", kr, out)
    for code, kr in _VERDICT_KR.items():        # wait → 관망 (점수 라벨 치환 뒤라 안전)
        out = re.sub(rf"\b{code}\b", kr, out)
    return out


def _name(row: dict[str, Any]) -> str:
    """종목명 — 없으면 '이름 미상'. **종목코드는 절대 폴백으로 쓰지 않는다**
    (feedback_no_stock_code_in_display: 사람이 보는 출력에 코드 금지)."""
    return str(row.get("display_name") or "").strip() or _NO_NAME


def _head(row: dict[str, Any]) -> str:
    """`▪ <b>종목명</b> [트랙]` 공통 머리."""
    track = _TRACK_SHORT.get(row.get("track", ""), row.get("track", ""))
    return f"▪ <b>{_name(row)}</b> [{track}]"


def _won(v: Any) -> str:
    return f"{float(v):,.0f}"


def _score_line(row: dict[str, Any]) -> str | None:
    """`타점 5.5 · 매수 6.0 · 수급 4.0 · 주도주 6.2` — 값 없는 항목만 생략."""
    scores = row.get("scores") or {}
    parts = [
        f"{label} {float(scores[key]):.1f}"
        for key, label in _SCORE_KR.items()
        if isinstance(scores.get(key), (int, float))
    ]
    return " · ".join(parts) if parts else None


def _conditional_line(row: dict[str, Any]) -> str | None:
    """진입 조건 — 가격대(진입존)가 있으면 가격대, 없으면 조건 문장, 둘 다 없으면 생략."""
    ce = row.get("conditional_entry") or {}
    if not isinstance(ce, dict):
        return None
    zone = ce.get("entry_zone") or []
    if isinstance(zone, (list, tuple)) and len(zone) >= 2:
        return f"→ {_won(zone[0])}~{_won(zone[1])} 눌림 시 진입 검토"
    note = str(ce.get("note") or "").strip()
    return f"→ {_humanize(note)}" if note else None


def _trade_plan_line(row: dict[str, Any]) -> str | None:
    """`진입 71,000 · 손절 66,000 · 목표 78,000/84,000/92,000`."""
    parts: list[str] = []
    if row.get("entry_price") is not None:
        parts.append(f"진입 {_won(row['entry_price'])}")
    if row.get("stop_loss") is not None:
        parts.append(f"손절 {_won(row['stop_loss'])}")
    targets = [t for t in (row.get("target_prices") or []) if t is not None]
    if targets:
        parts.append("목표 " + "/".join(_won(t) for t in targets))
    return " · ".join(parts) if parts else None


def _detail_block(row: dict[str, Any], *, with_stage: bool) -> list[str]:
    """종목 1건 상세 블록 — 머리줄 + (플랜) + 점수 + 사유 + 진입 조건."""
    verdict = _VERDICT_KR.get(row.get("verdict", ""), "관망")
    head = f"{_head(row)} {verdict}"
    if with_stage:
        stage = _STAGE_KR.get(row.get("funnel_stage", ""))
        if stage:
            head += f" · {stage}"
    confidence = row.get("confidence")
    if isinstance(confidence, (int, float)) and confidence:
        head += f" (신뢰 {int(confidence)})"

    lines = [head]
    for line in (_trade_plan_line(row), _score_line(row)):
        if line:
            lines.append(f"  {line}")
    reason = str(row.get("headline_reason") or "").strip()
    if reason:
        lines.append(f"  {_humanize(reason)}")
    cond = _conditional_line(row)
    if cond:
        lines.append(f"  {cond}")
    return lines


# --- 실패 사유 → 한국어 ------------------------------------------------------

_FAILURE_KR: dict[str, str] = {
    "no_yaml": "전략가가 권고 형식을 못 냈음 (재시도 후 실패)",
    "bad_track": "트랙 설정 오류",
}


def _failure_kr(reason: str) -> str:
    """실패 사유 한국어화. 원문은 알 수 없는 경우에만 짧게 남겨 디버깅 가능성 보존."""
    from core.signal.auto_signal import _is_transient  # 패턴 재정의 금지 — 단일 출처

    r = (reason or "").strip()
    if r in _FAILURE_KR:
        return _FAILURE_KR[r]
    if r.startswith("scorecard:"):
        return "점수표 계산 실패 — 지표 수집 오류"
    if _is_transient(r):
        return "전략가 응답 실패 — 일시적 (서버 과부하·타임아웃)"
    return f"권고 미발행 — {r[:60]}" if r else "권고 미발행"


# --- 헤더 --------------------------------------------------------------------


def _market_header(summary: dict[str, Any]) -> str:
    regime = summary.get("regime")
    posture = summary.get("entry_posture")
    regime_txt = f"{REGIME_KR.get(regime, regime)}({regime})" if regime else "미상"
    posture_txt = POSTURE_KR.get(posture, posture) if posture else "미상"
    return f"시장 체제: {regime_txt} · 진입 자세: {posture_txt}"


def _zero_signal_reason(summary: dict[str, Any]) -> str | None:
    """매수·매도 0 인 이유 — 결정론 근거가 있을 때만. 없으면 문장을 지어내지 않는다."""
    dd = summary.get("distribution_day_count")
    kill = summary.get("kill_switch_dd")
    if isinstance(dd, (int, float)) and isinstance(kill, (int, float)) and dd >= kill:
        return f"분산일 {int(dd)}건(임계 {int(kill)}) — 신규 진입 차단 국면"
    if summary.get("entry_posture") == "defensive":
        return "시장 방어 태세 — 신규 진입 보수적"
    return None


# --- 본체 --------------------------------------------------------------------


def render_daily_digest(summary: dict[str, Any]) -> str:
    """summary dict → 알림 본문. 순수 함수.

    불변식: 매수+매도+지켜볼+변화없음+미산출 = 평가 총건수 (푸터와 대조 가능).
    """
    results: list[dict[str, Any]] = list(summary.get("results") or [])
    persisted = [r for r in results if r.get("persisted")]
    buys = [r for r in persisted if r.get("verdict") == "buy"]
    sells = [r for r in persisted if r.get("verdict") == "sell"]
    watch = [r for r in persisted if r.get("verdict") not in ("buy", "sell")]
    unchanged = [r for r in results if not r.get("persisted") and r.get("skipped")]
    failed = [r for r in results if not r.get("persisted") and not r.get("skipped")]

    out: list[str] = [_market_header(summary)]
    if not results:
        out.append("")
        out.append("평가한 종목이 없습니다 — 스크리닝 통과 종목 0.")
        return "\n".join(out)

    # 매수 / 매도 — 0 건이어도 표시 ("신규 진입 없음" 자체가 정보).
    out.append("")
    headline = f"■ 매수 {len(buys)} · 매도 {len(sells)}"
    if not buys and not sells:
        headline += " — 신규 진입 없음"
    out.append(headline)
    if not buys and not sells:
        reason = _zero_signal_reason(summary)
        if reason:
            out.append(reason)
    for row in buys + sells:
        out.append("")
        out.extend(_detail_block(row, with_stage=False))

    # 지켜볼 종목 (관망) — 단계·점수·사유·진입 조건.
    if watch:
        out.append("")
        out.append(f"■ 지켜볼 종목 {len(watch)}")
        for row in watch:
            out.append("")
            out.extend(_detail_block(row, with_stage=True))

    # 변화 없음 — 밴드 게이트로 전략가 호출을 아낀 것. 판단 실종이 아니라 직전 판단 유효.
    if unchanged:
        out.append("")
        out.append(f"■ 변화 없음 {len(unchanged)} (직전 판단 유지)")
        for row in unchanged:
            prev = _VERDICT_KR.get(row.get("prev_verdict", ""))
            state = f"{prev} 유지" if prev else "직전 판단 유지"
            out.append(f"{_head(row)} {state} — 점수대 동일")

    # 미산출 — 조용한 실패를 숨기지 않는다 (SPEC §1-c).
    if failed:
        out.append("")
        out.append(f"⚠ 미산출 {len(failed)}")
        for row in failed:
            out.append(f"{_head(row)} — {_failure_kr(str(row.get('reason') or ''))}")

    out.append("")
    tracks = len({r.get("track") for r in results if r.get("track")}) or 1
    out.append(
        f"관심종목 {summary.get('screened', 0)}종 × {tracks}트랙 = {len(results)}건 평가."
    )
    return "\n".join(out)
