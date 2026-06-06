"""ANSWER-FIDELITY-001 (LB-MS1) — 답변 누수 봉합 테스트.

F1 echo 차단(raw/코드라벨/잘림) + F2 근거축 가변 + scrub 커버리지.
format_answer 통합은 call_llm mock (실 API 금지, CLAUDE.md 테스트 안전).
"""
from __future__ import annotations

import pytest

import core.intent.formatter as fmt_mod
from core.intent.formatter import (
    _formatter_system,
    _looks_like_echo,
    _strip_echo,
    format_answer,
    scrub_code_labels,
    select_evidence_axes,
)


@pytest.fixture(autouse=True)
def _fresh_caches():
    fmt_mod.reload_label_dictionary()
    yield
    fmt_mod.reload_label_dictionary()


# ============================================================
# F2 — 근거축 가변 (select_evidence_axes)
# ============================================================


def test_axes_ticker_present_default():
    axes = select_evidence_axes(route="both", scenario_id=2, ticker="005930")
    assert axes == ["수급", "차트", "실적"]


def test_axes_market_scenario_no_ticker():
    axes = select_evidence_axes(route="analyst_direct", scenario_id=3, ticker=None)
    assert axes == ["시장 국면", "시장 폭", "거시 지표"]


def test_axes_non_market_no_ticker_falls_back_default():
    axes = select_evidence_axes(route="both", scenario_id=2, ticker=None)
    assert axes == ["수급", "차트", "실적"]


def test_formatter_system_injects_axes_and_antiecho():
    sys = _formatter_system(["시장 국면", "거시 지표"])
    assert "[시장 국면]" in sys
    assert "[거시 지표]" in sys
    assert "수급" not in sys.split("## 출력 양식")[1].split("## 절대 규칙")[0]  # 고정 3요소 미주입
    assert "재출력 금지" in sys  # anti-echo 규칙
    assert "빈 축은 생략" in sys  # 정보부족 3줄 방지


# ============================================================
# F1 — echo 탐지 / 최후 정리
# ============================================================


def test_looks_like_echo_detects_compose_headers():
    assert _looks_like_echo("## 사용자 발화\n삼성전자랑 ...") is True
    assert _looks_like_echo("### stock_picker\n주도주 점수=7.0 ...") is True
    assert _looks_like_echo("지금은 보류 권고예요\n\n근거:\n- 외국인 매도세") is False
    assert _looks_like_echo("") is False


def test_strip_echo_removes_headers_and_labels():
    raw = (
        "## 사용자 발화\n삼성전자랑 하이닉스\n\n"
        "## 분석가 raw 응답 (prefetch 동시 호출)\n\n"
        "### stock_picker\n"
        "*   주도주 점수=7.0 입니다\n"
        "SK하이닉스는 시장 대비 강한 흐름을 보입니다.\n"
    )
    out = _strip_echo(raw)
    assert "## 사용자 발화" not in out
    assert "## 분석가 raw" not in out
    assert "### stock_picker" not in out
    assert "점수=" not in out
    assert "시장 대비 강한 흐름" in out


# ============================================================
# scrub 커버리지 (#4 누출 라벨)
# ============================================================


@pytest.mark.parametrize(
    "code,expected",
    [
        ("leader", "주도주"),
        ("buy_candidate", "매수 후보"),
        ("moderate_bull", "완만한 상승장"),
        ("supply_chain", "수급망 일치도"),
        ("alignment", "정배열"),
        ("CAN SLIM", "성장주 기준"),
    ],
)
def test_scrub_covers_leaked_labels(code, expected):
    assert expected in scrub_code_labels(f"종합 판단: {code} 입니다")


# ============================================================
# format_answer 통합 (call_llm mock)
# ============================================================


def _resp(content: str) -> dict:
    return {"content": content, "model": "gemini-x", "tokens_in": 1,
            "tokens_out": 1, "cost_usd": 0.0, "raw": {}}


@pytest.mark.asyncio
async def test_format_answer_echo_triggers_retry(monkeypatch):
    """1차 echo → 강제 재시도 → 2차 clean 채택, raw 마커 0."""
    calls: list[str] = []

    async def fake_call_llm(*, system, messages, model, **kw):
        calls.append(messages[-1]["content"])
        if len(calls) == 1:
            return _resp("## 분석가 raw 응답\n### stock_picker\n주도주 점수=7.0 ...")
        return _resp("지금은 SK하이닉스가 더 나아 보여요.\n\n근거:\n- 시장 대비 강해요")

    monkeypatch.setattr(fmt_mod, "call_llm", fake_call_llm)
    analysts = [{"id": "stock_picker", "text": "raw 비교 ...", "metadata": {}}]
    res = await format_answer("삼성 vs 하이닉스", analysts, [], provider="gemini",
                              route="analyst_direct", scenario_id=4, ticker="000660")
    assert len(calls) == 2  # 재시도 발생
    assert not _looks_like_echo(res.text)
    assert "## 분석가 raw" not in res.text


@pytest.mark.asyncio
async def test_format_answer_echo_both_fail_strips(monkeypatch):
    """재시도도 echo → _strip_echo 최후 정리로 raw 헤더 제거."""
    async def fake_call_llm(*, system, messages, model, **kw):
        return _resp("## 사용자 발화\n질문\n### stock_picker\n주도주 점수=9 강한 흐름입니다")

    monkeypatch.setattr(fmt_mod, "call_llm", fake_call_llm)
    analysts = [{"id": "stock_picker", "text": "raw ...", "metadata": {}}]
    res = await format_answer("비교", analysts, [], provider="gemini",
                              route="analyst_direct", scenario_id=4, ticker="000660")
    assert "## 사용자 발화" not in res.text
    assert "### stock_picker" not in res.text
    assert "점수=" not in res.text


@pytest.mark.asyncio
async def test_format_answer_market_query_uses_macro_axes(monkeypatch):
    """시장 질의(ticker None, scenario 3) → system 에 시장 국면/거시 축, 수급/차트/실적 고정 아님."""
    captured: dict = {}

    async def fake_call_llm(*, system, messages, model, **kw):
        captured["system"] = " ".join(b["text"] for b in system)
        return _resp("시장은 보수적으로 봐요.\n\n근거:\n- 약세 신호 누적")

    monkeypatch.setattr(fmt_mod, "call_llm", fake_call_llm)
    analysts = [{"id": "market_state_analyzer", "text": "raw 시장 ...", "metadata": {}}]
    await format_answer("지금 시장 어때?", analysts, [], provider="gemini",
                        route="analyst_direct", scenario_id=3, ticker=None)
    assert "[시장 국면]" in captured["system"]
    assert "[거시 지표]" in captured["system"]


# ============================================================
# F3 — 비교 양종목 (classifier 2종목 추출 + 라우터 양종목 호출)
# ============================================================


def test_extract_tickers_two_in_order():
    from core.intent.classifier import _extract_tickers_from_text

    out = _extract_tickers_from_text("삼성전자랑 SK하이닉스 중에 뭐가 나아?", limit=2)
    tickers = [t for t, _ in out]
    assert tickers == ["005930", "000660"]  # 등장 순서


def test_extract_tickers_dedup_and_overlap():
    from core.intent.classifier import _extract_tickers_from_text

    # 같은 종목 반복 → 1회 / 부분문자열(삼성 ⊂ 삼성전자) 중복 없음
    out = _extract_tickers_from_text("삼성전자 삼성전자 좋아?", limit=3)
    assert [t for t, _ in out] == ["005930"]


@pytest.mark.asyncio
async def test_router_comparison_prefetches_both_tickers(monkeypatch):
    import core.intent.router as rt
    from core.intent.classifier import IntentClassification

    seen: list[tuple[str, str | None]] = []

    async def fake_call(aid, messages, *, target_ticker, provider):
        seen.append((aid, target_ticker))
        return {"kind": "analyst", "id": aid, "target": target_ticker, "text": "ok", "metadata": {}}

    monkeypatch.setattr(rt, "_call_analyst_safe", fake_call)

    cls = IntentClassification(
        scenario_id=4, ticker="000660", ticker_display="SK하이닉스",
        agent_route="analyst_direct", analyst_ids=["stock_picker", "market_state_analyzer"],
        confidence=0.9, manual_fallback_required=False, stage="llm", latency_ms=0,
        raw_input="삼성 vs 하이닉스", reasoning="",
        secondary_ticker="005930", secondary_ticker_display="삼성전자",
    )
    await rt.route_intent(cls, [{"role": "user", "content": "삼성 vs 하이닉스"}], provider="mock")

    # stock_picker 는 양 종목(000660+005930), market_state_analyzer 는 1회만
    assert ("stock_picker", "000660") in seen
    assert ("stock_picker", "005930") in seen
    assert seen.count(("market_state_analyzer", "000660")) == 1
    assert ("market_state_analyzer", "005930") not in seen
