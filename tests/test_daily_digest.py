"""일일 요약 알림 렌더러 테스트 (AUTO-SIGNAL-DIGEST-001).

순수 함수라 fixture dict 만으로 전건 커버 — 외부 호출·DB·LLM 0.
"""
from __future__ import annotations

import re
from typing import Any

from core.signal.daily_digest import render_daily_digest


def _persisted(
    ticker: str,
    name: str,
    track: str = "B",
    verdict: str = "wait",
    **kw: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ticker": ticker, "track": track, "verdict": verdict, "persisted": True,
        "display_name": name, "confidence": 70,
        "headline_reason": "수급 약함, 거래량 0.91배로 트리거 미발동",
        "funnel_stage": "watching",
        "conditional_entry": {"note": "시장 위험 해소 후 재평가", "entry_zone": []},
        "scores": {"t_score": 5.5, "buy_score": 6.0, "f_score": 4.0, "s_score": 6.2},
        "entry_price": None, "stop_loss": None, "target_prices": [],
    }
    row.update(kw)
    return row


def _skipped(ticker: str, name: str, track: str = "B", prev: str = "wait") -> dict[str, Any]:
    return {
        "ticker": ticker, "track": track, "persisted": False, "skipped": True,
        "reason": "band_unchanged", "display_name": name, "prev_verdict": prev,
    }


def _failed(ticker: str, name: str, track: str = "A", reason: str = "no_yaml") -> dict[str, Any]:
    return {
        "ticker": ticker, "track": track, "persisted": False,
        "reason": reason, "display_name": name,
    }


def _summary(results: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    s: dict[str, Any] = {
        "cadence": "postclose", "as_of": "2026-08-10", "regime": "moderate_bear",
        "entry_posture": "defensive", "distribution_day_count": 7, "kill_switch_dd": 4,
        "watchlist": 50, "screened": len({r["ticker"] for r in results}),
        "evaluated": len(results), "results": results,
    }
    s.update(kw)
    return s


# --- 1. 매수 전건 상세 ------------------------------------------------------


def test_buy_row_renders_full_trade_plan() -> None:
    """매수는 진입·손절·목표를 전부 노출한다 (사용자가 바로 행동할 수 있게)."""
    body = render_daily_digest(_summary([
        _persisted("005930", "삼성전자", track="A", verdict="buy", confidence=78,
                   entry_price=71000, stop_loss=66000,
                   target_prices=[78000, 84000, 92000],
                   headline_reason="외인 순매수 전환 + 20일선 지지 확인"),
    ]))
    assert "삼성전자" in body
    assert "[중장기]" in body
    assert "매수" in body
    assert "진입 71,000" in body
    assert "손절 66,000" in body
    assert "78,000/84,000/92,000" in body
    assert "외인 순매수 전환 + 20일선 지지 확인" in body
    assert "신뢰 78" in body


def test_sell_row_is_rendered_in_its_own_bucket() -> None:
    body = render_daily_digest(_summary([
        _persisted("035420", "NAVER", verdict="sell", headline_reason="추세 이탈"),
    ]))
    assert "매도 1" in body
    assert "NAVER" in body
    assert "추세 이탈" in body


# --- 2. 매수·매도 0 일 때 "왜 0인지" 한 줄 ---------------------------------


def test_zero_signal_line_cites_distribution_day_kill_switch() -> None:
    body = render_daily_digest(_summary([_persisted("086790", "하나금융지주")]))
    assert "매수 0 · 매도 0" in body
    assert "신규 진입 없음" in body
    assert "분산일 7건(임계 4)" in body


def test_zero_signal_line_falls_back_to_defensive_posture() -> None:
    """분산일이 임계 미만이면 방어 태세를 사유로 쓴다."""
    body = render_daily_digest(_summary(
        [_persisted("086790", "하나금융지주")], distribution_day_count=1,
    ))
    assert "분산일" not in body
    assert "시장 방어 태세" in body


def test_zero_signal_line_omitted_when_no_deterministic_ground() -> None:
    """근거가 없으면 사유 문장을 지어내지 않는다 (투자 7계명 #6)."""
    body = render_daily_digest(_summary(
        [_persisted("086790", "하나금융지주")],
        distribution_day_count=1, entry_posture="neutral",
    ))
    assert "분산일" not in body
    assert "방어 태세" not in body
    assert "매수 0 · 매도 0" in body


# --- 3. 점수 줄 — None 항목만 생략 -----------------------------------------


def test_score_line_skips_none_entries_and_uses_korean_labels() -> None:
    body = render_daily_digest(_summary([
        _persisted("080220", "제주반도체",
                   scores={"t_score": 6.0, "buy_score": 5.5, "f_score": 5.0, "s_score": None}),
    ]))
    assert "타점 6.0" in body
    assert "매수 5.5" in body
    assert "수급 5.0" in body
    assert "주도주" not in body
    # 코드 라벨은 사용자 노출 금지
    for label in ("t_score", "buy_score", "f_score", "s_score", "F-Score", "S-Score"):
        assert label not in body


def test_score_line_omitted_when_all_scores_missing() -> None:
    body = render_daily_digest(_summary([
        _persisted("080220", "제주반도체", scores={}),
    ]))
    assert "제주반도체" in body
    assert "타점" not in body


# --- 4. 진입 조건 3분기 -----------------------------------------------------


def test_conditional_entry_zone_renders_price_range() -> None:
    body = render_daily_digest(_summary([
        _persisted("086790", "하나금융지주",
                   conditional_entry={"note": "눌림 대기", "entry_zone": [12300, 12800]}),
    ]))
    assert "12,300~12,800" in body


def test_conditional_entry_falls_back_to_note() -> None:
    body = render_daily_digest(_summary([
        _persisted("086790", "하나금융지주",
                   conditional_entry={"note": "시장 위험 해소 후 재평가", "entry_zone": []}),
    ]))
    assert "시장 위험 해소 후 재평가" in body


def test_conditional_entry_line_omitted_when_empty() -> None:
    body = render_daily_digest(_summary([
        _persisted("086790", "하나금융지주", conditional_entry=None),
    ]))
    assert "하나금융지주" in body
    assert "→" not in body


# --- 5. 변화 없음 = 직전 판단 유지 (밴드 스킵 착시 해소) -------------------


def test_band_skipped_bucket_shows_carried_over_verdict() -> None:
    body = render_daily_digest(_summary([
        _skipped("035420", "NAVER", prev="wait"),
        _skipped("005930", "삼성전자", prev="buy"),
    ]))
    assert "변화 없음 2" in body
    assert "직전 판단 유지" in body
    assert "NAVER" in body
    assert "관망 유지" in body
    assert "매수 유지" in body
    # "밴드 스킵" 이라는 내부 용어는 사용자에게 노출하지 않는다
    assert "밴드 스킵" not in body


def test_band_skipped_without_prev_verdict_is_graceful() -> None:
    row = _skipped("035420", "NAVER")
    del row["prev_verdict"]
    body = render_daily_digest(_summary([row]))
    assert "NAVER" in body
    assert "변화 없음 1" in body


# --- 6. 미산출 버킷 + 실패 사유 사전 ---------------------------------------


def test_failure_bucket_exists_and_maps_reasons_to_korean() -> None:
    body = render_daily_digest(_summary([
        _failed("086790", "하나금융지주", reason="no_yaml"),
        _failed("055550", "신한지주", reason="503 Service Unavailable"),
        _failed("035420", "NAVER", reason="scorecard:KeyError"),
        _failed("005930", "삼성전자", reason="bad_track"),
        _failed("000660", "SK하이닉스", reason="뭔가 알 수 없는 오류"),
    ]))
    assert "미산출 5" in body
    assert "전략가가 권고 형식을 못 냈음" in body
    assert "일시적" in body
    assert "점수표 계산 실패" in body
    assert "트랙 설정 오류" in body
    assert "권고 미발행" in body
    assert "뭔가 알 수 없는 오류" in body  # 원문 보존 (디버깅)


def test_failure_bucket_omitted_when_no_failures() -> None:
    body = render_daily_digest(_summary([_persisted("086790", "하나금융지주")]))
    assert "미산출" not in body


# --- 7. 종목코드 미노출 (feedback_no_stock_code_in_display 회귀 방지) -------


def test_no_stock_code_leaks_into_body() -> None:
    body = render_daily_digest(_summary([
        _persisted("005930", "삼성전자", track="A", verdict="buy",
                   entry_price=71000, stop_loss=66000, target_prices=[78000]),
        _persisted("086790", "하나금융지주"),
        _skipped("035420", "NAVER"),
        _failed("055550", "신한지주"),
    ]))
    for ticker in ("005930", "086790", "035420", "055550"):
        assert ticker not in body


def test_display_name_falls_back_without_leaking_code() -> None:
    """이름 해석 실패 시에도 코드를 노출하지 않는다."""
    row = _persisted("123456", "")
    body = render_daily_digest(_summary([row]))
    assert "123456" not in body
    assert "이름 미상" in body


# --- 8. 빈 입력 graceful ----------------------------------------------------


def test_empty_summary_is_graceful() -> None:
    body = render_daily_digest(_summary([], screened=0))
    assert body
    assert "평가한 종목이 없습니다" in body


def test_all_failed_summary_still_reports_totals() -> None:
    body = render_daily_digest(_summary([
        _failed("086790", "하나금융지주"), _failed("055550", "신한지주"),
    ]))
    assert "미산출 2" in body
    assert "매수 0 · 매도 0" in body


def test_missing_market_context_keys_are_graceful() -> None:
    """regime·posture 미상이어도 크래시 없이 렌더."""
    s = _summary([_persisted("086790", "하나금융지주")])
    for k in ("regime", "entry_posture", "distribution_day_count", "kill_switch_dd"):
        del s[k]
    body = render_daily_digest(s)
    assert "미상" in body
    assert "하나금융지주" in body


# --- 서식/정합 --------------------------------------------------------------


def test_footer_totals_reconcile_with_buckets() -> None:
    """버킷 합 = 평가 총건수. 남는 건이 숨지 않는다 (SPEC §7)."""
    results = [
        _persisted("005930", "삼성전자", track="A", verdict="buy"),
        _persisted("086790", "하나금융지주", track="B"),
        _skipped("035420", "NAVER", track="B"),
        _failed("055550", "신한지주", track="A"),
    ]
    body = render_daily_digest(_summary(results))
    assert "4건 평가" in body
    assert "2트랙" in body
    # 버킷 헤더(■/⚠ 로 시작하는 줄)의 숫자만 합산 — 상세 줄의 점수·가격과 섞이지 않게.
    headers = [ln for ln in body.split("\n") if ln.startswith(("■", "⚠"))]
    counts = [int(n) for ln in headers for n in re.findall(r"(\d+)", ln)]
    assert sum(counts) == 4


def test_stock_names_are_bolded_for_telegram() -> None:
    body = render_daily_digest(_summary([_persisted("086790", "하나금융지주")]))
    assert "<b>하나금융지주</b>" in body
    # 알림 서비스의 줄 경계 4096 분할이 태그를 깨지 않으려면 태그가 한 줄 안에 닫혀야 함
    for line in body.split("\n"):
        assert line.count("<b>") == line.count("</b>")


def test_funnel_stage_label_is_korean() -> None:
    body = render_daily_digest(_summary([
        _persisted("086790", "하나금융지주", funnel_stage="watching"),
        _persisted("055550", "신한지주", funnel_stage="interest"),
    ]))
    assert "매수대기" in body
    assert "관심" in body
    assert "watching" not in body
    assert "interest" not in body


# --- 9. 사유 문장의 내부 용어 한국어화 -------------------------------------


def test_reason_internal_terms_are_humanized() -> None:
    """전략가가 사유에 그대로 옮겨 적은 코드 용어를 사용자 노출 단에서 번역."""
    body = render_daily_digest(_summary([
        _persisted("086790", "하나금융지주", headline_reason=(
            "AlphaPosture 후보=wait — 25일 분산일(Distribution Day) 7건, "
            "kill switch 임계(4건) 초과. 시장 체제 moderate_bear, breadth 0.79, "
            "buy_score=6.0 / t_score=5.5"
        )),
    ]))
    # 헤더의 `약세(moderate_bear)` 병기는 의도된 설계 — 사유 줄만 검사한다.
    reason_line = next(ln for ln in body.split("\n") if "시장 진입 판단" in ln)
    for code in ("AlphaPosture", "Distribution Day", "kill switch", "moderate_bear",
                 "breadth", "buy_score", "t_score"):
        assert code not in reason_line
    assert "시장 진입 판단 후보=관망" in body
    assert "25일 분산일 7건" in body
    assert "강제 차단 임계(4건)" in body
    assert "시장 체제 약세" in body
    assert "상승종목 비율 0.79" in body
    assert "매수 점수=6.0" in body
    assert "타점 점수=5.5" in body
    # 수치는 그대로 보존
    assert "7건" in body and "0.79" in body


def test_conditional_note_is_humanized() -> None:
    body = render_daily_digest(_summary([
        _persisted("086790", "하나금융지주",
                   conditional_entry={"note": "kill switch 해제 후 재평가", "entry_zone": []}),
    ]))
    assert "kill switch" not in body
    assert "강제 차단 해제 후 재평가" in body


def test_humanize_leaves_plain_korean_untouched() -> None:
    reason = "외국인 순매수 전환 + 20일선 지지 확인, 거래량 1.8배"
    body = render_daily_digest(_summary([
        _persisted("005930", "삼성전자", headline_reason=reason),
    ]))
    assert reason in body
