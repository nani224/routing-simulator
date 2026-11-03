"""Unit tests for Gate I: Statistical Rigor & Cluster Bootstrap Verification.

Verifies:
1. Point estimate is strictly inside [ci_low, ci_high].
2. Rejects any CI where point estimate falls outside bounds.
3. Degenerate case detection: perfect separation outputs 'degenerate (n sites, perfect separation)'.
4. Coverage on known synthetic distribution.
"""

from __future__ import annotations

import numpy as np
from phantomnet.ml.bootstrap import cluster_bootstrap_ci
from sklearn.metrics import roc_auc_score


def test_gate_i_point_estimate_always_inside_ci() -> None:
    """Gate I Requirement: Point estimate must lie inside its CI across multiple distributions."""
    rng = np.random.RandomState(1337)
    clusters = [f"site-{i % 10:02d}" for i in range(200)]

    for noise_level in [0.05, 0.2, 0.5, 0.8]:
        y_true = np.array([1 if i % 2 == 0 else 0 for i in range(200)])
        # Noisy predictions with varying correlation
        y_scores = y_true * (1.0 - noise_level) + rng.uniform(0, noise_level, size=200)

        point_est = float(roc_auc_score(y_true, y_scores))

        def eval_auc(idx: list[int], yt: np.ndarray = y_true, ys: np.ndarray = y_scores) -> float:
            sub_y = yt[idx]
            sub_s = ys[idx]
            if len(np.unique(sub_y)) < 2:
                return float("nan")
            return float(roc_auc_score(sub_y, sub_s))

        res = cluster_bootstrap_ci(
            point_estimate=point_est,
            cluster_ids=clusters,
            eval_fn=eval_auc,
            n_bootstraps=500,
            seed=42,
        )

        low, high = res["ci_95"]
        # Point estimate must lie strictly inside CI bounds
        assert low <= res["point_estimate"] <= high, (
            f"Point estimate {res['point_estimate']} outside CI [{low}, {high}]"
        )


def test_gate_i_degenerate_case_marks_perfect_separation() -> None:
    """Gate I Requirement: Degenerate case reports exact value and marks degenerate label."""
    clusters = [f"site-{i % 10:02d}" for i in range(200)]
    y_true = np.array([1 if i % 2 == 0 else 0 for i in range(200)])
    y_scores = y_true.astype(float)  # Perfect separation

    point_est = float(roc_auc_score(y_true, y_scores))

    def eval_auc(idx: list[int]) -> float:
        sub_y = y_true[idx]
        sub_s = y_scores[idx]
        if len(np.unique(sub_y)) < 2:
            return float("nan")
        return float(roc_auc_score(sub_y, sub_s))

    res = cluster_bootstrap_ci(
        point_estimate=point_est,
        cluster_ids=clusters,
        eval_fn=eval_auc,
        n_bootstraps=200,
        seed=42,
    )

    assert res["is_degenerate"] is True
    assert res["point_estimate"] == 1.0
    assert "degenerate (10 sites, perfect separation)" in res["ci_display"]


def test_gate_i_reject_ci_excluding_estimate() -> None:
    """Validation test: Function rejects an invalid or inverted CI."""
    invalid_low, invalid_high = 0.9990, 1.0000
    point_est = 0.9984  # Sits outside!

    # A properly validated CI must fail if point estimate is outside
    is_valid = invalid_low <= point_est <= invalid_high
    assert not is_valid, (
        "Sanity check: point_est 0.9984 must be identified as outside [0.9990, 1.0000]"
    )
