"""Telegram 봇 명령어 핸들러.

/briefing     — 가장 최근 run 재전송 (cache). 없으면 안내.
/briefing_now — 강제 새 run (~30s). 중간에 "⏳ 내용 생성 중…" 메시지 먼저.
/help         — 명령어 목록.

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

from core.briefing import render_morning_pre
from core.contracts.briefing_part import BriefingResponse
from core.logging import get_logger
from server.api.briefings_on_demand import briefing_latest, briefing_run
from server.telegram.bot import get_chat_id

log = get_logger(__name__)

HELP_TEXT = (
    "🤖 wevelStock 브리핑 봇\n\n"
    "/briefing — 오늘자 최근 브리핑 재전송 (캐시)\n"
    "/briefing_now — 지금 기준으로 새 브리핑 실행 (약 30초)\n"
    "/help — 이 메시지"
)

NOT_YET_TEXT = (
    "오늘 아직 실행된 적 없음. `/briefing_now` 로 지금 실행할 수 있어요."
)

GENERATING_TEXT = "⏳ 내용 생성 중… (약 30초)"


def _authorized(update: Update) -> bool:
    expected = get_chat_id()
    chat = update.effective_chat
    if chat is None or expected is None:
        return False
    return str(chat.id) == expected


async def _send_briefing(update: Update, resp: BriefingResponse) -> None:
    """BriefingResponse → render → 3분할 sendMessage."""
    chat = update.effective_chat
    if chat is None:
        return
    texts = render_morning_pre(resp.parts, status=resp.status)
    total = len(texts)
    for idx, text in enumerate(texts, 1):
        header = f"[{idx}/{total}]\n"
        await chat.send_message(header + text)


async def cmd_briefing(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """가장 최근 run 재전송. 없으면 /briefing_now 안내."""
    if not _authorized(update):
        return
    try:
        resp = await briefing_latest("morning_pre")
    except HTTPException as e:
        if e.status_code == 404 and update.message is not None:
            await update.message.reply_text(NOT_YET_TEXT)
        elif update.message is not None:
            log.warning("cmd_briefing_error", status=e.status_code, detail=str(e.detail))
            await update.message.reply_text(f"일시적 오류: {e.detail}")
        return
    await _send_briefing(update, resp)


async def cmd_briefing_now(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """강제 새 run — 중간 "생성 중…" 메시지 먼저 보내고 완료 후 전송."""
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(GENERATING_TEXT)
    try:
        resp = await briefing_run("morning_pre", force=True, cache=False)
    except HTTPException as e:
        log.warning("cmd_briefing_now_error", status=e.status_code, detail=str(e.detail))
        if update.message is not None:
            await update.message.reply_text(f"새 브리핑 실행 실패: {e.detail}")
        return
    await _send_briefing(update, resp)


async def cmd_help(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(HELP_TEXT)
