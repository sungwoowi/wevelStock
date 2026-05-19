"""ANALYST-PERSONAS-001 v2 — 자료 0 시드 5 분석가 페르소나·매니페스트 양식 검증.

대상 5 분석가 (자료 0 시드, 2026-05-19 병렬 dispatch 작성):
- `market_state_analyzer` / `stock_picker` / `trading_journalist` / `flow_analyzer` / `news_curator`

검증:
- manifest 로드 (load_analyst_spec × 5)
- 8 섹션 portable 양식 (Identity / Domain Frame / Inputs / Outputs / Reasoning Doctrine /
  Knowledge Categories / Anti-patterns / Cross-Agent Boundaries)
- canon_categories 매핑 정합 (SPEC v2 § canon_categories 잠정 매핑 표 ↔ manifest)
- Track A·B persona reads_analysts 정합 (양쪽 박음 검증)
- Cross-Agent Boundaries 충돌 검증 (다른 분석가·Layer 3·4·5 영역 일관 분리)
- 핵심 가드 (박종훈 framework 직접 인용 금지 / 한국어 친화 용어 / cited 풀이 v3.1)
- 분석가별 특수 가드 (market_state cross-reference trigger / stock_picker G1 / news_curator SLOT S2)
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest
import yaml

analyst_mod = importlib.import_module("core.inference.run_analyst")
load_analyst_spec = analyst_mod.load_analyst_spec
ANALYSTS_DIR = analyst_mod.ANALYSTS_DIR

REPO_ROOT = Path(__file__).resolve().parents[1]
STRATEGISTS_DIR = REPO_ROOT / "agents" / "strategists"

SEED_5_ANALYSTS = [
    "market_state_analyzer",
    "stock_picker",
    "trading_journalist",
    "flow_analyzer",
    "news_curator",
]

# SPEC v2 § canon_categories 잠정 매핑 표 권위
EXPECTED_CANON_CATEGORIES = {
    "market_state_analyzer": [
        "market_macro/macro_indicators",
        "market_macro/regime_signals",
        "market_macro/cross_market",
        "market_macro/event_response",
    ],
    "stock_picker": [
        "stock_selection/sector_rotation",
        "stock_selection/momentum_leaders",
        "stock_selection/theme_play",
        "stock_selection/swing_candidates",
    ],
    "trading_journalist": [
        "trading_journal/pnl_tracking",
        "trading_journal/post_mortem",
        "trading_journal/memory_compression",
        "trading_journal/doctrine_evolution",
    ],
    "flow_analyzer": [
        "flow_analysis/liquidity_macro",
        "flow_analysis/industry_trend",
        "flow_analysis/sector_flow",
        "flow_analysis/stock_flow",
    ],
    "news_curator": [],  # SLOT S2 — 자료원 결정 후 SPEC 갱신, 현재 빈 list
}

EXPECTED_DEPT = {
    "market_state_analyzer": "market_macro",
    "stock_picker": "stock_selection",
    "trading_journalist": "trading_journal",
    "flow_analyzer": "flow_analysis",
    "news_curator": "news",
}


# ---------------------------------------------------------------------------
# Manifest 로드 + dept 정합
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("analyst_id", SEED_5_ANALYSTS)
def test_seed_analyst_manifest_loads(analyst_id: str) -> None:
    """5 분석가 manifest 가 AnalystSpec 으로 로딩되고 dept 정합."""
    spec = load_analyst_spec(analyst_id)
    assert spec.id == analyst_id
    assert spec.learning_dept == EXPECTED_DEPT[analyst_id]
    assert spec.persona_path.exists()
    assert spec.temperature == 0.4  # 결정론 강화 (5명 모두)
    assert spec.response_rules is not None


@pytest.mark.parametrize("analyst_id", SEED_5_ANALYSTS)
def test_seed_analyst_canon_categories_per_spec(analyst_id: str) -> None:
    """canon_categories 가 SPEC v2 § 잠정 매핑 표 권위와 일치."""
    spec = load_analyst_spec(analyst_id)
    expected = EXPECTED_CANON_CATEGORIES[analyst_id]
    assert spec.canon_categories == expected, (
        f"{analyst_id}: expected {expected}, got {spec.canon_categories}"
    )


# ---------------------------------------------------------------------------
# 8 섹션 portable 양식
# ---------------------------------------------------------------------------


REQUIRED_SECTIONS = [
    "## Identity",
    "## Domain Frame",
    "## Inputs",
    "## Outputs",
    "## Reasoning Doctrine",
    "## Knowledge Categories",
    "## Anti-patterns",
    "## Cross-Agent Boundaries",
]


@pytest.mark.parametrize("analyst_id", SEED_5_ANALYSTS)
def test_seed_analyst_has_eight_portable_sections(analyst_id: str) -> None:
    """ANALYST-PERSONAS-001 v2 의 8 섹션 portable 양식 존재."""
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{analyst_id}: missing section '{section}'"


# ---------------------------------------------------------------------------
# Track A·B persona reads_analysts 정합 (이중 박음 검증)
# ---------------------------------------------------------------------------


TRACK_A_READS = {
    "stock_picker",
    "stock_analyst",
    "wealth_strategist",
    "principle_guardian",
    "market_state_analyzer",
    "flow_analyzer",
}

TRACK_B_READS = {
    "stock_picker",
    "trader",
    "market_state_analyzer",
    "flow_analyzer",
    "principle_guardian",
}


def _load_strategist_reads(strategist_id: str) -> set[str]:
    manifest_path = STRATEGISTS_DIR / strategist_id / "manifest.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return set(raw.get("reads_analysts") or [])


def test_track_a_reads_includes_seed_3() -> None:
    """Track A reads_analysts 에 5 분석가 중 3명 (market_state·stock_picker·flow_analyzer) 포함."""
    track_a_reads = _load_strategist_reads("track_a")
    assert "market_state_analyzer" in track_a_reads
    assert "stock_picker" in track_a_reads
    assert "flow_analyzer" in track_a_reads
    # 검증: SPEC 권위와 일치
    assert track_a_reads == TRACK_A_READS


def test_track_b_reads_includes_seed_3() -> None:
    """Track B reads_analysts 에 5 분석가 중 3명 (market_state·stock_picker·flow_analyzer) 포함."""
    track_b_reads = _load_strategist_reads("track_b")
    assert "market_state_analyzer" in track_b_reads
    assert "stock_picker" in track_b_reads
    assert "flow_analyzer" in track_b_reads
    assert track_b_reads == TRACK_B_READS


def test_trading_journalist_news_curator_not_in_track_reads() -> None:
    """trading_journalist 와 news_curator 는 Track A·B reads_analysts 양쪽 X.

    trading_journalist = Layer 5 회고분석가 read 영역 (또는 사용자 직접 호출)
    news_curator = market_state·flow·stock_picker 간접 read (Track A·B 직접 read X)
    """
    track_a_reads = _load_strategist_reads("track_a")
    track_b_reads = _load_strategist_reads("track_b")
    for indirect_id in ["trading_journalist", "news_curator"]:
        assert indirect_id not in track_a_reads, (
            f"{indirect_id} should NOT be in Track A reads_analysts"
        )
        assert indirect_id not in track_b_reads, (
            f"{indirect_id} should NOT be in Track B reads_analysts"
        )


# ---------------------------------------------------------------------------
# 핵심 가드 — 박종훈 framework 직접 인용 금지
# ---------------------------------------------------------------------------


# 박종훈 framework 명제 ID 패턴 (M1-M3, C1-C5, I1-I6, SP*, W*) — 본문에 직접 인용 검출
# 단 manifest response_rules 의 *예시* 안에 박힌 것은 제외 (cited 풀이 v3.1 양식 예시).
# 검증: persona.md 본문에 "박종훈" 단어 직접 등장 0
PARK_FRAMEWORK_TERMS = ["박종훈", "Dalio 5단계", "Dalio 5 단계"]


@pytest.mark.parametrize("analyst_id", SEED_5_ANALYSTS)
def test_seed_analyst_no_park_jonghoon_direct_citation(analyst_id: str) -> None:
    """5 분석가 persona 본문에 박종훈 framework 직접 인용 X (가드 검증).

    `feedback_park_jonghoon_scope.md` 권위: 박종훈 framework = 거시적 경제 해석 통찰,
    트레이딩 의사결정 직접 반영 X. wealth_strategist 영역만 인용 OK.
    """
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")
    for term in PARK_FRAMEWORK_TERMS:
        # 단 "박종훈 framework 직접 인용 금지" 같은 메타-가드 문장은 허용 (negation context)
        # 단순 검출: term 이 본문에 등장하면 가드 문장인지 검사
        if term in text:
            # 가드 문장 검출: "박종훈" 주변에 "금지" / "X" / "안" / "않" 같은 negation 키워드 있는지
            indices = [i for i in range(len(text)) if text[i : i + len(term)] == term]
            for idx in indices:
                surrounding = text[max(0, idx - 200) : idx + len(term) + 200]
                has_negation = any(
                    neg in surrounding
                    for neg in [
                        "금지", "직접 인용 X", "안 함", "않음", "않는다", "안 한다",
                        "회피", "분리", "wealth_strategist", "권위", "위임", "본인은",
                        "자산복리부만", "별도 자료원", "본 분석가는 안", "본 분석가 영역 X",
                    ]
                )
                assert has_negation, (
                    f"{analyst_id}: '{term}' 직접 인용 검출 (negation 컨텍스트 없음). "
                    f"주변 텍스트: ...{surrounding}..."
                )


# ---------------------------------------------------------------------------
# 한국어 친화 용어 + cited 풀이 v3.1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("analyst_id", SEED_5_ANALYSTS)
def test_seed_analyst_cited_v3_1_format_keywords(analyst_id: str) -> None:
    """cited 풀이 v3.1 양식 키워드 존재 (cited + 근거 명제 풀이)."""
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")
    assert "cited" in text  # cited: [...] 마커
    # "근거 명제 풀이" 또는 "framework 밖" (자료 0 시드 케이스) 키워드
    assert "근거 명제 풀이" in text or "framework 밖" in text, (
        f"{analyst_id}: cited 풀이 v3.1 양식 키워드 없음"
    )


# ---------------------------------------------------------------------------
# Cross-Agent Boundaries 충돌 검증 (정정 1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("analyst_id", SEED_5_ANALYSTS)
def test_seed_analyst_cross_agent_boundaries_table_present(analyst_id: str) -> None:
    """Cross-Agent Boundaries 표가 다른 분석가·Layer 위임 매핑 명시.

    표 구조: '| 질문 유형 | 넘길 곳 |' (markdown 표 헤더) + 행에 인접 분석가 ID 또는 Layer 명시.
    """
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # Cross-Agent Boundaries § 추출
    boundary_start = text.find("## Cross-Agent Boundaries")
    assert boundary_start != -1, f"{analyst_id}: ## Cross-Agent Boundaries 섹션 없음"
    boundary_section = text[boundary_start:]

    # 표 행 존재 검증
    table_rows = [line for line in boundary_section.split("\n") if line.startswith("|") and "---" not in line]
    assert len(table_rows) >= 3, f"{analyst_id}: Cross-Agent Boundaries 표 행 3+ 필요 (header + 2+ rows)"


# ---------------------------------------------------------------------------
# 분석가별 특수 가드
# ---------------------------------------------------------------------------


def test_market_state_analyzer_cross_reference_trigger_3_cases() -> None:
    """market_state_analyzer 의 wealth_strategist cross-reference 발동 trigger 3 케이스 명시 (정정 3).

    (a) regime 전환 / (b) Distribution Day 4건+ kill switch / (c) 사이클 단계 변화 시그널
    """
    persona_path = ANALYSTS_DIR / "market_state_analyzer" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # 3 케이스 키워드
    assert "regime 전환" in text or "체제 전환" in text
    assert "Distribution Day 4" in text or "DD 4" in text or "분배일 4" in text
    assert "사이클 단계" in text or "Dalio" in text  # 사이클 변화 시그널
    # cross-reference 위임 명시
    assert "wealth_strategist" in text


def test_stock_picker_g1_guard_two_scores() -> None:
    """stock_picker G1 가드 — S-Score + buy_score 양쪽 발행 강제 명시."""
    persona_path = ANALYSTS_DIR / "stock_picker" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    assert "S-Score" in text
    assert "buy_score" in text
    assert "G1" in text or "양쪽 발행" in text or "두 점수" in text
    # 한 점수만 발행 결정 금지 명시
    assert "한 점수만" in text or "둘 다" in text or "양쪽" in text


def test_news_curator_slot_s2_data_source_pending() -> None:
    """news_curator SLOT S2 (자료원 미결정) 명시 + canon_categories 빈 list."""
    spec = load_analyst_spec("news_curator")
    assert spec.canon_categories == []  # 자료원 결정 후 SPEC 갱신, 현재 빈 list

    persona_path = ANALYSTS_DIR / "news_curator" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")
    assert "SLOT S2" in text or "자료원" in text
    assert "Perplexity" in text or "별도 SPEC" in text


def test_flow_analyzer_f_score_4_axis_weights() -> None:
    """flow_analyzer F-Score 4축 가중치 (0.4·0.3·0.2·0.1) 명시."""
    persona_path = ANALYSTS_DIR / "flow_analyzer" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    assert "F-Score" in text or "수급 점수" in text
    # 4축 가중치 (정확 숫자)
    assert "0.4" in text and "0.3" in text and "0.2" in text and "0.1" in text


def test_trading_journalist_layer_5_boundary() -> None:
    """trading_journalist 가 Layer 5 회고분석가 영역과 분리 명시."""
    persona_path = ANALYSTS_DIR / "trading_journalist" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    assert "회고분석가" in text or "Layer 5" in text
    assert "prism-insight" in text or "prism" in text  # 차용 원천 명시


# ---------------------------------------------------------------------------
# 8 분석가 boundary 충돌 검증 (정정 2 — 2026-05-19 data-3 사이클 신설)
# 본 세션 5명 + data 3명 = 9 분석가, 그 중 wealth_strategist 포함 8 분석가 사이
# Cross-Agent Boundaries 표 위임 매핑 정합성 자동 검증
# ---------------------------------------------------------------------------


ALL_8_ANALYSTS = [
    "wealth_strategist",
    "market_state_analyzer",
    "stock_picker",
    "trading_journalist",
    "flow_analyzer",
    "principle_guardian",
    "trader",
    "stock_analyst",
]
# news_curator 는 SLOT S2 (자료원 미결정, canon_categories 빈 list) → 본 검증 제외


@pytest.mark.parametrize("analyst_id", ALL_8_ANALYSTS)
def test_8_analyst_boundary_all_others_present(analyst_id: str) -> None:
    """각 분석가의 Cross-Agent Boundaries 표가 본인 외 7 분석가 모두 위임 명시.

    정정 2 — 8 분석가 사이 영역 권위 중복 0 건 자동 검증 (boundary 매트릭스 완전성).
    분석가 추가 시 boundary 누락 자동 catch.
    """
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    boundary_start = text.find("## Cross-Agent Boundaries")
    assert boundary_start != -1, f"{analyst_id}: ## Cross-Agent Boundaries 섹션 없음"
    boundary_section = text[boundary_start:]

    # 본 분석가 외 7 분석가 ID 가 boundary 섹션에 모두 등장 (위임 매핑)
    missing = []
    for other_id in ALL_8_ANALYSTS:
        if other_id == analyst_id:
            continue
        if other_id not in boundary_section:
            missing.append(other_id)

    assert not missing, (
        f"{analyst_id}: Cross-Agent Boundaries 에 위임 누락 {missing}. "
        f"8 분석가 사이 권위 중복 회피를 위해 모든 인접 분석가 명시 필요."
    )


# 8 분석가 발행 권위 키워드 매트릭스 — 각 분석가가 본인만 발행하는 고유 키워드
AUTHORITY_KEYWORDS = {
    "wealth_strategist": ["wealth_strategist"],  # ID 자체가 권위 시그널
    "market_state_analyzer": ["시장 체제", "Distribution Day", "분배일"],
    "stock_picker": ["S-Score", "buy_score"],
    "trading_journalist": ["매매 회고", "trading_journalist"],
    "flow_analyzer": ["F-Score", "수급 점수"],
    "principle_guardian": ["compliant", "violation", "7계명"],
    "trader": ["T-Score", "타점 점수"],
    "stock_analyst": ["Module A", "F1~F5", "holding_period"],
}


@pytest.mark.parametrize("analyst_id", ALL_8_ANALYSTS)
def test_8_analyst_authority_keyword_other_negation(analyst_id: str) -> None:
    """타 분석가 권위 키워드가 본 persona 에 나오면 negation 컨텍스트 필수.

    정정 2 보조 — 각 분석가가 본인 권위 외 키워드 사용 시 위임·금지·발행 X 명시.
    예: trader persona 에 'F-Score' 나오면 주변에 'flow_analyzer' / '발행 X' / '권위' 등 있어야.
    """
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    negation_keywords = [
        "권위", "위임", "발행 X", "발행 금지", "금지", "본 분석가 영역 X",
        "X (", "권한 없음", "본인은", "보내", "넘긴", "안 함", "않는다",
        "frame 밖", "다른 분석가", "분석가 영역", "영역 X", "input", "read",
        "Cross-Agent Boundaries", "Inputs", "Input 으로", "참조", "트리거 조건",
        "트리거", "시나리오", "확률", "이행", "전환", "변화", "snapshot",
        analyst_id,  # 본인 ID 인접에서는 OK (격자 발행 § 등)
    ]

    for other_id, keywords in AUTHORITY_KEYWORDS.items():
        if other_id == analyst_id:
            continue
        for kw in keywords:
            if kw not in text:
                continue
            # 모든 등장 위치에서 negation 컨텍스트 또는 인접 분석가 ID 검증
            indices = [i for i in range(len(text)) if text[i : i + len(kw)] == kw]
            for idx in indices:
                surrounding = text[max(0, idx - 250) : idx + len(kw) + 250]
                # 해당 키워드 인접에 (a) 그 키워드의 진짜 발행자 ID 또는 (b) negation 키워드
                has_owner = other_id in surrounding
                has_negation = any(n in surrounding for n in negation_keywords)
                assert has_owner or has_negation, (
                    f"{analyst_id}: 타 분석가({other_id}) 권위 키워드 '{kw}' 등장 시 "
                    f"발행자 ID 또는 negation 컨텍스트 없음. 주변: ...{surrounding}..."
                )
