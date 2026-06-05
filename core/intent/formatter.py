"""Answer formatter — PRODUCTION-UX-001 § R4 결단.

분석가/전략가 raw 응답 (cited + 격자 + 코드 라벨 풍부) → FAST tier (Flash-lite)
LLM 1콜 → **1~3줄 결론 + 1~3줄 근거 (수급/차트/실적 3요소)** 자연어 응답.

핵심 본질 (memory `feedback_production_answer_brevity`):
  - 코드 라벨 (S-Score / α / F-Score 등) 본문 노출 0건 — label_dictionary.yaml 사전
  - 결론·근거 각 ≤ 3줄
  - 사용자 발화 (예: "삼성전자 살까?") 에 직접 답변하는 톤
  - 분석가 prefetch raw 와 전략가 응답 모두 종합
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.llm.client import call_llm
from core.llm.tiers import resolve_model_for_area
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
LABEL_DICTIONARY_PATH = REPO_ROOT / "config" / "label_dictionary.yaml"

_LABEL_DICT_CACHE: dict | None = None


def _load_label_dictionary() -> dict:
    global _LABEL_DICT_CACHE
    if _LABEL_DICT_CACHE is None:
        if not LABEL_DICTIONARY_PATH.exists():
            log.warning("label_dictionary_missing", path=str(LABEL_DICTIONARY_PATH))
            _LABEL_DICT_CACHE = {"labels": {}, "evidence_categories": {}}
        else:
            try:
                _LABEL_DICT_CACHE = (
                    yaml.safe_load(LABEL_DICTIONARY_PATH.read_text(encoding="utf-8")) or {}
                )
            except Exception as e:  # noqa: BLE001
                log.warning("label_dictionary_load_failed", error=str(e))
                _LABEL_DICT_CACHE = {"labels": {}, "evidence_categories": {}}
    return _LABEL_DICT_CACHE


def reload_label_dictionary() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _LABEL_DICT_CACHE, _SCRUB_RULES_CACHE
    _LABEL_DICT_CACHE = None
    _SCRUB_RULES_CACHE = None


# ---------------------------------------------------------------------------
# 결정론 코드 라벨 스크러버 (ARCHITECTURE-HYBRID-EXECUTIVE-001 SLOT — Flash 누출 보험)
# ---------------------------------------------------------------------------
#
# system prompt 사전 주입만으론 약한 모델(Flash)이 `sweet`/`S-Score` 같은 코드 라벨을
# 본문에 잔존 노출. label_dictionary 를 단일 소스로 출력 텍스트에서 결정론 역치환 →
# 모델 무관 production-clean. natural 이 아니라 short 로 치환 (본문엔 간결형).

_SCRUB_RULES_CACHE: list[tuple[re.Pattern[str], str]] | None = None


def _is_code_form(label: str) -> bool:
    """스크러빙 대상 판정 — ASCII 알파벳 또는 그리스 α 를 포함한 '코드형' 라벨만.

    순수 한국어 key (`분배일` 등) 는 제외 — 이미 자연어라 이중 wrap 방지.
    """
    return bool(re.search(r"[A-Za-z]", label)) or "α" in label


def _scrub_rules() -> list[tuple[re.Pattern[str], str]]:
    """label_dictionary → (경계 인식 정규식, short 치환어) 리스트. 길이 내림차순.

    길이 내림차순: `S-Score` 가 `Score` 보다, `RS Score` 가 `RS` 보다 먼저 매칭.
    경계 `(?<![A-Za-z0-9_]) ... (?![A-Za-z0-9_])`: 짧은 ASCII 토큰(`RS`)이 영단어
    내부에서 오치환되는 것 방지 (한국어 인접은 경계로 막지 않으므로 정상 치환).
    """
    global _SCRUB_RULES_CACHE
    if _SCRUB_RULES_CACHE is None:
        labels = _load_label_dictionary().get("labels") or {}
        rules: list[tuple[re.Pattern[str], str]] = []
        for code, mapping in labels.items():
            if not _is_code_form(str(code)):
                continue
            if isinstance(mapping, dict):
                repl = mapping.get("short") or mapping.get("natural") or str(code)
            else:
                repl = str(mapping)
            pattern = re.compile(
                r"(?<![A-Za-z0-9_])" + re.escape(str(code)) + r"(?![A-Za-z0-9_])",
                re.IGNORECASE,
            )
            rules.append((pattern, str(repl)))
        rules.sort(key=lambda r: len(r[0].pattern), reverse=True)
        _SCRUB_RULES_CACHE = rules
    return _SCRUB_RULES_CACHE


def scrub_code_labels(text: str) -> str:
    """출력 텍스트에서 잔존 코드 라벨을 자연어 short 로 결정론 치환.

    format_answer / synthesize_executive 반환 직전에 적용 (모든 경로 일괄 커버).
    """
    if not text:
        return text
    for pattern, repl in _scrub_rules():
        text = pattern.sub(repl, text)
    return text


def _build_label_block() -> str:
    """label_dictionary → system prompt 의 사전 블록."""
    d = _load_label_dictionary()
    labels = d.get("labels") or {}
    cats = d.get("evidence_categories") or {}
    lines = [
        "## 코드 라벨 자연어 변환 사전 (절대 본문에 코드 라벨 노출 금지)",
        "",
    ]
    for code, mapping in labels.items():
        natural = (mapping or {}).get("natural", code) if isinstance(mapping, dict) else str(mapping)
        lines.append(f"- `{code}` → \"{natural}\"")
    lines.append("")
    lines.append("## 근거 3요소 (raw 에서 추출해 자연어로 풀이)")
    for cat, hint in cats.items():
        lines.append(f"- **{cat}**: {hint}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatter system prompt
# ---------------------------------------------------------------------------

_FORMATTER_SYSTEM = """당신은 wevelStock 의 자연어 답변 압축기입니다. 분석가/전략가들의 raw 응답
(cited + 격자 + 코드 라벨 풍부) 을 받아 사용자 발화에 직접 답변하는 짧은 자연어로 변환합니다.

## 출력 양식 (엄격)

```
[1~3줄 자연어 결론]

근거:
- [수급] 1줄 자연어 (외국인/기관 흐름, 시장 폭)
- [차트] 1줄 자연어 (추세, 가속도, 이동평균선)
- [실적] 1줄 자연어 (EPS/매출/F-Score 등 펀더멘털)
```

## 절대 규칙

1. **코드 라벨 본문 노출 금지** — `S-Score`, `α`, `F-Score`, `T-Score`, `buy_score`, `regime`,
   `verdict`, `cited`, `confidence`, `RS`, `breadth`, `divergence`, `Distribution Day`, `분배일`
   같은 문자열을 절대 본문에 노출하지 말 것. 위 변환 사전의 자연어로 대체.
2. **결론 ≤ 3줄, 근거 각 ≤ 1줄** — 사용자가 길게 읽지 않고 즉시 결정 가능.
3. **명령조 X, 친근체** — "~합니다 / ~예요" 톤. 격식체 + 반말 혼용 금지.
4. **3요소 모두 채우기** — raw 에 정보 부족하면 "정보 부족" 명시. 환각 금지.
5. **사용자 발화에 직접 답변** — "삼성전자 살까?" → "지금은 보류 권고예요" 식. 양식 YAML 그대로 노출 X.
6. **분석가 prefetch + 전략가 응답 종합** — 한쪽만 인용하지 말고 둘 다 통합.

## 입력 형식

사용자 발화 + 분석가 N명 raw + 전략가 M명 raw → 한 응답.
"""


_FORMATTER_DISCOVERY_SYSTEM = """당신은 wevelStock 의 종목 추천 답변기입니다. 사용자가 특정 종목을
지정하지 않고 추천을 요청했고, 종목선정가가 결정론 스크리닝 랭킹에서 후보 셔틀리스트를 발행했습니다.
사용자가 보는 것은 **추천 후보 목록** — "수급/차트/실적" 판단 양식이 아닙니다.

## 출력 양식 (엄격)

```
[1줄: 시장 체제 + 추천 톤 (예: "지금은 선별해서 접근하는 게 좋아요")]

추천 후보:
- 종목명: 한 줄 근거(강세·수급·추세) + 위험(과열·추격 등)
- … (종목선정가가 고른 3~5종만)

[1줄: 시장 경고 — 약세/매도신호 누적 시 "전반 보수적, 분할 접근" 등]
```

## 절대 규칙

1. **코드 라벨 본문 노출 금지** — `S-Score`, `RS`, `과열도`, `screening_score`, `regime`, `verdict`,
   `buy_score`, `분배일`, `Distribution Day` 등 → 자연어로 대체("상대강도 강함"→"시장 대비 강해요").
2. **종목선정가가 고른 후보만** — 셔틀리스트·종목선정가 응답에 없는 종목 임의 추가 금지(환각).
3. **후보가 없거나 비었으면** 솔직히 "지금은 추천할 만한 종목이 마땅치 않아요" + 한 줄 이유.
4. **전략가 응답은 시장 경고용으로만** — 전략가가 "관망"이라 해도 종목선정가 후보를 버리지 말 것.
   후보는 제시하되 시장 위험을 마지막 줄에 병기.
5. **친근체** ("~예요/~해요"). 종목명은 한글로(코드 옆 병기 가능).
"""


@dataclass
class FormatterResult:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    is_mock: bool
    upstream_error: str | None = None


def _is_mock_entry(entry: dict[str, Any]) -> bool:
    """raw 응답이 mock fallback 또는 LLM 호출 실패 결과인지 판정.

    mock 또는 upstream 실패한 응답을 formatter 입력으로 흘리면 자연어 답변에
    가짜 narrative 가 섞일 위험. 입력에서 제외 + 사용자에게 누락 명시.
    """
    md = entry.get("metadata") or {}
    if md.get("is_mock"):
        return True
    if md.get("upstream_error"):
        return True
    return False


def _compose_user_message(
    user_input: str,
    analyst_outputs: list[dict[str, Any]],
    strategist_outputs: list[dict[str, Any]],
) -> str:
    """formatter 호출용 user prompt — 사용자 발화 + raw 응답 풀세트.

    is_mock/upstream_error/호출 실패/빈 응답 은 본문에서 제외하고 끝에 누락
    목록만 한 줄로 명시. 자연어 답변에 mock narrative 가 섞이는 것 방지.
    """
    lines: list[str] = []
    lines.append(f"## 사용자 발화\n{user_input}\n")

    failed_analysts: list[str] = []
    failed_strategists: list[str] = []

    if analyst_outputs:
        lines.append("## 분석가 raw 응답 (prefetch 동시 호출)")
        for entry in analyst_outputs:
            aid = entry.get("id") or entry.get("agent_id", "?")
            text = (entry.get("text") or "").strip()
            err = entry.get("error")
            if err or _is_mock_entry(entry):
                failed_analysts.append(str(aid))
                continue
            if not text:
                failed_analysts.append(str(aid))
                continue
            # 각 분석가 응답 길이 제한 — formatter prompt 폭발 방지
            if len(text) > 2000:
                text = text[:2000] + "\n... (truncated)"
            lines.append(f"\n### {aid}\n{text}")
        lines.append("")
    if strategist_outputs:
        lines.append("## 전략가 raw 응답 (권고 본문)")
        for entry in strategist_outputs:
            sid = entry.get("agent_id", "?")
            text = (entry.get("text") or "").strip()
            err = entry.get("error")
            if err or _is_mock_entry(entry):
                failed_strategists.append(str(sid))
                continue
            if not text:
                failed_strategists.append(str(sid))
                continue
            if len(text) > 4000:
                text = text[:4000] + "\n... (truncated)"
            lines.append(f"\n### {sid}\n{text}")
        lines.append("")

    if failed_analysts or failed_strategists:
        lines.append("## 응답 누락 (LLM 호출 실패 또는 mock fallback)")
        if failed_analysts:
            lines.append(f"- 분석가 누락: {', '.join(failed_analysts)}")
        if failed_strategists:
            lines.append(f"- 전략가 누락: {', '.join(failed_strategists)}")
        lines.append(
            "위 영역은 본 답변에서 제외해주세요. 정보 부족 시 결론에서 '일부 분석 누락 — 잠시 후 재시도 권장' 으로 안내."
        )
        lines.append("")

    lines.append("위 raw 응답들을 종합하여 사용자 발화에 답변하는 자연어 1~3줄 결론 + 근거 3요소 양식으로 정리해주세요.")
    return "\n".join(lines)


async def format_answer(
    user_input: str,
    analyst_outputs: list[dict[str, Any]],
    strategist_outputs: list[dict[str, Any]],
    *,
    provider: str | None = None,
    discovery: bool = False,
) -> FormatterResult:
    """분석가 + 전략가 raw → 자연어 1~3줄 결론 + 근거 3요소.

    Args:
        user_input: 사용자 발화 (분류기에 들어간 원문).
        analyst_outputs: prefetch 분석가 list (각 dict = {id, text, metadata, error}).
        strategist_outputs: 전략가 list (각 dict = {agent_id, text, metadata, error}).
        provider: 명시 backend (None = config + auto fallback).

    Returns:
        FormatterResult(text, model, tokens_in/out, cost, latency_ms, is_mock).
        실패 시 text = 짧은 안내 + upstream_error 채움.
    """
    provider_resolved, model = resolve_model_for_area("answer_formatter")
    if provider:
        provider_resolved = provider

    # 모든 분석가/전략가 응답이 mock/error/빈 응답이면 LLM 호출 자체를 skip.
    # 자연어 답변에 가짜 narrative 가 섞이는 것 차단.
    started = time.monotonic()

    def _has_real(entries: list[dict[str, Any]]) -> bool:
        for e in entries:
            if e.get("error"):
                continue
            if _is_mock_entry(e):
                continue
            if (e.get("text") or "").strip():
                return True
        return False

    if not _has_real(analyst_outputs) and not _has_real(strategist_outputs):
        log.warning(
            "formatter_all_responses_missing",
            analyst_count=len(analyst_outputs),
            strategist_count=len(strategist_outputs),
        )
        return FormatterResult(
            text=(
                "분석가/전략가 응답을 받지 못했습니다 (LLM 호출 실패 또는 mock fallback). "
                "잠시 후 다시 시도해주세요."
            ),
            model=model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
            is_mock=False,
            upstream_error="all_upstream_responses_missing",
        )

    system_blocks: list[dict] = [
        {"type": "text", "text": _FORMATTER_DISCOVERY_SYSTEM if discovery else _FORMATTER_SYSTEM},
        {"type": "text", "text": _build_label_block()},
    ]
    user_msg = _compose_user_message(user_input, analyst_outputs, strategist_outputs)
    try:
        resp = await call_llm(
            system=system_blocks,
            messages=[{"role": "user", "content": user_msg}],
            model=model,
            max_tokens=800,
            temperature=0.3,
            provider=provider_resolved if provider_resolved != "mock" else None,
            mock_fallback_allowed=False,
        )
    except Exception as e:  # noqa: BLE001
        log.error(
            "formatter_call_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        return FormatterResult(
            text=(
                "응답 정리에 실패했습니다. raw 응답을 직접 확인해주세요. "
                f"(오류: {type(e).__name__})"
            ),
            model=model,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
            is_mock=False,
            upstream_error=str(e),
        )
    latency_ms = int((time.monotonic() - started) * 1000)
    raw = resp.get("raw") or {}
    is_mock = "-mock" in str(resp.get("model", "")) or bool(raw.get("mock"))
    return FormatterResult(
        text=scrub_code_labels(resp.get("content", "")),
        model=resp.get("model", model),
        tokens_in=int(resp.get("tokens_in", 0)),
        tokens_out=int(resp.get("tokens_out", 0)),
        cost_usd=float(resp.get("cost_usd", 0.0)),
        latency_ms=latency_ms,
        is_mock=is_mock,
        upstream_error=raw.get("error"),
    )
