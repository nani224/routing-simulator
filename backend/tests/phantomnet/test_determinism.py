"""Determinism test: same seed twice => identical event-log hash."""

from __future__ import annotations

from phantomnet.bus import PhantomEventBus
from phantomnet.synthetic import generate_synthetic_episode


def test_determinism_identical_seed_identical_hash() -> None:
    """Verify that identical seeds yield strictly identical SHA-256 event-log hashes."""
    seed = 42

    # Run 1
    events_run1 = generate_synthetic_episode(seed=seed)
    bus1 = PhantomEventBus(run_id="run-1")
    for ev in events_run1:
        bus1.publish_sync(ev)
    hash1 = bus1.get_run_hash()

    # Run 2
    events_run2 = generate_synthetic_episode(seed=seed)
    bus2 = PhantomEventBus(run_id="run-2")
    for ev in events_run2:
        bus2.publish_sync(ev)
    hash2 = bus2.get_run_hash()

    # Byte-level and hash equality
    assert len(events_run1) == len(events_run2)
    assert hash1 == hash2, f"Determinism failure: {hash1} != {hash2}"

    # Run 3 (different seed => different hash)
    events_run3 = generate_synthetic_episode(seed=999)
    bus3 = PhantomEventBus(run_id="run-3")
    for ev in events_run3:
        bus3.publish_sync(ev)
    hash3 = bus3.get_run_hash()

    assert hash3 != hash1, "Distinct seeds produced colliding run hash!"


def test_determinism_repeated_runs_stability() -> None:
    """Verify across 5 consecutive generations that the hash is perfectly invariant."""
    target_seed = 1337
    hashes: list[str] = []

    for idx in range(5):
        bus = PhantomEventBus(run_id=f"rep-{idx}")
        for ev in generate_synthetic_episode(seed=target_seed):
            bus.publish_sync(ev)
        hashes.append(bus.get_run_hash())

    # All 5 hashes must be completely identical
    assert len(set(hashes)) == 1

