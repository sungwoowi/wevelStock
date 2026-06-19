"""백테스트 1차 프로브 — 결정론 신호에 예측력(edge)이 있나? (R&D 탐색용·SPEC 전)

질문: 과거 여러 시점에서 종목을 신호로 줄세우면, 신호 높은 종목이 그 다음
H거래일 동안 실제로 더 올랐나? (cross-sectional · point-in-time · 오염 0)

데이터: chart_ohlcv (2018~2026, 167종목 500봉+) 만 사용 — 외부 API 0, 미래 컨닝 0.
신호 2종(가격에서만 산출 → 자연히 cutoff-clean):
  - mom_60  : 최근 60거래일 수익률 (모멘텀/추세 추종 프리미엄)
  - trend   : 120일 이평 대비 이격 (추세 위/아래)
지표:
  - IC      : 각 리밸런스 날짜의 Spearman(신호, 미래수익) 의 평균 + IC>0 비율
  - 분위    : 신호 상위 20%(Q5) vs 하위 20%(Q1) vs 전체평균 의 평균 미래수익
  - long edge: Q5 − 전체평균 (우린 롱만 하므로 이게 실전 의미)

usage: PYTHONIOENCODING=utf-8 uv run python scripts/_backtest_signal_probe.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DB = Path("data/db/stock-advisor.sqlite")
MIN_BARS = 500        # 충분한 히스토리 종목만
LOOKBACK = 60         # 모멘텀 신호 룩백 (거래일)
MA_WIN = 120          # 추세 이평 (거래일)
FWD = 20              # 미래수익 측정 구간 (거래일 ≈ 1개월)
REBAL = 20            # 리밸런스 간격 (거래일) — 겹치지 않게 표본 추출


def load_panel() -> pd.DataFrame:
    """ticker별 close 시계열 → 위치기반 신호·미래수익 패널 (date, ticker, mom_60, trend, fwd)."""
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT ticker, date, close FROM chart_ohlcv WHERE close IS NOT NULL ORDER BY ticker, date",
        con,
    )
    con.close()
    counts = df.groupby("ticker")["date"].transform("size")
    df = df[counts >= MIN_BARS].copy()

    rows: list[pd.DataFrame] = []
    for tk, g in df.groupby("ticker"):
        g = g.reset_index(drop=True)
        close = g["close"].astype(float)
        mom = close / close.shift(LOOKBACK) - 1.0
        ma = close.rolling(MA_WIN).mean()
        trend = close / ma - 1.0
        fwd = close.shift(-FWD) / close - 1.0
        rows.append(pd.DataFrame({"date": g["date"], "ticker": tk,
                                  "mom_60": mom, "trend": trend, "fwd": fwd}))
    panel = pd.concat(rows, ignore_index=True).dropna(subset=["fwd"])
    return panel


def evaluate(panel: pd.DataFrame, signal: str) -> dict:
    """리밸런스 날짜별 IC + 분위 평균 미래수익 집계."""
    sub = panel.dropna(subset=[signal]).copy()
    cal = sorted(sub["date"].unique())
    rebal = set(cal[::REBAL])  # 겹치지 않는 표본 날짜
    sub = sub[sub["date"].isin(rebal)]

    ics: list[float] = []
    q1s: list[float] = []
    q5s: list[float] = []
    means: list[float] = []
    for _, g in sub.groupby("date"):
        if len(g) < 10:  # 그 날 종목 너무 적으면 스킵
            continue
        ic = g[signal].corr(g["fwd"], method="spearman")
        if pd.notna(ic):
            ics.append(ic)
        try:
            q = pd.qcut(g[signal], 5, labels=False, duplicates="drop")
        except ValueError:
            continue
        g = g.assign(_q=q)
        nq = g["_q"].nunique()
        if nq < 5:
            continue
        q1s.append(g.loc[g["_q"] == 0, "fwd"].mean())
        q5s.append(g.loc[g["_q"] == nq - 1, "fwd"].mean())
        means.append(g["fwd"].mean())

    s = pd.Series
    return {
        "signal": signal,
        "n_dates": len(ics),
        "ic_mean": s(ics).mean(),
        "ic_pos_rate": (s(ics) > 0).mean(),
        "q5_fwd": s(q5s).mean(),
        "q1_fwd": s(q1s).mean(),
        "uni_fwd": s(means).mean(),
        "q5_minus_q1": s(q5s).mean() - s(q1s).mean(),
        "q5_minus_uni": s(q5s).mean() - s(means).mean(),
    }


def verdict(r: dict) -> str:
    ic, edge = r["ic_mean"], r["q5_minus_uni"]
    if ic > 0.03 and edge > 0.003 and r["ic_pos_rate"] > 0.55:
        return "🟢 edge 있음 (신호 상위가 평균을 꾸준히 상회)"
    if ic < -0.02 or edge < -0.002:
        return "🔴 역방향 — 이 신호는 단독으론 해로움"
    return "🟡 미미·노이즈 (단독 edge 약함)"


def main() -> None:
    print(f"[데이터] {DB}  룩백 {LOOKBACK}d · 추세이평 {MA_WIN}d · 미래 {FWD}d · 리밸런스 {REBAL}d")
    panel = load_panel()
    print(f"[패널] {panel['ticker'].nunique()}종목 · 관측 {len(panel):,}행 · "
          f"기간 {panel['date'].min()} ~ {panel['date'].max()}\n")

    for sig in ("mom_60", "trend"):
        r = evaluate(panel, sig)
        print(f"── 신호: {sig} ──")
        print(f"  리밸런스 날짜 수 : {r['n_dates']}")
        print(f"  평균 IC          : {r['ic_mean']:+.4f}   (IC>0 비율 {r['ic_pos_rate']:.0%})")
        print(f"  Q5(상위) 미래수익: {r['q5_fwd']:+.3%}")
        print(f"  Q1(하위) 미래수익: {r['q1_fwd']:+.3%}")
        print(f"  전체평균 미래수익: {r['uni_fwd']:+.3%}")
        print(f"  Q5−Q1 스프레드   : {r['q5_minus_q1']:+.3%}")
        print(f"  Q5−전체 (롱 edge): {r['q5_minus_uni']:+.3%}")
        print(f"  판정: {verdict(r)}\n")

    print("주의: 거래비용·슬리피지·생존편향 미반영(1차 거친 측정). 정식 채점은 SPEC 단계.")


if __name__ == "__main__":
    main()
