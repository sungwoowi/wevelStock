"""Notification delivery with graceful fallback.

Priority order for delivery:
1. Telegram (if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID set and telegram.enabled)
2. File fallback (data/notifications/YYYY-MM-DD.jsonl) — always on, even on Telegram failure
3. DB log (notifications_log table) — always on

All three are attempted in parallel-fallback mode:
- If Telegram fails, the file + DB entries still record the attempt.
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import httpx

from core.config import env, get_config
from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

NotificationLevel = Literal["info", "warning", "critical"]

# 알림 분류 (INFRA-MARKET-ASSETS-002 / notification-persistence-v1).
# UI 알림 탭 필터·미독 배지 소스. 미구현 트리거(trade_signal·account_safety·risk_alert)는
# 그 배선 때 명시 전달; 현재 발송 경로(브리핑 파이프라인)는 team_id 휴리스틱으로 태깅.
NotificationType = Literal[
    "market_briefing", "trade_signal", "account_safety", "flow_idea", "risk_alert"
]


def _infer_notification_type(team_id: str, explicit: str | None) -> str | None:
    """notification_type 결정 — 명시값 우선, 미전달 시 team_id(=pipeline_id) 휴리스틱.

    현재 발송은 전부 브리핑 파이프라인(market_briefing_*)이라 market_briefing 으로 태깅.
    미구현 트리거 3종은 배선 때 explicit 전달. 매칭 실패 시 None(미분류).
    """
    if explicit:
        return explicit
    tid = team_id.lower()
    if "briefing" in tid:
        return "market_briefing"
    if "risk" in tid or "alert" in tid:
        return "risk_alert"
    if "account" in tid:
        return "account_safety"
    if "flow" in tid or "idea" in tid:
        return "flow_idea"
    if "trade" in tid or "signal" in tid:
        return "trade_signal"
    return None


async def _send_telegram(message: str) -> bool:
    token = env("TELEGRAM_BOT_TOKEN")
    chat_id = env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
            if resp.status_code == 200:
                return True
            log.warning("telegram_non200", status=resp.status_code, body=resp.text[:200])
            return False
    except Exception as e:  # noqa: BLE001
        log.warning("telegram_error", error=str(e))
        return False


def _write_file_fallback(payload: dict) -> Path:
    cfg = get_config().telegram
    dir_path = Path(cfg.fallback_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{date.today().isoformat()}.jsonl"
    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return file_path


def _log_to_db(
    *,
    team_id: str,
    level: str,
    title: str,
    body: str,
    channel: str,
    delivered: bool,
    related_run_id: str | None,
    related_target: str | None,
    notification_type: str | None,
) -> None:
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO notifications_log
                (team_id, level, title, body, channel, delivered,
                 related_run_id, related_target, notification_type, is_read)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (team_id, level, title, body, channel, int(delivered),
             related_run_id, related_target, notification_type),
        )


def _format_message(team_id: str, title: str, body: str) -> str:
    cfg = get_config().telegram
    template = cfg.formats.get(team_id) or cfg.formats.get(
        "default", "<b>{title}</b>\n{body}"
    )
    return template.format(
        title=html.escape(title, quote=False),
        body=html.escape(body, quote=False),
    )


async def notify(
    *,
    team_id: str,
    level: NotificationLevel,
    title: str,
    body: str,
    related_run_id: str | None = None,
    related_target: str | None = None,
    notification_type: str | None = None,
) -> dict:
    """Send a notification.

    Returns a dict with delivery details. Never raises.

    notification_type: 알림 탭 분류 (market_briefing|trade_signal|account_safety|
        flow_idea|risk_alert). 미전달 시 team_id 휴리스틱으로 추론 (브리핑→market_briefing).
    """
    cfg = get_config().telegram
    message = _format_message(team_id, title, body)
    ntype = _infer_notification_type(team_id, notification_type)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "team_id": team_id,
        "level": level,
        "title": title,
        "body": body,
        "related_run_id": related_run_id,
        "related_target": related_target,
        "notification_type": ntype,
        "message": message,
    }

    sent_telegram = False
    if cfg.enabled:
        sent_telegram = await _send_telegram(message)

    file_path = _write_file_fallback({**payload, "delivered_telegram": sent_telegram})

    channel = "telegram" if sent_telegram else "file"
    try:
        _log_to_db(
            team_id=team_id,
            level=level,
            title=title,
            body=body,
            channel=channel,
            delivered=sent_telegram or True,  # file fallback is "delivered"
            related_run_id=related_run_id,
            related_target=related_target,
            notification_type=ntype,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("notification_db_log_failed", error=str(e))

    log.info(
        "notification_sent",
        team=team_id,
        level=level,
        channel=channel,
        file=str(file_path),
    )
    return {
        "channel": channel,
        "telegram_ok": sent_telegram,
        "file": str(file_path),
        "notification_type": ntype,
    }
