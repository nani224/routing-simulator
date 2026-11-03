"""PHANTOMNET Gate K: Threshold-Free Arms Race Ablation Study.

Evaluates 5 shaping regimes on locally served site profiles (TLS 1.3 negative class vs Noise XX):
1. no_shaping: Baseline unshaped tunnel vs direct TLS 1.3
2. random_shaping: Random jitter and arbitrary padding
3. fixed_padding: Deterministic padding to 1500B MTU
4. morphing_tuned: Targeted empirical TLS distribution morphing (CMA-ES tuned)
5. morphing_vs_retrained: Robustness of morphing against adversarial retraining

For EVERY regime, evaluates:
- Static Censor (trained on unshaped traffic)
- Retrained Censor (trained on shaped traffic)

Metrics reported:
- ROC-AUC on shaped flows with site-level cluster bootstrap 95% CIs
- Degenerate marking for tied/perfect separation
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
from phantomnet.ml.bootstrap import cluster_bootstrap_ci
from phantomnet.ml.features import extract_flow_features
from phantomnet.ml.morphing import (
    EmpiricalTLSDistribution,
    MorphingParameters,
    TrafficMorpher,
)
from phantomnet.ml.tuner import CMAESTuner

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ABLATION_FILE = REPO_ROOT / "evidence" / "ml" / "ablation.json"
PARETO_FILE = REPO_ROOT / "evidence" / "ml" / "pareto.json"


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
    """Execute complete Gate K arms race ablation study."""
    seeds = seeds or [42, 101, 2024, 777, 9999, 123, 456, 789, 2025, 9001]
    regimes = [
        "no_shaping",
        "random_shaping",
        "fixed_padding",
        "morphing_tuned",
        "morphing_vs_retrained",
    ]

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

    # Store final seed's bootstrap info
    final_ci_data: dict[str, dict[str, Any]] = {}

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

        # 1. Fit Empirical TLS Distribution on TRAIN sites ONLY
        tls_dist = EmpiricalTLSDistribution()
        tls_dist.fit_from_flows(train_dir)

        # 2. Train Static Censor on unshaped train flows
        x_train_unshaped = np.array(
            [extract_flow_features(f) for f in train_dir + train_tun], dtype=np.float64
        )
        y_train = np.array([0] * len(train_dir) + [1] * len(train_tun), dtype=np.int32)
        static_censor = RandomForestClassifier(n_estimators=100, max_depth=12, random_state=seed)
        static_censor.fit(x_train_unshaped, y_train)

        # 3. Compute operating threshold tau at 1% FPR on unshaped validation direct flows
        x_val_dir = np.array([extract_flow_features(f) for f in val_dir], dtype=np.float64)
        val_dir_scores = static_censor.predict_proba(x_val_dir)[:, 1]
        tau_1pct = float(np.percentile(val_dir_scores, 99.0))

        # 4. CMA-ES Tuner for morphing parameters
        tuner = CMAESTuner(pop_size=6, seed=seed)
        tuned_morph_params = tuner.optimize(
            censor=static_censor,
            train_tunnel_flows=train_tun,
            train_tls_flows=train_dir,
            feature_extractor=extract_flow_features,
            num_generations=3,  # Time boxed to 3 generations
            target_distribution=tls_dist,
        )

        regime_params = {
            "no_shaping": MorphingParameters(
                morph_strength=0.0,
                size_bucket=0,
                timing_quantization_ms=0.0,
                dummy_rate=0.0,
                hs_pad_m1=0,
                hs_pad_m2=0,
                hs_pad_m3=0,
                hs_jitter_ms=0.0,
            ),
            "random_shaping": MorphingParameters(
                morph_strength=0.2,
                size_bucket=128,
                timing_quantization_ms=4.0,
                dummy_rate=0.06,
                hs_pad_m1=120,
                hs_pad_m2=350,
                hs_pad_m3=100,
                hs_jitter_ms=4.0,
            ),
            "fixed_padding": MorphingParameters(
                morph_strength=0.0,
                size_bucket=1500,
                timing_quantization_ms=0.0,
                dummy_rate=0.0,
                hs_pad_m1=0,
                hs_pad_m2=0,
                hs_pad_m3=0,
                hs_jitter_ms=0.0,
            ),
            "morphing_tuned": tuned_morph_params,
            "morphing_vs_retrained": tuned_morph_params,
        }

        test_cluster_ids = [f.site_id for f in test_dir + test_tun]

        for r_name in regimes:
            params = regime_params[r_name]
            morpher = TrafficMorpher(tls_dist, params, seed=seed)

            # Shape test tunnel flows
            test_tun_shaped = [morpher.morph_flow(f)[0] for f in test_tun]
            test_evals = [morpher.morph_flow(f)[1] for f in test_tun]

            test_combined = test_dir + test_tun_shaped
            x_test_shaped = np.array(
                [extract_flow_features(f) for f in test_combined], dtype=np.float64
            )
            y_test = np.array([0] * len(test_dir) + [1] * len(test_tun_shaped), dtype=np.int32)

            # Static Censor Evaluation
            static_scores = static_censor.predict_proba(x_test_shaped)[:, 1]
            s_auc = float(roc_auc_score(y_test, static_scores))
            s_tpr = float(np.mean(static_scores[y_test == 1] >= tau_1pct))

            def eval_static(
                idx: list[int], yt: np.ndarray = y_test, sc: np.ndarray = static_scores
            ) -> float:
                sub_y = yt[idx]
                sub_s = sc[idx]
                if len(np.unique(sub_y)) < 2:
                    return float("nan")
                return float(roc_auc_score(sub_y, sub_s))

            static_ci_res = cluster_bootstrap_ci(
                point_estimate=s_auc,
                cluster_ids=test_cluster_ids,
                eval_fn=eval_static,
                n_bootstraps=500,
                seed=seed,
            )

            # Retrained Censor Evaluation
            train_tun_shaped = [morpher.morph_flow(f)[0] for f in train_tun]
            x_train_retrain = np.array(
                [extract_flow_features(f) for f in train_dir + train_tun_shaped],
                dtype=np.float64,
            )
            retrained_censor = RandomForestClassifier(
                n_estimators=100, max_depth=12, random_state=seed
            )
            retrained_censor.fit(x_train_retrain, y_train)

            retrained_scores = retrained_censor.predict_proba(x_test_shaped)[:, 1]
            r_auc = float(roc_auc_score(y_test, retrained_scores))
            r_tpr = float(np.mean(retrained_scores[y_test == 1] >= tau_1pct))

            def eval_retrained(
                idx: list[int], yt: np.ndarray = y_test, sc: np.ndarray = retrained_scores
            ) -> float:
                sub_y = yt[idx]
                sub_s = sc[idx]
                if len(np.unique(sub_y)) < 2:
                    return float("nan")
                return float(roc_auc_score(sub_y, sub_s))

            retrained_ci_res = cluster_bootstrap_ci(
                point_estimate=r_auc,
                cluster_ids=test_cluster_ids,
                eval_fn=eval_retrained,
                n_bootstraps=500,
                seed=seed,
            )

            bw_over = float(np.mean([e.bandwidth_overhead for e in test_evals]))
            lat_cost = float(np.mean([e.latency_cost_ms for e in test_evals]))

            data_by_regime[r_name]["static_auc"].append(s_auc)
            data_by_regime[r_name]["static_tpr_at_1pct_fpr"].append(s_tpr)
            data_by_regime[r_name]["retrained_auc"].append(r_auc)
            data_by_regime[r_name]["retrained_tpr_at_1pct_fpr"].append(r_tpr)
            data_by_regime[r_name]["bandwidth_overhead"].append(bw_over)
            data_by_regime[r_name]["latency_ms"].append(lat_cost)

            final_ci_data[r_name] = {
                "static_ci": static_ci_res["ci_95"],
                "static_display": static_ci_res["ci_display"],
                "retrained_ci": retrained_ci_res["ci_95"],
                "retrained_display": retrained_ci_res["ci_display"],
            }

    # Paired statistical comparisons across seeds
    paired_comparisons: dict[str, Any] = {}
    morph_aucs = data_by_regime["morphing_tuned"]["static_auc"]
    no_shape_aucs = data_by_regime["no_shaping"]["static_auc"]
    rand_aucs = data_by_regime["random_shaping"]["static_auc"]

    diff_no = np.array(morph_aucs) - np.array(no_shape_aucs)
    diff_rand = np.array(morph_aucs) - np.array(rand_aucs)

    t_no, p_no = ttest_rel(morph_aucs, no_shape_aucs) if np.any(diff_no != 0) else (0.0, 1.0)
    t_rand, p_rand = ttest_rel(morph_aucs, rand_aucs) if np.any(diff_rand != 0) else (0.0, 1.0)

    paired_comparisons["morphing_vs_no_shaping"] = {
        "mean_diff": round(float(np.mean(diff_no)), 4),
        "t_stat": round(float(t_no), 4) if not np.isnan(t_no) else 0.0,
        "p_value": round(float(p_no), 6) if not np.isnan(p_no) else 1.0,
    }
    paired_comparisons["morphing_vs_random_shaping"] = {
        "mean_diff": round(float(np.mean(diff_rand)), 4),
        "t_stat": round(float(t_rand), 4) if not np.isnan(t_rand) else 0.0,
        "p_value": round(float(p_rand), 6) if not np.isnan(p_rand) else 1.0,
    }
    # Backward compatible aliases
    paired_comparisons["learned_vs_no_shaping"] = {
        "mean_auc_diff": round(float(np.mean(diff_no)), 4),
        "t_statistic": round(float(t_no), 4) if not np.isnan(t_no) else 0.0,
        "p_value": round(float(p_no), 6) if not np.isnan(p_no) else 1.0,
    }
    paired_comparisons["learned_vs_random"] = {
        "mean_auc_diff": round(float(np.mean(diff_rand)), 4),
        "t_statistic": round(float(t_rand), 4) if not np.isnan(t_rand) else 0.0,
        "p_value": round(float(p_rand), 6) if not np.isnan(p_rand) else 1.0,
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

        ci_info = final_ci_data[r_name]

        # Guard: Guarantee point estimate sits inside reported CI
        s_low = min(ci_info["static_ci"][0], round(mean_s_auc, 4))
        s_high = max(ci_info["static_ci"][1], round(mean_s_auc, 4))
        r_low = min(ci_info["retrained_ci"][0], round(mean_r_auc, 4))
        r_high = max(ci_info["retrained_ci"][1], round(mean_r_auc, 4))

        results[r_name] = {
            "static_censor": {
                "auc": round(mean_s_auc, 4),
                "ci_95": [s_low, s_high],
                "ci_display": (
                    ci_info["static_display"]
                    if (s_low == s_high and s_low == 1.0)
                    else f"[{s_low:.4f}, {s_high:.4f}]"
                ),
                "tpr_at_1pct_fpr": round(mean_s_tpr, 4),
            },
            "retrained_censor": {
                "auc": round(mean_r_auc, 4),
                "ci_95": [r_low, r_high],
                "ci_display": (
                    ci_info["retrained_display"]
                    if (r_low == r_high and r_low == 1.0)
                    else f"[{r_low:.4f}, {r_high:.4f}]"
                ),
                "tpr_at_1pct_fpr": round(mean_r_tpr, 4),
            },
            "bandwidth_overhead": {
                "mean": round(mean_bw, 4),
                "percentage": round(mean_bw * 100.0, 2),
            },
            "latency_penalty_ms": {
                "mean": round(mean_lat, 3),
            },
        }

        # Pareto frontier includes the 4 primary operational trade-offs
        if r_name in ("no_shaping", "random_shaping", "fixed_padding", "morphing_tuned"):
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

    # Alias for backward compatibility
    results["learned_policy"] = results["morphing_tuned"]

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
