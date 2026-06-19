"""백테스트 1차 — α(결정론 코어)가 6M/12M·장세별로 모멘텀을 이기나? (R&D·SPEC 전)

모멘텀/추세는 6~12개월·하락장에서 선택 edge 가 확인됨(_backtest_horizon_regime_probe).
이제 같은 조건에서 **우리 α 가 멍청한 모멘텀을 이기나**를 본다. α 는 Stage2 LLM 을 꺼
결정론 코어만 사용(hindsight 오염·네트워크 차단). 패널을 CSV 로 저장 → 재스윕 시 재계산 불필요.

usage: PYTHONIOENCODING=utf-8 uv run python scripts/_backtest_alpha_horizon_regime.py
"""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from collectors import anchors

async def _no_llm(*a, **k):  # noqa: ANN002, ANN003
    return None
anchors.select_anchors_via_llm = _no_llm  # type: ignore[assignment]

DB = Path("data/db/stock-advisor.sqlite")
PANEL_OUT = Path("data/_alpha_backtest_panel.csv")
MIN_BARS = 500
LOOKBACK = 60
REBAL = 60
H = {"6M": 120, "12M": 250}
BEAR_FROM, BEAR_TO = "2022-01-01", "2024-12-31"


def load_prices() -> dict[str, pd.DataFrame]:
    con = sqlite3.connect(DB)
    df = pd.read_sql_query(
        "SELECT ticker, date, close FROM chart_ohlcv WHERE close IS NOT NULL ORDER BY ticker, date", con)
    con.close()
    counts = df.groupby("ticker")["date"].transform("size")
    df = df[counts >= MIN_BARS]
    return {tk: g.reset_index(drop=True) for tk, g in df.groupby("ticker")}


async def build_panel() -> pd.DataFrame:
    prices = load_prices()
    tickers = sorted(prices)
    cal = sorted({d for g in prices.values() for d in g["date"]})
    rebal = cal[LOOKBACK::REBAL]
    rebal = [d for d in rebal if d <= cal[-max(H.values()) - 1]]
    print(f"[설계] {len(tickers)}종목 × {len(rebal)}시점 = {len(tickers)*len(rebal):,} α콜 "
          f"(~{len(tickers)*len(rebal)*0.3/60:.0f}분)", flush=True)
    rows: list[dict] = []
    for di, D in enumerate(rebal):
        Dd = date.fromisoformat(D)
        for tk in tickers:
            g = prices[tk]
            idx = g.index[g["date"] == D]
            if len(idx) == 0:
                continue
            i = int(idx[0])
            if i < LOOKBACK:
                continue
            close = g["close"].astype(float)
            row = {"date": D, "ticker": tk, "mom_60": close.iloc[i] / close.iloc[i - LOOKBACK] - 1.0}
            for name, h in H.items():
                row[f"fwd_{name}"] = close.iloc[i + h] / close.iloc[i] - 1.0 if i + h < len(g) else None
            try:
                res = await anchors.compute_alpha_3tf(tk, cutoff_date=Dd)
                row["alpha_d"], row["alpha_w"] = res["daily"].value, res["weekly"].value
            except Exception:  # noqa: BLE001
                row["alpha_d"] = row["alpha_w"] = None
            rows.append(row)
        print(f"  [{di+1}/{len(rebal)}] {D}", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(PANEL_OUT, index=False)
    print(f"[저장] 패널 → {PANEL_OUT} ({len(df):,}행)", flush=True)
    return df


def edge(sub: pd.DataFrame, signal: str, fwd: str) -> dict:
    s = sub.dropna(subset=[signal, fwd])
    ics, e = [], []
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
        e.append(gg.loc[gg["_q"] == gg["_q"].max(), fwd].mean() - g[fwd].mean())
    return {"n": len(ics), "ic": pd.Series(ics).mean(), "edge": pd.Series(e).mean()}


def report(panel: pd.DataFrame) -> None:
    bull = panel[(panel["date"] < BEAR_FROM) | (panel["date"] > BEAR_TO)]
    bear = panel[(panel["date"] >= BEAR_FROM) & (panel["date"] <= BEAR_TO)]
    print(f"\n[패널] {panel['ticker'].nunique()}종목 · 관측 {len(panel):,} · α유효 {panel['alpha_d'].notna().sum():,}\n")
    for name in H:
        fwd = f"fwd_{name}"
        print(f"══ 지평선 {name} ══   (edge = Q5−전체평균 = 상위 선택 우위)")
        print(f"{'신호':<10}{'│ 하락장 IC':>12}{'edge':>9}{'│ 상승장 IC':>12}{'edge':>9}")
        for sig in ("alpha_d", "alpha_w", "mom_60"):
            b, c = edge(bear, sig, fwd), edge(bull, sig, fwd)
            print(f"{sig:<10}{b['ic']:>+12.3f}{b['edge']:>+9.2%}{c['ic']:>+12.3f}{c['edge']:>+9.2%}")
        ad, aw, mm = edge(bear, "alpha_d", fwd), edge(bear, "alpha_w", fwd), edge(bear, "mom_60", fwd)
        best_a = max(ad["edge"], aw["edge"])
        verdict = ("🟢 α가 모멘텀을 이김" if best_a > mm["edge"] + 0.005
                   else "🔴 α가 모멘텀에 못 미침" if best_a < mm["edge"] - 0.005
                   else "🟡 α≈모멘텀 (복잡함이 값을 못 함)")
        print(f"  → 하락장 {name}: α최고 {best_a:+.2%} vs 모멘텀 {mm['edge']:+.2%}  {verdict}\n")
    print("주의: 거래비용·생존편향 미반영. 배포본 α(LLM 선택)는 hindsight 로 미측정. 하락장 표본 적음(거침).")


def main() -> None:
    print(f"[데이터] {DB}  α=결정론코어(LLM off) · 지평선 6M/12M · 리밸런스 {REBAL}d", flush=True)
    panel = asyncio.run(build_panel())
    report(panel)


if __name__ == "__main__":
    main()
