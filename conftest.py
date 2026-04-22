"""Root conftest — isolates tests with a temporary SQLite DB.

Sets DB_PATH before the config module caches anything, so the whole test
session uses a scratch DB. Also forces test mode so core.config.loader does
NOT auto-discover and load the real `.env` (which would leak real
TELEGRAM_BOT_TOKEN and cause tests to send real messages).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# 1. Scratch DB path
_tmp = Path(tempfile.mkdtemp(prefix="wevelstock-test-"))
os.environ["DB_PATH"] = str(_tmp / "test.sqlite")
os.environ.setdefault("LOG_LEVEL", "WARNING")

# 2. Hard override secrets to empty — setdefault was insufficient because
#    loader.load_dotenv(override=True) later fills them from the real .env.
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

# 3. Tell loader to skip auto .env discovery during tests.
os.environ["WEVELSTOCK_SKIP_DOTENV"] = "1"


@pytest.fixture(autouse=True)
def _block_real_notifications(monkeypatch):
    """Safety net: force core.notification.notify() to a no-op fake in tests.

    Even if TELEGRAM_BOT_TOKEN somehow leaks in, this fixture prevents real
    Telegram HTTP calls during the whole test session.
    """
    import core.notification.service as svc

    async def _fake_notify(**kwargs):
        return {
            "channel": "file",
            "telegram_ok": None,
            "file": "test-noop",
        }

    monkeypatch.setattr(svc, "notify", _fake_notify)
