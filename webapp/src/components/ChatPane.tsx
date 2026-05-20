"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";

type Role = "user" | "assistant";
type ChatMessage = { role: Role; content: string };
export type ProviderName = "gemini" | "claude_code" | "anthropic" | "mock";
export type ProviderChoice = ProviderName | "auto";
export type PaneKind = "analyst" | "strategist";

export type AgentOption = { id: string; label: string };

export type ChatMetadata = {
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
  // analyst 전용
  analyst_id?: string;
  learning_dept?: string;
  // INFRA-CHART-DATA-001 — stock_analyst 만
  chart_ticker?: string | null;
  chart_source?: string | null;
  chart_ohlcv_count?: number | null;
  chart_data_age_seconds?: number | null;
  chart_failures?: string[];
  // strategist 전용
  strategist_id?: string;
  track?: string;
  target?: string;
  reads_analysts?: string[];
  analyst_published_count?: number;
  analyst_missing_count?: number;
  analyst_missing_ids?: string[];
};

type AnalystMeta = {
  id: string;
  display_name: string;
  learning_dept: string;
  reads: string[];
  model: string | null;
};
type StrategistMeta = {
  id: string;
  display_name: string;
  track: string;
  reads_analysts: string[];
  reads: string[];
  canon_categories: string[];
  model: string | null;
  max_tokens: number;
  temperature: number;
};
type AgentMeta =
  | { kind: "analyst"; data: AnalystMeta }
  | { kind: "strategist"; data: StrategistMeta };

const CONTEXT_LIMIT = 200_000;

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
  const isStrategist = meta.strategist_id != null;
  const published = meta.analyst_published_count ?? 0;
  const missing = meta.analyst_missing_count ?? 0;
  const total = published + missing;
  const missingIds = meta.analyst_missing_ids || [];
  // INFRA-CHART-DATA-001 — chart 메타 (stock_analyst)
  const hasChart = meta.chart_ticker != null;
  const chartSrc = meta.chart_source || "unknown";
  const chartFailures = meta.chart_failures || [];
  const chartSrcColor =
    chartSrc === "db" || chartSrc === "kis"
      ? "text-emerald-400"
      : chartSrc === "stale_cache"
      ? "text-amber-400"
      : "text-red-400";
  return (
    <div
      className={`text-[11px] font-mono text-neutral-500 border-l-2 ${borderColor} pl-3 mt-1 leading-relaxed`}
    >
      <span className="text-neutral-400">{providerLabel}</span>
      {isStrategist && (
        <>
          {" "}· track {meta.track || "?"} · target {meta.target || "global"} ·{" "}
          <span
            className={missing > 0 ? "text-amber-400" : "text-emerald-400"}
            title={missing > 0 ? `missing: ${missingIds.join(",")}` : "all analysts published"}
          >
            scores {published}/{total}
          </span>
        </>
      )}
      {hasChart && (
        <>
          {" "}· chart{" "}
          <span className={chartSrcColor} title={chartFailures.length ? `failures: ${chartFailures.join(", ")}` : "OK"}>
            {chartSrc}
          </span>
          {meta.chart_ohlcv_count != null && meta.chart_ohlcv_count > 0 && (
            <> ({meta.chart_ohlcv_count}봉)</>
          )}
        </>
      )}
      {" "}· prompt{" "}
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

type ChatPaneProps = {
  kind: PaneKind;
  title: string;
  subtitle: string;
  agents: AgentOption[];
  defaultAgentId: string;
  provider: ProviderChoice;
  /** stock_analyst chart_data_md 주입용 ticker. analyst 면 stock_analyst 선택 시만 노출. strategist 면 항상 노출 (target). */
  showTickerField?: boolean;
};

export function ChatPane({
  kind,
  title,
  subtitle,
  agents,
  defaultAgentId,
  provider,
  showTickerField = true,
}: ChatPaneProps) {
  const [agentId, setAgentId] = useState(defaultAgentId);
  const [target, setTarget] = useState(kind === "strategist" ? "global" : "");
  const [agentMeta, setAgentMeta] = useState<AgentMeta | null | undefined>(undefined);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [perTurnMeta, setPerTurnMeta] = useState<ChatMetadata[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // analyst 면 stock_analyst 선택 시만 ticker 필드 의미 있음. strategist 면 항상.
  const tickerFieldVisible =
    showTickerField &&
    (kind === "strategist" || (kind === "analyst" && agentId === "stock_analyst"));

  useEffect(() => {
    let aborted = false;
    const endpoint =
      kind === "analyst"
        ? `${API_BASE}/api/analysts/${agentId}`
        : `${API_BASE}/api/strategists/${agentId}`;
    setAgentMeta(undefined);
    fetch(endpoint)
      .then((r) => (r.ok ? r.json() : Promise.reject(`${r.status}`)))
      .then((m) => {
        if (aborted) return;
        if (kind === "analyst") {
          setAgentMeta({ kind: "analyst", data: m as AnalystMeta });
        } else {
          setAgentMeta({ kind: "strategist", data: m as StrategistMeta });
        }
      })
      .catch(() => !aborted && setAgentMeta(null));
    return () => {
      aborted = true;
    };
  }, [agentId, kind]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

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
    setMessages([...next, { role: "assistant", content: "" }]);
    setInput("");
    setLoading(true);

    try {
      const body: {
        messages: ChatMessage[];
        provider?: ProviderName;
        target?: string;
        target_ticker?: string;
      } = {
        messages: next,
      };
      if (provider !== "auto") {
        body.provider = provider;
      }
      if (kind === "strategist") {
        body.target = target || "global";
      } else if (kind === "analyst" && agentId === "stock_analyst" && target.trim()) {
        // INFRA-CHART-DATA-001 — stock_analyst chart_data_md [4] 자동 주입.
        // ticker 6자리 숫자 또는 한글 종목명 모두 허용 (server _resolve_ticker 가 매핑).
        body.target_ticker = target.trim();
      }
      const endpoint =
        kind === "analyst"
          ? `${API_BASE}/api/analysts/${agentId}/chat/stream`
          : `${API_BASE}/api/strategists/${agentId}/chat/stream`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`${res.status} ${res.statusText}: ${detail}`);
      }
      if (!res.body) throw new Error("response body is null (streaming unsupported)");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalMeta: ChatMetadata | null = null;
      let streamError: string | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sep: number;
        while ((sep = buffer.indexOf("\n\n")) >= 0) {
          const frame = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
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
            const { type: _t, ...rest } = event;
            void _t;
            finalMeta = rest as unknown as ChatMetadata;
          } else if (event.type === "error") {
            streamError = (event.message as string) || "stream error";
          }
        }
      }

      if (streamError) throw new Error(streamError);
      if (finalMeta) setPerTurnMeta((prev) => [...prev, finalMeta!]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
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

  function onAgentChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setAgentId(e.target.value);
    setMessages([]);
    setPerTurnMeta([]);
    setError(null);
  }

  return (
    <section className="flex flex-col bg-neutral-950/50 border border-neutral-800 rounded-lg p-4 min-h-0">
      <header className="space-y-2 pb-3 border-b border-neutral-800">
        <h2 className="text-lg font-bold tracking-tight">
          {title}
          <span className="ml-2 text-xs font-normal text-neutral-500">{subtitle}</span>
        </h2>
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <label className="text-xs text-neutral-400 shrink-0">
            {kind === "analyst" ? "분석가" : "전략가"}
          </label>
          <select
            value={agentId}
            onChange={onAgentChange}
            disabled={loading}
            className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 font-mono text-xs flex-1 min-w-0"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.label}
              </option>
            ))}
          </select>
        </div>
        {tickerFieldVisible && (
          <div className="flex items-center gap-2 flex-wrap text-sm">
            <label className="text-xs text-neutral-400 shrink-0" title={
              kind === "analyst"
                ? "stock_analyst chart_data_md [4] 주입용. 6자리 ticker (005930) 또는 한글 종목명 (삼성전자) 입력 — server 가 매핑. 비워두면 chart 미주입."
                : "team_outputs 의 target. 6자리 ticker, 한글 종목명, 또는 'global' (시장 전체)."
            }>
              {kind === "analyst" ? "종목" : "target"}
            </label>
            <input
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder={kind === "analyst" ? "예: 005930 또는 삼성전자" : "예: 005930, 삼성전자, global"}
              className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 font-mono text-xs w-56"
            />
            {kind === "analyst" && !target.trim() && (
              <span className="text-[11px] text-amber-400" title="비어있으면 chart_data_md [4] 미주입 → α/F1/F4=null">
                ⚠ 입력 필요 (미입력 시 chart 미주입)
              </span>
            )}
          </div>
        )}
        {agentMeta === undefined ? (
          <div className="text-[11px] text-neutral-500">메타 로딩…</div>
        ) : agentMeta?.kind === "analyst" ? (
          <div className="text-[11px] text-neutral-500 font-mono">
            {agentMeta.data.display_name} · 학습부:{" "}
            {agentMeta.data.learning_dept} · RAG:{" "}
            {agentMeta.data.reads.join(",")}
          </div>
        ) : agentMeta?.kind === "strategist" ? (
          <div className="text-[11px] text-neutral-500 font-mono">
            {agentMeta.data.display_name} · track {agentMeta.data.track} ·
            reads: {agentMeta.data.reads_analysts.join(",")}
          </div>
        ) : (
          <div className="text-[11px] text-red-500">메타 로드 실패</div>
        )}
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-3 space-y-3 min-h-[280px] my-2"
      >
        {messages.length === 0 && (
          <div className="text-xs text-neutral-500 italic">
            {kind === "analyst"
              ? '예: "삼성전자 분석" (stock_analyst + ticker 005930), "지금 자산 비중 어떻게?" (wealth_strategist)'
              : '예: "long: 삼성전자 분석" (track_a + target 005930), "swing: 005930"'}
          </div>
        )}
        {messages.map((m, i) => {
          const meta = m.role === "assistant" ? perTurnMeta[Math.floor(i / 2)] : null;
          return (
            <div key={i}>
              <div
                className={
                  m.role === "user"
                    ? "text-[10px] uppercase tracking-wide text-neutral-500 mb-1"
                    : "text-[10px] uppercase tracking-wide text-emerald-500 mb-1"
                }
              >
                {m.role === "user"
                  ? "you"
                  : agentMeta?.data.display_name || agentId}
              </div>
              <div className="whitespace-pre-wrap text-xs leading-relaxed">
                {m.content}
              </div>
              {meta && <MetadataBar meta={meta} />}
            </div>
          );
        })}
        {loading && (
          <div className="text-xs text-neutral-500 italic">
            {kind === "analyst" ? "분석가가 생각 중…" : "전략가가 종합 중…"}
          </div>
        )}
      </div>

      {error && (
        <div className="text-xs text-red-400 font-mono border border-red-900 rounded p-2 bg-red-950/30 mb-2">
          {error}
        </div>
      )}

      <div className="space-y-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={3}
          placeholder="질문 입력. Ctrl+Enter 전송."
          className="w-full bg-neutral-900 border border-neutral-700 rounded px-3 py-2 text-xs resize-none focus:border-emerald-700 focus:outline-none"
          disabled={loading}
        />
        <div className="flex items-center justify-between text-[11px]">
          <div className="text-neutral-500 font-mono">
            {cumulativeTotal.toLocaleString()}/{CONTEXT_LIMIT.toLocaleString()} tok ·
            ${cumulativeCost.toFixed(4)} · {messages.length / 2} turn
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={clearMessages}
              disabled={messages.length === 0 || loading}
              className="text-[11px] px-2 py-1 border border-neutral-700 rounded hover:bg-neutral-800 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              /clear
            </button>
            <button
              type="button"
              onClick={() => void send()}
              disabled={loading || !input.trim()}
              className="text-[11px] px-3 py-1 bg-emerald-700 hover:bg-emerald-600 rounded disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {loading ? "…" : "전송"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
