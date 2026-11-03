"""Censor lab tests: rule-based heuristics, trained model slot, and adaptive retraining."""

from __future__ import annotations

import time

import pytest
from phantomnet.censor.censors import AdaptiveCensor, RuleBasedCensor, TrainedClassifierCensor
from phantomnet.censor.interface import CensorAction
from phantomnet.censor.proxy import TokenBucket


def test_rule_based_censor_unshaped_vs_shaped() -> None:
    """Verify rule censor flags unshaped MTU bursts and allows shaped traffic."""
    censor = RuleBasedCensor(mtu_cluster_threshold=3, block_threshold=0.85)

    # 1. Unshaped flow: consecutive 1420-byte MTU packets
    now = time.time()
    decisions = []
    for i in range(6):
        d = censor.inspect(size=1420, direction="TX", timestamp=now + (i * 0.05))
        decisions.append(d)

    # Escalation from warmup to throttle/block
    assert decisions[-1].action in (CensorAction.BLOCK, CensorAction.THROTTLE)
    assert decisions[-1].score >= 0.60
    assert "MTU" in decisions[-1].reason

    # 2. Reset and test shaped flow: varied smaller packet sizes (cover profile)
    censor.reset()
    shaped_sizes = [256, 512, 128, 768, 512, 384, 512, 256]
    shaped_decisions = []
    for i, sz in enumerate(shaped_sizes):
        d = censor.inspect(size=sz, direction="TX", timestamp=now + (i * 0.1))
        shaped_decisions.append(d)

    # All shaped packets should remain under ALLOW
    assert all(d.action == CensorAction.ALLOW for d in shaped_decisions)
    assert shaped_decisions[-1].score < 0.35


def test_trained_classifier_censor_scoring() -> None:
    """Verify trained classifier slot calculates feature vectors and logistic boundary."""
    censor = TrainedClassifierCensor()

    now = time.time()
    # High mean size + low standard deviation => high suspicion score
    for i in range(10):
        censor.inspect(size=1420, direction="TX", timestamp=now + i * 0.02)

    decision = censor.inspect(size=1420, direction="TX", timestamp=now + 0.22)
    assert decision.score > 0.50
    assert "mean_size" in decision.metadata
    assert "std_size" in decision.metadata

    # Shaped traffic with high variance
    censor.reset()
    for i, sz in enumerate([100, 1400, 200, 1200, 300, 1100, 150, 900]):
        decision = censor.inspect(
            size=sz, direction="TX" if i % 2 == 0 else "RX", timestamp=now + i * 0.08
        )

    # High variance and mixed direction keeps score low
    assert decision.score < 0.55
    assert decision.action == CensorAction.ALLOW


def test_adaptive_censor_retraining() -> None:
    """Verify adaptive censor updates sensitivity and retrain round on persistent flows."""
    censor = AdaptiveCensor(retrain_interval=10)
    now = time.time()

    for i in range(25):
        d = censor.inspect(size=1420, direction="TX", timestamp=now + (i * 0.01))

    # Must have completed at least 2 retrain rounds
    assert censor.retrain_round >= 2
    assert d.metadata["retrain_round"] >= 2
    assert censor.sensitivity_multiplier > 1.0


@pytest.mark.asyncio
async def test_token_bucket_rate_limiter() -> None:
    """Verify token bucket rate limiter introduces appropriate delay when exhausted."""
    # 10,000 bytes/sec, capacity 5,000 bytes
    bucket = TokenBucket(rate_bps=10_000.0, capacity_bytes=5_000.0)

    # First packet within capacity: 0.0s delay
    delay1 = await bucket.consume(3000)
    assert delay1 == 0.0

    # Second packet exceeds remaining 2000 tokens: requires delay
    delay2 = await bucket.consume(3000)
    assert delay2 > 0.05
