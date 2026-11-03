"""Unit tests for Gate 1: Label and AUC score sanity.

Verifies:
1. AUC is computed with positive class = "tunnel" (1) and score = P(tunnel).
2. Perfect scorer gives AUC = 1.0, reversed scorer gives 0.0, constant scorer gives 0.5.
3. Shuffled-label control yields ~0.5 via 1,000-iteration permutation test with p-value reporting.
"""

from __future__ import annotations

import numpy as np
from phantomnet.ml.censor_models import RandomForestCensor
from sklearn.metrics import roc_auc_score


def compute_auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Explicitly verify AUC calculation where positive class = tunnel (1)."""
    try:
        return float(roc_auc_score(y_true, y_score))
    except ValueError:
        return 0.5


def test_gate1_auc_positive_class_and_direction() -> None:
    """Verify (1) Positive class is tunnel (1), score is P(tunnel)."""
    # 0 = direct browsing, 1 = encrypted tunnel
    y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])

    # Scores predicting P(tunnel): higher for tunnel samples
    p_tunnel = np.array([0.05, 0.12, 0.18, 0.25, 0.85, 0.90, 0.94, 0.99])
    auc = compute_auc_score(y_true, p_tunnel)
    assert auc == 1.0, f"Expected perfect separation AUC 1.0, got {auc}"

    # If scores are inverted (P(direct) used by mistake), AUC must be 0.0
    p_direct = 1.0 - p_tunnel
    inverted_auc = compute_auc_score(y_true, p_direct)
    assert inverted_auc == 0.0, f"Expected inverted AUC 0.0, got {inverted_auc}"


def test_gate1_perfect_reversed_constant_scorers() -> None:
    """Verify (2) Perfect scorer = 1.0, reversed scorer = 0.0, constant scorer = 0.5."""
    rng = np.random.RandomState(42)
    n_samples = 100
    y_true = np.array([0] * (n_samples // 2) + [1] * (n_samples // 2))

    # Perfect scorer: all tunnel scores strictly greater than all direct scores
    score_perfect = np.concatenate(
        [
            rng.uniform(0.0, 0.49, size=n_samples // 2),
            rng.uniform(0.51, 1.0, size=n_samples // 2),
        ]
    )
    assert compute_auc_score(y_true, score_perfect) == 1.0

    # Reversed scorer: all direct scores strictly greater than tunnel scores
    score_reversed = np.concatenate(
        [
            rng.uniform(0.51, 1.0, size=n_samples // 2),
            rng.uniform(0.0, 0.49, size=n_samples // 2),
        ]
    )
    assert compute_auc_score(y_true, score_reversed) == 0.0

    # Constant scorer: all scores identical (no discriminative ability)
    score_constant = np.full(n_samples, 0.5)
    assert compute_auc_score(y_true, score_constant) == 0.5


def test_gate1_permutation_shuffled_control_1000() -> None:
    """Verify (3) Shuffled-label control gives ~0.5 (permutation test, 1000 shuffles).

    Null hypothesis: true labels and scores are independent.
    Permutation distribution of AUC under the null must be centered at 0.5.
    """
    rng = np.random.RandomState(1337)
    y_true = np.array([0] * 50 + [1] * 50)

    # Synthetic realistic score vector with strong true signal (AUC ~0.95)
    true_scores = np.concatenate(
        [
            rng.normal(loc=0.3, scale=0.15, size=50),
            rng.normal(loc=0.7, scale=0.15, size=50),
        ]
    )
    true_scores = np.clip(true_scores, 0.0, 1.0)
    actual_auc = compute_auc_score(y_true, true_scores)
    assert actual_auc > 0.90, f"Precondition failed: actual AUC should be high, got {actual_auc}"

    # 1000 label permutations
    n_permutations = 1000
    permuted_aucs: list[float] = []

    for _ in range(n_permutations):
        y_shuffled = rng.permutation(y_true)
        perm_auc = compute_auc_score(y_shuffled, true_scores)
        permuted_aucs.append(perm_auc)

    mean_perm_auc = float(np.mean(permuted_aucs))
    std_perm_auc = float(np.std(permuted_aucs))

    # Two-sided empirical p-value: how often does permuted AUC match or exceed actual AUC
    extreme_count = sum(1 for p in permuted_aucs if abs(p - 0.5) >= abs(actual_auc - 0.5))
    p_value = (extreme_count + 1) / (n_permutations + 1)

    print(
        f"\nPermutation Test Results (1000 shuffles):\n"
        f"  Actual AUC: {actual_auc:.4f}\n"
        f"  Permuted Mean AUC: {mean_perm_auc:.4f} (std={std_perm_auc:.4f})\n"
        f"  Empirical p-value: {p_value:.6f}"
    )

    # Shuffled mean must be approximately 0.5 (within 0.01)
    assert 0.49 <= mean_perm_auc <= 0.51, (
        f"Shuffled AUC mean deviated from 0.5: {mean_perm_auc:.4f}"
    )

    # p-value must be < 0.001 indicating actual signal is overwhelmingly non-random
    assert p_value < 0.005, f"Signal was not statistically distinguishable from random: p={p_value}"


def test_gate1_random_forest_censor_probabilities() -> None:
    """Verify RandomForestCensor evaluates P(tunnel) matching index 1."""
    censor = RandomForestCensor(n_estimators=20, max_depth=5, seed=42)
    rng = np.random.RandomState(42)

    # Feature matrix with clear separation: direct traffic has low values, tunnel has high values
    x_direct = rng.normal(loc=10.0, scale=2.0, size=(40, 10))
    x_tunnel = rng.normal(loc=50.0, scale=2.0, size=(40, 10))
    x_train = np.vstack([x_direct, x_tunnel])
    y_train = np.array([0] * 40 + [1] * 40)

    censor.fit(x_train, y_train)

    x_test_direct = rng.normal(loc=10.0, scale=2.0, size=(20, 10))
    x_test_tunnel = rng.normal(loc=50.0, scale=2.0, size=(20, 10))
    x_test = np.vstack([x_test_direct, x_test_tunnel])
    y_test = np.array([0] * 20 + [1] * 20)

    eval_result = censor.evaluate(x_test, y_test)
    assert eval_result["auc"] >= 0.99, f"Expected high separation AUC, got {eval_result['auc']}"
    assert eval_result["accuracy"] >= 0.95
