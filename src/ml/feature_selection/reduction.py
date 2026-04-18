"""
Feature Reduction: select_features (AFML Ch.8).

Single entry point for feature selection before training MetaLabeler.
Supports three methods:

1. **"mda"** (Mean Decrease Accuracy) — permutation importance via CV.
   Recommended by default. Integrates with PurgedKFold for correct
   importance estimation on time series.

2. **"mutual_info"** — mutual information with the target variable.
   Faster than MDA, no CV required. Good for initial screening.

3. **"pca_variance"** — PCA with explained variance threshold.
   Returns original features with the highest contribution to components
   covering >= pca_variance_threshold of variance.

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.8
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.feature_selection import mutual_info_classif

from src.ml.feature_selection.importance import mda_importance

if TYPE_CHECKING:
    from sklearn.model_selection import BaseCrossValidator


def select_features(
    X: pd.DataFrame,
    y: pd.Series,
    method: Literal["mda", "mutual_info", "pca_variance"] = "mda",
    n_features: int = 50,
    cv: BaseCrossValidator | None = None,
    model: Any = None,
    groups: pd.Series | None = None,
    pca_variance_threshold: float = 0.95,
) -> list[str]:
    """
    Selects features using the specified method.

    Args:
        X:                    DataFrame of features (n_samples x n_features).
        y:                    Target variable (classification).
        method:               Selection method: "mda", "mutual_info", "pca_variance".
        n_features:           Maximum number of features to select.
                              If X has fewer features, all are returned.
                              For "pca_variance" serves as an upper bound;
                              actual count is determined by the variance threshold.
        cv:                   CV splitter for the "mda" method.
                              Defaults to PurgedKFold(n_splits=5).
        model:                sklearn model for the "mda" method.
                              Defaults to RandomForestClassifier(n_estimators=100).
        groups:               t1 Series for PurgedKFold purging ("mda" only).
        pca_variance_threshold: Minimum fraction of explained variance for
                              the "pca_variance" method. E.g., 0.95 = 95%.

    Returns:
        List of selected feature names (all keys from X.columns).

    Raises:
        ValueError: for unknown method value.
    """
    if method == "mda":
        if model is None:
            from sklearn.ensemble import RandomForestClassifier

            model = RandomForestClassifier(n_estimators=100, random_state=0, n_jobs=-1)

        importance = mda_importance(model, X, y, cv=cv, groups=groups)
        return [str(f) for f in importance.index[:n_features]]

    if method == "mutual_info":
        mi = mutual_info_classif(X, y, random_state=0)
        mi_series = pd.Series(mi, index=X.columns).sort_values(ascending=False)
        return [str(f) for f in mi_series.index[:n_features]]

    if method == "pca_variance":
        n_fit = min(n_features, X.shape[1], X.shape[0])
        pca = PCA(n_components=n_fit)
        pca.fit(X)

        # Number of components covering >= pca_variance_threshold
        cumvar = np.cumsum(pca.explained_variance_ratio_)
        n_components = int(np.searchsorted(cumvar, pca_variance_threshold) + 1)
        n_components = min(n_components, n_features)

        # For each original feature — sum of |loadings| across selected components
        # pca.components_ shape: (n_components_fitted, n_features)
        loadings = np.abs(pca.components_[:n_components])  # (n_comp, n_feat)
        feature_contribution = loadings.sum(axis=0)  # (n_feat,)

        ranked = pd.Series(feature_contribution, index=X.columns).sort_values(
            ascending=False
        )
        return [str(f) for f in ranked.index[:n_components]]

    raise ValueError(
        f"Unknown method: {method!r}. "
        f"Allowed values: 'mda', 'mutual_info', 'pca_variance'."
    )
