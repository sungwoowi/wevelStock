"""Telegram 봇 명령어 핸들러.

/briefing_pre       — 장전 브리핑 (09:00 이후엔 아침 보관본 재전송)
/briefing_pre_force — 09:00 이후에도 LLM 실시간 실행 (복구용, ~30s)
/briefing_now       — 강제 새 run (~30s, Phase 2 에서 market_briefing 로 의미 전환 예정)
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

from core.briefing import render_morning_pre
from core.contracts.briefing_part import BriefingResponse
from core.logging import get_logger
from server.api.briefings_on_demand import briefing_run
from server.telegram.bot import get_chat_id

log = get_logger(__name__)

HELP_TEXT = (
    "🤖 wevelStock 브리핑 봇\n\n"
    "/briefing_pre — 오늘 장전 브리핑 (09:00 이후엔 아침 보관본 재전송)\n"
    "/briefing_pre_force — 09:00 이후에도 LLM 실시간 실행 (서버 다운 등 복구용, ~30s)\n"
    "/briefing_now — 지금 기준으로 새 브리핑 실행 (~30s, v1 호환)\n"
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


async def _send_briefing(update: Update, resp: BriefingResponse) -> None:
    """BriefingResponse → render → 3분할 sendMessage. `note` 있으면 첫 분할에 prefix."""
    chat = update.effective_chat
    if chat is None:
        return
    texts = render_morning_pre(resp.parts, status=resp.status)
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
    return ""


async def cmd_briefing_now(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """강제 새 run — 중간 "생성 중…" 메시지 먼저 보내고 완료 후 전송."""
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(GENERATING_TEXT)
    try:
        resp = await briefing_run(
            "morning_pre", force=True, cache=False, notify=False
        )
    except HTTPException as e:
        log.warning("cmd_briefing_now_error", status=e.status_code, detail=str(e.detail))
        if update.message is not None:
            await update.message.reply_text(f"새 브리핑 실행 실패: {e.detail}")
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
            "morning_pre", force=False, cache=False, notify=False
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
            "morning_pre", force=True, cache=False, notify=False
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


async def cmd_help(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not _authorized(update):
        return
    if update.message is not None:
        await update.message.reply_text(HELP_TEXT)
