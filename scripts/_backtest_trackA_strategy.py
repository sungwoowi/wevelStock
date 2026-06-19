"""Track A 전략 백테스트 — 신호가 아니라 '실제 포트폴리오'로 돈을 버나?

검증된 신호(이평선 정배열 ma_stack + 상대강도 mom_120)를 합쳐 상위 종목을 사서
정기 교체하는 포트폴리오의 **자산곡선을 거래비용 빼고 시장(전체평균 보유)과 비교**.
횡단면 edge ≠ 실현 수익이므로 이게 "실제로 시장을 이기나"의 진짜 답.

규칙:
  - 유니버스: chart_ohlcv 167종(500봉+). 벤치마크 = 전체 동일가중 보유(=종목선택 0, '시장').
  - 신호 = 각 날짜 ma_stack 백분위순위 + mom_120 백분위순위 평균.
  - 매 REBAL 거래일마다 상위 QUINTILE(상위20%) 동일가중 보유 → 다음 리밸까지.
  - 거래비용 = 교체율 × 라운드트립 0.30%(한국 수수료+매도세 근사) 차감.
  - 측정: 누적·CAGR·변동성·샤프·MDD + 장세별(하락 2022~2024 / 상승). 자산곡선 CSV 저장.
usage: PYTHONIOENCODING=utf-8 uv run python scripts/_backtest_trackA_strategy.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

DB = Path("data/db/stock-advisor.sqlite")
OUT = Path("data/_trackA_equity_curve.csv")
MIN_BARS = 500
RT_COST = 0.003          # 라운드트립 거래비용 0.30%
TOP_PCT = 0.20           # 상위 20% 보유
BEAR_FROM, BEAR_TO = "2022-01-01", "2024-12-31"


def load() -> tuple[dict, dict, list]:
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT ticker, date, close FROM chart_ohlcv WHERE close IS NOT NULL ORDER BY ticker, date", con)
    con.close()
    counts = df.groupby("ticker")["date"].transform("size")
    df = df[counts >= MIN_BARS]
    price, sig = {}, {}
    for tk, g in df.groupby("ticker"):
        g = g.reset_index(drop=True)
        c = g["close"].astype(float)
        ma20, ma60, ma120 = c.rolling(20).mean(), c.rolling(60).mean(), c.rolling(120).mean()
        stack = (c > ma20).astype(int) + (ma20 > ma60).astype(int) + (ma60 > ma120).astype(int)
        mom = c / c.shift(120) - 1.0
        price[tk] = pd.Series(c.values, index=g["date"].values)
        sig[tk] = pd.DataFrame({"stack": stack.values, "mom": mom.values}, index=g["date"].values)
    cal = sorted(df["date"].unique())
    return price, sig, cal


def run(price: dict, sig: dict, cal: list, rebal: int) -> pd.DataFrame:
    dates = cal[120::rebal]
    rows, held = [], set()
    eq_net = eq_gross = bench = 1.0
    for i in range(len(dates) - 1):
        t, t2 = dates[i], dates[i + 1]
        cand = []
        for tk, ser in price.items():
            if t in ser.index and t2 in ser.index and t in sig[tk].index:
                s = sig[tk].loc[t]
                if pd.notna(s["stack"]) and pd.notna(s["mom"]):
                    cand.append((tk, s["stack"], s["mom"], ser.loc[t2] / ser.loc[t] - 1.0))
        if len(cand) < 20:
            continue
        cdf = pd.DataFrame(cand, columns=["tk", "stack", "mom", "ret"])
        cdf["score"] = cdf["stack"].rank(pct=True) + cdf["mom"].rank(pct=True)
        k = max(1, int(len(cdf) * TOP_PCT))
        sel = cdf.nlargest(k, "score")
        port, mkt = sel["ret"].mean(), cdf["ret"].mean()
        newheld = set(sel["tk"])
        turnover = 1.0 - (len(held & newheld) / len(newheld)) if newheld else 1.0
        cost = turnover * RT_COST
        held = newheld
        eq_gross *= (1 + port)
        eq_net *= (1 + port - cost)
        bench *= (1 + mkt)
        rows.append({"date": t2, "strat_net": eq_net, "strat_gross": eq_gross, "bench": bench,
                     "period_net": port - cost, "period_bench": mkt, "turnover": turnover})
    return pd.DataFrame(rows)


def stats(curve: pd.DataFrame, col: str, ppy: float) -> dict:
    r = curve[f"period_{'net' if col=='strat_net' else 'bench'}"]
    eq = curve[col]
    n_years = len(r) / ppy
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (1 / n_years) - 1 if n_years > 0 else float("nan")
    vol = r.std() * np.sqrt(ppy)
    sharpe = (r.mean() * ppy) / vol if vol else float("nan")
    peak = eq.cummax()
    mdd = ((eq - peak) / peak).min()
    return {"total": total, "cagr": cagr, "vol": vol, "sharpe": sharpe, "mdd": mdd}


def regime_cum(curve: pd.DataFrame, pcol: str) -> tuple[float, float]:
    bear = curve[(curve["date"] >= BEAR_FROM) & (curve["date"] <= BEAR_TO)][pcol]
    bull = curve[(curve["date"] < BEAR_FROM) | (curve["date"] > BEAR_TO)][pcol]
    return (1 + bear).prod() - 1, (1 + bull).prod() - 1


def report_one(price, sig, cal, rebal: int) -> None:
    ppy = 250 / rebal
    curve = run(price, sig, cal, rebal)
    if curve.empty:
        print(f"[리밸 {rebal}d] 데이터 부족")
        return
    s, b = stats(curve, "strat_net", ppy), stats(curve, "bench", ppy)
    print(f"══ 리밸런스 {rebal}거래일마다 (연 {ppy:.0f}회 교체) · {curve['date'].iloc[0]}~{curve['date'].iloc[-1]} ══")
    print(f"{'':<14}{'전략(비용후)':>14}{'시장(전체보유)':>16}")
    print(f"{'누적수익':<14}{s['total']:>+13.1%}{b['total']:>+16.1%}")
    print(f"{'연복리(CAGR)':<14}{s['cagr']:>+13.1%}{b['cagr']:>+16.1%}")
    print(f"{'연변동성':<14}{s['vol']:>13.1%}{b['vol']:>16.1%}")
    print(f"{'샤프(≈효율)':<14}{s['sharpe']:>13.2f}{b['sharpe']:>16.2f}")
    print(f"{'최대낙폭(MDD)':<14}{s['mdd']:>13.1%}{b['mdd']:>16.1%}")
    sb_bear, sb_bull = regime_cum(curve, "period_net")
    mb_bear, mb_bull = regime_cum(curve, "period_bench")
    print(f"{'하락장 누적':<14}{sb_bear:>+13.1%}{mb_bear:>+16.1%}   (2022~2024)")
    print(f"{'상승장 누적':<14}{sb_bull:>+13.1%}{mb_bull:>+16.1%}")
    print(f"{'평균 교체율':<14}{curve['turnover'].mean():>13.0%}  (높을수록 비용↑)")
    print(f"  → 전략이 시장 대비 연복리 {s['cagr']-b['cagr']:+.1%}p / MDD {s['mdd']-b['mdd']:+.1%}p\n")
    if rebal == 60:
        curve.to_csv(OUT, index=False)
        print(f"  [저장] 자산곡선 → {OUT}\n")


def main() -> None:
    price, sig, cal = load()
    print(f"[데이터] {len(price)}종목 · {cal[0]}~{cal[-1]} · 신호=이평선정배열+상대강도 상위 {TOP_PCT:.0%}")
    print(f"  벤치마크=전체 동일가중 보유(시장). 비용=교체율×{RT_COST:.1%}. 생존편향 미반영(낙관).\n")
    for rebal in (20, 60, 120):   # 월·분기·반기 교체
        report_one(price, sig, cal, rebal)
    print("주의: 167종은 '현재 살아있는' 종목이라 생존편향으로 결과가 낙관적. KOSPI 지수 직접 비교 아닌")
    print("      '전체 동일가중 보유' 대비(=종목선택 실력 순수 측정). 실 KOSPI는 대형주 가중이라 다름.")


if __name__ == "__main__":
    main()
