"""Interactive simulation session control, event injection, comparison, and export router."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from routelab.api.models import (
    CompareRequest,
    InjectEventRequest,
    SimulationStepRequest,
    StartSimulationRequest,
)
from routelab.api.state import session_manager
from routelab.plugins.interface import RoutingProtocol
from routelab.sim.comparator import CompareEngine
from routelab.sim.engine import ScheduledSimulationEvent
from routelab.topology.model import Topology, TopologyLink, TopologyNode

router = APIRouter(prefix="", tags=["simulation"])


@router.post("/simulation/start")
async def start_simulation(req: StartSimulationRequest) -> dict[str, Any]:
    """Start an interactive simulation session with configured topology and protocol."""
    try:
        res = await session_manager.start_session(
            topology_name=req.topology_name,
            topology_data=req.topology_data,
            protocol_name=req.protocol_name,
            protocol_config=req.protocol_config,
            node_protocols=req.node_protocols,
            quiescence_window_s=req.quiescence_window_s,
            clock_mode=req.clock_mode,
            clock_speed=req.clock_speed,
            seed=req.seed,
        )
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to start simulation: {exc}") from exc


@router.post("/simulation/step")
async def step_simulation(req: SimulationStepRequest) -> dict[str, Any]:
    """Advance simulation forward by a discrete time step."""
    try:
        return await session_manager.step(duration_s=req.step_duration_s)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to step simulation: {exc}") from exc


@router.post("/simulation/event")
async def inject_event(req: InjectEventRequest) -> dict[str, Any]:
    """Inject a dynamic link or node event during active simulation."""
    try:
        return await session_manager.inject_event(action=req.action, params=req.params)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to inject event: {exc}") from exc


@router.post("/simulation/pause")
def pause_simulation() -> dict[str, Any]:
    """Pause active simulation execution."""
    return session_manager.pause()


@router.post("/simulation/resume")
def resume_simulation() -> dict[str, Any]:
    """Resume active simulation execution."""
    return session_manager.resume()


@router.post("/simulation/events")
async def inject_events_alias(req: InjectEventRequest) -> dict[str, Any]:
    """Alias for event injection."""
    return await inject_event(req)


@router.post("/simulation/stop")
async def stop_simulation() -> dict[str, Any]:
    """Stop active simulation session."""
    return await session_manager.stop_session()


@router.get("/simulation/state")
def get_simulation_state() -> dict[str, Any]:
    """Retrieve full telemetry and routing state snapshot."""
    return session_manager.get_state()


@router.post("/simulation/compare")
async def compare_protocols(req: CompareRequest) -> dict[str, Any]:
    """Run deterministic comparative simulation across multiple routing algorithms."""
    # Resolve topology
    topo: Topology
    if req.topology_data:
        topo = Topology(name=req.topology_name or "Custom-Compare-Topo")
        for n_dict in req.topology_data.get("nodes", []):
            topo.add_node(TopologyNode.from_dict(n_dict))
        for lnk_dict in req.topology_data.get("links", []):
            topo.add_link(TopologyLink.from_dict(lnk_dict))
    elif req.topology_name in session_manager.PRESET_MAP:
        topo = session_manager.PRESET_MAP[req.topology_name]()
    else:
        topo = session_manager.PRESET_MAP["Course-6-Node-Benchmark"]()

    # Parse scheduled events
    events: list[ScheduledSimulationEvent] = []
    for ev in req.events:
        events.append(
            ScheduledSimulationEvent(
                timestamp=float(ev["timestamp"]),
                action=str(ev["action"]),
                params=dict(ev.get("params", {})),
            )
        )

    # Build protocol pairs
    protocol_factories: list[tuple[str, Callable[[], RoutingProtocol]]] = []
    for p_name in req.protocols:
        if p_name in session_manager.PROTOCOL_MAP:
            target_factory = session_manager.PROTOCOL_MAP[p_name]

            def _create_factory(
                f: Callable[[dict[str, Any]], RoutingProtocol] = target_factory,
            ) -> Callable[[], RoutingProtocol]:
                return lambda: f({})

            protocol_factories.append((p_name, _create_factory()))

    if not protocol_factories:
        raise HTTPException(status_code=400, detail="No recognized protocol names provided")

    report = await CompareEngine.compare(
        topology=topo,
        protocols=protocol_factories,
        events=events,
        seed=req.seed,
        time_limit_s=req.time_limit_s,
        quiescence_window_s=req.quiescence_window_s,
    )

    return report.to_dict()


@router.get("/export/csv")
def export_csv() -> Response:
    """Export simulation event history as CSV."""
    csv_data = session_manager.export_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="simulation_log.csv"'},
    )


@router.get("/export/json")
def export_json() -> dict[str, Any]:
    """Export complete simulation telemetry and event log as JSON."""
    return session_manager.export_json()
