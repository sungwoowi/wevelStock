"""뉴스 일일 적재 job (NEWS-SOURCE-001 후속 SLOT "일일 cron").

평일 18:05 KST 일일 허브(run_daily_refresh)의 뉴스 단계. 그동안 뉴스 적재
(fetch→classify→digest)는 함수만 있고 cron 에 미등록이었다 → 본 job 으로 합류.

흐름:
  1. collect_from_sources([RssNewsSource()]) — 자동수집 RSS fetch (url dedup, 어댑터 graceful)
  2. upsert_news_items() — news_source_items url 멱등 적재 (raw 내구성 먼저)
  3. universe/name_code_map 구성 — 거래대금 상위(KIS) + 하드코딩 KR_NAME_TO_TICKER 병합.
  4. classify_news_items(name_code_map=) — LLM 라벨 + affected_refs 캐노니컬화(종목명→코드).
  5. upsert_news_items() — 라벨 재적재
  6. build_news_digest 다중 scope — market + universe 종목 N + 14섹터 결정론 집계(멱등).
     결정론이라 추가 LLM 비용 0. 각 scope 독립 격리.

멱등: url PK(news_source_items) / (scope,date) PK(news_digest_snapshot) → 하루 여러 번 안전.
graceful: 외부 호출(RSS/Gemini/KIS) 실패가 전체를 막지 않도록 단계별 격리. snapshot_macro 패턴 mirror.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")


def _today_kst_str() -> str:
    """us_macro._today_kst_str mirror — 적재 날짜는 KST 기준."""
    return datetime.now(_KST).strftime("%Y-%m-%d")


async def _build_universe_and_name_map() -> tuple[list[str], dict[str, str]]:
    """거래대금 상위(KIS) + 하드코딩 매핑 → (universe ticker 목록, {종목명: 6자리코드}).

    KIS 1콜 묶음(fetch_kr_leading_stocks)으로 종목 scope 루프용 ticker 와
    affected_refs 캐노니컬화용 name→code 맵을 함께 만든다. top-50 밖 일상 종목은
    KR_NAME_TO_TICKER(~30종)로 보강(live 우선, setdefault). KIS 실패 시 호출부가 격리.
    """
    from collectors.kr_leading_stocks import fetch_kr_leading_stocks
    from collectors.screening import get_universe_limits
    from core.inference.run_analyst import KR_NAME_TO_TICKER

    kospi_limit, kosdaq_limit = get_universe_limits()
    leading = await fetch_kr_leading_stocks(kospi_limit=kospi_limit, kosdaq_limit=kosdaq_limit)

    tickers: list[str] = []
    name_map: dict[str, str] = {}
    for grp in ("kospi", "kosdaq"):
        for it in leading.get(grp, []):
            t = (it.get("ticker") or "").strip()
            nm = (it.get("name") or "").strip()
            if t:
                tickers.append(t)
                if nm:
                    name_map[nm] = t
    tickers = [t for t in dict.fromkeys(tickers) if t]
    # 거래대금 상위 밖 일상 종목 보강 (live 우선 — 미존재 키만 채움)
    for nm, code in KR_NAME_TO_TICKER.items():
        name_map.setdefault(nm, code)
    return tickers, name_map


def _interpretation_market_context(date: str) -> str | None:
    """해석 4축 ⑷(시장 실반응·파동 정합) 재료 — 결정론 실측 md (LLM 0, graceful).

    market_view 스냅샷(regime·entry_posture·미장 risk 토큰·지수 반응 흡수)을 재사용.
    오늘 없으면 최근 3일 lookback(주말·장전 커버) + 시점 표기. 전부 없으면 None
    (프롬프트가 '판단 불가' 지시로 처리).
    """
    from datetime import timedelta

    from collectors.market_view import get_today_view, render_market_view_md

    try:
        base = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return None
    for back in range(0, 4):
        day = (base - timedelta(days=back)).strftime("%Y-%m-%d")
        try:
            view = get_today_view(day, "KOSPI")
        except Exception as e:  # noqa: BLE001 — 컨텍스트 부재가 해석을 막지 않음
            log.warning("interpretation_context_failed", date=day, error=str(e))
            return None
        if view is not None:
            md = render_market_view_md(view)
            if back > 0:
                md = f"(주의: {back}일 전 {day} 스냅샷 — 최신 아님)\n{md}"
            return md
    return None


async def run_news_ingest(date: str | None = None) -> dict[str, Any]:
    """뉴스 일일 적재 entrypoint. 일일 허브가 호출.

    Args:
        date: 집계 대상 KST 날짜('YYYY-MM-DD'). None 시 오늘(KST).

    Returns:
        {
          "date": str,
          "collected": int,        # RSS 수집 건수
          "classified": int,       # LLM 라벨 성공 건수
          "digest": {"tone": ..., "source": ..., "themes": int} 또는 {"error": ...},  # market scope (하위호환)
          "scopes_persisted": int, # 영속된 scope 수 (market + 종목 + 섹터)
          "scopes_failed": int,    # 격리된 scope 실패 수
          "elapsed_s": float,
          "failures": [{"stage": ..., "error": ...}],
        }
    """
    from collectors.kr_sectors import DEFAULT_TRACKED_ETFS
    from collectors.news_source import (
        RssNewsSource,
        backfill_unlabeled_news,
        build_news_digest,
        classify_news_items,
        collect_from_sources,
        digest_persist_empty_scopes,
        digest_scope_universe_limit,
        interpret_elevated_events,
        upsert_news_digest,
        upsert_news_items,
    )

    target_date = date or _today_kst_str()
    started = time.monotonic()
    log.info("news_ingest_start", date=target_date)

    failures: list[dict[str, str]] = []
    collected = 0
    classified = 0
    digest_result: dict[str, Any] = {}

    # 1~2단계: 수집 + raw 내구성 적재
    items: list[Any] = []
    try:
        items = await collect_from_sources([RssNewsSource()])
        collected = len(items)
        upsert_news_items(items)
        log.info("news_ingest_collected", count=collected)
    except Exception as e:  # noqa: BLE001
        log.exception("news_ingest_collect_failed", error=str(e))
        failures.append({"stage": "collect", "error": str(e)})

    # 3단계: universe + name_code_map 구성 (KIS, 격리). 실패해도 market scope 는 진행.
    universe_tickers: list[str] = []
    name_code_map: dict[str, str] = {}
    try:
        universe_tickers, name_code_map = await _build_universe_and_name_map()
        log.info("news_ingest_universe", tickers=len(universe_tickers), names=len(name_code_map))
    except Exception as e:  # noqa: BLE001
        log.warning("news_ingest_universe_failed", error=str(e))
        failures.append({"stage": "universe", "error": str(e)})

    # 4단계: LLM 분류 + affected_refs 캐노니컬화 + 라벨 재적재. 수집분이 있을 때만.
    if items:
        try:
            classified_items = await classify_news_items(items, name_code_map=name_code_map)
            classified = sum(1 for it in classified_items if it.labeled_by == "llm")
            upsert_news_items(classified_items)
            log.info("news_ingest_classified", labeled=classified, total=len(classified_items))
        except Exception as e:  # noqa: BLE001
            log.exception("news_ingest_classify_failed", error=str(e))
            failures.append({"stage": "classify", "error": str(e)})

    # 4.5단계: 미라벨링 백필 (AUTO-SIGNAL-INTEGRITY-001 T0-d) — 과거 classify 실패분 재시도.
    # 오늘 수집분의 실패도 포함되나 limit 로 유계·캐시 멱등. 잔량은 로그로 관측 가능.
    backfilled = 0
    try:
        bf = await backfill_unlabeled_news(name_code_map=name_code_map)
        backfilled = bf.get("labeled", 0)
        if bf.get("candidates"):
            log.info("news_ingest_backfill", **bf)
    except Exception as e:  # noqa: BLE001
        log.warning("news_ingest_backfill_failed", error=str(e))
        failures.append({"stage": "backfill", "error": str(e)})

    # 5단계: 다중 scope 결정론 집계 (market + 종목 N + 14섹터). 분류 실패해도 적재분으로 집계.
    # 결정론이라 추가 LLM 비용 0. 각 scope 독립 격리 — 하나 실패가 나머지를 막지 않음.
    limit = digest_scope_universe_limit()
    persist_empty = digest_persist_empty_scopes()
    scopes: list[tuple[str, str | None, str | None]] = [("market", None, None)]
    scopes += [(f"ticker:{t}", t, None) for t in universe_tickers[:limit]]
    scopes += [(f"sector:{name}", None, name) for _, name in DEFAULT_TRACKED_ETFS]

    scopes_persisted = 0
    scopes_failed = 0
    market_digest_obj: Any | None = None
    for scope_label, tk, sec in scopes:
        try:
            digest = build_news_digest(target_date, ticker=tk, sector=sec, persist=False)
            # market 은 항상 영속(다운스트림 의존). 종목/섹터는 토글에 따라 빈 scope 스킵.
            if scope_label == "market" or persist_empty or digest.source != "empty":
                upsert_news_digest(digest)
                scopes_persisted += 1
            if scope_label == "market":
                market_digest_obj = digest
                digest_result = {
                    "tone": digest.tone,
                    "source": digest.source,
                    "themes": len(digest.top_themes),
                }
        except Exception as e:  # noqa: BLE001
            log.warning("news_ingest_digest_scope_failed", scope=scope_label, error=str(e))
            failures.append({"stage": f"digest:{scope_label}", "error": str(e)})
            scopes_failed += 1
    if not digest_result:
        digest_result = {"error": "market_scope_failed"}
    log.info(
        "news_ingest_digest_done",
        scopes_persisted=scopes_persisted,
        scopes_failed=scopes_failed,
    )

    # 5.5단계: 격상 이벤트 LLM 해석 (NEWS-EVENT-INTERPRETATION-001 M1-b, market 전용).
    # 격상 감지는 5단계 build_news_digest 가 결정론으로 끝냄 — 여기선 미해석분만 LLM
    # (일 0~2건 상한, 캐시 멱등 → 06:40 장전·18:05 장후 하루 2회 돌아도 재해석은 기사
    # 집합이 늘었을 때뿐). 해석 attach 후 재영속. 실패는 격리 (advisory 층이라 비치명).
    elevated_events = list(getattr(market_digest_obj, "elevated_events", None) or [])
    interpreted = 0
    if elevated_events:
        try:
            pending = [e for e in elevated_events if e.get("interpretation") is None]
            if pending:
                ctx_md = _interpretation_market_context(target_date)
                await interpret_elevated_events(
                    elevated_events, date=target_date, market_context_md=ctx_md
                )
                upsert_news_digest(market_digest_obj)
            interpreted = sum(
                1 for e in elevated_events if e.get("interpretation") is not None
            )
            log.info(
                "news_ingest_interpreted",
                elevated=len(elevated_events), interpreted=interpreted,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("news_ingest_interpret_failed", error=str(e))
            failures.append({"stage": "interpret", "error": str(e)})
    if isinstance(digest_result, dict) and "error" not in digest_result:
        digest_result["elevated"] = len(elevated_events)
        digest_result["interpreted"] = interpreted

    elapsed = time.monotonic() - started
    log.info(
        "news_ingest_done",
        date=target_date,
        collected=collected,
        classified=classified,
        scopes_persisted=scopes_persisted,
        elapsed_s=round(elapsed, 2),
        failures=len(failures),
    )
    return {
        "date": target_date,
        "collected": collected,
        "classified": classified,
        "backfilled": backfilled,
        "digest": digest_result,
        "scopes_persisted": scopes_persisted,
        "scopes_failed": scopes_failed,
        "elapsed_s": round(elapsed, 2),
        "failures": failures,
    }
