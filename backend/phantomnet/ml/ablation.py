"""Ablation studies across >=10 distinct seeds with 95% Confidence Intervals.

Evaluates 5 distinct regimes on REAL traffic across held-out disjoint sites:
1. no_shaping: Plain tunnel without modification vs direct
2. random_shaping: Random jitter and arbitrary padding vs direct
3. fixed_padding: Deterministic padding to 1500B MTU vs direct
4. learned_policy: CMA-ES tuned policy vs baseline censor
5. learned_vs_retrained: Robustness of learned policy against retrained censor

Exports results to /evidence/ml/ablation.json and /evidence/ml/pareto.json.
Includes paired t-test comparisons between learned policy and baselines.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import ttest_rel

from phantomnet.data.capture import (
    CATEGORIES,
    SITES_60,
    capture_all_dataset,
    load_dataset_from_disk,
    save_dataset_to_disk,
)
from phantomnet.ml.censor_models import RandomForestCensor
from phantomnet.ml.features import extract_flow_features
from phantomnet.ml.mask_engine import MaskEngine, MaskParameters
from phantomnet.ml.tuner import CMAESTuner

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def compute_mean_and_95ci(values: list[float]) -> dict[str, float]:
    """Compute mean and 95% confidence interval for a list of metric observations."""
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "ci_95": 0.0, "low": 0.0, "high": 0.0}
    mean = float(np.mean(values))
    if n == 1:
        return {
            "mean": round(mean, 4),
            "ci_95": 0.0,
            "low": round(mean, 4),
            "high": round(mean, 4),
        }

    std = float(np.std(values, ddof=1))
    ci = 1.96 * (std / math.sqrt(n))
    return {
        "mean": round(mean, 4),
        "ci_95": round(ci, 4),
        "low": round(max(0.0, mean - ci), 4),
        "high": round(min(1.0, mean + ci), 4),
    }


def partition_sites_disjoint(
    seed: int,
) -> tuple[list[str], list[str], list[str]]:
    """Partition 60 sites into disjoint Train (40), Val (10), Test (10)."""
    rng = random.Random(seed)
    train_sites: list[str] = []
    val_sites: list[str] = []
    test_sites: list[str] = []

    for cat in CATEGORIES:
        cat_sites = [s["site_id"] for s in SITES_60 if s["category"] == cat]
        rng.shuffle(cat_sites)
        train_sites.extend(cat_sites[:8])  # 8 * 5 = 40
        val_sites.extend(cat_sites[8:10])  # 2 * 5 = 10
        test_sites.extend(cat_sites[10:12])  # 2 * 5 = 10

    return train_sites, val_sites, test_sites


def run_ablation_study(
    seeds: list[int] | None = None,
    output_dir: str = "evidence/ml",
) -> dict[str, Any]:
    """Run full ablation benchmarks across >=10 seeds and write artifacts."""
    seeds = seeds or [42, 101, 2024, 777, 9999, 123, 456, 789, 2025, 9001]
    regimes = [
        "no_shaping",
        "random_shaping",
        "fixed_padding",
        "learned_policy",
        "learned_vs_retrained",
    ]

    # Ensure dataset is loaded or captured
    try:
        all_flows, _manifest = load_dataset_from_disk()
    except FileNotFoundError:
        import asyncio

        all_flows, manifest = asyncio.run(capture_all_dataset(flows_per_class=20, seed=42))
        save_dataset_to_disk(all_flows, manifest)

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
        train_site_ids, val_site_ids, test_site_ids = partition_sites_disjoint(seed=seed)
        train_set = set(train_site_ids)
        val_set = set(val_site_ids)
        test_set = set(test_site_ids)

        train_flows = [f for f in all_flows if f.site_id in train_set]
        val_flows = [f for f in all_flows if f.site_id in val_set]
        test_flows = [f for f in all_flows if f.site_id in test_set]

        # Extract training features and labels
        x_train = np.array([extract_flow_features(f) for f in train_flows])
        y_train = np.array([1 if f.is_tunnel else 0 for f in train_flows])

        # Train baseline censor on unshaped traffic
        censor = RandomForestCensor(n_estimators=100, max_depth=12, seed=seed)
        censor.fit(x_train, y_train)

        engine = MaskEngine(seed=seed)

        # Separate test flows into direct and tunnel
        test_direct = [f for f in test_flows if not f.is_tunnel]
        test_tunnel = [f for f in test_flows if f.is_tunnel]

        # 1. No Shaping (Plain unshaped tunnel vs direct)
        test_eval_no_shape = censor.evaluate(
            np.array([extract_flow_features(f) for f in test_direct + test_tunnel]),
            np.array([0] * len(test_direct) + [1] * len(test_tunnel)),
        )
        metrics_by_regime["no_shaping"]["auc"].append(test_eval_no_shape["auc"])
        metrics_by_regime["no_shaping"]["f1"].append(test_eval_no_shape["f1"])
        metrics_by_regime["no_shaping"]["bandwidth_overhead"].append(0.0)
        metrics_by_regime["no_shaping"]["latency_ms"].append(0.0)
        metrics_by_regime["no_shaping"]["defender_reward"].append(1.0 - test_eval_no_shape["auc"])

        # 2. Random Shaping
        rand_params = MaskParameters(
            pad_bucket=128, jitter_ms=5.0, dummy_rate=0.08, morph_ratio=0.3
        )
        rand_tunnel = [engine.shape_flow(f, rand_params)[0] for f in test_tunnel]
        rand_evals = [engine.shape_flow(f, rand_params)[1] for f in test_tunnel]
        x_rand = np.array([extract_flow_features(f) for f in test_direct + rand_tunnel])
        y_test = np.array([0] * len(test_direct) + [1] * len(rand_tunnel))
        rand_res = censor.evaluate(x_rand, y_test)
        metrics_by_regime["random_shaping"]["auc"].append(rand_res["auc"])
        metrics_by_regime["random_shaping"]["f1"].append(rand_res["f1"])
        metrics_by_regime["random_shaping"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in rand_evals]))
        )
        metrics_by_regime["random_shaping"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in rand_evals]))
        )
        metrics_by_regime["random_shaping"]["defender_reward"].append(
            float(np.mean([m.reward for m in rand_evals]))
        )

        # 3. Fixed Padding (MTU 1500)
        fixed_params = MaskParameters(
            pad_bucket=1500, jitter_ms=0.0, dummy_rate=0.0, morph_ratio=0.0
        )
        fixed_tunnel = [engine.shape_flow(f, fixed_params)[0] for f in test_tunnel]
        fixed_evals = [engine.shape_flow(f, fixed_params)[1] for f in test_tunnel]
        x_fixed = np.array([extract_flow_features(f) for f in test_direct + fixed_tunnel])
        fixed_res = censor.evaluate(x_fixed, y_test)
        metrics_by_regime["fixed_padding"]["auc"].append(fixed_res["auc"])
        metrics_by_regime["fixed_padding"]["f1"].append(fixed_res["f1"])
        metrics_by_regime["fixed_padding"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in fixed_evals]))
        )
        metrics_by_regime["fixed_padding"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in fixed_evals]))
        )
        metrics_by_regime["fixed_padding"]["defender_reward"].append(
            float(np.mean([m.reward for m in fixed_evals]))
        )

        # 4. Learned Policy (CMA-ES tuned on validation sites)
        val_tunnel = [f for f in val_flows if f.is_tunnel]
        tuner = CMAESTuner(seed=seed, pop_size=8)
        learned_params, _ = tuner.tune_step(censor, val_tunnel, extract_flow_features, engine)

        learned_tunnel = [engine.shape_flow(f, learned_params)[0] for f in test_tunnel]
        learned_evals = [engine.shape_flow(f, learned_params)[1] for f in test_tunnel]
        x_learned = np.array([extract_flow_features(f) for f in test_direct + learned_tunnel])
        learned_res = censor.evaluate(x_learned, y_test)
        metrics_by_regime["learned_policy"]["auc"].append(learned_res["auc"])
        metrics_by_regime["learned_policy"]["f1"].append(learned_res["f1"])
        metrics_by_regime["learned_policy"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in learned_evals]))
        )
        metrics_by_regime["learned_policy"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in learned_evals]))
        )
        metrics_by_regime["learned_policy"]["defender_reward"].append(
            float(np.mean([m.reward for m in learned_evals]))
        )

        # 5. Learned vs Retrained Censor (Adversary retrains on newly shaped flows)
        train_direct = [f for f in train_flows if not f.is_tunnel]
        train_tunnel = [f for f in train_flows if f.is_tunnel]
        train_tunnel_shaped = [engine.shape_flow(f, learned_params)[0] for f in train_tunnel]

        x_retrain = np.array([extract_flow_features(f) for f in train_direct + train_tunnel_shaped])
        y_retrain = np.array([0] * len(train_direct) + [1] * len(train_tunnel_shaped))

        retrained_censor = RandomForestCensor(n_estimators=100, max_depth=12, seed=seed)
        retrained_censor.fit(x_retrain, y_retrain)

        retrained_res = retrained_censor.evaluate(x_learned, y_test)
        metrics_by_regime["learned_vs_retrained"]["auc"].append(retrained_res["auc"])
        metrics_by_regime["learned_vs_retrained"]["f1"].append(retrained_res["f1"])
        metrics_by_regime["learned_vs_retrained"]["bandwidth_overhead"].append(
            float(np.mean([m.bandwidth_overhead for m in learned_evals]))
        )
        metrics_by_regime["learned_vs_retrained"]["latency_ms"].append(
            float(np.mean([m.latency_cost_ms for m in learned_evals]))
        )
        stealth_retrained = 1.0 - retrained_res["auc"]
        bw_cost = float(np.mean([m.bandwidth_overhead for m in learned_evals]))
        lat_cost = float(np.mean([m.latency_cost_ms for m in learned_evals]))
        metrics_by_regime["learned_vs_retrained"]["defender_reward"].append(
            stealth_retrained - 0.4 * bw_cost - 0.02 * lat_cost
        )

    # Paired Student t-test comparisons across seeds
    auc_learned = metrics_by_regime["learned_policy"]["auc"]
    auc_no_shaping = metrics_by_regime["no_shaping"]["auc"]
    auc_random = metrics_by_regime["random_shaping"]["auc"]

    t_stat_vs_none, p_val_vs_none = ttest_rel(auc_learned, auc_no_shaping)
    t_stat_vs_rand, p_val_vs_rand = ttest_rel(auc_learned, auc_random)

    paired_comparisons = {
        "learned_vs_no_shaping": {
            "mean_auc_diff": round(float(np.mean(auc_learned) - np.mean(auc_no_shaping)), 4),
            "t_statistic": round(float(t_stat_vs_none), 4),
            "p_value": round(float(p_val_vs_none), 6),
            "statistically_significant": bool(p_val_vs_none < 0.05),
        },
        "learned_vs_random": {
            "mean_auc_diff": round(float(np.mean(auc_learned) - np.mean(auc_random)), 4),
            "t_statistic": round(float(t_stat_vs_rand), 4),
            "p_value": round(float(p_val_vs_rand), 6),
            "statistically_significant": bool(p_val_vs_rand < 0.05),
        },
    }

    results: dict[str, Any] = {}
    for r in regimes:
        results[r] = {
            "censor_auc": compute_mean_and_95ci(metrics_by_regime[r]["auc"]),
            "f1_score": compute_mean_and_95ci(metrics_by_regime[r]["f1"]),
            "bandwidth_overhead": compute_mean_and_95ci(metrics_by_regime[r]["bandwidth_overhead"]),
            "latency_cost_ms": compute_mean_and_95ci(metrics_by_regime[r]["latency_ms"]),
            "defender_reward": compute_mean_and_95ci(metrics_by_regime[r]["defender_reward"]),
        }

    out_dir = REPO_ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ablation_payload = {
        "title": "PHANTOMNET Real Traffic Adversarial Censorship Defense Ablation Study",
        "dataset_name": "PHANTOMNET_REAL_TRAFFIC_60SITES",
        "num_seeds": len(seeds),
        "seeds": seeds,
        "site_split": {"train": 40, "val": 10, "test": 10},
        "flows_evaluated_per_seed": {
            "train": len(train_flows),
            "val": len(val_flows),
            "test": len(test_flows),
        },
        "results": results,
        "paired_comparisons": paired_comparisons,
    }

    with open(out_dir / "ablation.json", "w", encoding="utf-8") as f:
        json.dump(ablation_payload, f, indent=2)

    # Compute Pareto frontier table
    pareto_list = []
    for r in regimes:
        bw_pct = results[r]["bandwidth_overhead"]["mean"] * 100.0
        auc_val = results[r]["censor_auc"]["mean"]
        auc_ci = results[r]["censor_auc"]["ci_95"]
        stealth = round(1.0 - auc_val, 4)
        reward_val = results[r]["defender_reward"]["mean"]

        pareto_list.append(
            {
                "regime": r,
                "bandwidth_overhead_pct": round(bw_pct, 2),
                "stealth_score": stealth,
                "censor_auc": auc_val,
                "auc_ci_95": auc_ci,
                "reward": reward_val,
            }
        )

    with open(out_dir / "pareto.json", "w", encoding="utf-8") as f:
        json.dump(pareto_list, f, indent=2)

    print(f"Ablation study written to {out_dir / 'ablation.json'}")
    return ablation_payload


if __name__ == "__main__":
    run_ablation_study()
