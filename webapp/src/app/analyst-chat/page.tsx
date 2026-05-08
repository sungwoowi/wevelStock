"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

type Role = "user" | "assistant";
type ChatMessage = { role: Role; content: string };
type ProviderName = "gemini" | "claude_code" | "anthropic" | "mock";
type ProviderChoice = ProviderName | "auto";
type ChatMetadata = {
  analyst_id?: string;
  display_name?: string;
  rag_dept?: string;
  rag_chunks_returned?: number;
  system_prompt_chars?: number;
  cache_breakpoint_count?: number;
  tokens_in?: number;
  tokens_out?: number;
  cache_read_tokens?: number;
  cache_creation_tokens?: number;
  model?: string;
  cost_usd?: number;
  latency_s?: number;
  first_token_ms?: number | null;
  is_mock?: boolean;
  upstream_error?: string | null;
  provider_requested?: ProviderName | null;
  provider_used?: string;
};
type AnalystMeta = {
  id: string;
  display_name: string;
  learning_dept: string;
  reads: string[];
  model: string | null;
};

const CONTEXT_LIMIT = 200_000;

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

function MetadataBar({ meta }: { meta: ChatMetadata }) {
  if (!meta) return null;
  const cacheLabel =
    (meta.cache_read_tokens || 0) > 0
      ? `hit (read ${meta.cache_read_tokens?.toLocaleString()})`
      : (meta.cache_creation_tokens || 0) > 0
      ? `created (${meta.cache_creation_tokens?.toLocaleString()})`
      : "miss";
  const borderColor = meta.is_mock
    ? "border-amber-700"
    : meta.upstream_error
    ? "border-red-800"
    : "border-neutral-800";
  const providerUsed = meta.provider_used || "auto";
  const providerRequested = meta.provider_requested;
  const providerLabel =
    providerRequested && providerRequested !== providerUsed
      ? `[${providerUsed} ← req:${providerRequested}]`
      : `[${providerUsed}]`;
  return (
    <div
      className={`text-[11px] font-mono text-neutral-500 border-l-2 ${borderColor} pl-3 mt-1 leading-relaxed`}
    >
      <span className="text-neutral-400">{providerLabel}</span> · prompt{" "}
      {meta.system_prompt_chars?.toLocaleString()} chars · RAG{" "}
      {meta.rag_chunks_returned} chunks · cache {cacheLabel} · turn tokens{" "}
      {meta.tokens_in?.toLocaleString()}/{meta.tokens_out?.toLocaleString()} ·
      cost{" "}
      {providerUsed === "claude_code"
        ? "$0 (subscription)"
        : `$${meta.cost_usd?.toFixed(4)}`}{" "}
      · {meta.latency_s?.toFixed(1)}s
      {meta.first_token_ms != null && (
        <span className="text-emerald-400"> (first {meta.first_token_ms}ms)</span>
      )}{" "}
      · {meta.model}
      {meta.is_mock && (
        <span className="ml-2 px-1.5 py-0.5 bg-amber-900/40 text-amber-400 rounded">
          ⚠ MOCK fallback
        </span>
      )}
      {meta.upstream_error && (
        <div className="mt-1 text-red-400 break-all">
          [upstream error] {meta.upstream_error}
        </div>
      )}
    </div>
  );
}

export default function AnalystChatPage() {
  const [analystId, setAnalystId] = useState("wealth_strategist");
  const [analystMeta, setAnalystMeta] = useState<AnalystMeta | null | undefined>(
    undefined,
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [perTurnMeta, setPerTurnMeta] = useState<ChatMetadata[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<ProviderChoice>("auto");
  const [llmConfig, setLlmConfig] = useState<LlmConfigInfo | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let aborted = false;
    fetch(`${API_BASE}/api/analysts/${analystId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(`${r.status}`)))
      .then((m: AnalystMeta) => !aborted && setAnalystMeta(m))
      .catch(() => !aborted && setAnalystMeta(null));
    return () => {
      aborted = true;
    };
  }, [analystId]);

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

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  const providerOptions = STATIC_PROVIDER_OPTIONS.map((opt) => {
    if (opt.value !== "auto" || !llmConfig) return opt;
    const chain = llmConfig.fallback_chain.join(" → ");
    return {
      ...opt,
      label: `자동 (${llmConfig.model})`,
      hint: `현재 1순위: ${llmConfig.model} · 폴백: ${chain}`,
    };
  });

  const cumulativeIn = perTurnMeta.reduce((s, m) => s + (m.tokens_in ?? 0), 0);
  const cumulativeOut = perTurnMeta.reduce((s, m) => s + (m.tokens_out ?? 0), 0);
  const cumulativeTotal = cumulativeIn + cumulativeOut;
  const cumulativeCost = perTurnMeta.reduce(
    (s, m) => s + (m.provider_used === "claude_code" ? 0 : m.cost_usd ?? 0),
    0,
  );

  async function send() {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    setError(null);
    const next: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
    // 빈 assistant 메시지를 미리 추가 — text_delta 가 누적되며 채워짐
    setMessages([...next, { role: "assistant", content: "" }]);
    setInput("");
    setLoading(true);

    try {
      const body: { messages: ChatMessage[]; provider?: ProviderName } = {
        messages: next,
      };
      if (provider !== "auto") {
        body.provider = provider;
      }
      const res = await fetch(
        `${API_BASE}/api/analysts/${analystId}/chat/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
      );
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`${res.status} ${res.statusText}: ${detail}`);
      }
      if (!res.body) {
        throw new Error("response body is null (streaming unsupported)");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalMeta: ChatMetadata | null = null;
      let streamError: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE 프레임 분리: 두 개의 LF 가 이벤트 종결자
        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          // "data: {...}" 라인만 추출
          const line = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          const payload = line.slice(5).trim();
          if (!payload) continue;
          let event: { type: string; [k: string]: unknown };
          try {
            event = JSON.parse(payload);
          } catch {
            continue;
          }
          if (event.type === "text_delta") {
            const delta = String(event.text || "");
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (!last || last.role !== "assistant") return prev;
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...last,
                content: last.content + delta,
              };
              return updated;
            });
          } else if (event.type === "metadata") {
            // metadata 이벤트는 분석가의 풍부한 키들 포함 (run_analyst_stream 가공).
            // SSE 부속 키 (type) 만 제거.
            const { type: _t, ...rest } = event;
            void _t;
            finalMeta = rest as unknown as ChatMetadata;
          } else if (event.type === "error") {
            streamError =
              (event.message as string) || "stream error";
          }
          // "done" 은 무시 — while 루프가 자연 종료
        }
      }

      if (streamError) {
        throw new Error(streamError);
      }
      if (finalMeta) {
        setPerTurnMeta((prev) => [...prev, finalMeta!]);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      // 사용자 + 빈 assistant 모두 롤백
      setMessages((prev) => prev.slice(0, -2));
    } finally {
      setLoading(false);
    }
  }

  function clearMessages() {
    setMessages([]);
    setPerTurnMeta([]);
    setError(null);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <main className="mx-auto max-w-4xl p-6 md:p-10 space-y-4 min-h-screen flex flex-col">
      <header>
        <a href="/" className="text-xs text-neutral-500 hover:underline">
          ← wevelStock 메인
        </a>
        <h1 className="text-2xl font-bold tracking-tight mt-2">
          분석가 추론부 데모
          <span className="ml-3 text-sm font-normal text-neutral-500">
            Layer 2 · 자유 질문 → canon + RAG + persona 응답
          </span>
        </h1>
        <div className="mt-3 flex items-center gap-3 text-sm flex-wrap">
          <label className="text-neutral-400">분석가</label>
          <input
            value={analystId}
            onChange={(e) => setAnalystId(e.target.value)}
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 font-mono text-xs"
          />
          {analystMeta === undefined ? (
            <span className="text-xs text-neutral-500">분석가 메타 로딩…</span>
          ) : analystMeta ? (
            <span className="text-xs text-neutral-500">
              {analystMeta.display_name} · 학습부:{" "}
              {analystMeta.learning_dept} · RAG: {analystMeta.reads.join(",")}
            </span>
          ) : (
            <span className="text-xs text-red-500">분석가 메타 로드 실패</span>
          )}
        </div>
        <div className="mt-2 flex items-center gap-3 text-sm flex-wrap">
          <label className="text-neutral-400">LLM</label>
          <div className="inline-flex rounded border border-neutral-700 overflow-hidden">
            {providerOptions.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setProvider(opt.value)}
                disabled={loading}
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
          <span className="text-[11px] text-neutral-500">
            {providerOptions.find((o) => o.value === provider)?.hint}
          </span>
        </div>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-neutral-925 border border-neutral-800 rounded-md p-4 space-y-4 min-h-[300px]"
      >
        {messages.length === 0 && (
          <div className="text-sm text-neutral-500 italic">
            예: "지금 자산 비중을 어떻게 가져가야 할까?" "원달러 1450 돌파
            시그널 어떻게 봐?" — 멀티턴으로 캐치볼 가능
          </div>
        )}
        {messages.map((m, i) => {
          const meta =
            m.role === "assistant"
              ? perTurnMeta[Math.floor(i / 2)]
              : null;
          return (
            <div key={i}>
              <div
                className={
                  m.role === "user"
                    ? "text-xs uppercase tracking-wide text-neutral-500 mb-1"
                    : "text-xs uppercase tracking-wide text-emerald-500 mb-1"
                }
              >
                {m.role === "user" ? "you" : analystMeta?.display_name || analystId}
              </div>
              <div className="whitespace-pre-wrap text-sm leading-relaxed">
                {m.content}
              </div>
              {meta && <MetadataBar meta={meta} />}
            </div>
          );
        })}
        {loading && (
          <div className="text-xs text-neutral-500 italic">
            분석가가 생각 중…
          </div>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-400 font-mono border border-red-900 rounded p-2 bg-red-950/30">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={3}
          placeholder="질문을 입력하세요. Ctrl+Enter 로 전송."
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-sm resize-none focus:border-emerald-700 focus:outline-none"
          disabled={loading}
        />
        <div className="flex items-center justify-between text-xs">
          <div className="text-neutral-500 font-mono">
            누적 {cumulativeTotal.toLocaleString()}/
            {CONTEXT_LIMIT.toLocaleString()} tokens · 비용 $
            {cumulativeCost.toFixed(4)} · {messages.length / 2} turn
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={clearMessages}
              disabled={messages.length === 0 || loading}
              className="text-xs px-3 py-1 border border-neutral-700 rounded hover:bg-neutral-800 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              /clear
            </button>
            <button
              type="button"
              onClick={() => void send()}
              disabled={loading || !input.trim()}
              className="text-xs px-4 py-1 bg-emerald-700 hover:bg-emerald-600 rounded disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {loading ? "…" : "전송 (Ctrl+Enter)"}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
