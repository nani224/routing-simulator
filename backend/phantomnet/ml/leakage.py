"""PHANTOMNET Gate B: Systematic Leakage and Feature Attribution Ablations.

Evaluates 6 feature ablations:
1. All features (full flow)
2. Handshake-only (first 4 packets of flow)
3. No handshake (drop first 4 packets of flow)
4. Size-only features (histograms, moments)
5. Timing-only features (inter-packet gaps, duration)
6. Direction-only features (ratios, burst dynamics)

Reports test ROC-AUC with genuine 95% site-level bootstrap confidence intervals
and permutation feature importance. Outputs to /evidence/ml/leakage.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from phantomnet.data.capture import load_dataset_from_disk
from phantomnet.data.traces import FlowTrace
from phantomnet.ml.features import extract_flow_features

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LEAKAGE_FILE = REPO_ROOT / "evidence" / "ml" / "leakage.json"

FEATURE_NAMES = (
    [f"tx_size_bin_{i}" for i in range(10)]
    + [f"rx_size_bin_{i}" for i in range(10)]
    + [f"gap_bin_{i}" for i in range(10)]
    + [
        "tx_pkt_ratio",
        "rx_pkt_ratio",
        "tx_byte_ratio",
        "rx_byte_ratio",
        "mean_burst_norm",
        "max_burst_norm",
        "tx_mean",
        "tx_std",
        "rx_mean",
        "rx_std",
        "total_pkts_log",
        "total_duration_log",
    ]
)

# Indices for modality subsets
SIZE_INDICES = list(range(0, 20)) + [36, 37, 38, 39]
TIMING_INDICES = list(range(20, 30)) + [41]
DIRECTION_INDICES = list(range(30, 36)) + [40]


def compute_site_bootstrap_auc_ci(
    test_flows: list[FlowTrace],
    y_true: np.ndarray,
    y_scores: np.ndarray,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute ROC-AUC and 95% CI via site-level cluster bootstrapping."""
    rng = np.random.RandomState(seed)
    unique_sites = sorted({f.site_id for f in test_flows})
    site_indices: dict[str, list[int]] = {s: [] for s in unique_sites}
    for idx, f in enumerate(test_flows):
        site_indices[f.site_id].append(idx)

    main_auc = float(roc_auc_score(y_true, y_scores))

    boot_aucs: list[float] = []
    n_sites = len(unique_sites)
    for _ in range(n_bootstraps):
        sampled_sites = rng.choice(unique_sites, size=n_sites, replace=True)
        sampled_indices: list[int] = []
        for s in sampled_sites:
            sampled_indices.extend(site_indices[s])

        b_true = y_true[sampled_indices]
        b_scores = y_scores[sampled_indices]
        if len(np.unique(b_true)) < 2:
            continue
        boot_aucs.append(float(roc_auc_score(b_true, b_scores)))

    if boot_aucs:
        ci_lower = float(np.percentile(boot_aucs, 2.5))
        ci_upper = float(np.percentile(boot_aucs, 97.5))
    else:
        ci_lower, ci_upper = main_auc, main_auc

    return round(main_auc, 4), round(ci_lower, 4), round(ci_upper, 4)


def extract_features_for_ablation(flows: list[FlowTrace], condition: str) -> np.ndarray:
    """Extract feature matrices according to experimental condition."""
    if condition == "all_features":
        return np.array([extract_flow_features(f) for f in flows], dtype=np.float64)

    elif condition == "handshake_only":
        trimmed = [
            FlowTrace(
                site_id=f.site_id,
                category=f.category,
                is_tunnel=f.is_tunnel,
                packets=f.packets[:4],
            )
            for f in flows
        ]
        return np.array([extract_flow_features(f) for f in trimmed], dtype=np.float64)

    elif condition == "no_handshake":
        trimmed = [
            FlowTrace(
                site_id=f.site_id,
                category=f.category,
                is_tunnel=f.is_tunnel,
                packets=f.packets[4:],
            )
            for f in flows
        ]
        return np.array([extract_flow_features(f) for f in trimmed], dtype=np.float64)

    elif condition == "size_only":
        full = np.array([extract_flow_features(f) for f in flows], dtype=np.float64)
        return full[:, SIZE_INDICES]

    elif condition == "timing_only":
        full = np.array([extract_flow_features(f) for f in flows], dtype=np.float64)
        return full[:, TIMING_INDICES]

    elif condition == "direction_only":
        full = np.array([extract_flow_features(f) for f in flows], dtype=np.float64)
        return full[:, DIRECTION_INDICES]

    raise ValueError(f"Unknown ablation condition: {condition}")


def run_leakage_study() -> dict[str, Any]:
    """Execute complete Gate B leakage ablation study."""
    flows, manifest = load_dataset_from_disk()

    # Split sites disjointly: 40 train, 10 val, 10 test
    sites = sorted({f.site_id for f in flows})
    train_sites = set(sites[:40])
    test_sites = set(sites[50:])

    train_flows = [f for f in flows if f.site_id in train_sites]
    test_flows = [f for f in flows if f.site_id in test_sites]

    y_train = np.array([1 if f.is_tunnel else 0 for f in train_flows], dtype=np.int32)
    y_test = np.array([1 if f.is_tunnel else 0 for f in test_flows], dtype=np.int32)

    conditions = [
        ("all_features", "Full 42-D statistical feature vector"),
        ("handshake_only", "Handshake only (first 4 packets of exchange)"),
        ("no_handshake", "No handshake (first 4 packets stripped)"),
        ("size_only", "Packet size histograms and moments only"),
        ("timing_only", "Inter-packet delay gaps and total duration only"),
        ("direction_only", "Directional ratios, volume ratios, burst dynamics only"),
    ]

    results: dict[str, Any] = {}

    for cond_name, description in conditions:
        X_train = extract_features_for_ablation(train_flows, cond_name)
        X_test = extract_features_for_ablation(test_flows, cond_name)

        clf = RandomForestClassifier(n_estimators=100, random_state=42)
        clf.fit(X_train, y_train)
        scores = clf.predict_proba(X_test)[:, 1]

        auc, ci_low, ci_high = compute_site_bootstrap_auc_ci(
            test_flows, y_test, scores, n_bootstraps=1000, seed=42
        )

        results[cond_name] = {
            "description": description,
            "feature_count": int(X_train.shape[1]),
            "test_auc": auc,
            "ci_95": [ci_low, ci_high],
        }

    # Top feature importances under all_features condition
    X_train_all = extract_features_for_ablation(train_flows, "all_features")
    X_test_all = extract_features_for_ablation(test_flows, "all_features")
    clf_all = RandomForestClassifier(n_estimators=100, random_state=42)
    clf_all.fit(X_train_all, y_train)

    gini_importances = clf_all.feature_importances_
    perm = permutation_importance(
        clf_all, X_test_all, y_test, n_repeats=10, random_state=42, scoring="roc_auc"
    )
    top_indices = np.argsort(gini_importances)[::-1][:10]

    top_features: list[dict[str, Any]] = []
    for idx in top_indices:
        top_features.append(
            {
                "feature_index": int(idx),
                "feature_name": FEATURE_NAMES[idx],
                "gini_importance": round(float(gini_importances[idx]), 4),
                "permutation_mean": round(float(perm.importances_mean[idx]), 4),
                "permutation_std": round(float(perm.importances_std[idx]), 4),
            }
        )

    output = {
        "dataset_name": manifest.get("dataset_name", "TLS13_DATASET"),
        "negative_class": "TLS 1.3 HTTPS (RFC 8446)",
        "tunnel_class": "Noise XX (ChaCha20-Poly1305)",
        "train_sites": len(train_sites),
        "test_sites": len(test_sites),
        "train_flows": len(train_flows),
        "test_flows": len(test_flows),
        "ablations": results,
        "top_permutation_features": top_features,
    }

    LEAKAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LEAKAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"[OK] Saved leakage ablation results to {LEAKAGE_FILE}")
    return output


def main() -> None:
    run_leakage_study()


if __name__ == "__main__":
    main()
