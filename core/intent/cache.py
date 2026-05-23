"""Intent classification 결과 캐시 — `llm_call_cache` table 재사용.

PRODUCTION-UX-001 § R2 결단:
  - type='intent_classification'
  - TTL 30 일 (표현 분류는 시대-안정적 — 사용자 통찰 인용)
  - cache_key = sha256(normalized_input + model_name)

cycle 14 `collectors/anchors.py::_get_cached_anchor / _store_cached_anchor`
패턴 1:1 mirror. anchor_selection 과 type 만 다름.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

CACHE_TYPE = "intent_classification"
DEFAULT_TTL_DAYS = 30


def normalize_input(text: str) -> str:
    """캐시 key 정규화 — 앞뒤 공백 + 연속 공백 + lowercase.

    표현 변형 ("삼성전자 살까?" / " 삼성전자  살까 ? ") 이 같은 캐시 hit 되도록.
    물음표/느낌표 등 구두점은 보존 (의도 차이 가능성).
    """
    return " ".join(text.strip().lower().split())


def cache_key(normalized_input: str, model: str) -> str:
    """sha256 (normalized_input + '|' + model). model 변경 시 캐시 자동 무효화."""
    return hashlib.sha256(f"{normalized_input}|{model}".encode("utf-8")).hexdigest()


def get_cached_classification(input_hash: str, *, ttl_days: int = DEFAULT_TTL_DAYS) -> dict | None:
    """llm_call_cache 에서 intent classification 조회 — TTL 초과 시 None.

    Returns:
        dict 또는 None. dict 는 classify_intent 가 직렬화한 풀세트
        (scenario_id, ticker, agent_route, analyst_ids, confidence, reasoning).
    """
    db = get_db()
    try:
        row = db.fetch_one(
            "SELECT response_json, created_at FROM llm_call_cache "
            "WHERE input_hash = ? AND type = ?",
            (input_hash, CACHE_TYPE),
        )
    except Exception as e:  # pragma: no cover — DB 부재 환경
        log.warning("intent_cache_lookup_failed", error=str(e))
        return None
    if row is None:
        return None
    try:
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(days=ttl_days):
            return None
        return json.loads(row["response_json"])
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        log.warning("intent_cache_parse_failed", error=str(e))
        return None


def store_cached_classification(
    input_hash: str,
    response: dict,
    *,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> None:
    """classification 결과 적재 — ON CONFLICT REPLACE 멱등.

    model 변경 시엔 cache_key 자체가 달라지므로 별도 row 가 됨 (의도된 동작).
    """
    db = get_db()
    try:
        with db.connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_call_cache
                    (input_hash, model, response_json, tokens_in, tokens_out, cost_usd, ttl_days, created_at, type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(input_hash) DO UPDATE SET
                    response_json = excluded.response_json,
                    tokens_in     = excluded.tokens_in,
                    tokens_out    = excluded.tokens_out,
                    cost_usd      = excluded.cost_usd,
                    created_at    = excluded.created_at,
                    type          = excluded.type
                """,
                (
                    input_hash,
                    model,
                    json.dumps(response, ensure_ascii=False),
                    tokens_in,
                    tokens_out,
                    cost_usd,
                    ttl_days,
                    datetime.now(timezone.utc).isoformat(),
                    CACHE_TYPE,
                ),
            )
    except Exception as e:  # pragma: no cover — DB 부재 환경
        log.warning("intent_cache_store_failed", error=str(e))
