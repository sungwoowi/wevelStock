"""Team/MCP/batch registry — scans filesystem + parses manifest.yaml files.

Central source of truth for: "which teams exist, what runtime, which schedule,
which are enabled."
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAMS_DIR = REPO_ROOT / "teams"
MCP_DIR = REPO_ROOT / "mcp-servers"


class ScheduleEntry(BaseModel):
    trigger: Literal["cron", "interval", "event"]
    expr: str | None = None
    timezone: str | None = None
    hours: int | None = None
    minutes: int | None = None
    seconds: int | None = None
    on: str | None = None
    id: str | None = None


class TeamManifest(BaseModel):
    id: str
    name: str
    type: str = "team-agent"
    runtime: Literal["rule", "llm", "hybrid"] = "rule"
    inputs: list[dict] = Field(default_factory=list)
    outputs: list[dict] = Field(default_factory=list)
    schedule: list[ScheduleEntry] = Field(default_factory=list)
    contract_version: str = "1.0"
    depends_on: list[str] = Field(default_factory=list)
    status: str = "planned"
    owner: str = ""
    memory: dict[str, Any] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)

    path: Path | None = None  # Filled in after load

    model_config = {"arbitrary_types_allowed": True}


def _load_manifest(path: Path) -> TeamManifest | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    try:
        m = TeamManifest(**data)
    except Exception:  # noqa: BLE001
        return None
    m.path = path.parent
    return m


def list_all_teams() -> list[TeamManifest]:
    """Scan teams/ directory and return all valid manifests (excluding _template)."""
    result: list[TeamManifest] = []
    if not TEAMS_DIR.exists():
        return result
    for child in sorted(TEAMS_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        manifest_path = child / "manifest.yaml"
        if not manifest_path.exists():
            continue
        m = _load_manifest(manifest_path)
        if m is not None:
            result.append(m)
    return result


def list_active_teams() -> list[TeamManifest]:
    """Return teams whose config.teams.<id>.enabled == True (defaults to True)."""
    from core.config import get_config  # late import to avoid cycle

    cfg = get_config()
    all_teams = list_all_teams()

    def _enabled(team_id: str) -> bool:
        teams_cfg = cfg.teams
        # known typed entries
        if team_id == "principles":
            return teams_cfg.principles.enabled
        if team_id == "daily-briefing":
            return teams_cfg.daily_briefing.enabled
        if team_id == "orchestrator":
            return teams_cfg.orchestrator.enabled
        # extra dict
        extra = teams_cfg.extra.get(team_id, {})
        return extra.get("enabled", True)

    return [t for t in all_teams if _enabled(t.id)]


def get_team(team_id: str) -> TeamManifest | None:
    for t in list_all_teams():
        if t.id == team_id:
            return t
    return None


def refresh_registry_file() -> None:
    """Regenerate teams/registry.yaml from filesystem scan."""
    all_teams = list_all_teams()
    payload = {
        "teams": [
            {"id": t.id, "name": t.name, "runtime": t.runtime, "status": t.status}
            for t in all_teams
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    registry_path = TEAMS_DIR / "registry.yaml"
    if TEAMS_DIR.exists():
        registry_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Pipeline registry (new — coexists with teams for migration period)
# ---------------------------------------------------------------------------

def list_all_pipelines():
    """Delegate to pipelines._registry for pipeline discovery."""
    from pipelines._registry import list_all_pipelines as _list
    return _list()


def list_active_pipelines():
    """Delegate to pipelines._registry for active pipeline discovery."""
    from pipelines._registry import list_active_pipelines as _list
    return _list()


def get_pipeline(pipeline_id: str):
    """Delegate to pipelines._registry for pipeline lookup."""
    from pipelines._registry import get_pipeline as _get
    return _get(pipeline_id)
