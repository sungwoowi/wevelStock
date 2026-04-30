"""Phase 2 — market_briefing 파이프라인 단위 테스트.

대상: persist stage / render_market_briefing / 단위 변환 helpers.

collector / KIS 호출은 mock 수준 — 실 KIS 호출은 별도 ad-hoc 스크립트로
별도 검증 (이번 세션 M1, M2 의 ad-hoc 실증으로 커버).
"""
from __future__ import annotations

import asyncio

import pytest

from core.briefing import (
    get_parts_by_run,
    render_market_briefing,
)
from core.contracts.briefing_part import BriefingPart
from pipelines._base import StageContext


def _mock_market_data() -> dict:
    """collect_kr_market stage 의 return shape 모방."""
    return {
        "indices": {
            "kospi": {
                "value": 6690.9,
                "change_pct": 0.75,
                "trade_amount": 31453311,
                "volume": 717859,
            },
            "kosdaq": {
                "value": 1220.26,
                "change_pct": 0.39,
                "trade_amount": 15791971,
                "volume": 1255886,
            },
            "kospi200": {
                "value": 905.42,
                "change_pct": 0.82,
                "trade_amount": 0,
                "volume": 0,
            },
            "fetched_at": "2026-04-30T09:30:25+09:00",
            "source": "kis",
        },
        "supply_demand": {
            "kospi": {
                "market": "kospi",
                "individual_net_amount_m": 1182435,
                "foreign_net_amount_m": -1455933,
                "institution_net_amount_m": 283792,
                "fin_invest_net_amount_m": 508920,
                "pension_net_amount_m": 35039,
            },
            "kosdaq": {
                "market": "kosdaq",
                "individual_net_amount_m": 128603,
                "foreign_net_amount_m": -42542,
                "institution_net_amount_m": -28700,
                "fin_invest_net_amount_m": -15000,
                "pension_net_amount_m": 8400,
            },
            "source": "kis",
        },
        "futures_supply_demand": {
            "trade_date": "20260430",
            "individual_net_amount_b": -41,
            "foreign_net_amount_b": 445,
            "institution_net_amount_b": -400,
            "fetched_at_krx": "2026.04.30 PM 11:05:36",
            "source": "krx",
        },
        "leading_stocks": {
            "kospi": [
                {
                    "name": "HD현대중공업",
                    "ticker": "329180",
                    "change_pct": 3.45,
                    "match": "meets_criteria",
                    "cap_tier": "top20",
                },
                {
                    "name": "삼성SDI",
                    "ticker": "006400",
                    "change_pct": 4.71,
                    "match": "meets_criteria",
                    "cap_tier": "top20",
                },
            ],
            "kosdaq": [
                {
                    "name": "서진시스템",
                    "ticker": "178320",
                    "change_pct": 10.53,
                    "match": "meets_criteria",
                },
            ],
            "stats": {
                "kospi_matched": 2,
                "kospi_fill": 0,
                "kosdaq_matched": 1,
                "kosdaq_fill": 0,
            },
        },
        "sectors": {
            "all": [
                {"name": "KODEX 2차전지산업", "ticker": "305720", "change_pct": 2.02},
                {"name": "KODEX AI반도체", "ticker": "394670", "change_pct": 1.09},
                {"name": "KODEX 반도체", "ticker": "091160", "change_pct": 0.5},
            ],
            "strong": [
                {"name": "KODEX 2차전지산업", "ticker": "305720", "change_pct": 2.02},
                {"name": "KODEX AI반도체", "ticker": "394670", "change_pct": 1.09},
            ],
            "min_change_pct": 1.0,
        },
    }


def _market_parts() -> list[BriefingPart]:
    md = _mock_market_data()
    return [
        BriefingPart(
            key="market_overview",
            label="시장개요",
            order=1,
            data={"indices": md["indices"], "fetched_at": md["indices"]["fetched_at"]},
        ),
        BriefingPart(
            key="supply_sectors",
            label="수급+강세섹터",
            order=2,
            data={
                "supply_demand": md["supply_demand"],
                "futures_supply_demand": md["futures_supply_demand"],
                "sectors": md["sectors"],
            },
        ),
        BriefingPart(
            key="leading_stocks",
            label="주도주",
            order=3,
            data={"leading_stocks": md["leading_stocks"]},
        ),
    ]


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    from core.db import get_db

    db = get_db()
    with db.connect() as conn:
        conn.execute("DELETE FROM briefing_parts")


# ----------------------------------------------------------------------------
# Persist stage
# ----------------------------------------------------------------------------


def test_persist_stage_writes_three_parts() -> None:
    from pipelines.market_briefing_now.stages.persist import PersistStage

    md = _mock_market_data()
    ctx = StageContext(
        run_id="test_market_run",
        pipeline_id="market_briefing_now",
        date="2026-04-30",
        data={"collect_kr_market": md},
    )
    result = asyncio.run(PersistStage().run(ctx))

    assert result.status == "ok"
    assert result.data["counts"]["briefing_parts"] == 3

    parts = get_parts_by_run("market_briefing_now", "test_market_run")
    assert len(parts) == 3
    keys = {p.key for p in parts}
    assert keys == {"market_overview", "supply_sectors", "leading_stocks"}
    by_key = {p.key: p for p in parts}
    assert by_key["market_overview"].order == 1
    assert by_key["supply_sectors"].order == 2
    assert by_key["leading_stocks"].order == 3


def test_persist_stage_handles_empty_collect_data() -> None:
    """collect 결과가 빈 dict 여도 persist 는 부분 데이터로 진행."""
    from pipelines.market_briefing_now.stages.persist import PersistStage

    ctx = StageContext(
        run_id="test_empty_run",
        pipeline_id="market_briefing_now",
        date="2026-04-30",
        data={"collect_kr_market": {}},
    )
    result = asyncio.run(PersistStage().run(ctx))
    assert result.status == "ok"
    parts = get_parts_by_run("market_briefing_now", "test_empty_run")
    assert len(parts) == 3


# ----------------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------------


def test_render_market_briefing_returns_three_strings() -> None:
    parts = _market_parts()
    texts = render_market_briefing(parts)
    assert len(texts) == 3

    # part 1 (시장 개요) — 지수 + KOSPI200 + 거래대금 + 출처
    assert "KOSPI" in texts[0]
    assert "6,690.90" in texts[0]
    assert "(+0.75%)" in texts[0]
    assert "31.45조" in texts[0]
    assert "KOSPI200" in texts[0]
    assert "905.42" in texts[0]
    assert "선물 기초" in texts[0]
    assert "출처: KIS API" in texts[0]
    assert "09:30:25" in texts[0]

    # part 2 (수급 + 섹터) — KOSPI/KOSDAQ 분리 헤더 + 5주체(개인/외인/기관/금투/연기금) + 섹터
    assert "[KOSPI]" in texts[1]
    assert "[KOSDAQ]" in texts[1]
    assert "외인" in texts[1]
    assert "-1.46조" in texts[1]  # KOSPI 외인 시장 전체 -1,455,933백만 = -1.456조
    assert "개인" in texts[1]
    assert "기관" in texts[1]
    assert "금융투자" in texts[1]
    assert "연기금" in texts[1]
    # 세로 나열 순서 검증: 개인 → 외인 → 기관 → 금융투자 → 연기금
    kospi_idx = texts[1].index("[KOSPI]")
    kosdaq_idx = texts[1].index("[KOSDAQ]")
    section = texts[1][kospi_idx:kosdaq_idx]
    order = [section.index(label) for label in ["개인", "외인", "기관", "금융투자", "연기금"]]
    assert order == sorted(order), f"순서 위반: {order}"
    # KOSPI200 선물 수급 (KRX, 3주체) — [KOSPI200 선물] 헤더로 통일
    assert "[KOSPI200 선물]" in texts[1]
    assert "+4,450억" in texts[1]  # 외인 +445 십억 = +4,450억
    # ※ 안내는 선물 블록 뒤로 이동
    assert texts[1].index("[KOSPI200 선물]") < texts[1].index("※ 기관=")
    assert "시장 전체" in texts[1]
    assert "KODEX 2차전지산업" in texts[1]
    assert "+2.02%" in texts[1]

    # part 3 (주도주) — 대형/중소형 분리 + 매칭 조건 + 선별 조건 안내
    assert "[KOSPI 대형주 (시총20위)]" in texts[2]
    assert "[KOSPI 중소형 (시총20위 외)]" in texts[2]
    assert "[KOSDAQ]" in texts[2]
    assert "HD현대중공업" in texts[2]
    assert "삼성SDI" in texts[2]
    assert "🔥" in texts[2]
    assert "(top20+2%)" in texts[2]
    assert "선별 조건" in texts[2]


def test_render_market_briefing_empty_strong_sectors() -> None:
    """조건 충족 0 이어도 강세 섹터 영역에 등락률 순으로 채워서 표시."""
    parts = _market_parts()
    for p in parts:
        if p.key == "supply_sectors":
            p.data["sectors"]["strong"] = []
    texts = render_market_briefing(parts)
    # 조건 충족 0 표기 + 등락률 순으로 추적 ETF 표시
    assert "조건 충족 0개" in texts[1]
    # all 의 첫 ETF (KODEX 2차전지산업) 가 등락률순으로 출력
    assert "KODEX 2차전지산업" in texts[1]


def test_render_market_briefing_no_sectors_at_all() -> None:
    """all 도 비어있으면 '추적 ETF 없음' 메시지."""
    parts = _market_parts()
    for p in parts:
        if p.key == "supply_sectors":
            p.data["sectors"]["all"] = []
            p.data["sectors"]["strong"] = []
    texts = render_market_briefing(parts)
    assert "추적 ETF 없음" in texts[1]


def test_render_market_briefing_empty_leading() -> None:
    """모든 그룹이 비어있어도 각 그룹 헤더와 '없음' 메시지 출력."""
    parts = _market_parts()
    for p in parts:
        if p.key == "leading_stocks":
            p.data["leading_stocks"]["kospi"] = []
            p.data["leading_stocks"]["kosdaq"] = []
            p.data["leading_stocks"]["stats"] = {}
    texts = render_market_briefing(parts)
    assert "[KOSPI 대형주 (시총20위)]" in texts[2]
    assert "[KOSPI 중소형 (시총20위 외)]" in texts[2]
    assert "[KOSDAQ]" in texts[2]
    # 대형/KOSDAQ 빈 메시지 + 중소형 안내 문구
    assert "해당 종목 없음" in texts[2]
    assert "거래대금 상위 30 풀에 미포함" in texts[2]


def test_render_market_briefing_handles_missing_indices() -> None:
    """KIS index 호출이 실패해서 error dict 반환된 경우."""
    parts = _market_parts()
    for p in parts:
        if p.key == "market_overview":
            p.data["indices"]["kospi"] = {"error": "kis_unavailable"}
    texts = render_market_briefing(parts)
    assert "조회 실패" in texts[0]


def test_render_market_briefing_orders_by_part_order() -> None:
    """parts 가 역순으로 들어와도 order 기준 정렬."""
    parts = list(reversed(_market_parts()))
    texts = render_market_briefing(parts)
    # part 1 (order=1) 의 시그니처
    assert "출처: KIS API" in texts[0]
    # part 3 (order=3) 의 시그니처
    assert "주도주" in texts[2]


# ----------------------------------------------------------------------------
# Unit converters
# ----------------------------------------------------------------------------


def test_fmt_won_million_units() -> None:
    """단위 변환: 1조 = 1,000,000 백만원, 1억 = 100 백만원."""
    from core.briefing.render import _fmt_won_million

    # 0.94조 (940,771 백만원) → 1조 미만은 억 표기
    assert _fmt_won_million(940_771) == "+9,408억"
    # 27조 (27,000,000 백만원) → 조 표기
    assert _fmt_won_million(27_000_000) == "+27.00조"
    # 2.5조 (2,500,000 백만원) → 조 표기 정확
    assert _fmt_won_million(2_500_000) == "+2.50조"
    # 음수 1500억 (-150,000 백만원)
    assert _fmt_won_million(-150_000) == "-1,500억"
    # None / 0
    assert _fmt_won_million(None) == "?"
    assert _fmt_won_million(0) == "+0억"


def test_fmt_trade_amount_units() -> None:
    from core.briefing.render import _fmt_trade_amount

    assert _fmt_trade_amount(31453311) == "31.45조"
    assert _fmt_trade_amount(None) == "?"
    assert _fmt_trade_amount(0) == "0.00조"
