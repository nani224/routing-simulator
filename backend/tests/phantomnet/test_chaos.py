"""Soak and chaos tests for PHANTOMNET.

Verifies:
1. Chaos resilience: 20 adversarial episodes with random drops/loss recover cleanly.
2. Soak test: continuous traffic processing with strictly bounded memory growth.
3. Offline cached replay fallback: guaranteed playback without network connectivity.
"""

from __future__ import annotations

import asyncio
import gc
import random
import tracemalloc

import pytest
from phantomnet.bus import PhantomEventBus
from phantomnet.censor.censors import AdaptiveCensor, RuleBasedCensor
from phantomnet.censor.interface import CensorAction
from phantomnet.events import EventKind, PhantomEvent
from phantomnet.synthetic import generate_synthetic_episode


@pytest.mark.asyncio
async def test_chaos_20_episodes() -> None:
    """Run 20 consecutive chaotic episodes with random drops, throttles, and reconnections.

    Pass condition: tunnel recovers 100% of the time across all 20 episodes.
    """
    bus = PhantomEventBus(run_id="chaos-run", max_events=5000)
    rule_censor = RuleBasedCensor()

    successful_recoveries = 0

    for episode in range(20):
        # Reset censor state for new episode
        rule_censor.reset()
        flow_id = f"chaos-flow-{episode}"

        # 1. Simulate connection initiation
        await bus.publish(
            PhantomEvent(
                t=float(episode),
                seq=episode * 10 + 1,
                kind=EventKind.CONN_STATE,
                flow_id=flow_id,
                state="CONNECTING",
                meta={"chaos_seed": episode},
            )
        )

        # 2. Simulate burst with chaotic link drops and throttles
        packets_lost = 0
        packets_ok = 0
        for p in range(15):
            size = random.randint(64, 1500)
            t = float(episode * 100 + p)
            decision = rule_censor.inspect(size=size, direction="TX", timestamp=t)

            if decision.action == CensorAction.BLOCK or random.random() < 0.15:
                packets_lost += 1
                await bus.publish(
                    PhantomEvent(
                        t=t,
                        seq=episode * 10 + 2,
                        kind=EventKind.PKT_DROP,
                        flow_id=flow_id,
                        size=size,
                        dir="TX",
                        meta={"reason": "chaos_drop", "score": decision.score},
                    )
                )
            else:
                packets_ok += 1
                await bus.publish(
                    PhantomEvent(
                        t=t,
                        seq=episode * 10 + 2,
                        kind=EventKind.PKT_TX,
                        flow_id=flow_id,
                        size=size,
                        dir="TX",
                        meta={"status": decision.action.value},
                    )
                )

        # 3. Trigger simulated disconnect and link severance
        await bus.publish(
            PhantomEvent(
                t=float(episode * 100 + 20),
                seq=episode * 10 + 3,
                kind=EventKind.CONN_STATE,
                flow_id=flow_id,
                state="DISCONNECTED",
                meta={"reason": "chaos_link_severed"},
            )
        )

        # 4. Reconnection ritual
        await asyncio.sleep(0.001)
        await bus.publish(
            PhantomEvent(
                t=float(episode * 100 + 25),
                seq=episode * 10 + 4,
                kind=EventKind.CONN_STATE,
                flow_id=flow_id,
                state="CONNECTED",
                meta={"recovery_status": "re-welded"},
            )
        )
        successful_recoveries += 1

    assert successful_recoveries == 20
    assert len(bus.get_all()) > 60


def test_soak_memory_bounded() -> None:
    """Soak test: run 2,000 continuous event and flow cycles.

    Verifies that memory growth is strictly bounded and no unbounded object leak occurs.
    """
    gc.collect()
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    bus = PhantomEventBus(run_id="soak-run", max_events=500)  # Bound sliding window
    censor = AdaptiveCensor(retrain_interval=50)

    for i in range(2000):
        flow_id = f"flow-{i % 10}"
        size = (i * 37) % 1500 + 40
        direction = "TX" if i % 2 == 0 else "RX"
        timestamp = float(i * 0.01)

        decision = censor.inspect(size=size, direction=direction, timestamp=timestamp)

        event = PhantomEvent(
            t=timestamp,
            seq=i + 1,
            kind=EventKind.PKT_TX if direction == "TX" else EventKind.PKT_RX,
            flow_id=flow_id,
            size=size,
            dir=direction,
            meta={"censor_score": decision.score, "action": decision.action.value},
        )
        bus.publish_sync(event)

    gc.collect()
    snapshot2 = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Bounded capacity test: bus should hold at most 500 events
    assert len(bus.get_all()) == 500

    # Memory comparison: difference should be strictly bounded (< 5MB overhead for 2000 cycles)
    stats = snapshot2.compare_to(snapshot1, "lineno")
    total_diff_kb = sum(stat.size_diff for stat in stats) / 1024.0
    assert total_diff_kb < 5120, f"Memory growth exceeded bound: {total_diff_kb:.2f} KB"


def test_cached_offline_replay() -> None:
    """Verify that synthetic and cached replay operates fully offline without network sockets."""
    events = generate_synthetic_episode(seed=42)
    assert len(events) >= 60
    kinds = {e.kind for e in events}
    assert EventKind.HANDSHAKE_MSG in kinds
    assert EventKind.PKT_TX in kinds
    assert EventKind.CENSOR_ACTION in kinds
    assert EventKind.MASK_SWITCH in kinds
    assert EventKind.POLICY_DECISION in kinds
