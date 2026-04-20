"""Stage: notify — 3분할 텔레그램 메시지 발송.

LLM은 analyze 단계에서 1회 호출되어 통합 JSON을 생성했고,
이 stage는 rendering만 담당:

  [1/3] 간밤시황: overnight_us + macro + night_futures
  [2/3] 시나리오 + 뉴스 Top 3
  [3/3] 포지션 + 신규 + 7계명 체크

Each message is sent via core.notification.notify() which auto-falls back
to file storage when Telegram is disabled.
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.notification import notify
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)

# Icons for impact direction in news block
IMPACT_ICON = {"bullish": "⬆️", "bearish": "⬇️", "neutral": "➡️"}

# Icons for positions_advice verdict
VERDICT_ICON = {
    "HOLD": "▫",
    "BUY_ADD": "🟢",
    "SELL_PART": "🟡",
    "SELL_ALL": "🔴",
}


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


def _build_msg_1_overnight(overnight_us: dict, macro: dict, night_futures: dict) -> str:
    lines: list[str] = []
    lines.append("🌙 간밤 시황")
    lines.append("")
    lines.append("🇺🇸 미국 지수")
    for key, label in [("nasdaq", "나스닥"), ("sp500", "S&P500"),
                        ("sox", "SOX (반도체)"), ("vix", "VIX (변동성 지수)")]:
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


def _build_msg_2_scenario_news(
    scenario: dict, news_impact: list[dict], news_items: list[dict]
) -> str:
    lines: list[str] = []
    lines.append("📈 오늘 시나리오")
    if scenario:
        expected = scenario.get("expected_open", "?")
        bias = scenario.get("bias", "?")
        conf = scenario.get("confidence", "?")
        lines.append(f"  예상 개장: {expected}  |  바이어스: {bias}  |  신뢰 {conf}")
        narrative = (scenario.get("narrative") or "").strip()
        if narrative:
            # Keep it short for Telegram
            lines.append("")
            lines.append(narrative[:600])

    # Attach impact to news items by URL
    by_url = {e.get("url"): e for e in (news_impact or []) if e.get("url")}
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


def _build_msg_3_positions(
    positions_advice: list[dict],
    new_candidates: list[dict],
    principles: dict,
) -> str:
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
    violations = (principles or {}).get("violations") or []
    warnings = (principles or {}).get("warnings") or []
    if violations:
        lines.append(f"⚠️ 7계명 위반 {len(violations)}건")
        for v in violations[:3]:
            lines.append(f"  - [계명 {v.get('commandment')}] {v.get('title')}")
    elif warnings:
        lines.append(f"🔸 7계명 경고 {len(warnings)}건")
    else:
        lines.append("✅ 7계명 체크: 위반 없음")

    return "\n".join(lines)


async def _send_part(ctx: StageContext, label: str, body: str) -> dict:
    return await notify(
        team_id=ctx.pipeline_id,
        level="info",
        title=f"[{ctx.date} 07:00] {label}",
        body=body,
        related_run_id=ctx.run_id,
        related_target="global",
    )


class NotifyStage(Stage):
    stage_id = "notify"
    stage_type = "act"

    async def run(self, ctx: StageContext) -> StageResult:
        overnight = ctx.get_stage_data("collect_overnight_us") or {}
        futures = ctx.get_stage_data("collect_night_futures") or {}
        news = ctx.get_stage_data("collect_news") or {}
        analyze_data = ctx.get_stage_data("analyze") or {}
        principles = ctx.get_stage_data("check_principles") or {}

        briefing = analyze_data.get("briefing") or {}

        msg1 = _build_msg_1_overnight(
            overnight.get("overnight_us", {}),
            overnight.get("macro", {}),
            futures.get("night_futures", {}),
        )
        msg2 = _build_msg_2_scenario_news(
            briefing.get("scenario") or {},
            briefing.get("news_impact") or [],
            news.get("items", []),
        )
        msg3 = _build_msg_3_positions(
            briefing.get("positions_advice") or [],
            briefing.get("new_candidates") or [],
            principles,
        )

        r1 = await _send_part(ctx, "간밤시황 1/3", msg1)
        r2 = await _send_part(ctx, "시나리오+뉴스 2/3", msg2)
        r3 = await _send_part(ctx, "포지션+신규 3/3", msg3)

        log.info(
            "morning_pre_notified",
            pipeline=ctx.pipeline_id,
            channel_1=r1.get("channel"),
            channel_2=r2.get("channel"),
            channel_3=r3.get("channel"),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "parts": [
                    {"label": "overnight", "channel": r1.get("channel"),
                     "chars": len(msg1)},
                    {"label": "scenario_news", "channel": r2.get("channel"),
                     "chars": len(msg2)},
                    {"label": "positions", "channel": r3.get("channel"),
                     "chars": len(msg3)},
                ],
            },
        )
