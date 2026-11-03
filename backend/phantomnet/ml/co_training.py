"""Adversarial Co-Training loop between Censor and Defender Mask Policy.

Emits canonical TRAIN_ROUND and POLICY_DECISION events to PhantomEventBus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from phantomnet.bus import PhantomEventBus, global_event_bus
from phantomnet.data.traces import (
    generate_synthetic_site_flow,
    partition_disjoint_sites,
)
from phantomnet.events import EventKind, PhantomEvent
from phantomnet.ml.censor_models import RandomForestCensor
from phantomnet.ml.features import extract_flow_features
from phantomnet.ml.mask_engine import MaskEngine
from phantomnet.ml.tuner import CMAESTuner, TerrainScanner

if TYPE_CHECKING:
    from phantomnet.data.traces import FlowTrace


class AdversarialCoTrainer:
    """Orchestrates iterative co-training between the censor and mask defender."""

    def __init__(
        self,
        event_bus: PhantomEventBus | None = None,
        rounds: int = 5,
        seed: int = 42,
    ) -> None:
        self.event_bus = event_bus if event_bus is not None else global_event_bus
        self.rounds = rounds
        self.seed = seed
        self.censor = RandomForestCensor(n_estimators=50, max_depth=8, seed=seed)
        self.mask_engine = MaskEngine(seed=seed)
        self.tuner = CMAESTuner(seed=seed)
        self.terrain_scanner = TerrainScanner()
        self._seq = 1

    def run_co_training_loop(self) -> list[dict[str, Any]]:
        """Execute R rounds of co-training and emit typed spine events."""
        train_sites, val_sites, test_sites = partition_disjoint_sites(seed=self.seed)

        # Generate base flows for each site partition
        train_flows = [
            generate_synthetic_site_flow(
                s["site_id"], s["category"], is_tunnel=False, seed=self.seed + i
            )
            for i, s in enumerate(train_sites)
        ]
        val_flows = [
            generate_synthetic_site_flow(
                s["site_id"], s["category"], is_tunnel=False, seed=self.seed + 100 + i
            )
            for i, s in enumerate(val_sites)
        ]
        test_flows = [
            generate_synthetic_site_flow(
                s["site_id"], s["category"], is_tunnel=False, seed=self.seed + 200 + i
            )
            for i, s in enumerate(test_sites)
        ]

        # Extract features for unshaped baseline
        x_train_raw = np.array([extract_flow_features(f) for f in train_flows])
        x_test_raw = np.array([extract_flow_features(f) for f in test_flows])

        # Binary labels: 1 = tunnel/suspicious, 0 = regular web traffic
        # Initially, half are unencrypted web, half are plain tunnel
        y_train = np.array([1 if i % 2 == 0 else 0 for i in range(len(train_flows))])
        y_test = np.array([1 if i % 2 == 0 else 0 for i in range(len(test_flows))])

        # Initial Censor Training (Round 0)
        self.censor.fit(x_train_raw, y_train)
        self.censor.evaluate(x_test_raw, y_test)

        round_history: list[dict[str, Any]] = []

        # Terrain scanner selects starting mask
        current_mask = self.terrain_scanner.select_starting_mask()
        t_sim = 1.0

        for r in range(1, self.rounds + 1):
            t_sim += 1.0

            # 1. Defender Step: CMA-ES tunes mask parameters against current censor
            best_params, reward = self.tuner.tune_step(
                censor=self.censor,
                val_traces=val_flows,
                feature_extractor=extract_flow_features,
                engine=self.mask_engine,
            )
            current_mask = best_params

            # 2. Evaluate shaped flows against current censor
            shaped_test_flows: list[FlowTrace] = []
            bw_overheads: list[float] = []
            latency_costs: list[float] = []

            for f in test_flows:
                s_flow, metrics = self.mask_engine.shape_flow(f, current_mask)
                shaped_test_flows.append(s_flow)
                bw_overheads.append(metrics.bandwidth_overhead)
                latency_costs.append(metrics.latency_cost_ms)

            x_test_shaped = np.array([extract_flow_features(f) for f in shaped_test_flows])
            censor_shaped_metrics = self.censor.evaluate(x_test_shaped, y_test)

            mean_bw_overhead = float(np.mean(bw_overheads))
            mean_latency = float(np.mean(latency_costs))
            stealth_score = 1.0 - censor_shaped_metrics["auc"]
            attacker_loss = 1.0 - censor_shaped_metrics["auc"]
            defender_reward = reward

            # 3. Emit POLICY_DECISION event
            policy_event = PhantomEvent(
                version=1,
                seq=self._seq,
                t=round(t_sim, 2),
                kind=EventKind.POLICY_DECISION,
                mask_id=f"learned_r{r}",
                meta={
                    "round": r,
                    "reasoning": (
                        f"CMA-ES tuned bucket={current_mask.pad_bucket}B, "
                        f"jitter={current_mask.jitter_ms:.1f}ms, "
                        f"dummy={current_mask.dummy_rate:.2f}. "
                        f"Stealth={stealth_score:.3f}"
                    ),
                    "bandwidth_overhead": round(mean_bw_overhead * 100, 1),
                    "latency_cost_ms": round(mean_latency, 2),
                    "stealth_gain": round(stealth_score, 3),
                },
            )
            self._seq += 1
            self.event_bus.publish_sync(policy_event)

            # 4. Emit TRAIN_ROUND event
            train_event = PhantomEvent(
                version=1,
                seq=self._seq,
                t=round(t_sim + 0.2, 2),
                kind=EventKind.TRAIN_ROUND,
                meta={
                    "round": r,
                    "attacker_loss": round(attacker_loss, 4),
                    "defender_reward": round(defender_reward, 4),
                    "stealth": round(stealth_score, 4),
                    "overhead": round(mean_bw_overhead, 4),
                    "censor_auc": censor_shaped_metrics["auc"],
                },
            )
            self._seq += 1
            self.event_bus.publish_sync(train_event)

            round_record = {
                "round": r,
                "pad_bucket": current_mask.pad_bucket,
                "jitter_ms": current_mask.jitter_ms,
                "dummy_rate": current_mask.dummy_rate,
                "stealth": round(stealth_score, 4),
                "bandwidth_overhead": round(mean_bw_overhead, 4),
                "latency_cost_ms": round(mean_latency, 2),
                "censor_auc": censor_shaped_metrics["auc"],
                "attacker_loss": round(attacker_loss, 4),
                "defender_reward": round(defender_reward, 4),
            }
            round_history.append(round_record)

            # 5. Censor Retraining Step:
            # Retrain censor on a mixed dataset including newly shaped flows
            shaped_train_flows = [
                self.mask_engine.shape_flow(f, current_mask)[0] for f in train_flows
            ]
            x_train_shaped = np.array([extract_flow_features(f) for f in shaped_train_flows])

            x_mixed = np.vstack([x_train_raw, x_train_shaped])
            y_mixed = np.concatenate([y_train, y_train])

            self.censor.fit(x_mixed, y_mixed)

        return round_history
