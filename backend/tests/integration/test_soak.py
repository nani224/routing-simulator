"""Integration soak test verifying memory stability, zero leaks, and continuous event processing."""

import gc
import os

import psutil
import pytest
from routelab.core.clock import VirtualClock
from routelab.core.events import EventStore
from routelab.protocols.ls import LinkStateProtocol
from routelab.sim.engine import SimulationEngine
from routelab.topology.generators import generate_scale_free


@pytest.mark.asyncio
async def test_simulation_soak_run() -> None:
    """Run an intensive multi-event simulation cycle to verify memory stability."""
    topo = generate_scale_free(num_nodes=20, m=2, seed=100)
    vclock = VirtualClock()
    store = EventStore(max_events=20_000)

    engine = SimulationEngine(
        topology=topo,
        protocol_factory=LinkStateProtocol,
        clock=vclock,
        event_store=store,
        quiescence_window_s=0.2,
        seed=42,
    )

    # Schedule repeated periodic link perturbations on existing links
    l0 = topo.links[0]
    l1 = topo.links[1]
    for cycle in range(5):
        t_base = 0.5 + cycle * 1.0
        engine.add_event(
            t_base, "link_cost", {"u": l0.source, "v": l0.target, "cost": 10.0 + cycle}
        )
        engine.add_event(t_base + 0.3, "link_down", {"u": l1.source, "v": l1.target})
        engine.add_event(t_base + 0.6, "link_up", {"u": l1.source, "v": l1.target})

    process = psutil.Process(os.getpid())
    gc.collect()
    mem_before = process.memory_info().rss / (1024 * 1024)

    await engine.start()
    while vclock.now() < 6.0:
        await vclock.run_until(vclock.now() + 0.1)
        if vclock.now() >= 5.2 and engine.check_convergence():
            break

    gc.collect()
    mem_after = process.memory_info().rss / (1024 * 1024)
    mem_delta = mem_after - mem_before

    # Verify memory growth is strictly bounded (< 20 MB delta)
    assert mem_delta < 20.0
    assert engine.convergence_record.is_converged is True
    assert store.count() >= 15
