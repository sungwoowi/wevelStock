"""가이드 품질 검증 probe — production-chat 경로 직접 구동 → md 기록 (재사용 도구).

production_chat.post_production_chat 미러: classify_intent → route_intent → format_answer.
provider=gemini (실 배포 경로). 결과를 utf-8 md 파일로 누적 기록(사용자 검토용, cp949 회피).
gemini 503 일시 과부하는 query 단위 1회 재시도.

usage: uv run python scripts/_guide_probe.py "<out.md>" "질의1" ["질의2" ...]
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from core.intent import classify_intent, format_answer, route_intent

PROVIDER = "gemini"


def _is_transient(msg: str | None) -> bool:
    return bool(msg) and ("503" in msg or "UNAVAILABLE" in msg or "high demand" in msg)


async def _run_once(query: str) -> list[str]:
    """단일 query 1회 실행 → md 라인. 실패 시 예외 전파(상위서 재시도)."""
    L: list[str] = []
    cls = await classify_intent(query, provider=PROVIDER)
    L.append(f"## 질의: {query}\n")
    L.append("### 분류 (intent)")
    L.append(f"- scenario `{cls.scenario_id}` · route `{cls.agent_route}` · "
             f"종목 `{cls.ticker}` ({cls.ticker_display}) · 확신도 {cls.confidence:.2f} · "
             f"stage {cls.stage}")
    L.append(f"- 호출 분석가: {cls.analyst_ids}")
    if cls.manual_fallback_required:
        L.append("- ⚠ manual_fallback_required (확신도 낮음/종목 미매핑)")
    L.append("")

    messages = [{"role": "user", "content": query}]
    route = await route_intent(cls, messages, provider=PROVIDER)
    analyst_outputs = [r for r in route.agent_responses
                       if r.get("kind") in ("analyst", "analyst_prefetch")]
    strategist_outputs = [r for r in route.agent_responses
                          if r.get("kind") in ("strategist", "refuse_or_guide", "pending_ms5")]

    L.append(f"### 에이전트 {len(route.agent_responses)}개 (route.error={route.error})")
    transient = False
    for r in route.agent_responses:
        aid = r.get("agent") or r.get("id") or r.get("agent_id") or "?"
        kind = r.get("kind")
        meta = r.get("metadata") or {}
        score_keys = {k: v for k, v in meta.items()
                      if any(s in k for s in ("score", "cited", "advisory", "verdict"))}
        up = meta.get("upstream_error") or r.get("error")
        if _is_transient(up):
            transient = True
        flags = []
        if meta.get("is_mock"):
            flags.append("⚠MOCK")
        if up:
            flags.append(f"err={up[:80]}")
        L.append(f"- `{kind}` **{aid}** {('· '.join(flags)) or 'ok'}")
        if score_keys:
            L.append(f"  - 점수: `{score_keys}`")
    L.append("")

    discovery = cls.ticker is None and cls.agent_route in ("track_a", "track_b", "both")
    fmt = await format_answer(
        user_input=query, analyst_outputs=analyst_outputs,
        strategist_outputs=strategist_outputs, provider=PROVIDER, discovery=discovery,
        route=cls.agent_route, scenario_id=cls.scenario_id, ticker=cls.ticker,
    )
    if _is_transient(fmt.upstream_error):
        transient = True
    L.append(f"### 종합 가이드 (사용자가 보는 답변)")
    L.append(f"_model={fmt.model} · is_mock={fmt.is_mock} · err={fmt.upstream_error} · "
             f"${fmt.cost_usd:.4f} · {fmt.latency_ms}ms_")
    L.append("")
    L.append("> " + (fmt.text or "(빈 응답)").replace("\n", "\n> "))
    L.append("")
    if transient:
        L.append("_⚠ 일부 호출에 gemini 503 일시 과부하 흔적 — 재시도해도 남으면 인프라 노이즈_")
        L.append("")
    L.append("---\n")
    return L


async def probe(query: str) -> list[str]:
    for attempt in (1, 2):
        try:
            lines = await _run_once(query)
            # 전략가/포맷터 전부 transient 로 깨졌으면 1회 재시도
            if attempt == 1 and any("⚠ 일부 호출에 gemini 503" in x for x in lines):
                await asyncio.sleep(8)
                continue
            return lines
        except Exception as e:  # noqa: BLE001
            if attempt == 1:
                await asyncio.sleep(8)
                continue
            return [f"## 질의: {query}\n\n**❌ 실행 실패**: `{type(e).__name__}: {e}`\n\n---\n"]
    return []


async def main() -> None:
    if len(sys.argv) < 3:
        print("usage: _guide_probe.py '<out.md>' '질의1' ['질의2' ...]")
        return
    out_path = Path(sys.argv[1])
    queries = sys.argv[2:]
    header = ["# 가이드 품질 검증 — production-chat (provider=gemini)\n",
              f"_총 {len(queries)}개 질의 · 실 배포 경로(classify→route→format)_\n", "---\n"]
    out_path.write_text("\n".join(header), encoding="utf-8")
    for i, q in enumerate(queries, 1):
        print(f"[{i}/{len(queries)}] {q}")
        lines = await probe(q)
        with out_path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"  → 기록됨 ({out_path})")


if __name__ == "__main__":
    asyncio.run(main())
