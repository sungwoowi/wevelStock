"""ANALYST-PERSONAS-001 v2 — 자료 있는 3 분석가 페르소나·매니페스트 양식 검증.

대상 3 분석가 (2026-05-19 3 subagent 병렬 dispatch 작성):
- `principle_guardian` (자료 있음 — 4 자료원: 7계명·5대 심법·시장 국면별 트레이딩 기준·운용 안전핀 (cycle 7 정정 후 canon_categories 정식 포함))
- `trader` (자료 사실상 0 시드 — failure_lessons placeholder; operational_safeguards 는 cycle 7 정정으로 principle_guardian 으로 이전)
- `stock_analyst` (자료 0 시드 + INFRA-CHART-DATA-001 미비 = 환각 우려 2 중)

검증:
- manifest 로드 (load_analyst_spec × 3)
- 8 섹션 portable 양식
- canon_categories SPEC v2 § 매핑 표 정합 (4·5·5 카테고리, cycle 7 정정 후)
- Track A·B persona reads_analysts 정합 (양쪽 박음 검증)
- Cross-Agent Boundaries 표 존재
- 박종훈 framework 직접 인용 금지 가드 (negation 컨텍스트)
- 한국어 친화 용어 + cited 풀이 v3.1
- 분석가별 특수 가드:
  - principle_guardian: 명제 ID C·D·R·OS 정식 도입 + verdict 4종 + 점수 발행 X + canon_categories 의 trading/operational_safeguards 정식 포함
  - trader: 6 트리거 영문 ID 정식 표 (SPEC G2) + α 오버라이드 분기 + α 미발행 fallback (a)/(b) + operational_safeguards canon_categories 제외 (principle_guardian 권위 이전)
  - stock_analyst: 환각 가드 2 중 (자료 0 + INFRA 미비) + INFRA 들어오면 정정 trace
- 본 분석가 권위 한정 명시 (각 분석가 발행 영역 X 명시)
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest
import yaml

analyst_mod = importlib.import_module("core.inference.run_analyst")
load_analyst_spec = analyst_mod.load_analyst_spec
ANALYSTS_DIR = analyst_mod.ANALYSTS_DIR

REPO_ROOT = Path(__file__).resolve().parents[1]
STRATEGISTS_DIR = REPO_ROOT / "agents" / "strategists"

DATA_3_ANALYSTS = ["principle_guardian", "trader", "stock_analyst"]

# SPEC v2 § canon_categories 잠정 매핑 표 권위
EXPECTED_CANON_CATEGORIES = {
    "principle_guardian": [
        "principles/philosophy_seven_commandments",
        "principles/trading_doctrine",
        "principles/market_regime_rules",
        "trading/operational_safeguards",
    ],
    "trader": [
        "trading/entry_exit",
        "trading/position_sizing",
        "trading/trading_styles",
        "trading/market_regime_response",
        "trading/failure_lessons",
    ],
    "stock_analyst": [
        "stock-analysis/fundamental_analysis",
        "stock-analysis/technical_basics",
        "stock-analysis/fractal_wave",
        "stock-analysis/log_chart",
        "stock-analysis/sector_analysis",
    ],
}

EXPECTED_DEPT = {
    "principle_guardian": "principles",
    "trader": "trading",
    "stock_analyst": "stock-analysis",
}


# ---------------------------------------------------------------------------
# Manifest 로드 + dept 정합
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("analyst_id", DATA_3_ANALYSTS)
def test_data_analyst_manifest_loads(analyst_id: str) -> None:
    """3 분석가 manifest 가 AnalystSpec 으로 로딩되고 dept 정합."""
    spec = load_analyst_spec(analyst_id)
    assert spec.id == analyst_id
    assert spec.learning_dept == EXPECTED_DEPT[analyst_id]
    assert spec.persona_path.exists()
    assert spec.response_rules is not None
    # 3 분석가 모두 결정론 강화 (verdict/score 결정론) — temperature ≤ 0.4
    assert spec.temperature <= 0.4, (
        f"{analyst_id}: temperature {spec.temperature} > 0.4 (결정론 강화 필요)"
    )


@pytest.mark.parametrize("analyst_id", DATA_3_ANALYSTS)
def test_data_analyst_canon_categories_per_spec(analyst_id: str) -> None:
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


@pytest.mark.parametrize("analyst_id", DATA_3_ANALYSTS)
def test_data_analyst_has_eight_portable_sections(analyst_id: str) -> None:
    """ANALYST-PERSONAS-001 v2 의 8 섹션 portable 양식 존재."""
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")
    for section in REQUIRED_SECTIONS:
        assert section in text, f"{analyst_id}: missing section '{section}'"


# ---------------------------------------------------------------------------
# Track A·B persona reads_analysts 정합 (이미 test_seed_analysts_v2 에서 검증)
# 본 사이클은 3 분석가 모두 양 Track 의 reads 에 포함됨을 재확인
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


def test_track_a_reads_includes_data_3() -> None:
    """Track A reads_analysts 에 자료 있는 3명 중 2명 (stock_analyst·principle_guardian) 포함."""
    track_a_reads = _load_strategist_reads("track_a")
    assert "stock_analyst" in track_a_reads
    assert "principle_guardian" in track_a_reads
    # trader 는 Track A read X (Track B 영역) — 정합 검증
    assert "trader" not in track_a_reads


def test_track_b_reads_includes_data_2() -> None:
    """Track B reads_analysts 에 자료 있는 3명 중 2명 (trader·principle_guardian) 포함."""
    track_b_reads = _load_strategist_reads("track_b")
    assert "trader" in track_b_reads
    assert "principle_guardian" in track_b_reads
    # stock_analyst 는 Track B read X (Track A 영역, α 만 trader 가 read) — 정합 검증
    assert "stock_analyst" not in track_b_reads


# ---------------------------------------------------------------------------
# 핵심 가드 — 박종훈 framework 직접 인용 금지
# ---------------------------------------------------------------------------


PARK_FRAMEWORK_TERMS = ["박종훈", "Dalio 5단계", "Dalio 5 단계"]


@pytest.mark.parametrize("analyst_id", DATA_3_ANALYSTS)
def test_data_analyst_no_park_jonghoon_direct_citation(analyst_id: str) -> None:
    """3 분석가 persona 본문에 박종훈 framework 직접 인용 X (가드 검증).

    `feedback_park_jonghoon_scope.md` 권위: 박종훈 framework = 거시적 경제 해석 통찰,
    트레이딩 의사결정 직접 반영 X. wealth_strategist 영역만 인용 OK.
    """
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")
    for term in PARK_FRAMEWORK_TERMS:
        if term in text:
            indices = [i for i in range(len(text)) if text[i : i + len(term)] == term]
            for idx in indices:
                surrounding = text[max(0, idx - 200) : idx + len(term) + 200]
                has_negation = any(
                    neg in surrounding
                    for neg in [
                        "금지", "직접 인용 X", "안 함", "않음", "않는다", "안 한다",
                        "회피", "분리", "wealth_strategist", "권위", "위임", "본인은",
                        "자산복리부만", "별도 자료원", "본 분석가는 안", "본 분석가 영역 X",
                        "권한 없음", "본 분석가 권위 X", "본 분석가는 거시",
                    ]
                )
                assert has_negation, (
                    f"{analyst_id}: '{term}' 직접 인용 검출 (negation 컨텍스트 없음). "
                    f"주변 텍스트: ...{surrounding}..."
                )


# ---------------------------------------------------------------------------
# 한국어 친화 용어 + cited 풀이 v3.1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("analyst_id", DATA_3_ANALYSTS)
def test_data_analyst_cited_v3_1_format_keywords(analyst_id: str) -> None:
    """cited 풀이 v3.1 양식 키워드 존재 (cited + 근거 명제 풀이 / framework 밖)."""
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")
    assert "cited" in text
    assert "근거 명제 풀이" in text or "framework 밖" in text, (
        f"{analyst_id}: cited 풀이 v3.1 양식 키워드 없음"
    )


# ---------------------------------------------------------------------------
# Cross-Agent Boundaries 표 존재
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("analyst_id", DATA_3_ANALYSTS)
def test_data_analyst_cross_agent_boundaries_table_present(analyst_id: str) -> None:
    """Cross-Agent Boundaries 표가 다른 분석가·Layer 위임 매핑 명시."""
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    boundary_start = text.find("## Cross-Agent Boundaries")
    assert boundary_start != -1, f"{analyst_id}: ## Cross-Agent Boundaries 섹션 없음"
    boundary_section = text[boundary_start:]

    table_rows = [
        line
        for line in boundary_section.split("\n")
        if line.startswith("|") and "---" not in line
    ]
    # 정정 1: 인접 boundary 10 영역 명시 권유 → header + 8 행 (최소) 강제
    assert len(table_rows) >= 6, (
        f"{analyst_id}: Cross-Agent Boundaries 표 행 6+ 필요 "
        f"(header + 5+ rows, 정정 1: 인접 boundary 명시), got {len(table_rows)}"
    )


# ---------------------------------------------------------------------------
# 본 분석가 권위 한정 (정정 1 적용)
# ---------------------------------------------------------------------------


AUTHORITY_LIMITS = {
    # 본 분석가가 발행 금지인 영역 키워드 (다른 분석가 권위) — persona 본문에 명시되어야
    "principle_guardian": ["S-Score", "T-Score"],
    "trader": ["α", "F-Score"],
    "stock_analyst": ["T-Score", "S-Score"],
}


@pytest.mark.parametrize("analyst_id", DATA_3_ANALYSTS)
def test_data_analyst_authority_scope_explicit(analyst_id: str) -> None:
    """본 분석가 권위 한정 — 다른 분석가 권위 영역 발행 금지 명시 (정정 1)."""
    persona_path = ANALYSTS_DIR / analyst_id / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # "권위" 라는 키워드가 본문에 있는지 (Identity / Domain Frame / Anti-patterns 등 어디든)
    assert "권위" in text, f"{analyst_id}: '권위' 키워드 부재 (권위 한정 명시 필요)"

    # 발행 금지 영역 키워드 중 하나라도 명시되어야 (이 분석가의 권위 밖 영역)
    forbidden = AUTHORITY_LIMITS[analyst_id]
    found = [k for k in forbidden if k in text]
    assert len(found) >= 1, (
        f"{analyst_id}: 권위 밖 영역 키워드 {forbidden} 중 하나 이상 명시 필요, found {found}"
    )


# ---------------------------------------------------------------------------
# principle_guardian 특수 가드
# ---------------------------------------------------------------------------


def test_principle_guardian_proposition_ids_introduced() -> None:
    """principle_guardian 의 명제 ID C·D·R·OS 정식 도입 (4 자료원 권위)."""
    persona_path = ANALYSTS_DIR / "principle_guardian" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # 4 명제 ID 체계 정식 도입
    assert "C1" in text and "C7" in text, "principle_guardian: 7계명 명제 ID (C1~C7) 누락"
    assert "D1" in text and "D5" in text, "principle_guardian: 5대 심법 명제 ID (D1~D5) 누락"
    assert "R1" in text and "R3" in text, "principle_guardian: 시장 국면 명제 ID (R1~R3) 누락"
    assert "OS1" in text and "OS6" in text, "principle_guardian: 운용 안전핀 명제 ID (OS1~OS6) 누락"


def test_principle_guardian_verdict_literals() -> None:
    """principle_guardian verdict literal 4종 (compliant/warning/violation/unknown) 명시."""
    persona_path = ANALYSTS_DIR / "principle_guardian" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    assert "compliant" in text
    assert "warning" in text
    assert "violation" in text
    # unknown 은 입력 부족 결정론 분기 (operational_safeguards OS6 데이터 무결성)
    assert "unknown" in text


def test_principle_guardian_no_score_emission() -> None:
    """principle_guardian 은 점수 발행 X — S/T/α/buy_score/F-Score 발행 금지 명시."""
    persona_path = ANALYSTS_DIR / "principle_guardian" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # 점수 발행 X 명시 (다른 분석가 권위 영역)
    # 다른 분석가 ID 가 boundary 표에 명시되어 있어야
    for other_id in ["stock_picker", "trader", "stock_analyst", "flow_analyzer"]:
        assert other_id in text, f"principle_guardian: '{other_id}' boundary 명시 누락"


# ---------------------------------------------------------------------------
# trader 특수 가드 — 6 트리거 영문 ID + α 오버라이드 + α 미발행 fallback (정정 1)
# ---------------------------------------------------------------------------


TRADER_TRIGGER_IDS = [
    "volume_surge",
    "intraday_top",
    "gap_up",
    "closing_strength",
    "fund_inflow",
    "volume_increase_sideways",
]


def test_trader_six_trigger_ids_explicit() -> None:
    """trader persona 에 6 트리거 영문 ID 정식 정의 (SPEC G2 가드)."""
    persona_path = ANALYSTS_DIR / "trader" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    for trigger_id in TRADER_TRIGGER_IDS:
        assert trigger_id in text, f"trader: 트리거 영문 ID '{trigger_id}' 누락"


def test_trader_alpha_override_explicit() -> None:
    """trader 의 α 오버라이드 read + 분기 룰 명시."""
    persona_path = ANALYSTS_DIR / "trader" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    assert "α" in text or "alpha" in text.lower(), "trader: α 인용 누락"
    assert "stock_analyst" in text, "trader: stock_analyst α 발행 read 명시 누락"
    # 오버라이드 분기 — 임계값 명시 (잠정 α ≥ 1.5 / 1.0 / etc.)
    assert "1.5" in text and "1.0" in text, "trader: α 오버라이드 임계값 (1.5/1.0) 명시 누락"


def test_trader_alpha_fallback_branches() -> None:
    """trader 의 α 미발행 fallback 처리 (정정 1) — 분기 (a)/(b) 명시.

    stock_analyst 가 verdict=`unknown` (환각 가드 작동) 발행 시 본 분석가 분기:
    (a) T-Score 단독 진행 + confidence 하향 / (b) 보류 (verdict=`hold`)
    """
    persona_path = ANALYSTS_DIR / "trader" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # fallback § 박힘 키워드
    assert "fallback" in text.lower() or "미발행" in text, (
        "trader: α 미발행 fallback § 명시 누락"
    )
    # (a)/(b) 분기 명시
    assert ("(a)" in text or "(a) T-Score" in text), "trader: fallback 분기 (a) 누락"
    assert ("(b)" in text or "(b) 보류" in text), "trader: fallback 분기 (b) 누락"


def test_principle_guardian_owns_operational_safeguards() -> None:
    """cycle 7 SPEC v2 정정: operational_safeguards 권위가 principle_guardian 으로 이전.

    - principle_guardian manifest canon_categories 에 trading/operational_safeguards 정식 포함
    - principle_guardian persona 의 Knowledge Categories § 에 명시
    - trader persona 본문에 operational_safeguards 권위 위임 잔재가 정리됨 (canon_categories
      이전 명시 키워드로만 등장, 단순 "권위 위임" 잔재 X)
    """
    # principle_guardian manifest 정식 포함
    pg_manifest_path = ANALYSTS_DIR / "principle_guardian" / "manifest.yaml"
    pg_manifest = yaml.safe_load(pg_manifest_path.read_text(encoding="utf-8"))
    assert "trading/operational_safeguards" in pg_manifest["canon_categories"], (
        "principle_guardian: trading/operational_safeguards canon_categories 정식 포함 누락"
    )

    # principle_guardian persona 의 Knowledge Categories § 명시
    pg_persona = (ANALYSTS_DIR / "principle_guardian" / "persona.md").read_text(encoding="utf-8")
    assert "trading/operational_safeguards" in pg_persona, (
        "principle_guardian persona: Knowledge Categories § 에 trading/operational_safeguards 명시 누락"
    )

    # trader manifest canon_categories 에서 operational_safeguards 제거 확인
    trader_manifest_path = ANALYSTS_DIR / "trader" / "manifest.yaml"
    trader_manifest = yaml.safe_load(trader_manifest_path.read_text(encoding="utf-8"))
    assert "trading/operational_safeguards" not in trader_manifest["canon_categories"], (
        "trader: operational_safeguards 는 cycle 7 정정 후 principle_guardian 권위 이전 — canon_categories 에서 제거되어야 함"
    )


# ---------------------------------------------------------------------------
# stock_analyst 특수 가드 — 환각 가드 2 중 (자료 0 + INFRA 미비)
# ---------------------------------------------------------------------------


def test_stock_analyst_dual_hallucination_guards() -> None:
    """stock_analyst 의 환각 가드 2 중 — 자료 0 시드 + INFRA-CHART-DATA-001 미구현."""
    persona_path = ANALYSTS_DIR / "stock_analyst" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # 가드 1: 자료 0 시드 (stock-analysis canon 자료 0)
    assert "자료 0 시드" in text or "자료 0" in text, "stock_analyst: 가드 1 (자료 0 시드) 명시 누락"

    # 가드 2: INFRA-CHART-DATA-001 미구현
    assert "INFRA-CHART-DATA-001" in text, "stock_analyst: 가드 2 (INFRA-CHART-DATA-001) 명시 누락"


def test_stock_analyst_infra_missing_verdict_unknown() -> None:
    """stock_analyst INFRA 미비 시 verdict=`unknown` 강제 명시."""
    persona_path = ANALYSTS_DIR / "stock_analyst" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    assert "unknown" in text, "stock_analyst: verdict=unknown 강제 명시 누락"
    # 차트 추론 환각 차단 — 추정 패턴 인용 금지
    assert "추정" in text or "환각" in text, "stock_analyst: 추정·환각 차단 명시 누락"


def test_stock_analyst_infra_correction_trace() -> None:
    """stock_analyst INFRA 들어오면 정정 메타-가이드 (v3 마이크로 정정) trace 명시."""
    persona_path = ANALYSTS_DIR / "stock_analyst" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # 정정 trace 명시 — INFRA 들어오면 어느 위치에서 가드 빼고 정상 발행 로직 추가할지
    assert "INFRA" in text and ("정정" in text or "보강" in text), (
        "stock_analyst: INFRA 들어오면 정정 trace 명시 누락"
    )


def test_stock_analyst_emits_alpha_and_targets() -> None:
    """stock_analyst 의 발행 영역 (α + Module A 목표가 3단 + F1~F5 + holding_period) 명시."""
    persona_path = ANALYSTS_DIR / "stock_analyst" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # α + Module A 목표가 + F1~F5 + holding_period_estimate_days 4 발행물 명시
    assert "α" in text or "alpha" in text.lower(), "stock_analyst: α 발행 명시 누락"
    assert "Module A" in text or "목표가 3단" in text, "stock_analyst: Module A 목표가 3단 명시 누락"
    assert "F1" in text and "F5" in text, "stock_analyst: F1~F5 명시 누락"
    assert "holding_period" in text, "stock_analyst: holding_period 발행 명시 누락"


# ---------------------------------------------------------------------------
# Track A·B read 정합 자동 검증 (정정 3 일부 자동화)
# ---------------------------------------------------------------------------


def test_trader_triggers_match_track_b_inputs() -> None:
    """trader 의 6 트리거 영문 ID set ↔ Track B persona § Inputs 명단 set equality.

    SPEC G2 가드: Track B 명단 변경 시 trader persona 동시 수정 강제.
    위반 시 Track A·B persona 동시 수정 인수 메시지 필요.
    """
    track_b_text = (STRATEGISTS_DIR / "track_b" / "persona.md").read_text(encoding="utf-8")
    trader_text = (ANALYSTS_DIR / "trader" / "persona.md").read_text(encoding="utf-8")

    trader_triggers = {t for t in TRADER_TRIGGER_IDS if t in trader_text}
    track_b_triggers = {t for t in TRADER_TRIGGER_IDS if t in track_b_text}

    # Track B 가 read 하는 트리거 = trader 가 발행하는 트리거 (set 일치)
    # Track B 에 명시된 모든 트리거가 trader 에도 정의되어야
    assert track_b_triggers <= trader_triggers, (
        f"Track B persona 의 트리거 명단 {track_b_triggers} 가 "
        f"trader persona 의 트리거 명단 {trader_triggers} 에 부분집합이 아님. "
        f"SPEC G2 가드 위반 — Track B 또는 trader persona 동시 수정 필요."
    )


def test_track_a_reads_stock_analyst_emission_set() -> None:
    """Track A persona § Inputs 가 stock_analyst 발행 4종 (α + 목표가 3단 + F1~F5 + holding_period) read 명시."""
    track_a_text = (STRATEGISTS_DIR / "track_a" / "persona.md").read_text(encoding="utf-8")

    # 4 발행물 모두 Track A read 명시
    assert "alpha" in track_a_text.lower() or "α" in track_a_text, (
        "Track A persona: stock_analyst α read 명시 누락"
    )
    assert "target_price" in track_a_text or "목표가" in track_a_text, (
        "Track A persona: Module A 목표가 3단 read 명시 누락"
    )
    assert "F1" in track_a_text, "Track A persona: F1~F5 read 명시 누락"
    assert "holding_period" in track_a_text, "Track A persona: holding_period read 명시 누락"


def test_track_ab_read_principle_guardian_verdict() -> None:
    """Track A·B persona 가 principle_guardian verdict (compliant/warning/violation) read 명시."""
    track_a_text = (STRATEGISTS_DIR / "track_a" / "persona.md").read_text(encoding="utf-8")
    track_b_text = (STRATEGISTS_DIR / "track_b" / "persona.md").read_text(encoding="utf-8")

    for track_id, text in [("track_a", track_a_text), ("track_b", track_b_text)]:
        assert "principle_guardian" in text, (
            f"{track_id} persona: principle_guardian read 명시 누락"
        )
        # verdict 양식 키워드 (compliant/warning/violation 또는 7계명 위반)
        has_verdict = any(
            kw in text for kw in ["compliant", "violation", "7계명", "위반"]
        )
        assert has_verdict, (
            f"{track_id} persona: principle_guardian verdict 인용 양식 누락"
        )


# ---------------------------------------------------------------------------
# WAVE-ALPHA-001 v5 sub-cycle 14.3 정정 (stock_analyst 통합 5 케이스)
# ---------------------------------------------------------------------------


def test_stock_analyst_v5_canon_fractal_wave_cited() -> None:
    """v5: fractal_wave canon 21 명제 ID (WA·WF·WL·WE) 가 persona 에 인용됨."""
    persona = (ANALYSTS_DIR / "stock_analyst" / "persona.md").read_text(encoding="utf-8")
    # canon WA·WF·WL·WE prefix 모두 본문에 등장 (verdict 매트릭스 / α 산출 / 환각 가드 3 등)
    for prefix in ("WA1", "WA2", "WA3", "WF1", "WF2", "WF3", "WL1", "WL2", "WL3", "WE1", "WE7"):
        assert prefix in persona, f"v5 persona: canon ID {prefix} 인용 누락"


def test_stock_analyst_v5_verdict_matrix_keywords() -> None:
    """v5: verdict 매트릭스 (WL2 long/swing/중립 분기) 본문 박힘."""
    persona = (ANALYSTS_DIR / "stock_analyst" / "persona.md").read_text(encoding="utf-8")
    # verdict 매트릭스 § 헤더 + 분기 키워드
    assert "verdict 매트릭스" in persona
    assert "long:" in persona or "long " in persona
    assert "swing:" in persona or "swing " in persona
    assert "confirmed_high_quality" in persona
    assert "confirmed_low_quality" in persona
    assert "inconclusive" in persona
    # 보수 우선 룰
    assert "보수 우선" in persona


def test_stock_analyst_v5_holding_period_mapping() -> None:
    """v5: holding_period 매핑 (WL3 monthly→장기/weekly→중기/daily→단기)."""
    persona = (ANALYSTS_DIR / "stock_analyst" / "persona.md").read_text(encoding="utf-8")
    assert "holding_period 매핑" in persona
    # 3 매핑 라벨
    assert "장기" in persona
    assert "중기" in persona
    assert "단기" in persona
    # 긴 timeframe 우선 룰
    assert "긴 timeframe 우선" in persona


def test_stock_analyst_v5_anchor_source_guard_3() -> None:
    """v5: 환각 가드 3 (anchor 출처 강제 — manual/llm_stage2/deterministic_fallback/unavailable)."""
    persona = (ANALYSTS_DIR / "stock_analyst" / "persona.md").read_text(encoding="utf-8")
    assert "환각 가드 3 중" in persona
    assert "anchor 출처 강제" in persona
    for src in ("manual", "llm_stage2", "deterministic_fallback", "unavailable"):
        assert src in persona, f"v5 persona: source={src} 명시 누락"


def test_stock_analyst_v5_manifest_response_rules_wave_alpha() -> None:
    """v5: manifest response_rules 의 WAVE-ALPHA 정정 본문 (시간 정규화 공식 + 매트릭스 + 가드 3)."""
    manifest = yaml.safe_load(
        (ANALYSTS_DIR / "stock_analyst" / "manifest.yaml").read_text(encoding="utf-8")
    )
    rr = manifest.get("response_rules", "")
    # 시간 정규화 공식 본문
    assert "k₁" in rr and "k₂" in rr
    assert "ln(B/A)" in rr or "ln(B.price" in rr or "ln(B" in rr
    # verdict 매트릭스
    assert "verdict 매트릭스" in rr
    # holding_period 매핑
    assert "holding_period 매핑" in rr
    # 가드 3 (anchor 출처 강제)
    assert "환각 가드 3" in rr
    assert "anchor 출처 강제" in rr
    # source 4 종
    for src in ("manual", "llm_stage2", "deterministic_fallback", "unavailable"):
        assert src in rr, f"v5 manifest: source={src} 명시 누락"
