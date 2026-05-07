"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { API_BASE, fetcher } from "@/lib/api";

type Part = {
  key: string;
  label: string;
  order: number;
  data: Record<string, unknown>;
};

type Run = {
  run_id: string;
  generated_at: string; // "YYYY-MM-DD HH:MM:SS" UTC from SQLite
  parts: Part[];
  rendered: string[]; // 텔레그램 봇이 보내는 사람용 텍스트 메시지 (파트별)
};

type RecentResponse = {
  pipeline_id: string;
  count: number;
  runs: Run[];
};

const PIPELINES: { id: string; label: string }[] = [
  { id: "market_briefing_pre", label: "장전 (평일 07:00 자동)" },
  { id: "market_briefing_now", label: "장중 (자동 + 봇)" },
];

const LIMIT = 20;

function formatRunLabel(generatedAt: string): { date: string; time: string } {
  // SQLite "2026-05-06 22:00:08" UTC → 로컬 시각 표시
  const iso = generatedAt.replace(" ", "T") + "Z";
  const d = new Date(iso);
  if (isNaN(d.getTime())) {
    return { date: generatedAt.slice(0, 10), time: generatedAt.slice(11, 16) };
  }
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return { date: `${yyyy}-${mm}-${dd}`, time: `${hh}:${mi}` };
}

function runTrigger(runId: string): "auto" | "manual" {
  return runId.includes("#sched-") ? "auto" : "manual";
}

export function BriefingPartsCard() {
  const [pipelineId, setPipelineId] = useState(PIPELINES[0].id);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);

  const { data, error, isLoading } = useSWR<RecentResponse>(
    `/api/briefings/${pipelineId}/recent?limit=${LIMIT}`,
    fetcher,
    { refreshInterval: 5000, shouldRetryOnError: false },
  );

  // 파이프라인 전환 또는 데이터 갱신 시 가장 최근 run 으로 기본 선택
  useEffect(() => {
    if (!data?.runs?.length) {
      setSelectedRunId(null);
      return;
    }
    if (
      !selectedRunId ||
      !data.runs.find((r) => r.run_id === selectedRunId)
    ) {
      setSelectedRunId(data.runs[0].run_id);
    }
  }, [data, selectedRunId]);

  const selectedRun = useMemo(
    () => data?.runs.find((r) => r.run_id === selectedRunId) ?? null,
    [data, selectedRunId],
  );

  const groupedRuns = useMemo(() => {
    const groups = new Map<string, Run[]>();
    for (const r of data?.runs ?? []) {
      const { date } = formatRunLabel(r.generated_at);
      if (!groups.has(date)) groups.set(date, []);
      groups.get(date)!.push(r);
    }
    return Array.from(groups.entries());
  }, [data]);

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold">브리핑 이력</h2>
          <p className="text-xs text-neutral-500">
            BRIEFING-ON-DEMAND-001 · 자동 스케줄 + 봇/API 온디맨드 누적 (run_id 단위 시계열)
          </p>
        </div>
        <div className="flex gap-1">
          {PIPELINES.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => {
                setPipelineId(p.id);
                setSelectedRunId(null);
              }}
              className={
                pipelineId === p.id
                  ? "text-xs px-2.5 py-1 bg-emerald-700 rounded"
                  : "text-xs px-2.5 py-1 border border-neutral-700 rounded hover:bg-neutral-800"
              }
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm text-neutral-500">로딩…</p>}
      {error && !isLoading && (
        <p className="text-sm text-amber-400">
          ⚠ 아직 실행된 적 없음 — 텔레그램 `/briefing_now` 또는 스케줄 대기
        </p>
      )}

      {data && data.runs.length > 0 && (
        <div className="grid md:grid-cols-[220px_1fr] gap-4">
          {/* 좌측: 날짜 그룹별 run 리스트 */}
          <aside className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
            {groupedRuns.map(([date, runs]) => (
              <div key={date}>
                <div className="text-[10px] font-mono text-neutral-600 uppercase tracking-wider mb-1">
                  {date} · {runs.length} run
                </div>
                <ul className="space-y-1">
                  {runs.map((r) => {
                    const { time } = formatRunLabel(r.generated_at);
                    const trig = runTrigger(r.run_id);
                    const active = r.run_id === selectedRunId;
                    return (
                      <li key={r.run_id}>
                        <button
                          type="button"
                          onClick={() => setSelectedRunId(r.run_id)}
                          className={
                            active
                              ? "w-full text-left px-2 py-1.5 rounded bg-emerald-900/40 border border-emerald-800 text-xs"
                              : "w-full text-left px-2 py-1.5 rounded border border-transparent hover:bg-neutral-800/60 text-xs text-neutral-400"
                          }
                        >
                          <div className="flex items-center gap-2">
                            <span className="font-mono">{time}</span>
                            <span
                              className={
                                trig === "auto"
                                  ? "text-[9px] px-1 py-px bg-sky-900/50 text-sky-300 rounded"
                                  : "text-[9px] px-1 py-px bg-amber-900/50 text-amber-300 rounded"
                              }
                            >
                              {trig === "auto" ? "AUTO" : "BOT"}
                            </span>
                          </div>
                          <div className="text-[10px] text-neutral-600 font-mono truncate mt-0.5">
                            {r.parts.length} parts
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </aside>

          {/* 우측: 선택된 run 의 텔레그램 텍스트 */}
          <section className="min-w-0">
            {selectedRun && (
              <>
                <div className="text-xs text-neutral-500 font-mono mb-2 break-all">
                  run_id: {selectedRun.run_id}
                </div>
                {selectedRun.rendered.length === 0 ? (
                  <p className="text-sm text-amber-400">
                    ⚠ 이 파이프라인 ({pipelineId}) 의 텔레그램 렌더러가 없습니다.
                    하단 JSON 으로 확인하세요.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {selectedRun.rendered.map((msg, i) => (
                      <div
                        key={i}
                        className="rounded-md border border-neutral-800 bg-neutral-950/60 p-3"
                      >
                        <div className="text-[10px] font-mono text-neutral-600 uppercase tracking-wider mb-2">
                          파트 {i + 1}/{selectedRun.rendered.length}
                          {selectedRun.parts[i] && (
                            <span className="ml-2 text-neutral-500">
                              · {selectedRun.parts[i].label}
                            </span>
                          )}
                        </div>
                        <pre className="text-sm leading-relaxed text-neutral-200 whitespace-pre-wrap font-sans">
                          {msg}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}

                <div className="mt-4 flex items-center justify-between text-[11px] text-neutral-600 font-mono">
                  <button
                    type="button"
                    onClick={() => setShowJson((v) => !v)}
                    className="underline hover:text-neutral-400"
                  >
                    {showJson ? "▼ raw JSON 숨기기" : "▶ raw JSON 보기 (디버그)"}
                  </button>
                  <a
                    href={`${API_BASE}/api/briefings/${pipelineId}/recent?limit=${LIMIT}`}
                    target="_blank"
                    rel="noreferrer"
                    className="underline hover:text-neutral-400"
                  >
                    endpoint
                  </a>
                </div>
                {showJson && (
                  <pre className="mt-2 text-[11px] font-mono text-neutral-500 bg-neutral-950/60 p-3 max-h-96 overflow-auto whitespace-pre-wrap break-all border border-neutral-800 rounded">
                    {JSON.stringify(selectedRun.parts, null, 2)}
                  </pre>
                )}
              </>
            )}
          </section>
        </div>
      )}

      {data && data.runs.length === 0 && !isLoading && (
        <p className="text-sm text-neutral-500">기록된 브리핑 없음</p>
      )}
    </div>
  );
}
