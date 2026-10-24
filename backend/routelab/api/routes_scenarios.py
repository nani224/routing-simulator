"""Scenario listing and automated batch execution router."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from routelab.api.models import RunScenarioRequest, ScenarioSummary
from routelab.sim.scenario import ScenarioRunner

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

SCENARIOS_DIR = Path("examples/scenarios")


@router.get("", response_model=list[ScenarioSummary])
def list_scenarios() -> list[ScenarioSummary]:
    """Scan and list all predefined course scenarios."""
    if not SCENARIOS_DIR.exists():
        return []

    summaries: list[ScenarioSummary] = []
    for file_path in sorted(SCENARIOS_DIR.glob("*.json")):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            summaries.append(
                ScenarioSummary(
                    name=data.get("name", file_path.stem),
                    description=data.get("description", ""),
                    file_name=file_path.name,
                    default_protocol=data.get("default_protocol", "distance_vector"),
                    event_count=len(data.get("events", [])),
                )
            )
        except Exception:
            continue
    return summaries


@router.get("/{file_name}")
def get_scenario_definition(file_name: str) -> dict[str, Any]:
    """Retrieve raw JSON configuration for a specific scenario."""
    target = SCENARIOS_DIR / file_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Scenario file '{file_name}' not found")

    with open(target, encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


@router.post("/run")
async def run_scenario(req: RunScenarioRequest) -> dict[str, Any]:
    """Execute scenario deterministically and return metrics report."""
    target = SCENARIOS_DIR / req.file_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"Scenario file '{req.file_name}' not found")

    scenario = ScenarioRunner.load_from_file(target)

    # Apply overrides if specified
    if req.override_protocol:
        scenario.default_protocol = req.override_protocol
    if req.time_limit_s is not None:
        scenario.time_limit_s = req.time_limit_s
    if req.quiescence_window_s is not None:
        scenario.quiescence_window_s = req.quiescence_window_s
    if req.seed is not None:
        scenario.seed = req.seed

    result = await ScenarioRunner.run(scenario)

    return {
        "scenario_name": result.scenario_name,
        "is_converged": result.is_converged,
        "convergence_time_s": result.convergence_time_s,
        "event_count": result.event_count,
        "metrics": result.metrics.to_dict(),
        "final_routes": result.final_routes,
    }
