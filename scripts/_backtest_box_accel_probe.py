"""백테스트 — Track B 박스저점 순환매(평균회귀) + Track A 가속도(2차함수) 진입.

사용자 정정(2026-06-20):
  - 신고가 '근접'이 아니라 **신고가 추세가 2차함수로 가속화되는 구간 진입 후 3~6달 홀드** (Track A).
    → 단순 nh_prox 대신 **가속도(accel)** = 모멘텀이 빨라지는가(로그곡선 볼록) 로 측정.
  - 단타는 하락장에선 모멘텀 추격 X, **박스권 매매** → Track B ② = 추세 상단(>MA120) 박스에서
    저점 진입(평균회귀). 짧게(2주~1달) 먹고 나옴.

신호:
  box_btm  : (추세 종목 한정·close>MA120) 최근 40일 레인지 내 위치의 역수 = 박스 저점 근접도
  accel    : (20일수익) − (직전 20일수익) = 모멘텀 가속도(2차함수 볼록 진입)
지표 = Q5(상위20%)−전체평균. 장세분리(하락 2022~2024 vs 상승). 가격만·cutoff-clean.
usage: PYTHONIOENCODING=utf-8 uv run python scripts/_backtest_box_accel_probe.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB = Path("data/db/stock-advisor.sqlite")
MIN_BARS = 500
REBAL = 20
BEAR_FROM, BEAR_TO = "2022-01-01", "2024-12-31"
H_B = {"2주": 10, "1달": 20}      # Track B (박스 평균회귀)
H_A = {"3달": 60, "6달": 120}     # Track A (가속도 추세)


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
        ma120 = c.rolling(120).mean()
        mn, mx = c.rolling(40).min(), c.rolling(40).max()
        rng_pos = (c - mn) / (mx - mn)            # 0=박스바닥, 1=박스천장
        out = {
            "date": g["date"], "ticker": tk,
            "uptrend": (c > ma120),                # 추세 상단 (박스가 추세 위)
            "box_btm": 1.0 - rng_pos,              # 높을수록 박스 저점
            "accel": (c / c.shift(20) - 1.0) - (c.shift(20) / c.shift(40) - 1.0),
        }
        for name, h in {**H_B, **H_A}.items():
            out[f"fwd_{name}"] = c.shift(-h) / c - 1.0
        rows.append(pd.DataFrame(out))
    return pd.concat(rows, ignore_index=True)


def edge(sub: pd.DataFrame, signal: str, fwd: str) -> dict:
    s = sub.dropna(subset=[signal, fwd])
    cal = sorted(s["date"].unique())
    s = s[s["date"].isin(set(cal[::REBAL]))]
    ics, e, n = [], [], []
    for _, g in s.groupby("date"):
        if len(g) < 10:
            continue
        n.append(len(g))
        ic = g[signal].corr(g[fwd], method="spearman")
        if pd.notna(ic):
            ics.append(ic)
        try:
            q = pd.qcut(g[signal].rank(method="first"), 5, labels=False)
        except ValueError:
            continue
        gg = g.assign(_q=q)
        e.append(gg.loc[gg["_q"] == 4, fwd].mean() - g[fwd].mean())
    return {"ic": pd.Series(ics).mean(), "edge": pd.Series(e).mean(), "avg_n": pd.Series(n).mean()}


def section(title: str, panel: pd.DataFrame, signal: str, horizons: dict) -> None:
    bull = panel[(panel["date"] < BEAR_FROM) | (panel["date"] > BEAR_TO)]
    bear = panel[(panel["date"] >= BEAR_FROM) & (panel["date"] <= BEAR_TO)]
    print(f"══ {title} (신호: {signal}) ══")
    print(f"{'보유':<6}{'│ 하락장 edge':>14}{'IC':>9}{'│ 상승장 edge':>14}{'IC':>9}{'│종목/날':>9}")
    for name in horizons:
        fwd = f"fwd_{name}"
        b, c = edge(bear, signal, fwd), edge(bull, signal, fwd)
        print(f"{name:<6}{b['edge']:>+14.2%}{b['ic']:>+9.3f}{c['edge']:>+14.2%}{c['ic']:>+9.3f}"
              f"{b['avg_n']:>9.0f}")
    print()


def main() -> None:
    panel = load_panel()
    up = panel[panel["uptrend"]]
    print(f"[데이터] {panel['ticker'].nunique()}종목 · {panel['date'].min()}~{panel['date'].max()}")
    print("  edge = Q5(상위20%)−전체평균. 하락장=2022~2024.\n")
    section("Track B — 박스저점 진입 (추세 상단·평균회귀)", up, "box_btm", H_B)
    section("Track A — 가속도 진입 (2차함수 볼록)", panel, "accel", H_A)
    print("판독: 하락장에서도 edge>0 이어야 지속가능. box_btm=추세종목만(>MA120) 대상.")
    print("주의: 거래비용·생존편향 미반영. '박스'를 변동성으로 더 엄밀히 거르면 결과 달라질 수 있음(1차 거침).")


if __name__ == "__main__":
    main()
