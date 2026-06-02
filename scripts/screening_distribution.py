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
    uv run python scripts/screening_distribution.py --k 2.0           # 과열도 k 스윕(진단 전용)

`--k <value>` 는 config/screening.yaml 편집 없이 한 프로세스에서 과열도 채점 계수를
override 해 분포 변화를 즉시 비교(캘리브레이션 스윕). 승리 k 는 config 에 별도 반영.

산출: _screening_distribution.json (rows + 축별 분위수 통계 + 과열도 포화 진단 + regime
경계 근접도) + 콘솔 표 4종.
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


def _saturation_diag(rows: list[dict]) -> dict[str, object]:
    """과열도(extension_score) 천장 포화 원인 분리.

    공식 `clamp(10 - k·extension/ADR)` 에서 ma20 아래(extension_pct ≤ 0)면 무조건 10 clamp
    → k 무관. 따라서 ext==10 종목을 (B) ma20-아래 vs (A) ma20-위 과열도 압축으로 나눠
    "k 조정으로 풀리는 포화"가 얼마인지 판정한다. ratio_above_at_ceiling 이 높을수록 k 상향 유효.
    """
    scored = [r for r in rows if r.get("extension_score") is not None]
    n = len(scored)
    if n == 0:
        return {"n": 0}
    below_ma20 = [r for r in scored if (r.get("extension_pct") or 0.0) <= 0.0]
    at_ceiling = [r for r in scored if r["extension_score"] >= 10.0]
    ceiling_below = [r for r in at_ceiling if (r.get("extension_pct") or 0.0) <= 0.0]
    ceiling_above = [r for r in at_ceiling if (r.get("extension_pct") or 0.0) > 0.0]
    # SCREEN-RS C 이후: ceiling 중 ma20-아래 = deadband 내 얕은 눌림(건강, 의도된 10).
    # ma20 아래로 deadband 넘게 빠진 broken 은 이제 < 10 으로 감점됨 → ceiling 에 안 남음.
    return {
        "n": n,
        "below_ma20": len(below_ma20),
        "below_ma20_pct": round(len(below_ma20) / n * 100, 1),
        "at_ceiling_10": len(at_ceiling),
        "at_ceiling_pct": round(len(at_ceiling) / n * 100, 1),
        "ceiling_within_deadband": len(ceiling_below),   # ma20 아래지만 deadband 내 = 건강(정상)
        "ceiling_at_or_above_ma20": len(ceiling_above),  # ma20 정확히 위 = 과열 없음(정상)
        "verdict": (
            f"정상 — ceiling {len(at_ceiling)}종 = deadband 내 눌림 "
            f"{len(ceiling_below)} + ma20 근접 위 {len(ceiling_above)} (C floor 적용)"
            if at_ceiling
            else "포화 없음"
        ),
    }


async def _run(
    basket: list[tuple[str, str]],
    *,
    k_override: float | None = None,
    k_below_override: float | None = None,
    deadband_override: float | None = None,
) -> dict:
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
    parts = []
    if k_override is not None:
        parts.append(f"k={k_override}")
    if k_below_override is not None:
        parts.append(f"k_below={k_below_override}")
    if deadband_override is not None:
        parts.append(f"deadband={deadband_override}")
    k_label = ("override " + " ".join(parts)) if parts else "k=config"
    print(f"후보 풀 {len(tickers)}종 랭킹 (regime={regime}, {k_label}, DB 일봉) ...", flush=True)
    ranked = rank_candidates(
        tickers, regime,
        k_override=k_override,
        k_below_override=k_below_override,
        deadband_override=deadband_override,
    )
    rows: list[dict] = []
    for r in ranked:
        rows.append({**r, "name": name_map.get(r["ticker"], r["ticker"])})

    stats = {
        "rs_score": _stats([r["rs_score"] for r in rows]),
        "extension_score": _stats([r["extension_score"] for r in rows]),
        "screening_score": _stats([r["screening_score"] for r in rows]),
        # 과열도 입력 raw 분포 (포화가 입력단에서 어디서 오는지)
        "extension_pct": _stats([r.get("extension_pct") for r in rows]),
        "normalized": _stats([r.get("normalized") for r in rows]),
    }
    excluded = [r["ticker"] for r in rows if r["rank"] is None]
    return {
        "regime": regime,
        "k_override": k_override,
        "k_below_override": k_below_override,
        "deadband_override": deadband_override,
        "regime_weights": get_regime_weights().get(regime or "", {"w_rs": 0.5, "w_ext": 0.5}),
        "boundary": boundary,
        "macro_error": macro_err,
        "rows": rows,
        "stats": stats,
        "saturation": _saturation_diag(rows),
        "excluded": excluded,
    }


def _fmt(v: object, width: int = 8) -> str:
    if v is None:
        return "—".rjust(width)
    if isinstance(v, float):
        return f"{v:.2f}".rjust(width)
    return str(v).rjust(width)


_NUMERIC_FLAGS = {"--k": "k", "--k-below": "k_below", "--deadband": "deadband"}


def _parse_args(argv: list[str]) -> tuple[dict[str, float], list[str]]:
    """`--k 2.0`/`--k=2.0` 등 숫자 플래그 + 나머지 ticker. 소비 토큰은 ticker 에서 제외.

    지원 플래그: --k(과열 계수) / --k-below(이탈 계수) / --deadband(완충대 ADR).
    반환: ({flag_name: float}, [ticker, ...]).
    """
    overrides: dict[str, float] = {}
    consumed: set[int] = set()
    i = 0
    while i < len(argv):
        a = argv[i]
        matched: str | None = None
        raw: str | None = None
        for flag, name in _NUMERIC_FLAGS.items():
            if a == flag and i + 1 < len(argv):
                matched, raw = name, argv[i + 1]
                consumed.update({i, i + 1})
                i += 1
                break
            if a.startswith(flag + "="):
                matched, raw = name, a.split("=", 1)[1]
                consumed.add(i)
                break
        if matched is not None and raw is not None:
            try:
                overrides[matched] = float(raw)
            except ValueError:
                print(f"⚠ {a} 값 파싱 실패: {raw!r} → config 사용", flush=True)
        i += 1
    tickers = [
        a for j, a in enumerate(argv) if j not in consumed and not a.startswith("--")
    ]
    return overrides, tickers


def main() -> None:
    overrides, args = _parse_args(sys.argv[1:])
    basket = [(t, t) for t in args] if args else DEFAULT_BASKET

    result = asyncio.run(_run(
        basket,
        k_override=overrides.get("k"),
        k_below_override=overrides.get("k_below"),
        deadband_override=overrides.get("deadband"),
    ))
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    ov = []
    if result.get("k_override") is not None:
        ov.append(f"k={result['k_override']}")
    if result.get("k_below_override") is not None:
        ov.append(f"k_below={result['k_below_override']}")
    if result.get("deadband_override") is not None:
        ov.append(f"deadband={result['deadband_override']}")
    k_label = ("override " + " ".join(ov)) if ov else "k=config"

    # 표 1 — 종목별 점수 (ext% = ma20 대비 이격, 음수면 ma20 아래 → ext_score 10 clamp)
    print("\n" + "=" * 100)
    print(f"종목별 RS + 과열도 + 합성 점수  (regime={result['regime']} "
          f"{k_label} weights={result['regime_weights']})")
    print("=" * 100)
    hdr = (f"{'rank':>4} {'ticker':>7} {'name':>14} {'rs':>7} {'ext':>7} "
           f"{'ext%':>7} {'screen':>7}  reason")
    print(hdr)
    print("-" * 100)
    for r in sorted(result["rows"], key=lambda x: (x["rank"] is None, x["rank"] or 0)):
        print(
            f"{_fmt(r['rank'], 4)} {r['ticker']:>7} {r['name'][:14]:>14} "
            f"{_fmt(r['rs_score'], 7)} {_fmt(r['extension_score'], 7)} "
            f"{_fmt(r.get('extension_pct'), 7)} "
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

    # 표 3 — 과열도 천장 포화 진단 (k 재정합 유효성 판정)
    print("\n" + "=" * 100)
    print("과열도(extension_score) 천장 포화 진단 — k 조정으로 풀리는 포화인가?")
    print("=" * 100)
    sd = result.get("saturation") or {}
    if not sd.get("n"):
        print("(과열도 산출 종목 없음)")
    else:
        print(f"산출 {sd['n']}종 | ext_score==10 {sd['at_ceiling_10']}종 "
              f"({sd['at_ceiling_pct']}%) | ma20-아래 {sd['below_ma20']}종 "
              f"({sd['below_ma20_pct']}%)")
        print(f"  ceiling 내역: deadband 내 눌림 {sd['ceiling_within_deadband']}종 / "
              f"ma20 근접 위 {sd['ceiling_at_or_above_ma20']}종 (둘 다 건강=정상)")
        verdict = sd.get("verdict", "")
        print(f"  ✓ 판정: {verdict}")

    # 표 4 — regime 경계 근접도 (히스테리시스 필요성 진단)
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
