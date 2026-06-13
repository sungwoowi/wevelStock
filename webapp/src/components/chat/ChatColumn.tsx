"use client";

import { cn } from "@/lib/utils";
import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "./useChatStream";
import { useChatStream } from "./useChatStream";

const AGENT_KR: Record<string, string> = {
  track_a: "중장기 전략가",
  track_b: "단기 전략가",
  stock_picker: "종목선정가",
  trader: "트레이더",
  stock_analyst: "종목분석가",
  market_state_analyzer: "시장상태분석가",
  flow_analyzer: "수급분석가",
  principle_guardian: "원칙수호자",
  wealth_strategist: "자산전략가",
  news_curator: "뉴스큐레이터",
};
const agentKR = (a: string) => AGENT_KR[a] || a;

function EvidenceCollapse({ msg }: { msg: ChatMessage }) {
  const [open, setOpen] = useState(false);
  const ev = msg.evidence ?? [];
  if (ev.length === 0) return null;
  return (
    <div className="mt-2">
      <button type="button" onClick={() => setOpen((o) => !o)} className="text-xs font-semibold text-info">
        근거 {open ? "접기 ▴" : "보기 ▾"} ({ev.length})
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-2 border-t border-border pt-2">
          {ev.map((e, i) => (
            <div key={i} className="rounded-xl bg-surface p-3">
              <span className="text-[11px] font-bold text-faint">{agentKR(e.agent)}</span>
              <p className="mt-1 whitespace-pre-wrap text-[12px] leading-relaxed text-body">{e.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Bubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "user") {
    return (
      <div className="max-w-[80%] self-end rounded-2xl bg-profit/15 px-4 py-3 text-sm leading-relaxed text-foreground">
        {msg.content}
      </div>
    );
  }
  const thinking = (msg.status === "thinking" || msg.status === "streaming") && !msg.content;
  return (
    <div className="max-w-full self-start rounded-2xl border border-border bg-card px-5 py-4">
      {thinking ? (
        <div className="flex flex-col gap-1.5">
          <span className="animate-pulse text-sm font-semibold text-faint">분석 중…</span>
          {msg.preview && (
            <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-faint">{msg.preview}</p>
          )}
        </div>
      ) : (
        <>
          <p
            className={cn(
              "whitespace-pre-wrap text-[15px] leading-relaxed",
              msg.status === "error" ? "text-loss" : "text-body",
            )}
          >
            {msg.content}
          </p>
          <EvidenceCollapse msg={msg} />
        </>
      )}
    </div>
  );
}

export function ChatColumn({ header }: { header?: React.ReactNode }) {
  const { messages, busy, send } = useChatStream();
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (busy || !input.trim()) return;
    send(input);
    setInput("");
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-9rem)] w-full max-w-[760px] flex-col gap-4">
      {header}
      <div className="flex flex-1 flex-col gap-3">
        {messages.length === 0 && (
          <p className="text-sm leading-relaxed text-faint">
            무엇이든 물어보세요 — 종목·시장·내 계좌까지 시스템이 종합해 답합니다.
          </p>
        )}
        {messages.map((m, i) => (
          <Bubble key={i} msg={m} />
        ))}
        <div ref={endRef} />
      </div>
      <form
        onSubmit={submit}
        className="sticky bottom-4 flex items-center gap-2 rounded-2xl border border-border bg-card p-2 pl-4 shadow-sm"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="예: 삼성전자 지금 사도 돼? / 단타 추천해줘 / 내 계좌 괜찮아?"
          className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-faint"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="shrink-0 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition disabled:opacity-50"
        >
          {busy ? "분석 중" : "보내기"}
        </button>
      </form>
    </div>
  );
}
