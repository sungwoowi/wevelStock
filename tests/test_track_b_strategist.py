"""STRATEGY-TRACK-001 — Track B 페르소나·매니페스트 양식 검증.

대상:
- `agents/strategists/track_b/manifest.yaml` 로딩 (load_strategist_spec)
- `agents/strategists/track_b/persona.md` 8 섹션 양식 존재
- `input_routing` 블록 정합 (swing:/short:/trigger: + fallback=false + auto.conditions)

Track A 는 `test_run_strategist.py` 가 fake_strategists fixture 로 검증 (실 manifest 무관).
본 파일은 Track B 실 manifest/persona 의 SPEC 정합만 검증 — 회귀 baseline.
"""
from __future__ import annotations

import importlib

import pytest
import yaml

from core.contracts.team_output import StandardOutput

strat_mod = importlib.import_module("core.strategist.run_strategist")
load_strategist_spec = strat_mod.load_strategist_spec
STRATEGISTS_DIR = strat_mod.STRATEGISTS_DIR


# ---------------------------------------------------------------------------
# manifest.yaml 정합
# ---------------------------------------------------------------------------


def test_track_b_manifest_loads() -> None:
    """Track B manifest 가 StrategistSpec 으로 로딩되고 SPEC 정합."""
    spec = load_strategist_spec("track_b")
    assert spec.id == "track_b"
    assert spec.display_name == "Track B 프랙탈 1 파 전략가"  # 2026-05-19 본질 표기 갱신 (기간 어휘 폐기)
    assert spec.track == "B"
    # SPEC L152-157 reads_analysts 5명
    assert spec.reads_analysts == [
        "stock_picker",
        "trader",
        "market_state_analyzer",
        "flow_analyzer",
        "principle_guardian",
    ]
    # canon_categories 3개 (시장 체제 + 트레이딩 doctrine + 운영 안전장치)
    assert spec.canon_categories == [
        "principles/market_regime_rules",
        "principles/trading_doctrine",
        "trading/operational_safeguards",
    ]
    assert spec.reads_depts == ["trading", "principles"]
    # llm 결정론 강화
    assert spec.temperature == 0.4
    assert spec.max_tokens == 5000
    assert spec.response_rules is not None
    assert "Track B" not in spec.response_rules or "단기" in spec.response_rules or "swing" in spec.response_rules.lower()


def test_track_b_manifest_input_routing() -> None:
    """input_routing 블록 정합 — STRATEGY-TRACK-001 § Track Selector L210-216 권위."""
    manifest_path = STRATEGISTS_DIR / "track_b" / "manifest.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    routing = raw["input_routing"]

    # 명시 단축어 3개 (swing: / short: / trigger:)
    shortcuts = routing["shortcuts"]["explicit"]
    assert "swing:" in shortcuts
    assert "short:" in shortcuts
    assert "trigger:" in shortcuts

    # auto.conditions = any_trigger_fired (분석가 v2 후 활성, v1 placeholder)
    auto_conditions = routing["auto"]["conditions"]
    assert any(
        isinstance(c, dict) and c.get("any_trigger_fired") is True for c in auto_conditions
    )

    # fallback=false (Track A 가 fallback default)
    assert routing["fallback"] is False


def test_track_b_manifest_response_rules_has_required_fields() -> None:
    """response_rules 가 권고 양식 필수 필드 + Track B 본질 룰 명시."""
    spec = load_strategist_spec("track_b")
    rules = spec.response_rules or ""

    # 권고 양식 필수 키워드
    assert "strategist-recommendation-v1" in rules
    assert "track=\"B\"" in rules or 'track="B"' in rules
    assert "yesterday_verdict_delta" in rules
    assert "triggers_fired" in rules
    assert "trailing_stop" in rules

    # 한국어 친화 용어 강제
    assert "타점 점수" in rules
    assert "매수 점수" in rules

    # cited 풀이 v3.1
    assert "v3.1" in rules
    assert "근거 명제 풀이" in rules

    # Track B 본질 룰
    assert "-7%" in rules  # 절대 매도
    assert "trailing stop 내림 금지" in rules or "일방향 래칫" in rules or "trailing" in rules.lower()


# ---------------------------------------------------------------------------
# persona.md 8 섹션 양식 존재
# ---------------------------------------------------------------------------


def test_track_b_persona_has_eight_portable_sections() -> None:
    """ANALYST-PERSONAS-001 v2 의 8 섹션 portable 양식 — Track A 와 동형."""
    persona_path = STRATEGISTS_DIR / "track_b" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # 8 섹션 헤더 존재 (ANALYST-PERSONAS-001 portable 양식)
    expected_sections = [
        "## Identity",
        "## Domain Frame",
        "## Inputs",
        "## Outputs",
        "## Reasoning Doctrine",
        "## Knowledge Categories",
        "## Anti-patterns",
        "## Cross-Agent Boundaries",
    ]
    for section in expected_sections:
        assert section in text, f"missing section: {section}"


def test_track_b_persona_has_essential_concepts() -> None:
    """Track B 본질 (카페 운영 / 1주~3개월 / 6 트리거 / Distribution kill switch / trailing stop / -7%) 존재."""
    persona_path = STRATEGISTS_DIR / "track_b" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    # 본질 키워드
    assert "카페" in text  # 비유
    assert "20-30%" in text  # 자본 비중
    assert "R/R" in text  # 손익비 게임
    assert "6 가지 트리거" in text or "6 트리거" in text
    assert "Distribution Day" in text
    assert "trailing stop" in text.lower() or "Trailing" in text
    assert "-7%" in text  # 절대 매도
    assert "일방향 래칫" in text


def test_track_b_persona_anti_patterns_block_long_term() -> None:
    """Track B 페르소나가 추세 추적 권고 / 월봉 위계 차단 룰 명시 (Track A frame 침범 방지).

    2026-05-19 본질 재정의: "중장기 권고 금지" → "추세 추적 권고 금지" (기간 기준 → 전략 본질 기준).
    """
    persona_path = STRATEGISTS_DIR / "track_b" / "persona.md"
    text = persona_path.read_text(encoding="utf-8")

    assert "추세 추적 권고 금지" in text  # 본질 재정의 후 새 anti-pattern 키워드
    assert "월봉" in text  # 월봉 위계 인용 금지 룰
    assert "1 파 완성 후" in text or "1 파 완성 후에도" in text  # 추세 인계 메커니즘 자각


# ---------------------------------------------------------------------------
# run_strategist metadata (Track B 호출 시 track="B" 정합)
# ---------------------------------------------------------------------------


def _fake_output(team_id: str, target: str, verdict: str, confidence: int) -> StandardOutput:
    return StandardOutput.build(
        team_id=team_id,
        run_id=f"{team_id}-run-1",
        verdict=verdict,
        confidence=confidence,
        reasons=[f"{team_id} reason"],
        target=target,
        data={"score": confidence / 10.0},
    )


@pytest.mark.asyncio
async def test_run_strategist_track_b_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Track B 호출 시 metadata.track="B" + reads_analysts 5명 정합 (실 manifest 사용)."""

    class _FakeSnapshot:
        fetched_at = 0
        failures: dict = {}
        source_map: dict = {}
        db_run_ids: dict = {}

    async def fake_build_snapshot():
        return _FakeSnapshot(), True

    monkeypatch.setattr(strat_mod, "build_market_snapshot", fake_build_snapshot)
    monkeypatch.setattr(strat_mod, "render_snapshot_md", lambda _s: "# Market snapshot fake")

    from core.contracts.knowledge import SystemPromptBundle

    async def fake_build_pipeline_prompt(**kwargs):
        return SystemPromptBundle(
            blocks=[
                {"type": "text", "text": "## Persona\nP"},
                {"type": "text", "text": "## Response rules\nR"},
            ],
            cache_breakpoint_count=1,
        )

    monkeypatch.setattr(strat_mod, "build_pipeline_prompt", fake_build_pipeline_prompt)

    def fake_load_latest(team_id: str, target: str = "global"):
        if team_id == "trader":
            return _fake_output("trader", target, "buy", 70)
        return None

    monkeypatch.setattr(strat_mod, "load_latest", fake_load_latest)

    async def fake_call_llm(*, system, messages, model, max_tokens, temperature,
                            provider=None, mock_fallback_allowed=True, **_kw):
        return {
            "content": "Track B 응답 (mock)",
            "model": "test-mock",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost_usd": 0.0001,
            "raw": {"mock": True},
        }

    monkeypatch.setattr(strat_mod, "call_llm", fake_call_llm)

    resp = await strat_mod.run_strategist(
        "track_b",
        [{"role": "user", "content": "swing: 삼성전자"}],
        target="005930",
    )

    assert resp.text == "Track B 응답 (mock)"
    md = resp.metadata
    assert md["strategist_id"] == "track_b"
    assert md["track"] == "B"
    assert md["target"] == "005930"
    assert len(md["reads_analysts"]) == 5
    assert md["analyst_published_count"] == 1  # trader 만 발행
    assert md["analyst_missing_count"] == 4
    assert set(md["analyst_missing_ids"]) == {
        "stock_picker",
        "market_state_analyzer",
        "flow_analyzer",
        "principle_guardian",
    }
