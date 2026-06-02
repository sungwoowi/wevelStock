"""SLOT R1/R2/R3 — S-Score rs/extension/screening production 분포 진단 (SCREEN-RS-EXTENSION-001 튜닝).

leading 종목 후보 풀을 라이브 일봉으로 랭킹해 rs_score · extension_score · screening_score
분포를 수집하고, config/screening.yaml 의 임계(k·adr_window·regime_weights·regime_thresholds)
재정합 근거를 만든다. 함께 라이브 regime + 그 입력(breadth·slope·분산일)의 **경계 근접도**를
출력해 regime 진동(strong/moderate 토글) 봉합 필요성을 다음 세션이 판단하게 한다.

`flow_distribution.py` 패턴 mirror. **단, 단위가 다름**: F-Score 는 종목별 독립 probe 지만
RS 는 후보 풀 내 백분위(scoring.stock_rs_score)라 풀 전체를 `rank_candidates` **한 번**으로
랭킹한다(종목 루프 X). 실 KIS 호출은 regime 용 `compute_market_macro` 1회뿐 —
RS/extension 은 DB 일봉(load_ohlcv_from_db)만 read 하므로 fan-out KIS 없음(rate limit 무관).

실행:
    uv run python scripts/screening_distribution.py                  # 기본 ~13종 바구니
    uv run python scripts/screening_distribution.py 005930 000660    # 커스텀 ticker

산출: _screening_distribution.json (rows + 축별 분위수 통계 + regime 경계 근접도) + 콘솔 표 3종.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Windows utf-8 stdout
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # noqa: BLE001
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from collectors.market_macro import classify_market_regime, compute_market_macro
from collectors.screening import get_regime_thresholds, get_regime_weights, rank_candidates

OUT_PATH = REPO_ROOT / "_screening_distribution.json"

# leading 후보 풀 (flow_distribution.py 바구니 재사용 — 테마 10종 커버, 풀 정규화에 충분한 크기).
# RS 는 이 풀 내 상대 백분위이므로 풀이 작으면 분위수 해상도가 낮음(베이스라인 진단 목적엔 충분).
DEFAULT_BASKET: list[tuple[str, str]] = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("042700", "한미반도체"),
    ("005380", "현대차"),
    ("000270", "기아"),
    ("373220", "LG에너지솔루션"),
    ("247540", "에코프로비엠"),
    ("012450", "한화에어로스페이스"),
    ("042660", "한화오션"),
    ("207940", "삼성바이오로직스"),
    ("196170", "알테오젠"),
    ("090430", "아모레퍼시픽"),
    ("454910", "두산로보틱스"),
]


def _quantile(sorted_vals: list[float], q: float) -> float:
    """선형보간 분위수 (numpy 무의존). sorted_vals 비어있지 않다고 가정."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def _stats(vals: list[float | None]) -> dict[str, float | int] | None:
    clean = sorted(v for v in vals if v is not None)
    if not clean:
        return None
    return {
        "n": len(clean),
        "min": round(clean[0], 4),
        "p10": round(_quantile(clean, 0.10), 4),
        "p25": round(_quantile(clean, 0.25), 4),
        "median": round(_quantile(clean, 0.50), 4),
        "p75": round(_quantile(clean, 0.75), 4),
        "p90": round(_quantile(clean, 0.90), 4),
        "max": round(clean[-1], 4),
    }


# 경계 근접도 = |지표 - 임계| 가 이 값보다 작으면 진동 위험(flicker risk)으로 표기.
_BREADTH_FLICKER_BAND = 0.03    # 상승종목 비율
_SLOPE_FLICKER_BAND = 0.5       # ma20 5일 기울기 %
_DIST_FLICKER_BAND = 1          # 25일 분산일 카운트


def _boundary_proximity(macro: object, thresholds: dict[str, float]) -> dict[str, object]:
    """라이브 regime + 분류 입력의 경계 근접도. regime 진동(히스테리시스) 필요성 진단."""
    def _g(key: str) -> object:
        return getattr(macro, key, None)

    breadth = _g("breadth_ratio")
    slope = _g("ma20_slope_pct_5d")
    dist = _g("distribution_count_25d") or 0
    bw = thresholds.get("breadth_weak", 0.40)
    bs = thresholds.get("breadth_strong", 0.55)
    ps = thresholds.get("parabolic_slope_pct", 3.0)
    dc = thresholds.get("distribution_ceiling", 5)

    flickers: list[str] = []
    proximity: dict[str, object] = {}

    if breadth is not None:
        d_weak = round(breadth - bw, 4)
        d_strong = round(breadth - bs, 4)
        proximity["breadth_ratio"] = breadth
        proximity["dist_to_breadth_weak"] = d_weak
        proximity["dist_to_breadth_strong"] = d_strong
        if abs(d_weak) < _BREADTH_FLICKER_BAND:
            flickers.append(f"breadth {breadth} ~ breadth_weak {bw} (Δ{d_weak:+})")
        if abs(d_strong) < _BREADTH_FLICKER_BAND:
            flickers.append(f"breadth {breadth} ~ breadth_strong {bs} (Δ{d_strong:+})")
    if slope is not None:
        d_slope = round(slope - ps, 4)
        proximity["ma20_slope_pct_5d"] = slope
        proximity["dist_to_parabolic_slope"] = d_slope
        if abs(d_slope) < _SLOPE_FLICKER_BAND:
            flickers.append(f"slope {slope} ~ parabolic_slope {ps} (Δ{d_slope:+})")
    d_dist = dist - dc
    proximity["distribution_count_25d"] = dist
    proximity["dist_to_distribution_ceiling"] = d_dist
    if abs(d_dist) <= _DIST_FLICKER_BAND:
        flickers.append(f"distribution {dist} ~ ceiling {dc} (Δ{d_dist:+})")

    return {
        "position": _g("position"),
        "trend": _g("trend"),
        "breadth_source": _g("breadth_source"),
        "thresholds": {"breadth_weak": bw, "breadth_strong": bs,
                       "parabolic_slope_pct": ps, "distribution_ceiling": dc},
        "proximity": proximity,
        "flicker_risk": flickers,
    }


async def _run(basket: list[tuple[str, str]]) -> dict:
    name_map = {t: n for t, n in basket}
    tickers = [t for t, _ in basket]
    thresholds = get_regime_thresholds()

    # 1) 라이브 regime — 실 KIS 1콜 (compute_market_macro KOSPI)
    regime: str | None = None
    boundary: dict[str, object] = {}
    macro_err: str | None = None
    try:
        print("KOSPI 시장 매크로 fetch (regime 산출) ...", flush=True)
        macro = await compute_market_macro("KOSPI")
        regime = classify_market_regime(macro, thresholds=thresholds)
        boundary = _boundary_proximity(macro, thresholds)
        print(
            f"      → regime={regime} | position={boundary.get('position')} "
            f"trend={boundary.get('trend')} breadth={macro.breadth_ratio} "
            f"slope={macro.ma20_slope_pct_5d} dist={macro.distribution_count_25d}",
            flush=True,
        )
    except Exception as e:  # noqa: BLE001 — macro 실패해도 RS 분포는 산출
        macro_err = str(e)
        print(f"      ⚠ 매크로 실패: {e} → regime=None(균등 가중 fallback)", flush=True)

    # 2) 후보 풀 랭킹 — DB 일봉만, 한 번 (RS = 풀 내 백분위)
    print(f"후보 풀 {len(tickers)}종 랭킹 (regime={regime}, DB 일봉) ...", flush=True)
    ranked = rank_candidates(tickers, regime)
    rows: list[dict] = []
    for r in ranked:
        rows.append({**r, "name": name_map.get(r["ticker"], r["ticker"])})

    stats = {
        "rs_score": _stats([r["rs_score"] for r in rows]),
        "extension_score": _stats([r["extension_score"] for r in rows]),
        "screening_score": _stats([r["screening_score"] for r in rows]),
    }
    excluded = [r["ticker"] for r in rows if r["rank"] is None]
    return {
        "regime": regime,
        "regime_weights": get_regime_weights().get(regime or "", {"w_rs": 0.5, "w_ext": 0.5}),
        "boundary": boundary,
        "macro_error": macro_err,
        "rows": rows,
        "stats": stats,
        "excluded": excluded,
    }


def _fmt(v: object, width: int = 8) -> str:
    if v is None:
        return "—".rjust(width)
    if isinstance(v, float):
        return f"{v:.2f}".rjust(width)
    return str(v).rjust(width)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    basket = [(t, t) for t in args] if args else DEFAULT_BASKET

    result = asyncio.run(_run(basket))
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # 표 1 — 종목별 점수
    print("\n" + "=" * 92)
    print(f"종목별 RS + 과열도 + 합성 점수  (regime={result['regime']} "
          f"weights={result['regime_weights']})")
    print("=" * 92)
    hdr = (f"{'rank':>4} {'ticker':>7} {'name':>14} {'rs':>7} {'ext':>7} "
           f"{'screen':>7}  reason")
    print(hdr)
    print("-" * 92)
    for r in sorted(result["rows"], key=lambda x: (x["rank"] is None, x["rank"] or 0)):
        print(
            f"{_fmt(r['rank'], 4)} {r['ticker']:>7} {r['name'][:14]:>14} "
            f"{_fmt(r['rs_score'], 7)} {_fmt(r['extension_score'], 7)} "
            f"{_fmt(r['screening_score'], 7)}  {r.get('reason', '')}"
        )

    # 표 2 — 축별 분위수 (재스케일 근거)
    print("\n" + "=" * 92)
    print("축별 분포 통계 (raw 0~10 — k/adr_window/regime_weights 재정합 근거)")
    print("=" * 92)
    for axis, s in result["stats"].items():
        if s is None:
            print(f"{axis:>18}: (데이터 없음)")
            continue
        print(
            f"{axis:>18}: n={s['n']} min={s['min']} p10={s['p10']} p25={s['p25']} "
            f"median={s['median']} p75={s['p75']} p90={s['p90']} max={s['max']}"
        )
    if result["excluded"]:
        print(f"\n랭킹 제외(60일 데이터 부족) {len(result['excluded'])}종: "
              + ", ".join(result["excluded"]))

    # 표 3 — regime 경계 근접도 (히스테리시스 필요성 진단)
    print("\n" + "=" * 92)
    print("regime 경계 근접도 (진동/히스테리시스 필요성 진단)")
    print("=" * 92)
    b = result["boundary"]
    if not b:
        print(f"(매크로 산출 실패: {result['macro_error']})")
    else:
        print(f"regime={result['regime']} | position={b.get('position')} "
              f"trend={b.get('trend')} | breadth_source={b.get('breadth_source')}")
        print(f"임계: {b.get('thresholds')}")
        print(f"근접도: {b.get('proximity')}")
        flickers = b.get("flicker_risk") or []
        if flickers:
            print("⚠ 진동 위험 (경계 인접 — 히스테리시스 후보):")
            for f in flickers:
                print(f"   · {f}")
        else:
            print("✓ 경계에서 충분히 떨어짐 — 현재 run 진동 위험 낮음")

    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
