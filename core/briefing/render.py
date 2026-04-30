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


def _fmt_won_million(million_won: Any) -> str:
    """백만원 단위 정수 → 한국식 표기 (억/조).

    예) 940771 → "+9,408억", 2715000 → "+27.15조", -150000 → "-1,500억"
    """
    if million_won is None:
        return "?"
    try:
        eok = float(million_won) / 100.0  # 100 백만 = 1 억
    except (TypeError, ValueError):
        return "?"
    sign = "+" if eok >= 0 else ""
    if abs(eok) >= 10000:
        return f"{sign}{eok / 10000:,.2f}조"
    return f"{sign}{eok:,.0f}억"


def _fmt_trade_amount(million_won: Any) -> str:
    """거래대금 백만원 정수 → 조 단위 표기."""
    if million_won is None:
        return "?"
    try:
        jo = float(million_won) / 1_000_000.0  # 100만 백만 = 1 조
    except (TypeError, ValueError):
        return "?"
    return f"{jo:,.2f}조"


def render_market_overview(data: dict) -> str:
    """market_briefing 'market_overview' 파트 — KOSPI/KOSDAQ 지수 + 거래대금."""
    indices = data.get("indices") or {}
    fetched_at = data.get("fetched_at") or indices.get("fetched_at") or ""
    # ISO 의 시간 부분만 (예: 2026-04-30T09:30:25+09:00 → 09:30:25)
    time_str = ""
    if fetched_at:
        time_str = fetched_at.split("T", 1)[-1].split("+", 1)[0]

    lines: list[str] = []
    lines.append("📊 시장 개요")
    lines.append(f"출처: KIS API · {time_str} KST" if time_str else "출처: KIS API")
    lines.append("")
    lines.append("🇰🇷 국내 지수")

    for key, label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
        v = indices.get(key) or {}
        if "error" in v:
            lines.append(f"  * {label}: (조회 실패)")
            continue
        lines.append(
            f"  * {label} {_fmt_num(v.get('value'))} "
            f"({_fmt_pct(v.get('change_pct'))}) "
            f"| 거래대금 {_fmt_trade_amount(v.get('trade_amount'))}"
        )

    # KOSPI200 — 코스피 선물의 기초지수
    k200 = indices.get("kospi200") or {}
    if k200 and "error" not in k200:
        lines.append(
            f"  * KOSPI200 (선물 기초) {_fmt_num(k200.get('value'))} "
            f"({_fmt_pct(k200.get('change_pct'))})"
        )

    return "\n".join(lines)


def render_supply_sectors(data: dict) -> str:
    """market_briefing 'supply_sectors' 파트 — 수급 + 강세 섹터."""
    supply = data.get("supply_demand") or {}
    sectors = data.get("sectors") or {}

    lines: list[str] = []
    lines.append("💰 시장 수급 (시장 전체 누적)")
    for key, label in [("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")]:
        s = supply.get(key) or {}
        lines.append("")
        lines.append(f"[{label}]")
        if not s or s.get("no_data") or s.get("error"):
            lines.append("  (수급 데이터 없음)")
            continue
        lines.append(f"  개인   {_fmt_won_million(s.get('individual_net_amount_m'))}")
        lines.append(f"  외인   {_fmt_won_million(s.get('foreign_net_amount_m'))}")
        lines.append(f"  기관   {_fmt_won_million(s.get('institution_net_amount_m'))}")
        lines.append(f"  금융투자 {_fmt_won_million(s.get('fin_invest_net_amount_m'))}")
        lines.append(f"  연기금  {_fmt_won_million(s.get('pension_net_amount_m'))}")

    # 선물 수급 (KOSPI200 선물, KRX backend, 3주체)
    futures = data.get("futures_supply_demand") or {}
    if futures and not futures.get("error"):
        ind_b = futures.get("individual_net_amount_b")
        frgn_b = futures.get("foreign_net_amount_b")
        org_b = futures.get("institution_net_amount_b")
        if ind_b is not None or frgn_b is not None or org_b is not None:
            # 십억원 → 백만원 환산 (1 십억 = 1,000 백만) 후 기존 helper 사용
            def _b(v: int | None) -> str:
                return _fmt_won_million((v or 0) * 1000)
            lines.append("")
            lines.append("[KOSPI200 선물]")
            lines.append(f"  개인   {_b(ind_b)}")
            lines.append(f"  외인   {_b(frgn_b)}")
            lines.append(f"  기관   {_b(org_b)}")

    # 용어 안내 — 기관은 합계, 그 안에 금융투자/투신/보험/연기금/기타 포함
    lines.append("")
    lines.append("※ 기관=금융투자+투신+보험+연기금+기타 합계 · 금융투자=증권사 자기매매")

    # 강세 섹터: 조건 충족 (≥threshold%) 우선 + 그 외 등락률 순으로 10개까지 채움.
    # 주도주 표시 패턴 일치 (🔥 = 조건 충족 / · = 등락률순 채움).
    lines.append("")
    all_sectors = sectors.get("all") or []  # 이미 등락률 내림차순 정렬됨
    strong = sectors.get("strong") or []
    threshold = sectors.get("min_change_pct", 1.0)
    total = len(all_sectors)

    strong_tickers = {e.get("ticker") for e in strong}
    rest = [e for e in all_sectors if e.get("ticker") not in strong_tickers]
    combined = strong + rest
    top_n = combined[:10]

    lines.append(
        f"📊 강세 섹터 (조건 ≥{threshold:g}% 우선 + 등락률 순으로 채움)"
    )
    if not top_n:
        lines.append("  (추적 ETF 없음)")
    else:
        for etf in top_n:
            is_strong = etf.get("ticker") in strong_tickers
            icon = "⭐" if is_strong else "·"
            name = etf.get("name") or etf.get("ticker", "?")
            tag = "조건충족" if is_strong else "등락률순"
            lines.append(
                f"  {icon} {name:<22} {_fmt_pct(etf.get('change_pct'))}  ({tag})"
            )
        lines.append(
            f"  (총 {total}개 추적, 조건 충족 {len(strong)}개)"
        )

    return "\n".join(lines)


def _render_stock_row(r: dict, tag: str) -> str:
    icon = "🔥" if r.get("match") == "meets_criteria" else "·"
    final_tag = tag if r.get("match") == "meets_criteria" else "거래대금"
    name = r.get("name") or r.get("ticker", "?")
    return f"  {icon} {name:<14} {_fmt_pct(r.get('change_pct'))}  ({final_tag})"


def render_leading_stocks(data: dict) -> str:
    """market_briefing 'leading_stocks' 파트 — KOSPI/KOSDAQ 주도주.

    KOSPI 는 시총20위 (대형주) / 시총20위 외 (중소형) 으로 별도 그룹 표시.
    대형주는 변동 적은 우량주가 위쪽을 차지해 진짜 주도주(중소형 강세) 가
    묻히는 것을 방지.
    """
    leading = data.get("leading_stocks") or {}
    kospi = leading.get("kospi") or []
    kosdaq = leading.get("kosdaq") or []

    # KOSPI 분할: 대형주 (top20) vs 중소형 (mid_small)
    kospi_top20 = [r for r in kospi if r.get("cap_tier") == "top20"]
    kospi_mid = [r for r in kospi if r.get("cap_tier") != "top20"]

    def _split_count(rows: list[dict]) -> tuple[int, int]:
        matched = sum(1 for r in rows if r.get("match") == "meets_criteria")
        return matched, len(rows) - matched

    lines: list[str] = []
    lines.append("🚀 주도주")

    # KOSPI 대형주
    lines.append("")
    matched, fill = _split_count(kospi_top20)
    lines.append(
        f"[KOSPI 대형주 (시총20위)] 조건충족 {matched} / 거래대금채움 {fill}"
    )
    if not kospi_top20:
        lines.append("  (해당 종목 없음)")
    else:
        for r in kospi_top20:
            lines.append(_render_stock_row(r, "top20+2%"))

    # KOSPI 중소형
    lines.append("")
    matched, fill = _split_count(kospi_mid)
    lines.append(
        f"[KOSPI 중소형 (시총20위 외)] 조건충족 {matched} / 거래대금채움 {fill}"
    )
    if not kospi_mid:
        lines.append("  (거래대금 상위 30 풀에 미포함 — 강세 중소형은 별도 등락률 API 필요)")
    else:
        for r in kospi_mid:
            lines.append(_render_stock_row(r, "외부+5%"))

    # KOSDAQ
    lines.append("")
    matched, fill = _split_count(kosdaq)
    lines.append(
        f"[KOSDAQ] 조건충족 {matched} / 거래대금채움 {fill}"
    )
    if not kosdaq:
        lines.append("  (해당 종목 없음)")
    else:
        for r in kosdaq:
            lines.append(_render_stock_row(r, "5%+"))

    lines.append("")
    lines.append("선별 조건 (거래대금 상위 30 종목 풀에서 추출):")
    lines.append("  · KOSPI 대형주 (시총20위): 등락률 ≥ 2%")
    lines.append("  · KOSPI 중소형 (시총20위 외): 등락률 ≥ 5%")
    lines.append("  · KOSDAQ: 등락률 ≥ 5%")
    lines.append("  · 조건 충족 우선, 부족 시 거래대금 상위로 채움")
    lines.append("  🔥 조건 충족 / · 거래대금 순")

    return "\n".join(lines)


_MARKET_BRIEFING_RENDERERS = {
    "market_overview": render_market_overview,
    "supply_sectors": render_supply_sectors,
    "leading_stocks": render_leading_stocks,
}


def render_market_briefing(
    parts: list[BriefingPart],
    status: BriefingStatus = "ok",
) -> list[str]:
    """market_briefing 브리핑 전체 → 3분할 텍스트 리스트 (order 순).

    LLM 호출이 없으므로 status 는 항상 "ok" 가정 (시그니처 호환 위해 받음).
    봇 핸들러가 BriefingResponse.note 를 별도로 처리해 prefix 부착.
    """
    out: list[str] = []
    for p in sorted(parts, key=lambda x: x.order):
        renderer = _MARKET_BRIEFING_RENDERERS.get(p.key)
        if renderer is None:
            continue
        out.append(renderer(p.data))
    return out
