"""
CalibratedMetaLabeler: MetaLabeler with explicit calibration parameters.

Unlike MetaLabeler(calibrate=True), which uses default sigmoid/cv=5,
CalibratedMetaLabeler provides direct access to:
  - calibration method: "sigmoid" (Platt scaling) or "isotonic" regression
  - number of CV folds for calibration
  - Brier score and reliability curve for assessing probability reliability

Reference: Niculescu-Mizil & Caruana (2005), "Predicting Good Probabilities With
           Supervised Learning", ICML
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss

from src.ml.metalabeling.pipeline import MetaLabeler

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd


class CalibratedMetaLabeler(MetaLabeler):
    """
    MetaLabeler with explicit probability calibration configuration.

    Extends MetaLabeler by adding:
      - selection of calibration method ("sigmoid" | "isotonic")
      - selection of number of CV folds for CalibratedClassifierCV
      - method ``calibration_score()`` — Brier score for reliability assessment
      - method ``reliability_curve()`` — data for reliability diagram

    Args:
        base_model:          sklearn-compatible classifier.
        calibration_method:  Calibration method: "sigmoid" or "isotonic".
        cv:                  Number of folds for CalibratedClassifierCV (>= 2).
        feature_selector:    Callable[[X, y], list[str]] for feature selection.

    Example::

        labeler = CalibratedMetaLabeler(
            calibration_method="isotonic", cv=3
        )
        labeler.fit(X_train, y_train)
        brier = labeler.calibration_score(X_test, y_test)
        frac, pred = labeler.reliability_curve(X_test, y_test, n_bins=10)
    """

    def __init__(
        self,
        base_model: Any = None,
        calibration_method: str = "sigmoid",
        cv: int = 5,
        feature_selector: Callable[[pd.DataFrame, pd.Series], list[str]] | None = None,
    ) -> None:
        if calibration_method not in ("sigmoid", "isotonic"):
            raise ValueError(
                f"calibration_method must be 'sigmoid' or 'isotonic', "
                f"got {calibration_method!r}"
            )
        if cv < 2:
            raise ValueError(f"cv must be >= 2, got {cv}")

        # calibrate=True is enforced — that is the purpose of this class
        super().__init__(
            base_model=base_model,
            calibrate=True,
            feature_selector=feature_selector,
        )
        self.calibration_method = calibration_method
        self.cv = cv

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        sample_weight: pd.Series | np.ndarray | None = None,
    ) -> CalibratedMetaLabeler:
        """
        Trains the model with explicit calibration parameters.

        Overrides the parent fit to use calibration_method and cv.

        Args:
            X:             Feature matrix.
            y:             Target labels.
            sample_weight: Optional sample weights.

        Returns:
            self (for method chaining).
        """
        if self.feature_selector is not None:
            self._selected_features = self.feature_selector(X, y)
            X_fit = X[self._selected_features]
        else:
            self._selected_features = list(X.columns)
            X_fit = X

        model: Any = CalibratedClassifierCV(
            clone(self.base_model),
            cv=self.cv,
            method=self.calibration_method,
        )

        if sample_weight is not None:
            sw = np.asarray(sample_weight)
            model.fit(X_fit, y, sample_weight=sw)
        else:
            model.fit(X_fit, y)

        self._fitted_model = model
        return self

    def calibration_score(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> float:
        """
        Computes Brier score to assess calibration reliability.

        Brier score = mean((p_i - y_i)^2). Lower is better.
        Random classifier ~ 0.25 (with 50/50 classes).

        Args:
            X: Feature matrix (test).
            y: True labels (test).

        Returns:
            float in range [0.0, 1.0]. 0.0 — perfect calibration.

        Raises:
            RuntimeError: if the model has not been trained.
        """
        proba = self.predict_proba(X)
        return float(brier_score_loss(y, proba[:, 1]))

    def reliability_curve(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_bins: int = 10,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Returns data for a reliability diagram (calibration curve).

        Args:
            X:      Feature matrix (test).
            y:      True labels.
            n_bins: Number of bins (affects curve granularity).

        Returns:
            Tuple (fraction_of_positives, mean_predicted_value):
              - fraction_of_positives: true fraction of positives in each bin.
              - mean_predicted_value:  mean predicted probability in each bin.

        Raises:
            RuntimeError: if the model has not been trained.
        """
        proba = self.predict_proba(X)
        frac, pred = calibration_curve(y, proba[:, 1], n_bins=n_bins)
        return np.asarray(frac), np.asarray(pred)
