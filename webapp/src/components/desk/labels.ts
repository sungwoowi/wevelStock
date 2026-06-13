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
