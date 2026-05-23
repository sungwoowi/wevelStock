"use client";

/**
 * PRODUCTION-UX-001 — 근거 토글.
 *
 * default = 닫힘 (formatted 자연어 응답만 표시).
 * 클릭 시 raw 분석가/전략가 응답 풀세트 노출 — R&D 수준 투명성. LLM 추가 호출 X.
 */

import { useState } from "react";

type AgentResponse = {
  kind: string;
  agent_id: string;
  text: string;
  error?: string | null;
  metadata?: Record<string, any>;
};

export function EvidenceToggle({ responses }: { responses: AgentResponse[] }) {
  const [open, setOpen] = useState(false);
  if (!responses || responses.length === 0) return null;

  const kindLabel = (k: string) =>
    k === "analyst_prefetch"
      ? "분석가 (prefetch)"
      : k === "analyst"
      ? "분석가"
      : k === "strategist"
      ? "전략가"
      : k === "refuse_or_guide"
      ? "안내"
      : k === "pending_ms5"
      ? "(MS5 대기)"
      : k;

  return (
    <div className="border border-neutral-800 rounded-md bg-neutral-950/50">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-neutral-400 hover:bg-neutral-900"
      >
        <span>
          {open ? "▼" : "▶"} 근거 보기 ({responses.length} 항목 — 분석가 + 전략가 raw 응답)
        </span>
        <span className="text-[11px] text-neutral-500">
          코드 라벨 + 명제 ID + 격자 풀세트
        </span>
      </button>
      {open && (
        <div className="border-t border-neutral-800 p-3 space-y-3 text-sm">
          {responses.map((r, i) => {
            const isMock = Boolean(r.metadata?.is_mock);
            const upstreamError = r.metadata?.upstream_error;
            const isDegraded = Boolean(r.error || isMock || upstreamError);
            return (
              <div
                key={i}
                className={
                  "border rounded p-2 " +
                  (isDegraded
                    ? "border-red-900 bg-red-950/30"
                    : "border-neutral-800 bg-neutral-950")
                }
              >
                <div className="flex items-baseline justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] uppercase tracking-wider text-neutral-500">
                      {kindLabel(r.kind)}
                    </span>
                    <span className="font-mono text-xs text-emerald-300">
                      {r.agent_id}
                    </span>
                    {isMock && (
                      <span className="text-[10px] font-bold text-red-300 bg-red-900/40 px-1.5 py-0.5 rounded">
                        ⚠ MOCK 응답
                      </span>
                    )}
                  </div>
                  {r.metadata?.model && (
                    <span className="text-[11px] text-neutral-500 font-mono">
                      {String(r.metadata.model)}
                    </span>
                  )}
                </div>
                {r.error && (
                  <div className="text-xs text-red-400 mb-1">호출 실패: {r.error}</div>
                )}
                {!r.error && upstreamError && (
                  <div className="text-xs text-red-400 mb-1">
                    LLM 응답 누락: {String(upstreamError)}
                  </div>
                )}
                <pre className="whitespace-pre-wrap break-words text-xs text-neutral-300 font-mono">
                  {r.text || (isDegraded ? "" : "(빈 응답)")}
                </pre>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
