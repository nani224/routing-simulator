"""CMA-ES optimization and Terrain Scanner for empirical traffic morphing tuning.

Gate J Requirement 3:
Minimizes a smooth fitness function combining:
1. Frozen censor's continuous mean predicted probability P(tunnel)
2. 1D Wasserstein distance (Earth Mover's Distance) to empirical TLS packet sizes and gaps
3. Bandwidth overhead percentage
4. Latency penalty

Logs the generation-by-generation fitness curve to /evidence/ml/fitness.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy.stats import wasserstein_distance

from phantomnet.ml.mask_engine import MaskEngine, MaskParameters
from phantomnet.ml.morphing import (
    EmpiricalTLSDistribution,
    MorphingParameters,
    TrafficMorpher,
)

if TYPE_CHECKING:
    from sklearn.ensemble import RandomForestClassifier

    from phantomnet.data.traces import FlowTrace

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FITNESS_JSON_FILE = REPO_ROOT / "evidence" / "ml" / "fitness.json"


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
    """Covariance Matrix Adaptation Evolution Strategy (CMA-ES) with smooth fitness."""

    def __init__(
        self,
        pop_size: int = 8,
        seed: int = 42,
    ) -> None:
        self.rng = np.random.RandomState(seed)
        self.dim = 8  # 8 MorphingParameters
        self.pop_size = pop_size
        self.mu = pop_size // 2

        # Mean vector in normalized space [0, 1]
        self.mean = np.array([0.5, 0.25, 0.2, 0.15, 0.35, 0.5, 0.3, 0.2], dtype=np.float64)
        self.sigma = 0.25
        self.cov = np.eye(self.dim, dtype=np.float64)

        # Recombination weights
        weights = math.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.weights = weights / np.sum(weights)

        self.fitness_history: list[dict[str, Any]] = []

    def _denormalize(self, norm_vec: np.ndarray) -> MorphingParameters:
        """Map normalized [0, 1] vector back to concrete MorphingParameters."""
        v = np.clip(norm_vec, 0.0, 1.0)
        morph_strength = float(v[0])
        size_bucket = int(32 + v[1] * 480)  # 32 to 512
        timing_quant = float(v[2] * 15.0)  # 0 to 15 ms
        dummy_rate = float(v[3] * 0.20)  # 0 to 20%
        hs_pad_m1 = int(v[4] * 350)  # 0 to 350 bytes
        hs_pad_m2 = int(v[5] * 700)  # 0 to 700 bytes
        hs_pad_m3 = int(v[6] * 250)  # 0 to 250 bytes
        hs_jitter = float(v[7] * 10.0)  # 0 to 10 ms

        return MorphingParameters(
            morph_strength=morph_strength,
            size_bucket=size_bucket,
            timing_quantization_ms=timing_quant,
            dummy_rate=dummy_rate,
            hs_pad_m1=hs_pad_m1,
            hs_pad_m2=hs_pad_m2,
            hs_pad_m3=hs_pad_m3,
            hs_jitter_ms=hs_jitter,
        )

    def optimize(
        self,
        censor: RandomForestClassifier,
        train_tunnel_flows: list[FlowTrace],
        train_tls_flows: list[FlowTrace],
        feature_extractor: Any,
        num_generations: int = 5,
        target_distribution: EmpiricalTLSDistribution | None = None,
    ) -> MorphingParameters:
        """Run CMA-ES optimization minimizing smooth multi-objective loss."""
        if target_distribution is None:
            target_distribution = EmpiricalTLSDistribution()
            target_distribution.fit_from_flows(train_tls_flows)

        target_tx_sizes = target_distribution.tx_sizes
        target_tx_gaps = target_distribution.tx_gaps

        best_overall_params = self._denormalize(self.mean)
        best_overall_loss = float("inf")

        sample_flows = train_tunnel_flows[:16]  # Subsample for fast evaluation

        for gen in range(1, num_generations + 1):
            cov_reg = self.cov + np.eye(self.dim) * 1e-4
            samples = self.rng.multivariate_normal(
                self.mean, (self.sigma**2) * cov_reg, size=self.pop_size
            )

            candidate_params = [self._denormalize(s) for s in samples]
            candidate_losses: list[float] = []
            candidate_details: list[dict[str, float]] = []

            for params in candidate_params:
                morpher = TrafficMorpher(target_distribution, params, seed=42 + gen)
                shaped_results = [morpher.morph_flow(f) for f in sample_flows]
                shaped_flows = [r[0] for r in shaped_results]
                evals = [r[1] for r in shaped_results]

                # 1. Feature extraction & censor probability
                feats = np.array([feature_extractor(f) for f in shaped_flows])
                probs = censor.predict_proba(feats)[:, 1]
                mean_censor_p = float(np.mean(probs))

                # 2. Wasserstein distance on packet sizes and gaps
                shaped_sizes: list[int] = []
                shaped_gaps: list[float] = []
                for f in shaped_flows:
                    for p in f.packets:
                        if p.direction == "TX":
                            shaped_sizes.append(p.size)
                            if p.dt > 0:
                                shaped_gaps.append(p.dt)

                w_size = (
                    float(wasserstein_distance(shaped_sizes, target_tx_sizes))
                    if shaped_sizes
                    else 100.0
                )
                w_gap = (
                    float(wasserstein_distance(shaped_gaps, target_tx_gaps))
                    if shaped_gaps
                    else 0.05
                )

                bw_over = float(np.mean([e.bandwidth_overhead for e in evals]))
                lat_cost = float(np.mean([e.latency_cost_ms for e in evals]))

                # Smooth continuous loss function (minimization)
                loss = (
                    mean_censor_p
                    + (0.001 * w_size)
                    + (0.01 * w_gap)
                    + (0.4 * bw_over)
                    + (0.02 * lat_cost)
                )

                candidate_losses.append(loss)
                candidate_details.append(
                    {
                        "censor_p": mean_censor_p,
                        "w_size": w_size,
                        "w_gap": w_gap,
                        "bw_overhead": bw_over,
                        "latency_ms": lat_cost,
                    }
                )

            # Sort ascending (minimization)
            ranked_idx = np.argsort(candidate_losses)
            best_gen_idx = int(ranked_idx[0])
            best_gen_loss = candidate_losses[best_gen_idx]
            best_gen_params = candidate_params[best_gen_idx]

            if best_gen_loss < best_overall_loss:
                best_overall_loss = best_gen_loss
                best_overall_params = best_gen_params

            # Log generation metrics
            gen_log = {
                "generation": gen,
                "best_loss": round(best_gen_loss, 4),
                "mean_censor_p": round(candidate_details[best_gen_idx]["censor_p"], 4),
                "w_size_distance": round(candidate_details[best_gen_idx]["w_size"], 4),
                "w_gap_distance": round(candidate_details[best_gen_idx]["w_gap"], 4),
                "bandwidth_overhead_pct": round(
                    candidate_details[best_gen_idx]["bw_overhead"] * 100.0, 2
                ),
                "latency_cost_ms": round(candidate_details[best_gen_idx]["latency_ms"], 3),
            }
            self.fitness_history.append(gen_log)

            # CMA update
            selected_samples = samples[ranked_idx[: self.mu]]
            old_mean = self.mean.copy()
            self.mean = np.dot(self.weights, selected_samples)

            diff = selected_samples - old_mean
            self.cov = np.dot(self.weights * diff.T, diff) / (self.sigma**2 + 1e-6)
            self.sigma = max(0.05, self.sigma * 0.95)

        # Export fitness.json
        FITNESS_JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(FITNESS_JSON_FILE, "w", encoding="utf-8") as out_f:
            json.dump(
                {
                    "optimizer": "CMA-ES (Covariance Matrix Adaptation Evolution Strategy)",
                    "objective": "Smooth Multi-Objective Loss (P(tunnel) + Wasserstein + Overhead)",
                    "generations_run": num_generations,
                    "population_size": self.pop_size,
                    "fitness_curve": self.fitness_history,
                },
                out_f,
                indent=2,
            )

        return best_overall_params

    def tune_step(
        self,
        censor: Any,
        val_traces: list[FlowTrace],
        feature_extractor: Any,
        engine: MaskEngine,
    ) -> tuple[MaskParameters, float]:
        """Backward-compatible tune step for legacy MaskEngine."""
        _ = censor
        _ = feature_extractor
        norm_vec = self.rng.uniform(0.0, 1.0, size=10)
        p = MaskParameters(
            pad_bucket=int(32 + norm_vec[0] * 480),
            jitter_ms=float(norm_vec[1] * 15.0),
            dummy_rate=float(norm_vec[2] * 0.25),
            burst_chop=int(3 + norm_vec[3] * 12),
            morph_ratio=float(norm_vec[4] * 0.8),
            hs_pad_m1=int(norm_vec[5] * 450),
            hs_pad_m2=int(norm_vec[6] * 650),
            hs_pad_m3=int(norm_vec[7] * 250),
            hs_preamble_count=int(round(norm_vec[8] * 2.0)),
            hs_jitter_ms=float(norm_vec[9] * 15.0),
        )
        rewards = []
        for trace in val_traces[:4]:
            _, eval_m = engine.shape_flow(trace, p, censor_confidence=0.5)
            rewards.append(eval_m.reward)
        return p, float(np.mean(rewards))
