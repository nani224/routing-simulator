"""Machine Learning Censor classifiers: Random Forest and 1D Deep Representation.

Evaluated strictly on held-out sites to prevent data leakage.
Reports AUC, F1 score, confusion matrix, precision, and recall.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.neural_network import MLPClassifier


class RandomForestCensor:
    """Random Forest traffic classifier trained on statistical flow metadata."""

    def __init__(self, n_estimators: int = 100, max_depth: int = 12, seed: int = 42) -> None:
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=seed,
            n_jobs=1,
        )
        self.is_fitted = False

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model.fit(x, y)
        self.is_fitted = True

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return np.full((len(x), 2), 0.5)
        res: np.ndarray = np.asarray(self.model.predict_proba(x))
        return res

    def evaluate(self, x_test: np.ndarray, y_test: np.ndarray) -> dict[str, Any]:
        """Compute comprehensive performance metrics on held-out test data."""
        if not self.is_fitted or len(x_test) == 0:
            return {"auc": 0.5, "f1": 0.0, "accuracy": 0.5}

        probs = self.predict_proba(x_test)[:, 1]
        preds = (probs >= 0.5).astype(int)

        try:
            auc = float(roc_auc_score(y_test, probs))
        except ValueError:
            auc = 0.5

        f1 = float(f1_score(y_test, preds, zero_division=0))
        acc = float(accuracy_score(y_test, preds))
        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))
        cm = confusion_matrix(y_test, preds).tolist()

        return {
            "auc": round(auc, 4),
            "f1": round(f1, 4),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "confusion_matrix": cm,
        }


class OneDCNNCensor:
    """1D Deep Feature classifier serving as the deep learning censor."""

    def __init__(self, hidden_layer_sizes: tuple[int, ...] = (64, 32), seed: int = 42) -> None:
        self.model = MLPClassifier(
            hidden_layer_sizes=hidden_layer_sizes,
            activation="relu",
            max_iter=300,
            random_state=seed,
        )
        self.is_fitted = False

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model.fit(x, y)
        self.is_fitted = True

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return np.full((len(x), 2), 0.5)
        res: np.ndarray = np.asarray(self.model.predict_proba(x))
        return res

    def evaluate(self, x_test: np.ndarray, y_test: np.ndarray) -> dict[str, Any]:
        if not self.is_fitted or len(x_test) == 0:
            return {"auc": 0.5, "f1": 0.0, "accuracy": 0.5}

        probs = self.predict_proba(x_test)[:, 1]
        preds = (probs >= 0.5).astype(int)

        try:
            auc = float(roc_auc_score(y_test, probs))
        except ValueError:
            auc = 0.5

        f1 = float(f1_score(y_test, preds, zero_division=0))
        acc = float(accuracy_score(y_test, preds))
        cm = confusion_matrix(y_test, preds).tolist()

        return {
            "auc": round(auc, 4),
            "f1": round(f1, 4),
            "accuracy": round(acc, 4),
            "confusion_matrix": cm,
        }
