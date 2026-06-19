"""백테스트 1차 — α(WAVE-ALPHA 결정론 코어)가 멍청한 모멘텀을 이기나? (R&D·SPEC 전)

배경: α 배포본은 'Stage1 결정론 후보 + Stage2 LLM 선택' 2단계라 LLM이 끼면
백테스트가 hindsight 오염된다. 그래서 **Stage2 LLM 을 끄고 결정론 fallback(④)** 만
써서 *파동 수학 자체*의 예측력을 측정한다 (cutoff-clean · 네트워크 0).

방식: _backtest_signal_probe 와 동일 cross-sectional 틀. 같은 167종목·같은 리밸런스
날짜에서 신호별(α_daily / α_weekly / mom_60)로 줄세워 다음 FWD거래일 수익 대조 →
IC + 분위 edge 를 head-to-head 비교.

usage: PYTHONIOENCODING=utf-8 uv run python scripts/_backtest_alpha_probe.py
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from collectors import anchors

# Stage2 LLM 무력화 → 결정론 fallback 강제 (백테스트 오염·네트워크 차단)
async def _no_llm(*a, **k):  # noqa: ANN002, ANN003
    return None
anchors.select_anchors_via_llm = _no_llm  # type: ignore[assignment]

DB = Path("data/db/stock-advisor.sqlite")
MIN_BARS = 500
LOOKBACK = 60
FWD = 20
REBAL = 60   # 거래일 간격 (속도 위해 모멘텀 프로브의 20 → 60)


def load_prices() -> dict[str, pd.DataFrame]:
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT ticker, date, close FROM chart_ohlcv WHERE close IS NOT NULL ORDER BY ticker, date",
        con,
    )
    con.close()
    counts = df.groupby("ticker")["date"].transform("size")
    df = df[counts >= MIN_BARS]
    return {tk: g.reset_index(drop=True) for tk, g in df.groupby("ticker")}


async def build_panel() -> pd.DataFrame:
    prices = load_prices()
    tickers = sorted(prices)
    # 글로벌 거래일 달력 (가장 긴 종목 기준)
    cal = sorted({d for g in prices.values() for d in g["date"]})
    rebal = cal[LOOKBACK::REBAL]
    rebal = [d for d in rebal if d <= cal[-FWD - 1]]  # 미래수익 확보 가능한 날짜만
    print(f"[설계] {len(tickers)}종목 × {len(rebal)}시점 = {len(tickers)*len(rebal):,} α콜 "
          f"(콜당 ~0.3s 예상 → ~{len(tickers)*len(rebal)*0.3/60:.0f}분)", flush=True)

    rows: list[dict] = []
    for di, D in enumerate(rebal):
        Dd = date.fromisoformat(D)
        for tk in tickers:
            g = prices[tk]
            idx = g.index[g["date"] == D]
            if len(idx) == 0:
                continue
            i = int(idx[0])
            if i < LOOKBACK or i + FWD >= len(g):
                continue
            close = g["close"].astype(float)
            mom = close.iloc[i] / close.iloc[i - LOOKBACK] - 1.0
            fwd = close.iloc[i + FWD] / close.iloc[i] - 1.0
            try:
                res = await anchors.compute_alpha_3tf(tk, cutoff_date=Dd)
                a_d = res["daily"].value
                a_w = res["weekly"].value
            except Exception:  # noqa: BLE001
                a_d = a_w = None
            rows.append({"date": D, "ticker": tk, "alpha_d": a_d, "alpha_w": a_w,
                         "mom_60": mom, "fwd": fwd})
        print(f"  [{di+1}/{len(rebal)}] {D} 완료", flush=True)
    return pd.DataFrame(rows)


def evaluate(panel: pd.DataFrame, signal: str) -> dict:
    sub = panel.dropna(subset=[signal, "fwd"]).copy()
    ics, q1s, q5s, means = [], [], [], []
    for _, g in sub.groupby("date"):
        if len(g) < 10:
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
    return {"signal": signal, "n_dates": len(ics), "ic_mean": s(ics).mean(),
            "ic_pos_rate": (s(ics) > 0).mean(), "q5_fwd": s(q5s).mean(),
            "q1_fwd": s(q1s).mean(), "uni_fwd": s(means).mean(),
            "q5_minus_q1": s(q5s).mean() - s(q1s).mean(),
            "q5_minus_uni": s(q5s).mean() - s(means).mean()}


def main() -> None:
    print(f"[데이터] {DB}  α=결정론코어(LLM off) · 미래 {FWD}d · 리밸런스 {REBAL}d", flush=True)
    panel = asyncio.run(build_panel())
    print(f"\n[패널] 관측 {len(panel):,}행 · α유효 {panel['alpha_d'].notna().sum():,}\n", flush=True)
    results = {sig: evaluate(panel, sig) for sig in ("alpha_d", "alpha_w", "mom_60")}
    print(f"{'신호':<10}{'IC평균':>10}{'IC>0':>8}{'Q5수익':>10}{'전체평균':>10}{'롱edge(Q5-전체)':>16}")
    for sig, r in results.items():
        print(f"{sig:<10}{r['ic_mean']:>+10.4f}{r['ic_pos_rate']:>7.0%}"
              f"{r['q5_fwd']:>+10.2%}{r['uni_fwd']:>+10.2%}{r['q5_minus_uni']:>+16.2%}", flush=True)
    a, m = results["alpha_d"], results["mom_60"]
    print("\n── 판정: α(결정론) vs 모멘텀 ──")
    if a["q5_minus_uni"] > m["q5_minus_uni"] and a["ic_mean"] > m["ic_mean"]:
        print("🟢 α가 모멘텀보다 낫다 — 파동 코어에 추가 edge 신호.")
    elif a["q5_minus_uni"] <= 0 and a["ic_mean"] <= 0:
        print("🔴 α(결정론 단독)도 edge 없음 — 값은 LLM 선택·합류·타이밍에서 와야.")
    else:
        print("🟡 비등/미미 — 결정론 α 단독으론 모멘텀과 큰 차이 없음.")
    print("주의: 거래비용·생존편향 미반영. LLM 선택 α(배포본)는 hindsight 때문에 미측정.")


if __name__ == "__main__":
    main()
