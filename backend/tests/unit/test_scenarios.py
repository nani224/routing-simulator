"""Unit tests for ScenarioRunner loading and execution of scenario JSON files."""

from pathlib import Path

import pytest
from routelab.sim.scenario import ScenarioRunner


@pytest.mark.asyncio
async def test_scenario_runner_6_node_json() -> None:
    scenario_path = Path("examples/scenarios/6_node_dv_vs_ls.json")
    scenario = ScenarioRunner.load_from_file(scenario_path)

    assert scenario.name == "6-Node Course Baseline (DV vs LS)"
    assert len(scenario.events) == 2

    result = await ScenarioRunner.run(scenario)

    assert result.is_converged
    assert result.convergence_time_s > 0
    assert result.metrics.node_count == 6
    assert result.metrics.link_count == 8
    assert "A" in result.final_routes
    assert len(result.final_routes["A"]) > 0


@pytest.mark.asyncio
async def test_scenario_runner_count_to_infinity_json() -> None:
    scenario_path = Path("examples/scenarios/count_to_infinity.json")
    scenario = ScenarioRunner.load_from_file(scenario_path)

    result = await ScenarioRunner.run(scenario)
    assert result.is_converged
    assert result.metrics.node_count == 4


@pytest.mark.asyncio
async def test_scenario_runner_bgp_tier1_json() -> None:
    scenario_path = Path("examples/scenarios/bgp_tier1_peering.json")
    scenario = ScenarioRunner.load_from_file(scenario_path)

    result = await ScenarioRunner.run(scenario)
    assert result.is_converged
    assert result.metrics.node_count == 4
