"""Pydantic request and response models for the RouteLab REST and WebSocket API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    project: str = "RouteLab Routing Protocol Simulator"
    team: str = "Team 20 (Aakarsh, Sravan, Sneha)"


class TopologySummary(BaseModel):
    name: str
    node_count: int
    link_count: int
    is_preset: bool = True
    description: str = ""


class GenerateTopologyRequest(BaseModel):
    kind: str = Field(
        ...,
        description="Topology generator type: ring, grid, tree, random_geometric, scale_free",
    )
    node_count: int = Field(default=8, ge=2, le=200)
    name: str = "Generated-Topology"
    seed: int = 42
    # Additional optional generator params
    width: int | None = None
    height: int | None = None
    branching_factor: int = 2
    depth: int = 3
    radius: float = 0.4
    attachment_m: int = 2


class PluginSummary(BaseModel):
    name: str
    version: str
    author: str
    description: str
    config_schema: dict[str, Any] = Field(default_factory=dict)
    is_builtin: bool = True


class StartSimulationRequest(BaseModel):
    topology_name: str = "Course-6-Node-Benchmark"
    topology_data: dict[str, Any] | None = None
    protocol_name: str = "distance_vector"
    protocol_config: dict[str, Any] = Field(default_factory=dict)
    node_protocols: dict[str, str] = Field(default_factory=dict)
    quiescence_window_s: float = 0.3
    clock_mode: str = Field(default="virtual", pattern="^(realtime|virtual)$")
    clock_speed: float = 1.0
    seed: int = 42


class SimulationStepRequest(BaseModel):
    step_duration_s: float = Field(default=0.1, ge=0.001, le=10.0)


class InjectEventRequest(BaseModel):
    action: str = Field(
        ...,
        description=(
            "Action type: link_down, link_up, link_cost, node_crash, node_recover, inject_packet"
        ),
    )
    params: dict[str, Any] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    topology_name: str = "Course-6-Node-Benchmark"
    topology_data: dict[str, Any] | None = None
    protocols: list[str] = Field(
        default_factory=lambda: ["distance_vector", "link_state", "flooding"]
    )
    events: list[dict[str, Any]] = Field(default_factory=list)
    time_limit_s: float = 20.0
    quiescence_window_s: float = 0.3
    seed: int = 42


class ScenarioSummary(BaseModel):
    name: str
    description: str
    file_name: str
    default_protocol: str
    event_count: int


class RunScenarioRequest(BaseModel):
    file_name: str
    override_protocol: str | None = None
    time_limit_s: float | None = None
    quiescence_window_s: float | None = None
    seed: int | None = None
