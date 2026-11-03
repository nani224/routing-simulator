"""Unit tests for Gate J.3: Smooth Fitness Function and Generation Curve Logging.

Verifies:
1. /evidence/ml/fitness.json exists and has valid structure with multi-generation curve.
2. The fitness curve is not constant across generations.
3. CMAESTuner executes multi-objective optimization with continuous loss components
   (mean censor probability, Wasserstein distances for packet sizes and gaps,
   bandwidth overhead, and latency penalty).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from phantomnet.data.traces import FlowTrace, PacketMeta
from phantomnet.ml.features import extract_flow_features
from phantomnet.ml.morphing import EmpiricalTLSDistribution
from phantomnet.ml.tuner import CMAESTuner
from sklearn.ensemble import RandomForestClassifier

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_fitness_json_artifact_exists_and_curve_is_not_constant() -> None:
    """Verify evidence/ml/fitness.json exists and logs a non-constant fitness curve."""
    fitness_file = REPO_ROOT / "evidence" / "ml" / "fitness.json"
    assert fitness_file.exists(), "evidence/ml/fitness.json must exist"

    with open(fitness_file, encoding="utf-8") as f:
        data = json.load(f)

    assert "optimizer" in data
    assert "objective" in data
    assert "generations_run" in data
    assert "fitness_curve" in data

    curve = data["fitness_curve"]
    assert len(curve) >= 2, f"Fitness curve must contain at least 2 generations, got {len(curve)}"

    # Verify each generation log contains required multi-objective metrics
    for gen_log in curve:
        assert "generation" in gen_log
        assert "best_loss" in gen_log
        assert "mean_censor_p" in gen_log
        assert "w_size_distance" in gen_log
        assert "w_gap_distance" in gen_log
        assert "bandwidth_overhead_pct" in gen_log
        assert "latency_cost_ms" in gen_log

    # Check that the curve is not constant
    losses = [g["best_loss"] for g in curve]
    # Verify not all losses are identical
    distinct_losses = set(losses)
    assert len(distinct_losses) > 1, f"Fitness curve must not be constant: {losses}"


def test_cma_es_smooth_fitness_optimization_progression() -> None:
    """Verify CMA-ES optimizer runs on sample flows and records progression."""
    # Construct synthetic direct TLS and tunnel flows
    rng = np.random.RandomState(42)

    tls_flows: list[FlowTrace] = []
    tun_flows: list[FlowTrace] = []

    for i in range(10):
        # TLS flows have larger TX packets (ClientHello ~240, TLS record ~137)
        tls_pkts = [
            PacketMeta(size=int(rng.choice([240, 137, 1400])), direction="TX", dt=0.01)
            for _ in range(12)
        ]
        tls_flows.append(
            FlowTrace(site_id=f"site-{i}", category="news", is_tunnel=False, packets=tls_pkts)
        )

        # Tunnel flows have smaller TX packets (96, 128, 88)
        tun_pkts = [
            PacketMeta(size=int(rng.choice([96, 128, 88])), direction="TX", dt=0.01)
            for _ in range(12)
        ]
        tun_flows.append(
            FlowTrace(site_id=f"site-{i}", category="news", is_tunnel=True, packets=tun_pkts)
        )

    # Fit a mock censor
    all_flows = tls_flows + tun_flows
    x_train = np.array([extract_flow_features(f) for f in all_flows], dtype=np.float64)
    y_train = np.array([0] * len(tls_flows) + [1] * len(tun_flows), dtype=np.int32)

    censor = RandomForestClassifier(n_estimators=10, max_depth=4, random_state=42)
    censor.fit(x_train, y_train)

    tls_dist = EmpiricalTLSDistribution()
    tls_dist.fit_from_flows(tls_flows)

    tuner = CMAESTuner(pop_size=6, seed=42)
    best_params = tuner.optimize(
        censor=censor,
        train_tunnel_flows=tun_flows,
        train_tls_flows=tls_flows,
        feature_extractor=extract_flow_features,
        num_generations=2,
        target_distribution=tls_dist,
    )

    assert best_params is not None
    assert len(tuner.fitness_history) == 2
    # Verify fitness is finite and non-negative
    for entry in tuner.fitness_history:
        assert entry["best_loss"] >= 0.0
        assert 0.0 <= entry["mean_censor_p"] <= 1.0
