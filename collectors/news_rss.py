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

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at,
        }


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


async def fetch_news(
    *,
    queries: list[str] | None = None,
    limit_per_source: int = 15,
) -> list[dict]:
    """Fetch news from multiple sources in parallel.

    queries: Google News search terms. Defaults to a curated list
             focused on US markets + KR-relevant themes.
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
    return [it.to_dict() for it in merged]
