"""Pipeline execution framework: Stage, StageContext, StageResult, PipelineRunner.

Each pipeline is a sequence of stages executed in dependency order.
Stages with no mutual dependency run in parallel via asyncio.gather.
"""
from __future__ import annotations

import asyncio
import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import get_config
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Output of a single stage execution."""

    stage_id: str
    status: str = "ok"  # ok | warning | error
    data: dict[str, Any] = field(default_factory=dict)
    verdict: str | None = None
    confidence: int | None = None
    reasons: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class StageContext:
    """Accumulated context passed through the pipeline.

    Each stage reads previous results from ``data[stage_id]`` and writes
    its own result, which the runner adds after the stage completes.
    """

    run_id: str
    pipeline_id: str
    date: str  # YYYY-MM-DD
    data: dict[str, Any] = field(default_factory=dict)
    config: Any = None  # RuntimeConfig, set by runner

    def get_stage_data(self, stage_id: str) -> dict[str, Any]:
        """Retrieve a prior stage's output data."""
        return self.data.get(stage_id, {})


@dataclass
class PipelineResult:
    """Aggregated result of a full pipeline run."""

    pipeline_id: str
    run_id: str
    stages: dict[str, StageResult] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    final_verdict: str | None = None
    final_confidence: int | None = None

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Abstract Stage
# ---------------------------------------------------------------------------

class Stage(ABC):
    """Base class for all pipeline stages."""

    stage_id: str = ""
    stage_type: str = "collect"  # collect | check | analyze | act

    @abstractmethod
    async def run(self, ctx: StageContext) -> StageResult:
        """Execute this stage and return a result."""
        ...


# ---------------------------------------------------------------------------
# Pipeline manifest (parsed from manifest.yaml)
# ---------------------------------------------------------------------------

@dataclass
class StageManifest:
    """Parsed stage entry from pipeline manifest.yaml."""

    id: str
    module: str
    type: str = "collect"
    runtime: str = "code"  # code | llm
    depends_on: list[str] = field(default_factory=list)
    parallel_with: str | None = None
    timeout_sec: int = 60
    memory: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineManifest:
    """Parsed pipeline manifest.yaml."""

    id: str
    name: str
    stages: list[StageManifest] = field(default_factory=list)
    schedule: list[dict[str, Any]] = field(default_factory=list)
    knowledge: dict[str, Any] = field(default_factory=dict)
    contract_version: str = "1.0"
    status: str = "active"
    path: Path | None = None


# ---------------------------------------------------------------------------
# Pipeline Runner
# ---------------------------------------------------------------------------

def _topological_levels(stages: list[StageManifest]) -> list[list[StageManifest]]:
    """Group stages into execution waves respecting depends_on.

    Stages declaring ``parallel_with`` are merged into the same wave as
    their partner.
    """
    by_id = {s.id: s for s in stages}

    # Build dependency graph, including parallel_with as co-dependency
    remaining: dict[str, set[str]] = {}
    for s in stages:
        deps = set(d for d in s.depends_on if d in by_id)
        if s.parallel_with and s.parallel_with in by_id:
            # parallel_with means "run at the same time as", so share deps
            partner = by_id[s.parallel_with]
            deps |= set(d for d in partner.depends_on if d in by_id)
        remaining[s.id] = deps

    levels: list[list[StageManifest]] = []
    resolved: set[str] = set()

    while remaining:
        level_ids = [sid for sid, deps in remaining.items() if not (deps - resolved)]
        if not level_ids:
            log.warning("stage_dependency_cycle", remaining=list(remaining.keys()))
            break
        level = [by_id[sid] for sid in level_ids]
        levels.append(level)
        for sid in level_ids:
            remaining.pop(sid)
        resolved.update(level_ids)

    return levels


def _load_stage(pipeline_id: str, stage_manifest: StageManifest) -> Stage:
    """Dynamically import a stage module and return a Stage instance."""
    module_path = f"pipelines.{pipeline_id}.{stage_manifest.module}"
    mod = importlib.import_module(module_path)

    # Convention: module defines a class that inherits Stage
    # Find it automatically
    for attr_name in dir(mod):
        attr = getattr(mod, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, Stage)
            and attr is not Stage
        ):
            instance = attr()
            instance.stage_id = stage_manifest.id
            instance.stage_type = stage_manifest.type
            return instance

    raise ImportError(
        f"No Stage subclass found in {module_path}"
    )


class PipelineRunner:
    """Executes a pipeline's stages in dependency-aware parallel waves."""

    async def run(
        self,
        manifest: PipelineManifest,
        *,
        input_data: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> PipelineResult:
        if run_id is None:
            run_id = datetime.now(timezone.utc).astimezone().isoformat()

        today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")

        ctx = StageContext(
            run_id=run_id,
            pipeline_id=manifest.id,
            date=today,
            data=input_data.copy() if input_data else {},
            config=get_config(),
        )

        result = PipelineResult(
            pipeline_id=manifest.id,
            run_id=run_id,
        )

        levels = _topological_levels(manifest.stages)

        for level in levels:
            outcomes = await asyncio.gather(
                *(self._run_one(manifest.id, sm, ctx) for sm in level),
                return_exceptions=False,
            )
            for stage_result in outcomes:
                result.stages[stage_result.stage_id] = stage_result
                if stage_result.status == "error":
                    result.errors[stage_result.stage_id] = (
                        stage_result.error or "unknown"
                    )
                else:
                    # Accumulate data for downstream stages
                    ctx.data[stage_result.stage_id] = stage_result.data

                # Track the last analyze stage as the final verdict
                if stage_result.verdict is not None:
                    result.final_verdict = stage_result.verdict
                    result.final_confidence = stage_result.confidence

        return result

    async def _run_one(
        self,
        pipeline_id: str,
        stage_manifest: StageManifest,
        ctx: StageContext,
    ) -> StageResult:
        """Execute a single stage with error isolation."""
        try:
            stage = _load_stage(pipeline_id, stage_manifest)
        except Exception as e:  # noqa: BLE001
            log.error(
                "stage_import_failed",
                pipeline=pipeline_id,
                stage=stage_manifest.id,
                error=str(e),
            )
            return StageResult(
                stage_id=stage_manifest.id,
                status="error",
                error=f"import: {e}",
            )

        try:
            return await asyncio.wait_for(
                stage.run(ctx),
                timeout=stage_manifest.timeout_sec,
            )
        except asyncio.TimeoutError:
            log.error(
                "stage_timeout",
                pipeline=pipeline_id,
                stage=stage_manifest.id,
                timeout=stage_manifest.timeout_sec,
            )
            return StageResult(
                stage_id=stage_manifest.id,
                status="error",
                error=f"timeout after {stage_manifest.timeout_sec}s",
            )
        except Exception as e:  # noqa: BLE001
            log.error(
                "stage_run_failed",
                pipeline=pipeline_id,
                stage=stage_manifest.id,
                error=str(e),
            )
            return StageResult(
                stage_id=stage_manifest.id,
                status="error",
                error=str(e),
            )
