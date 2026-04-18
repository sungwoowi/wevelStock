"""Pipeline registry — scans pipelines/ for manifest.yaml files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from core.logging import get_logger
from pipelines._base import PipelineManifest, StageManifest

log = get_logger(__name__)

PIPELINES_DIR = Path(__file__).resolve().parent


def _parse_stage(raw: dict[str, Any]) -> StageManifest:
    return StageManifest(
        id=raw["id"],
        module=raw.get("module", f"stages.{raw['id']}"),
        type=raw.get("type", "collect"),
        runtime=raw.get("runtime", "code"),
        depends_on=raw.get("depends_on", []),
        parallel_with=raw.get("parallel_with"),
        timeout_sec=raw.get("timeout_sec", 60),
        memory=raw.get("memory", {}),
    )


def _load_manifest(path: Path) -> PipelineManifest | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        log.warning("pipeline_manifest_parse_error", path=str(path), error=str(e))
        return None

    try:
        stages = [_parse_stage(s) for s in data.get("stages", [])]
        return PipelineManifest(
            id=data["id"],
            name=data.get("name", data["id"]),
            stages=stages,
            schedule=data.get("schedule", []),
            knowledge=data.get("knowledge", {}),
            contract_version=data.get("contract_version", "1.0"),
            status=data.get("status", "active"),
            path=path.parent,
        )
    except (KeyError, TypeError) as e:
        log.warning("pipeline_manifest_invalid", path=str(path), error=str(e))
        return None


def list_all_pipelines() -> list[PipelineManifest]:
    """Scan pipelines/ directory for valid manifest.yaml files."""
    result: list[PipelineManifest] = []
    if not PIPELINES_DIR.exists():
        return result
    for child in sorted(PIPELINES_DIR.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        manifest_path = child / "manifest.yaml"
        if not manifest_path.exists():
            continue
        m = _load_manifest(manifest_path)
        if m is not None:
            result.append(m)
    return result


def list_active_pipelines() -> list[PipelineManifest]:
    """Return pipelines whose status is 'active'."""
    return [p for p in list_all_pipelines() if p.status == "active"]


def get_pipeline(pipeline_id: str) -> PipelineManifest | None:
    """Look up a specific pipeline by id."""
    for p in list_all_pipelines():
        if p.id == pipeline_id:
            return p
    return None
