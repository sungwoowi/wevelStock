"use client";

/**
 * PRODUCTION-UX-001 — manual fallback drop-down.
 *
 * 분류 신뢰도 < 0.6 또는 ticker 매핑 실패 시 사용자가 직접 시나리오 + 종목 선택.
 * resolve_ticker 한계 (30 종목) 까지 보완 — INFRA-TICKER-RESOLVER-001 SLOT.
 */

import { useState } from "react";

export type ManualOverride = {
  scenario_id: number;
  ticker: string | null;
  ticker_display: string | null;
  agent_route: string;
  analyst_ids: string[];
};

const SCENARIOS: { id: number; label: string; route: string; analyst_ids?: string[] }[] = [
  { id: 1, label: "1 · 보유 종목 결정", route: "track_a" },
  { id: 2, label: "2 · 신규 진입", route: "both" },
  { id: 3, label: "3 · 시장 판단", route: "analyst_direct", analyst_ids: ["market_state_analyzer"] },
  { id: 4, label: "4 · 섹터 선택", route: "analyst_direct", analyst_ids: ["stock_picker", "market_state_analyzer"] },
  { id: 5, label: "5 · 주도주 진입", route: "both" },
  { id: 6, label: "6 · 매도 시그널", route: "track_a" },
  { id: 7, label: "7 · 손절 발동", route: "track_a", analyst_ids: ["principle_guardian"] },
  { id: 8, label: "8 · 추매 시그널", route: "track_a" },
  { id: 9, label: "9 · 시장 위기", route: "analyst_direct", analyst_ids: ["market_state_analyzer", "principle_guardian"] },
  { id: 10, label: "10 · 계좌 안심", route: "track_a" },
];

const TICKERS: { code: string; name: string }[] = [
  // KOSPI 시총 상위
  { code: "005930", name: "삼성전자" },
  { code: "000660", name: "SK하이닉스" },
  { code: "207940", name: "삼성바이오로직스" },
  { code: "373220", name: "LG에너지솔루션" },
  { code: "005380", name: "현대차" },
  { code: "000270", name: "기아" },
  { code: "035420", name: "NAVER" },
  { code: "068270", name: "셀트리온" },
  { code: "005490", name: "POSCO홀딩스" },
  { code: "012450", name: "한화에어로스페이스" },
  { code: "028260", name: "삼성물산" },
  { code: "105560", name: "KB금융" },
  { code: "329180", name: "HD현대중공업" },
  { code: "042660", name: "한화오션" },
  { code: "035720", name: "카카오" },
  { code: "055550", name: "신한지주" },
  { code: "003550", name: "LG" },
  { code: "015760", name: "한국전력" },
  { code: "032830", name: "삼성생명" },
  { code: "086790", name: "하나금융지주" },
  { code: "006400", name: "삼성SDI" },
  { code: "051910", name: "LG화학" },
  { code: "012330", name: "현대모비스" },
  // KOSDAQ
  { code: "247540", name: "에코프로비엠" },
  { code: "086520", name: "에코프로" },
  { code: "196170", name: "알테오젠" },
  { code: "091990", name: "셀트리온헬스케어" },
  { code: "028300", name: "HLB" },
  { code: "058470", name: "리노공업" },
  { code: "042700", name: "한미반도체" },
  { code: "277810", name: "레인보우로보틱스" },
  { code: "035900", name: "JYP엔터" },
];

export function IntentFallback({
  onApply,
  defaultScenario,
  defaultTicker,
}: {
  onApply: (override: ManualOverride) => void;
  defaultScenario?: number;
  defaultTicker?: string | null;
}) {
  const [scenario, setScenario] = useState<number>(defaultScenario || 2);
  const [ticker, setTicker] = useState<string>(defaultTicker || "");

  function handleApply() {
    const scn = SCENARIOS.find((s) => s.id === scenario);
    if (!scn) return;
    const tk = TICKERS.find((t) => t.code === ticker);
    onApply({
      scenario_id: scn.id,
      ticker: tk?.code || null,
      ticker_display: tk?.name || null,
      agent_route: scn.route,
      analyst_ids: scn.analyst_ids || [],
    });
  }

  return (
    <div className="border border-amber-700 bg-amber-950/30 rounded-md p-3 space-y-2 text-xs">
      <div className="font-medium text-amber-300">
        ⚠ 분류 신뢰도 부족 — 직접 시나리오/종목 선택
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <label className="text-neutral-400">시나리오</label>
        <select
          value={scenario}
          onChange={(e) => setScenario(Number(e.target.value))}
          className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs"
        >
          {SCENARIOS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label} → {s.route}
            </option>
          ))}
        </select>
        <label className="text-neutral-400 ml-2">종목</label>
        <select
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs"
        >
          <option value="">(없음 / global)</option>
          {TICKERS.map((t) => (
            <option key={t.code} value={t.code}>
              {t.name} ({t.code})
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleApply}
          className="px-2 py-1 bg-amber-700 hover:bg-amber-600 rounded text-xs"
        >
          이 조합으로 재전송
        </button>
      </div>
      <div className="text-[11px] text-neutral-500">
        원본 발화 그대로 다시 전송하되, 위 조합이 분류 결과로 사용됩니다.
      </div>
    </div>
  );
}
