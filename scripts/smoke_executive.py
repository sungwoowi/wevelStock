"""ARCHITECTURE-HYBRID-EXECUTIVE-001 PoC smoke — formatter vs 임원 1:1 비교.

동일 분석가/전략가 입력에 formatter('압축기') 와 synthesize_executive('임원')를
모두 돌려 **종합 레이어 차이만 격리** 비교. 실 Gemini 호출 (TESTING 설정 X).

실행:
    uv run python scripts/smoke_executive.py            # 005930 "삼성전자 살까?"
    uv run python scripts/smoke_executive.py "셀트리온 어때?"

산출: _smoke_executive_compare.json (formatter 답변 + 임원 답변 + 메타).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Windows utf-8 stdout
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.executive import synthesize_executive
from core.intent import classify_intent, format_answer, route_intent

OUT_PATH = REPO_ROOT / "_smoke_executive_compare.json"


async def _run(user_input: str, *, skip_pro: bool = False) -> dict:
    print(f"[1/4] classify: {user_input!r}")
    classification = await classify_intent(user_input)
    print(f"      → scenario={classification.scenario_id} ticker={classification.ticker} route={classification.agent_route}")

    print("[2/4] route_intent (분석가/전략가 prefetch — 실 LLM)...")
    messages = [{"role": "user", "content": user_input}]
    route_resp = await route_intent(classification, messages)
    agent_responses = route_resp.agent_responses

    analyst_outputs = [
        r for r in agent_responses if r.get("kind") in ("analyst", "analyst_prefetch")
    ]
    strategist_outputs = [
        r for r in agent_responses
        if r.get("kind") in ("strategist", "refuse_or_guide", "pending_ms5")
    ]
    print(f"      → 분석가 {len(analyst_outputs)} / 전략가 {len(strategist_outputs)}")

    def _pack(r) -> dict:
        return {
            "text": r.text,
            "model": r.model,
            "tokens_out": r.tokens_out,
            "cost_usd": r.cost_usd,
            "latency_ms": r.latency_ms,
            "is_mock": r.is_mock,
            "upstream_error": r.upstream_error,
        }

    print("[3/5] formatter (압축기, FAST tier)...")
    fmt = await format_answer(
        user_input=user_input,
        analyst_outputs=analyst_outputs,
        strategist_outputs=strategist_outputs,
    )

    if skip_pro:
        print("[4/5] 임원 종합 — Pro SKIP (--flash, 50/일 예산 절약)")
        exe_pro = None
    else:
        print("[4/5] 임원 종합 — Pro (gemini-2.5-pro, thinking ON, max_tokens 8000)...")
        exe_pro = await synthesize_executive(
            user_input=user_input,
            analyst_outputs=analyst_outputs,
            strategist_outputs=strategist_outputs,
            model="gemini-2.5-pro",
        )

    print("[5/5] 임원 종합 — Flash (gemini-2.5-flash)...")
    exe_flash = await synthesize_executive(
        user_input=user_input,
        analyst_outputs=analyst_outputs,
        strategist_outputs=strategist_outputs,
        model="gemini-2.5-flash",
    )

    return {
        "user_input": user_input,
        "classification": route_resp.classification,
        "analyst_count": len(analyst_outputs),
        "strategist_count": len(strategist_outputs),
        "analyst_ids": [r.get("agent_id") for r in analyst_outputs],
        "strategist_ids": [r.get("agent_id") for r in strategist_outputs],
        "formatter": _pack(fmt),
        "executive_pro": _pack(exe_pro) if exe_pro is not None else None,
        "executive_flash": _pack(exe_flash),
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skip_pro = "--flash" in sys.argv
    user_input = args[0] if args else "삼성전자 살까?"
    result = asyncio.run(_run(user_input, skip_pro=skip_pro))
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    def _meta(d: dict) -> str:
        return (f"model={d['model']} / out={d['tokens_out']}tok / {d['latency_ms']}ms "
                f"/ ${d['cost_usd']:.4f}" + (f" / ⚠{d['upstream_error']}" if d['upstream_error'] else ""))

    print("\n" + "=" * 70)
    print(f"질문: {result['user_input']}")
    print(f"분석가 {result['analyst_count']} / 전략가 {result['strategist_count']}")
    print("=" * 70)
    print("\n──────── [A] formatter (현행 '압축기' · FAST) ────────")
    print(result["formatter"]["text"])
    print(f"\n  ({_meta(result['formatter'])})")
    if result.get("executive_pro"):
        print("\n──────── [B] 임원 — Gemini 2.5 Pro (thinking) ────────")
        print(result["executive_pro"]["text"])
        print(f"\n  ({_meta(result['executive_pro'])})")
    print("\n──────── [C] 임원 — Gemini 2.5 Flash (튜닝 doctrine) ────────")
    print(result["executive_flash"]["text"])
    print(f"\n  ({_meta(result['executive_flash'])})")
    print("\n" + "=" * 70)
    print("비용·속도 한눈에:")
    for k in ("formatter", "executive_pro", "executive_flash"):
        if result.get(k):
            print(f"  {k:16s} {_meta(result[k])}")
    print(f"저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
