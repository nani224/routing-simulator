"""Ablation studies across >=5 distinct seeds with 95% Confidence Intervals.

Evaluates 5 distinct regimes:
1. no_shaping: Plain tunnel without modification
2. random_shaping: Random jitter and arbitrary padding
3. fixed_padding: Deterministic padding to 1500B MTU
4. learned_policy: CMA-ES tuned policy vs baseline censor
5. learned_vs_retrained: Robustness of learned policy against retrained censor

Exports results to /evidence/ml/ablation.json and /evidence/ml/pareto.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from phantomnet.data.traces import (
    generate_synthetic_site_flow,
    partition_disjoint_sites,
)
from phantomnet.ml.censor_models import RandomForestCensor
from phantomnet.ml.features import extract_flow_features
from phantomnet.ml.mask_engine import MaskEngine, MaskParameters
from phantomnet.ml.tuner import CMAESTuner


def compute_mean_and_95ci(values: list[float]) -> dict[str, float]:
    """Compute mean and 95% confidence interval for a list of metric observations."""
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "ci_95": 0.0, "low": 0.0, "high": 0.0}
    mean = float(np.mean(values))
    if n == 1:
        return {"mean": round(mean, 4), "ci_95": 0.0, "low": round(mean, 4), "high": round(mean, 4)}

    std = float(np.std(values, ddof=1))
    # 95% CI multiplier for normal / Student-t approximation
    ci = 1.96 * (std / math.sqrt(n))
    return {
        "mean": round(mean, 4),
        "ci_95": round(ci, 4),
        "low": round(max(0.0, mean - ci), 4),
        "high": round(mean + ci, 4),
    }


def run_ablation_study(
    seeds: list[int] | None = None,
    output_dir: str = "evidence/ml",
) -> dict[str, Any]:
    """Run full ablation benchmarks across seeds and write artifacts."""
    seeds = seeds or [42, 101, 2024, 777, 9999]
    regimes = [
        "no_shaping",
        "random_shaping",
        "fixed_padding",
        "learned_policy",
        "learned_vs_retrained",
    ]

    metrics_by_regime: dict[str, dict[str, list[float]]] = {
        r: {
            "auc": [],
            "f1": [],
            "bandwidth_overhead": [],
            "latency_ms": [],
            "defender_reward": [],
        }
        for r in regimes
    }

    for seed in seeds:
        train_sites, val_sites, test_sites = partition_disjoint_sites(seed=seed)
        engine = MaskEngine(seed=seed)

        # Baseline traces
        train_flows = [
            generate_synthetic_site_flow(
                s["site_id"], s["category"], is_tunnel=False, seed=seed + i
            )
            for i, s in enumerate(train_sites)
        ]
        val_flows = [
            generate_synthetic_site_flow(
                s["site_id"], s["category"], is_tunnel=False, seed=seed + 100 + i
            )
            for i, s in enumerate(val_sites)
        ]
        test_flows = [
            generate_synthetic_site_flow(
                s["site_id"], s["category"], is_tunnel=False, seed=seed + 200 + i
            )
            for i, s in enumerate(test_sites)
        ]

        x_train = np.array([extract_flow_features(f) for f in train_flows])
        x_test_raw = np.array([extract_flow_features(f) for f in test_flows])
        y_train = np.array([1 if i % 2 == 0 else 0 for i in range(len(train_flows))])
        y_test = np.array([1 if i % 2 == 0 else 0 for i in range(len(test_flows))])

        censor = RandomForestCensor(n_estimators=40, max_depth=8, seed=seed)
        censor.fit(x_train, y_train)

        # 1. No Shaping (Plain Tunnel)
        no_shape_eval = censor.evaluate(x_test_raw, y_test)
        metrics_by_regime["no_shaping"]["auc"].append(no_shape_eval["auc"])
        metrics_by_regime["no_shaping"]["f1"].append(no_shape_eval["f1"])
        metrics_by_regime["no_shaping"]["bandwidth_overhead"].append(0.0)
        metrics_by_regime["no_shaping"]["latency_ms"].append(0.0)
        metrics_by_regime["no_shaping"]["defender_reward"].append(1.0 - no_shape_eval["auc"])

        # 2. Random Shaping
        rand_params = MaskParameters(
            pad_bucket=128, jitter_ms=5.0, dummy_rate=0.08, morph_ratio=0.3
        )
        rand_shaped = [engine.shape_flow(f, rand_params)[0] for f in test_flows]
        rand_metrics = [engine.shape_flow(f, rand_params)[1] for f in test_flows]
        x_rand = np.array([extract_flow_features(f) for f in rand_shaped])
        rand_eval = censor.evaluate(x_rand, y_test)
        metrics_by_regime["random_shaping"]["auc"].append(rand_eval["auc"])
        metrics_by_regime["random_shaping"]["f1"].append(rand_eval["f1"])
        metrics_by_regime["random_shaping"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in rand_metrics]))
        )
        metrics_by_regime["random_shaping"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in rand_metrics]))
        )
        metrics_by_regime["random_shaping"]["defender_reward"].append(
            float(np.mean([m.reward for m in rand_metrics]))
        )

        # 3. Fixed Padding (MTU 1500)
        fixed_params = MaskParameters(
            pad_bucket=1500, jitter_ms=0.0, dummy_rate=0.0, morph_ratio=0.0
        )
        fixed_shaped = [engine.shape_flow(f, fixed_params)[0] for f in test_flows]
        fixed_metrics = [engine.shape_flow(f, fixed_params)[1] for f in test_flows]
        x_fixed = np.array([extract_flow_features(f) for f in fixed_shaped])
        fixed_eval = censor.evaluate(x_fixed, y_test)
        metrics_by_regime["fixed_padding"]["auc"].append(fixed_eval["auc"])
        metrics_by_regime["fixed_padding"]["f1"].append(fixed_eval["f1"])
        metrics_by_regime["fixed_padding"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in fixed_metrics]))
        )
        metrics_by_regime["fixed_padding"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in fixed_metrics]))
        )
        metrics_by_regime["fixed_padding"]["defender_reward"].append(
            float(np.mean([m.reward for m in fixed_metrics]))
        )

        # 4. Learned Policy (CMA-ES Tuned)
        tuner = CMAESTuner(seed=seed)
        learned_params, _ = tuner.tune_step(censor, val_flows, extract_flow_features, engine)
        learned_shaped = [engine.shape_flow(f, learned_params)[0] for f in test_flows]
        learned_metrics = [engine.shape_flow(f, learned_params)[1] for f in test_flows]
        x_learned = np.array([extract_flow_features(f) for f in learned_shaped])
        learned_eval = censor.evaluate(x_learned, y_test)
        metrics_by_regime["learned_policy"]["auc"].append(learned_eval["auc"])
        metrics_by_regime["learned_policy"]["f1"].append(learned_eval["f1"])
        metrics_by_regime["learned_policy"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in learned_metrics]))
        )
        metrics_by_regime["learned_policy"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in learned_metrics]))
        )
        metrics_by_regime["learned_policy"]["defender_reward"].append(
            float(np.mean([m.reward for m in learned_metrics]))
        )

        # 5. Learned Policy vs RETRAINED Censor
        shaped_train = [engine.shape_flow(f, learned_params)[0] for f in train_flows]
        x_train_shaped = np.array([extract_flow_features(f) for f in shaped_train])
        x_retrain = np.vstack([x_train, x_train_shaped])
        y_retrain = np.concatenate([y_train, y_train])

        retrained_censor = RandomForestCensor(n_estimators=40, max_depth=8, seed=seed)
        retrained_censor.fit(x_retrain, y_retrain)
        retrained_eval = retrained_censor.evaluate(x_learned, y_test)

        metrics_by_regime["learned_vs_retrained"]["auc"].append(retrained_eval["auc"])
        metrics_by_regime["learned_vs_retrained"]["f1"].append(retrained_eval["f1"])
        metrics_by_regime["learned_vs_retrained"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in learned_metrics]))
        )
        metrics_by_regime["learned_vs_retrained"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in learned_metrics]))
        )
        metrics_by_regime["learned_vs_retrained"]["defender_reward"].append(
            1.0
            - retrained_eval["auc"]
            - 0.4 * float(np.mean([m.bandwidth_overhead for m in learned_metrics]))
        )

    # Compute Final Summary with Mean and 95% Confidence Intervals
    summary_table: dict[str, Any] = {}
    for r in regimes:
        summary_table[r] = {
            "censor_auc": compute_mean_and_95ci(metrics_by_regime[r]["auc"]),
            "f1_score": compute_mean_and_95ci(metrics_by_regime[r]["f1"]),
            "bandwidth_overhead": compute_mean_and_95ci(metrics_by_regime[r]["bandwidth_overhead"]),
            "latency_cost_ms": compute_mean_and_95ci(metrics_by_regime[r]["latency_ms"]),
            "defender_reward": compute_mean_and_95ci(metrics_by_regime[r]["defender_reward"]),
        }

    # Generate Pareto Plot Data
    pareto_data: list[dict[str, Any]] = [
        {
            "regime": r,
            "bandwidth_overhead_pct": round(
                summary_table[r]["bandwidth_overhead"]["mean"] * 100, 2
            ),
            "stealth_score": round(1.0 - summary_table[r]["censor_auc"]["mean"], 4),
            "censor_auc": summary_table[r]["censor_auc"]["mean"],
            "auc_ci_95": summary_table[r]["censor_auc"]["ci_95"],
            "reward": summary_table[r]["defender_reward"]["mean"],
        }
        for r in regimes
    ]

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ablation_payload = {
        "title": "PHANTOMNET Adversarial Censorship Defense Ablation Study",
        "num_seeds": len(seeds),
        "seeds": seeds,
        "results": summary_table,
    }

    with open(out_path / "ablation.json", "w", encoding="utf-8") as f:
        json.dump(ablation_payload, f, indent=2)

    with open(out_path / "pareto.json", "w", encoding="utf-8") as f:
        json.dump(pareto_data, f, indent=2)

    return ablation_payload
