"""Three concrete censor implementations behind the common metadata inspection interface."""

from __future__ import annotations

import collections
import math
from typing import Any

from phantomnet.censor.interface import BaseCensor, CensorAction, CensorDecision


class RuleBasedCensor(BaseCensor):
    """Inspects packet sizes and inter-arrival gaps using fixed heuristic rules."""

    def __init__(
        self,
        name: str = "rule-heuristic-censor",
        window_size: int = 10,
        mtu_cluster_threshold: int = 4,
        block_threshold: float = 0.90,
        throttle_threshold: float = 0.60,
    ) -> None:
        super().__init__(name)
        self.window_size = window_size
        self.mtu_cluster_threshold = mtu_cluster_threshold
        self.block_threshold = block_threshold
        self.throttle_threshold = throttle_threshold

        self._sizes: collections.deque[int] = collections.deque(maxlen=window_size)
        self._timestamps: collections.deque[float] = collections.deque(maxlen=window_size)

    def inspect(self, size: int, direction: str, timestamp: float) -> CensorDecision:
        del direction  # Heuristics operate on packet size/time distribution
        self._sizes.append(size)
        self._timestamps.append(timestamp)

        if len(self._sizes) < 3:
            return CensorDecision(
                score=0.10,
                action=CensorAction.ALLOW,
                confidence=0.20,
                reason="Warmup baseline",
            )

        # Heuristic 1: Cluster of unshaped MTU-sized packets (1400 - 1500 bytes)
        mtu_count = sum(1 for s in self._sizes if 1400 <= s <= 1500)
        # Heuristic 2: Low variance in packet size indicates unshaped plain tunnel
        mean_size = sum(self._sizes) / len(self._sizes)
        var_size = sum((s - mean_size) ** 2 for s in self._sizes) / len(self._sizes)
        std_size = math.sqrt(var_size)

        score = 0.10
        if mtu_count >= self.mtu_cluster_threshold:
            score += 0.50 + min(0.35, (mtu_count - self.mtu_cluster_threshold) * 0.10)
        if std_size < 50.0 and mean_size > 1000:
            score += 0.30

        score = min(1.0, max(0.05, score))
        confidence = round(min(0.99, score * 1.05), 2)

        if score >= self.block_threshold:
            action = CensorAction.BLOCK
            reason = f"Unshaped MTU cluster detected ({mtu_count} packets in window >= 1400B)"
        elif score >= self.throttle_threshold:
            action = CensorAction.THROTTLE
            reason = (
                f"Suspicious uniform large frame distribution "
                f"(mean={mean_size:.1f}B, std={std_size:.1f}B)"
            )
        else:
            action = CensorAction.ALLOW
            reason = "Flow matches normal randomized/shaped traffic profile"

        return CensorDecision(
            score=round(score, 3),
            action=action,
            confidence=confidence,
            reason=reason,
            metadata={
                "mtu_count": mtu_count,
                "mean_size": round(mean_size, 1),
                "std_size": round(std_size, 1),
            },
        )

    def reset(self) -> None:
        self._sizes.clear()
        self._timestamps.clear()


class TrainedClassifierCensor(BaseCensor):
    """Model slot censor evaluating logistic scoring over rolling feature vectors."""

    def __init__(
        self,
        name: str = "trained-classifier-slot",
        window_size: int = 15,
        weights: dict[str, float] | None = None,
        bias: float = -2.5,
    ) -> None:
        super().__init__(name)
        self.window_size = window_size
        self.bias = bias
        # Pre-trained weights for feature vector [mean_size/1000, std/1000, tx_ratio, gap]
        self.weights = weights or {
            "norm_mean_size": 3.8,
            "norm_std_size": -2.2,
            "tx_ratio": 1.2,
            "mean_gap_s": -1.5,
        }

        self._history: collections.deque[tuple[int, str, float]] = collections.deque(
            maxlen=window_size
        )

    def inspect(self, size: int, direction: str, timestamp: float) -> CensorDecision:
        self._history.append((size, direction, timestamp))

        if len(self._history) < 4:
            return CensorDecision(
                score=0.12,
                action=CensorAction.ALLOW,
                confidence=0.25,
                reason="Collecting feature vector samples",
            )

        sizes = [item[0] for item in self._history]
        dirs = [item[1] for item in self._history]
        times = [item[2] for item in self._history]

        mean_size = sum(sizes) / len(sizes)
        var_size = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)
        std_size = math.sqrt(var_size)
        tx_ratio = sum(1 for d in dirs if d == "TX") / len(dirs)

        gaps = [times[i] - times[i - 1] for i in range(1, len(times))]
        mean_gap = sum(gaps) / len(gaps) if gaps else 0.05

        # Feature normalization
        x1 = mean_size / 1000.0
        x2 = std_size / 1000.0
        x3 = tx_ratio
        x4 = min(1.0, mean_gap)

        logit = (
            self.weights["norm_mean_size"] * x1
            + self.weights["norm_std_size"] * x2
            + self.weights["tx_ratio"] * x3
            + self.weights["mean_gap_s"] * x4
            + self.bias
        )

        score = 1.0 / (1.0 + math.exp(-max(-15.0, min(15.0, logit))))
        confidence = round(min(0.99, abs(score - 0.5) * 2), 2)

        if score >= 0.85:
            action = CensorAction.BLOCK
            reason = f"Classifier probability {score:.2f} >= 0.85 block boundary"
        elif score >= 0.55:
            action = CensorAction.THROTTLE
            reason = f"Classifier probability {score:.2f} in throttle zone"
        else:
            action = CensorAction.ALLOW
            reason = f"Classifier probability {score:.2f} below threshold (evasion successful)"

        return CensorDecision(
            score=round(score, 3),
            action=action,
            confidence=confidence,
            reason=reason,
            metadata={
                "mean_size": round(mean_size, 1),
                "std_size": round(std_size, 1),
                "tx_ratio": round(tx_ratio, 2),
                "mean_gap_ms": round(mean_gap * 1000, 1),
            },
        )

    def reset(self) -> None:
        self._history.clear()


class AdaptiveCensor(BaseCensor):
    """Online adaptive censor that tracks flow histories and retrains thresholds dynamically."""

    def __init__(
        self,
        name: str = "adaptive-retraining-censor",
        retrain_interval: int = 20,
    ) -> None:
        super().__init__(name)
        self.retrain_interval = retrain_interval
        self.total_packets_seen = 0
        self.retrain_round = 0
        self.sensitivity_multiplier = 1.0

        self._base_censor = TrainedClassifierCensor(name=f"{name}-base")
        self._recent_suspicious_count = 0

    def inspect(self, size: int, direction: str, timestamp: float) -> CensorDecision:
        self.total_packets_seen += 1
        decision = self._base_censor.inspect(size, direction, timestamp)

        if decision.action != CensorAction.ALLOW:
            self._recent_suspicious_count += 1

        # Periodic adaptive retrain step
        if self.total_packets_seen % self.retrain_interval == 0:
            self.retrain_round += 1
            if self._recent_suspicious_count >= 5:
                # Flow is persistently evasive or unshaped; increase sensitivity
                self.sensitivity_multiplier = min(2.5, self.sensitivity_multiplier + 0.3)
                self._base_censor.bias += 0.4
            else:
                self.sensitivity_multiplier = max(0.8, self.sensitivity_multiplier - 0.1)

            self._recent_suspicious_count = 0

        adapted_score = min(1.0, decision.score * self.sensitivity_multiplier)
        if adapted_score >= 0.85:
            action = CensorAction.BLOCK
            reason = (
                f"Adaptive censor (round {self.retrain_round}) slammed gate "
                f"(score={adapted_score:.2f})"
            )
        elif adapted_score >= 0.55:
            action = CensorAction.THROTTLE
            reason = (
                f"Adaptive censor (round {self.retrain_round}) rate limiting "
                f"(score={adapted_score:.2f})"
            )
        else:
            action = CensorAction.ALLOW
            reason = f"Adaptive censor (round {self.retrain_round}) allowed flow"

        meta: dict[str, Any] = dict(decision.metadata)
        meta["retrain_round"] = self.retrain_round
        meta["sensitivity"] = round(self.sensitivity_multiplier, 2)

        return CensorDecision(
            score=round(adapted_score, 3),
            action=action,
            confidence=decision.confidence,
            reason=reason,
            metadata=meta,
        )

    def reset(self) -> None:
        self.total_packets_seen = 0
        self.retrain_round = 0
        self.sensitivity_multiplier = 1.0
        self._recent_suspicious_count = 0
        self._base_censor.reset()
