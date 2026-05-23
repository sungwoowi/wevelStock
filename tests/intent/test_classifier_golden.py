"""PRODUCTION-UX-001 — Intent Classifier 골든 eval.

시나리오 1~5 × 9건 = **45 골든 케이스**. PROD-UX-1 v1 시연 인수 기준:
  - 정확도 (scenario·route 모두 일치) ≥ 85%
  - Stage 1 hit ≥ 40%

발화 다양성: 키워드만 / 격식체 / 반말 / 줄임말 / 종목명 포함 / 종목명 영문 / 오타 /
공백 변형 / 명시 단축어.

본 테스트는 **Stage 1 결정론** 만 활성 (skip_stage2=True). Stage 2 LLM
정합성은 별도 통합 테스트 (`test_classifier_stage2.py` — 후속 PROD-UX-2 에서
mock provider 로 검증).
"""
from __future__ import annotations

import asyncio
import os

import pytest

os.environ.setdefault("TESTING", "1")

from core.intent.classifier import (
    IntentClassification,
    classify_intent,
    reload_keywords,
)


# ---------------------------------------------------------------------------
# 골든 셋 — (input, expected_scenario_id, expected_agent_route)
# ticker 필요 여부는 시나리오에 따라 (1·2·6·7·8 = ticker 권장).
# ---------------------------------------------------------------------------

GOLDEN_CASES: list[tuple[str, int, str]] = [
    # ──────────────────────────── Scenario 1: 보유 (track_a) ────────────────────────────
    ("삼성전자 들고 있는데 어떻게 해", 1, "track_a"),
    ("SK하이닉스 보유 중인데", 1, "track_a"),
    ("기아 갖고 있어요", 1, "track_a"),
    ("LG에너지솔루션 가지고 있는데 ", 1, "track_a"),
    ("카카오 물려서 답답해", 1, "track_a"),
    ("내 종목 어떻게 해야 돼", 1, "track_a"),
    ("내가 산 NAVER 어떡하지", 1, "track_a"),
    ("삼성바이오로직스 샀는데 빠지네", 1, "track_a"),
    ("현대차 들고 있" , 1, "track_a"),
    # ──────────────────────────── Scenario 2: 진입 (both) ────────────────────────────
    ("삼성전자 살까?", 2, "both"),
    ("지금 SK하이닉스 사도 돼?", 2, "both"),
    ("카카오 들어가도 될까", 2, "both"),
    ("LG화학 진입 타이밍?", 2, "both"),
    ("현대모비스 매수 타이밍 어때", 2, "both"),
    ("기아 신규 진입 괜찮?", 2, "both"),
    ("지금 들어가도 돼", 2, "both"),
    ("네이버 매수해도 좋을까", 2, "both"),
    ("LG에너지솔루션 사도 될까", 2, "both"),
    # ──────────────────────────── Scenario 3: 시장 판단 (analyst_direct) ────────────────────────────
    ("지금 시장 어때", 3, "analyst_direct"),
    ("시장이 어때요", 3, "analyst_direct"),
    ("오늘 장 어때", 3, "analyst_direct"),
    ("장이 어때 오늘", 3, "analyst_direct"),
    ("코스피 분위기 어때", 3, "analyst_direct"),
    ("시장 분위기 좀", 3, "analyst_direct"),
    ("장세가 어떤지 봐줘", 3, "analyst_direct"),
    ("불장이야 횡보야", 3, "analyst_direct"),
    ("지수 어떻게 되고 있어", 3, "analyst_direct"),
    # ──────────────────────────── Scenario 4: 섹터 선택 (analyst_direct) ────────────────────────────
    ("어떤 섹터 강해", 4, "analyst_direct"),
    ("강한 섹터 추천해줘", 4, "analyst_direct"),
    ("섹터 추천 부탁해", 4, "analyst_direct"),
    ("섹터 top 3 알려줘", 4, "analyst_direct"),
    ("주도 섹터가 뭐야", 4, "analyst_direct"),
    ("어느 업종 강해 지금", 4, "analyst_direct"),
    ("강한 업종 보여줘", 4, "analyst_direct"),
    ("어떤 섹터 들어가야 해", 4, "analyst_direct"),
    ("강한 섹터 top", 4, "analyst_direct"),
    # ──────────────────────────── Scenario 5: 주도주 진입 (both) ────────────────────────────
    ("지금 뭐 사?", 5, "both"),
    ("뭐 살까 오늘", 5, "both"),
    ("뭐가 좋아 지금", 5, "both"),
    ("주도주 추천", 5, "both"),
    ("지금 사면 좋은 거 있어?", 5, "both"),
    ("뭐 추천해줘", 5, "both"),
    ("추천 종목 좀", 5, "both"),
    ("오늘 뭐 들어가지", 5, "both"),
    ("뭐 사야 돼 지금", 5, "both"),
]


@pytest.fixture(autouse=True)
def _reload_keywords_before_each():
    """yaml hot-reload 안전 — 매 테스트마다 캐시 클리어."""
    reload_keywords()
    yield
    reload_keywords()


def _classify_sync(text: str) -> IntentClassification:
    """async classify_intent 를 동기 wrap (Stage 1 만 = LLM 호출 없음)."""
    return asyncio.run(classify_intent(text, skip_stage2=True))


class TestGoldenAccuracy:
    """45 골든 케이스 전체 정확도 — scenario·route 모두 일치해야 통과."""

    def test_full_accuracy_meets_threshold(self) -> None:
        """전체 45건 정확도 ≥ 85% (38건 이상 정답)."""
        correct = 0
        wrong: list[tuple[str, int, str, IntentClassification]] = []
        for text, expected_scenario, expected_route in GOLDEN_CASES:
            result = _classify_sync(text)
            ok = (
                result.scenario_id == expected_scenario
                and result.agent_route == expected_route
            )
            if ok:
                correct += 1
            else:
                wrong.append((text, expected_scenario, expected_route, result))

        total = len(GOLDEN_CASES)
        accuracy = correct / total
        assert accuracy >= 0.85, (
            f"Golden accuracy {accuracy:.1%} < 85%. "
            f"{len(wrong)}/{total} wrong:\n"
            + "\n".join(
                f"  - {t!r} expected=({es},{er}) got=({r.scenario_id},{r.agent_route} conf={r.confidence})"
                for t, es, er, r in wrong[:5]
            )
        )

    def test_stage1_hit_rate_meets_threshold(self) -> None:
        """Stage 1 (결정론) hit 비율 ≥ 40%. 모두 deterministic 으로 잡혀야."""
        stage1_hits = 0
        for text, _es, _er in GOLDEN_CASES:
            result = _classify_sync(text)
            if result.stage == "deterministic":
                stage1_hits += 1
        hit_rate = stage1_hits / len(GOLDEN_CASES)
        assert hit_rate >= 0.40, (
            f"Stage 1 hit rate {hit_rate:.1%} < 40% — keyword 룰 보강 필요"
        )


class TestPerScenarioAccuracy:
    """시나리오별 정확도 — 각 시나리오 9건 중 7건 이상 (≥ 77%) 정답."""

    @pytest.mark.parametrize("scenario_id", [1, 2, 3, 4, 5])
    def test_per_scenario_min_accuracy(self, scenario_id: int) -> None:
        cases = [c for c in GOLDEN_CASES if c[1] == scenario_id]
        assert len(cases) == 9, f"scenario {scenario_id} 케이스 = 9 (실제 {len(cases)})"
        correct = sum(
            1
            for text, es, er in cases
            if (r := _classify_sync(text)).scenario_id == es and r.agent_route == er
        )
        accuracy = correct / len(cases)
        assert accuracy >= 7 / 9, (
            f"scenario {scenario_id} accuracy {correct}/{len(cases)} < 7/9"
        )


class TestShortcuts:
    """단축어 (long:/swing:/both:) 명시 분기."""

    def test_long_shortcut_routes_to_track_a(self) -> None:
        r = _classify_sync("long: 삼성전자")
        assert r.scenario_id == 2
        assert r.agent_route == "track_a"
        assert r.stage == "deterministic"
        assert r.confidence >= 0.9

    def test_swing_shortcut_routes_to_track_b(self) -> None:
        r = _classify_sync("swing: 카카오")
        assert r.scenario_id == 2
        assert r.agent_route == "track_b"
        assert r.stage == "deterministic"

    def test_both_shortcut_routes_to_both(self) -> None:
        r = _classify_sync("both: SK하이닉스")
        assert r.scenario_id == 2
        assert r.agent_route == "both"
        assert r.stage == "deterministic"


class TestTickerExtraction:
    """발화에서 종목명 매칭 → ticker 정규화."""

    def test_ticker_from_name(self) -> None:
        r = _classify_sync("삼성전자 들고 있는데 어떻게 해")
        assert r.ticker == "005930"
        assert r.ticker_display == "삼성전자"

    def test_ticker_from_6digit(self) -> None:
        r = _classify_sync("000660 살까")
        assert r.ticker == "000660"

    def test_ticker_longest_match_first(self) -> None:
        """'삼성바이오로직스' 가 '삼성' 보다 먼저 매칭되어야 (substring 충돌 방지)."""
        r = _classify_sync("삼성바이오로직스 들고 있어")
        assert r.ticker == "207940"
        assert r.ticker_display == "삼성바이오로직스"

    def test_no_ticker_when_absent(self) -> None:
        r = _classify_sync("지금 시장 어때")
        assert r.ticker is None
        assert r.scenario_id == 3


class TestManualFallback:
    """ticker 필요 시나리오 (1·2·6·7·8) + ticker 매핑 실패 → manual_fallback_required=True."""

    def test_scenario_1_without_ticker_requires_fallback(self) -> None:
        """발화에 종목명 없으면 시나리오 1 매칭이지만 fallback 필요."""
        r = _classify_sync("들고 있는데 어떻게")
        # scenario 1 매칭 (보유 keyword), ticker null → manual fallback
        assert r.scenario_id == 1
        assert r.ticker is None
        assert r.manual_fallback_required is True

    def test_scenario_3_without_ticker_no_fallback(self) -> None:
        """시나리오 3 (시장 판단) 은 ticker 불필요."""
        r = _classify_sync("지금 시장 어때")
        assert r.scenario_id == 3
        assert r.ticker is None
        assert r.manual_fallback_required is False


class TestEdgeCases:
    """엣지 케이스 — 빈 입력 / 매핑 불가 / 모호 발화."""

    def test_empty_input(self) -> None:
        r = _classify_sync("")
        assert r.scenario_id == 0
        assert r.agent_route == "refuse_or_guide"
        assert r.manual_fallback_required is True

    def test_unrelated_chitchat(self) -> None:
        """비관련 발화 — Stage 1 miss + Stage 2 skip → refuse_or_guide."""
        r = _classify_sync("오늘 날씨 어때")
        # 'today weather' 는 keyword 매칭 없음, refuse_or_guide
        assert r.agent_route == "refuse_or_guide"

    def test_pending_ms5_keyword(self) -> None:
        r = _classify_sync("시스템 개선 제안")
        assert r.scenario_id == 11
        assert r.agent_route == "pending_ms5"
