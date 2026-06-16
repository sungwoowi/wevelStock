"""PAPER-TRADING-001 (RB-MS2) M1 — 전략가 권고 구조화 파싱 + 영속/조회 테스트.

전략가 persona 가 이미 발행하는 strategist-recommendation-v1 YAML 블록을 파싱해
StrategistRecommendation 으로 구조화하고 team_outputs 에 영속/조회한다 (C 결정).
"""
from __future__ import annotations

import pytest

from core.db.connection import Database, reset_db
from core.strategist import recommendation
from core.strategist.recommendation import (
    StrategistRecommendation,
    load_active_recommendations,
    parse_recommendation,
    persist_recommendation,
    persist_strategist_recommendations,
)

# Track B 전략가 출력 — YAML 블록 + 자연어 보충 (실제 발행 형태)
SAMPLE_B = """분석 결과 매수 권고합니다.

```yaml
recommendation_id: REC-20260609-005930-B
date: 2026-06-09
ticker: "005930"
display_name: "삼성전자"
track: B
verdict: "buy"
entry_price: 68000
target_price_1: 74000
target_price_2: null
target_price_3: null
stop_loss: 65000
risk_reward: 2.0
cited_scores:
  buy_score: 7
  t_score: 7
  f_score: 6
  s_score: null
  alpha: 1.6
confidence: 75
reasons:
  - "타점 점수 7 — 거래량 급증 트리거"
  - "매수 점수 7 — CAN SLIM 통과"
data:
  market_regime: "strong_bull"
  triggers_fired: ["volume_surge"]
contract_version: "1.0"
```

자연어 보충: 6 트리거 중 거래량 급증이 발동했고 R/R 2.0 으로 strong_bull floor 통과.
"""

# Track A — 목표가 3단 사용
SAMPLE_A = """중장기 진입 권고.

```yaml
recommendation_id: REC-20260609-005930-A
date: 2026-06-09
ticker: "005930"
display_name: "삼성전자"
track: A
verdict: "buy"
entry_price: 68000
target_price_1: 80000
target_price_2: 92000
target_price_3: 105000
stop_loss: 62000
risk_reward: 3.2
cited_scores:
  s_score: 8.5
  alpha: 1.6
  f_score: 7
confidence: 80
reasons:
  - "S-Score 8.5 — 월봉 7월선 위"
data:
  market_regime: "strong_bull"
contract_version: "1.0"
```
"""


# ---------------------------------------------------------------------------
# parse_recommendation — 순수 함수
# ---------------------------------------------------------------------------


def test_parse_track_b_extracts_core_fields():
    rec = parse_recommendation(SAMPLE_B)
    assert rec is not None
    assert rec.recommendation_id == "REC-20260609-005930-B"
    assert rec.ticker == "005930"
    assert rec.track == "B"
    assert rec.verdict == "buy"
    assert rec.entry_price == 68000
    assert rec.stop_loss == 65000


def test_parse_track_b_single_target():
    # Track B 는 target_price_1 만 — null 차수는 targets 에서 제외
    rec = parse_recommendation(SAMPLE_B)
    assert rec.target_prices == [74000]


def test_parse_track_a_three_targets():
    rec = parse_recommendation(SAMPLE_A)
    assert rec.target_prices == [80000, 92000, 105000]
    assert rec.risk_reward == pytest.approx(3.2)


def test_parse_cited_scores_preserved():
    rec = parse_recommendation(SAMPLE_B)
    assert rec.cited_scores["buy_score"] == 7
    assert rec.cited_scores["t_score"] == 7
    assert rec.cited_scores["s_score"] is None


# ---------------------------------------------------------------------------
# 다단 트레이드 플랜 (TRADE-PLAN-LIFECYCLE-001 B-MS1) — 가산 파싱, 하위호환
# ---------------------------------------------------------------------------

SAMPLE_MULTI_LEVEL = """다단 플랜 매수 권고.

```yaml
recommendation_id: REC-20260616-000660-A
date: 2026-06-16
ticker: "000660"
display_name: "SK하이닉스"
track: A
verdict: "buy"
entry_price: 10000
target_price_1: 11000
target_price_2: 12500
stop_loss: 9500
risk_reward: 2.0
scaled_buy:
  - {leg: 1, price: 10000, ratio: 0.6}
  - {leg: 2, price: 9800, ratio: 0.3}
  - {leg: 3, price: 9650, ratio: 0.1}
scaled_sell:
  - {leg: 1, price: 11000, ratio: 0.5}
  - {leg: 2, price: 12500, ratio: 0.5}
stop_basis: "close"
stop_label: "직전 스윙저점"
cited_scores:
  s_score: 8
confidence: 78
contract_version: "1.0"
```
"""


def test_parse_multi_level_into_trade_plan():
    rec = parse_recommendation(SAMPLE_MULTI_LEVEL)
    assert rec is not None
    plan = rec.data.get("trade_plan")
    assert plan is not None
    assert len(plan["scaled_buy"]) == 3
    assert plan["scaled_buy"][0] == {"leg": 1, "price": 10000.0, "ratio": 0.6}
    assert len(plan["scaled_sell"]) == 2
    assert plan["stop_basis"] == "close"
    assert plan["stop_label"] == "직전 스윙저점"
    # 기존 단일 필드도 그대로(하위호환).
    assert rec.entry_price == 10000
    assert rec.target_prices == [11000, 12500]


def test_parse_backward_compat_no_plan():
    """다단 필드 없는 기존 권고 → data.trade_plan 없음(무변)."""
    rec = parse_recommendation(SAMPLE_B)
    assert "trade_plan" not in rec.data


# TRADE-PLAN-LIFECYCLE-001 2단계 — LLM 이 발행한 매수대기 단계 필드(data) 보존
SAMPLE_WATCHING = """관망이나 매수대기 단계로 진입 시나리오 제시.

```yaml
recommendation_id: REC-20260616-005930-A
date: 2026-06-16
ticker: "005930"
display_name: "삼성전자"
track: A
verdict: "wait"
confidence: 40
reasons:
  - "강세장이나 과열 — 눌림 대기"
data:
  funnel_stage: "watching"
  stage_scenario: "종가 20일선(9,800) 회복+거래량 동반 시 1차 진입, 미달 시 스윙저점(9,500) 분할"
  waiting_entry: 9800
contract_version: "1.0"
```
"""


def test_parse_preserves_watching_stage_fields():
    """파서는 data 블록을 통째 보존 — 매수대기 단계 필드 수정 불필요(가산만)."""
    rec = parse_recommendation(SAMPLE_WATCHING)
    assert rec is not None
    assert rec.verdict == "wait"
    assert rec.data["funnel_stage"] == "watching"
    assert "20일선" in rec.data["stage_scenario"]
    assert rec.data["waiting_entry"] == 9800


def test_parse_returns_none_when_no_yaml_block():
    # 권고 양식 미발행(개념 질문 응답 등) → graceful None
    assert parse_recommendation("R/R 이란 손익비를 뜻합니다. 별다른 권고 없음.") is None


def test_parse_returns_none_on_missing_required_field():
    bad = """```yaml
date: 2026-06-09
verdict: "buy"
entry_price: 100
```"""
    # recommendation_id / ticker / track 누락 → None (영속 대상 아님)
    assert parse_recommendation(bad) is None


def test_parse_returns_none_on_malformed_yaml():
    bad = """```yaml
recommendation_id: [unclosed
ticker: broken: : :
```"""
    assert parse_recommendation(bad) is None


# ---------------------------------------------------------------------------
# is_actionable — 가상 체결 대상 판정
# ---------------------------------------------------------------------------


def test_actionable_buy_with_valid_levels():
    rec = parse_recommendation(SAMPLE_B)
    assert rec.is_actionable is True


def test_not_actionable_when_not_buy():
    rec = parse_recommendation(SAMPLE_B.replace('verdict: "buy"', 'verdict: "hold"'))
    assert rec.is_actionable is False


def test_not_actionable_when_entry_below_stop():
    # entry ≤ stop → 리스크 역산 불가 → 체결 대상 아님
    rec = parse_recommendation(SAMPLE_B.replace("entry_price: 68000", "entry_price: 64000"))
    assert rec.is_actionable is False


def test_not_actionable_when_stop_missing():
    rec = parse_recommendation(SAMPLE_B.replace("stop_loss: 65000", "stop_loss: null"))
    assert rec.is_actionable is False


# ---------------------------------------------------------------------------
# persist / load_active — team_outputs 라운드트립
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    db = Database(tmp_path / "test_rec.sqlite")
    monkeypatch.setattr("core.outputs.get_db", lambda: db)
    monkeypatch.setattr(recommendation, "get_db", lambda: db)
    return db


def test_persist_then_load_active_round_trips(isolated_db):
    rec = parse_recommendation(SAMPLE_B)
    persist_recommendation(rec)

    active = load_active_recommendations()
    assert len(active) == 1
    loaded = active[0]
    assert loaded.recommendation_id == rec.recommendation_id
    assert loaded.ticker == "005930"
    assert loaded.track == "B"
    assert loaded.entry_price == 68000
    assert loaded.stop_loss == 65000
    assert loaded.target_prices == [74000]
    assert loaded.cited_scores["buy_score"] == 7


def test_persist_is_idempotent_per_recommendation(isolated_db):
    rec = parse_recommendation(SAMPLE_B)
    persist_recommendation(rec)
    persist_recommendation(rec)  # 같은 recommendation_id 재영속 → 행 1개 유지
    assert len(load_active_recommendations()) == 1


def test_load_active_dedups_by_ticker_track_keeps_one(isolated_db):
    # 같은 (track,ticker)가 다른 cadence/날짜 id로 여러 번 영속 → 최신 1건만 (중복 버그 수정).
    persist_recommendation(parse_recommendation(SAMPLE_B))  # REC-20260609-005930-B
    alt = SAMPLE_B.replace("REC-20260609-005930-B", "REC-20260610-12:35-005930-B")
    persist_recommendation(parse_recommendation(alt))
    active = load_active_recommendations()
    assert len(active) == 1
    assert active[0].ticker == "005930" and active[0].track == "B"


def test_load_active_keeps_both_tracks_same_ticker(isolated_db):
    # 같은 종목이라도 Track A/B는 별개 권고 → 둘 다 유지.
    persist_recommendation(parse_recommendation(SAMPLE_B))  # 005930 B
    persist_recommendation(parse_recommendation(SAMPLE_A))  # 005930 A
    active = load_active_recommendations()
    assert len(active) == 2
    assert {r.track for r in active} == {"A", "B"}


def test_load_recovers_flat_data_extras_round_trip(isolated_db):
    # 영속은 rec.data 를 top-level 로 평탄화 → 로드 시 alpha_posture·funnel_stage 등 복원돼야 함.
    rec = parse_recommendation(SAMPLE_B)
    rec.data["funnel_stage"] = "watching"
    rec.data["alpha_posture"] = {"verdict_candidate": "wait", "conditional_entry": {"trigger": "pullback"}}
    rec.data["source"] = "auto"
    persist_recommendation(rec)
    loaded = load_active_recommendations()[0]
    assert loaded.data["funnel_stage"] == "watching"
    assert loaded.data["alpha_posture"]["verdict_candidate"] == "wait"
    assert loaded.data["source"] == "auto"


def test_persist_strategist_recommendations_from_agent_responses(isolated_db):
    # production_chat 의 agent_responses 에서 strategist 응답만 골라 영속
    responses = [
        {"kind": "analyst", "id": "trader", "text": "타점 점수 7"},
        {"kind": "strategist", "agent_id": "track_b", "text": SAMPLE_B},
    ]
    ids = persist_strategist_recommendations(responses)
    assert ids == ["REC-20260609-005930-B"]
    assert len(load_active_recommendations()) == 1


def test_persist_strategist_recommendations_skips_when_no_recommendation(isolated_db):
    # 권고 양식 미발행(개념 질문 등) strategist 응답 → 영속 0
    responses = [{"kind": "strategist", "agent_id": "track_b", "text": "R/R 은 손익비입니다."}]
    assert persist_strategist_recommendations(responses) == []
    assert load_active_recommendations() == []


def test_persist_strategist_recommendations_ignores_errored(isolated_db):
    responses = [{"kind": "strategist", "agent_id": "track_b", "text": SAMPLE_B, "error": "boom"}]
    assert persist_strategist_recommendations(responses) == []


def test_load_active_excludes_non_recommendation_global(isolated_db):
    # target=global (시장 전체 판단 등) 은 종목 권고가 아니므로 제외
    from core.contracts.team_output import StandardOutput
    from core.outputs import persist_output

    persist_output(
        StandardOutput.build(
            team_id="track_b",
            run_id="GLOBAL-1",
            verdict="neutral",
            confidence=50,
            reasons=["시장 전반 관망"],
            target="global",
        )
    )
    persist_recommendation(parse_recommendation(SAMPLE_B))

    active = load_active_recommendations()
    assert len(active) == 1
    assert active[0].ticker == "005930"
