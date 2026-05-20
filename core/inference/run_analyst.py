"""분석가 단일 호출 함수.

`run_analyst(analyst_id, messages)` = 멀티턴 messages 배열을 받아 분석가의 응답을
반환한다. 단일 턴이면 messages 길이 1, 멀티턴이면 [user, assistant, user, ...] 누적.

흐름:
  1. agents/analysts/<id>/manifest.yaml 로드 (reads, llm.*, response_rules)
  2. agents/analysts/<id>/persona.md 경로 확정
  3. compose.build_pipeline_prompt(rag_dept=reads[0], query_for_rag=last_user_msg, ...)
     → SystemPromptBundle (canon + persona + memory + RAG + response_rules 블록)
  4. core.llm.client.call_llm(system=blocks, messages=messages, ...)
  5. metadata 산출 (system char 수, RAG 회수 chunk 수, cache token, cost, latency)

Anthropic prompt caching 은 build_pipeline_prompt 가 cache_control 을 system 블록에
이미 박아준다. messages 는 매 턴 변하므로 캐시 X.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from collectors.charts import build_chart_data, render_chart_data_md
from collectors.fundamentals import get_fundamentals, render_fundamental_data_md
from collectors.snapshot import build_market_snapshot, render_snapshot_md
from core.knowledge.compose import build_pipeline_prompt
from core.llm.client import call_llm, call_llm_stream
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSTS_DIR = REPO_ROOT / "agents" / "analysts"


@dataclass(frozen=True)
class AnalystSpec:
    """agents/analysts/<id>/manifest.yaml + persona.md 경로 묶음."""

    id: str
    display_name: str
    learning_dept: str
    reads: list[str]
    canon_categories: list[str]
    persona_path: Path
    model: str | None
    max_tokens: int
    temperature: float
    response_rules: str | None
    reads_chart_data: bool = False  # INFRA-CHART-DATA-001 — stock_analyst 만 True
    reads_fundamental_data: bool = False  # INFRA-FUNDAMENTAL-DATA-001 — stock_analyst 만 True


@dataclass
class AnalystResponse:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AnalystNotFoundError(FileNotFoundError):
    pass


def load_analyst_spec(analyst_id: str) -> AnalystSpec:
    """분석가 manifest 로드. 분석가가 없으면 AnalystNotFoundError."""
    analyst_dir = ANALYSTS_DIR / analyst_id
    manifest_path = analyst_dir / "manifest.yaml"
    persona_path = analyst_dir / "persona.md"
    if not manifest_path.exists():
        raise AnalystNotFoundError(
            f"manifest not found: {manifest_path} (분석가 '{analyst_id}' 가 등록되지 않았습니다)"
        )
    if not persona_path.exists():
        raise AnalystNotFoundError(f"persona not found: {persona_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    llm_cfg = raw.get("llm") or {}

    return AnalystSpec(
        id=raw.get("id", analyst_id),
        display_name=raw.get("display_name", analyst_id),
        learning_dept=raw.get("learning_dept", ""),
        reads=list(raw.get("reads") or []),
        canon_categories=list(raw.get("canon_categories") or []),
        persona_path=persona_path,
        model=llm_cfg.get("model"),
        max_tokens=int(llm_cfg.get("max_tokens", 4000)),
        temperature=float(llm_cfg.get("temperature", 0.4)),
        response_rules=raw.get("response_rules"),
        reads_chart_data=bool(raw.get("reads_chart_data", False)),
        reads_fundamental_data=bool(raw.get("reads_fundamental_data", False)),
    )


def _last_user_text(messages: list[dict]) -> str | None:
    """마지막 user 메시지의 텍스트 (RAG query 로 사용)."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # Anthropic 의 content blocks 형식 — 텍스트 부분만 추출
                parts = [b.get("text", "") for b in content if isinstance(b, dict)]
                joined = "\n".join(p for p in parts if p)
                return joined or None
    return None


def _system_char_count(blocks: list[dict]) -> int:
    return sum(len(b.get("text", "")) for b in blocks if isinstance(b, dict))


def _rag_chunks_in_blocks(blocks: list[dict]) -> int:
    """## Retrieved References 블록의 ### 헤더 개수 = 회수된 chunk 수."""
    for b in blocks:
        text = b.get("text", "")
        if text.startswith("## Retrieved References"):
            return text.count("\n### [")
    return 0


def _extract_cache_tokens(raw: dict) -> tuple[int, int]:
    """raw["usage"] 에서 cache_read / cache_creation tokens 추출."""
    usage = raw.get("usage") or {}
    return (
        int(usage.get("cache_read_input_tokens") or 0),
        int(usage.get("cache_creation_input_tokens") or 0),
    )


# ----------------------------------------------------------------------
# 종목명 ↔ ticker 매핑 (KR 시총 상위 30) — production UX 의 첫 시동.
# 별도 SPEC `INFRA-TICKER-RESOLVER-001` 후속에서 KRX 종목 마스터 다운로드 +
# 약칭/alias + 종목명 fuzzy 검색으로 확장. 현재는 하드코드 dict 로 일상 종목 커버.
# ----------------------------------------------------------------------

KR_NAME_TO_TICKER: dict[str, str] = {
    # KOSPI 시총 상위 20
    "삼성전자": "005930",
    "삼성전자우": "005935",
    "SK하이닉스": "000660",
    "삼성바이오로직스": "207940",
    "LG에너지솔루션": "373220",
    "현대차": "005380",
    "기아": "000270",
    "NAVER": "035420",
    "네이버": "035420",
    "셀트리온": "068270",
    "POSCO홀딩스": "005490",
    "포스코홀딩스": "005490",
    "한화에어로스페이스": "012450",
    "삼성물산": "028260",
    "KB금융": "105560",
    "HD현대중공업": "329180",
    "한화오션": "042660",
    "카카오": "035720",
    "신한지주": "055550",
    "LG": "003550",
    "한국전력": "015760",
    "삼성생명": "032830",
    "하나금융지주": "086790",
    "삼성SDI": "006400",
    "LG화학": "051910",
    "현대모비스": "012330",
    # KOSDAQ 시총 상위 10
    "에코프로비엠": "247540",
    "에코프로": "086520",
    "알테오젠": "196170",
    "셀트리온헬스케어": "091990",
    "HLB": "028300",
    "리노공업": "058470",
    "한미반도체": "042700",
    "레인보우로보틱스": "277810",
    "JYP Ent.": "035900",
    "JYP엔터": "035900",
}

# 역방향 = ticker → 표시명 (chart_data_md 헤더용)
KR_TICKER_TO_NAME: dict[str, str] = {}
for _n, _t in KR_NAME_TO_TICKER.items():
    # 중복 ticker 의 경우 첫 등장만 (우선순위). 정식 한글명 선호.
    if _t not in KR_TICKER_TO_NAME:
        KR_TICKER_TO_NAME[_t] = _n


# KOSDAQ ticker set (시총 상위 — yfinance 의 .KQ suffix 매핑용).
# 그 외 = KOSPI (.KS) 기본 가정. fundamental fetch 시 market 결정 base.
KOSDAQ_TICKERS: set[str] = {
    "247540",  # 에코프로비엠
    "086520",  # 에코프로
    "196170",  # 알테오젠
    "091990",  # 셀트리온헬스케어
    "028300",  # HLB
    "058470",  # 리노공업
    "042700",  # 한미반도체
    "277810",  # 레인보우로보틱스
    "035900",  # JYP Ent.
}


def market_for_ticker(ticker: str) -> str:
    """6자리 한국 ticker → market suffix ("KS" 또는 "KQ").

    KOSDAQ_TICKERS 에 포함되면 KQ, 그 외는 KS (KOSPI 기본 가정).
    미주 종목은 별도 호출 경로 (현재 미지원).
    """
    if ticker in KOSDAQ_TICKERS:
        return "KQ"
    return "KS"


def _normalize_name(s: str) -> str:
    """공백 제거 + 소문자. '삼성 전자' / 'sk 하이닉스' 같은 입력도 매칭."""
    return s.replace(" ", "").lower()


# 정규화 키 → ticker (런타임 첫 호출 시 lazy build 도 가능하지만 모듈 로드 시 한 번이면 충분)
_NORMALIZED_NAME_TO_TICKER: dict[str, str] = {
    _normalize_name(n): t for n, t in KR_NAME_TO_TICKER.items()
}


def resolve_ticker(raw: str | None) -> tuple[str | None, str | None]:
    """입력값 → (ticker_6digit, display_name).

    - 6자리 숫자 = ticker 그대로 통과 (display_name = KR_TICKER_TO_NAME lookup 또는 None)
    - 한글/영문 종목명 = KR_NAME_TO_TICKER 매핑 (공백/대소문자 정규화)
    - 매핑 실패 = (None, raw) — chart_failures 에 명시

    Args:
        raw: 사용자 입력 (None / 빈 string / 공백만 = (None, None))

    Returns:
        (ticker, display_name). ticker None = 매핑 실패.
    """
    if not raw:
        return None, None
    s = raw.strip()
    if not s:
        return None, None
    # 6자리 숫자 = ticker 직접
    if s.isdigit() and len(s) == 6:
        return s, KR_TICKER_TO_NAME.get(s)
    # 한글/영문 종목명 → ticker (정확 매칭)
    if s in KR_NAME_TO_TICKER:
        return KR_NAME_TO_TICKER[s], s
    # 정규화 (공백 제거 + 소문자) 매칭
    tk = _NORMALIZED_NAME_TO_TICKER.get(_normalize_name(s))
    if tk is not None:
        return tk, KR_TICKER_TO_NAME.get(tk, s)
    return None, s


async def _maybe_build_chart_data_md(
    spec: AnalystSpec, target_ticker: str | None
) -> tuple[str | None, dict[str, Any]]:
    """INFRA-CHART-DATA-001 — reads_chart_data + target_ticker 충족 시 chart_data_md 산출.

    target_ticker = 6자리 ticker 또는 한글 종목명 모두 허용 (resolve_ticker 자동 매핑).

    Returns:
        (chart_data_md, chart_meta). chart_data_md=None 이면 metadata 만 빈 dict 풀세트.
    """
    base_meta: dict[str, Any] = {
        "chart_data_age_seconds": None,
        "chart_fetch_seconds": None,
        "chart_cache_hit": None,
        "chart_failures": [],
        "chart_ohlcv_count": None,
        "chart_source": None,
        "chart_ticker": None,
    }
    if not spec.reads_chart_data:
        return None, base_meta
    if not target_ticker or not target_ticker.strip():
        # SPEC: target ticker 부재 시 silent skip (verdict=inconclusive 은 persona 가 판단)
        base_meta["chart_failures"] = ["target_ticker_absent"]
        return None, base_meta

    # 종목명 → ticker 매핑 (한글/영문 입력 시 자동 변환)
    resolved_ticker, display_name = resolve_ticker(target_ticker)
    if resolved_ticker is None:
        base_meta["chart_ticker"] = target_ticker
        base_meta["chart_failures"] = [
            f"ticker_resolve_failed:{target_ticker}"
        ]
        return None, base_meta

    started = time.monotonic()
    try:
        chart, cache_hit = await build_chart_data(resolved_ticker)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "chart_data_inject_failed", ticker=resolved_ticker, error=str(e)
        )
        base_meta["chart_ticker"] = resolved_ticker
        base_meta["chart_failures"] = [f"build_chart_data:{type(e).__name__}"]
        base_meta["chart_fetch_seconds"] = round(time.monotonic() - started, 2)
        return None, base_meta

    fetch_seconds = round(time.monotonic() - started, 2)
    chart_md = render_chart_data_md(chart, name=display_name)
    return chart_md, {
        "chart_data_age_seconds": max(0, int(time.time() - chart.fetched_at)),
        "chart_fetch_seconds": fetch_seconds,
        "chart_cache_hit": cache_hit,
        "chart_failures": list(chart.failures),
        "chart_ohlcv_count": chart.ohlcv_count,
        "chart_source": chart.source,
        "chart_ticker": chart.ticker,
    }


async def _maybe_build_fundamental_data_md(
    spec: AnalystSpec, target_ticker: str | None
) -> tuple[str | None, dict[str, Any]]:
    """INFRA-FUNDAMENTAL-DATA-001 — reads_fundamental_data + target_ticker 충족 시 fundamental_data_md 산출.

    target_ticker = 6자리 ticker 또는 한글 종목명 모두 허용 (resolve_ticker 자동 매핑).
    KOSDAQ_TICKERS 포함 시 market="KQ", 그 외 "KS".

    Returns:
        (fundamental_data_md, fundamental_meta). md=None 이면 metadata 만 base dict.
    """
    base_meta: dict[str, Any] = {
        "fundamental_source": None,
        "fundamental_fetched_at": None,
        "fundamental_age_seconds": None,
        "fundamental_failures": [],
        "fundamental_quarter_count": None,
        "fundamental_ratios_count": None,
        "fundamental_ticker_used": None,
    }
    if not spec.reads_fundamental_data:
        return None, base_meta
    if not target_ticker or not target_ticker.strip():
        base_meta["fundamental_failures"] = ["target_ticker_absent"]
        return None, base_meta

    resolved_ticker, display_name = resolve_ticker(target_ticker)
    if resolved_ticker is None:
        base_meta["fundamental_ticker_used"] = target_ticker
        base_meta["fundamental_failures"] = [
            f"ticker_resolve_failed:{target_ticker}"
        ]
        return None, base_meta

    market = market_for_ticker(resolved_ticker)
    try:
        f = await get_fundamentals(resolved_ticker, market=market)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "fundamental_data_inject_failed",
            ticker=resolved_ticker,
            error=str(e),
        )
        base_meta["fundamental_ticker_used"] = resolved_ticker
        base_meta["fundamental_failures"] = [
            f"get_fundamentals:{type(e).__name__}"
        ]
        return None, base_meta

    if f is None:
        base_meta["fundamental_ticker_used"] = resolved_ticker
        base_meta["fundamental_failures"] = ["no_fundamental_data"]
        return None, base_meta

    ratios_count = sum(
        1 for v in (
            f.eps_ttm, f.pe_ratio, f.roe, f.operating_margin, f.debt_to_equity
        ) if v is not None
    )
    fund_md = render_fundamental_data_md(f, name=display_name)
    return fund_md, {
        "fundamental_source": f.source,
        "fundamental_fetched_at": f.fetched_at_iso,
        "fundamental_age_seconds": max(0, int(time.time() - f.fetched_at)),
        "fundamental_failures": list(f.failures),
        "fundamental_quarter_count": len(f.quarter_labels),
        "fundamental_ratios_count": ratios_count,
        "fundamental_ticker_used": f.ticker,
    }


async def run_analyst(
    analyst_id: str,
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    include_memory: bool = True,
    provider: str | None = None,
    target_ticker: str | None = None,
) -> AnalystResponse:
    """단일 분석가 호출. 멀티턴 messages 배열 그대로 수용.

    Args:
        analyst_id: agents/analysts/<id>/ 의 디렉토리명
        messages: [{"role": "user"|"assistant", "content": str}, ...]
                  단일 턴이면 길이 1, 멀티턴이면 누적
        model/max_tokens/temperature: manifest 값을 override (선택)
        include_memory: core/memory 시계열 메모리 주입 ON/OFF
        provider: "gemini" | "claude_code" | "anthropic" | "mock" 명시 시 그
                  backend 강제 호출 (자동 폴백 X — 에러 propagate). None 이면
                  config.llm.provider + 자동 폴백 체인. 톤 비교용.

    Returns:
        AnalystResponse(text, metadata)
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_analyst_spec(analyst_id)
    rag_dept = spec.reads[0] if spec.reads else None
    query_for_rag = _last_user_text(messages)

    snap_started = time.monotonic()
    snapshot, snapshot_cache_hit = await build_market_snapshot()
    snapshot_fetch_seconds = round(time.monotonic() - snap_started, 2)
    snapshot_age_seconds = max(0, int(time.time() - snapshot.fetched_at))
    market_snapshot_md = render_snapshot_md(snapshot)

    chart_data_md, chart_meta = await _maybe_build_chart_data_md(spec, target_ticker)
    fundamental_data_md, fundamental_meta = await _maybe_build_fundamental_data_md(
        spec, target_ticker
    )

    bundle = await build_pipeline_prompt(
        context_id=spec.id,
        persona_path=spec.persona_path,
        include_shared_canon=True,
        include_memory=include_memory,
        token_budget_memory=4000,
        query_for_rag=query_for_rag,
        rag_dept=rag_dept,
        canon_categories=spec.canon_categories or None,
        market_snapshot_md=market_snapshot_md,
        chart_data_md=chart_data_md,
        fundamental_data_md=fundamental_data_md,
        response_rules=spec.response_rules,
    )

    sys_chars = _system_char_count(bundle.blocks)
    rag_chunks = _rag_chunks_in_blocks(bundle.blocks)

    started = time.monotonic()
    resp = await call_llm(
        system=bundle.blocks,
        messages=messages,
        model=model or spec.model,
        max_tokens=max_tokens or spec.max_tokens,
        temperature=temperature if temperature is not None else spec.temperature,
        provider=provider,
    )
    latency_s = time.monotonic() - started

    cache_read, cache_creation = _extract_cache_tokens(resp.get("raw") or {})

    # raw error / mock fallback 가시화 — 503/rate limit/키 누락 같은 silent fallback 진단용
    raw = resp.get("raw") or {}
    upstream_error = raw.get("error")
    is_mock = "-mock" in str(resp.get("model", "")) or bool(raw.get("mock"))

    # provider_used: 실제 응답을 만든 backend (auto fallback 시 fallback_used 우선)
    provider_used = (
        raw.get("fallback_used")
        or raw.get("provider")
        or (provider if provider else "auto")
    )

    metadata = {
        "analyst_id": spec.id,
        "display_name": spec.display_name,
        "learning_dept": spec.learning_dept,
        "rag_dept": rag_dept,
        "rag_chunks_returned": rag_chunks,
        "system_prompt_chars": sys_chars,
        "system_blocks": len(bundle.blocks),
        "cache_breakpoint_count": bundle.cache_breakpoint_count,
        "tokens_in": resp.get("tokens_in", 0),
        "tokens_out": resp.get("tokens_out", 0),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "model": resp.get("model", ""),
        "cost_usd": resp.get("cost_usd", 0.0),
        "latency_s": round(latency_s, 2),
        "is_mock": is_mock,
        "upstream_error": upstream_error,  # 실 LLM 호출 실패 시 원인 (mock fallback 진단)
        "provider_requested": provider,  # 사용자 명시 선택 (None = auto)
        "provider_used": provider_used,  # 실제 응답 backend
        "snapshot_age_seconds": snapshot_age_seconds,
        "snapshot_fetch_seconds": snapshot_fetch_seconds,
        "snapshot_cache_hit": snapshot_cache_hit,
        "snapshot_failures": snapshot.failures,
        "snapshot_source_map": dict(snapshot.source_map),
        "snapshot_db_run_ids": dict(snapshot.db_run_ids),
        **chart_meta,
        **fundamental_meta,
    }

    log.info(
        "analyst_call_done",
        analyst=spec.id,
        chars=sys_chars,
        rag_chunks=rag_chunks,
        tokens_in=metadata["tokens_in"],
        tokens_out=metadata["tokens_out"],
        cache_read=cache_read,
        cost_usd=metadata["cost_usd"],
        latency_s=metadata["latency_s"],
    )

    return AnalystResponse(text=resp.get("content", ""), metadata=metadata)


async def run_analyst_stream(
    analyst_id: str,
    messages: list[dict],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    include_memory: bool = True,
    provider: str | None = None,
    target_ticker: str | None = None,
):
    """run_analyst 의 streaming 변종. text_delta 이벤트 흘림 + 종료 시 metadata.

    Yields:
        {"type": "text_delta", "text": str}      # 토큰 청크
        {"type": "metadata", **metadata_dict}     # 종료 직전 1회 (run_analyst 의
                                                    metadata 키 + cumulative content)
        {"type": "error", ...}                    # provider 실패
        {"type": "done"}                          # 정상 종료

    System prompt 합성 (manifest+persona+canon+RAG+memory+market_snapshot) 은
    run_analyst 와 동일. call_llm 대신 call_llm_stream 사용.
    """
    if not messages:
        raise ValueError("messages 가 비어있습니다 (최소 1턴 user 입력 필요)")

    spec = load_analyst_spec(analyst_id)
    rag_dept = spec.reads[0] if spec.reads else None
    query_for_rag = _last_user_text(messages)

    snap_started = time.monotonic()
    snapshot, snapshot_cache_hit = await build_market_snapshot()
    snapshot_fetch_seconds = round(time.monotonic() - snap_started, 2)
    snapshot_age_seconds = max(0, int(time.time() - snapshot.fetched_at))
    market_snapshot_md = render_snapshot_md(snapshot)

    chart_data_md, chart_meta = await _maybe_build_chart_data_md(spec, target_ticker)
    fundamental_data_md, fundamental_meta = await _maybe_build_fundamental_data_md(
        spec, target_ticker
    )

    bundle = await build_pipeline_prompt(
        context_id=spec.id,
        persona_path=spec.persona_path,
        include_shared_canon=True,
        include_memory=include_memory,
        token_budget_memory=4000,
        query_for_rag=query_for_rag,
        rag_dept=rag_dept,
        canon_categories=spec.canon_categories or None,
        market_snapshot_md=market_snapshot_md,
        chart_data_md=chart_data_md,
        fundamental_data_md=fundamental_data_md,
        response_rules=spec.response_rules,
    )

    sys_chars = _system_char_count(bundle.blocks)
    rag_chunks = _rag_chunks_in_blocks(bundle.blocks)

    started = time.monotonic()
    first_token_at: float | None = None
    last_metadata: dict | None = None
    last_error: dict | None = None

    async for event in call_llm_stream(
        system=bundle.blocks,
        messages=messages,
        model=model or spec.model,
        max_tokens=max_tokens or spec.max_tokens,
        temperature=temperature if temperature is not None else spec.temperature,
        provider=provider,
    ):
        etype = event.get("type")
        if etype == "text_delta":
            if first_token_at is None:
                first_token_at = time.monotonic()
            yield event
        elif etype == "metadata":
            last_metadata = event
            # metadata 는 우리가 보강한 형식으로 끝에 다시 emit
            continue
        elif etype == "error":
            last_error = event
            yield event
        elif etype == "done":
            # done 은 마지막에 우리가 emit
            break
        else:
            # 알 수 없는 이벤트 — 그대로 흘림
            yield event

    latency_s = time.monotonic() - started
    first_token_ms = (
        int((first_token_at - started) * 1000) if first_token_at else None
    )

    # last_metadata 가 없으면 (예: error 만 발생) 빈 dict 로 보호
    md_src = last_metadata or {}
    raw = md_src.get("raw") or {}
    cache_read, cache_creation = _extract_cache_tokens(raw)
    upstream_error = raw.get("error") or (last_error.get("message") if last_error else None)
    is_mock = "-mock" in str(md_src.get("model", "")) or bool(raw.get("mock"))
    provider_used = (
        raw.get("fallback_used")
        or raw.get("provider")
        or (provider if provider else "auto")
    )

    metadata = {
        "analyst_id": spec.id,
        "display_name": spec.display_name,
        "learning_dept": spec.learning_dept,
        "rag_dept": rag_dept,
        "rag_chunks_returned": rag_chunks,
        "system_prompt_chars": sys_chars,
        "system_blocks": len(bundle.blocks),
        "cache_breakpoint_count": bundle.cache_breakpoint_count,
        "tokens_in": md_src.get("tokens_in", 0),
        "tokens_out": md_src.get("tokens_out", 0),
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "model": md_src.get("model", ""),
        "cost_usd": md_src.get("cost_usd", 0.0),
        "latency_s": round(latency_s, 2),
        "first_token_ms": first_token_ms,
        "is_mock": is_mock,
        "upstream_error": upstream_error,
        "provider_requested": provider,
        "provider_used": provider_used,
        "snapshot_age_seconds": snapshot_age_seconds,
        "snapshot_fetch_seconds": snapshot_fetch_seconds,
        "snapshot_cache_hit": snapshot_cache_hit,
        "snapshot_failures": snapshot.failures,
        "snapshot_source_map": dict(snapshot.source_map),
        "snapshot_db_run_ids": dict(snapshot.db_run_ids),
        **chart_meta,
        **fundamental_meta,
        "content": md_src.get("content", ""),  # 누적 텍스트 (검증용)
    }

    log.info(
        "analyst_stream_done",
        analyst=spec.id,
        chars=sys_chars,
        rag_chunks=rag_chunks,
        tokens_in=metadata["tokens_in"],
        tokens_out=metadata["tokens_out"],
        cache_read=cache_read,
        cost_usd=metadata["cost_usd"],
        latency_s=metadata["latency_s"],
        first_token_ms=first_token_ms,
    )

    yield {"type": "metadata", **metadata}
    yield {"type": "done"}
