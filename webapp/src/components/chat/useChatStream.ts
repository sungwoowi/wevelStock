"use client";

import { API_BASE } from "@/lib/api";
import { useCallback, useEffect, useRef, useState } from "react";

export type Evidence = { agent: string; kind: string; text: string };
export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  status?: "thinking" | "streaming" | "done" | "error";
  preview?: string;
  evidence?: Evidence[];
};

/** production 채팅 SSE 소비 훅 — `/api/chat/production/stream`.
 * 디버그(classification·token·cost) 미노출 — 최종 종합 답변(formatted) + 근거(raw)만 표면화.
 */
export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const msgRef = useRef<ChatMessage[]>([]);
  useEffect(() => {
    msgRef.current = messages;
  }, [messages]);

  const send = useCallback(async (question: string) => {
    const q = question.trim();
    if (busyRef.current || !q) return;
    busyRef.current = true;
    setBusy(true);

    // 멀티턴 — 직전 확정 대화 + 새 질문
    const history = msgRef.current
      .filter((m) => m.role === "user" || (m.role === "assistant" && m.status === "done"))
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [
      ...prev,
      { role: "user", content: q },
      { role: "assistant", content: "", status: "thinking", preview: "", evidence: [] },
    ]);

    const patch = (p: Partial<ChatMessage>) =>
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant") next[next.length - 1] = { ...last, ...p };
        return next;
      });

    try {
      const res = await fetch(`${API_BASE}/api/chat/production/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: [...history, { role: "user", content: q }] }),
      });
      if (!res.ok || !res.body) throw new Error(`${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      const agentText: Record<string, string> = {};
      const evidence: Evidence[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const mm = part.match(/^data:\s*(.+)$/m);
          if (!mm) continue;
          let ev: Record<string, unknown>;
          try {
            ev = JSON.parse(mm[1]);
          } catch {
            continue;
          }
          const type = ev.type as string;
          if (type === "analyst_prefetch" && ev.text && !ev.error) {
            evidence.push({ agent: String(ev.agent), kind: "analyst", text: String(ev.text) });
            patch({ evidence: [...evidence] });
          } else if (type === "text_delta" && ev.agent && ev.text) {
            const a = String(ev.agent);
            agentText[a] = (agentText[a] || "") + String(ev.text);
            patch({ status: "streaming", preview: agentText[a] });
          } else if (type === "agent_done" && ev.agent && agentText[String(ev.agent)]) {
            evidence.push({ agent: String(ev.agent), kind: "strategist", text: agentText[String(ev.agent)] });
            patch({ evidence: [...evidence] });
          } else if (type === "formatted") {
            patch({ content: String(ev.text || "(응답 없음)"), status: "done", preview: "" });
          } else if (type === "formatted_error" || (type === "error" && ev.fatal)) {
            patch({
              content: String(ev.message || "응답 생성에 실패했어요. 잠시 후 다시 시도해 주세요."),
              status: "error",
              preview: "",
            });
          }
        }
      }
      // 스트림 종료 — formatted 미수신 시 preview 폴백
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant" && !last.content) {
          next[next.length - 1] = {
            ...last,
            content: last.preview || "응답을 받지 못했어요. 다시 시도해 주세요.",
            status: "done",
            preview: "",
          };
        }
        return next;
      });
    } catch {
      patch({ content: "서버 연결에 실패했어요. 백엔드가 실행 중인지 확인해 주세요.", status: "error" });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  return { messages, busy, send };
}
