"""STRATEGY-TRACK-001 — Layer 3 전략가 호출 함수 단위 테스트.

대상:
- `load_strategist_spec(strategist_id)`: manifest + persona 로드 + dataclass 매핑
- `gather_analyst_scores(analyst_ids, target)`: team_outputs DB row 모음 (load_latest mock)
- `render_analyst_scores_block(scores)`: 분석가 점수 → markdown 양식 (발행 + 미발행)
- `_insert_analyst_scores_block(blocks, scores_md)`: RAG 직전 insert
- `run_strategist(...)`: end-to-end happy path (build_market_snapshot + compose + call_llm 모두 mock)

실 LLM / DB / Chroma 호출 X — 모두 monkeypatch.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

from core.contracts.team_output import StandardOutput

# core/strategist/__init__.py 의 re-export 가 `import core.strategist.run_strategist
# as strat_mod` 시 함수를 attribute 로 가로채는 문제 우회 (test_retrieve_categories.py
# 와 동일 패턴 — RESUME.md '테스트의 importlib 우회' 참조).
strat_mod = importlib.import_module("core.strategist.run_strategist")

StrategistNotFoundError = strat_mod.StrategistNotFoundError
_insert_analyst_scores_block = strat_mod._insert_analyst_scores_block
gather_analyst_scores = strat_mod.gather_analyst_scores
load_strategist_spec = strat_mod.load_strategist_spec
render_analyst_scores_block = strat_mod.render_analyst_scores_block
run_strategist = strat_mod.run_strategist


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_strategist_tree(root: Path, strategist_id: str = "track_test") -> Path:
    """`<root>/<strategist_id>/{persona.md, manifest.yaml}` 임시 트리 생성."""
    strat_dir = root / strategist_id
    strat_dir.mkdir(parents=True, exist_ok=True)
    (strat_dir / "persona.md").write_text(
        "# Track Test 전략가\n\nTest persona body.\n", encoding="utf-8"
    )
    (strat_dir / "manifest.yaml").write_text(
        f"""id: {strategist_id}
display_name: Track Test 전략가
track: T
reads_analysts:
  - stock_picker
  - stock_analyst
reads:
  - principles
canon_categories:
  - principles/philosophy_seven_commandments
llm:
  model: null
  max_tokens: 4000
  temperature: 0.4
response_rules: |
  Test response rules.
contract_version: "1.0"
""",
        encoding="utf-8",
    )
    return strat_dir


@pytest.fixture
def fake_strategists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _make_strategist_tree(tmp_path)
    monkeypatch.setattr(strat_mod, "STRATEGISTS_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# load_strategist_spec
# ---------------------------------------------------------------------------


def test_load_strategist_spec_returns_dataclass(fake_strategists: Path) -> None:
    spec = load_strategist_spec("track_test")
    assert spec.id == "track_test"
    assert spec.display_name == "Track Test 전략가"
    assert spec.track == "T"
    assert spec.reads_analysts == ["stock_picker", "stock_analyst"]
    assert spec.reads_depts == ["principles"]
    assert spec.canon_categories == ["principles/philosophy_seven_commandments"]
    assert spec.model is None
    assert spec.max_tokens == 4000
    assert spec.temperature == 0.4
    assert "Test response rules" in (spec.response_rules or "")
    assert spec.persona_path.exists()


def test_load_strategist_spec_missing_raises(fake_strategists: Path) -> None:
    with pytest.raises(StrategistNotFoundError):
        load_strategist_spec("non_existent")


# ---------------------------------------------------------------------------
# gather_analyst_scores
# ---------------------------------------------------------------------------


def _fake_output(team_id: str, target: str, verdict: str, confidence: int) -> StandardOutput:
    return StandardOutput.build(
        team_id=team_id,
        run_id=f"{team_id}-run-1",
        verdict=verdict,
        confidence=confidence,
        reasons=[f"{team_id} reason 1", f"{team_id} reason 2"],
        target=target,
        data={"score": confidence / 10.0, "tag": team_id},
    )


def test_gather_analyst_scores_mixed_published_and_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_load_latest(team_id: str, target: str = "global") -> StandardOutput | None:
        if team_id == "stock_picker":
            return _fake_output("stock_picker", target, "buy", 80)
        if team_id == "stock_analyst":
            return None  # 미발행
        return None

    monkeypatch.setattr(strat_mod, "load_latest", fake_load_latest)

    scores = gather_analyst_scores(
        ["stock_picker", "stock_analyst", "wealth_strategist"],
        target="005930",
    )

    assert scores["stock_picker"]["found"] is True
    assert scores["stock_picker"]["verdict"] == "buy"
    assert scores["stock_picker"]["confidence"] == 80
    assert scores["stock_picker"]["data"]["score"] == 8.0
    assert scores["stock_analyst"]["found"] is False
    assert scores["wealth_strategist"]["found"] is False


def test_gather_analyst_scores_db_error_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB 접근 실패해도 크래시 금지 — found=False + error 메시지 보존."""

    def fake_load_latest(team_id: str, target: str = "global") -> StandardOutput | None:
        raise RuntimeError("simulated db failure")

    monkeypatch.setattr(strat_mod, "load_latest", fake_load_latest)

    scores = gather_analyst_scores(["stock_picker"], target="global")
    assert scores["stock_picker"]["found"] is False
    assert "simulated db failure" in scores["stock_picker"]["error"]


# ---------------------------------------------------------------------------
# render_analyst_scores_block
# ---------------------------------------------------------------------------


def test_render_analyst_scores_block_published_and_missing() -> None:
    scores = {
        "stock_picker": {
            "found": True,
            "timestamp": "2026-05-18T10:00:00+09:00",
            "verdict": "buy",
            "confidence": 80,
            "reasons": ["RS Top 1", "외인 60일 +1.2조"],
            "data": {"s_score": 8.5},
        },
        "stock_analyst": {"found": False},
    }
    md = render_analyst_scores_block(scores)
    assert "## Analyst Scores (Layer 2" in md
    assert "### stock_picker" in md
    assert "verdict: buy" in md
    assert "confidence: 80" in md
    assert "s_score: 8.5" in md
    assert "### stock_analyst" in md
    assert "미발행" in md
    assert "cited_scores 해당 필드 = null" in md


def test_render_analyst_scores_block_empty_returns_header_only() -> None:
    md = render_analyst_scores_block({})
    assert "## Analyst Scores" in md  # 헤더는 늘 박힘
    # 분석가별 ### 헤더는 없어야
    assert "###" not in md


# ---------------------------------------------------------------------------
# _insert_analyst_scores_block
# ---------------------------------------------------------------------------


def test_insert_analyst_scores_block_before_rag() -> None:
    blocks = [
        {"type": "text", "text": "## Investment Knowledge (Canon)\nCANON"},
        {"type": "text", "text": "## Persona\nPERSONA"},
        {"type": "text", "text": "## Retrieved References\nCHUNK"},
        {"type": "text", "text": "## Response rules\nRULES"},
    ]
    out = _insert_analyst_scores_block(blocks, "## Analyst Scores\nSCORES")
    # RAG 직전에 insert (index 2)
    texts = [b["text"] for b in out]
    assert texts[0].startswith("## Investment Knowledge")
    assert texts[1].startswith("## Persona")
    assert texts[2].startswith("## Analyst Scores")
    assert texts[3].startswith("## Retrieved References")
    assert texts[4].startswith("## Response rules")


def test_insert_analyst_scores_block_no_rag_inserts_before_rules() -> None:
    blocks = [
        {"type": "text", "text": "## Investment Knowledge (Canon)\nCANON"},
        {"type": "text", "text": "## Persona\nPERSONA"},
        {"type": "text", "text": "## Response rules\nRULES"},
    ]
    out = _insert_analyst_scores_block(blocks, "## Analyst Scores\nSCORES")
    texts = [b["text"] for b in out]
    assert texts[-1].startswith("## Response rules")
    assert texts[-2].startswith("## Analyst Scores")


def test_insert_analyst_scores_block_empty_scores_unchanged() -> None:
    blocks = [{"type": "text", "text": "## Persona\nP"}]
    out = _insert_analyst_scores_block(blocks, "   ")
    assert out == blocks


# ---------------------------------------------------------------------------
# run_strategist (end-to-end happy path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_strategist_happy_path(
    fake_strategists: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """build_market_snapshot + compose.build_pipeline_prompt + call_llm 모두 mock.

    검증:
    - StrategistResponse.text 반환
    - metadata 에 strategist_id / track / target / analyst_published_count 채워짐
    - LLM 에 전달된 system blocks 안에 ## Analyst Scores 블록 포함
    """
    captured_call: dict[str, Any] = {}

    # snapshot mock
    class _FakeSnapshot:
        fetched_at = 0
        failures: dict = {}
        source_map: dict = {}
        db_run_ids: dict = {}

    async def fake_build_snapshot():
        return _FakeSnapshot(), True

    def fake_render(_snap):
        return "# Market snapshot fake"

    monkeypatch.setattr(strat_mod, "build_market_snapshot", fake_build_snapshot)
    monkeypatch.setattr(strat_mod, "render_snapshot_md", fake_render)

    # compose mock — 단순 블록 반환
    from core.contracts.knowledge import SystemPromptBundle

    async def fake_build_pipeline_prompt(**kwargs):
        captured_call["compose_kwargs"] = kwargs
        return SystemPromptBundle(
            blocks=[
                {"type": "text", "text": "## Persona\nP"},
                {"type": "text", "text": "## Response rules\nR"},
            ],
            cache_breakpoint_count=1,
        )

    monkeypatch.setattr(strat_mod, "build_pipeline_prompt", fake_build_pipeline_prompt)

    # load_latest mock — stock_picker 만 발행
    def fake_load_latest(team_id: str, target: str = "global"):
        if team_id == "stock_picker":
            return _fake_output("stock_picker", target, "buy", 80)
        return None

    monkeypatch.setattr(strat_mod, "load_latest", fake_load_latest)

    # call_llm mock
    async def fake_call_llm(*, system, messages, model, max_tokens, temperature, provider=None):
        captured_call["system_blocks"] = system
        captured_call["messages"] = messages
        captured_call["model"] = model
        captured_call["max_tokens"] = max_tokens
        captured_call["temperature"] = temperature
        return {
            "content": "권고 응답 본문 (mock)",
            "model": "test-model-mock",
            "tokens_in": 1234,
            "tokens_out": 567,
            "cost_usd": 0.001,
            "raw": {"mock": True},
        }

    monkeypatch.setattr(strat_mod, "call_llm", fake_call_llm)

    resp = await run_strategist(
        "track_test",
        [{"role": "user", "content": "long: 삼성전자 분석해줘"}],
        target="005930",
    )

    # 응답
    assert resp.text == "권고 응답 본문 (mock)"

    # metadata
    md = resp.metadata
    assert md["strategist_id"] == "track_test"
    assert md["track"] == "T"
    assert md["target"] == "005930"
    assert md["reads_analysts"] == ["stock_picker", "stock_analyst"]
    assert md["analyst_published_count"] == 1
    assert md["analyst_missing_count"] == 1
    assert md["analyst_missing_ids"] == ["stock_analyst"]
    assert md["is_mock"] is True
    assert md["tokens_in"] == 1234
    assert md["tokens_out"] == 567

    # system blocks 안에 분석가 점수 블록 박힘 (Response rules 직전)
    system_blocks = captured_call["system_blocks"]
    texts = [b["text"] for b in system_blocks]
    score_block_idx = next(
        i for i, t in enumerate(texts) if t.startswith("## Analyst Scores")
    )
    assert score_block_idx is not None
    # stock_picker 의 점수가 들어있어야
    assert "stock_picker" in texts[score_block_idx]
    assert "verdict: buy" in texts[score_block_idx]
    assert "confidence: 80" in texts[score_block_idx]
    # stock_analyst 는 미발행 표시
    assert "stock_analyst" in texts[score_block_idx]
    assert "미발행" in texts[score_block_idx]


@pytest.mark.asyncio
async def test_run_strategist_empty_messages_raises(fake_strategists: Path) -> None:
    with pytest.raises(ValueError, match="messages"):
        await run_strategist("track_test", [])
