"""SLOT S2 — F-Score 세 축 production 분포 진단 (INFRA-STOCK-SUPPLY-001 튜닝).

다종목 라이브 종목 수급으로 theme_match ratio · momentum_raw · inflow_speed_raw 분포를
수집해 `config/score_inputs.yaml::flow` breakpoints 재튜닝 근거를 만든다.
**실 KIS 호출**(TESTING 미설정), 종목 **순차**(rate limit — 병렬 fan-out 금지).

theme_match 의 raw ratio 는 FlowInputs 가 노출하지 않으므로(score 만 노출) 스크립트가
`score_theme_match` 와 동일식 `authority_net / (5주체 abs 합 + 1)` 로 재계산한다.

실행:
    uv run python scripts/flow_distribution.py                  # 기본 ~13종 바구니
    uv run python scripts/flow_distribution.py 005930 000660    # 커스텀 ticker

산출: _flow_distribution.json (종목별 raw/score + 축별 분위수 통계) + 콘솔 표.
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

from collectors.flow_inputs import build_flow_inputs
from collectors.score_inputs_config import get_theme_authority
from collectors.stock_supply import get_stock_market_cap
from collectors.theme_match import _NET_KEYS, _SUBJECT_ALIAS
from core.inference.run_analyst import market_for_ticker

OUT_PATH = REPO_ROOT / "_flow_distribution.json"

# 테마 10종 커버 바구니 (테마별 1~2 대표주). KOSDAQ 은 market_for_ticker 자동 판별.
DEFAULT_BASKET: list[tuple[str, str]] = [
    ("005930", "삼성전자"),        # AI_semiconductor / semiconductor
    ("000660", "SK하이닉스"),       # semiconductor
    ("042700", "한미반도체"),       # AI_semiconductor
    ("005380", "현대차"),           # automotive
    ("000270", "기아"),             # automotive
    ("373220", "LG에너지솔루션"),    # secondary_battery
    ("247540", "에코프로비엠"),      # secondary_battery (KOSDAQ)
    ("012450", "한화에어로스페이스"),  # defense_nuclear
    ("042660", "한화오션"),         # shipbuilding
    ("207940", "삼성바이오로직스"),   # bio
    ("196170", "알테오젠"),         # bio (KOSDAQ)
    ("090430", "아모레퍼시픽"),      # cosmetics
    ("454910", "두산로보틱스"),      # robotics
]


def _theme_ratio(net_sums: dict[str, int], theme: str | None) -> float | None:
    """score_theme_match 와 동일식 ratio 재계산 (FlowInputs 미노출 → 진단용 복제)."""
    if not theme:
        return None
    authority_map = get_theme_authority()
    subjects = authority_map.get(theme)
    if not subjects:
        return None
    authority_net = 0
    for s in subjects:
        authority_net += int(net_sums.get(_SUBJECT_ALIAS.get(s, s), 0))
    total_abs = sum(abs(int(net_sums.get(k, 0))) for k in _NET_KEYS) + 1
    return max(-1.0, min(1.0, authority_net / total_abs))


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


async def _probe(ticker: str, name: str) -> dict:
    """1 종목 라이브 수급 → raw 지표 + 현 breakpoints score."""
    market = "KOSDAQ" if market_for_ticker(ticker) == "KQ" else "KOSPI"
    fi = await build_flow_inputs(market=market, ticker=ticker)
    try:
        market_cap = await get_stock_market_cap(ticker)
    except Exception:  # noqa: BLE001
        market_cap = None
    ratio = _theme_ratio(fi.net_sums, fi.theme_match_theme)
    return {
        "ticker": ticker,
        "name": name,
        "market": market,
        "source": fi.source,
        "actual_days": fi.actual_days,
        "theme": fi.theme_match_theme,
        "theme_source": fi.theme_match_source,
        "net_sums": fi.net_sums,
        "market_cap_mwon": market_cap,  # 백만원
        # raw 지표 (튜닝 근거)
        "theme_ratio_raw": None if ratio is None else round(ratio, 4),
        "momentum_raw": fi.momentum_raw,
        "inflow_speed_raw": fi.inflow_speed_raw,
        "agreement": fi.agreement,
        # 현 breakpoints score (before)
        "theme_match_score": fi.theme_match_score,
        "momentum_score": fi.momentum_score,
        "inflow_score": fi.inflow_score,
        "advisory_f_score": fi.advisory_f_score,
    }


async def _run(basket: list[tuple[str, str]]) -> dict:
    rows: list[dict] = []
    errors: list[dict] = []
    for i, (ticker, name) in enumerate(basket, 1):
        print(f"[{i}/{len(basket)}] {ticker} {name} 수급 fetch ...", flush=True)
        try:
            row = await _probe(ticker, name)
            rows.append(row)
            print(
                f"      → theme={row['theme']}({row['theme_source']}) "
                f"ratio={row['theme_ratio_raw']} mom={row['momentum_raw']} "
                f"inflow={row['inflow_speed_raw']} | F(adv)={row['advisory_f_score']} "
                f"src={row['source']}",
                flush=True,
            )
        except Exception as e:  # noqa: BLE001 — 한 종목 실패가 전체 중단 막지 않음
            errors.append({"ticker": ticker, "name": name, "error": str(e)})
            print(f"      ⚠ 실패: {e}", flush=True)
        await asyncio.sleep(0.15)  # KIS 호출 간격 (최소 100ms)

    stats = {
        "theme_ratio_raw": _stats([r["theme_ratio_raw"] for r in rows]),
        "momentum_raw": _stats([r["momentum_raw"] for r in rows]),
        "inflow_speed_raw": _stats([r["inflow_speed_raw"] for r in rows]),
        "advisory_f_score": _stats([r["advisory_f_score"] for r in rows]),
    }
    return {"rows": rows, "errors": errors, "stats": stats}


def _fmt(v: object, width: int = 8) -> str:
    if v is None:
        return "—".rjust(width)
    if isinstance(v, float):
        return f"{v:.2f}".rjust(width)
    return str(v).rjust(width)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        basket = [(t, t) for t in args]
    else:
        basket = DEFAULT_BASKET

    result = asyncio.run(_run(basket))
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 100)
    print("종목별 raw 지표 + 현 config breakpoints score")
    print("=" * 100)
    hdr = (
        f"{'ticker':>7} {'name':>14} {'theme':>16} {'ratio':>8} {'mom_raw':>8} "
        f"{'inflow':>9} {'tm_sc':>6} {'mom_sc':>6} {'inf_sc':>6} {'F_adv':>6}"
    )
    print(hdr)
    print("-" * 100)
    for r in result["rows"]:
        print(
            f"{r['ticker']:>7} {r['name'][:14]:>14} {str(r['theme'])[:16]:>16} "
            f"{_fmt(r['theme_ratio_raw'])} {_fmt(r['momentum_raw'])} "
            f"{_fmt(r['inflow_speed_raw'], 9)} {_fmt(r['theme_match_score'], 6)} "
            f"{_fmt(r['momentum_score'], 6)} {_fmt(r['inflow_score'], 6)} "
            f"{_fmt(r['advisory_f_score'], 6)}"
        )

    print("\n" + "=" * 100)
    print("축별 분포 통계 (raw — breakpoints 재스케일 근거)")
    print("=" * 100)
    for axis, s in result["stats"].items():
        if s is None:
            print(f"{axis:>18}: (데이터 없음)")
            continue
        print(
            f"{axis:>18}: n={s['n']} min={s['min']} p10={s['p10']} p25={s['p25']} "
            f"median={s['median']} p75={s['p75']} p90={s['p90']} max={s['max']}"
        )

    print("\n시총 단위 교차 확인 (market_cap_mwon = 백만원):")
    for r in result["rows"]:
        mc = r["market_cap_mwon"]
        human = f"{mc / 1_000_000:.2f}조" if mc else "—"
        print(f"  {r['ticker']} {r['name'][:12]:>12}: {mc} 백만원 ≈ {human}")

    if result["errors"]:
        print(f"\n⚠ 실패 {len(result['errors'])}종: " +
              ", ".join(f"{e['ticker']}({e['error'][:40]})" for e in result["errors"]))
    print(f"\n저장: {OUT_PATH}")


if __name__ == "__main__":
    main()
