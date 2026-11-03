"""CMA-ES optimization and Terrain Scanner multi-armed bandit for policy parameter tuning."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

from phantomnet.ml.mask_engine import MaskEngine, MaskParameters

if TYPE_CHECKING:
    from phantomnet.data.traces import FlowTrace
    from phantomnet.ml.censor_models import RandomForestCensor


class TerrainScanner:
    """Multi-Armed Bandit using UCB1 to select initial mask profile based on network terrain."""

    def __init__(self, candidates: list[MaskParameters] | None = None) -> None:
        self.candidates = candidates or [
            MaskParameters(
                pad_bucket=64, jitter_ms=1.0, dummy_rate=0.02, burst_chop=10, morph_ratio=0.1
            ),
            MaskParameters(
                pad_bucket=128, jitter_ms=3.0, dummy_rate=0.05, burst_chop=8, morph_ratio=0.25
            ),
            MaskParameters(
                pad_bucket=256, jitter_ms=5.0, dummy_rate=0.10, burst_chop=6, morph_ratio=0.4
            ),
            MaskParameters(
                pad_bucket=512, jitter_ms=8.0, dummy_rate=0.15, burst_chop=4, morph_ratio=0.6
            ),
        ]
        self.counts = [0] * len(self.candidates)
        self.rewards = [0.0] * len(self.candidates)
        self.total_pulls = 0

    def select_starting_mask(self) -> MaskParameters:
        """Select mask candidate maximizing Upper Confidence Bound (UCB1)."""
        self.total_pulls += 1
        for i, count in enumerate(self.counts):
            if count == 0:
                self.counts[i] += 1
                return self.candidates[i]

        ucb_values: list[float] = []
        for i in range(len(self.candidates)):
            mean_reward = self.rewards[i] / float(self.counts[i])
            bonus = math.sqrt((2.0 * math.log(self.total_pulls)) / float(self.counts[i]))
            ucb_values.append(mean_reward + bonus)

        best_idx = int(np.argmax(ucb_values))
        self.counts[best_idx] += 1
        return self.candidates[best_idx]

    def update(self, idx: int, reward: float) -> None:
        self.rewards[idx] += reward


class CMAESTuner:
    """Covariance Matrix Adaptation Evolution Strategy (CMA-ES) for mask parameter optimization."""

    def __init__(
        self,
        initial_params: MaskParameters | None = None,
        pop_size: int = 8,
        seed: int = 42,
    ) -> None:
        self.rng = np.random.RandomState(seed)
        self.initial_params = initial_params or MaskParameters()
        self.dim = 5
        self.pop_size = pop_size
        self.mu = pop_size // 2

        # Mean vector in normalized space [0, 1]
        self.mean = np.array([0.25, 0.2, 0.15, 0.4, 0.25], dtype=np.float64)
        self.sigma = 0.2
        self.cov = np.eye(self.dim, dtype=np.float64)

        # Recombination weights
        weights = math.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.weights = weights / np.sum(weights)

    def _denormalize(self, norm_vec: np.ndarray) -> MaskParameters:
        """Map normalized [0, 1] parameters back to concrete MaskParameters."""
        v = np.clip(norm_vec, 0.0, 1.0)
        pad = int(32 + v[0] * 480)  # 32 to 512
        jitter = float(v[1] * 15.0)  # 0 to 15ms
        dummy = float(v[2] * 0.25)  # 0 to 25%
        chop = int(3 + v[3] * 12)  # 3 to 15
        morph = float(v[4] * 0.8)  # 0 to 0.8

        return MaskParameters(
            pad_bucket=pad,
            jitter_ms=jitter,
            dummy_rate=dummy,
            burst_chop=chop,
            morph_ratio=morph,
        )

    def tune_step(
        self,
        censor: RandomForestCensor,
        val_traces: list[FlowTrace],
        feature_extractor: Any,
        engine: MaskEngine,
    ) -> tuple[MaskParameters, float]:
        """Perform one generation of CMA-ES and return best candidate and reward."""
        # 1. Sample population
        # Regularize cov to guarantee positive-definiteness
        cov_reg = self.cov + np.eye(self.dim) * 1e-4
        samples = self.rng.multivariate_normal(
            self.mean, (self.sigma**2) * cov_reg, size=self.pop_size
        )

        candidate_params = [self._denormalize(s) for s in samples]
        fitness_scores: list[float] = []

        # 2. Evaluate each candidate against censor on validation flows
        for p in candidate_params:
            batch_rewards: list[float] = []
            for trace in val_traces[:4]:  # Sample representative flows
                shaped_trace, _ = engine.shape_flow(trace, p, censor_confidence=0.5)
                feat = feature_extractor(shaped_trace)
                censor_prob = float(censor.predict_proba(feat.reshape(1, -1))[0, 1])

                _, eval_metrics = engine.shape_flow(trace, p, censor_confidence=censor_prob)
                batch_rewards.append(eval_metrics.reward)

            fitness_scores.append(float(np.mean(batch_rewards)))

        # 3. Sort by descending reward (maximization)
        ranked_indices = np.argsort(fitness_scores)[::-1]
        best_idx = int(ranked_indices[0])
        best_params = candidate_params[best_idx]
        best_reward = fitness_scores[best_idx]

        # 4. Update distribution mean and covariance
        selected_samples = samples[ranked_indices[: self.mu]]
        old_mean = self.mean.copy()
        self.mean = np.dot(self.weights, selected_samples)

        # Adapt step size and covariance
        diff = selected_samples - old_mean
        self.cov = np.dot(self.weights * diff.T, diff) / (self.sigma**2 + 1e-6)
        # Bounded decay for step size
        self.sigma = max(0.05, self.sigma * 0.95)

        return best_params, best_reward
