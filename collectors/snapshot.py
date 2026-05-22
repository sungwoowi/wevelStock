"""Market snapshot for analyst system prompt — DB-first hybrid + 5분 인메모리 캐시.

목적: 분석가 LLM 호출 직전에 user_want_spec Task 2/3 의 시장 raw 를 모아
      `compose.build_pipeline_prompt` 의 RAG 직전 블록으로 자동 주입한다.
      framework 명제만 인용하던 응답이 실제 환율·VIX·수급 수치와 결합되도록.

DB-first 흐름:
  1) `briefing_parts` (market_briefing_now / market_briefing_pre) latest part 조회
  2) **시간대 인식 임계** 판정 — 다음 cron 발동 시각까지가 fresh
       (한국 cron 30 9,12,14 * * 1-5 / 미국 cron 0 7 * * 1-5)
  3) Stale 또는 부재 시에만 part 단위 부분 cold fetch (한국 5 / 미국 2)

5-Layer 정합: 분석가가 collector 직호출 = "수집팀 → 분석팀" 단방향 위반. DB 우선
      = briefing cron (수집팀) 이 raw 적재 → 분석가 (분석팀) 가 DB 에서 읽음.

7 collector (DB stale 시 부분/전체 호출):
  1) us_markets.fetch_overnight       — 나스닥/S&P500/SOX/VIX/DXY/USD-KRW/US10Y/금/WTI
  2) fear_greed.fetch_fear_greed      — CNN F&G 0~100
  3) kr_indices.fetch_kr_indices      — KOSPI/KOSDAQ/KOSPI200
  4) kr_supply_demand                 — KOSPI/KOSDAQ 5주체 수급 (백만원)
  5) kr_sectors                       — 강세 섹터 ETF (+1% 이상)
  6) kr_leading_stocks                — 코스피 10 + 코스닥 7 주도주
  7) kr_futures_supply_demand         — KOSPI200 선물 3주체 (십억원, KRX)

캐시: 모듈 수준 _LAST 인메모리. max_age_seconds (기본 300s) 안이면 재사용.
      서버 1 프로세스 가정 — 분산 환경 시 별도 backend 필요.

Partial failure: asyncio.gather(return_exceptions=True) — 일부 실패해도 나머지
                  진행, 실패 collector 키는 snapshot.failures 에 기록.
"""
from __future__ import annotations

import asyncio
import sys
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from collectors.fear_greed import fetch_fear_greed
from collectors.kr_futures_supply_demand import fetch_kr_futures_supply_demand
from collectors.kr_indices import fetch_kr_indices
from collectors.kr_leading_stocks import fetch_kr_leading_stocks
from collectors.kr_sectors import fetch_kr_sectors
from collectors.kr_supply_demand import fetch_kr_supply_demand
from collectors.market_macro import MarketMacro, compute_market_macro
from collectors.sector_rs import SectorRS, compute_sector_rs
from collectors.supply_demand_history import get_supply_60d
from collectors.us_markets import fetch_overnight
from connectors.kis import KISClient
from connectors.krx import KRXClient
from core.briefing import parts_store
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")

# 한국 정규장 cron 시각 (KST). manifest `30 9,12,14 * * 1-5` 와 일치.
_KR_CRON_HM: list[tuple[int, int]] = [(9, 30), (12, 30), (14, 30)]
# 미국 overnight cron 시각 (KST). manifest `0 7 * * 1-5`.
_US_CRON_HM: tuple[int, int] = (7, 0)
# Cron 발동 후 적재 완료까지 grace (네트워크 + KIS 22콜 ~28s).
_CRON_GRACE_SECONDS = 60


@dataclass
class MarketSnapshot:
    fetched_at: float                       # epoch seconds (호출 시각)
    fetched_at_iso: str                     # KST ISO-8601 (호출 시각)
    overnight: dict[str, Any]
    fear_greed: dict[str, Any]
    kr_indices: dict[str, Any]
    kr_supply: dict[str, Any]
    kr_futures_supply: dict[str, Any]
    kr_sectors: dict[str, Any]
    kr_leading: dict[str, Any]
    failures: list[str] = field(default_factory=list)
    source_map: dict[str, str] = field(default_factory=dict)  # "kr"|"us" → "db"|"fetch"
    db_run_ids: dict[str, str] = field(default_factory=dict)  # pipeline_id → run_id
    db_age_seconds: dict[str, float] = field(default_factory=dict)  # pipeline_id → age
    # INFRA-SNAPSHOT-EXTEND-001 (cycle 13) — A·B·C 카테고리 신규 3 필드.
    market_macro: dict[str, Any] = field(default_factory=dict)   # A: {"KOSPI": MarketMacro dict, "KOSDAQ": ...}
    sector_rs: list[dict[str, Any]] = field(default_factory=list)  # B: [SectorRS dict, ...] 14 섹터
    kr_supply_60d: dict[str, Any] = field(default_factory=dict)  # C: {"KOSPI": {...}, "KOSDAQ": {...}}
    snapshot_extend_failures: list[str] = field(default_factory=list)  # 본 SPEC 신규 fetcher 실패만 (failures 와 별개)


_LAST: MarketSnapshot | None = None
_LAST_AT: float = 0.0


# ---------------------------------------------------------------------------
# 시간대 인식 임계 (KR/US)
# ---------------------------------------------------------------------------


def _last_business_day(now_kst: datetime) -> datetime:
    """가장 최근 평일 (now 가 평일이면 자기 자신)."""
    d = now_kst
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d


def _last_expected_kr_cron(now_kst: datetime) -> datetime:
    """이 시각 기준 가장 최근에 발동했어야 하는 한국 cron 시각.

    평일 정규장 중이면 가장 가까운 과거 cron, 그 이전이면 직전 영업일 14:30.
    토/일이면 금요일 14:30.
    """
    weekday = now_kst.weekday()
    if weekday < 5:
        # 오늘의 cron 시각들 (역순) 중 now 이전 첫 번째
        for h, m in reversed(_KR_CRON_HM):
            cron_t = now_kst.replace(hour=h, minute=m, second=0, microsecond=0)
            if now_kst >= cron_t:
                return cron_t
        # 자정 ~ 09:30 — 직전 영업일 14:30
    # 토/일/평일 09:30 전 — 직전 영업일 14:30
    prev = _last_business_day(now_kst - timedelta(days=1))
    h, m = _KR_CRON_HM[-1]
    return prev.replace(hour=h, minute=m, second=0, microsecond=0)


def _last_expected_us_cron(now_kst: datetime) -> datetime:
    """이 시각 기준 가장 최근에 발동했어야 하는 미국 overnight cron (07:00 KST 평일)."""
    weekday = now_kst.weekday()
    h, m = _US_CRON_HM
    today_700 = now_kst.replace(hour=h, minute=m, second=0, microsecond=0)
    if weekday < 5 and now_kst >= today_700:
        return today_700
    # 평일 07:00 전 또는 토/일 → 직전 영업일 07:00
    prev = _last_business_day(now_kst - timedelta(days=1))
    return prev.replace(hour=h, minute=m, second=0, microsecond=0)


def kr_threshold_seconds(now_kst: datetime) -> int:
    """한국 그룹 신선도 임계 (초). DB age 가 이 값 이하이면 fresh.

    기준: now 와 가장 최근 발동했어야 할 cron 시각의 차 + grace (60s).
    공휴일은 미반영 (직전 영업일 cron 으로 fallback).
    """
    last_cron = _last_expected_kr_cron(now_kst)
    delta = (now_kst - last_cron).total_seconds()
    return int(delta) + _CRON_GRACE_SECONDS


def us_threshold_seconds(now_kst: datetime) -> int:
    """미국 overnight 그룹 신선도 임계 (초). DB age 가 이 값 이하이면 fresh."""
    last_cron = _last_expected_us_cron(now_kst)
    delta = (now_kst - last_cron).total_seconds()
    return int(delta) + _CRON_GRACE_SECONDS


# ---------------------------------------------------------------------------
# INFRA-SNAPSHOT-EXTEND-001 dataclass → dict 직렬화 helper
# ---------------------------------------------------------------------------


def _macro_to_dict(m: MarketMacro) -> dict[str, Any]:
    """MarketMacro dataclass → plain dict (snapshot.market_macro 저장용)."""
    return {
        "date": m.date,
        "index_close": m.index_close,
        "ma_36m": m.ma_36m, "ma_60m": m.ma_60m, "position": m.position,
        "ma_20d": m.ma_20d, "ma_60d": m.ma_60d,
        "ma20_slope_pct_5d": m.ma20_slope_pct_5d,
        "ma60_slope_pct_20d": m.ma60_slope_pct_20d,
        "trend": m.trend,
        "advancing": m.advancing, "declining": m.declining,
        "unchanged": m.unchanged, "breadth_ratio": m.breadth_ratio,
        "is_distribution_day": m.is_distribution_day,
        "change_pct": m.change_pct, "volume_change_pct": m.volume_change_pct,
        "distribution_count_25d": m.distribution_count_25d,
        "recent_distribution_days": m.recent_distribution_days,
        "source": m.source,
    }


def _sector_rs_to_dict(r: SectorRS) -> dict[str, Any]:
    """SectorRS dataclass → plain dict."""
    return {
        "sector": r.sector,
        "etf_ticker": r.etf_ticker,
        "rs_score": r.rs_score,
        "return_60d": r.return_60d,
        "kospi_return_60d": r.kospi_return_60d,
        "rs_ratio": r.rs_ratio,
    }


# ---------------------------------------------------------------------------
# 어댑터 (briefing_parts data_json → snapshot dict)
# ---------------------------------------------------------------------------


def _find_part_data(parts: list, key: str) -> dict | None:
    """Part 리스트에서 part_key 매칭하는 data_json 추출. 없으면 None."""
    for p in parts:
        if getattr(p, "key", None) == key:
            return p.data
    return None


def _adapt_overnight_from_part(part_data: dict) -> tuple[dict, dict]:
    """`market_briefing_pre` overnight part data_json → (overnight, fear_greed).

    persist 가 `{overnight_us: {nasdaq, sp500, sox, vix, fear_greed},
                  macro: {dxy, usdkrw, us_10y, gold, wti}, night_futures: ...}` 적재.
    snapshot.overnight 은 fetch_overnight() 의 평면 dict 형식 (fear_greed 분리).
    """
    overnight_us = part_data.get("overnight_us") or {}
    macro = part_data.get("macro") or {}
    overnight: dict[str, Any] = {
        k: v for k, v in overnight_us.items() if k != "fear_greed"
    }
    overnight.update(macro)
    fear_greed = overnight_us.get("fear_greed") or {}
    return overnight, fear_greed


def _adapt_kr_indices_from_part(part_data: dict) -> dict:
    """`market_briefing_now` market_overview part → snapshot.kr_indices."""
    return part_data.get("indices") or {}


def _adapt_kr_supply_sectors_from_part(part_data: dict) -> tuple[dict, dict, dict]:
    """`market_briefing_now` supply_sectors part → (kr_supply, kr_futures_supply, kr_sectors)."""
    return (
        part_data.get("supply_demand") or {},
        part_data.get("futures_supply_demand") or {},
        part_data.get("sectors") or {},
    )


def _adapt_kr_leading_from_part(part_data: dict) -> dict:
    """`market_briefing_now` leading_stocks part → snapshot.kr_leading."""
    return part_data.get("leading_stocks") or {}


# ---------------------------------------------------------------------------
# build_market_snapshot — DB-first hybrid
# ---------------------------------------------------------------------------


async def build_market_snapshot(
    *,
    kis: KISClient | None = None,
    krx: KRXClient | None = None,
    max_age_seconds: int = 60,
) -> tuple[MarketSnapshot, bool]:
    """DB-first hybrid + 짧은 인메모리 캐시 (default 60s).

    DB-first 가 0.3s 수준이라 5분 캐시는 cron 발동 직후 옛 데이터 노출 위험만 컸다.
    인메모리 캐시는 동시 호출 race / 짧은 burst 에 한정.

    Returns:
        (snapshot, cache_hit). cache_hit=True 면 max_age_seconds 안 인메모리 재사용.
        DB hit 와 cache hit 는 다름 — DB hit 는 snapshot.source_map 으로 노출.

    동작:
        1. 인메모리 캐시 (5분) hit 면 즉시 반환.
        2. briefing_parts latest part 조회 + 시간대 인식 임계 판정.
        3. Stale/부재 그룹의 collector 만 cold 호출 (부분 fetch).
        4. DB 그룹은 어댑터로 snapshot dict 조립.

    Note:
        - cold call 시 stderr 에 진행 표시.
        - 동시 호출 시 두 번 fetch 될 수 있음 (last-writer-wins).
        - kis/krx 가 None 이면 자체 context manager 로 단명 client 생성.
    """
    global _LAST, _LAST_AT

    now = time.time()
    if _LAST is not None and (now - _LAST_AT) < max_age_seconds:
        return _LAST, True

    started = time.monotonic()
    now_kst = datetime.now(_KST)
    kr_th = kr_threshold_seconds(now_kst)
    us_th = us_threshold_seconds(now_kst)

    # 1) DB latest parts 조회
    now_db = parts_store.get_latest_parts_with_age("market_briefing_now")
    pre_db = parts_store.get_latest_parts_with_age("market_briefing_pre")

    kr_from_db = now_db is not None and now_db[2] <= kr_th
    us_from_db = pre_db is not None and pre_db[2] <= us_th

    # 2) 부분 cold fetch — stale 그룹만
    bucket: dict[str, Any] = {
        k: {} for k in (
            "overnight", "fear_greed", "kr_indices", "kr_supply",
            "kr_sectors", "kr_leading", "kr_futures_supply",
        )
    }
    failures: list[str] = []

    fetch_tasks: list = []
    fetch_labels: list[str] = []

    async with AsyncExitStack() as stack:
        if not us_from_db:
            fetch_tasks.append(fetch_overnight())
            fetch_labels.append("overnight")
            fetch_tasks.append(fetch_fear_greed())
            fetch_labels.append("fear_greed")

        if not kr_from_db:
            kis_client = kis
            krx_client = krx
            if kis_client is None:
                kis_client = await stack.enter_async_context(KISClient())
            if krx_client is None:
                krx_client = await stack.enter_async_context(KRXClient())
            fetch_tasks.append(fetch_kr_indices(kis_client))
            fetch_labels.append("kr_indices")
            fetch_tasks.append(fetch_kr_supply_demand(kis_client))
            fetch_labels.append("kr_supply")
            fetch_tasks.append(fetch_kr_sectors(kis_client))
            fetch_labels.append("kr_sectors")
            fetch_tasks.append(fetch_kr_leading_stocks(kis_client))
            fetch_labels.append("kr_leading")
            fetch_tasks.append(fetch_kr_futures_supply_demand(krx_client))
            fetch_labels.append("kr_futures_supply")

        if fetch_tasks:
            sys.stderr.write(
                f"[market snapshot fetching {len(fetch_tasks)} collectors "
                f"(kr={'db' if kr_from_db else 'fetch'} "
                f"us={'db' if us_from_db else 'fetch'})...]\n"
            )
            sys.stderr.flush()
            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        else:
            results = []

    for label, res in zip(fetch_labels, results):
        if isinstance(res, Exception):
            bucket[label] = {"error": f"{type(res).__name__}: {res}"}
            failures.append(label)
        else:
            bucket[label] = res

    # 3) DB 어댑터 적용 — fresh 그룹만
    db_run_ids: dict[str, str] = {}
    db_age_seconds: dict[str, float] = {}

    if us_from_db and pre_db is not None:
        run_id, parts, age = pre_db
        db_run_ids["market_briefing_pre"] = run_id
        db_age_seconds["market_briefing_pre"] = age
        overnight_part = _find_part_data(parts, "overnight")
        if overnight_part:
            ov, fg = _adapt_overnight_from_part(overnight_part)
            bucket["overnight"] = ov
            bucket["fear_greed"] = fg
        else:
            bucket["overnight"] = {"error": "overnight part missing in DB"}
            bucket["fear_greed"] = {"error": "fear_greed part missing in DB"}
            failures.extend(["overnight", "fear_greed"])

    if kr_from_db and now_db is not None:
        run_id, parts, age = now_db
        db_run_ids["market_briefing_now"] = run_id
        db_age_seconds["market_briefing_now"] = age
        mo = _find_part_data(parts, "market_overview")
        ss = _find_part_data(parts, "supply_sectors")
        ls = _find_part_data(parts, "leading_stocks")
        if mo is not None:
            bucket["kr_indices"] = _adapt_kr_indices_from_part(mo)
        else:
            bucket["kr_indices"] = {"error": "market_overview part missing in DB"}
            failures.append("kr_indices")
        if ss is not None:
            sup, fut, sec = _adapt_kr_supply_sectors_from_part(ss)
            bucket["kr_supply"] = sup
            bucket["kr_futures_supply"] = fut
            bucket["kr_sectors"] = sec
        else:
            err = {"error": "supply_sectors part missing in DB"}
            bucket["kr_supply"] = err
            bucket["kr_futures_supply"] = err
            bucket["kr_sectors"] = err
            failures.extend(["kr_supply", "kr_futures_supply", "kr_sectors"])
        if ls is not None:
            bucket["kr_leading"] = _adapt_kr_leading_from_part(ls)
        else:
            bucket["kr_leading"] = {"error": "leading_stocks part missing in DB"}
            failures.append("kr_leading")

    # INFRA-SNAPSHOT-EXTEND-001 신규 3 fetcher — A 시장매크로 / B 섹터 RS / C 5주체 60일.
    # asyncio.gather 병렬 + return_exceptions 부분 발행. chart_ohlcv read 없을 시 자연 None.
    extend_failures: list[str] = []
    market_macro_dict: dict[str, Any] = {}
    sector_rs_list: list[dict[str, Any]] = []
    kr_supply_60d_dict: dict[str, Any] = {}
    try:
        macro_kospi_task = compute_market_macro("KOSPI")
        macro_kosdaq_task = compute_market_macro("KOSDAQ")
        sector_rs_task = compute_sector_rs()
        supply_kospi_task = get_supply_60d("KOSPI")
        supply_kosdaq_task = get_supply_60d("KOSDAQ")
        extend_results = await asyncio.gather(
            macro_kospi_task, macro_kosdaq_task, sector_rs_task,
            supply_kospi_task, supply_kosdaq_task,
            return_exceptions=True,
        )
        macro_kospi, macro_kosdaq, sector_rs_res, supply_kospi, supply_kosdaq = extend_results
        if isinstance(macro_kospi, MarketMacro):
            market_macro_dict["KOSPI"] = _macro_to_dict(macro_kospi)
        else:
            extend_failures.append("market_macro_kospi")
        if isinstance(macro_kosdaq, MarketMacro):
            market_macro_dict["KOSDAQ"] = _macro_to_dict(macro_kosdaq)
        else:
            extend_failures.append("market_macro_kosdaq")
        if isinstance(sector_rs_res, list):
            sector_rs_list = [_sector_rs_to_dict(r) for r in sector_rs_res]
        else:
            extend_failures.append("sector_rs")
        if isinstance(supply_kospi, dict):
            kr_supply_60d_dict["KOSPI"] = supply_kospi
        else:
            extend_failures.append("supply_60d_kospi")
        if isinstance(supply_kosdaq, dict):
            kr_supply_60d_dict["KOSDAQ"] = supply_kosdaq
        else:
            extend_failures.append("supply_60d_kosdaq")
    except Exception as exc:  # pragma: no cover — 위 gather 가 잡지만 안전망
        log.warning("snapshot_extend_unexpected", error=str(exc))
        extend_failures.append("snapshot_extend_unexpected")

    elapsed = time.monotonic() - started
    source_map = {
        "kr": "db" if kr_from_db else "fetch",
        "us": "db" if us_from_db else "fetch",
    }
    snapshot = MarketSnapshot(
        fetched_at=now,
        fetched_at_iso=datetime.fromtimestamp(now, _KST).isoformat(timespec="seconds"),
        overnight=bucket["overnight"],
        fear_greed=bucket["fear_greed"],
        kr_indices=bucket["kr_indices"],
        kr_supply=bucket["kr_supply"],
        kr_futures_supply=bucket["kr_futures_supply"],
        kr_sectors=bucket["kr_sectors"],
        kr_leading=bucket["kr_leading"],
        failures=failures,
        source_map=source_map,
        db_run_ids=db_run_ids,
        db_age_seconds=db_age_seconds,
        market_macro=market_macro_dict,
        sector_rs=sector_rs_list,
        kr_supply_60d=kr_supply_60d_dict,
        snapshot_extend_failures=extend_failures,
    )
    _LAST = snapshot
    _LAST_AT = now

    if fetch_tasks:
        sys.stderr.write(
            f"[market snapshot ready in {elapsed:.1f}s · "
            f"{len(failures)} failed · "
            f"kr={source_map['kr']} us={source_map['us']}]\n"
        )
        sys.stderr.flush()
    log.info(
        "market_snapshot_built",
        elapsed_s=round(elapsed, 2),
        failures=failures,
        source_map=source_map,
        db_run_ids=db_run_ids,
        cold_collectors=len(fetch_tasks),
    )
    return snapshot, False


def reset_cache() -> None:
    """테스트 전용 — 모듈 캐시 초기화."""
    global _LAST, _LAST_AT
    _LAST = None
    _LAST_AT = 0.0


# ---------------------------------------------------------------------------
# Render — analyst system prompt 용 마크다운
# ---------------------------------------------------------------------------


def _pct(v: Any) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "?"


def _num(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return "?"


def _won_m(million: Any) -> str:
    """백만원 → 한국식 억/조 (부호 포함)."""
    if million is None:
        return "?"
    try:
        eok = float(million) / 100.0
    except (TypeError, ValueError):
        return "?"
    sign = "+" if eok >= 0 else ""
    if abs(eok) >= 10000:
        return f"{sign}{eok / 10000:,.2f}조"
    return f"{sign}{eok:,.0f}억"


def _won_b(billion: Any) -> str:
    """십억원 → 억 (부호 포함). 1 십억원 = 10 억."""
    if billion is None:
        return "?"
    try:
        eok = float(billion) * 10.0
    except (TypeError, ValueError):
        return "?"
    sign = "+" if eok >= 0 else ""
    if abs(eok) >= 10000:
        return f"{sign}{eok / 10000:,.2f}조"
    return f"{sign}{eok:,.0f}억"


def _trade_amount_jo(million_won: Any) -> str:
    if million_won is None:
        return "?"
    try:
        jo = float(million_won) / 1_000_000.0
    except (TypeError, ValueError):
        return "?"
    return f"{jo:,.2f}조"


def _err_msg(d: Any) -> str:
    return d.get("error") if isinstance(d, dict) else "수집 실패"


def _format_age(seconds: float) -> str:
    """초 → 사람 친화 라벨 (분 / 시간)."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}초 전"
    if s < 3600:
        return f"{s // 60}분 전"
    hours = s / 3600
    if hours < 24:
        return f"{hours:.1f}시간 전"
    return f"{hours / 24:.1f}일 전"


def _format_source_line(snapshot: MarketSnapshot) -> str | None:
    """source_map + db_age_seconds → "_데이터 출처_" 라인.

    분석가가 데이터 시점을 정확히 인지하도록 호출 시각이 아니라
    실제 적재 시각 (DB age) 기준으로 표시.
    """
    if not snapshot.source_map:
        return None
    parts: list[str] = []
    pipeline_map = {"kr": "market_briefing_now", "us": "market_briefing_pre"}
    label_map = {"kr": "한국", "us": "미국"}
    for group in ("us", "kr"):  # 시간순 (overnight 먼저, 한국 정규장 뒤)
        src = snapshot.source_map.get(group)
        if src is None:
            continue
        label = label_map[group]
        if src == "db":
            age = snapshot.db_age_seconds.get(pipeline_map[group])
            age_label = _format_age(age) if age is not None else "?"
            parts.append(f"{label}=DB ({age_label} 적재)")
        else:
            parts.append(f"{label}=직접 수집 (방금)")
    return "_데이터 출처: " + " · ".join(parts) + "_"


def render_snapshot_md(snapshot: MarketSnapshot) -> str:
    """분석가 system prompt 용 마크다운.

    실패 항목은 `[수집 실패 - 사유]` 로 표기 — 7계명 #6 (데이터 없이 추측 X) 정합.
    헤더에 데이터 출처/적재 시점 명시 — 호출 시각이 아니라 실 데이터의 시점.
    """
    lines: list[str] = []
    age = max(0, int(time.time() - snapshot.fetched_at))
    lines.append(f"_호출: {snapshot.fetched_at_iso} · {age}s_")
    src_line = _format_source_line(snapshot)
    if src_line:
        lines.append(src_line)
    lines.append("")

    # 1. 미국 지수
    lines.append("### 미국 지수 (전일 종가 대비)")
    overnight = snapshot.overnight if isinstance(snapshot.overnight, dict) else {}
    for key, label in [
        ("nasdaq", "나스닥"),
        ("sp500", "S&P500"),
        ("sox", "필반(SOX)"),
        ("vix", "VIX"),
    ]:
        v = overnight.get(key)
        if isinstance(v, dict) and "error" not in v:
            lines.append(f"- {label} {_num(v.get('price'))} ({_pct(v.get('change_pct'))})")
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(v)}]")
    lines.append("")

    # 2. 환율·금리·원자재
    lines.append("### 환율·금리·원자재 (전일 종가 대비)")
    for key, label in [
        ("dxy", "DXY (달러인덱스)"),
        ("usdkrw", "USD/KRW (원달러)"),
        ("us_10y", "US10Y (10년 국채금리)"),
        ("gold", "금 GC=F"),
        ("wti", "WTI CL=F"),
    ]:
        v = overnight.get(key)
        if isinstance(v, dict) and "error" not in v:
            lines.append(f"- {label} {_num(v.get('price'))} ({_pct(v.get('change_pct'))})")
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(v)}]")
    lines.append("")

    # 3. 공포·탐욕
    lines.append("### 공포·탐욕 (CNN F&G)")
    fg = snapshot.fear_greed if isinstance(snapshot.fear_greed, dict) else {}
    if "error" not in fg and fg.get("score") is not None:
        prev = fg.get("previous_close")
        rating_kr = fg.get("rating_kr") or fg.get("rating") or ""
        prev_str = f" (전일 {prev})" if prev is not None else ""
        lines.append(f"- score {fg['score']} [{rating_kr}]{prev_str}")
    else:
        lines.append(f"- [수집 실패 - {_err_msg(fg)}]")
    lines.append("")

    # 4. 한국 지수
    lines.append("### 한국 지수 (KRX 정규장 전일 종가 대비)")
    indices = snapshot.kr_indices if isinstance(snapshot.kr_indices, dict) else {}
    for key, label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
        v = indices.get(key)
        if isinstance(v, dict) and "error" not in v:
            lines.append(
                f"- {label} {_num(v.get('value'))} ({_pct(v.get('change_pct'))}) · "
                f"거래대금 {_trade_amount_jo(v.get('trade_amount'))}"
            )
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(v)}]")
    k200 = indices.get("kospi200")
    if isinstance(k200, dict) and "error" not in k200:
        lines.append(
            f"- KOSPI200 (선물 기초) {_num(k200.get('value'))} "
            f"({_pct(k200.get('change_pct'))})"
        )
    lines.append("")

    # 5. 5주체 수급
    lines.append("### 시장 전체 수급 (시장 합계 누적)")
    supply = snapshot.kr_supply if isinstance(snapshot.kr_supply, dict) else {}
    for key, label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
        s = supply.get(key)
        if isinstance(s, dict) and "error" not in s:
            lines.append(
                f"- {label}: 개인 {_won_m(s.get('individual_net_amount_m'))} / "
                f"외인 {_won_m(s.get('foreign_net_amount_m'))} / "
                f"기관 {_won_m(s.get('institution_net_amount_m'))} "
                f"(금투 {_won_m(s.get('fin_invest_net_amount_m'))} / "
                f"연기금 {_won_m(s.get('pension_net_amount_m'))})"
            )
        else:
            lines.append(f"- {label}: [수집 실패 - {_err_msg(s)}]")
    lines.append("")

    # 6. 선물 수급
    lines.append("### KOSPI200 선물 수급 (3주체)")
    fut = snapshot.kr_futures_supply if isinstance(snapshot.kr_futures_supply, dict) else {}
    if "error" not in fut and fut.get("trade_date"):
        lines.append(
            f"- {fut.get('trade_date')}: 개인 {_won_b(fut.get('individual_net_amount_b'))} / "
            f"외인 {_won_b(fut.get('foreign_net_amount_b'))} / "
            f"기관 {_won_b(fut.get('institution_net_amount_b'))}"
        )
    else:
        lines.append(f"- [수집 실패 - {_err_msg(fut)}]")
    lines.append("")

    # 7. 강세 섹터
    lines.append("### 강세 섹터 (+1% 이상, 상승률 순)")
    sectors = snapshot.kr_sectors if isinstance(snapshot.kr_sectors, dict) else {}
    if "error" not in sectors:
        strong = sectors.get("strong") or []
        if strong:
            for r in strong:
                lines.append(
                    f"- {r.get('name', '?')} ({r.get('ticker', '?')}) "
                    f"{_pct(r.get('change_pct'))}"
                )
        else:
            lines.append("- (조건 충족 ETF 없음)")
    else:
        lines.append(f"- [수집 실패 - {_err_msg(sectors)}]")
    lines.append("")

    # 8. 주도주
    lines.append("### 주도주 (KOSPI 10 + KOSDAQ 7, match 우선 + 거래대금 보충)")
    leading = snapshot.kr_leading if isinstance(snapshot.kr_leading, dict) else {}
    if "error" not in leading:
        for market_key, market_label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
            rows = leading.get(market_key) or []
            if not rows:
                lines.append(f"- {market_label}: (없음)")
                continue
            lines.append(f"- {market_label}:")
            for r in rows:
                tier = r.get("cap_tier", "")
                match = r.get("match", "")
                tag = f"[{tier}·{match}]" if tier else f"[{match}]"
                lines.append(
                    f"  · {r.get('name', '?')} ({r.get('ticker', '?')}) "
                    f"{_pct(r.get('change_pct'))} {tag}"
                )
    else:
        lines.append(f"- [수집 실패 - {_err_msg(leading)}]")

    # ----------------------------------------------------------------------
    # INFRA-SNAPSHOT-EXTEND-001 — 9, 10, 11 신규 섹션 (A·B·C)
    # 빈 데이터는 graceful skip (분석가가 무의미한 "수집 실패" 줄을 보지 않도록).
    # snapshot_extend_failures 가 있으면 마지막에 라벨로만 노출.
    # ----------------------------------------------------------------------
    macro_dict = snapshot.market_macro if isinstance(snapshot.market_macro, dict) else {}
    sector_rs = snapshot.sector_rs if isinstance(snapshot.sector_rs, list) else []
    supply_60d = snapshot.kr_supply_60d if isinstance(snapshot.kr_supply_60d, dict) else {}
    has_extend = bool(macro_dict or sector_rs or supply_60d)

    # 9. 시장 매크로 통계
    if macro_dict:
        lines.append("")
        lines.append("### 시장 매크로 통계 (지수 위계·등락 추세·breadth·Distribution Day)")
        for market_key in ("KOSPI", "KOSDAQ"):
            m = macro_dict.get(market_key)
            if not isinstance(m, dict):
                continue
            lines.append(f"#### {market_key}")
            lines.append(
                f"- 지수 위계: {_num(m.get('index_close'))} "
                f"(36월선 {_num(m.get('ma_36m'))} / 60월선 {_num(m.get('ma_60m'))}) "
                f"— **{m.get('position', '?')}**"
            )
            lines.append(
                f"- 등락 추세: ma20 기울기 {_pct(m.get('ma20_slope_pct_5d'))} (5일) / "
                f"ma60 기울기 {_pct(m.get('ma60_slope_pct_20d'))} (20일) "
                f"— **{m.get('trend', '?')}**"
            )
            adv = m.get("advancing")
            dec = m.get("declining")
            br = m.get("breadth_ratio")
            if adv is not None and dec is not None:
                lines.append(
                    f"- Breadth: 상승 {adv} / 하락 {dec} / 보합 {m.get('unchanged', 0)} · "
                    f"비율 {_num(br, decimals=3) if br is not None else '?'}"
                )
            dd_count = m.get("distribution_count_25d", 0)
            dd_warn = " ⚠ kill switch 임계" if dd_count >= 4 else ""
            lines.append(
                f"- Distribution Day (25일): **{dd_count}**{dd_warn} "
                f"(오늘 발동 {'예' if m.get('is_distribution_day') else '아니오'})"
            )

    # 10. 섹터 RS
    if sector_rs:
        lines.append("")
        lines.append("### 섹터 RS (60일 excess return vs KOSPI, 0~10 점수)")
        for r in sector_rs:
            lines.append(
                f"- {r.get('sector', '?')} ({r.get('etf_ticker', '?')}): "
                f"**{_num(r.get('rs_score'), decimals=2)}** "
                f"(60일 {_pct(r.get('return_60d'))} / KOSPI {_pct(r.get('kospi_return_60d'))} / "
                f"excess {_pct(r.get('rs_ratio'))})"
            )

    # 11. 5주체 수급 60일 누적
    if supply_60d:
        lines.append("")
        lines.append("### 5주체 수급 60일 누적 (백만원, 음수=순매도)")
        for market_key in ("KOSPI", "KOSDAQ"):
            s = supply_60d.get(market_key)
            if not isinstance(s, dict):
                continue
            lines.append(
                f"- {market_key} (실측 {s.get('actual_days', 0)}일): "
                f"외인 {_won_m(s.get('foreign_net_60d'))} / "
                f"기관 {_won_m(s.get('institution_net_60d'))} / "
                f"개인 {_won_m(s.get('individual_net_60d'))} "
                f"(금투 {_won_m(s.get('financial_inv_net_60d'))} / "
                f"연기금 {_won_m(s.get('pension_net_60d'))}) "
                f"— 부호 일치도 **{_num(s.get('agreement_score_60d'), decimals=1)}/10**"
            )

    # 본 분석가 사용 지침 (셋 중 하나라도 발행된 경우에만)
    if has_extend:
        lines.append("")
        lines.append("### 본 분석가 사용 지침 (INFRA-SNAPSHOT-EXTEND-001)")
        lines.append(
            "- **market_state_analyzer**: 9 (지수 위계·추세·breadth·DD) 4축 종합 → 시장 체제 판정. "
            "DD 4+ 시 kill switch 강제 발동."
        )
        lines.append(
            "- **stock_picker**: 10 (섹터 RS) Top 3 = 후보 섹터 + buy_score L (Leader) 축 산출."
        )
        lines.append(
            "- **flow_analyzer**: 11 (5주체 60일) 4축 합 (테마-주체 매칭 0.4 + 60일 모멘텀 0.3 + "
            "자금 유입 속도 0.2 + 부호 일치도 0.1) = F-Score."
        )

    if snapshot.failures:
        lines.append("")
        lines.append(f"_누락 collector: {', '.join(snapshot.failures)}_")

    if snapshot.snapshot_extend_failures:
        lines.append(
            f"_누락 snapshot extend: {', '.join(snapshot.snapshot_extend_failures)}_"
        )

    return "\n".join(lines)
