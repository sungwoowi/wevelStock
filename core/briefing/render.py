"""브리핑 파트 렌더러.

파이프라인별 JSON 데이터 → 텔레그램/웹앱 공용 텍스트.
`render_<pipeline_id>()` 함수를 추가하는 방식으로 파이프라인 확장.
"""
from __future__ import annotations

from typing import Any

from core.contracts.briefing_part import BriefingPart, BriefingStatus

import html

IMPACT_ICON = {"bullish": "⬆️", "bearish": "⬇️", "neutral": "➡️"}

VERDICT_ICON = {
    # HOLD ▫(회색 소형)는 다크 배경에서 안 보임 (2026-07-07 사용자) — 색 원 계열로 통일.
    "HOLD": "🔵",
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
    lines.append("🇺🇸 미국 지수  (괄호 = 전일 종가 대비)")
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

    # 미국 야간선물 (현물 지수 마감 후 흐름 — '선물' 명시로 위 현물과 구분).
    fut_bits: list[str] = []
    for key, label in [("nq_futures", "나스닥100선물"), ("es_futures", "S&P500선물")]:
        fv = overnight_us.get(key) or {}
        if "error" not in fv and fv.get("change_pct") is not None:
            fut_bits.append(f"{label} {_fmt_pct(fv.get('change_pct'))}")
    if fut_bits:
        lines.append("  * 🌃 야간선물 " + " · ".join(fut_bits))

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
        lines.append("🌐 거시경제 지표  (괄호 = 전일 종가 대비)")
        for key, label in [
            ("dxy", "💵 (달러인덱스)"),
            ("usdkrw", "🇰🇷 (원달러환율)"),
            ("us_10y", "美10Y (10년 국채금리)"),
            ("gold", "🥇 (국제금시세)"),
            ("wti", "WTI (서부 텍사스산 원유 선물)"),
            ("brent", "브렌트유 (북해산 원유 선물)"),
        ]:
            v = macro.get(key) or {}
            if "error" not in v:
                lines.append(
                    f"  * {label} {_fmt_num(v.get('price'))} "
                    f"({_fmt_pct(v.get('change_pct'))})"
                )

    nf = (night_futures or {}).get("kospi200_cme_night") or {}
    if nf and "error" not in nf:
        # source_kr 로 실선물/CME/EWY 대용 명시 — EWY 대용을 진짜 야간선물로 오인 방지.
        src_kr = nf.get("source_kr") or nf.get("source", "?")
        lines.append("")
        lines.append(
            f"🔮 KOSPI200 야간선물 {_fmt_pct(nf.get('change_pct'))} ({src_kr})"
        )

    return "\n".join(lines)


# 노출 단 코드 라벨 금지 — expected_open/bias 영문 enum 을 한국어로 (미매핑 값은 원문 유지).
_EXPECTED_OPEN_KR = {
    "gap_up_big": "큰 갭 상승",
    "gap_up_small": "소폭 갭 상승",
    "flat": "보합",
    "gap_down_small": "소폭 갭 하락",
    "gap_down_big": "큰 갭 하락",
}
_BIAS_KR = {
    "bullish": "강세",
    "neutral_positive": "중립(우호)",
    "neutral": "중립",
    "neutral_negative": "중립(경계)",
    "bearish": "약세",
}


def _clip_sentence(text: str, limit: int) -> str:
    """limit 근처의 **문장 경계**에서 클립 — 중간 뚝 끊김("…미칠 것으로") 방지.

    limit 안에 마지막 문장 끝('다.' 등 마침표)이 있으면 거기까지, 없으면 limit 에서
    자르고 말줄임(…) 표기. 짧은 텍스트는 그대로 (2026-07-07 사용자 제보 수리).
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind("다. "), head.rfind("다.\n"), head.rfind(". "))
    if head.endswith("다.") or head.endswith("."):
        cut = len(head) - 2
    if cut >= int(limit * 0.4):  # 문장 끝이 너무 앞이면(정보 손실 과다) 말줄임으로
        return text[: cut + 2].rstrip()
    return head.rstrip() + "…"


def _render_horizon_view(icon: str, label: str, view: dict) -> list[str]:
    """단기/장기 관점 블록 — 스탠스 라벨 + 실전 대응 guidance."""
    stance = (view.get("stance") or "").strip()
    guidance = (view.get("guidance") or "").strip()
    if not (stance or guidance):
        return []
    lines = ["", f"{icon} {label} — 스탠스: {stance or '?'}"]
    if guidance:
        lines.append(f"  {guidance[:400]}")
    return lines


def render_scenario(data: dict) -> str:
    """morning_pre 'scenario' 파트 — 오늘 시나리오 + 단기/장기 실전 관점 + 핵심 뉴스 Top 5."""
    scenario = data.get("scenario") or {}
    news_impact = data.get("news_impact") or []
    news_items = data.get("news_items") or []

    lines: list[str] = []
    lines.append("📈 오늘 시나리오")
    if scenario:
        expected = scenario.get("expected_open", "?")
        bias = scenario.get("bias", "?")
        conf = scenario.get("confidence", "?")
        expected_kr = _EXPECTED_OPEN_KR.get(expected, expected)
        bias_kr = _BIAS_KR.get(bias, bias)
        lines.append(f"  예상 개장: {expected_kr}  |  바이어스: {bias_kr}  |  신뢰 {conf}")
        narrative = (scenario.get("narrative") or "").strip()
        if narrative:
            lines.append("")
            lines.append(narrative[:600])
        # 단기/장기 관점 분리 (2026-07-06 사용자 요청) — "홀딩할지 매도할지 매수할지"
        # 판단에 직결. 당장 행동(단기) → 큰 그림(장기) 순. 구버전 응답은 블록 생략(graceful).
        lines.extend(_render_horizon_view("⚡", "단기 (1~2주)", scenario.get("short_term") or {}))
        lines.extend(_render_horizon_view("🌊", "장기 (1개월+)", scenario.get("long_term") or {}))

    by_url = {e.get("url"): e for e in news_impact if e.get("url")}
    lines.append("")
    # 기호 범례 — 받는 사람이 설명 없이 읽게 + 파급=느낌표(소 무표시·중 ❗·대 ‼️),
    # 제목=한국어 헤드라인+링크 임베드 (2026-07-07 사용자 시안 선택: 종목당 3줄→2줄).
    lines.append("📰 핵심 뉴스  (⬆️호재 ⬇️악재 ➡️중립 · ❗파급중 ‼️파급대)")
    top = news_items[:5]
    if not top:
        lines.append("  (뉴스 수집 실패)")
    mag_icon = {2: "❗", 3: "‼️"}
    for i, it in enumerate(top, 1):
        url = it.get("url")
        title = it.get("title", "(제목 없음)")
        imp = by_url.get(url, {})
        icon = IMPACT_ICON.get(imp.get("impact_direction"), "•")
        mag = imp.get("impact_magnitude")
        note = imp.get("impact_note")
        # 한국어 헤드라인 우선(영문 원제목의 "정신없음" 해소), 없으면 원제목 폴백.
        headline = html.escape((imp.get("headline_kr") or title)[:60])
        if url:
            # parse_mode=HTML — 링크를 제목에 임베드 (🔗 줄 제거). DB/파일 폴백은
            # notification service 가 plain 으로 strip (웹앱 알림 탭 태그 노출 방지).
            headline = f'<a href="{html.escape(url, quote=True)}">{headline}</a>'
        lines.append(f"{i}. {icon}{mag_icon.get(mag, '')} {headline}")
        if note:
            lines.append(f"   └ {html.escape(note[:100])}")

    return "\n".join(lines)


def render_positions(data: dict) -> str:
    """morning_pre 'positions' 파트 — 보유/관심 + 섹터 관점 + 신규 후보 + 7계명 체크."""
    positions_advice = data.get("positions_advice") or []
    new_candidates = data.get("new_candidates") or []
    sector_watch = data.get("sector_watch") or {}
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
            reason = p.get("reason", "")
            lines.append(f"  {icon} {name} — {verdict}")
            if reason:
                lines.append(f"     {_clip_sentence(reason, 240)}")

    # 섹터 관점 (2026-07-07 사용자 요청) — LLM 이 산출하던 sector_watch 를 렌더가
    # 버리고 있었음. 약세 = 행동 함의(신규 회피·보유 비중 축소 검토)까지 — 시장 안
    # 좋은 날 보유가 없어도 "무엇을 피할지"가 안내되는 층.
    bullish = [s for s in (sector_watch.get("bullish") or []) if s]
    bearish = [s for s in (sector_watch.get("bearish") or []) if s]
    if bullish or bearish:
        lines.append("")
        lines.append("🧭 섹터 관점")
        if bullish:
            lines.append(f"  강세: {', '.join(bullish[:5])}")
        if bearish:
            lines.append(f"  약세·회피: {', '.join(bearish[:5])} (신규 회피 · 보유 시 비중 축소 검토)")

    lines.append("")
    lines.append("✨ 신규 매수 후보")
    if not new_candidates:
        lines.append("  (오늘은 신규 후보 없음)")
    else:
        # 종목줄/이유줄 분리 + 항목 간 빈 줄 (2026-07-07 "띄어쓰기 안 돼 힘들다").
        # 내부 라벨(Canon: 경로·점수 코드) 누출은 결정론 스크러버 재사용으로 차단.
        from core.intent.formatter import scrub_code_labels

        for i, c in enumerate(new_candidates[:3], 1):
            sector = c.get("sector") or "?"
            name = c.get("name") or c.get("ticker", "?")
            reason = scrub_code_labels(_clip_sentence(c.get("reason", ""), 200))
            if i > 1:
                lines.append("")
            # 종목명 볼드 — "약하게 보인다" (2026-07-07). notification 이 <b> 보존/strip 처리.
            lines.append(f"{i}. <b>{html.escape(str(name))}</b> [{sector}]")
            if reason:
                lines.append(f"   └ {reason}")

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
    lines.append("🇰🇷 국내 지수  (괄호 = KRX 정규장 전일 종가 대비)")

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
        f"📊 강세 섹터 (조건 ≥{threshold:g}% 우선 + KRX 정규장 전일 종가 대비 상승률 순)"
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
    lines.append("🚀 주도주  (괄호 % = KRX 정규장 전일 종가 대비 등락)")

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
    lines.append("  · KOSPI 대형주 (시총20위): 전일 종가 대비 ≥ 2%")
    lines.append("  · KOSPI 중소형 (시총20위 외): 전일 종가 대비 ≥ 5%")
    lines.append("  · KOSDAQ: 전일 종가 대비 ≥ 5%")
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


_PIPELINE_RENDERERS = {
    "market_briefing_pre": render_morning_pre,
    "market_briefing_now": render_market_briefing,
}


def render_pipeline(
    pipeline_id: str,
    parts: list[BriefingPart],
    status: BriefingStatus = "ok",
) -> list[str]:
    """pipeline_id 기반 분기 — 텔레그램·webapp 공용 진입점.

    매핑되는 함수가 없으면 빈 리스트 반환 (caller 가 fallback).
    """
    renderer = _PIPELINE_RENDERERS.get(pipeline_id)
    if renderer is None:
        return []
    return renderer(parts, status)
