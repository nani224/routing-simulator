"""PHANTOMNET Gate C & Gate E: Threshold-Free Arms Race Ablation Study.

Evaluates 4 shaping regimes on locally served site profiles (TLS 1.3 negative class vs Noise XX):
1. no_shaping: Baseline unshaped tunnel vs direct TLS 1.3
2. random_shaping: Random jitter and arbitrary padding
3. fixed_padding: Deterministic padding to 1500B MTU
4. learned_policy: CMA-ES joint optimization of transport & handshake parameters

For EVERY regime, evaluates:
- Static Censor (trained on unshaped traffic)
- Retrained Censor (trained on shaped traffic)

Metrics reported:
- ROC-AUC on shaped flows with site-level bootstrap 95% CI
- True Positive Rate (TPR) at 1% False Positive Rate (FPR), with operating threshold
  selected on unshaped validation data
- Bandwidth overhead (%) and latency penalty (ms)
- Paired statistical tests across >=10 seeds
- Pareto trade-off frontier (stealth vs overhead)

Exports to:
- /evidence/ml/ablation.json
- /evidence/ml/pareto.json
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import ttest_rel
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

from phantomnet.data.capture import (
    CATEGORIES,
    SITES_60,
    capture_all_dataset,
    load_dataset_from_disk,
    save_dataset_to_disk,
)
from phantomnet.data.traces import FlowTrace
from phantomnet.ml.features import extract_flow_features
from phantomnet.ml.mask_engine import MaskEngine, MaskParameters
from phantomnet.ml.tuner import CMAESTuner

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ABLATION_FILE = REPO_ROOT / "evidence" / "ml" / "ablation.json"
PARETO_FILE = REPO_ROOT / "evidence" / "ml" / "pareto.json"


def compute_site_level_bootstrap_ci(
    test_flows: list[FlowTrace],
    y_true: np.ndarray,
    y_scores: np.ndarray,
    tau_1pct: float,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> tuple[float, float, float, float, float, float]:
    """Compute AUC and TPR@1%FPR with genuine 95% site-level cluster bootstrap CIs."""
    rng = np.random.RandomState(seed)
    unique_sites = sorted({f.site_id for f in test_flows})
    site_indices: dict[str, list[int]] = {s: [] for s in unique_sites}
    for idx, f in enumerate(test_flows):
        site_indices[f.site_id].append(idx)

    # Point estimates
    main_auc = float(roc_auc_score(y_true, y_scores))
    pos_mask = y_true == 1
    main_tpr = float(np.mean(y_scores[pos_mask] >= tau_1pct)) if np.any(pos_mask) else 0.0

    boot_aucs: list[float] = []
    boot_tprs: list[float] = []
    n_sites = len(unique_sites)

    for _ in range(n_bootstraps):
        sampled_sites = rng.choice(unique_sites, size=n_sites, replace=True)
        sampled_idx: list[int] = []
        for s in sampled_sites:
            sampled_idx.extend(site_indices[s])

        b_true = y_true[sampled_idx]
        b_scores = y_scores[sampled_idx]
        if len(np.unique(b_true)) < 2:
            continue

        boot_aucs.append(float(roc_auc_score(b_true, b_scores)))
        b_pos = b_true == 1
        if np.any(b_pos):
            boot_tprs.append(float(np.mean(b_scores[b_pos] >= tau_1pct)))

    auc_low = float(np.percentile(boot_aucs, 2.5)) if boot_aucs else main_auc
    auc_high = float(np.percentile(boot_aucs, 97.5)) if boot_aucs else main_auc
    tpr_low = float(np.percentile(boot_tprs, 2.5)) if boot_tprs else main_tpr
    tpr_high = float(np.percentile(boot_tprs, 97.5)) if boot_tprs else main_tpr

    return (
        round(main_auc, 4),
        round(auc_low, 4),
        round(auc_high, 4),
        round(main_tpr, 4),
        round(tpr_low, 4),
        round(tpr_high, 4),
    )


def partition_sites_disjoint(seed: int) -> tuple[list[str], list[str], list[str]]:
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
    """Execute complete Gate C & Gate E arms race ablation study."""
    seeds = seeds or [42, 101, 2024, 777, 9999, 123, 456, 789, 2025, 9001]
    regimes = ["no_shaping", "random_shaping", "fixed_padding", "learned_policy"]

    try:
        all_flows, manifest = load_dataset_from_disk()
    except FileNotFoundError:
        import asyncio

        all_flows, manifest = asyncio.run(capture_all_dataset(flows_per_class=20, seed=42))
        save_dataset_to_disk(all_flows, manifest)

    # Accumulators across seeds
    data_by_regime: dict[str, dict[str, list[float]]] = {
        r: {
            "static_auc": [],
            "static_tpr_at_1pct_fpr": [],
            "retrained_auc": [],
            "retrained_tpr_at_1pct_fpr": [],
            "bandwidth_overhead": [],
            "latency_ms": [],
        }
        for r in regimes
    }

    # Store final seed's bootstrap CIs for representative reporting
    final_cis: dict[str, dict[str, list[float]]] = {}

    for seed in seeds:
        train_site_ids, val_site_ids, test_site_ids = partition_sites_disjoint(seed=seed)
        train_set = set(train_site_ids)
        val_set = set(val_site_ids)
        test_set = set(test_site_ids)

        train_flows = [f for f in all_flows if f.site_id in train_set]
        val_flows = [f for f in all_flows if f.site_id in val_set]
        test_flows = [f for f in all_flows if f.site_id in test_set]

        train_dir = [f for f in train_flows if not f.is_tunnel]
        train_tun = [f for f in train_flows if f.is_tunnel]
        val_dir = [f for f in val_flows if not f.is_tunnel]
        test_dir = [f for f in test_flows if not f.is_tunnel]
        test_tun = [f for f in test_flows if f.is_tunnel]

        # 1. Train Static Censor on unshaped train flows
        x_train_unshaped = np.array(
            [extract_flow_features(f) for f in train_dir + train_tun], dtype=np.float64
        )
        y_train = np.array([0] * len(train_dir) + [1] * len(train_tun), dtype=np.int32)
        static_censor = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=seed)
        static_censor.fit(x_train_unshaped, y_train)

        # 2. Compute operating threshold tau at 1% FPR on unshaped validation direct flows
        x_val_dir = np.array([extract_flow_features(f) for f in val_dir], dtype=np.float64)
        val_dir_scores = static_censor.predict_proba(x_val_dir)[:, 1]
        tau_1pct = float(np.percentile(val_dir_scores, 99.0))

        engine = MaskEngine(seed=seed)

        # Regimes configuration
        regime_params: dict[str, MaskParameters] = {
            "no_shaping": MaskParameters(
                pad_bucket=0,
                jitter_ms=0.0,
                dummy_rate=0.0,
                burst_chop=100,
                morph_ratio=0.0,
                hs_pad_m1=0,
                hs_pad_m2=0,
                hs_pad_m3=0,
                hs_preamble_count=0,
                hs_jitter_ms=0.0,
            ),
            "random_shaping": MaskParameters(
                pad_bucket=128,
                jitter_ms=4.0,
                dummy_rate=0.06,
                burst_chop=8,
                morph_ratio=0.25,
                hs_pad_m1=120,
                hs_pad_m2=350,
                hs_pad_m3=100,
                hs_preamble_count=1,
                hs_jitter_ms=4.0,
            ),
            "fixed_padding": MaskParameters(
                pad_bucket=1500,
                jitter_ms=0.0,
                dummy_rate=0.0,
                burst_chop=100,
                morph_ratio=0.0,
                hs_pad_m1=1400,
                hs_pad_m2=1400,
                hs_pad_m3=1400,
                hs_preamble_count=0,
                hs_jitter_ms=0.0,
            ),
        }

        # CMA-ES optimization for learned policy on validation sites
        val_tunnel = [f for f in val_flows if f.is_tunnel]
        tuner = CMAESTuner(seed=seed, pop_size=8)
        best_learned_params, _ = tuner.tune_step(
            static_censor, val_tunnel, extract_flow_features, engine
        )
        regime_params["learned_policy"] = best_learned_params

        # Evaluate all 4 regimes
        for r_name in regimes:
            params = regime_params[r_name]

            # Shape test tunnel flows
            test_tun_shaped = [engine.shape_flow(f, params)[0] for f in test_tun]
            test_evals = [engine.shape_flow(f, params)[1] for f in test_tun]

            test_combined = test_dir + test_tun_shaped
            x_test_shaped = np.array(
                [extract_flow_features(f) for f in test_combined], dtype=np.float64
            )
            y_test = np.array([0] * len(test_dir) + [1] * len(test_tun_shaped), dtype=np.int32)

            # Evaluate against Static Censor
            static_scores = static_censor.predict_proba(x_test_shaped)[:, 1]
            (
                s_auc,
                s_auc_l,
                s_auc_h,
                s_tpr,
                s_tpr_l,
                s_tpr_h,
            ) = compute_site_level_bootstrap_ci(
                test_combined, y_test, static_scores, tau_1pct, n_bootstraps=1000, seed=seed
            )

            # Train and evaluate Retrained Censor
            train_tun_shaped = [engine.shape_flow(f, params)[0] for f in train_tun]
            x_train_retrain = np.array(
                [extract_flow_features(f) for f in train_dir + train_tun_shaped],
                dtype=np.float64,
            )
            retrained_censor = RandomForestClassifier(
                n_estimators=100, max_depth=12, random_state=seed
            )
            retrained_censor.fit(x_train_retrain, y_train)

            # Retrained operating threshold at 1% FPR
            x_val_dir_retrain = x_val_dir
            val_scores_retrain = retrained_censor.predict_proba(x_val_dir_retrain)[:, 1]
            tau_1pct_retrain = float(np.percentile(val_scores_retrain, 99.0))

            retrained_scores = retrained_censor.predict_proba(x_test_shaped)[:, 1]
            (
                r_auc,
                r_auc_l,
                r_auc_h,
                r_tpr,
                r_tpr_l,
                r_tpr_h,
            ) = compute_site_level_bootstrap_ci(
                test_combined,
                y_test,
                retrained_scores,
                tau_1pct_retrain,
                n_bootstraps=1000,
                seed=seed,
            )

            bw_over = float(np.mean([m.bandwidth_overhead for m in test_evals]))
            lat_pen = float(np.mean([m.latency_cost_ms for m in test_evals]))

            data_by_regime[r_name]["static_auc"].append(s_auc)
            data_by_regime[r_name]["static_tpr_at_1pct_fpr"].append(s_tpr)
            data_by_regime[r_name]["retrained_auc"].append(r_auc)
            data_by_regime[r_name]["retrained_tpr_at_1pct_fpr"].append(r_tpr)
            data_by_regime[r_name]["bandwidth_overhead"].append(bw_over)
            data_by_regime[r_name]["latency_ms"].append(lat_pen)

            if seed == seeds[-1]:
                final_cis[r_name] = {
                    "static_auc_ci": [s_auc_l, s_auc_h],
                    "static_tpr_ci": [s_tpr_l, s_tpr_h],
                    "retrained_auc_ci": [r_auc_l, r_auc_h],
                    "retrained_tpr_ci": [r_tpr_l, r_tpr_h],
                }

    # Paired statistical comparisons across seeds
    auc_learned = data_by_regime["learned_policy"]["static_auc"]
    auc_none = data_by_regime["no_shaping"]["static_auc"]
    auc_rand = data_by_regime["random_shaping"]["static_auc"]

    t_vs_none, p_vs_none = ttest_rel(auc_learned, auc_none)
    t_vs_rand, p_vs_rand = ttest_rel(auc_learned, auc_rand)

    sig_vs_none = bool(p_vs_none < 0.05) if not math.isnan(p_vs_none) else False
    sig_vs_rand = bool(p_vs_rand < 0.05) if not math.isnan(p_vs_rand) else False

    paired_comparisons = {
        "learned_vs_no_shaping": {
            "mean_auc_diff": round(float(np.mean(auc_learned) - np.mean(auc_none)), 4),
            "t_statistic": round(float(t_vs_none), 4) if not math.isnan(t_vs_none) else 0.0,
            "p_value": round(float(p_vs_none), 6) if not math.isnan(p_vs_none) else 1.0,
            "statistically_significant": sig_vs_none,
        },
        "learned_vs_random": {
            "mean_auc_diff": round(float(np.mean(auc_learned) - np.mean(auc_rand)), 4),
            "t_statistic": round(float(t_vs_rand), 4) if not math.isnan(t_vs_rand) else 0.0,
            "p_value": round(float(p_vs_rand), 6) if not math.isnan(p_vs_rand) else 1.0,
            "statistically_significant": sig_vs_rand,
        },
    }

    # Aggregate results for JSON export
    results: dict[str, Any] = {}
    pareto_list: list[dict[str, Any]] = []

    for r_name in regimes:
        d = data_by_regime[r_name]
        mean_s_auc = float(np.mean(d["static_auc"]))
        mean_s_tpr = float(np.mean(d["static_tpr_at_1pct_fpr"]))
        mean_r_auc = float(np.mean(d["retrained_auc"]))
        mean_r_tpr = float(np.mean(d["retrained_tpr_at_1pct_fpr"]))
        mean_bw = float(np.mean(d["bandwidth_overhead"]))
        mean_lat = float(np.mean(d["latency_ms"]))

        ci_info = final_cis[r_name]

        results[r_name] = {
            "static_censor": {
                "auc": round(mean_s_auc, 4),
                "ci_95": ci_info["static_auc_ci"],
                "tpr_at_1pct_fpr": round(mean_s_tpr, 4),
                "tpr_ci_95": ci_info["static_tpr_ci"],
            },
            "retrained_censor": {
                "auc": round(mean_r_auc, 4),
                "ci_95": ci_info["retrained_auc_ci"],
                "tpr_at_1pct_fpr": round(mean_r_tpr, 4),
                "tpr_ci_95": ci_info["retrained_tpr_ci"],
            },
            "bandwidth_overhead": {
                "mean": round(mean_bw, 4),
                "percentage": round(mean_bw * 100.0, 2),
            },
            "latency_penalty_ms": {
                "mean": round(mean_lat, 3),
            },
        }

        pareto_list.append(
            {
                "regime": r_name,
                "bandwidth_overhead_pct": round(mean_bw * 100.0, 2),
                "latency_cost_ms": round(mean_lat, 3),
                "static_auc": round(mean_s_auc, 4),
                "retrained_auc": round(mean_r_auc, 4),
                "static_tpr_at_1pct_fpr": round(mean_s_tpr, 4),
                "retrained_tpr_at_1pct_fpr": round(mean_r_tpr, 4),
            }
        )

    output = {
        "dataset_name": manifest.get("dataset_name", "TLS13_DATASET"),
        "negative_class": "TLS 1.3 HTTPS (RFC 8446)",
        "tunnel_class": "Noise XX (ChaCha20-Poly1305)",
        "num_seeds": len(seeds),
        "seeds_tested": seeds,
        "site_split": {"train": 40, "val": 10, "test": 10},
        "results": results,
        "paired_comparisons": paired_comparisons,
    }

    out_dir_path = Path(output_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    with open(out_dir_path / "ablation.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    with open(out_dir_path / "pareto.json", "w", encoding="utf-8") as f:
        json.dump(pareto_list, f, indent=2)

    print(
        f"[OK] Saved ablation results to {out_dir_path / 'ablation.json'} and "
        f"{out_dir_path / 'pareto.json'}"
    )
    return output


def main() -> None:
    run_ablation_study()


if __name__ == "__main__":
    main()
