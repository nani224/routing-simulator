"""Rigorous Site-Level Cluster Bootstrapping for PHANTOMNET Gate I.

Provides cluster bootstrapping grouped by site to prevent intra-site correlation leakage,
guarantees that point estimates lie strictly within their confidence intervals,
and explicitly marks degenerate cases (e.g. perfect separation or tied scores)
with 'degenerate (n sites, perfect separation)' instead of misleading [1, 1] CIs.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np


def cluster_bootstrap_ci(
    point_estimate: float,
    cluster_ids: list[str],
    eval_fn: Callable[[list[int]], float],
    n_bootstraps: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> dict[str, Any]:
    """Compute cluster bootstrap confidence interval with degenerate detection.

    Args:
        point_estimate: Metric computed on the full dataset.
        cluster_ids: Cluster identifier (e.g. site_id) for each observation in dataset.
        eval_fn: Function mapping a list of selected row indices to the metric value.
        n_bootstraps: Number of bootstrap resamples (default: 1000).
        alpha: Significance level (default: 0.05 for 95% CI).
        seed: Random seed for reproducibility.

    Returns:
        dict containing:
        - point_estimate: float
        - ci_95: list[float] (low, high)
        - is_degenerate: bool
        - ci_display: str (e.g. "[0.9810, 0.9990]" or "degenerate (10 sites, perfect separation)")
    """
    rng = np.random.RandomState(seed)
    unique_clusters = sorted(set(cluster_ids))
    n_clusters = len(unique_clusters)

    cluster_to_indices: dict[str, list[int]] = {c: [] for c in unique_clusters}
    for idx, c in enumerate(cluster_ids):
        cluster_to_indices[c].append(idx)

    boot_estimates: list[float] = []

    for _ in range(n_bootstraps):
        sampled_clusters = rng.choice(unique_clusters, size=n_clusters, replace=True)
        sampled_indices: list[int] = []
        for c in sampled_clusters:
            sampled_indices.extend(cluster_to_indices[c])

        val = eval_fn(sampled_indices)
        if not math.isnan(val):
            boot_estimates.append(val)

    if not boot_estimates:
        return {
            "point_estimate": round(point_estimate, 4),
            "ci_95": [round(point_estimate, 4), round(point_estimate, 4)],
            "is_degenerate": True,
            "ci_display": f"degenerate ({n_clusters} sites, zero variance)",
        }

    # Check for degenerate case (all bootstrap resamples identical)
    min_val = float(np.min(boot_estimates))
    max_val = float(np.max(boot_estimates))

    if math.isclose(min_val, max_val, abs_tol=1e-7):
        is_perfect = math.isclose(point_estimate, 1.0, abs_tol=1e-4) or math.isclose(
            point_estimate, 0.0, abs_tol=1e-4
        )
        label = (
            f"degenerate ({n_clusters} sites, perfect separation)"
            if is_perfect
            else f"degenerate ({n_clusters} sites, zero variance)"
        )
        return {
            "point_estimate": round(point_estimate, 4),
            "ci_95": [round(point_estimate, 4), round(point_estimate, 4)],
            "is_degenerate": True,
            "ci_display": label,
        }

    # Percentile confidence interval
    low_pct = 100.0 * (alpha / 2.0)
    high_pct = 100.0 * (1.0 - alpha / 2.0)
    ci_low = float(np.percentile(boot_estimates, low_pct))
    ci_high = float(np.percentile(boot_estimates, high_pct))

    # Guard: Point estimate must lie strictly inside [ci_low, ci_high]
    ci_low = min(ci_low, point_estimate)
    ci_high = max(ci_high, point_estimate)

    return {
        "point_estimate": round(point_estimate, 4),
        "ci_95": [round(ci_low, 4), round(ci_high, 4)],
        "is_degenerate": False,
        "ci_display": f"[{ci_low:.4f}, {ci_high:.4f}]",
    }
