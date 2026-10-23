"""Unit tests for RealtimeClock and VirtualClock."""

import asyncio

import pytest
from routelab.core.clock import RealtimeClock, VirtualClock


@pytest.mark.asyncio
async def test_realtime_clock_scaling() -> None:
    clock = RealtimeClock(initial_speed=2.0)
    assert clock.speed == 2.0
    assert not clock.is_virtual

    t0 = clock.now()
    await clock.sleep(0.04)  # 0.04 / 2.0 = 0.02s real time
    t1 = clock.now()
    assert t1 > t0
    assert (t1 - t0) >= 0.03


@pytest.mark.asyncio
async def test_realtime_clock_pause_resume() -> None:
    clock = RealtimeClock(initial_speed=1.0)
    clock.pause()
    assert clock.is_paused

    p_time_1 = clock.now()
    await asyncio.sleep(0.02)
    p_time_2 = clock.now()
    assert p_time_1 == pytest.approx(p_time_2, abs=1e-4)

    clock.resume()
    assert not clock.is_paused
    await asyncio.sleep(0.02)
    assert clock.now() > p_time_2


@pytest.mark.asyncio
async def test_virtual_clock_determinism() -> None:
    vclock1 = VirtualClock(seed=123)
    vclock2 = VirtualClock(seed=123)

    assert vclock1.is_virtual
    assert vclock1.now() == 0.0

    # Verify RNG determinism
    samples1 = [vclock1.rng.random() for _ in range(10)]
    samples2 = [vclock2.rng.random() for _ in range(10)]
    assert samples1 == samples2


@pytest.mark.asyncio
async def test_virtual_clock_event_scheduling() -> None:
    clock = VirtualClock(seed=42)
    events: list[str] = []

    clock.schedule(0.1, lambda: events.append("first"))
    clock.schedule(0.3, lambda: events.append("third"))
    clock.schedule(0.2, lambda: events.append("second"))

    assert clock.has_pending_events()
    assert clock.next_event_time() == 0.1

    await clock.step()
    assert events == ["first"]
    assert clock.now() == 0.1

    await clock.run_until(0.35)
    assert events == ["first", "second", "third"]
    assert clock.now() == 0.35
    assert not clock.has_pending_events()


def test_clock_invalid_speed() -> None:
    with pytest.raises(ValueError, match="Clock speed must be positive"):
        RealtimeClock(initial_speed=-1.0)

    clock = RealtimeClock()
    with pytest.raises(ValueError, match="Clock speed must be positive"):
        clock.speed = 0.0


def test_virtual_clock_advance() -> None:
    clock = VirtualClock()
    clock.advance(5.5)
    assert clock.now() == 5.5

    with pytest.raises(ValueError, match="Time cannot move backwards"):
        clock.advance(-1.0)
