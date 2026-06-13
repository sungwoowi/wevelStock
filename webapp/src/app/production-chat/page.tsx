"use client";

/**
 * PRODUCTION-UX-001 — 자연어 채팅창 production UX (PROD-UX-1+2).
 *
 * 하나의 채팅 입력창 + 자연어 1~3줄 결론/근거 + 근거 토글 (raw) + manual fallback.
 *
 * PROD-UX-2 변화 (옵션 A 협동 + formatter):
 *   - 라우터가 분석가 6명 동시 호출 후 전략가에 raw 직접 주입 (DB read 우회)
 *   - formatter (FAST tier Flash-lite) 가 raw → 1~3줄 자연어 압축
 *   - 코드 라벨 (S-Score/α 등) 자연어 변환 (label_dictionary.yaml)
 *   - 근거 토글 = raw 분석가/전략가 응답 풀세트
 *   - manual fallback drop-down = 분류 신뢰도 < 0.6 시 직접 시나리오/종목 선택
 *
 * SSE 이벤트:
 *   { type: "classification", scenario_id, ticker, agent_route, confidence, ... }
 *   { type: "prefetch_start", track_ids: ["track_a", "track_b"] }
 *   { type: "analyst_prefetch", agent, text, metadata, error }
 *   { type: "prefetch_done", analysts, missing }
 *   { type: "agent_start", agent, kind }
 *   { type: "text_delta", text, agent }
 *   { type: "agent_metadata", agent, ...metadata }
 *   { type: "agent_done", agent }
 *   { type: "formatted", text, model, ...metadata }
 *   { type: "done" }
 */

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import { EvidenceToggle } from "./components/EvidenceToggle";
import { IntentFallback, ManualOverride } from "./components/IntentFallback";

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

type AgentResponse = {
  agent: string;
  kind: string;
  text: string;
  metadata?: Record<string, any>;
  error?: string | null;
  done: boolean;
};

type FormattedAnswer = {
  text: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number;
  is_mock: boolean;
  upstream_error?: string | null;
};

type Exchange = {
  user: string;
  classification?: Classification;
  prefetchTrackIds?: string[];
  agentResponses: AgentResponse[];
  formatted?: FormattedAnswer;
  streaming: boolean;
  error?: string | null;
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
    c.stage === "deterministic" ? "결정론" : c.stage === "cache" ? "캐시" : "LLM";
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
        <span className="text-neutral-500">
          {stageLabel} · {c.latency_ms}ms
        </span>
      </div>
      {c.upstream_error && (
        <div className="text-red-400">LLM 오류: {c.upstream_error}</div>
      )}
    </div>
  );
}

function FormattedAnswerCard({
  fmt,
  prefetchTrackIds,
  agentResponses,
}: {
  fmt?: FormattedAnswer;
  prefetchTrackIds?: string[];
  agentResponses: AgentResponse[];
}) {
  if (!fmt) {
    // 아직 형성 중이면 빈 placeholder + 진행 상태
    return (
      <div className="border border-neutral-800 rounded-md p-3 bg-neutral-950 text-sm text-neutral-400">
        분석가 + 전략가 응답 종합 중…
        {prefetchTrackIds && prefetchTrackIds.length > 0 && (
          <div className="text-[11px] text-neutral-500 mt-1">
            prefetch 진행: {prefetchTrackIds.join(", ")} (분석가 동시 호출)
          </div>
        )}
        {agentResponses.length > 0 && (
          <div className="text-[11px] text-neutral-500 mt-1">
            {agentResponses.filter((r) => r.done).length}/{agentResponses.length} agent 완료
          </div>
        )}
      </div>
    );
  }
  const borderColor = fmt.upstream_error
    ? "border-red-800"
    : fmt.is_mock
    ? "border-amber-700"
    : "border-emerald-800";
  return (
    <div className={`border ${borderColor} rounded-md p-3 bg-emerald-950/20 space-y-2`}>
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wider text-emerald-400">답변</span>
        <div className="text-[11px] text-neutral-500 font-mono space-x-2">
          {fmt.is_mock && (
            <span className="text-amber-400">⚠ MOCK</span>
          )}
          {fmt.model && <span>{fmt.model}</span>}
          {typeof fmt.latency_ms === "number" && <span>{fmt.latency_ms}ms</span>}
          {typeof fmt.cost_usd === "number" && fmt.cost_usd > 0 && (
            <span>${fmt.cost_usd.toFixed(4)}</span>
          )}
        </div>
      </div>
      {fmt.upstream_error && (
        <div className="text-xs text-red-400">오류: {fmt.upstream_error}</div>
      )}
      <pre className="whitespace-pre-wrap break-words text-base text-neutral-100 font-sans leading-relaxed">
        {fmt.text}
      </pre>
    </div>
  );
}

export default function ProductionChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  // 종합 모드 (ARCHITECTURE-HYBRID-EXECUTIVE-001): off=압축기(formatter) / flash=임원·Flash / pro=임원·Pro.
  // 기본 flash = 임원 종합 켜짐 (저렴·시연 즉시 체감). Pro 자동 발동 라우팅은 SLOT S7.
  const [executiveMode, setExecutiveMode] = useState<"off" | "flash" | "pro">("flash");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [exchanges]);

  async function sendMessage(text: string, manualOverride?: ManualOverride) {
    if (!text.trim() || streaming) return;
    const userMsg: Message = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setStreaming(true);

    const exchangeIdx = exchanges.length;
    setExchanges((prev) => [
      ...prev,
      { user: text, agentResponses: [], streaming: true },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const body: Record<string, any> = {
        messages: newMessages,
        manual_override: manualOverride || null,
      };
      if (executiveMode === "flash") {
        body.executive_mode = true;
      } else if (executiveMode === "pro") {
        body.executive_mode = true;
        body.executive_tier = "deep";
      }
      const res = await fetch(`${API_BASE}/api/chat/production/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`${res.status} ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      const agentMap = new Map<string, AgentResponse>();
      let prefetchTrackIds: string[] | undefined;
      let formatted: FormattedAnswer | undefined;
      let classification: Classification | undefined;

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
            classification = evt as Classification;
          } else if (t === "prefetch_start") {
            prefetchTrackIds = evt.track_ids;
          } else if (t === "analyst_prefetch") {
            const aid = evt.agent;
            agentMap.set(aid, {
              agent: aid,
              kind: "analyst_prefetch",
              text: evt.text || "",
              metadata: evt.metadata,
              error: evt.error,
              done: true,
            });
          } else if (t === "prefetch_done") {
            // no-op (이미 analyst_prefetch 들로 표시됨)
          } else if (t === "agent_start") {
            agentMap.set(evt.agent, {
              agent: evt.agent,
              kind: evt.kind,
              text: "",
              done: false,
            });
          } else if (t === "text_delta") {
            const ar = agentMap.get(evt.agent);
            if (ar) {
              ar.text += evt.text || "";
            }
          } else if (t === "agent_metadata") {
            const ar = agentMap.get(evt.agent);
            if (ar) {
              ar.metadata = { ...(ar.metadata || {}), ...evt };
            }
          } else if (t === "agent_error") {
            const ar = agentMap.get(evt.agent);
            if (ar) ar.error = evt.message;
          } else if (t === "agent_done") {
            const ar = agentMap.get(evt.agent);
            if (ar) ar.done = true;
          } else if (t === "formatted") {
            formatted = {
              text: evt.text,
              model: evt.model,
              tokens_in: evt.tokens_in,
              tokens_out: evt.tokens_out,
              cost_usd: evt.cost_usd,
              latency_ms: evt.latency_ms,
              is_mock: evt.is_mock,
              upstream_error: evt.upstream_error,
            };
          } else if (t === "formatted_error") {
            formatted = {
              text: "(자연어 정리 실패 — 아래 '근거 보기' 토글로 raw 응답 확인)",
              model: "",
              tokens_in: 0,
              tokens_out: 0,
              cost_usd: 0,
              latency_ms: 0,
              is_mock: false,
              upstream_error: evt.message,
            };
          }

          // 점진 갱신
          setExchanges((prev) => {
            const next = [...prev];
            next[exchangeIdx] = {
              ...next[exchangeIdx],
              classification,
              prefetchTrackIds,
              agentResponses: Array.from(agentMap.values()),
              formatted,
              streaming: true,
            };
            return next;
          });
        }
      }

      // 종료 후 finalize
      setExchanges((prev) => {
        const next = [...prev];
        next[exchangeIdx] = {
          ...next[exchangeIdx],
          streaming: false,
        };
        return next;
      });
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        setExchanges((prev) => {
          const next = [...prev];
          next[exchangeIdx] = {
            ...next[exchangeIdx],
            error: `전송 실패: ${e?.message || e}`,
            streaming: false,
          };
          return next;
        });
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
    setExchanges([]);
    setStreaming(false);
  }

  function handleManualOverride(idx: number, override: ManualOverride) {
    const ex = exchanges[idx];
    if (!ex) return;
    sendMessage(ex.user, override);
  }

  return (
    <main className="mx-auto max-w-[1100px] p-4 md:p-6 space-y-4 min-h-screen flex flex-col">
      <header className="space-y-2">
        <a href="/dev" className="text-xs text-neutral-500 hover:underline">
          ← R&D 데모 허브
        </a>
        <div className="flex items-baseline justify-between gap-4 flex-wrap">
          <h1 className="text-2xl font-bold tracking-tight">
            production 채팅 (자연어)
            <span className="ml-3 text-sm font-normal text-neutral-500">
              PRODUCTION-UX-001 · PROD-UX-1+2 · 분석가 협동 + 자연어 압축
            </span>
          </h1>
          <div className="text-xs text-neutral-500">
            v1 시연 = 시나리오 1~10 (보유/진입/시장/섹터/주도주/매도/손절/추매/위기/계좌)
          </div>
        </div>
        <p className="text-xs text-neutral-500">
          자연어로 묻기만 하면 자동 분류 → 분석가 동시 호출 → 전략가가 raw 통합 →
          자연어 1~3줄 결론. 근거 토글로 분석가/전략가 raw 응답 풀세트 확인. 기존
          R&D 비교 UI 는{" "}
          <a href="/analyst-chat" className="underline text-emerald-400">
            /analyst-chat
          </a>{" "}
          에 보존.
        </p>
      </header>

      <div className="border border-neutral-800 rounded-md p-3 bg-neutral-900/30 text-xs space-y-2">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-neutral-500 uppercase tracking-wider">종합 모드</span>
          <div className="inline-flex rounded border border-neutral-700 overflow-hidden">
            {([
              { value: "off", label: "압축기", hint: "formatter — raw 를 1~3줄로 압축 (현행)" },
              { value: "flash", label: "임원 · Flash", hint: "투자 총괄 임원 doctrine 종합 (Gemini Flash · 저렴)" },
              { value: "pro", label: "임원 · Pro", hint: "임원 종합 (Gemini Pro · 주요 트리거용, 50/일)" },
            ] as const).map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setExecutiveMode(opt.value)}
                disabled={streaming}
                title={opt.hint}
                className={
                  executiveMode === opt.value
                    ? "px-3 py-1 bg-emerald-700 text-white disabled:opacity-50"
                    : "px-3 py-1 bg-neutral-900 text-neutral-400 hover:bg-neutral-800 disabled:opacity-50"
                }
              >
                {opt.label}
              </button>
            ))}
          </div>
          <span className="text-neutral-600">
            {executiveMode === "off"
              ? "raw 응답을 짧게 압축만 합니다."
              : "여러 분석가·전략가 판단을 임원이 doctrine 으로 종합해 직답합니다."}
          </span>
        </div>
        <div className="text-neutral-500 uppercase tracking-wider">
          예시 발화 (클릭 시 자동 입력)
        </div>
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
        className="flex-1 min-h-[300px] overflow-y-auto space-y-4 border border-neutral-800 rounded-md p-3 bg-neutral-950"
      >
        {exchanges.length === 0 && !streaming && (
          <div className="text-sm text-neutral-500 text-center py-10">
            자연어로 질문해보세요. 예: "삼성전자 살까?"
          </div>
        )}

        {exchanges.map((ex, i) => (
          <div key={i} className="space-y-2">
            <div className="text-right">
              <div className="inline-block bg-blue-900/50 px-3 py-1.5 rounded text-sm">
                {ex.user}
              </div>
            </div>

            {ex.classification && <ClassificationBadge c={ex.classification} />}

            {ex.classification?.manual_fallback_required && (
              <IntentFallback
                defaultScenario={ex.classification.scenario_id}
                defaultTicker={ex.classification.ticker || undefined}
                onApply={(ov) => handleManualOverride(i, ov)}
              />
            )}

            <FormattedAnswerCard
              fmt={ex.formatted}
              prefetchTrackIds={ex.prefetchTrackIds}
              agentResponses={ex.agentResponses}
            />

            <EvidenceToggle
              responses={ex.agentResponses.map((ar) => ({
                kind: ar.kind,
                agent_id: ar.agent,
                text: ar.text,
                error: ar.error,
                metadata: ar.metadata,
              }))}
            />

            {ex.error && (
              <div className="text-sm text-red-400 border border-red-900 bg-red-950/30 rounded p-2">
                {ex.error}
              </div>
            )}
          </div>
        ))}
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
