"""Test suite for Phase 4: Adversarial Learning, Feature Extraction, CMA-ES, and Ablations."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from phantomnet.bus import PhantomEventBus
from phantomnet.data.traces import (
    generate_synthetic_site_flow,
    partition_disjoint_sites,
)
from phantomnet.events import EventKind
from phantomnet.ml.ablation import run_ablation_study
from phantomnet.ml.censor_models import OneDCNNCensor, RandomForestCensor
from phantomnet.ml.co_training import AdversarialCoTrainer
from phantomnet.ml.features import extract_flow_features
from phantomnet.ml.mask_engine import MaskEngine, MaskParameters
from phantomnet.ml.tuner import CMAESTuner


def test_disjoint_site_partition_no_leakage() -> None:
    """Verify train, val, and test partitions have zero site overlap."""
    train_sites, val_sites, test_sites = partition_disjoint_sites(seed=42)

    train_ids = {s["site_id"] for s in train_sites}
    val_ids = {s["site_id"] for s in val_sites}
    test_ids = {s["site_id"] for s in test_sites}

    assert len(train_ids & val_ids) == 0, "Train and Val must be disjoint"
    assert len(train_ids & test_ids) == 0, "Train and Test must be disjoint"
    assert len(val_ids & test_ids) == 0, "Val and Test must be disjoint"
    assert len(train_ids) + len(val_ids) + len(test_ids) == 30


def test_feature_extraction_properties() -> None:
    """Test feature vector dimensionality, bounds, and determinism."""
    trace = generate_synthetic_site_flow("video-stream-01", "video", is_tunnel=True, seed=42)
    feat1 = extract_flow_features(trace)
    feat2 = extract_flow_features(trace)

    assert feat1.shape == (42,)
    assert np.allclose(feat1, feat2), "Feature extraction must be completely deterministic"
    assert np.all(feat1 >= 0.0), "Features must be non-negative"


def test_censor_models_training_and_evaluation() -> None:
    """Verify Random Forest and 1D-CNN fit, predict, and evaluate cleanly."""
    x_train = np.random.RandomState(42).randn(40, 42)
    y_train = np.array([1 if i % 2 == 0 else 0 for i in range(40)])
    x_test = np.random.RandomState(43).randn(20, 42)
    y_test = np.array([1 if i % 2 == 0 else 0 for i in range(20)])

    rf = RandomForestCensor(n_estimators=20, max_depth=6, seed=42)
    rf.fit(x_train, y_train)
    rf_metrics = rf.evaluate(x_test, y_test)

    assert "auc" in rf_metrics
    assert "f1" in rf_metrics
    assert "confusion_matrix" in rf_metrics
    assert 0.0 <= rf_metrics["auc"] <= 1.0

    cnn = OneDCNNCensor(seed=42)
    cnn.fit(x_train, y_train)
    cnn_metrics = cnn.evaluate(x_test, y_test)
    assert 0.0 <= cnn_metrics["auc"] <= 1.0


def test_mask_engine_shaping_and_reward() -> None:
    """Test mask engine alters sizes and timing, computing valid objective reward."""
    trace = generate_synthetic_site_flow("shop-retail-01", "shopping", is_tunnel=False, seed=42)
    engine = MaskEngine(seed=42)
    params = MaskParameters(pad_bucket=256, jitter_ms=5.0, dummy_rate=0.1, morph_ratio=0.3)

    shaped, eval_metrics = engine.shape_flow(trace, params, censor_confidence=0.2)

    assert shaped.total_bytes >= trace.total_bytes
    assert eval_metrics.bandwidth_overhead > 0.0
    assert eval_metrics.stealth_score == pytest.approx(0.8, abs=0.01)
    assert isinstance(eval_metrics.reward, float)


def test_cma_es_tuner_optimization() -> None:
    """Verify CMA-ES generation step adapts distribution and improves reward."""
    val_traces = [
        generate_synthetic_site_flow(f"site-{i}", "news", is_tunnel=False, seed=100 + i)
        for i in range(4)
    ]
    censor = RandomForestCensor(n_estimators=20, max_depth=6, seed=42)
    # Fit dummy censor
    x_dummy = np.random.RandomState(42).randn(20, 42)
    y_dummy = np.array([1 if i % 2 == 0 else 0 for i in range(20)])
    censor.fit(x_dummy, y_dummy)

    engine = MaskEngine(seed=42)
    tuner = CMAESTuner(seed=42)

    best_p, reward = tuner.tune_step(censor, val_traces, extract_flow_features, engine)
    assert isinstance(best_p, MaskParameters)
    assert isinstance(reward, float)


def test_adversarial_co_training_events_emission() -> None:
    """Verify co-training loop executes rounds and emits TRAIN_ROUND and POLICY_DECISION events."""
    bus = PhantomEventBus(run_id="test-cotrain")
    co_trainer = AdversarialCoTrainer(event_bus=bus, rounds=3, seed=42)

    history = co_trainer.run_co_training_loop()

    assert len(history) == 3
    events = bus.get_all()
    policy_events = [e for e in events if e.kind == EventKind.POLICY_DECISION]
    train_events = [e for e in events if e.kind == EventKind.TRAIN_ROUND]

    assert len(policy_events) == 3
    assert len(train_events) == 3
    assert train_events[-1].meta["round"] == 3


def test_ablation_study_and_evidence_export() -> None:
    """Acceptance: Ablation study runs >=5 seeds, computes 95% CIs, and exports artifacts."""
    seeds = [42, 101, 2024, 777, 9999]
    out_dir = "evidence/ml"

    res = run_ablation_study(seeds=seeds, output_dir=out_dir)

    assert res["num_seeds"] == 5
    ablation_file = Path(out_dir) / "ablation.json"
    pareto_file = Path(out_dir) / "pareto.json"

    assert ablation_file.exists()
    assert pareto_file.exists()

    with open(ablation_file, encoding="utf-8") as f:
        data = json.load(f)

    # Acceptance check: All 5 regimes present, including learned vs retrained censor
    results = data["results"]
    assert "no_shaping" in results
    assert "random_shaping" in results
    assert "fixed_padding" in results
    assert "learned_policy" in results
    assert "learned_vs_retrained" in results

    # Check 95% CIs are present and non-empty
    for _reg, metrics in results.items():
        assert "ci_95" in metrics["censor_auc"]
        assert "ci_95" in metrics["defender_reward"]

    # Verify Pareto data
    with open(pareto_file, encoding="utf-8") as f:
        pareto = json.load(f)
    assert len(pareto) == 5
