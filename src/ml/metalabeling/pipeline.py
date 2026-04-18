"""
MetaLabeler: pipeline for filtering trading signals (AFML Ch.10).

Wrapper around an sklearn classifier with:
  - Feature selection (MDI/MDA/SFI from Block E)
  - Optional probability calibration (CalibratedClassifierCV)
  - Support for uniqueness sample weights (from Block C)
  - Save/load artifacts via joblib bound to RunContext

Artifact storage: local files in {data_dir}/artifacts/{run_id}/.
S3 — out of scope for this phase.

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.10
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import joblib
import numpy as np
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pandas as pd

    from src.core.run_context import RunContext


class MetaLabeler:
    """
    Metalabeling pipeline — trains a secondary classifier for signal filtering.

    Accepts feature matrix X and labels y (from triple_barrier_labels),
    optionally selects features, and trains base_model.

    Compatible with MetaScorer Protocol (predict_proba).

    Args:
        base_model:       sklearn-compatible classifier.
                          Defaults to RandomForestClassifier(n_estimators=100).
        calibrate:        If True, wraps base_model in CalibratedClassifierCV.
        feature_selector: Callable[[X, y], list[str]] — feature selection function.
                          Example: ``lambda X, y: select_features(X, y, method="mda")``.
                          If None, all features are used.

    Example::

        labeler = MetaLabeler(
            feature_selector=lambda X, y: select_features(X, y, method="mutual_info", n_features=30)
        )
        labeler.fit(X_train, y_train, sample_weight=weights)
        proba = labeler.predict_proba(X_test)
    """

    def __init__(
        self,
        base_model: Any = None,
        calibrate: bool = True,
        feature_selector: Callable[[pd.DataFrame, pd.Series], list[str]] | None = None,
    ) -> None:
        if base_model is None:
            from sklearn.ensemble import RandomForestClassifier

            base_model = RandomForestClassifier(
                n_estimators=100, random_state=0, n_jobs=1
            )
        self.base_model = base_model
        self.calibrate = calibrate
        self.feature_selector = feature_selector
        self._fitted_model: Any = None
        self._selected_features: list[str] | None = None
        self._run_context: RunContext | None = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        sample_weight: pd.Series | np.ndarray | None = None,
    ) -> MetaLabeler:
        """
        Trains the MetaLabeler on data X, y.

        Steps:
          1. feature_selector(X, y) -> feature selection (if provided).
          2. Build model (with CalibratedClassifierCV if calibrate=True).
          3. fit(X_selected, y, sample_weight).

        Args:
            X:             Feature matrix.
            y:             Target labels.
            sample_weight: Optional sample weights (from get_uniqueness_weights).

        Returns:
            self (for method chaining).
        """
        if self.feature_selector is not None:
            self._selected_features = self.feature_selector(X, y)
            X_fit = X[self._selected_features]
        else:
            self._selected_features = list(X.columns)
            X_fit = X

        if self.calibrate:
            model: Any = CalibratedClassifierCV(
                clone(self.base_model), cv=5, method="sigmoid"
            )
        else:
            model = clone(self.base_model)

        if sample_weight is not None:
            sw = np.asarray(sample_weight)
            model.fit(X_fit, y, sample_weight=sw)
        else:
            model.fit(X_fit, y)

        self._fitted_model = model
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predicts class probabilities.

        Args:
            X: Feature matrix (must contain the same columns as during training).

        Returns:
            np.ndarray of shape (n_samples, n_classes).

        Raises:
            RuntimeError: if the model has not been trained (fit was not called).
        """
        if self._fitted_model is None:
            raise RuntimeError("MetaLabeler is not trained. Call fit() first.")
        if self._selected_features is not None:
            X_pred = X[self._selected_features]
        else:
            X_pred = X
        return np.asarray(self._fitted_model.predict_proba(X_pred))

    def save(self, path: Path, run_context: RunContext) -> None:
        """
        Saves the trained model as a joblib artifact.

        Creates parent directories if needed.

        Args:
            path:        Path to the artifact file.
            run_context: RunContext for binding the artifact to a run_id.

        Raises:
            RuntimeError: if the model has not been trained (fit was not called).
        """
        if self._fitted_model is None:
            raise RuntimeError("MetaLabeler is not trained. Call fit() first.")
        self._run_context = run_context
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self._fitted_model,
                "selected_features": self._selected_features,
                "run_context": run_context,
                "calibrate": self.calibrate,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> MetaLabeler:
        """
        Loads a trained MetaLabeler from a joblib artifact.

        Args:
            path: Path to the artifact file.

        Returns:
            MetaLabeler with restored model and run_context.
        """
        data: dict[str, Any] = joblib.load(path)
        obj = cls.__new__(cls)
        obj._fitted_model = data["model"]
        obj._selected_features = data["selected_features"]
        obj._run_context = data["run_context"]
        obj.calibrate = data["calibrate"]
        obj.base_model = None
        obj.feature_selector = None
        return obj

    @property
    def run_context(self) -> RunContext | None:
        """RunContext of the artifact (None if model has not been saved)."""
        return self._run_context

    @property
    def selected_features(self) -> list[str] | None:
        """List of features selected during training (None if fit was not called)."""
        return self._selected_features

    @property
    def n_features_in(self) -> int | None:
        """Number of features used during training."""
        if self._selected_features is None:
            return None
        return len(self._selected_features)
