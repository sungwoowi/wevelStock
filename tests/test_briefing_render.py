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


def test_render_overnight_us_night_futures_and_brent() -> None:
    """미국 야간선물(NQ/ES) + 브렌트유 노출, 현물과 '선물' 라벨로 구분 (INFRA-MARKET-ASSETS-002)."""
    data = _overnight_fixture()
    data["overnight_us"]["nq_futures"] = {"price": 21000.0, "change_pct": 0.16}
    data["overnight_us"]["es_futures"] = {"price": 6100.0, "change_pct": 0.22}
    data["macro"]["brent"] = {"price": 74.0, "change_pct": -1.14}
    text = render_overnight(data)
    assert "야간선물 나스닥100선물 +0.16% · S&P500선물 +0.22%" in text
    assert "브렌트유" in text


def test_render_overnight_night_futures_source_kr() -> None:
    """source_kr 가 있으면 실선물/대용 구분 표기 (INFRA-MARKET-ASSETS-002)."""
    real = _overnight_fixture()
    real["night_futures"]["kospi200_cme_night"] = {
        "change_pct": 5.16, "source": "kis", "source_kr": "실선물",
    }
    text = render_overnight(real)
    assert "KOSPI200 야간선물 +5.16% (실선물)" in text

    proxy = _overnight_fixture()
    proxy["night_futures"]["kospi200_cme_night"] = {
        "change_pct": 0.4, "source": "EWY", "source_kr": "EWY ETF(대용)",
    }
    assert "(EWY ETF(대용))" in render_overnight(proxy)


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


def test_render_scenario_short_long_split() -> None:
    """단기(1~2주)/장기(1개월+) 관점 분리 + 스탠스·실전 대응 노출 (2026-07-06 사용자 요청).

    '이 시장에서 홀딩할지 매도할지 매수할지' 판단에 직결되는 구조 —
    관점별 스탠스 라벨 + 조건부 대응 guidance 가 각각 별도 블록으로.
    """
    data = _scenario_fixture()
    data["scenario"]["short_term"] = {
        "stance": "매수 대기",
        "guidance": "추가 상승 시 부분 매도 자리, 지난주 저점 부근 재매수 대기가 유리합니다.",
    }
    data["scenario"]["long_term"] = {
        "stance": "홀딩",
        "guidance": "이번 악재는 기존 뉴스의 재탕 — 구조 변곡이 아니므로 저점 매수분은 8월까지 기다리는 편이 낫습니다.",
    }
    text = render_scenario(data)
    assert "단기 (1~2주)" in text
    assert "장기 (1개월+)" in text
    assert "매수 대기" in text and "재매수 대기" in text
    assert "홀딩" in text and "재탕" in text
    # 단기 블록이 장기보다 먼저 (당장 행동 → 큰 그림 순)
    assert text.index("단기 (1~2주)") < text.index("장기 (1개월+)")


def test_render_scenario_backward_compat_narrative_only() -> None:
    """구버전 응답(short/long 없음) — 기존 narrative 렌더 유지 (graceful)."""
    text = render_scenario(_scenario_fixture())
    assert "반도체 섹터 주도 상승" in text
    assert "단기 (1~2주)" not in text


def test_render_news_magnitude_exclamation_icons() -> None:
    """파급 규모 = 느낌표 기호 (소=무표시·중=❗·대=‼️) — 사용자 시안 선택 (2026-07-07)."""
    data = _scenario_fixture()
    data["news_impact"][0]["impact_magnitude"] = 3
    text = render_scenario(data)
    assert "⬆️‼️" in text
    assert "[3]" not in text and "파급 대]" not in text


def test_render_news_legend_line() -> None:
    """기호 범례 — 받는 사람이 설명 없이 알 수 있게 (2026-07-07 사용자 지적)."""
    text = render_scenario(_scenario_fixture())
    assert "⬆️호재" in text and "⬇️악재" in text and "➡️중립" in text
    assert "❗파급중" in text and "‼️파급대" in text


def test_render_news_korean_headline_with_embedded_link() -> None:
    """한국어 헤드라인 + 링크 임베드 — 🔗 줄 제거, 종목당 2줄 (사용자 시안 선택)."""
    data = _scenario_fixture()
    data["news_impact"][0]["headline_kr"] = "나스닥 반등, 기술주 불안 완화"
    text = render_scenario(data)
    assert '<a href="http://example.com/a">나스닥 반등, 기술주 불안 완화</a>' in text
    assert "🔗 http://example.com/a" not in text  # 링크 줄 사라짐
    assert "NVIDIA 어닝 서프라이즈" not in text    # 원제목 대신 한국어 헤드라인


def test_render_news_headline_fallback_and_escape() -> None:
    """headline_kr 없으면 원제목 폴백 + HTML 이스케이프 (parse_mode=HTML 파손 방지)."""
    data = _scenario_fixture()
    data["news_items"][0]["title"] = "A&B <급등> 소식"
    text = render_scenario(data)
    assert "A&amp;B &lt;급등&gt; 소식" in text  # 원제목 폴백 + escape


def test_render_scenario_korean_labels() -> None:
    """expected_open/bias 코드 라벨을 한국어로 노출 (노출 단 코드 라벨 금지 원칙)."""
    data = _scenario_fixture()
    data["scenario"]["expected_open"] = "gap_down_big"
    data["scenario"]["bias"] = "bearish"
    text = render_scenario(data)
    assert "큰 갭 하락" in text
    assert "약세" in text
    assert "gap_down_big" not in text
    assert "bearish" not in text


def test_render_positions_with_advice_and_candidate() -> None:
    text = render_positions(_positions_fixture())
    assert "보유/관심 의견" in text
    assert "삼성전자" in text
    assert "BUY_ADD" in text
    assert "🟢" in text


def test_render_hold_icon_visible() -> None:
    """HOLD 아이콘 = 🔵 (▫ 회색 소형은 안 보임 — 2026-07-07 사용자 지적)."""
    data = _positions_fixture()
    data["positions_advice"][0]["verdict"] = "HOLD"
    text = render_positions(data)
    assert "🔵 삼성전자 — HOLD" in text
    assert "▫" not in text


def test_render_candidates_airy_layout() -> None:
    """신규 후보 — 종목줄/이유줄 분리 + 항목 간 빈 줄 (2026-07-07 '띄어쓰기 힘들다')."""
    data = _positions_fixture()
    data["new_candidates"] = [
        {"sector": "반도체", "name": "SK하이닉스", "reason": "SOX 급등 — 눌림목 반등 기대."},
        {"sector": "반도체장비", "name": "주성엔지니어링", "reason": "장비주 수혜 — 교집합 수급."},
    ]
    text = render_positions(data)
    block = text.split("신규 매수 후보")[1]
    lines = block.splitlines()
    # 종목명 줄과 이유 줄이 분리 (한 줄 통짜 금지)
    name_line = next(l for l in lines if "SK하이닉스" in l)
    assert "SOX 급등" not in name_line
    assert any("└" in l and "SOX 급등" in l for l in lines)
    # 항목 사이 빈 줄 (밀집 해소)
    idx1 = next(i for i, l in enumerate(lines) if "SK하이닉스" in l)
    idx2 = next(i for i, l in enumerate(lines) if "주성엔지니어링" in l)
    assert any(not lines[i].strip() for i in range(idx1, idx2)), "항목 간 빈 줄 없음"


def test_render_sector_watch_compass() -> None:
    """섹터 관점(강세/약세·회피) 렌더 — 시장 안 좋은 날 홀딩/회피 안내 (2026-07-07 요청).

    sector_watch 는 LLM 이 이미 산출하는데 렌더가 버리고 있던 필드.
    """
    data = _positions_fixture()
    data["sector_watch"] = {"bullish": ["반도체", "조선"], "bearish": ["건설", "화학"]}
    text = render_positions(data)
    assert "섹터" in text
    assert "반도체" in text and "조선" in text
    assert "건설" in text and "화학" in text
    assert "회피" in text or "비중 축소" in text  # 약세 = 행동 함의 표기


def test_render_sector_watch_absent_graceful() -> None:
    """sector_watch 없거나 빈 값 — 섹터 블록 생략 (구버전 응답 호환)."""
    text = render_positions(_positions_fixture())
    assert "약세·회피" not in text
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
