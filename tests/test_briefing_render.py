"""core/briefing/render.py — 파트별 렌더 + morning_pre 3분할 스냅샷.

공용 렌더 함수가 notify.py 의 기존 `_build_msg_*` 와 동일한 내용을
만드는지 확인. 파트별 fixture 로 핵심 키워드를 검증.
"""
from __future__ import annotations

from core.briefing.render import (
    DEGRADED_PREFIX,
    render_morning_pre,
    render_overnight,
    render_positions,
    render_scenario,
)
from core.contracts.briefing_part import BriefingPart


def _overnight_fixture() -> dict:
    return {
        "overnight_us": {
            "nasdaq": {"price": 20000.12, "change_pct": 1.25},
            "sp500": {"price": 5800.5, "change_pct": 0.45},
            "sox": {"price": 5200.0, "change_pct": 2.1},
            "vix": {"price": 14.3, "change_pct": -3.1},
            "fear_greed": {
                "score": 72,
                "rating_kr": "탐욕",
                "change_pct": 5.2,
            },
        },
        "macro": {
            "dxy": {"price": 104.5, "change_pct": -0.1},
            "usdkrw": {"price": 1380.0, "change_pct": 0.3},
            "us_10y": {"price": 4.25, "change_pct": 0.02},
        },
        "night_futures": {
            "kospi200_cme_night": {"change_pct": 0.4, "source": "CME"},
        },
    }


def _scenario_fixture() -> dict:
    return {
        "scenario": {
            "expected_open": "강세",
            "bias": "long",
            "confidence": 72,
            "narrative": "반도체 섹터 주도 상승 예상 — 엔비디아 실적 호재가 국내 IT 에 전이",
        },
        "news_impact": [
            {
                "url": "http://example.com/a",
                "impact_direction": "bullish",
                "impact_magnitude": 3,
                "impact_note": "AI 수요 견조",
            }
        ],
        "news_items": [
            {"url": "http://example.com/a", "title": "NVIDIA 어닝 서프라이즈"},
            {"url": "http://example.com/b", "title": "한은 동결 결정"},
        ],
    }


def _positions_fixture() -> dict:
    return {
        "positions_advice": [
            {
                "ticker": "005930",
                "name": "삼성전자",
                "verdict": "BUY_ADD",
                "reason": "HBM 수요 확대로 Q3 실적 기대",
            }
        ],
        "new_candidates": [
            {"sector": "반도체", "name": "SK하이닉스", "reason": "HBM3E 양산"}
        ],
        "principles": {"violations": [], "warnings": []},
    }


def test_render_overnight_contains_key_sections() -> None:
    text = render_overnight(_overnight_fixture())
    assert "간밤 시황" in text
    assert "나스닥" in text
    assert "+1.25%" in text
    assert "공포·탐욕 지수 72" in text
    assert "KOSPI200 야간선물" in text


def test_render_overnight_empty_sections_drop() -> None:
    text = render_overnight({})
    assert "간밤 시황" in text
    # fear_greed 블록이 비어있으면 라인이 없어야
    assert "공포·탐욕 지수" not in text


def test_render_scenario_includes_news_and_narrative() -> None:
    text = render_scenario(_scenario_fixture())
    assert "오늘 시나리오" in text
    assert "바이어스: long" in text
    assert "반도체 섹터 주도 상승" in text
    assert "NVIDIA 어닝" in text
    assert "⬆️" in text  # impact_direction=bullish


def test_render_scenario_empty_news_shows_fallback() -> None:
    text = render_scenario({"scenario": {}, "news_items": [], "news_impact": []})
    assert "뉴스 수집 실패" in text


def test_render_positions_with_advice_and_candidate() -> None:
    text = render_positions(_positions_fixture())
    assert "보유/관심 의견" in text
    assert "삼성전자" in text
    assert "BUY_ADD" in text
    assert "🟢" in text
    assert "SK하이닉스" in text
    assert "7계명 체크: 위반 없음" in text


def test_render_positions_with_violations() -> None:
    data = {
        "positions_advice": [],
        "new_candidates": [],
        "principles": {
            "violations": [
                {"commandment": 1, "title": "총 투자비중 초과"},
            ]
        },
    }
    text = render_positions(data)
    assert "7계명 위반 1건" in text
    assert "[계명 1] 총 투자비중 초과" in text


def test_render_morning_pre_full_three_parts_ok_status() -> None:
    parts = [
        BriefingPart(
            key="scenario", label="시나리오+뉴스", order=2, data=_scenario_fixture()
        ),
        BriefingPart(
            key="overnight", label="간밤시황", order=1, data=_overnight_fixture()
        ),
        BriefingPart(
            key="positions", label="포지션+신규", order=3, data=_positions_fixture()
        ),
    ]
    texts = render_morning_pre(parts, status="ok")
    # order 로 정렬되었는지 확인
    assert len(texts) == 3
    assert "간밤 시황" in texts[0]
    assert "오늘 시나리오" in texts[1]
    assert "보유/관심 의견" in texts[2]
    # 정상 상태에서는 degraded prefix 없음
    for t in texts:
        assert not t.startswith(DEGRADED_PREFIX)


def test_render_morning_pre_degraded_adds_prefix() -> None:
    parts = [
        BriefingPart(
            key="overnight", label="간밤시황", order=1, data=_overnight_fixture()
        ),
    ]
    texts = render_morning_pre(parts, status="degraded")
    assert len(texts) == 1
    assert texts[0].startswith(DEGRADED_PREFIX)
    assert "일시적 LLM 장애" in texts[0]
    assert "간밤 시황" in texts[0]  # 본문 유지


def test_render_morning_pre_unknown_key_skipped() -> None:
    parts = [
        BriefingPart(
            key="overnight", label="간밤시황", order=1, data=_overnight_fixture()
        ),
        BriefingPart(key="unknown", label="???", order=2, data={"whatever": 1}),
    ]
    texts = render_morning_pre(parts, status="ok")
    assert len(texts) == 1  # unknown 은 skip
