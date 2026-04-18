"""Daily DB backup job — copies the SQLite file to data/backups/.
Keeps the latest 30 days.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from core.config import get_config
from core.logging import get_logger

log = get_logger(__name__)


async def run_backup() -> dict:
    cfg = get_config()
    db_path = Path(cfg.database.path)
    backup_dir = db_path.parent.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dst = backup_dir / f"{db_path.stem}-{stamp}.sqlite"
    try:
        shutil.copy2(db_path, dst)
    except FileNotFoundError:
        log.warning("db_missing_for_backup", path=str(db_path))
        return {"status": "skipped", "reason": "db missing"}

    # Retain latest 30
    files = sorted(backup_dir.glob(f"{db_path.stem}-*.sqlite"))
    for old in files[:-30]:
        try:
            old.unlink()
        except OSError:
            pass

    log.info("db_backup_written", path=str(dst))
    return {"status": "ok", "backup": str(dst)}


if __name__ == "__main__":
    import asyncio
    print(asyncio.run(run_backup()))
