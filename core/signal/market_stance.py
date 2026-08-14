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
from core.llm.client import call_llm
from core.logging import get_logger
from core.notification.service import notify

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
#   2,000 → 3,000 (2026-08-13, F3 이평 구조 축 합류). 지수 2 + 종목 5 의 구조 줄이
#   ~700자를 쓴다. 늘린 만큼은 **사실**이지 지시문이 아니라 Track C 다이어트 방향과
#   어긋나지 않는다 (지시문 감축 · 사실 증가 = SPEC §3-c 역전).
RENDER_BUDGET_CHARS = 3000
_MAX_SECTORS_PER_BAND = 5
# F2 — 오늘 반응 축. 임계 미만은 잡음이라 안 싣는다.
_TODAY_MOVE_MIN = 1.0
_MAX_TODAY = 3


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
    rs_ratio: float                   # 60일 초과수익
    excess_1d: float | None = None    # 당일 초과수익 = 시장의 오늘 반응 (F2)
    excess_5d: float | None = None
    turning: str | None = None        # rebound_attempt | fatigue


@dataclass
class SectorBands:
    strong: list[SectorEntry] = field(default_factory=list)
    neutral: list[SectorEntry] = field(default_factory=list)
    avoid: list[SectorEntry] = field(default_factory=list)
    # F2 다중 시간축 — 60일 밴드는 큰 흐름이지만 구조적으로 후행한다.
    today_strong: list[SectorEntry] = field(default_factory=list)
    today_weak: list[SectorEntry] = field(default_factory=list)
    turning: list[SectorEntry] = field(default_factory=list)


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
class StructureDigest:
    """다중 시간축 이평 구조의 압축 투영 (F3). 지수·종목 **같은 형태**로 담는다.

    `MAStructure` 원본은 시간축×이평×미분이라 통째로 실으면 md 예산을 먹는다. LLM 이
    실제로 쓰는 건 ① 정배열/역배열 ② 20선과의 관계와 그 **움직임** ③ 월봉 지지력 ④ 라벨.
    """

    name: str
    kind: str                                   # index | leader
    market: str | None = None
    close: float | None = None
    change_pct: float | None = None
    daily_order: str | None = None
    weekly_order: str | None = None
    ma20_deviation_pct: float | None = None
    ma20_motion: str | None = None              # diverging | converging | flat
    ma20_accel: str | None = None               # accelerating | decelerating | steady
    monthly_support_event: str | None = None
    monthly_months_held: int | None = None
    labels: list[str] = field(default_factory=list)
    bars: int = 0
    data_date: str | None = None


@dataclass
class StructureRead:
    """F3 — 지수·주도 종목의 이평 구조 축.

    판세에 개별 종목 축이 없어 *"삼성전자가 20일선 하단에서 변곡하는 장대양봉"* 같은 걸
    못 보던 자리를 메운다. 사용자 정의 체계(일 7·13·20·60·120 / 주 5·10·20 / 월 7)를
    **지수와 종목에 같은 렌즈로** 적용한다.
    """

    indices: list[StructureDigest] = field(default_factory=list)
    leaders: list[StructureDigest] = field(default_factory=list)
    # 차트가 안 갱신돼 구조를 못 낸 **종목** 수(지수 제외 — 지수는 stale_axes 가 경고).
    # 조용히 빼면 "커버리지가 원래 이만큼"으로 읽히므로 숫자로 남긴다
    # (2026-08-13 갱신 3일 전멸 사고가 정확히 그렇게 숨었다).
    skipped_stale: int = 0
    skipped_short: int = 0


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
    structures: StructureRead = field(default_factory=StructureRead)
    # 신선도 (2026-08-12 사고) — 지수 차트가 5일 멈췄는데 breadth·야간선물은 실시간이라
    # "반쯤 신선한" 판세가 나갔다. 완전히 죽었으면 알아챘을 것을 반쯤 살아서 못 잡았다.
    index_data_date: str | None = None
    stale_axes: list[str] = field(default_factory=list)
    # 섹터 RS 를 떠받치는 ETF 차트 중 오늘 봉이 없는 수. 60일 초과수익은 ETF 일봉에서
    # 나오므로 차트가 멈추면 밴드가 통째로 과거를 가리키는데, 스냅샷 행 날짜는 오늘이라
    # 날짜 검사로는 안 잡힌다 (2026-08-13: ETF 14종이 5일 낡은 채 밴드가 발행되고 있었다).
    stale_sector_etfs: int = 0
    sector_etf_total: int = 0

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
    # 갭 판정 = 야간 **순수 이동** 기준 (collectors.night_futures 단일 출처).
    #   2026-08-12 사고: 전일 대비 누적(+4.6%)을 야간 이동으로 오인해 "갭상승 우위"를
    #   발행했다. 실제 야간 이동은 +0.34%. 임계도 그쪽 모듈이 소유한다.
    from collectors.night_futures import gap_call_from

    night.gap_call = gap_call_from(night.k200_night_pct)
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


SECTOR_BENCHMARK_MARKET = "KOSPI"


def _collect_sectors(db: Any, as_of: str, market: str = SECTOR_BENCHMARK_MARKET) -> SectorBands:
    """섹터 3밴드. **벤치마크 시장을 하나로 고정**한다 (M1-c 이후 양 시장이 적재되므로).

    같은 테마가 코스피 대비·코스닥 대비 두 행으로 존재한다 — 둘 다 읽으면 섹터가 중복되고
    한 섹터가 강세·회피 양쪽에 걸리는 모순이 생긴다. 판세의 기준 시장은 KOSPI 로 두고,
    코스닥 대비 값은 필요할 때 별도로 조회한다(현재는 미사용 — 과잉 노출 회피).
    """
    cols = ("sector, etf_ticker, rs_ratio, excess_1d, excess_5d, turning")
    rows = db.fetch_all(
        f"SELECT {cols} FROM sector_rs_snapshot "
        "WHERE date = ? AND market = ? AND rs_ratio IS NOT NULL ORDER BY rs_ratio DESC",
        (as_of, market),
    )
    if not rows:   # 해당 시장 미적재 시 시장 무관 폴백 (구 데이터 호환)
        rows = db.fetch_all(
            f"SELECT {cols} FROM sector_rs_snapshot WHERE date = ? "
            "AND rs_ratio IS NOT NULL ORDER BY rs_ratio DESC", (as_of,),
        )
    bands = SectorBands()
    for r in rows:
        e = SectorEntry(
            sector=_short_sector(r["etf_ticker"], r["sector"]),
            rs_ratio=round(_f(r["rs_ratio"]) or 0.0, 1),
            excess_1d=_f(r["excess_1d"]), excess_5d=_f(r["excess_5d"]),
            turning=r["turning"],
        )
        if e.rs_ratio >= SECTOR_STRONG_MIN:
            bands.strong.append(e)
        elif e.rs_ratio <= SECTOR_AVOID_MAX:
            bands.avoid.append(e)
        else:
            bands.neutral.append(e)
    bands.avoid.sort(key=lambda e: e.rs_ratio)   # 나쁜 순 (피할 것부터)

    # F2 — 오늘 반응 축. 60일 밴드와 **독립**으로 뽑는다(회피 섹터가 오늘 강세일 수 있고,
    # 그 엇갈림이 바로 변곡 신호다).
    todays = [e for e in (bands.strong + bands.neutral + bands.avoid) if e.excess_1d is not None]
    todays.sort(key=lambda e: e.excess_1d, reverse=True)
    bands.today_strong = [e for e in todays if e.excess_1d >= _TODAY_MOVE_MIN][:_MAX_TODAY]
    bands.today_weak = [e for e in reversed(todays) if e.excess_1d <= -_TODAY_MOVE_MIN][:_MAX_TODAY]
    # turning 은 저장돼 있으면 그대로, 없으면 여기서 파생 — 구 데이터·수동 적재도 커버.
    from collectors.sector_rs import turning_signal

    for e in bands.strong + bands.neutral + bands.avoid:
        if not e.turning:
            e.turning = turning_signal(
                excess_60d=e.rs_ratio, excess_5d=e.excess_5d, excess_1d=e.excess_1d
            )
    bands.turning = [
        e for e in (bands.strong + bands.neutral + bands.avoid) if e.turning
    ][:_MAX_TODAY]
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


INDEX_BENCHMARK_TICKER = "0001"


_INDEX_MATCH_TOL = 0.5   # 지수 포인트. 반올림·시점 차 흡수, 며칠치 괴리는 못 넘김


def _index_freshness(
    db: Any, as_of: str, legs: list[MarketLeg]
) -> tuple[str | None, list[str]]:
    """판세가 **실제로 읽는 값**이 오늘 것인지 검증.

    2026-08-12 사고: `chart_ohlcv` 지수가 08-07 에 멈춘 사이 `market_macro_snapshot` 은
    08-08~08-12 행을 매일 만들면서 **08-07 종가를 그대로 복사**했다. 행 날짜만 오늘이라
    날짜 검사로는 안 잡힌다. breadth·야간선물은 KIS 실시간이라 신선해서 "반쯤 신선한"
    판세가 그럴듯하게 나갔다.

    그래서 두 겹으로 본다:
      ① 원천(chart_ohlcv)에 as_of 봉이 있는가
      ② 판세가 쓰는 index_close 가 그 봉의 종가와 **일치**하는가
    ②가 핵심이다 — 원천만 고쳐도 소비 스냅샷이 낡았으면 똑같이 틀린다.
    """
    row = db.fetch_one(
        "SELECT MAX(date) AS d FROM chart_ohlcv WHERE ticker = ?", (INDEX_BENCHMARK_TICKER,)
    )
    latest = str(row["d"]) if row and row["d"] else None
    if not latest or latest < as_of:
        return latest, ["index_ohlcv"]

    bar = db.fetch_one(
        "SELECT close FROM chart_ohlcv WHERE ticker = ? AND date = ?",
        (INDEX_BENCHMARK_TICKER, as_of),
    )
    kospi = next((l for l in legs if l.market == "KOSPI"), None)
    if bar is None or kospi is None or kospi.close is None:
        return latest, []
    if abs(float(bar["close"]) - kospi.close) > _INDEX_MATCH_TOL:
        return latest, ["index_snapshot_mismatch"]
    return latest, []


def _sector_freshness(db: Any, as_of: str) -> tuple[int, int]:
    """(낡은 ETF 수, 전체 ETF 수) — 섹터 밴드가 오늘 차트로 계산됐는지.

    지수와 같은 함정이다. `sector_rs_snapshot` 행은 매일 생기지만 그 계산의 입력인
    ETF 일봉이 멈춰 있으면 밴드는 며칠 전 시장을 가리킨다. 그래서 스냅샷 날짜가 아니라
    **입력 차트의 신선도**를 본다 (원천이 아니라 소비값을 검증하는 것과 같은 원리).
    """
    rows = db.fetch_all(
        """
        SELECT s.etf_ticker AS ticker,
               (SELECT MAX(c.date) FROM chart_ohlcv c WHERE c.ticker = s.etf_ticker) AS last_bar
          FROM (SELECT DISTINCT etf_ticker FROM sector_rs_snapshot
                 WHERE date = ? AND rs_ratio IS NOT NULL AND etf_ticker IS NOT NULL) s
        """,
        (as_of,),
    )
    if not rows:
        return 0, 0
    stale = sum(1 for r in rows if not r["last_bar"] or str(r["last_bar"]) < as_of)
    return stale, len(rows)


def build_stance_facts(as_of: str, session: str) -> StanceFacts:
    """판세 결정론 팩트 수집 — DB read only. LLM 0 · 외부 호출 0.

    각 축은 독립 graceful — 한 축이 비어도 나머지는 채워진다(판세가 안 나가는 것보다 낫다).
    단 **신선도는 별개** — 낡은 값으로 아는 척하는 건 빈 판세보다 나쁘다.
    """
    db = get_db()
    legs = _collect_legs(db, as_of)
    index_date, stale = _index_freshness(db, as_of, legs)
    # 섹터 신선도는 **stale_axes 에 넣지 않는다.** 그 집합은 발행 자체를 막는 차단 조건이라
    # (핵심 축=지수), 섹터 하나 낡았다고 판세 전체를 침묵시키면 과잉이다. 대신 md 에
    # 경고로 실어 LLM 이 섹터 회전을 단정하지 못하게 한다 — 축 강등이지 차단이 아니다.
    stale_etfs, total_etfs = _sector_freshness(db, as_of)
    if stale_etfs:
        log.warning(
            "stance_sector_charts_stale", as_of=as_of, stale=stale_etfs, total=total_etfs,
        )
    return StanceFacts(
        index_data_date=index_date,
        stale_axes=stale,
        stale_sector_etfs=stale_etfs,
        sector_etf_total=total_etfs,
        as_of=as_of, session=session, legs=legs,
        night=_collect_night(db, as_of, legs),
        sectors=_collect_sectors(db, as_of),
        flows=_collect_flows(db, as_of),
        assets=_collect_assets(db, as_of),
        shorts=_collect_shorts(as_of),
        structures=_collect_structures(db, as_of),
    )


# ---------------------------------------------------------------------------
# F3 — 이평 구조 축 (지수 + 주도 종목). 신규 수집 0 — chart_ohlcv·universe_membership read.
# ---------------------------------------------------------------------------

_MAX_LEADERS = 5              # 판세에 실을 종목 수. 더 실으면 md 예산을 먹고 LLM 이 뭉갠다.
_LEADER_CANDIDATES = 20       # 이 중 차트가 신선한 것만 위에서부터 채운다.
_STRUCTURE_MIN_BARS = 60      # 60봉 미만이면 구조를 말하지 않는다 (20선·60선이 안 나온다).
_INDEX_TICKERS = (("0001", "코스피", "KOSPI"), ("1001", "코스닥", "KOSDAQ"))


def _digest_structure(
    structure: Any,
    *,
    name: str,
    kind: str,
    market: str | None = None,
    change_pct: float | None = None,
    data_date: str | None = None,
) -> StructureDigest:
    """`MAStructure` → 판세용 압축 투영. 없는 축은 None 그대로 둔다."""
    d = StructureDigest(
        name=name, kind=kind, market=market, change_pct=change_pct, data_date=data_date,
        labels=list(structure.labels),
    )
    daily = structure.daily
    if daily is not None:
        d.bars = daily.bars
        d.close = daily.close
        d.daily_order = daily.order
        ma20 = daily.dev(20)
        if ma20 is not None:
            d.ma20_deviation_pct = ma20.deviation_pct
            d.ma20_motion = ma20.motion
            d.ma20_accel = ma20.accel
    if structure.weekly is not None:
        d.weekly_order = structure.weekly.order
    if structure.monthly_support is not None:
        d.monthly_support_event = structure.monthly_support.event
        d.monthly_months_held = structure.monthly_support.months_held
    return d


def _latest_bar_date(db: Any, ticker: str) -> str | None:
    row = db.fetch_one("SELECT MAX(date) AS d FROM chart_ohlcv WHERE ticker = ?", (ticker,))
    return str(row["d"]) if row and row["d"] else None


def _structure_for_ticker(
    db: Any, ticker: str, as_of: str
) -> tuple[Any | None, str | None, str | None]:
    """(MAStructure, data_date, skip_reason) — 낡거나 짧으면 구조를 만들지 않는다.

    skip_reason ∈ {None, "stale", "short"}. **낡은 차트로 이평 변곡을 말하는 것이
    이 축에서 가장 위험한 실패**라 신선도를 통과 조건으로 둔다.
    """
    from collectors.charts import load_ohlcv_from_db
    from core.signal.ma_structure import build_ma_structure

    data_date = _latest_bar_date(db, ticker)
    if data_date is None or data_date < as_of:
        return None, data_date, "stale"
    df = load_ohlcv_from_db(ticker)
    if df is None or len(df) < _STRUCTURE_MIN_BARS:
        return None, data_date, "short"
    return build_ma_structure(df, name=ticker), data_date, None


def _collect_structures(db: Any, as_of: str) -> StructureRead:
    """F3 수집 — 지수 2 + 거래대금 상위 주도 종목. 실패해도 판세는 발행된다."""
    out = StructureRead()

    for ticker, label, market in _INDEX_TICKERS:
        try:
            st, data_date, skip = _structure_for_ticker(db, ticker, as_of)
        except Exception as e:  # noqa: BLE001 — 한 지수 실패가 나머지를 막지 않음
            log.warning("stance_structure_index_failed", ticker=ticker, error=str(e))
            continue
        if st is None:
            # 지수 신선도는 이미 `stale_axes` 가 최상단에 경고한다. 여기서 또 세면
            # "차트 미갱신 N종"의 N 이 지수+종목 혼합이 돼 메시지가 거짓이 된다.
            log.info("stance_structure_index_skipped", ticker=ticker, reason=skip)
            continue
        out.indices.append(
            _digest_structure(st, name=label, kind="index", market=market, data_date=data_date)
        )

    try:
        rows = db.fetch_all(
            """
            SELECT ticker, name, market, rank, change_pct
              FROM universe_membership
             WHERE date = (SELECT MAX(date) FROM universe_membership WHERE date <= ?)
               AND list_type = 'trade_value'
             ORDER BY rank
             LIMIT ?
            """,
            (as_of, _LEADER_CANDIDATES),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("stance_structure_universe_failed", as_of=as_of, error=str(e))
        return out

    from collectors.universe_membership import resolve_stock_name

    for r in rows:
        if len(out.leaders) >= _MAX_LEADERS:
            break
        ticker = r["ticker"]
        try:
            st, data_date, skip = _structure_for_ticker(db, ticker, as_of)
        except Exception as e:  # noqa: BLE001
            log.warning("stance_structure_leader_failed", ticker=ticker, error=str(e))
            continue
        if st is None:
            if skip == "stale":
                out.skipped_stale += 1
            elif skip == "short":
                out.skipped_short += 1
            continue
        out.leaders.append(
            _digest_structure(
                st,
                # 사람·LLM 노출단은 종목명 (feedback_no_stock_code_in_display)
                name=resolve_stock_name(ticker, r["name"] or ""),
                kind="leader",
                market=r["market"],
                change_pct=_f(r["change_pct"]),
                data_date=data_date,
            )
        )
    return out


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
_TURNING_KR = {"rebound_attempt": "반등 시도", "fatigue": "주도 피로"}
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


_ORDER_KR = {"bullish_stack": "정배열", "bearish_stack": "역배열", "mixed": "혼조"}
_MOTION_KR = {"diverging": "벌어짐", "converging": "수렴", "flat": "정체"}
_ACCEL_KR = {"accelerating": "가속", "decelerating": "감속", "steady": "일정"}
_SUPPORT_KR = {
    "regained": "지지 회복", "lost": "이탈", "holding": "지지 유지", "below": "아래",
}


def _structure_line(d: StructureDigest) -> str:
    """구조 한 줄 — 정지 사진(이격도)이 아니라 **움직임**까지 한 줄에 넣는다."""
    head = d.name
    if d.change_pct is not None:
        head += f" {_pct(d.change_pct)}"
    bits: list[str] = []

    order = " / ".join(
        f"{lbl} {_ORDER_KR[o]}"
        for lbl, o in (("일봉", d.daily_order), ("주봉", d.weekly_order))
        if o in _ORDER_KR
    )
    if order:
        bits.append(order)

    if d.ma20_deviation_pct is not None:
        motion = " · ".join(
            x for x in (_MOTION_KR.get(d.ma20_motion or ""), _ACCEL_KR.get(d.ma20_accel or ""))
            if x
        )
        tail = f" ({motion})" if motion else ""
        bits.append(f"20일선 {d.ma20_deviation_pct:+.1f}%{tail}")

    if d.monthly_support_event in _SUPPORT_KR:
        held = f" {d.monthly_months_held}개월" if d.monthly_months_held else ""
        bits.append(f"월봉 7선 {_SUPPORT_KR[d.monthly_support_event]}{held}")

    line = f"- {head} · {' · '.join(bits)}" if bits else f"- {head}"
    # 라벨 = 코드가 감지한 **사건**. 앞줄이 이미 말한 것(배열·월봉 지지)은 빼고,
    # 짧은 축부터 싣는다 — 일봉 변곡이 가장 실행 가능한데 슬롯을 월·주봉이 먹으면 묻힌다.
    events = [
        l for l in d.labels
        if "정배열" not in l and "역배열" not in l and "월봉" not in l
    ]
    events.sort(key=lambda l: 0 if "일선" in l else 1)
    if events:
        line += f"\n  ↳ {' · '.join(events[:3])}"
    return line


def _render_structures(s: StructureRead) -> list[str]:
    """F3 블록 — 지수·종목에 같은 이평 렌즈를 적용한 결과."""
    if not s.indices and not s.leaders and not (s.skipped_stale or s.skipped_short):
        return []
    L = ["\n### 이평 구조 (일 7·13·20·60·120 / 주 5·10·20 / 월 7 · 종가 기준)"]
    if not s.indices and not s.leaders:
        # **전멸 케이스에서 침묵하지 않는다.** 블록을 통째로 생략하면 "원래 없는 축"으로
        # 읽혀서, 갱신이 멈춘 걸 아무도 모른다 (2026-08-13 사고가 정확히 그렇게 숨었다).
        return L + [
            f"- ⚠ 산출 0 — 차트 미갱신 {s.skipped_stale}종 · 이력 부족 {s.skipped_short}종. "
            "**이평 구조·변곡을 언급하지 말 것** (근거 데이터가 없다)."
        ]
    for d in s.indices:
        L.append(_structure_line(d))
    if s.leaders:
        L.append("- **거래대금 상위 종목**")
        for d in s.leaders:
            L.append("  " + _structure_line(d).replace("\n  ↳", "\n    ↳"))
    skipped = s.skipped_stale + s.skipped_short
    if skipped:
        # 조용히 빼면 "커버리지가 원래 이만큼"으로 읽힌다. 빠진 사실을 남긴다.
        parts = []
        if s.skipped_stale:
            parts.append(f"차트 미갱신 {s.skipped_stale}종")
        if s.skipped_short:
            parts.append(f"이력 부족 {s.skipped_short}종")
        L.append(f"- ※ {' · '.join(parts)}은 구조 미산출 — 이 종목들은 판단에서 제외할 것.")
    return L


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
    if facts.stale_axes:
        # LLM 이 못 지나치게 최상단에 박는다 — 낡은 값으로 단정하는 것이 최악.
        L.append(
            f"\n⚠ **데이터가 낡았다**: 지수 차트 최신일이 {facts.index_data_date or '없음'} "
            f"(요청일 {facts.as_of}). 지수·추세·이격 수치를 오늘 값으로 단정하지 말 것."
        )

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

    # F3 — 이평 구조 (지수 + 주도 종목). 지수 바로 뒤 = 사실 우선순위 상위
    #      (예산 초과 시 아래에서부터 잘리므로 위치가 곧 중요도다).
    L.extend(_render_structures(facts.structures))

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
        L.append("\n### 섹터 추세 (60일 초과수익)")
        if facts.stale_sector_etfs:
            # 밴드 **바로 위**에 붙인다. 아래에 달면 LLM 이 숫자를 먼저 읽고 결론을 굳힌다.
            L.append(
                f"- ⚠ 섹터 ETF {facts.stale_sector_etfs}/{facts.sector_etf_total}종의 차트가 "
                f"{facts.as_of} 이전에서 멈춰 있다 — 아래 60일 수치는 과거 구간이다. "
                "**섹터 회전을 오늘의 사실로 단정하지 말 것.**"
            )
        L.extend(band_lines)

    # F2 — 오늘 반응 + 전환. 60일 밴드는 구조적으로 후행하므로 짧은 축을 따로 보여준다.
    if b.today_strong or b.today_weak:
        L.append("\n### 섹터 — 오늘 반응 (당일 초과수익)")
        if b.today_strong:
            L.append("- 오늘 강세: " + " · ".join(
                f"{e.sector} {e.excess_1d:+.1f}%" for e in b.today_strong))
        if b.today_weak:
            L.append("- 오늘 약세: " + " · ".join(
                f"{e.sector} {e.excess_1d:+.1f}%" for e in b.today_weak))
    if b.turning:
        L.append("- **전환 조짐**: " + " · ".join(
            f"{e.sector}({_TURNING_KR.get(e.turning, e.turning)}, 60일 {e.rs_ratio:+.1f}% "
            f"↔ 최근 {(e.excess_5d if e.excess_5d is not None else (e.excess_1d or 0)):+.1f}%)"
            for e in b.turning
        ))
        L.append("  ※ 60일 추세와 최근 움직임이 엇갈린다 — 추세 라벨만 보고 단정하지 말 것.")

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


# ===========================================================================
# M1-e — 판세 판단 (LLM 1콜) + 영속 + 알림
#   결정론 사실(M1-a~c)을 주입하고 **해석만** 시킨다. 숫자를 지어내지 않게 하는 것이 이
#   층의 전부다 — 사실은 위에서 다 계산돼 오고, LLM 은 "그래서 무슨 국면인가"만 답한다.
# ===========================================================================

STANCE_KR = {"selective": "기민한 선별", "watch": "관망", "avoid": "회피"}
_SESSION_KR = {"postclose": "장마감", "premarket": "아침"}
_SCENARIO_MARK = {"risk": "⚠", "opportunity": "🔎", "reduce": "🔻"}

_STANCE_SYSTEM = """당신은 한국 주식시장 판세를 읽는 애널리스트다.

아래 [시장 판세 사실]은 전부 실측값이다. **숫자를 새로 만들어내지 말고**, 주어진 사실만
근거로 지금이 어떤 국면인지 판단하라.

판단 원칙:
- 지수 하나로 결론내지 말 것. 지수와 상승종목 폭이 엇갈리면 그 자체가 핵심 신호다.
- 섹터 회전을 읽어라 — 어디서 돈이 빠져 어디로 가는가. 피해야 할 섹터를 명시하라.
- 수급은 방향뿐 아니라 연속성과 엇갈림(현물↔선물)을 보라.
- 자산군(금·유가·금리·달러)이 국내 섹터 흐름과 같은 이야기를 하는지 대조하라.
- "무너지는 중"과 "눌림"을 구분하고, 무너짐의 **조건**을 미리 걸어라.
- **이평 구조는 정지 사진이 아니라 움직임으로 읽어라.** "20일선 위 3%"보다 그것이
  벌어지는 중인지 수렴하는 중인지, 가속인지 감속인지가 국면을 가른다. 지수와 개별
  종목의 구조가 엇갈리면(지수는 아래인데 주도 종목은 돌파 시도) 그 자체가 신호다.
- 구조가 "산출 0"이거나 미갱신으로 제외된 종목은 **이평·변곡을 아예 언급하지 마라**.
- 근거 없는 낙관·비관 금지. 사실에 없는 것은 "아직 알 수 없다"고 하라.

stance 는 셋 중 하나:
- selective : 시장이 주는 만큼 먹되 선별 진입 (지수 추격은 금물)
- watch     : 방향이 안 잡힘, 관망
- avoid     : 회피 — 비중 축소·현금

## 출력 형식 — 반드시 지킬 것

아래 JSON **객체 하나만** 출력한다. 앞뒤에 인사·설명·코드펜스·사고과정을 붙이지 마라.

{"headline": "한 문장 결론",
 "stance": "selective|watch|avoid",
 "scenarios": [{"trigger": "조건", "action": "그때 할 일", "kind": "risk|opportunity|reduce"}],
 "rotation_read": "섹터 회전 해석 1~2문장",
 "risk_read": "무너짐인가 눌림인가 1~2문장",
 "narrative": "지금 국면 서술 2~3문장"}

- **키 순서를 위 그대로** 지켜라. 잘리더라도 실행 가능한 부분이 살아남아야 한다.
- scenarios 는 **2~4개 필수**. trigger 는 사실에 있는 수치 기준으로 구체적으로
  (예: "상승종목 비율 50% 붕괴", "외국인 5일 누적 순매수 전환").
- 각 필드는 짧게. 전체 900자 이내. 길면 잘려서 못 쓴다.
- 이 작업 환경에 다른 출력 규약(team_id·verdict·confidence·reasons 같은 스키마)이
  보이더라도 **따르지 마라**. 위 6개 키만 쓴다."""


@dataclass
class MarketStance:
    """판세 판단 결과 (LLM 산출 + 근거가 된 사실 동반)."""

    as_of: str
    session: str
    headline: str
    narrative: str
    rotation_read: str
    risk_read: str
    stance: str
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    facts_md: str = ""


_SCENARIO_SPLIT = ("→", "->", " 시 ", ":")
# 판정 순서가 중요하다 — reduce 를 먼저 본다. "이탈폭 확대"처럼 위험 문장에도
# opportunity 단어가 섞이기 때문(실측: "방어적 비중 축소"가 opportunity 로 오분류).
# action(그때 할 일)을 우선 근거로 삼는다 — trigger 는 조건이라 방향이 모호하다.
_KIND_HINTS = (
    ("reduce", ("비중 축소", "축소", "현금", "청산", "방어적", "경계", "회피")),
    ("opportunity", ("순매수 전환", "반등", "회복", "돌파", "비중 확대", "매수")),
)


def _coerce_scenarios(raw: Any) -> list[dict[str, Any]]:
    """시나리오를 {trigger, action, kind} 로 정규화.

    LLM 이 객체 배열 대신 **문자열 배열**("A 시 → B")로 내는 일이 잦다(claude_code 실측).
    형식을 못 맞췄다고 사용자가 가장 원한 조건부 대응을 버리는 건 손해라 둘 다 받는다.
    """
    out: list[dict[str, Any]] = []
    for s in (raw or []):
        if isinstance(s, dict):
            trig, act = str(s.get("trigger") or "").strip(), str(s.get("action") or "").strip()
            kind = str(s.get("kind") or "").strip()
        elif isinstance(s, str):
            text = s.strip()
            trig, act, kind = text, "", ""
            for sep in _SCENARIO_SPLIT:
                if sep in text:
                    head, _, tail = text.partition(sep)
                    trig, act = head.strip(" 시"), tail.strip()
                    break
        else:
            continue
        if not trig:
            continue
        if kind not in ("risk", "opportunity", "reduce"):
            kind = "risk"
            # action 우선 — 조건(trigger)보다 "그때 할 일"이 방향을 정확히 담는다.
            for source in (act, trig):
                matched = next(
                    (g for g, words in _KIND_HINTS if any(w in source for w in words)), None
                )
                if matched:
                    kind = matched
                    break
        out.append({"trigger": trig, "action": act, "kind": kind})
    return out


def _parse_stance(raw: str, as_of: str, session: str, facts_md: str) -> "MarketStance | None":
    from core.llm.client import parse_json_response

    try:
        d = parse_json_response(raw or "")
    except Exception as e:  # noqa: BLE001 — JSON 파싱 실패는 판세 미발행으로 끝낸다
        log.warning("stance_json_parse_failed", session=session, error=str(e))
        return None
    if not isinstance(d, dict) or not d.get("headline"):
        return None
    stance = str(d.get("stance") or "watch").strip().lower()
    if stance not in STANCE_KR:
        stance = "watch"
    scen = _coerce_scenarios(d.get("scenarios"))
    return MarketStance(
        as_of=as_of, session=session,
        headline=str(d["headline"]).strip(),
        narrative=str(d.get("narrative") or "").strip(),
        rotation_read=str(d.get("rotation_read") or "").strip(),
        risk_read=str(d.get("risk_read") or "").strip(),
        stance=stance, scenarios=scen[:4], facts_md=facts_md,
    )


def _persist_stance(stance: "MarketStance", facts: StanceFacts, market: str = "KOSPI") -> None:
    """판세를 market_view_snapshot 확장 컬럼에 병합. 결정론 행이 없으면 새로 만든다."""
    import json

    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO market_view_snapshot (date, market, session, source) "
            "VALUES (?,?,?,'stance') ON CONFLICT(date, market, session) DO NOTHING",
            (stance.as_of, market, stance.session),
        )
        conn.execute(
            "UPDATE market_view_snapshot SET narrative=?, rotation_read=?, risk_read=?, "
            "  stance=?, facts_json=? WHERE date=? AND market=? AND session=?",
            (
                f"{stance.headline}\n{stance.narrative}".strip(),
                stance.rotation_read, stance.risk_read, stance.stance,
                json.dumps(
                    {"facts": facts.to_dict(), "scenarios": stance.scenarios},
                    ensure_ascii=False,
                ),
                stance.as_of, market, stance.session,
            ),
        )


async def generate_market_stance(
    as_of: str,
    session: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> "MarketStance | None":
    """결정론 팩트 → LLM 1콜 → 판세 판단 영속. 실패 시 None(크래시 없음).

    비용: 시장 1건이라 **종목 수와 무관하게 하루 2콜**.
    """
    facts = build_stance_facts(as_of, session)
    if facts.stale_axes:
        # 핵심 축(지수)이 낡으면 **LLM 을 호출하지도 않는다** — 틀린 판세보다 침묵이 낫고,
        # 낡은 입력에 돈을 쓸 이유도 없다 (2026-08-12 사고).
        log.warning(
            "market_stance_stale_input", as_of=as_of, session=session,
            stale=facts.stale_axes, index_data_date=facts.index_data_date,
        )
        return None
    facts_md = render_stance_facts_md(facts)
    session_kr = _SESSION_KR.get(session, session)
    user = (
        f"[{session_kr} 판세 요청 · {as_of}]\n\n{facts_md}\n\n"
        "위 사실만 근거로 지금 국면을 판단하라.\n"
        "출력은 headline·narrative·rotation_read·risk_read·stance·scenarios "
        "6개 키를 가진 JSON 객체 하나뿐이다. 다른 텍스트를 붙이지 마라."
    )
    try:
        resp = await call_llm(
            call_type="market_stance",
            target=session,
            system=_STANCE_SYSTEM,
            messages=[{"role": "user", "content": user}],
            model=model,
            provider=provider,
            max_tokens=2048,
            temperature=0.3,
            # JSON 강제 콜은 thinking 예산 잠식으로 잘린 전적 있음
            # ([[feedback_gemini_thinking_budget_json]]).
            thinking_budget=0,
        )
    except Exception as e:  # noqa: BLE001 — LLM 실패가 크래시로 번지지 않음
        log.warning("market_stance_llm_failed", as_of=as_of, session=session, error=str(e))
        return None

    stance = _parse_stance(resp.get("content", ""), as_of, session, facts_md)
    if stance is None:
        log.warning("market_stance_parse_failed", as_of=as_of, session=session)
        return None
    try:
        _persist_stance(stance, facts)
    except Exception as e:  # noqa: BLE001 — 영속 실패가 알림을 막지 않음
        log.warning("market_stance_persist_failed", as_of=as_of, error=str(e))
    log.info("market_stance_generated", as_of=as_of, session=session, stance=stance.stance)
    return stance


def render_stance_notification(stance: "MarketStance") -> str:
    """🧭 판세 알림 본문. 사람이 읽는 단 — 코드 라벨 금지, 조건부 대응 형식."""
    session_kr = _SESSION_KR.get(stance.session, stance.session)
    L: list[str] = [stance.headline, ""]
    if stance.narrative:
        L.append(stance.narrative)
    if stance.facts_md:
        # 사실 블록 동반 — 판단과 숫자가 같이 있어야 사용자가 검증할 수 있다.
        body = "\n".join(
            ln for ln in stance.facts_md.split("\n") if not ln.startswith("## ")
        ).strip()
        if body:
            L.append("")
            L.append(body)
    if stance.rotation_read:
        L.append("")
        L.append("■ 섹터 회전")
        L.append(stance.rotation_read)
    if stance.risk_read:
        L.append("")
        L.append("■ 위험")
        L.append(stance.risk_read)

    L.append("")
    L.append(f"■ 자세 — {STANCE_KR.get(stance.stance, stance.stance)}")
    if stance.scenarios:
        L.append("")
        L.append("■ 시나리오")
        for s in stance.scenarios:
            mark = _SCENARIO_MARK.get(str(s.get("kind")), "·")
            act = str(s.get("action") or "").strip()
            L.append(f"{mark} {s['trigger']}" + (f" → {act}" if act else ""))
    L.append("")
    L.append(f"({session_kr} 판세 · {stance.as_of})")
    return "\n".join(L)


async def run_market_stance(
    as_of: str, session: str, *, provider: str | None = None, notify_user: bool = True
) -> "MarketStance | None":
    """판세 1회 = 생성 + 영속 + 알림. cron 진입점.

    LLM 이 실패하면 **알림을 보내지 않는다** — 빈 판세를 보내느니 침묵이 낫다.
    """
    stance = await generate_market_stance(as_of, session, provider=provider)
    if stance is None or not notify_user:
        return stance
    session_kr = _SESSION_KR.get(session, session)
    try:
        await notify(
            team_id="market_stance", level="info",
            title=f"🧭 시장 판세 — {session_kr} ({as_of})",
            body=render_stance_notification(stance),
            notification_type="market_briefing",
        )
    except Exception as e:  # noqa: BLE001 — 알림 실패가 판세 영속을 무르지 않음
        log.warning("market_stance_notify_failed", as_of=as_of, error=str(e))
    return stance
