// 데스크 도메인 → 한국어 표시 라벨 (코드 라벨 노출 금지, production 친화).

/** 권고 verdict → 한국어. */
export function verdictKR(v: string): string {
  switch (v) {
    case "buy":
      return "매수";
    case "hold":
      return "보유";
    case "wait":
      return "관망";
    case "sell":
      return "매도";
    case "trim":
      return "부분익절";
    default:
      return v || "—";
  }
}

/** 진입 단계(funnel_stage) → 한국어. TRADE-PLAN-LIFECYCLE 2단계. */
export function stageKR(stage: string): string {
  switch (stage) {
    case "entering":
      return "진입";
    case "watching":
      return "매수대기";
    case "interest":
      return "관심";
    default:
      return "관심";
  }
}

/** 단계 배지 색 — 진입=초록 / 매수대기=주황 / 관심=회색. */
export function stageTone(stage: string): "profit" | "amber" | "neutral" {
  if (stage === "entering") return "profit";
  if (stage === "watching") return "amber";
  return "neutral";
}

/** 단계 표시 순서 (진입 ▸ 매수대기 ▸ 관심). */
export const STAGE_ORDER = ["entering", "watching", "interest"] as const;

/** 거래대금 상위 경과일 → "거래대금 상위 N일 전" (null=기록 없음). */
export function universeKR(daysAgo: number | null | undefined): string | null {
  if (daysAgo === null || daysAgo === undefined) return null;
  if (daysAgo <= 0) return "오늘 거래대금 상위";
  if (daysAgo === 1) return "어제 거래대금 상위";
  return `${daysAgo}일 전 거래대금 상위`;
}

/** 체결 reason → 한국어 (매매 일지). */
export function fillReasonKR(side: string, reason: string, leg: number): string {
  if (side === "sell") {
    if (reason === "stop") return "손절";
    if (reason.startsWith("target")) return "익절";
    return "매도";
  }
  if (reason === "entry" || leg === 1) return "1차 매수";
  return `${leg}차 매수`;
}
