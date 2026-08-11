"""시장 판세 — 결정론 팩트 수집 + 렌더 (ADVISOR-CORE-001 M1-a).

**LLM 0.** 이미 DB 에 쌓이는데 판세 해석에 안 쓰이던 재료를 모아 구조화하고,
LLM 이 읽을 md 로 렌더한다. 판단(narrative·stance)은 M1-e 가 이 팩트를 읽고 한다.

지금까지 시장은 `regime / entry_posture` 라벨 2개로만 표현됐다. 그래서 2026-08-10 같은 날 —
지수는 20일선 아래인데 상승종목이 79%, 반도체만 무너지고 원자력·건설로 자금이 도는 국면 —
이 "약세장·방어"로 뭉개졌다. 이 모듈이 채우는 자리가 그 사이다.

**엇갈림(divergence)을 1급 시민으로 다룬다.** 추세↔상승종목폭, 현물↔선물 — 단일 지표가
아니라 지표 간 불일치가 국면 전환의 신호이고, 기존 파이프라인이 통째로 놓치던 정보다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

# 선물 수급을 담는 supply_demand_history 의 market 값 (신규 테이블 0 — 기존 표 재사용).
FUTURES_MARKET = "K200_FUT"

# 섹터 밴드 경계 (코스피 대비 60일 초과수익 %). config 외부화 대상 SLOT —
# 지금은 실측 분포(2026-08-10: +27.4 ~ -20.6)에서 잡은 보수적 기본값.
SECTOR_STRONG_MIN = 10.0
SECTOR_AVOID_MAX = -5.0

# 야간선물 → 시초가 판정 임계 (%).
GAP_THRESHOLD = 0.5

# 렌더 예산 — Track C 프롬프트에서 판세가 차지할 몫 (SPEC §3-c).
RENDER_BUDGET_CHARS = 2000
_MAX_SECTORS_PER_BAND = 5


@dataclass
class MarketLeg:
    """한 시장(코스피/코스닥)의 결정론 상태."""

    market: str
    close: float | None = None
    change_pct: float | None = None
    advancing: int | None = None
    declining: int | None = None
    breadth_ratio: float | None = None
    ma20_gap_pct: float | None = None
    trend: str | None = None
    distribution_count: int | None = None
    breadth_diverges: bool = False   # 추세↔상승종목폭 불일치


@dataclass
class NightRead:
    """야간선물 → 내일 시초가."""

    k200_night_pct: float | None = None
    nq_futures_pct: float | None = None
    es_futures_pct: float | None = None
    gap_call: str = "unknown"        # gap_up | flat | gap_down | unknown


@dataclass
class SectorEntry:
    sector: str
    rs_ratio: float


@dataclass
class SectorBands:
    strong: list[SectorEntry] = field(default_factory=list)
    neutral: list[SectorEntry] = field(default_factory=list)
    avoid: list[SectorEntry] = field(default_factory=list)


@dataclass
class FlowRead:
    """5주체 수급 — 당일값이 아니라 연속성·누적으로 본다."""

    foreign_1d: float | None = None
    foreign_5d: float | None = None
    foreign_streak: int = 0          # 부호=방향, 절대값=연속 일수
    institution_1d: float | None = None
    individual_1d: float | None = None
    pension_1d: float | None = None
    futures_foreign_net: float | None = None
    spot_futures_diverge: bool = False


@dataclass
class AssetRead:
    nasdaq_pct: float | None = None
    sox_pct: float | None = None
    vix: float | None = None
    dxy: float | None = None
    us_10y: float | None = None
    us_10y_bp: float | None = None
    gold_pct: float | None = None
    wti_pct: float | None = None


@dataclass
class ShortRead:
    """숏 압력 (M1-b) — 공매도·대주잔고·프로그램. 미수집이면 전부 None."""

    covered_tickers: int = 0
    avg_short_ratio: float | None = None
    max_short_ratio: float | None = None
    top_short_name: str | None = None
    total_short_balance: int | None = None
    short_balance_date: str | None = None
    short_balance_change: int | None = None
    program_net_amount: int | None = None


@dataclass
class StanceFacts:
    as_of: str
    session: str
    legs: list[MarketLeg] = field(default_factory=list)
    night: NightRead = field(default_factory=NightRead)
    sectors: SectorBands = field(default_factory=SectorBands)
    flows: FlowRead = field(default_factory=FlowRead)
    assets: AssetRead = field(default_factory=AssetRead)
    shorts: ShortRead = field(default_factory=ShortRead)

    def to_dict(self) -> dict[str, Any]:
        """facts_json 영속용 — point-in-time 리플레이 재현."""
        return asdict(self)


# ---------------------------------------------------------------------------
# 수집
# ---------------------------------------------------------------------------


def _f(v: Any) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _build_leg(row: Any) -> MarketLeg:
    close, ma20 = _f(row["index_close"]), _f(row["ma_20d"])
    gap = ((close - ma20) / ma20 * 100.0) if (close and ma20) else None
    breadth = _f(row["breadth_ratio"])
    trend = row["trend"]
    # 하락 추세인데 상승종목이 과반 = 대형주 단독 하락 / 상승 추세인데 상승종목이 소수 = 지수 착시.
    diverges = bool(
        breadth is not None and trend in ("downtrend", "uptrend")
        and ((trend == "downtrend" and breadth > 0.5) or (trend == "uptrend" and breadth < 0.5))
    )
    return MarketLeg(
        market=row["market"], close=close, change_pct=_f(row["change_pct"]),
        advancing=_i(row["advancing"]), declining=_i(row["declining"]),
        breadth_ratio=breadth,
        ma20_gap_pct=round(gap, 2) if gap is not None else None,
        trend=trend, distribution_count=_i(row["distribution_count_25d"]),
        breadth_diverges=diverges,
    )


def _collect_legs(db: Any, as_of: str) -> list[MarketLeg]:
    rows = db.fetch_all(
        "SELECT * FROM market_macro_snapshot WHERE date = ? ORDER BY market DESC", (as_of,)
    )
    return [_build_leg(r) for r in rows]


def _collect_night(db: Any, as_of: str, legs: list[MarketLeg]) -> NightRead:
    k200 = db.fetch_one(
        "SELECT kospi200_night_change_pct AS v FROM market_macro_snapshot "
        "WHERE date = ? AND market = 'KOSPI'", (as_of,),
    )
    usm = db.fetch_one(
        "SELECT nq_futures_change_pct AS nq, es_futures_change_pct AS es "
        "FROM us_macro_snapshot WHERE date = ?", (as_of,),
    )
    night = NightRead(
        k200_night_pct=_f(k200["v"]) if k200 else None,
        nq_futures_pct=_f(usm["nq"]) if usm else None,
        es_futures_pct=_f(usm["es"]) if usm else None,
    )
    v = night.k200_night_pct
    if v is None:
        night.gap_call = "unknown"
    elif v <= -GAP_THRESHOLD:
        night.gap_call = "gap_down"
    elif v >= GAP_THRESHOLD:
        night.gap_call = "gap_up"
    else:
        night.gap_call = "flat"
    return night


_BRAND_TOKENS = {"KODEX", "TIGER", "ACE", "200", "TOP10"}


def _short_sector(ticker: str | None, full: str) -> str:
    """ETF 풀네임 → 사람이 읽는 섹터명 ("TIGER 화장품" → "화장품").

    1순위 = `config/market_view.yaml` 의 `sector_labels` (티커 매핑, 이미 존재 — 재사용).
    2순위 = 브랜드 접두 제거 stem (`news_source._build_sector_map` 과 같은 규칙).
    """
    try:
        from collectors.market_view import load_market_view_config

        labels = load_market_view_config().get("sector_labels") or {}
        if ticker and ticker in labels:
            return str(labels[ticker])
    except Exception:  # noqa: BLE001 — config 부재가 판세를 막지 않음
        pass
    stem = " ".join(t for t in str(full).split() if t not in _BRAND_TOKENS)
    return stem or str(full)


def _collect_sectors(db: Any, as_of: str) -> SectorBands:
    rows = db.fetch_all(
        "SELECT sector, etf_ticker, rs_ratio FROM sector_rs_snapshot WHERE date = ? "
        "AND rs_ratio IS NOT NULL ORDER BY rs_ratio DESC", (as_of,),
    )
    bands = SectorBands()
    for r in rows:
        e = SectorEntry(
            sector=_short_sector(r["etf_ticker"], r["sector"]),
            rs_ratio=round(_f(r["rs_ratio"]) or 0.0, 1),
        )
        if e.rs_ratio >= SECTOR_STRONG_MIN:
            bands.strong.append(e)
        elif e.rs_ratio <= SECTOR_AVOID_MAX:
            bands.avoid.append(e)
        else:
            bands.neutral.append(e)
    bands.avoid.sort(key=lambda e: e.rs_ratio)   # 나쁜 순 (피할 것부터)
    return bands


def _collect_flows(db: Any, as_of: str) -> FlowRead:
    rows = db.fetch_all(
        "SELECT date, foreign_net, institution_net, individual_net, pension_net "
        "FROM supply_demand_history WHERE market = 'KOSPI' AND date <= ? "
        "ORDER BY date DESC LIMIT 5", (as_of,),
    )
    fl = FlowRead()
    if rows:
        head = rows[0]
        fl.foreign_1d = _f(head["foreign_net"])
        fl.institution_1d = _f(head["institution_net"])
        fl.individual_1d = _f(head["individual_net"])
        fl.pension_1d = _f(head["pension_net"])
        vals = [_f(r["foreign_net"]) for r in rows]
        fl.foreign_5d = sum(v for v in vals if v is not None) or None
        # 연속성 — 당일 부호와 같은 부호가 몇 일 이어졌나 (부호로 방향 표현).
        if vals and vals[0] is not None and vals[0] != 0:
            sign = 1 if vals[0] > 0 else -1
            streak = 0
            for v in vals:
                if v is None or (v > 0) != (sign > 0):
                    break
                streak += 1
            fl.foreign_streak = streak * sign

    fut = db.fetch_one(
        "SELECT foreign_net FROM supply_demand_history WHERE market = ? AND date <= ? "
        "ORDER BY date DESC LIMIT 1", (FUTURES_MARKET, as_of),
    )
    if fut:
        fl.futures_foreign_net = _f(fut["foreign_net"])
    # 현물↔선물 방향 엇갈림 = 헤지 청산 / 단기 반등 대비 신호. 기존 파이프라인 미포착.
    if fl.foreign_1d is not None and fl.futures_foreign_net is not None:
        fl.spot_futures_diverge = (fl.foreign_1d > 0) != (fl.futures_foreign_net > 0)
    return fl


def _collect_assets(db: Any, as_of: str) -> AssetRead:
    r = db.fetch_one("SELECT * FROM us_macro_snapshot WHERE date = ?", (as_of,))
    if r is None:
        return AssetRead()
    return AssetRead(
        nasdaq_pct=_f(r["nasdaq_change_pct"]), sox_pct=_f(r["sox_change_pct"]),
        vix=_f(r["vix"]), dxy=_f(r["dxy"]), us_10y=_f(r["us_10y"]),
        us_10y_bp=_f(r["us_10y_change_bp"]), gold_pct=_f(r["gold_change_pct"]),
        wti_pct=_f(r["wti_change_pct"]),
    )


def build_stance_facts(as_of: str, session: str) -> StanceFacts:
    """판세 결정론 팩트 수집 — DB read only. LLM 0 · 외부 호출 0.

    각 축은 독립 graceful — 한 축이 비어도 나머지는 채워진다(판세가 안 나가는 것보다 낫다).
    """
    db = get_db()
    legs = _collect_legs(db, as_of)
    return StanceFacts(
        as_of=as_of, session=session, legs=legs,
        night=_collect_night(db, as_of, legs),
        sectors=_collect_sectors(db, as_of),
        flows=_collect_flows(db, as_of),
        assets=_collect_assets(db, as_of),
        shorts=_collect_shorts(as_of),
    )


def _collect_shorts(as_of: str) -> ShortRead:
    """숏 압력 집계 (M1-b). 미수집이면 빈 ShortRead — 판세는 그래도 발행된다."""
    try:
        from collectors.short_sale import summarize_short_pressure
        from collectors.universe_membership import resolve_stock_name

        s = summarize_short_pressure(as_of)
        return ShortRead(
            covered_tickers=s.covered_tickers,
            avg_short_ratio=s.avg_short_ratio,
            max_short_ratio=s.max_short_ratio,
            # 사람·LLM 노출단은 종목명 (feedback_no_stock_code_in_display)
            top_short_name=(
                resolve_stock_name(s.top_short_ticker, "") if s.top_short_ticker else None
            ),
            total_short_balance=s.total_short_balance,
            short_balance_date=s.short_balance_date,
            short_balance_change=s.short_balance_change,
            program_net_amount=s.total_program_net_amount,
        )
    except Exception as e:  # noqa: BLE001 — 숏 층 부재가 판세를 막지 않음
        log.warning("stance_shorts_failed", as_of=as_of, error=str(e))
        return ShortRead()


# ---------------------------------------------------------------------------
# 렌더 — LLM 이 읽을 사실 블록 (순수)
# ---------------------------------------------------------------------------

_MARKET_KR = {"KOSPI": "코스피", "KOSDAQ": "코스닥"}
_TREND_KR = {"uptrend": "상승", "downtrend": "하락", "sideways": "횡보"}
_GAP_KR = {
    "gap_up": "갭상승 우위", "gap_down": "갭하락 우위",
    "flat": "보합 출발 예상", "unknown": "미상",
}


def _pct(v: float | None, digits: int = 2) -> str:
    return f"{v:+.{digits}f}%" if v is not None else "—"


def _eok(v: float | None) -> str:
    """백만원 → 억/조 (사람이 읽는 단위)."""
    if v is None:
        return "—"
    trillion = v / 1_000_000.0
    if abs(trillion) >= 1:
        return f"{trillion:+,.1f}조"
    return f"{v / 100.0:+,.0f}억"


def _band_line(label: str, entries: list[SectorEntry]) -> str | None:
    if not entries:
        return None
    shown = entries[:_MAX_SECTORS_PER_BAND]
    body = " · ".join(f"{e.sector} {e.rs_ratio:+.1f}%" for e in shown)
    more = f" 외 {len(entries) - len(shown)}" if len(entries) > len(shown) else ""
    return f"- {label}: {body}{more}"


def render_stance_facts_md(facts: StanceFacts) -> str:
    """판세 LLM 이 읽을 사실 md. 해석은 넣지 않는다 — 판단은 LLM 몫.

    단 **엇갈림은 문장으로 명시**한다. 지표를 나열만 하면 LLM 이 놓치는데, 국면 전환의
    핵심 신호라 사실 층에서 이름을 붙여 준다.
    """
    L: list[str] = [f"## [시장 판세 사실] {facts.as_of} · {facts.session}"]

    # 양대 시장
    if facts.legs:
        L.append("\n### 지수")
        for leg in facts.legs:
            name = _MARKET_KR.get(leg.market, leg.market)
            close = f"{leg.close:,.2f}" if leg.close is not None else "—"
            ad = (f"상승 {leg.advancing:,} / 하락 {leg.declining:,}"
                  if leg.advancing is not None and leg.declining is not None else "")
            breadth = f"({leg.breadth_ratio:.1%})" if leg.breadth_ratio is not None else ""
            L.append(
                f"- {name} {close} {_pct(leg.change_pct)} · {ad} {breadth}".rstrip()
            )
            bits = []
            if leg.ma20_gap_pct is not None:
                bits.append(f"20일선 대비 {leg.ma20_gap_pct:+.1f}%")
            if leg.trend:
                bits.append(f"추세 {_TREND_KR.get(leg.trend, leg.trend)}")
            if leg.distribution_count is not None:
                bits.append(f"25일 분산일 {leg.distribution_count}건")
            if bits:
                L.append(f"  {' · '.join(bits)}")
        diverged = [l for l in facts.legs if l.breadth_diverges]
        for leg in diverged:
            name = _MARKET_KR.get(leg.market, leg.market)
            L.append(
                f"- **엇갈림**: {name} 는 {_TREND_KR.get(leg.trend, leg.trend)} 추세인데 "
                f"상승종목이 {leg.breadth_ratio:.0%} — 지수와 종목이 따로 움직인다."
            )

    # 야간선물
    n = facts.night
    if n.gap_call != "unknown" or n.nq_futures_pct is not None:
        L.append("\n### 야간선물 → 내일 시초")
        L.append(
            f"- KOSPI200 야간 {_pct(n.k200_night_pct)} · 나스닥선물 {_pct(n.nq_futures_pct)} "
            f"· S&P선물 {_pct(n.es_futures_pct)}"
        )
        L.append(f"- 판정: {_GAP_KR[n.gap_call]}")

    # 섹터 3밴드
    b = facts.sectors
    band_lines = [
        x for x in (
            _band_line("강세", b.strong), _band_line("중립", b.neutral),
            _band_line("회피", b.avoid),
        ) if x
    ]
    if band_lines:
        L.append("\n### 섹터 (60일 초과수익)")
        L.extend(band_lines)

    # 수급
    fl = facts.flows
    if fl.foreign_1d is not None or fl.futures_foreign_net is not None:
        L.append("\n### 수급")
        if fl.foreign_1d is not None:
            streak = ""
            if abs(fl.foreign_streak) >= 2:
                word = "순매수" if fl.foreign_streak > 0 else "순매도"
                streak = f" ({abs(fl.foreign_streak)}일 연속 {word})"
            L.append(f"- 외국인 현물 {_eok(fl.foreign_1d)}{streak} · 5일 누적 {_eok(fl.foreign_5d)}")
            L.append(
                f"- 기관 {_eok(fl.institution_1d)} · 개인 {_eok(fl.individual_1d)} "
                f"· 연기금 {_eok(fl.pension_1d)}"
            )
        if fl.futures_foreign_net is not None:
            L.append(f"- 외국인 선물 {_eok(fl.futures_foreign_net)}")
        if fl.spot_futures_diverge:
            L.append(
                "- **엇갈림**: 외국인 현물과 선물의 방향이 반대다 — 헤지 청산이나 "
                "단기 반등 대비일 수 있어 추세 전환 확정으로 읽지 말 것."
            )

    # 숏 압력 (M1-b) — 수집분이 있을 때만. 숏커버링 반등 판단의 재료.
    sh = facts.shorts
    if sh.covered_tickers:
        L.append("\n### 숏 압력")
        bits = [f"평균 공매도 비중 {sh.avg_short_ratio}%"] if sh.avg_short_ratio is not None else []
        if sh.max_short_ratio is not None:
            top = f" ({sh.top_short_name})" if sh.top_short_name else ""
            bits.append(f"최고 {sh.max_short_ratio}%{top}")
        if bits:
            L.append(f"- {' · '.join(bits)} · 표본 {sh.covered_tickers}종")
        if sh.total_short_balance is not None:
            # 수준보다 증감이 신호 — 줄면 숏커버링 진행, 늘면 압력 축적.
            delta = ""
            if sh.short_balance_change is not None:
                word = "감소(커버링 진행)" if sh.short_balance_change < 0 else "증가(압력 축적)"
                delta = f" · 직전 대비 {sh.short_balance_change:+,}주 {word}"
            asof = f" [{sh.short_balance_date} 결제 기준]" if sh.short_balance_date else ""
            L.append(f"- 대주 잔고 합 {sh.total_short_balance:,}주{delta}{asof}")
        if sh.program_net_amount is not None:
            L.append(f"- 프로그램 순매수 {_eok(sh.program_net_amount)}")

    # 자산군
    a = facts.assets
    if any(v is not None for v in (a.gold_pct, a.wti_pct, a.us_10y, a.vix, a.sox_pct)):
        L.append("\n### 자산군·미장")
        L.append(
            f"- 나스닥 {_pct(a.nasdaq_pct)} · 미 반도체 {_pct(a.sox_pct)} · VIX "
            f"{a.vix if a.vix is not None else '—'}"
        )
        bp = f"({a.us_10y_bp:+.0f}bp)" if a.us_10y_bp is not None else ""
        L.append(
            f"- 미 10년 국채 {a.us_10y if a.us_10y is not None else '—'}%{bp} · 달러 "
            f"{a.dxy if a.dxy is not None else '—'} · 금 {_pct(a.gold_pct)} · 유가 {_pct(a.wti_pct)}"
        )

    md = "\n".join(L)
    if len(md) > RENDER_BUDGET_CHARS:   # 예산 초과 시 줄 단위 절단 (사실 우선순위 = 위에서부터)
        cut: list[str] = []
        size = 0
        for line in L:
            if size + len(line) + 1 > RENDER_BUDGET_CHARS:
                break
            cut.append(line)
            size += len(line) + 1
        md = "\n".join(cut)
        log.info("stance_facts_md_truncated", as_of=facts.as_of, chars=len(md))
    return md
