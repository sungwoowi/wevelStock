"""Telegram 봇 빌더 + long-polling 태스크.

서버 부팅 시 `build_application()` 호출 → 토큰 없으면 None 반환(봇 비활성),
토큰 있으면 `run_polling_forever()` 를 asyncio.create_task 로 돌림.

다른 코드(e.g. server.main.py lifespan) 에서 asyncio 이벤트루프 를 이미 돌리고
있으므로, PTB `Application.run_polling()` 의 자체 루프를 피하고
`initialize → start → updater.start_polling → (대기) → graceful shutdown` 을
수동으로 조립한다.
"""
from __future__ import annotations

import asyncio
import os

from telegram import BotCommand
from telegram.ext import Application

from core.logging import get_logger

log = get_logger(__name__)


def _env(name: str) -> str | None:
    v = os.environ.get(name) or ""
    return v.strip() or None


def get_bot_token() -> str | None:
    return _env("TELEGRAM_BOT_TOKEN")


def get_chat_id() -> str | None:
    return _env("TELEGRAM_CHAT_ID")


def build_application() -> Application | None:
    """토큰 있으면 Application 빌드 + 핸들러 등록, 없으면 None."""
    token = get_bot_token()
    if not token:
        log.info("telegram_bot_disabled", reason="no_token")
        return None

    from telegram.ext import CommandHandler

    from server.telegram.commands import (
        cmd_briefing_now,
        cmd_briefing_pre,
        cmd_briefing_pre_force,
        cmd_help,
    )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("briefing_pre", cmd_briefing_pre))
    app.add_handler(CommandHandler("briefing_pre_force", cmd_briefing_pre_force))
    app.add_handler(CommandHandler("briefing_now", cmd_briefing_now))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    return app


async def _setup_bot_commands(app: Application) -> None:
    """슬래시 자동완성 목록 등록. 실패해도 봇은 계속 동작."""
    try:
        await app.bot.set_my_commands(
            [
                BotCommand("briefing_pre", "장전 브리핑 (09:00 이후엔 아침 보관본)"),
                BotCommand("briefing_pre_force", "09:00 이후 LLM 실시간 실행 (~30s)"),
                BotCommand("briefing_now", "지금 기준으로 새 브리핑 실행 (~30s)"),
                BotCommand("help", "명령어 목록"),
            ]
        )
    except Exception as e:  # noqa: BLE001
        log.warning("telegram_set_my_commands_failed", error=str(e))


async def run_polling_forever(app: Application) -> None:
    """long-polling 영구 실행 — lifespan 이 cancel 할 때까지 블록."""
    await app.initialize()
    await _setup_bot_commands(app)
    await app.start()
    if app.updater is None:
        log.warning("telegram_updater_missing")
        await app.shutdown()
        return

    await app.updater.start_polling(drop_pending_updates=True)
    log.info("telegram_bot_started")
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        log.info("telegram_bot_stopping")
        raise
    finally:
        try:
            if app.updater is not None:
                await app.updater.stop()
        except Exception as e:  # noqa: BLE001
            log.warning("telegram_updater_stop_failed", error=str(e))
        try:
            await app.stop()
        except Exception as e:  # noqa: BLE001
            log.warning("telegram_app_stop_failed", error=str(e))
        try:
            await app.shutdown()
        except Exception as e:  # noqa: BLE001
            log.warning("telegram_app_shutdown_failed", error=str(e))
