"""Integrated config (defaults + runtime + .env) with hot reload."""
from core.config.loader import (
    env,
    get_config,
    load_config,
    on_config_change,
    start_watcher,
    stop_watcher,
    trigger_reload,
)
from core.config.schema import RuntimeConfig

__all__ = [
    "RuntimeConfig",
    "env",
    "get_config",
    "load_config",
    "on_config_change",
    "start_watcher",
    "stop_watcher",
    "trigger_reload",
]
