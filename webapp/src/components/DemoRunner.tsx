"use client";
import { useState } from "react";
import { API_BASE } from "@/lib/api";

const SCENARIOS = [
  { id: "normal", label: "정상 (준수)" },
  { id: "over-allocation", label: "비중 초과" },
  { id: "no-stop-loss", label: "손절 없음" },
  { id: "emotional", label: "감정 매매" },
];

export function DemoRunner() {
  const [running, setRunning] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function runScenario(scenario: string) {
    setRunning(true);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/demo/run?scenario=${scenario}`, {
        method: "POST",
      });
      const json = await res.json();
      setMsg(`✓ ${scenario} → ${json.verdict} (신뢰도 ${json.confidence})`);
    } catch (e) {
      setMsg(`✗ 실패: ${String(e)}`);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      <h2 className="text-lg font-semibold mb-3">데모 시나리오</h2>
      <p className="text-sm text-neutral-400 mb-4">
        포트폴리오 시나리오를 선택해 오케스트레이터를 실행합니다. 결과는 5초 내 위
        카드에 반영됩니다.
      </p>
      <div className="flex flex-wrap gap-2">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => runScenario(s.id)}
            disabled={running}
            className="rounded-md border border-neutral-700 bg-neutral-800/50 px-3 py-1.5 text-sm
              hover:border-neutral-500 hover:bg-neutral-800
              disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {s.label}
          </button>
        ))}
      </div>
      {msg && (
        <p className="mt-3 text-sm text-neutral-300 font-mono">{msg}</p>
      )}
    </div>
  );
}
