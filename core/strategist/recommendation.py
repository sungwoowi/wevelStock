"""전략가 권고 구조화 — PAPER-TRADING-001 (RB-MS2) M1.

전략가 persona 는 권고 시 이미 `strategist-recommendation-v1` YAML 블록을 발행한다
(track_a/b persona, STRATEGY-TRACK-001 § contract). 본 모듈은 그 블록을 파싱해
`StrategistRecommendation` 으로 구조화하고 team_outputs 에 영속/조회한다 (C 결정).

- 파싱 = 전략가가 의도적으로 발행한 전용 계약 블록을 `yaml.safe_load`. graceful(실패 → None).
- 영속 = `persist_output`(team_outputs, run_id=recommendation_id → 권고당 멱등). 신규 comms 테이블 X.
- 조회 = 데스크(RB-MS2)가 활성 권고(track_a/b·최근 N일·종목 target)를 read → 가상 체결.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import yaml

from core.contracts.team_output import StandardOutput
from core.db import get_db
from core.logging import get_logger
from core.outputs import persist_output

log = get_logger(__name__)

_YAML_FENCE = re.compile(r"```(?:yaml|yml)?\s*\n(.*?)```", re.DOTALL)
_REQUIRED = ("recommendation_id", "ticker", "track")

# 구조 필드(dataclass top-level + 발행 YAML 전용) — 영속 평탄화 dict 에서 data 복원 시 제외.
# 나머지 top-level 키(alpha_posture·funnel_stage·source·cadence 등)는 rec.data 로 복원.
_CORE_KEYS = frozenset({
    "recommendation_id", "date", "ticker", "display_name", "track", "verdict",
    "entry_price", "target_prices", "stop_loss", "risk_reward", "cited_scores",
    "confidence", "reasons", "contract_version",
    "target_price_1", "target_price_2", "target_price_3",  # 발행 형태
    "scaled_buy", "scaled_sell", "stop_basis", "stop_label", "deviation_reason",  # _parse_trade_plan 처리
})


@dataclass
class StrategistRecommendation:
    """strategist-recommendation-v1 구조화 — 가상 체결(RB-MS2)의 입력."""

    recommendation_id: str
    ticker: str
    track: str
    verdict: str
    date: str = ""
    display_name: str = ""
    entry_price: float | None = None
    target_prices: list[float] = field(default_factory=list)  # 비-null 목표가 (Track A 3단 / B 1단)
    stop_loss: float | None = None
    risk_reward: float | None = None
    cited_scores: dict[str, Any] = field(default_factory=dict)
    confidence: int = 0
    reasons: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    contract_version: str = "1.0"

    @property
    def is_actionable(self) -> bool:
        """가상 체결 대상 — 매수 권고 + 리스크 역산 가능(entry > stop)."""
        return (
            self.verdict == "buy"
            and self.entry_price is not None
            and self.stop_loss is not None
            and self.entry_price > self.stop_loss
        )

    def to_recommendation_dict(self) -> dict[str, Any]:
        """size_position(recommendation=...) 입력 dict (sizing.py 계약)."""
        return {
            "recommendation_id": self.recommendation_id,
            "ticker": self.ticker,
            "track": self.track,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target_prices": list(self.target_prices),
            "cited_scores": dict(self.cited_scores),
        }


def _coerce_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_ladder(raw: Any) -> list[dict[str, Any]]:
    """분할 사다리 (scaled_buy/scaled_sell) 정규화 → [{leg, price, ratio}] (graceful).

    LLM 발행 형태 수용: [{price, ratio}] 또는 [{leg, price, ratio}] 또는 [가격, ...].
    """
    if not isinstance(raw, list):
        return []
    legs: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            price = _coerce_float(item.get("price"))
            if price is None:
                continue
            legs.append({
                "leg": int(item.get("leg") or (i + 1)),
                "price": price,
                "ratio": _coerce_float(item.get("ratio")),
            })
        else:
            price = _coerce_float(item)
            if price is not None:
                legs.append({"leg": i + 1, "price": price, "ratio": None})
    return legs


def _parse_trade_plan(d: dict[str, Any]) -> dict[str, Any]:
    """다단 트레이드 플랜 필드 (TRADE-PLAN-LIFECYCLE-001 B-MS1) → data['trade_plan'] (graceful).

    LLM 이 메뉴에서 선택·조합해 발행한 다단 손절/분할매수/분할매도 + 메뉴-밖 deviation 근거.
    기존 단일 entry/stop/target 은 그대로 두고 *가산*만 한다(하위호환).
    """
    plan: dict[str, Any] = {}
    buy = _parse_ladder(d.get("scaled_buy"))
    sell = _parse_ladder(d.get("scaled_sell"))
    if buy:
        plan["scaled_buy"] = buy
    if sell:
        plan["scaled_sell"] = sell
    if d.get("stop_basis"):
        plan["stop_basis"] = str(d["stop_basis"])
    if d.get("stop_label"):
        plan["stop_label"] = str(d["stop_label"])
    if d.get("deviation_reason"):
        plan["deviation_reason"] = str(d["deviation_reason"])
    return plan


def _from_mapping(d: dict[str, Any]) -> StrategistRecommendation | None:
    """파싱·로드 공용 — dict → dataclass (필수 필드 검증, graceful)."""
    if not isinstance(d, dict):
        return None
    if any(not d.get(k) for k in _REQUIRED):
        return None
    # 발행 형태(target_price_1/2/3) 와 영속 형태(target_prices 리스트) 양쪽 수용.
    if isinstance(d.get("target_prices"), list):
        targets = [f for f in (_coerce_float(x) for x in d["target_prices"]) if f is not None]
    else:
        targets = [
            f for f in (_coerce_float(d.get(f"target_price_{i}")) for i in (1, 2, 3)) if f is not None
        ]
    # 다단 트레이드 플랜 (B-MS1) — 발행된 data 에 가산. 영속 형태(data.trade_plan)도 그대로 수용.
    data = dict(d.get("data") or {})
    # 영속 형태는 rec.data 를 top-level 로 평탄화(persist_recommendation) → core 키 외 나머지를
    # data 로 복원(alpha_posture·funnel_stage·source 등). 발행 형태(nested data)는 위에서 이미 수용.
    for k, v in d.items():
        if k not in _CORE_KEYS and k != "data" and k not in data:
            data[k] = v
    plan = _parse_trade_plan(d)
    if plan:
        data["trade_plan"] = {**(data.get("trade_plan") or {}), **plan}
    return StrategistRecommendation(
        recommendation_id=str(d["recommendation_id"]),
        ticker=str(d["ticker"]),
        track=str(d["track"]).upper(),
        verdict=str(d.get("verdict", "")),
        date=str(d.get("date", "")),
        display_name=str(d.get("display_name", "")),
        entry_price=_coerce_float(d.get("entry_price")),
        target_prices=targets,
        stop_loss=_coerce_float(d.get("stop_loss")),
        risk_reward=_coerce_float(d.get("risk_reward")),
        cited_scores=dict(d.get("cited_scores") or {}),
        confidence=int(d.get("confidence") or 0),
        reasons=[str(r) for r in (d.get("reasons") or [])],
        data=data,
        contract_version=str(d.get("contract_version", "1.0")),
    )


def parse_recommendation(text: str) -> StrategistRecommendation | None:
    """전략가 출력 텍스트의 strategist-recommendation-v1 YAML 블록 → 구조화 (graceful).

    권고 양식 미발행(개념 질문 등)·파싱 실패·필수 필드 누락 → None (영속 대상 아님).
    """
    if not text:
        return None
    blocks = _YAML_FENCE.findall(text)
    candidates = blocks or [text]  # 펜스 없으면 전체 텍스트도 시도 (best-effort)
    for block in candidates:
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        rec = _from_mapping(parsed) if isinstance(parsed, dict) else None
        if rec is not None:
            return rec
    return None


def persist_recommendation(rec: StrategistRecommendation | None) -> bool:
    """구조화 권고를 team_outputs 에 영속 (run_id=recommendation_id → 권고당 멱등).

    None 또는 비검증 권고 → skip(False). 영속 성공 → True.
    """
    if rec is None or not rec.recommendation_id:
        return False
    team_id = f"track_{rec.track.lower()}"
    data = {
        "recommendation_id": rec.recommendation_id,
        "date": rec.date,
        "ticker": rec.ticker,
        "display_name": rec.display_name,
        "track": rec.track,
        "verdict": rec.verdict,
        "entry_price": rec.entry_price,
        "target_prices": rec.target_prices,
        "stop_loss": rec.stop_loss,
        "risk_reward": rec.risk_reward,
        "cited_scores": rec.cited_scores,
        **rec.data,  # market_regime·triggers_fired 등 보존
    }
    try:
        persist_output(
            StandardOutput.build(
                team_id=team_id,
                run_id=rec.recommendation_id,
                verdict=rec.verdict or "unknown",
                confidence=max(0, min(100, rec.confidence)),
                reasons=rec.reasons or ["(권고 사유 미발행)"],
                target=rec.ticker,
                data=data,
            )
        )
        return True
    except Exception as e:  # noqa: BLE001 — 영속 실패가 권고 표시를 막지 않음
        log.warning("recommendation_persist_failed", rec_id=rec.recommendation_id, error=str(e))
        return False


def persist_strategist_recommendations(agent_responses: list[dict[str, Any]]) -> list[str]:
    """production_chat 의 agent_responses 중 strategist 응답을 파싱·영속.

    권고 양식 미발행(개념 질문)·에러 응답 → skip. 영속된 recommendation_id 목록 반환.
    호출자(API)는 이 결과로 비중 지시(size_position) 렌더를 트리거할 수 있다.
    """
    persisted: list[str] = []
    for r in agent_responses or []:
        if r.get("kind") != "strategist" or r.get("error"):
            continue
        rec = parse_recommendation(r.get("text") or "")
        if rec is not None and persist_recommendation(rec):
            persisted.append(rec.recommendation_id)
    return persisted


def load_recommendation(recommendation_id: str) -> StrategistRecommendation | None:
    """recommendation_id(=team_outputs.run_id) 로 권고 1건 조회 (없으면 None).

    데스크 상세(PAPER-DESK-UX-001)가 보유 포지션의 원안(entry/stop/분할)을 재구성할 때 read.
    """
    if not recommendation_id:
        return None
    row = get_db().fetch_one(
        "SELECT data_json FROM team_outputs "
        "WHERE run_id = ? AND team_id IN ('track_a', 'track_b') LIMIT 1",
        (recommendation_id,),
    )
    if row is None:
        return None
    try:
        data = json.loads(row["data_json"])
    except (json.JSONDecodeError, TypeError):
        return None
    return _from_mapping(data)


def load_active_recommendations(*, within_days: int = 30) -> list[StrategistRecommendation]:
    """활성 권고 조회 — track_a/b · 종목 target(global 제외) · 최근 within_days.

    데스크(RB-MS2)가 매일 이 목록을 read → 지정가 도달 판정·가상 체결.
    **동일 (track, ticker) 는 최신 1건만** — recommendation_id 는 cadence·날짜마다 달라지므로
    그 키로 dedup 하면 같은 종목이 cadence·일자마다 누적된다(데스크 중복 버그). timestamp DESC
    정렬 + (track, ticker) 첫 등장 = 종목별 최신 플랜.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=within_days)).isoformat()
    rows = get_db().fetch_all(
        """
        SELECT data_json, timestamp FROM team_outputs
        WHERE team_id IN ('track_a', 'track_b')
          AND target != 'global'
          AND timestamp >= ?
        ORDER BY timestamp DESC
        """,
        (cutoff,),
    )
    out: list[StrategistRecommendation] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        try:
            data = json.loads(row["data_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        rec = _from_mapping(data)
        if rec is None:
            continue
        key = (rec.track, rec.ticker)
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out
