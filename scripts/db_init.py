"""Initialize the SQLite database (creates schema if missing).

Usage:
    just db-init
    uv run python -m scripts.db_init
"""
from __future__ import annotations

from core.config import get_config
from core.db import get_db


def main() -> None:
    cfg = get_config()
    print(f"Initializing DB at: {cfg.database.path}")
    db = get_db()
    row = db.fetch_one("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    version = row["version"] if row else None
    print(f"Schema version: {version}")
    print("DB ready.")


if __name__ == "__main__":
    main()
