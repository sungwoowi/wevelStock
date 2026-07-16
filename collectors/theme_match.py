"""theme_match 직관축 — F-Score SLOT S1 (INFRA-SCORE-INPUTS-001).

F-Score(수급 점수) 4축 중 최대 가중(0.4) = theme_match = "이 종목 테마의 권위 주체
(외인·기관·연기금·개인 등)가 실제로 순매수 중인가". 테마 분류는 결정론 공식이 안 떨어지는
**직관 영역** → 2-Stage 하이브리드 (anchors.py 패턴 1:1 mirror, memory feedback_llm_intuition_distribution):

  1. classify_theme(ticker) = 종목 → 테마 분류
     a. manual_theme 맵 우선 (source='manual')
     b. Stage 1 결정론 후보 = config theme_taxonomy 키 (+ ticker 종목명)
     c. Stage 2 LLM 선택 (temperature=0.0, JSON) — llm_call_cache type='theme_match'
     d. 실패·미분류 시 → theme None (source='neutral_fallback')
  2. score_theme_match(theme, net_sums) = 결정론 채점
     theme_authority[theme]=권위 주체 → 그 주체 net / (5주체 abs 합 +1) = -1..+1 → breakpoints 0~10
  3. resolve_theme_match = 1+2 결합 → (score|None, theme|None, source)

⚠️ MVP 한계: net_sums 가 **시장 레벨**(KOSPI/KOSDAQ 집계) 프록시. 종목 레벨 수급 collector
도입 후 입력만 시장→종목으로 교체하면 골격은 그대로 (분류·채점 로직 100% 재사용).

cutoff_date 는 시그니처 호환을 위해 수용하되 **캐시 키엔 미포함** — 테마는 시간 안정적(slow-moving)
이라 백테스팅 시 일별 LLM 폭주를 피한다 (TTL 30일이 갱신 담당).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from collectors.scoring import map_to_axis
from core.db import get_db
from core.llm.client import call_llm, parse_json_response
from core.llm.tiers import resolve_model_for_area
from core.logging import get_logger

log = get_logger(__name__)

# FAST tier — resolve_model_for_area("theme_match") 가 현재 provider(gemini/claude_code/anthropic)에
# 맞는 모델을 반환. 과거 claude-haiku 하드코딩 + provider 미지정 → Gemini 한도 도달 시 claude_code 로
# 무성(silent) 폴백하며 22~41K 토큰 낭비하던 누수(2026-07-14~16)를 봉합.

_NET_KEYS = (
    "foreign_net",
    "institution_net",
    "individual_net",
    "financial_inv_net",
    "pension_net",
)
# 권위 주체 친화 이름 → net_sums 키 매핑 (config 는 짧은 이름, SLOT S8 scaffold).
_SUBJECT_ALIAS = {
    "foreign": "foreign_net",
    "institution": "institution_net",
    "individual": "individual_net",
    "financial_inv": "financial_inv_net",
    "pension": "pension_net",
}


@dataclass
class ThemeResult:
    """Stage 1+2 분류 결과. theme None = 미상(중립 fallback)."""

    ticker: str
    theme: str | None
    source: str  # 'manual' | 'llm' | 'neutral_fallback'
    reasoning: str = ""


# ---------------------------------------------------------------------------
# 캐싱 — llm_call_cache type='theme_match' (anchors 메커니즘 mirror)
# ---------------------------------------------------------------------------


def _theme_cache_key(ticker: str, taxonomy_keys: list[str]) -> str:
    """cache_key = "theme|{ticker}|{taxonomy version 8hex}". cutoff 미포함(테마 안정)."""
    tv = ",".join(sorted(taxonomy_keys))
    tv8 = hashlib.sha256(tv.encode("utf-8")).hexdigest()[:8]
    return f"theme|{ticker}|{tv8}"


def _get_cached_theme(input_hash: str, *, ttl_days: int = 30) -> dict | None:
    """llm_call_cache type='theme_match' 조회. TTL 30일."""
    db = get_db()
    row = db.fetch_one(
        "SELECT response_json, created_at FROM llm_call_cache "
        "WHERE input_hash = ? AND type = 'theme_match'",
        (input_hash,),
    )
    if row is None:
        return None
    try:
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(days=ttl_days):
            return None
        return json.loads(row["response_json"])
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _store_cached_theme(
    input_hash: str,
    response: dict,
    *,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    ttl_days: int = 30,
) -> None:
    """llm_call_cache 에 type='theme_match' 저장 (멱등 ON CONFLICT)."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_call_cache
                (input_hash, model, response_json, tokens_in, tokens_out, cost_usd, ttl_days, created_at, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'theme_match')
            ON CONFLICT(input_hash) DO UPDATE SET
                response_json = excluded.response_json,
                tokens_in     = excluded.tokens_in,
                tokens_out    = excluded.tokens_out,
                cost_usd      = excluded.cost_usd,
                created_at    = excluded.created_at,
                type          = 'theme_match'
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
            ),
        )


# ---------------------------------------------------------------------------
# Stage 1+2 — classify_theme
# ---------------------------------------------------------------------------


def _ticker_name(ticker: str) -> str | None:
    """ticker → 종목명 (lazy import, 순환 참조 회피 — fundamentals.py 패턴)."""
    try:
        from core.inference.run_analyst import KR_TICKER_TO_NAME

        return KR_TICKER_TO_NAME.get(ticker)
    except Exception:  # noqa: BLE001
        return None


def _format_theme_prompt(ticker: str, name: str | None, taxonomy: dict[str, str]) -> str:
    """LLM 입력 — 종목 + 테마 보기(key: 라벨) + JSON-only 지시."""
    opts = "\n".join(f"- {k}: {label}" for k, label in taxonomy.items())
    return f"""당신은 한국 주식 종목의 테마 분류기입니다. 아래 종목이 어느 테마에 속하는지 보기 key 중 하나만 고르세요.

종목코드: {ticker} | 종목명: {name or '미상'}

테마 보기 (key: 라벨):
{opts}

규칙:
- 보기 key 중 가장 지배적인 테마 하나만 선택.
- 어느 보기에도 명확히 해당하지 않으면 "none".
- 코스닥 중소형 테마성 종목이면 kosdaq_theme.

JSON 형식으로만 응답 (다른 텍스트 금지):
{{"theme": "<보기 key 또는 none>", "reasoning": "<한 문장으로 근거>"}}"""


async def classify_theme(
    ticker: str,
    *,
    cutoff_date: str | None = None,  # 시그니처 호환 (캐시 키 미포함 — 위 모듈 docstring)
    skip_cache: bool = False,
) -> ThemeResult:
    """종목 → 테마 분류 (manual → cache → Stage 2 LLM → neutral fallback)."""
    from collectors.score_inputs_config import get_manual_theme, get_theme_taxonomy

    ticker = (ticker or "").strip()
    taxonomy = get_theme_taxonomy()
    manual = get_manual_theme()

    if not ticker:
        return ThemeResult("", None, "neutral_fallback", "ticker 부재")

    # 1) manual override
    mt = manual.get(ticker)
    if mt is not None and mt in taxonomy:
        return ThemeResult(ticker, mt, "manual", "manual_theme override")

    # 2) taxonomy 부재 → 분류 불가
    if not taxonomy:
        return ThemeResult(ticker, None, "neutral_fallback", "theme_taxonomy 미정의")

    # 3) 캐시
    cache_key = _theme_cache_key(ticker, list(taxonomy.keys()))
    input_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
    if not skip_cache:
        cached = _get_cached_theme(input_hash)
        if cached is not None:
            theme = cached.get("theme")
            theme = theme if (theme in taxonomy) else None
            src = "llm" if theme is not None else "neutral_fallback"
            log.debug("theme_cache_hit", ticker=ticker, theme=theme)
            return ThemeResult(ticker, theme, src, str(cached.get("reasoning", "")))

    # 4) Stage 2 LLM
    name = _ticker_name(ticker)
    prompt = _format_theme_prompt(ticker, name, taxonomy)
    # 현재 provider 에 맞는 (provider, model) — provider 를 명시해 넘겨 무성 cross-provider 폴백 차단.
    _provider, _model = resolve_model_for_area("theme_match")
    try:
        resp = await call_llm(
            call_type="theme_match",
            target=ticker,
            system="You are a deterministic stock theme classifier. Output only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
            provider=_provider,
            model=_model,
            max_tokens=512,
            temperature=0.0,
            # Gemini-2.5 thinking 비활성 — thinking 토큰이 max_output 예산을 잠식해
            # JSON 이 잘리는 사고 방지 (라이브 검증 2026-05-31, anchors 와 동일 결함).
            thinking_budget=0,
        )
        result = parse_json_response(resp.get("content", ""))
    except Exception as e:  # noqa: BLE001
        log.warning("theme_llm_failed", ticker=ticker, error_type=type(e).__name__, error=str(e))
        return ThemeResult(ticker, None, "neutral_fallback", "LLM 실패")

    theme: str | None = None
    reasoning = ""
    if isinstance(result, dict):
        cand = str(result.get("theme", "")).strip()
        reasoning = str(result.get("reasoning", ""))[:300]
        if cand in taxonomy:
            theme = cand

    # 캐시 저장 (theme None 도 저장 — 재호출 방지)
    if not skip_cache:
        _store_cached_theme(
            input_hash,
            {"theme": theme, "reasoning": reasoning},
            model=resp.get("model") or _model,
            tokens_in=int(resp.get("tokens_in", 0)),
            tokens_out=int(resp.get("tokens_out", 0)),
            cost_usd=float(resp.get("cost_usd", 0.0)),
        )

    if theme is None:
        return ThemeResult(ticker, None, "neutral_fallback", reasoning or "LLM 미분류")
    return ThemeResult(ticker, theme, "llm", reasoning)


# ---------------------------------------------------------------------------
# 결정론 채점 — score_theme_match
# ---------------------------------------------------------------------------


def score_theme_match(
    theme: str,
    net_sums: dict[str, int],
    *,
    authority_map: dict[str, list[str]] | None = None,
    breakpoints: list[tuple[float, float]] | None = None,
) -> float | None:
    """theme + 5주체 net → 0~10 (결정론). 권위 주체 net 비율(-1..+1) → breakpoints.

    Args:
        theme: 분류된 테마 key.
        net_sums: 5주체 net 합 (백만원). _NET_KEYS.
        authority_map: 테마→권위 주체. None → config get_theme_authority().
        breakpoints: None → config get_breakpoints("flow","theme_match").

    Returns:
        0~10 점수, 또는 None (테마 권위 미정의 / breakpoints 부재).
    """
    if authority_map is None:
        from collectors.score_inputs_config import get_theme_authority

        authority_map = get_theme_authority()
    subjects = authority_map.get(theme)
    if not subjects:
        return None

    authority_net = 0
    for s in subjects:
        key = _SUBJECT_ALIAS.get(s, s)
        authority_net += int(net_sums.get(key, 0))
    total_abs = sum(abs(int(net_sums.get(k, 0))) for k in _NET_KEYS) + 1
    ratio = max(-1.0, min(1.0, authority_net / total_abs))

    if breakpoints is None:
        from collectors.score_inputs_config import get_breakpoints

        breakpoints = get_breakpoints("flow", "theme_match")
    if not breakpoints:
        return None
    return map_to_axis(ratio, breakpoints)


# ---------------------------------------------------------------------------
# 결합 — resolve_theme_match (flow_inputs 가 호출하는 진입점)
# ---------------------------------------------------------------------------


async def resolve_theme_match(
    ticker: str,
    net_sums: dict[str, int],
    *,
    cutoff_date: str | None = None,
    skip_cache: bool = False,
    authority_map: dict[str, list[str]] | None = None,
    breakpoints: list[tuple[float, float]] | None = None,
) -> tuple[float | None, str | None, str]:
    """(theme_match_score|None, theme|None, source). score None = 미해소 → 호출부 중립 fallback."""
    res = await classify_theme(ticker, cutoff_date=cutoff_date, skip_cache=skip_cache)
    if res.theme is None:
        return None, None, res.source
    score = score_theme_match(
        res.theme, net_sums, authority_map=authority_map, breakpoints=breakpoints
    )
    return score, res.theme, res.source
