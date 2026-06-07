"""News RSS collectors — title + url + published only, no article body.

Sources:
  - Yahoo Finance RSS     : https://finance.yahoo.com/news/rssindex
  - CNBC Markets RSS      : https://www.cnbc.com/id/15839069/device/rss/rss.html
  - Google News RSS       : https://news.google.com/rss/search?q=<query>

The LLM will decide impact magnitude/direction in the analyze stage.
We only normalize into NewsItem.
"""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import quote_plus

import httpx

from core.logging import get_logger

log = get_logger(__name__)

YAHOO_URL = "https://finance.yahoo.com/news/rssindex"
CNBC_MARKETS_URL = "https://www.cnbc.com/id/15839069/device/rss/rss.html"


def _google_news_rss(query: str) -> str:
    return (
        f"https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )


@dataclass
class NewsItem:
    title: str
    url: str
    source: str
    published_at: str | None = None
    # --- NEWS-SOURCE-001 라벨 (전부 Optional — 브리핑 collect_news 는 라벨 없이 동작) ---
    body: str | None = None  # 본문/유튜브 요약 (ManualNewsSource). RSS 는 제목만 → None
    category: str | None = None  # macro_policy|industry_trend|geopolitics|policy_political|corporate_events|market_sentiment
    time_axis: str | None = None  # ephemeral_shock|short_theme|structural_trend
    direction: str | None = None  # up|neutral|down
    magnitude: int | None = None  # 1|2|3
    confidence: int | None = None  # 0~100
    affected_scope: str | None = None  # market|sector|ticker
    affected_refs: list[str] = field(default_factory=list)
    labeled_by: str | None = None  # llm|manual|rss_raw
    collected_at: str | None = None  # ISO8601 (UTC) — 수집 시각

    def to_dict(self) -> dict:
        """브리핑 collect_news 하위호환 — 기존 4 키 그대로 (동작 불변)."""
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at,
        }

    def to_record(self) -> dict:
        """라벨 포함 전체 직렬화 (news_items DB / JSON round-trip). `affected` 는 계약대로 중첩."""
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at,
            "body": self.body,
            "category": self.category,
            "time_axis": self.time_axis,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "confidence": self.confidence,
            "affected": {"scope": self.affected_scope, "refs": list(self.affected_refs)},
            "labeled_by": self.labeled_by,
            "collected_at": self.collected_at,
        }

    @classmethod
    def from_record(cls, d: dict) -> "NewsItem":
        """to_record() 역직렬화. 중첩 `affected` 와 평면 affected_* 둘 다 수용."""
        affected = d.get("affected") or {}
        return cls(
            title=d["title"],
            url=d["url"],
            source=d.get("source", ""),
            published_at=d.get("published_at"),
            body=d.get("body"),
            category=d.get("category"),
            time_axis=d.get("time_axis"),
            direction=d.get("direction"),
            magnitude=d.get("magnitude"),
            confidence=d.get("confidence"),
            affected_scope=d.get("affected_scope") or affected.get("scope"),
            affected_refs=list(d.get("affected_refs") or affected.get("refs") or []),
            labeled_by=d.get("labeled_by"),
            collected_at=d.get("collected_at"),
        )


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_rss(xml_text: str, source: str) -> list[NewsItem]:
    """Parse an RSS 2.0 feed into NewsItem list.

    Returns empty list on malformed XML.
    """
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.warning("rss_parse_error", source=source, error=str(e))
        return items

    # RSS 2.0: rss > channel > item
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")
        if title_el is None or link_el is None:
            continue
        title = _strip_html(title_el.text or "")
        url = (link_el.text or "").strip()
        if not title or not url:
            continue
        items.append(
            NewsItem(
                title=title,
                url=url,
                source=source,
                published_at=(pub_el.text.strip() if (pub_el is not None and pub_el.text) else None),
            )
        )
    return items


async def _fetch_feed(url: str, source: str, limit: int = 20) -> list[NewsItem]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (wevelStock)"})
            if resp.status_code != 200:
                log.warning("rss_non200", source=source, status=resp.status_code)
                return []
            items = _parse_rss(resp.text, source)
            return items[:limit]
    except Exception as e:  # noqa: BLE001
        log.warning("rss_fetch_failed", source=source, error=str(e))
        return []


async def fetch_news_items(
    *,
    queries: list[str] | None = None,
    limit_per_source: int = 15,
) -> list[NewsItem]:
    """Fetch news from multiple sources in parallel → list[NewsItem].

    queries: Google News search terms. Defaults to a curated list
             focused on US markets + KR-relevant themes.

    RssNewsSource (NEWS-SOURCE-001) 가 이 함수를 래핑한다. 브리핑 collect_news 는
    하위호환을 위해 dict 를 반환하는 fetch_news() 를 계속 쓴다.
    """
    if queries is None:
        queries = [
            "Federal Reserve rate",
            "semiconductor chip",
            "Korea stocks Samsung",
            "AI tech stocks",
        ]

    tasks = [
        _fetch_feed(YAHOO_URL, "Yahoo", limit_per_source),
        _fetch_feed(CNBC_MARKETS_URL, "CNBC", limit_per_source),
    ]
    for q in queries:
        tasks.append(_fetch_feed(_google_news_rss(q), "GoogleNews", 5))

    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Dedupe by URL preserving order (earliest source wins)
    seen: set[str] = set()
    merged: list[NewsItem] = []
    for batch in results:
        for item in batch:
            if item.url in seen:
                continue
            seen.add(item.url)
            merged.append(item)

    log.info("news_collected", total=len(merged), sources=len(tasks))
    return merged


async def fetch_news(
    *,
    queries: list[str] | None = None,
    limit_per_source: int = 15,
) -> list[dict]:
    """브리핑 collect_news 하위호환 — fetch_news_items() 를 dict 로 변환 (동작 불변)."""
    items = await fetch_news_items(queries=queries, limit_per_source=limit_per_source)
    return [it.to_dict() for it in items]
