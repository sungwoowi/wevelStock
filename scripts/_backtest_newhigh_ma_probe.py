"""백테스트 — 사용자 실제 진입 시그니처(신고가·이평선·thrust·상대강도)가 현실적 보유기간에서 edge?

사용자 스타일(2026-06-20 정정):
  - Track B(단기 스윙·수주~1달): 신고가 추세 주도주 / 추세상단 박스저점 → 일봉·360분봉
  - Track A(중장기 추세·3~6달): 신고가 추세 주도주 → 주봉·월봉. (12개월+는 미장 지수/빅테크 별개)
  - 파동 해석의 관찰가능 입력 = 신고가 + 이평선 구조. LLM α는 백테스트 불가 → 이 가격 시그니처로 대체.

신호(모두 가격에서·cutoff-clean):
  nh_prox  : 종가 / 252일 최고가  (1.0=52주 신고가 = 신고가 주도주 근접도)
  ma_stack : 정배열 점수 0~3  (종가>MA20 + MA20>MA60 + MA60>MA120)  = 이평선 구조
  thrust_15: 최근 15일 수익률  (주봉 대양봉 클러스터 = 단기 대파동 thrust)
  mom_120  : 최근 120일 수익률  (상대강도 = 이미 검증된 주도주 신호, 비교 기준)

보유기간: 2주(10d)·1달(20d) = Track B / 3달(60d)·6달(120d) = Track A.
장세분리: 하락·횡보(2022~2024) vs 상승. 지표 = Q5−전체평균(상위 선택 우위) + IC.
usage: PYTHONIOENCODING=utf-8 uv run python scripts/_backtest_newhigh_ma_probe.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB = Path("data/db/stock-advisor.sqlite")
MIN_BARS = 500
REBAL = 20
HORIZONS = {"2주": 10, "1달": 20, "3달": 60, "6달": 120}
TRACK = {"2주": "B", "1달": "B", "3달": "A", "6달": "A"}
SIGNALS = ("nh_prox", "ma_stack", "thrust_15", "mom_120")
BEAR_FROM, BEAR_TO = "2022-01-01", "2024-12-31"


def load_panel() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT ticker, date, close FROM chart_ohlcv WHERE close IS NOT NULL ORDER BY ticker, date", con)
    con.close()
    counts = df.groupby("ticker")["date"].transform("size")
    df = df[counts >= MIN_BARS]
    rows: list[pd.DataFrame] = []
    for tk, g in df.groupby("ticker"):
        g = g.reset_index(drop=True)
        c = g["close"].astype(float)
        ma20, ma60, ma120 = c.rolling(20).mean(), c.rolling(60).mean(), c.rolling(120).mean()
        out = {
            "date": g["date"], "ticker": tk,
            "nh_prox": c / c.rolling(252).max(),
            "ma_stack": (c > ma20).astype(int) + (ma20 > ma60).astype(int) + (ma60 > ma120).astype(int),
            "thrust_15": c / c.shift(15) - 1.0,
            "mom_120": c / c.shift(120) - 1.0,
        }
        for name, h in HORIZONS.items():
            out[f"fwd_{name}"] = c.shift(-h) / c - 1.0
        rows.append(pd.DataFrame(out))
    return pd.concat(rows, ignore_index=True)


def edge(sub: pd.DataFrame, signal: str, fwd: str) -> dict:
    s = sub.dropna(subset=[signal, fwd])
    cal = sorted(s["date"].unique())
    s = s[s["date"].isin(set(cal[::REBAL]))]
    ics, e = [], []
    for _, g in s.groupby("date"):
        if len(g) < 10:
            continue
        ic = g[signal].corr(g[fwd], method="spearman")
        if pd.notna(ic):
            ics.append(ic)
        try:
            q = pd.qcut(g[signal].rank(method="first"), 5, labels=False)
        except ValueError:
            continue
        gg = g.assign(_q=q)
        e.append(gg.loc[gg["_q"] == 4, fwd].mean() - g[fwd].mean())
    return {"ic": pd.Series(ics).mean(), "edge": pd.Series(e).mean()}


def main() -> None:
    panel = load_panel()
    bull = panel[(panel["date"] < BEAR_FROM) | (panel["date"] > BEAR_TO)]
    bear = panel[(panel["date"] >= BEAR_FROM) & (panel["date"] <= BEAR_TO)]
    print(f"[데이터] {panel['ticker'].nunique()}종목 · {panel['date'].min()}~{panel['date'].max()}")
    print("  edge = Q5(상위20%)−전체평균. 하락장=2022~2024. ⭐=해당 트랙 권장 보유기간\n")
    for sig in SIGNALS:
        print(f"══ 신호: {sig} ══")
        print(f"{'보유':<6}{'트랙':<5}{'│ 하락장 edge':>14}{'IC':>9}{'│ 상승장 edge':>14}{'IC':>9}")
        for name, _h in HORIZONS.items():
            fwd = f"fwd_{name}"
            b, c = edge(bear, sig, fwd), edge(bull, sig, fwd)
            print(f"{name:<6}{TRACK[name]:<5}{b['edge']:>+14.2%}{b['ic']:>+9.3f}"
                  f"{c['edge']:>+14.2%}{c['ic']:>+9.3f}")
        print()
    print("판독: Track B는 2주/1달, Track A는 3달/6달 칸을 본다. 하락장에서도 edge>0 이어야 지속가능.")
    print("주의: 거래비용·생존편향 미반영. 박스저점 순환매(Track B ②)는 평균회귀라 별도 프로브 필요.")


if __name__ == "__main__":
    main()
