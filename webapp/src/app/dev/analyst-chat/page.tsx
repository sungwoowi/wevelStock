"use client";

import { useEffect, useState } from "react";
import { ChatPane, ProviderChoice, AgentOption } from "@/components/ChatPane";
import { API_BASE } from "@/lib/api";

type ProviderName = "gemini" | "claude_code" | "anthropic" | "mock";
type LlmConfigInfo = {
  provider: ProviderName;
  model: string;
  fallback_chain: string[];
};

const STATIC_PROVIDER_OPTIONS: { value: ProviderChoice; label: string; hint: string }[] = [
  { value: "auto", label: "자동 (기본)", hint: "runtime.yaml provider + 자동 폴백" },
  { value: "gemini", label: "Gemini", hint: "Google AI Studio (저렴, 503 가능)" },
  { value: "claude_code", label: "Claude Code", hint: "Pro/Max 구독 CLI (무료, ~10s 시작)" },
];

// 9 분석가 (ANALYST-PERSONAS-001 v2). select box 옵션.
const ANALYSTS: AgentOption[] = [
  { id: "stock_analyst", label: "stock_analyst — 종목분석가 (α, F1~F5, 목표가 3단)" },
  { id: "wealth_strategist", label: "wealth_strategist — 자산전략가 (거시 framework)" },
  { id: "principle_guardian", label: "principle_guardian — 원칙수호자 (7계명·verdict)" },
  { id: "trader", label: "trader — 트레이더 (T-Score, 6 트리거)" },
  { id: "market_state_analyzer", label: "market_state_analyzer — 시장상태분석가 (6 단계)" },
  { id: "stock_picker", label: "stock_picker — 종목선정가 (S-Score, buy_score)" },
  { id: "flow_analyzer", label: "flow_analyzer — 수급분석가 (F-Score, 5 주체)" },
  { id: "trading_journalist", label: "trading_journalist — 매매저널리스트 (post-mortem)" },
  { id: "news_curator", label: "news_curator — 뉴스큐레이터 (단기/장기/지정학)" },
];

// 2+ 전략가 (STRATEGY-TRACK-001).
const STRATEGISTS: AgentOption[] = [
  { id: "track_a", label: "track_a — 추세 추적 전략가 (중장기 수익금)" },
  { id: "track_b", label: "track_b — 프랙탈 1 파 전략가 (단기 손익비)" },
];

export default function AnalystChatPage() {
  const [provider, setProvider] = useState<ProviderChoice>("auto");
  const [llmConfig, setLlmConfig] = useState<LlmConfigInfo | null>(null);

  useEffect(() => {
    let aborted = false;
    fetch(`${API_BASE}/api/config/llm`)
      .then((r) => (r.ok ? r.json() : Promise.reject(`${r.status}`)))
      .then((c: LlmConfigInfo) => !aborted && setLlmConfig(c))
      .catch(() => !aborted && setLlmConfig(null));
    return () => {
      aborted = true;
    };
  }, []);

  const providerOptions = STATIC_PROVIDER_OPTIONS.map((opt) => {
    if (opt.value !== "auto" || !llmConfig) return opt;
    const chain = llmConfig.fallback_chain.join(" → ");
    return {
      ...opt,
      label: `자동 (${llmConfig.model})`,
      hint: `현재 1순위: ${llmConfig.model} · 폴백: ${chain}`,
    };
  });

  return (
    <main className="mx-auto max-w-[1600px] p-4 md:p-6 space-y-3 min-h-screen flex flex-col">
      <header className="space-y-2">
        <a href="/dev" className="text-xs text-neutral-500 hover:underline">
          ← R&D 데모 허브
        </a>
        <div className="flex items-baseline justify-between gap-4 flex-wrap">
          <h1 className="text-2xl font-bold tracking-tight">
            분석가 ↔ 전략가 비교 데모
            <span className="ml-3 text-sm font-normal text-neutral-500">
              Layer 2 · 3 · 좌/우 분할 — 동일 질문 양쪽 호출로 차이 비교
            </span>
          </h1>
          <div className="flex items-center gap-2 text-sm flex-wrap">
            <label className="text-neutral-400 text-xs">LLM</label>
            <div className="inline-flex rounded border border-neutral-700 overflow-hidden">
              {providerOptions.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setProvider(opt.value)}
                  className={
                    provider === opt.value
                      ? "px-3 py-1 text-xs bg-emerald-700 text-white"
                      : "px-3 py-1 text-xs bg-neutral-900 text-neutral-400 hover:bg-neutral-800"
                  }
                  title={opt.hint}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <span className="text-[11px] text-neutral-500 max-w-md">
              {providerOptions.find((o) => o.value === provider)?.hint}
            </span>
          </div>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-3 min-h-0">
        <ChatPane
          kind="analyst"
          title="분석가 (Layer 2)"
          subtitle="단일 dept · canon + RAG + chart_data_md [4]"
          agents={ANALYSTS}
          defaultAgentId="stock_analyst"
          provider={provider}
        />
        <ChatPane
          kind="strategist"
          title="전략가 (Layer 3)"
          subtitle="분석가 점수 종합 → 권고 발행"
          agents={STRATEGISTS}
          defaultAgentId="track_a"
          provider={provider}
        />
      </div>
    </main>
  );
}
