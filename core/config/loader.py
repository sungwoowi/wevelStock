"""Config loader with hot-reload support.

- Merges config/defaults.yaml (committed) + config/runtime.yaml (dynamic).
- .env provides secrets via python-dotenv.
- watchdog monitors runtime.yaml and swaps the Config atomically on change.
- Invalid YAML → previous config retained, error logged.
"""
from __future__ import annotations

import os
import subprocess
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


def _main_worktree_root() -> Path:
    """git common-dir 의 부모 = **메인 worktree** root. 서브 worktree 들이
    공유하는 루트 경로. `.env` 와 `data/` 가 여기 한 곳에만 있으면 됨.

    git 호출 실패 시 REPO_ROOT (현재 worktree) 로 fallback.
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if out.returncode == 0:
            git_common = Path(out.stdout.strip())
            if git_common.exists():
                return git_common.parent
    except (OSError, subprocess.SubprocessError):
        pass
    return REPO_ROOT


def _resolve_env_file() -> Path | None:
    """`.env` 탐색 — 현재 worktree → 메인 worktree 순.

    git worktree 환경에서 서브 worktree 에는 `.env` 를 두지 않고 메인에만
    둬도 모든 worktree 가 같은 시크릿을 공유.
    """
    local = REPO_ROOT / ".env"
    if local.exists():
        return local
    shared = _main_worktree_root() / ".env"
    if shared.exists():
        return shared
    return None

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
    # 테스트에서는 실 `.env` 자동 탐색을 건너뛴다 — 실 TELEGRAM_BOT_TOKEN 이
    # 주입되어 테스트가 실제 Telegram 호출을 발생시키는 사고 방지.
    if not os.environ.get("WEVELSTOCK_SKIP_DOTENV"):
        env_file = _resolve_env_file()
        if env_file is not None:
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

    # DB path 가 상대경로면 **메인 worktree root** 기준으로 절대화.
    # env var / yaml / .env 어디서 왔든 동일 적용 → 모든 git worktree 가 같은
    # SQLite 파일을 공유. 로컬 DB 는 공유가 자연스럽고, 서브 worktree 별로
    # 갈라지는 건 의도치 않은 격리.
    cfg_db_path = merged.get("database", {}).get("path")
    if cfg_db_path and not Path(cfg_db_path).is_absolute():
        shared_root = _main_worktree_root()
        merged.setdefault("database", {})["path"] = str(
            (shared_root / cfg_db_path).resolve()
        )

    if lvl := os.environ.get("LOG_LEVEL"):
        merged.setdefault("logging", {})["level"] = lvl.upper()
    if tz := os.environ.get("TIMEZONE"):
        merged["timezone"] = tz
    if sm := os.environ.get("SOURCE_MODE"):
        if sm in ("seed", "live"):
            merged["source_mode"] = sm
    # LLM provider 토글 — .env `LLM_PROVIDER` 가 llm.provider 를 오버라이드 (gemini↔claude_code 등).
    #   웹UI 토글은 runtime.yaml 을 쓰고(핫리로드), .env 는 서버 기동 시 고정 오버라이드.
    if lp := os.environ.get("LLM_PROVIDER"):
        if lp in ("gemini", "claude_code", "anthropic", "mock"):
            merged.setdefault("llm", {})["provider"] = lp

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
