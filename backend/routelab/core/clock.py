"""Time and clock abstractions for RouteLab.

Supports both wall-clock real-time execution with variable speed scaling,
and deterministic, reproducible virtual-clock execution for unit tests,
benchmarks, and comparative evaluations.
"""

from __future__ import annotations

import asyncio
import heapq
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any


class Clock(ABC):
    """Abstract base class for simulation clocks."""

    @abstractmethod
    def now(self) -> float:
        """Return the current simulation time in seconds."""

    @abstractmethod
    async def sleep(self, delay: float) -> None:
        """Asynchronously sleep for delay seconds (scaled by speed)."""

    @property
    @abstractmethod
    def is_virtual(self) -> bool:
        """Return True if this clock is a deterministic virtual clock."""

    @property
    @abstractmethod
    def speed(self) -> float:
        """Return current speed multiplier."""

    @speed.setter
    @abstractmethod
    def speed(self, value: float) -> None:
        """Set speed multiplier."""


class RealtimeClock(Clock):
    """Real-time clock with speed scaling, pause, resume, and step capabilities."""

    def __init__(self, initial_speed: float = 1.0) -> None:
        if initial_speed <= 0:
            msg = "Clock speed must be positive"
            raise ValueError(msg)
        self._speed: float = initial_speed
        self._start_wall_time: float = time.monotonic()
        self._sim_offset: float = 0.0
        self._is_paused: bool = False
        self._pause_event: asyncio.Event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
        self._pause_start_time: float = 0.0

    @property
    def is_virtual(self) -> bool:
        return False

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        if value <= 0:
            msg = "Clock speed must be positive"
            raise ValueError(msg)
        # Re-anchor time before changing speed
        current_now = self.now()
        self._start_wall_time = time.monotonic()
        self._sim_offset = current_now
        self._speed = value

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def pause(self) -> None:
        """Pause real-time progression."""
        if not self._is_paused:
            self._is_paused = True
            self._pause_start_time = time.monotonic()
            self._pause_event.clear()

    def resume(self) -> None:
        """Resume real-time progression."""
        if self._is_paused:
            paused_duration = time.monotonic() - self._pause_start_time
            self._start_wall_time += paused_duration
            self._is_paused = False
            self._pause_event.set()

    def now(self) -> float:
        if self._is_paused:
            wall_elapsed = self._pause_start_time - self._start_wall_time
        else:
            wall_elapsed = time.monotonic() - self._start_wall_time
        return self._sim_offset + (wall_elapsed * self._speed)

    async def sleep(self, delay: float) -> None:
        if delay <= 0:
            await asyncio.sleep(0)
            return

        # Wait until unpaused
        await self._pause_event.wait()
        real_delay = delay / self._speed
        await asyncio.sleep(real_delay)


@dataclass(order=True)
class _VirtualScheduledEvent:
    timestamp: float
    seq: int
    callback: Callable[[], Any] = field(compare=False)
    coroutine: Callable[[], Coroutine[Any, Any, Any]] | None = field(default=None, compare=False)


class VirtualClock(Clock):
    """Deterministic virtual clock for reproducible bit-for-bit runs."""

    def __init__(self, seed: int = 42, initial_time: float = 0.0) -> None:
        self._current_time: float = initial_time
        self._seed: int = seed
        self._rng: random.Random = random.Random(seed)
        self._event_queue: list[_VirtualScheduledEvent] = []
        self._seq: int = 0
        self._speed: float = 1.0

    @property
    def is_virtual(self) -> bool:
        return True

    @property
    def speed(self) -> float:
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        self._speed = max(0.01, value)

    @property
    def rng(self) -> random.Random:
        return self._rng

    def reset(self, seed: int | None = None, initial_time: float = 0.0) -> None:
        """Reset virtual clock and seeded RNG."""
        self._current_time = initial_time
        if seed is not None:
            self._seed = seed
        self._rng = random.Random(self._seed)
        self._event_queue.clear()
        self._seq = 0

    def now(self) -> float:
        return self._current_time

    def schedule(
        self,
        delay: float,
        callback: Callable[[], Any],
        coroutine: Callable[[], Coroutine[Any, Any, Any]] | None = None,
    ) -> int:
        """Schedule a callback at now + delay."""
        target_time = self._current_time + max(0.0, delay)
        self._seq += 1
        event = _VirtualScheduledEvent(
            timestamp=target_time,
            seq=self._seq,
            callback=callback,
            coroutine=coroutine,
        )
        heapq.heappush(self._event_queue, event)
        return self._seq

    async def sleep(self, delay: float) -> None:
        """In virtual clock mode, advance time deterministically."""
        target_time = self._current_time + max(0.0, delay)
        await self.run_until(target_time)

    def advance(self, delta: float) -> None:
        """Synchronously advance time by delta without running scheduled events."""
        if delta < 0:
            msg = "Time cannot move backwards"
            raise ValueError(msg)
        self._current_time += delta

    def has_pending_events(self) -> bool:
        return len(self._event_queue) > 0

    def next_event_time(self) -> float | None:
        if not self._event_queue:
            return None
        return self._event_queue[0].timestamp

    async def step(self) -> bool:
        """Execute the next scheduled event in virtual time. Returns False if queue empty."""
        if not self._event_queue:
            return False
        event = heapq.heappop(self._event_queue)
        if event.timestamp > self._current_time:
            self._current_time = event.timestamp

        res = event.callback()
        if asyncio.iscoroutine(res):
            await res
        if event.coroutine is not None:
            await event.coroutine()
        return True

    async def run_until(self, target_time: float) -> None:
        """Run all events scheduled up to target_time and set now() to target_time."""
        while self._event_queue and self._event_queue[0].timestamp <= target_time:
            await self.step()
        self._current_time = max(self._current_time, target_time)
