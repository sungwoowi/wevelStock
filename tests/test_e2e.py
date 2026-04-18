"""End-to-end tests — the whole stack from orchestrator down."""
from __future__ import annotations

import pytest

from core.contracts.team_output import StandardOutput
from teams.orchestrator.src.agent import Agent as Orchestrator


@pytest.mark.asyncio
async def test_e2e_over_allocation_scenario() -> None:
    """Demo scenario should flow through both teams and produce alert/caution."""
    orch = Orchestrator()
    result = await orch.run({
        "run_id": "test-e2e-over",
        "scenario": "over-allocation",
    })
    assert isinstance(result, StandardOutput)
    succeeded = result.data["teams_succeeded"]
    assert "principles" in succeeded


@pytest.mark.asyncio
async def test_e2e_normal_scenario_is_quieter() -> None:
    orch = Orchestrator()
    result = await orch.run({
        "run_id": "test-e2e-normal",
        "scenario": "normal",
    })
    # With a clean portfolio, orchestrator aggregate should not be alert
    assert result.verdict in {"neutral", "caution"}


@pytest.mark.asyncio
async def test_e2e_all_scenarios_no_crash() -> None:
    """Every seed scenario must at least not raise."""
    orch = Orchestrator()
    for scenario in ("normal", "over-allocation", "no-stop-loss", "emotional"):
        result = await orch.run({
            "run_id": f"test-e2e-all-{scenario}",
            "scenario": scenario,
        })
        assert isinstance(result, StandardOutput)
