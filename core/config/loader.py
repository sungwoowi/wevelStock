"""Config loader with hot-reload support.

- Merges config/defaults.yaml (committed) + config/runtime.yaml (dynamic).
- .env provides secrets via python-dotenv.
- watchdog monitors runtime.yaml and swaps the Config atomically on change.
- Invalid YAML → previous config retained, error logged.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv
from pydantic import ValidationError
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from core.config.schema import RuntimeConfig
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DEFAULTS_PATH = CONFIG_DIR / "defaults.yaml"
RUNTIME_PATH = CONFIG_DIR / "runtime.yaml"

_state_lock = threading.RLock()
_current_config: RuntimeConfig | None = None
_subscribers: list[Callable[[RuntimeConfig], None]] = []
_observer: Observer | None = None


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base (overlay wins)."""
    result = dict(base)
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> RuntimeConfig:
    """Load .env + defaults.yaml + runtime.yaml into a typed Config.

    Env vars that override YAML (for containers / tests):
        DB_PATH         → database.path
        LOG_LEVEL       → logging.level
        TIMEZONE        → timezone
        SOURCE_MODE     → source_mode
    """
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        # override=True: 시스템에 빈값으로 설정된 환경변수(예: Windows 사용자 env)를
        # .env 파일 값으로 강제 덮어쓰기. 없으면 .env가 무시됨.
        load_dotenv(env_file, override=True)

    defaults = _load_yaml(DEFAULTS_PATH)
    runtime = _load_yaml(RUNTIME_PATH)
    merged = _deep_merge(defaults, runtime)

    # Env var overrides (simple path overrides)
    db_path = os.environ.get("DB_PATH")
    if db_path:
        merged.setdefault("database", {})["path"] = db_path
    if lvl := os.environ.get("LOG_LEVEL"):
        merged.setdefault("logging", {})["level"] = lvl.upper()
    if tz := os.environ.get("TIMEZONE"):
        merged["timezone"] = tz
    if sm := os.environ.get("SOURCE_MODE"):
        if sm in ("seed", "live"):
            merged["source_mode"] = sm

    return RuntimeConfig(**merged)


def get_config() -> RuntimeConfig:
    """Return the current merged config (loads on first access)."""
    global _current_config
    with _state_lock:
        if _current_config is None:
            _current_config = load_config()
        return _current_config


def on_config_change(callback: Callable[[RuntimeConfig], None]) -> None:
    """Register a callback invoked whenever runtime.yaml is reloaded."""
    with _state_lock:
        _subscribers.append(callback)


def _reload_config() -> bool:
    """Try to reload. Returns True on success, False on validation error."""
    global _current_config
    try:
        new_cfg = load_config()
    except (ValidationError, yaml.YAMLError) as e:
        log.error("config_reload_failed", error=str(e))
        return False
    with _state_lock:
        _current_config = new_cfg
        subs = list(_subscribers)
    for cb in subs:
        try:
            cb(new_cfg)
        except Exception as e:  # noqa: BLE001
            log.error("config_subscriber_error", callback=repr(cb), error=str(e))
    log.info("config_reloaded")
    return True


class _ConfigWatchHandler(FileSystemEventHandler):
    def on_modified(self, event: FileSystemEvent) -> None:
        if Path(event.src_path).resolve() == RUNTIME_PATH.resolve():
            _reload_config()


def start_watcher() -> None:
    """Start watchdog observer on config/runtime.yaml. Idempotent."""
    global _observer
    with _state_lock:
        if _observer is not None:
            return
        # ensure config dir exists
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        RUNTIME_PATH.touch(exist_ok=True)
        _observer = Observer()
        _observer.schedule(_ConfigWatchHandler(), str(CONFIG_DIR), recursive=False)
        _observer.daemon = True
        _observer.start()
    log.info("config_watcher_started", path=str(RUNTIME_PATH))


def stop_watcher() -> None:
    global _observer
    with _state_lock:
        if _observer is not None:
            _observer.stop()
            _observer.join(timeout=2)
            _observer = None


def trigger_reload() -> bool:
    """Manually trigger a reload (used by /api/config/reload)."""
    return _reload_config()


def env(key: str, default: str | None = None) -> str | None:
    """Short helper to read an environment variable."""
    return os.environ.get(key, default)
