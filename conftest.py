"""Root conftest — isolates tests with a temporary SQLite DB.

Sets DB_PATH before the config module caches anything, so the whole test
session uses a scratch DB.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Prepare a scratch DB path before anything else imports core.config / core.db
_tmp = Path(tempfile.mkdtemp(prefix="wevelstock-test-"))
os.environ["DB_PATH"] = str(_tmp / "test.sqlite")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("TELEGRAM_CHAT_ID", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
