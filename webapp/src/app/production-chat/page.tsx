"use client";

/**
 * PRODUCTION-UX-001 — 자연어 채팅창 production UX (PROD-UX-1).
 *
 * 하나의 채팅 입력창 + 분류 결과 헤더 + agent 별 응답 카드.
 * 사용자가 코드 라벨(S-Score/α/F-Score) 노출 없이 시스템을 자연어로 사용하는 진입점.
 *
 * v1 시연 = 시나리오 1~5:
 *   "삼성전자 들고 있는데?" → 시나리오 1 → track_a
 *   "삼성전자 살까?"        → 시나리오 2 → both (track_a + track_b)
 *   "지금 시장 어때?"       → 시나리오 3 → market_state_analyzer 직접
 *   "어떤 섹터 강해?"        → 시나리오 4 → stock_picker + market_state_analyzer
 *   "지금 뭐 사?"           → 시나리오 5 → both
 *
 * SSE 프로토콜:
 *   { type: "classification", scenario_id, ticker, agent_route, confidence, ... }
 *   { type: "agent_start", agent, kind }
 *   { type: "text_delta", text, agent }
 *   { type: "agent_metadata", agent, ...metadata }
 *   { type: "agent_done", agent }
 *   { type: "done" }
 *
 * PROD-UX-1 = raw 응답 그대로 표시. 자연어 1~3줄 압축 + label_dictionary 는 PROD-UX-2 후속.
 */

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

type Role = "user" | "assistant";
type Message = { role: Role; content: string };

type Classification = {
  scenario_id: number;
  ticker: string | null;
  ticker_display: string | null;
  agent_route: string;
  analyst_ids: string[];
  confidence: number;
  manual_fallback_required: boolean;
  stage: "deterministic" | "cache" | "llm";
  latency_ms: number;
  raw_input: string;
  reasoning: string | null;
  upstream_error?: string | null;
};

type AgentMetadata = {
  agent: string;
  model?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd?: number;
  latency_s?: number;
  first_token_ms?: number | null;
  is_mock?: boolean;
  upstream_error?: string | null;
  analyst_published_count?: number;
  analyst_missing_count?: number;
};

type AgentResponse = {
  agent: string;
  kind: string; // strategist | analyst | refuse_or_guide | pending_ms5
  text: string;
  metadata?: AgentMetadata;
  error?: string | null;
  done: boolean;
};

const SCENARIO_NAMES: Record<number, string> = {
  1: "보유 종목 결정",
  2: "신규 진입",
  3: "시장 판단",
  4: "섹터 선택",
  5: "주도주 진입",
  6: "매도 시그널",
  7: "손절 발동",
  8: "추매 시그널",
  9: "시장 위기",
  10: "계좌 안심",
  11: "자가 진화",
};

const SAMPLE_PROMPTS = [
  "삼성전자 들고 있는데 어떻게 해",
  "삼성전자 살까?",
  "지금 시장 어때",
  "어떤 섹터 강해?",
  "지금 뭐 사?",
];

function ClassificationBadge({ c }: { c: Classification }) {
  const scenarioName = SCENARIO_NAMES[c.scenario_id] || "분류 미정";
  const confColor =
    c.confidence >= 0.85
      ? "bg-emerald-900 text-emerald-200"
      : c.confidence >= 0.6
      ? "bg-amber-900 text-amber-200"
      : "bg-red-900 text-red-200";
  const stageLabel =
    c.stage === "deterministic"
      ? "결정론"
      : c.stage === "cache"
      ? "캐시"
      : "LLM";
  return (
    <div className="border border-neutral-800 bg-neutral-900/50 rounded-md p-2 text-xs space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-neutral-500">시나리오</span>
        <span className="px-2 py-0.5 rounded bg-neutral-800 text-neutral-200">
          {c.scenario_id} · {scenarioName}
        </span>
        <span className="font-mono text-neutral-500">→ 호출</span>
        <span className="px-2 py-0.5 rounded bg-neutral-800 text-emerald-300 font-mono">
          {c.agent_route}
          {c.analyst_ids.length > 0 ? `: [${c.analyst_ids.join(", ")}]` : ""}
        </span>
        {c.ticker_display && (
          <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-200">
            {c.ticker_display} ({c.ticker})
          </span>
        )}
        <span className={`px-2 py-0.5 rounded ${confColor}`}>
          신뢰도 {(c.confidence * 100).toFixed(0)}%
        </span>
        <span className="text-neutral-500">{stageLabel} · {c.latency_ms}ms</span>
      </div>
      {c.manual_fallback_required && (
        <div className="text-amber-400">
          ⚠ 분류 신뢰도 낮음 — 직접 시나리오/종목 선택 권장 (manual fallback 은 PROD-UX-2)
        </div>
      )}
      {c.reasoning && (
        <div className="text-neutral-500 italic">근거: {c.reasoning}</div>
      )}
      {c.upstream_error && (
        <div className="text-red-400">LLM 오류: {c.upstream_error}</div>
      )}
    </div>
  );
}

function AgentCard({ ar }: { ar: AgentResponse }) {
  const kindLabel =
    ar.kind === "strategist"
      ? "전략가"
      : ar.kind === "analyst"
      ? "분석가"
      : ar.kind === "refuse_or_guide"
      ? "안내"
      : ar.kind === "pending_ms5"
      ? "(MS5 대기)"
      : ar.kind;
  const borderColor = ar.error
    ? "border-red-800"
    : ar.metadata?.is_mock
    ? "border-amber-700"
    : "border-neutral-800";
  return (
    <div className={`border ${borderColor} rounded-md p-3 bg-neutral-950 space-y-2`}>
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wider text-neutral-500">
            {kindLabel}
          </span>
          <span className="font-mono text-sm text-emerald-300">{ar.agent}</span>
          {!ar.done && (
            <span className="text-xs text-neutral-500 animate-pulse">스트리밍 중...</span>
          )}
        </div>
        {ar.metadata && (
          <div className="text-[11px] text-neutral-500 font-mono space-x-2">
            {ar.metadata.model && <span>{ar.metadata.model}</span>}
            {ar.metadata.is_mock && (
              <span className="text-amber-400">⚠ MOCK (실 LLM 호출 X)</span>
            )}
            {typeof ar.metadata.first_token_ms === "number" && (
              <span>first {ar.metadata.first_token_ms}ms</span>
            )}
            {typeof ar.metadata.latency_s === "number" && (
              <span>{ar.metadata.latency_s}s</span>
            )}
            {typeof ar.metadata.cost_usd === "number" && (
              <span>${ar.metadata.cost_usd.toFixed(4)}</span>
            )}
          </div>
        )}
      </div>
      {ar.metadata?.upstream_error && (
        <div className="text-xs text-red-400">
          업스트림 오류: {ar.metadata.upstream_error}
        </div>
      )}
      {ar.error && (
        <div className="text-xs text-red-400">에러: {ar.error}</div>
      )}
      <pre className="whitespace-pre-wrap break-words text-sm text-neutral-200 font-sans">
        {ar.text || (ar.done ? "(빈 응답)" : "")}
      </pre>
      {ar.metadata?.analyst_published_count != null && (
        <div className="text-[11px] text-neutral-500">
          분석가 read 발행 {ar.metadata.analyst_published_count} · 미발행{" "}
          {ar.metadata.analyst_missing_count ?? 0}
        </div>
      )}
    </div>
  );
}

export default function ProductionChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [classification, setClassification] = useState<Classification | null>(null);
  const [agentResponses, setAgentResponses] = useState<AgentResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [agentResponses, classification]);

  async function sendMessage(text: string) {
    if (!text.trim() || streaming) return;
    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setStreaming(true);
    setClassification(null);
    setAgentResponses([]);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/api/chat/production/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: newMessages }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`${res.status} ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      const agentState = new Map<string, AgentResponse>();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const dataMatch = line.match(/^data:\s*(.+)$/m);
          if (!dataMatch) continue;
          let evt: any;
          try {
            evt = JSON.parse(dataMatch[1]);
          } catch {
            continue;
          }
          const t = evt.type;
          if (t === "classification") {
            setClassification(evt as Classification);
          } else if (t === "agent_start") {
            const ar: AgentResponse = {
              agent: evt.agent,
              kind: evt.kind,
              text: "",
              done: false,
            };
            agentState.set(evt.agent, ar);
            setAgentResponses(Array.from(agentState.values()));
          } else if (t === "text_delta") {
            const agent = evt.agent;
            const existing = agentState.get(agent);
            if (existing) {
              existing.text += evt.text || "";
              setAgentResponses(Array.from(agentState.values()));
            }
          } else if (t === "agent_metadata") {
            const existing = agentState.get(evt.agent);
            if (existing) {
              existing.metadata = { ...existing.metadata, ...evt };
              setAgentResponses(Array.from(agentState.values()));
            }
          } else if (t === "agent_error") {
            const existing = agentState.get(evt.agent);
            if (existing) {
              existing.error = evt.message || "unknown error";
              setAgentResponses(Array.from(agentState.values()));
            }
          } else if (t === "agent_done") {
            const existing = agentState.get(evt.agent);
            if (existing) {
              existing.done = true;
              setAgentResponses(Array.from(agentState.values()));
            }
          } else if (t === "error") {
            setError(evt.message || "stream error");
          }
        }
      }
      // 모든 agent done
      for (const ar of agentState.values()) {
        ar.done = true;
      }
      setAgentResponses(Array.from(agentState.values()));
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        setError(`전송 실패: ${e?.message || e}`);
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  function handleAbort() {
    abortRef.current?.abort();
    setStreaming(false);
  }

  function handleReset() {
    abortRef.current?.abort();
    setMessages([]);
    setClassification(null);
    setAgentResponses([]);
    setError(null);
    setStreaming(false);
  }

  return (
    <main className="mx-auto max-w-[1100px] p-4 md:p-6 space-y-4 min-h-screen flex flex-col">
      <header className="space-y-2">
        <a href="/" className="text-xs text-neutral-500 hover:underline">
          ← wevelStock 메인
        </a>
        <div className="flex items-baseline justify-between gap-4 flex-wrap">
          <h1 className="text-2xl font-bold tracking-tight">
            production 채팅 (자연어)
            <span className="ml-3 text-sm font-normal text-neutral-500">
              PRODUCTION-UX-001 · PROD-UX-1 · 자동 라우팅 (분석가/전략가)
            </span>
          </h1>
          <div className="text-xs text-neutral-500">
            v1 시연 = 시나리오 1~5 (보유/진입/시장/섹터/주도주)
          </div>
        </div>
        <p className="text-xs text-neutral-500">
          자연어로 묻기만 하면 자동 분류 → 적절한 분석가/전략가 호출. PROD-UX-1 = raw
          응답 표시 (자연어 1~3줄 압축은 PROD-UX-2 후속). 기존 R&D 비교 UI 는{" "}
          <a href="/analyst-chat" className="underline text-emerald-400">
            /analyst-chat
          </a>{" "}
          에 보존.
        </p>
      </header>

      <div className="border border-neutral-800 rounded-md p-3 bg-neutral-900/30 text-xs space-y-2">
        <div className="text-neutral-500 uppercase tracking-wider">예시 발화 (클릭 시 자동 입력)</div>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setInput(p)}
              disabled={streaming}
              className="px-2 py-1 rounded border border-neutral-700 bg-neutral-900 hover:bg-neutral-800 disabled:opacity-50"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 min-h-[300px] overflow-y-auto space-y-3 border border-neutral-800 rounded-md p-3 bg-neutral-950"
      >
        {messages.length === 0 && !streaming && (
          <div className="text-sm text-neutral-500 text-center py-10">
            자연어로 질문해보세요. 예: "삼성전자 살까?"
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={
              m.role === "user"
                ? "text-right"
                : "text-left text-sm text-neutral-300"
            }
          >
            {m.role === "user" ? (
              <div className="inline-block bg-blue-900/50 px-3 py-1.5 rounded text-sm">
                {m.content}
              </div>
            ) : (
              <pre className="whitespace-pre-wrap break-words">{m.content}</pre>
            )}
          </div>
        ))}

        {classification && <ClassificationBadge c={classification} />}

        {agentResponses.map((ar) => (
          <AgentCard key={ar.agent} ar={ar} />
        ))}

        {error && (
          <div className="text-sm text-red-400 border border-red-900 bg-red-950/30 rounded p-2">
            {error}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={streaming}
          placeholder="자연어로 질문해주세요 (예: 삼성전자 살까?)"
          className="flex-1 bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm disabled:opacity-50"
        />
        {streaming ? (
          <button
            type="button"
            onClick={handleAbort}
            className="px-4 py-2 bg-red-800 hover:bg-red-700 rounded-md text-sm"
          >
            중단
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 disabled:opacity-50 rounded-md text-sm"
          >
            전송
          </button>
        )}
        <button
          type="button"
          onClick={handleReset}
          className="px-3 py-2 border border-neutral-700 hover:bg-neutral-800 rounded-md text-sm"
        >
          새 대화
        </button>
      </form>
    </main>
  );
}
