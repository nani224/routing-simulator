"""Unit tests for CompareEngine executing side-by-side protocol evaluations."""

import pytest
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.protocols.flooding import FloodingProtocol
from routelab.protocols.ls import LinkStateProtocol
from routelab.sim.comparator import CompareEngine
from routelab.sim.engine import ScheduledSimulationEvent
from routelab.topology.generators import preset_6_node


@pytest.mark.asyncio
async def test_compare_engine_dv_vs_ls_vs_flooding() -> None:
    topo = preset_6_node()

    # Identical failure injection schedule
    events = [
        ScheduledSimulationEvent(
            timestamp=0.1,
            action="link_down",
            params={"u": "A", "v": "B"},
        )
    ]

    report = await CompareEngine.compare(
        topology=topo,
        protocols=[
            ("distance_vector", lambda: DistanceVectorProtocol()),
            ("link_state", lambda: LinkStateProtocol()),
            ("flooding", lambda: FloodingProtocol()),
        ],
        events=events,
        seed=42,
        time_limit_s=20.0,
        quiescence_window_s=0.3,
    )

    assert report.topology_name == "Course-6-Node-Benchmark"
    assert "distance_vector" in report.metrics
    assert "link_state" in report.metrics
    assert "flooding" in report.metrics

    # Compare metrics
    dv_metrics = report.metrics["distance_vector"]
    ls_metrics = report.metrics["link_state"]
    flood_metrics = report.metrics["flooding"]

    assert dv_metrics.convergence_time_s > 0
    assert ls_metrics.convergence_time_s > 0
    assert flood_metrics.total_control_messages > 0

    # Flooding generates massive overhead
    assert flood_metrics.total_control_messages >= ls_metrics.total_control_messages

    # Verify winners dictionary
    assert "convergence_time" in report.winners
    assert "control_messages" in report.winners
    assert "control_bytes" in report.winners
    assert len(report.summary_notes) >= 1

    report_dict = report.to_dict()
    assert report_dict["seed"] == 42
    assert "metrics" in report_dict
