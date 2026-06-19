"""백테스트 1차 — 지평선(1/3/6/12개월) × 장세(하락·횡보 vs 상승) 스윕. (R&D·SPEC 전)

질문 2가지:
  ① 지평선을 늘리면(모멘텀·추세는 학술적으로 3~12개월 현상) edge 가 살아나나?
  ② 그 edge 가 **2022~2024 하락·횡보장에서도** 유지되나? (상승장만 타는 오탐 배제)

핵심 지표 = Q5−전체평균(롱 edge): 같은 날짜 상위 종목 − 그날 전체 평균 → *상대값*이라
"다 같이 올랐다"는 상승장 착시는 자동 제거. 장세 분리로 비수기 강건성까지 확인.

데이터: chart_ohlcv (167종목 500봉+) 만. 순수 가격 → 오염 0. 거래비용·생존편향 미반영.
usage: PYTHONIOENCODING=utf-8 uv run python scripts/_backtest_horizon_regime_probe.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB = Path("data/db/stock-advisor.sqlite")
MIN_BARS = 500
LOOKBACK = 60
MA_WIN = 120
REBAL = 20
HORIZONS = {"1M": 20, "3M": 60, "6M": 120, "12M": 250}
BEAR_FROM, BEAR_TO = "2022-01-01", "2024-12-31"   # 하락·횡보장


def load_panel() -> pd.DataFrame:
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT ticker, date, close FROM chart_ohlcv WHERE close IS NOT NULL ORDER BY ticker, date",
        con,
    )
    con.close()
    counts = df.groupby("ticker")["date"].transform("size")
    df = df[counts >= MIN_BARS]
    rows: list[pd.DataFrame] = []
    for tk, g in df.groupby("ticker"):
        g = g.reset_index(drop=True)
        close = g["close"].astype(float)
        out = {"date": g["date"], "ticker": tk,
               "mom_60": close / close.shift(LOOKBACK) - 1.0,
               "trend": close / close.rolling(MA_WIN).mean() - 1.0}
        for name, h in HORIZONS.items():
            out[f"fwd_{name}"] = close.shift(-h) / close - 1.0
        rows.append(pd.DataFrame(out))
    return pd.concat(rows, ignore_index=True)


def edge(sub: pd.DataFrame, signal: str, fwd: str) -> dict:
    s = sub.dropna(subset=[signal, fwd])
    cal = sorted(s["date"].unique())
    rebal = set(cal[::REBAL])
    s = s[s["date"].isin(rebal)]
    ics, q5_minus_uni = [], []
    for _, g in s.groupby("date"):
        if len(g) < 10:
            continue
        ic = g[signal].corr(g[fwd], method="spearman")
        if pd.notna(ic):
            ics.append(ic)
        try:
            q = pd.qcut(g[signal], 5, labels=False, duplicates="drop")
        except ValueError:
            continue
        gg = g.assign(_q=q)
        if gg["_q"].nunique() < 5:
            continue
        q5 = gg.loc[gg["_q"] == gg["_q"].max(), fwd].mean()
        q5_minus_uni.append(q5 - g[fwd].mean())
    ser = pd.Series
    return {"n": len(ics), "ic": ser(ics).mean(), "ic_pos": (ser(ics) > 0).mean(),
            "edge": ser(q5_minus_uni).mean()}


def main() -> None:
    panel = load_panel()
    bull = panel[(panel["date"] < BEAR_FROM) | (panel["date"] > BEAR_TO)]
    bear = panel[(panel["date"] >= BEAR_FROM) & (panel["date"] <= BEAR_TO)]
    print(f"[데이터] {panel['ticker'].nunique()}종목 · {panel['date'].min()}~{panel['date'].max()}")
    print(f"  하락·횡보장 = {BEAR_FROM}~{BEAR_TO} / 상승장 = 그 외\n")

    for signal in ("mom_60", "trend"):
        print(f"══ 신호: {signal} ══")
        print(f"{'지평선':<6}{'│ 전체 IC':>10}{'edge':>9}{'│ 하락장 IC':>12}{'edge':>9}"
              f"{'│ 상승장 IC':>12}{'edge':>9}")
        for name in HORIZONS:
            fwd = f"fwd_{name}"
            a = edge(panel, signal, fwd)
            b = edge(bear, signal, fwd)
            c = edge(bull, signal, fwd)
            print(f"{name:<6}{a['ic']:>+10.3f}{a['edge']:>+9.2%}"
                  f"{b['ic']:>+12.3f}{b['edge']:>+9.2%}"
                  f"{c['ic']:>+12.3f}{c['edge']:>+9.2%}")
        print()

    print("판독: 'edge>0 이 하락장에서도 유지'되어야 지속가능한 기준. 상승장만 +면 장세 베팅일 뿐.")
    print("주의: 거래비용·생존편향 미반영, 장기 지평선은 표본 겹침으로 IC 신뢰구간 낙관적.")


if __name__ == "__main__":
    main()
