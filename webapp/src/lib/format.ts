// 포맷 헬퍼 — 시황(MarketBoard)·데스크 공용. 백엔드 render 로직 mirror.

export function fmtNum(v: unknown, decimals = 0): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export function fmtPct(v: unknown): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

/** 백만원 → 억/조 (부호 포함). */
export function wonM(million: unknown): string {
  if (typeof million !== "number" || Number.isNaN(million)) return "—";
  const eok = million / 100;
  const sign = eok >= 0 ? "+" : "";
  if (Math.abs(eok) >= 10000) return `${sign}${(eok / 10000).toFixed(2)}조`;
  return `${sign}${eok.toLocaleString("en-US", { maximumFractionDigits: 0 })}억`;
}

/** 십억원 → 억/조 (×10, 부호 포함). */
export function wonB(billion: unknown): string {
  if (typeof billion !== "number" || Number.isNaN(billion)) return "—";
  const eok = billion * 10;
  const sign = eok >= 0 ? "+" : "";
  if (Math.abs(eok) >= 10000) return `${sign}${(eok / 10000).toFixed(2)}조`;
  return `${sign}${eok.toLocaleString("en-US", { maximumFractionDigits: 0 })}억`;
}

/** 거래대금(백만원) → 조/억 (부호 없음, 거래대금 상위 행용). */
export function tradeAmt(million: unknown): string {
  if (typeof million !== "number" || Number.isNaN(million)) return "";
  const eok = million / 100;
  if (eok >= 10000) return `${(eok / 10000).toFixed(1)}조`;
  return `${Math.round(eok).toLocaleString("en-US")}억`;
}

/** 거래대금(백만원) → 조 (소수 2자리, 국내 지수용). */
export function joM(million: unknown): string {
  if (typeof million !== "number" || Number.isNaN(million)) return "—";
  return `${(million / 1_000_000).toFixed(2)}조`;
}

/** 한국식 등락 색: 상승=빨강 / 하락=파랑 / 보합=회색 (시황 지수용). */
export function changeClass(v: unknown): string {
  if (typeof v !== "number" || Number.isNaN(v) || v === 0) return "text-flat";
  return v > 0 ? "text-up" : "text-down";
}

// ── 데스크(손익) — 의미색: 수익/이익=초록 / 손실=빨강 (시황 한국식과 다름) ──────────

/** 손익 의미색: 이익=초록(profit) / 손실=빨강(loss) / 0=보합. */
export function pnlClass(v: unknown): string {
  if (typeof v !== "number" || Number.isNaN(v) || v === 0) return "text-flat";
  return v > 0 ? "text-profit" : "text-loss";
}

/** 원화 raw(원) → 한국식 만/억/조 (부호 없음). 예) 402_400_000 → "4억 240만". */
export function wonKR(won: unknown): string {
  if (typeof won !== "number" || Number.isNaN(won)) return "—";
  const neg = won < 0;
  const abs = Math.abs(won);
  let out: string;
  if (abs >= 1e12) {
    out = `${(abs / 1e12).toFixed(2)}조`;
  } else if (abs >= 1e8) {
    const eok = Math.floor(abs / 1e8);
    const man = Math.round((abs - eok * 1e8) / 1e4);
    out = man ? `${eok}억 ${man.toLocaleString("en-US")}만` : `${eok}억`;
  } else if (abs >= 1e4) {
    out = `${Math.round(abs / 1e4).toLocaleString("en-US")}만`;
  } else {
    out = `${Math.round(abs).toLocaleString("en-US")}원`;
  }
  return neg ? `-${out}` : out;
}

/** 거래대금(원) → 억 단위 반올림 (억 이하 절삭·반올림). 예) 7_940_145_390_000 → "7조 9,401억". */
export function eokKR(won: unknown): string {
  if (typeof won !== "number" || Number.isNaN(won)) return "—";
  const eok = Math.round(won / 1e8);
  if (eok >= 10000) {
    const jo = Math.floor(eok / 10000);
    const rem = eok % 10000;
    return rem ? `${jo}조 ${rem.toLocaleString("en-US")}억` : `${jo}조`;
  }
  return `${eok.toLocaleString("en-US")}억`;
}

/** 거래량(주) → 만주/억주. 예) 12_340_000 → "1,234만주". */
export function volKR(v: unknown): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  if (v >= 1e8) return `${(v / 1e8).toFixed(1)}억주`;
  if (v >= 1e4) return `${Math.round(v / 1e4).toLocaleString("en-US")}만주`;
  return `${Math.round(v).toLocaleString("en-US")}주`;
}

/** 원화 raw(원) → 만/억 (부호 포함, 손익액용). 예) +35만. */
export function wonKRSigned(won: unknown): string {
  if (typeof won !== "number" || Number.isNaN(won)) return "—";
  return (won >= 0 ? "+" : "") + wonKR(won);
}

/** 주가(원) → 만 단위 (소수 1자리 기본). 예) 306_000 → "30.6만". */
export function manWon(won: unknown, decimals = 1): string {
  if (typeof won !== "number" || Number.isNaN(won)) return "—";
  if (Math.abs(won) < 1e4) return `${Math.round(won).toLocaleString("en-US")}원`;
  return `${(won / 1e4).toFixed(decimals)}만`;
}
