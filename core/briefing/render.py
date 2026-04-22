"""브리핑 파트 렌더러.

파이프라인별 JSON 데이터 → 텔레그램/웹앱 공용 텍스트.
`render_<pipeline_id>()` 함수를 추가하는 방식으로 파이프라인 확장.
"""
from __future__ import annotations

from typing import Any

from core.contracts.briefing_part import BriefingPart, BriefingStatus

IMPACT_ICON = {"bullish": "⬆️", "bearish": "⬇️", "neutral": "➡️"}

VERDICT_ICON = {
    "HOLD": "▫",
    "BUY_ADD": "🟢",
    "SELL_PART": "🟡",
    "SELL_ALL": "🔴",
}

DEGRADED_PREFIX = "⚠️ 일시적 LLM 장애 — mock 응답입니다\n\n"


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "?"


def _fmt_num(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return "?"


def render_overnight(data: dict) -> str:
    """morning_pre 'overnight' 파트 — 간밤 미국/거시/야간선물."""
    overnight_us = data.get("overnight_us") or {}
    macro = data.get("macro") or {}
    night_futures = data.get("night_futures") or {}

    lines: list[str] = []
    lines.append("🌙 간밤 시황")
    lines.append("")
    lines.append("🇺🇸 미국 지수")
    for key, label in [
        ("nasdaq", "나스닥"),
        ("sp500", "S&P500"),
        ("sox", "SOX (반도체)"),
        ("vix", "VIX (변동성 지수)"),
    ]:
        v = overnight_us.get(key) or {}
        if "error" not in v:
            lines.append(
                f"  * {label} {_fmt_num(v.get('price'))} "
                f"({_fmt_pct(v.get('change_pct'))})"
            )

    fg = overnight_us.get("fear_greed") or {}
    if fg and "error" not in fg and fg.get("score") is not None:
        pct = fg.get("change_pct")
        delta = f" ({_fmt_pct(pct)})" if pct is not None else ""
        lines.append(
            f"  * 공포·탐욕 지수 {fg['score']} "
            f"[{fg.get('rating_kr') or fg.get('rating')}]{delta}"
        )

    if macro:
        lines.append("")
        lines.append("🌐 거시경제 지표")
        for key, label in [
            ("dxy", "💵 (달러인덱스)"),
            ("usdkrw", "🇰🇷 (원달러환율)"),
            ("us_10y", "美10Y (10년 국채금리)"),
            ("gold", "🥇 (국제금시세)"),
            ("wti", "WTI (서부 텍사스산 원유 선물)"),
        ]:
            v = macro.get(key) or {}
            if "error" not in v:
                lines.append(
                    f"  * {label} {_fmt_num(v.get('price'))} "
                    f"({_fmt_pct(v.get('change_pct'))})"
                )

    nf = (night_futures or {}).get("kospi200_cme_night") or {}
    if nf and "error" not in nf:
        lines.append("")
        lines.append(
            f"🔮 KOSPI200 야간선물 {_fmt_pct(nf.get('change_pct'))} "
            f"(source: {nf.get('source', '?')})"
        )

    return "\n".join(lines)


def render_scenario(data: dict) -> str:
    """morning_pre 'scenario' 파트 — 오늘 시나리오 + 핵심 뉴스 Top 5."""
    scenario = data.get("scenario") or {}
    news_impact = data.get("news_impact") or []
    news_items = data.get("news_items") or []

    lines: list[str] = []
    lines.append("📈 오늘 시나리오")
    if scenario:
        expected = scenario.get("expected_open", "?")
        bias = scenario.get("bias", "?")
        conf = scenario.get("confidence", "?")
        lines.append(f"  예상 개장: {expected}  |  바이어스: {bias}  |  신뢰 {conf}")
        narrative = (scenario.get("narrative") or "").strip()
        if narrative:
            lines.append("")
            lines.append(narrative[:600])

    by_url = {e.get("url"): e for e in news_impact if e.get("url")}
    lines.append("")
    lines.append("📰 핵심 뉴스")
    top = news_items[:5]
    if not top:
        lines.append("  (뉴스 수집 실패)")
    for i, it in enumerate(top, 1):
        url = it.get("url")
        title = it.get("title", "(제목 없음)")
        imp = by_url.get(url, {})
        icon = IMPACT_ICON.get(imp.get("impact_direction"), "•")
        mag = imp.get("impact_magnitude")
        note = imp.get("impact_note")
        mag_str = f" [{mag}]" if mag else ""
        lines.append(f"{i}. {icon}{mag_str} {title[:80]}")
        if note:
            lines.append(f"   └ {note[:100]}")
        lines.append(f"   🔗 {url}")

    return "\n".join(lines)


def render_positions(data: dict) -> str:
    """morning_pre 'positions' 파트 — 보유/관심 + 신규 후보 + 7계명 체크."""
    positions_advice = data.get("positions_advice") or []
    new_candidates = data.get("new_candidates") or []
    principles = data.get("principles") or {}

    lines: list[str] = []
    lines.append("💼 보유/관심 의견")
    if not positions_advice:
        lines.append("  (보유/관심 종목 없음 — DB에 수동 등록 필요)")
    else:
        for p in positions_advice:
            verdict = str(p.get("verdict", "HOLD")).upper()
            icon = VERDICT_ICON.get(verdict, "•")
            name = p.get("name") or p.get("ticker", "?")
            ticker = p.get("ticker", "")
            reason = p.get("reason", "")
            lines.append(f"  {icon} {name} ({ticker}) — {verdict}")
            if reason:
                lines.append(f"     {reason[:120]}")

    lines.append("")
    lines.append("✨ 신규 매수 후보")
    if not new_candidates:
        lines.append("  (오늘은 신규 후보 없음)")
    else:
        for c in new_candidates[:3]:
            sector = c.get("sector") or "?"
            name = c.get("name") or c.get("ticker", "?")
            reason = c.get("reason", "")
            lines.append(f"  • [{sector}] {name} — {reason[:80]}")

    lines.append("")
    violations = principles.get("violations") or []
    warnings = principles.get("warnings") or []
    if violations:
        lines.append(f"⚠️ 7계명 위반 {len(violations)}건")
        for v in violations[:3]:
            lines.append(f"  - [계명 {v.get('commandment')}] {v.get('title')}")
    elif warnings:
        lines.append(f"🔸 7계명 경고 {len(warnings)}건")
    else:
        lines.append("✅ 7계명 체크: 위반 없음")

    return "\n".join(lines)


_MORNING_PRE_RENDERERS = {
    "overnight": render_overnight,
    "scenario": render_scenario,
    "positions": render_positions,
}


def render_morning_pre(
    parts: list[BriefingPart],
    status: BriefingStatus = "ok",
) -> list[str]:
    """morning_pre 브리핑 전체 → 3분할 텍스트 리스트 (order 순).

    `status == "degraded"` 인 경우 각 메시지 앞에 mock 경고 prefix 추가.
    """
    out: list[str] = []
    for p in sorted(parts, key=lambda x: x.order):
        renderer = _MORNING_PRE_RENDERERS.get(p.key)
        if renderer is None:
            continue
        text = renderer(p.data)
        if status == "degraded":
            text = DEGRADED_PREFIX + text
        out.append(text)
    return out
