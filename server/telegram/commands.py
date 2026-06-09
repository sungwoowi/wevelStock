"""Telegram 봇 명령어 핸들러.

/briefing_pre       — 장전 브리핑 (09:00 이후엔 아침 보관본 재전송)
/briefing_pre_force — 09:00 이후에도 LLM 실시간 실행 (복구용, ~30s)
/briefing_now       — 장중 실시간 시장 관찰 (market_briefing, KIS raw 데이터, ~30s)
/help               — 명령어 목록

chat_id 인증: `.env` 의 `TELEGRAM_CHAT_ID` 와 일치하지 않으면 **응답 없음**
(attack 벡터 최소화).

내부적으로 `server.api.briefings_on_demand` 의 핸들러 함수를 직접 호출하여
텔레그램/웹앱 동일 API 계약을 공유한다. HTTP loopback 을 피해 프로세스
내 단축 호출.
"""
from __future__ import annotations

from fastapi import HTTPException
from telegram import Update
from telegram.ext import ContextTypes

from core.briefing import render_market_briefing, render_morning_pre
from core.contracts.briefing_part import BriefingResponse
from core.logging import get_logger
from server.api.briefings_on_demand import briefing_run
from server.telegram.bot import get_chat_id

log = get_logger(__name__)

HELP_TEXT = (
    "🤖 wevelStock 브리핑 봇\n\n"
    "/briefing_pre — 오늘 장전 브리핑 (09:00 이후엔 아침 보관본 재전송)\n"
    "/briefing_pre_force — 09:00 이후에도 LLM 실시간 실행 (서버 다운 등 복구용, ~30s)\n"
    "/briefing_now — 장중 실시간 시장 관찰 — KIS 시세 (~30s)\n"
    "/accounts — 가상 4계좌 보유현황·평가손익\n"
    "/retro — 최근 90일 가이던스 회고 (시장 대비 적중도)\n"
    "/wealth — 복리 자산 추적 (자산 곡선·연 18% 목표 진척·MDD)\n"
    "/help — 이 메시지"
)

NO_PRE_SNAPSHOT_TEXT = (
    "오늘 장전 브리핑이 아직 생성되지 않았습니다.\n"
    "/briefing_pre_force 로 지금 실시간 실행할 수 있어요."
)

GENERATING_TEXT = "⏳ 내용 생성 중… (약 30초)"

CHECKING_PRE_TEXT = (
    "⏳ 장전 브리핑 확인 중… (보관본이면 즉시, 아니면 실시간 생성 ~30초)"
)


def _authorized(update: Update) -> bool:
    expected = get_chat_id()
    chat = update.effective_chat
    if chat is None or expected is None:
        return False
    return str(chat.id) == expected


_PIPELINE_RENDERERS = {
    "market_briefing_pre": render_morning_pre,
    "market_briefing_now": render_market_briefing,
}


async def _send_briefing(update: Update, resp: BriefingResponse) -> None:
    """BriefingResponse → render → 3분할 sendMessage. `note` 있으면 첫 분할에 prefix."""
    chat = update.effective_chat
    if chat is None:
        return
    renderer = _PIPELINE_RENDERERS.get(resp.pipeline_id, render_morning_pre)
    texts = renderer(resp.parts, status=resp.status)
    total = len(texts)
    prefix = _build_note_prefix(resp)
    for idx, text in enumerate(texts, 1):
        header = f"[{idx}/{total}]\n"
        if idx == 1 and prefix:
            await chat.send_message(prefix + "\n\n" + header + text)
        else:
            await chat.send_message(header + text)


def _build_note_prefix(resp: BriefingResponse) -> str:
    """`resp.note` 태그 → 사용자 노출 prefix. 없으면 빈 문자열."""
    if resp.note == "before_market_open":
        # run_id 는 `YYYY-MM-DDTHH:MM:SS...#manual-XXXX` 형식. 11~16 자리가 HH:MM
        hhmm = resp.run_id[11:16] if len(resp.run_id) >= 16 else "?"
        return f"⏰ 장 시작 전 데이터 기준 ({hhmm} 생성)"
    if resp.note == "market_closed":
        # run_id 의 날짜 부분 (YYYY-MM-DD) 을 추출
        date_part = resp.run_id[:10] if len(resp.run_id) >= 10 else "?"
        return (
            f"🔕 지금은 개장 시간이 아닙니다 — 가장 최근 시장 정보입니다 "
            f"({date_part} 기준)"
        )
    if resp.note == "market_briefing_early":
        return (
            "⚠️ 장 시작 직후 (09:00~09:19) — 거래량 적어 지표 신뢰도 낮습니다"
        )
    return ""


async def cmd_briefing_now(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """장중 실시간 시장 관찰 — market_briefing 강제 새 run (KIS raw 데이터)."""
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(GENERATING_TEXT)
    try:
        resp = await briefing_run(
            "market_briefing_now", force=True, cache=False, notify=False
        )
    except HTTPException as e:
        log.warning("cmd_briefing_now_error", status=e.status_code, detail=str(e.detail))
        if update.message is not None:
            await update.message.reply_text(f"브리핑 실행 실패: {e.detail}")
        return
    await _send_briefing(update, resp)


async def cmd_briefing_pre(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """morning_pre 기본 호출 — 09:00 이후엔 보관본 재전송, 이전엔 실시간."""
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(CHECKING_PRE_TEXT)
    try:
        resp = await briefing_run(
            "market_briefing_pre", force=False, cache=False, notify=False
        )
    except HTTPException as e:
        if e.status_code == 404 and update.message is not None:
            await update.message.reply_text(NO_PRE_SNAPSHOT_TEXT)
        elif update.message is not None:
            log.warning(
                "cmd_briefing_pre_error",
                status=e.status_code,
                detail=str(e.detail),
            )
            await update.message.reply_text(f"일시적 오류: {e.detail}")
        return
    await _send_briefing(update, resp)


async def cmd_briefing_pre_force(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """morning_pre force 실행 — 09:00 이후에도 LLM 실시간 실행."""
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(GENERATING_TEXT)
    try:
        resp = await briefing_run(
            "market_briefing_pre", force=True, cache=False, notify=False
        )
    except HTTPException as e:
        log.warning(
            "cmd_briefing_pre_force_error",
            status=e.status_code,
            detail=str(e.detail),
        )
        if update.message is not None:
            await update.message.reply_text(f"브리핑 실행 실패: {e.detail}")
        return
    await _send_briefing(update, resp)


def render_accounts_text(account_items: list[dict], holdings_by_id: dict[str, dict]) -> str:
    """가상 4계좌 현황 → 텔레그램 텍스트 (순수, 테스트 용이). 코드 라벨 노출 X."""
    lines = ["💼 가상 계좌 현황 (페이퍼)"]
    for a in account_items:
        h = holdings_by_id.get(a["account_id"], {"holdings": [], "summary": {}})
        lines.append(
            f"\n[{a['label']}] 투입 {a['deployed_weight'] * 100:.0f}% · 여력 {a['available_weight'] * 100:.0f}%"
        )
        if not h["holdings"]:
            lines.append("  · 보유 없음")
        for pos in h["holdings"]:
            sign = "+" if pos["unrealized_pct"] >= 0 else ""
            note = "" if pos["priced"] else " (시세 대기)"
            lines.append(
                f"  · {pos['ticker']} {pos['shares']:.0f}주 · 평단 {pos['avg_price']:,.0f} · "
                f"{sign}{pos['unrealized_pct']:.1f}%{note}"
            )
        s = h["summary"]
        if s.get("position_count"):
            lines.append(
                f"  평가손익 {s.get('unrealized_pnl_krw', 0):,.0f}원 · 실현 {s.get('realized_pnl_krw', 0):,.0f}원"
            )
    return "\n".join(lines)


async def cmd_accounts(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """가상 4계좌 보유현황 — webapp 과 동일 accounts API 소비."""
    if not _authorized(update):
        return
    from server.api.accounts import account_holdings, list_accounts

    try:
        accounts_resp = await list_accounts()
        holdings_by_id: dict[str, dict] = {}
        for a in accounts_resp["items"]:
            holdings_by_id[a["account_id"]] = await account_holdings(a["account_id"])
    except Exception as e:  # noqa: BLE001
        log.warning("cmd_accounts_error", error=str(e))
        if update.message is not None:
            await update.message.reply_text(f"계좌 조회 실패: {e}")
        return
    if update.message is not None:
        await update.message.reply_text(render_accounts_text(accounts_resp["items"], holdings_by_id))


async def cmd_retro(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """가이던스 회고 — 최근 90일 가상매매 적중도(시장 대비 초과수익·적중률)."""
    if not _authorized(update):
        return
    from core.guidance.kpi import get_kpi_summary
    from core.guidance.retrospective import render_retrospective

    try:
        summary = get_kpi_summary(period_days=90)
        text = render_retrospective(summary)
    except Exception as e:  # noqa: BLE001
        log.warning("cmd_retro_error", error=str(e))
        if update.message is not None:
            await update.message.reply_text(f"회고 조회 실패: {e}")
        return
    if update.message is not None:
        await update.message.reply_text(text)


async def cmd_wealth(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """복리 자산 추적 — 자산 곡선(실현 vs 총) + 연 18% 목표 진척 + MDD."""
    if not _authorized(update):
        return
    from core.account.compounding import (
        get_compound_progress,
        get_equity_curve,
        render_compound_summary,
    )

    try:
        text = render_compound_summary(get_compound_progress(), get_equity_curve())
    except Exception as e:  # noqa: BLE001
        log.warning("cmd_wealth_error", error=str(e))
        if update.message is not None:
            await update.message.reply_text(f"자산 조회 실패: {e}")
        return
    if update.message is not None:
        await update.message.reply_text(text)


async def cmd_help(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(HELP_TEXT)
