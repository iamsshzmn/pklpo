"""
Feature Importance: MDI, MDA, SFI (AFML Ch.8).

Три метода оценки важности признаков для tree-based моделей:

1. **MDI (Mean Decrease Impurity)** — читает feature_importances_ напрямую.
   Быстро, но смещено в пользу высококардинальных признаков.

2. **MDA (Mean Decrease Accuracy)** — permutation importance через CV.
   Для каждого фолда: обучает модель, затем поочерёдно перемешивает каждый
   признак в тестовой выборке и измеряет падение метрики. Менее смещено, чем MDI.

3. **SFI (Single Feature Importance)** — обучает модель отдельно на каждом признаке.
   Наименее смещено, но медленно (O(n_features) обучений).

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.8
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import check_scoring
from sklearn.model_selection import BaseCrossValidator, cross_val_score

from src.ml.validation.purged_kfold import PurgedKFold


def mdi_importance(model: Any, feature_names: list[str]) -> pd.Series:
    """
    Mean Decrease Impurity — читает feature_importances_ из обученной модели.

    Args:
        model:         Обученная tree-based модель с атрибутом feature_importances_
                       (например, RandomForestClassifier).
        feature_names: Список имён признаков (должен совпадать с порядком X.columns
                       при обучении модели).

    Returns:
        pd.Series[feature_name -> importance], отсортированный по убыванию.
        Сумма значений ≈ 1.0 (стандартное свойство feature_importances_).

    Raises:
        AttributeError: если model не имеет атрибута feature_importances_.
    """
    importances = np.array(model.feature_importances_, dtype=float)
    result = pd.Series(importances, index=feature_names, name="mdi_importance")
    return result.sort_values(ascending=False)


def mda_importance(
    model: Any,
    X: pd.DataFrame,
    y: pd.Series,
    cv: BaseCrossValidator | None = None,
    scoring: str = "accuracy",
    groups: pd.Series | None = None,
    random_state: int = 0,
) -> pd.Series:
    """
    Mean Decrease Accuracy — permutation importance через кросс-валидацию.

    Для каждого фолда:
      1. Клонирует и обучает model на train_idx.
      2. Вычисляет baseline_score на test_idx.
      3. Для каждого признака: перемешивает значения в test, измеряет score.
         MDA для признака = baseline - permuted_score.
    Возвращает среднее MDA по всем фолдам, отсортированное по убыванию.

    Args:
        model:        sklearn-совместимый классификатор (не обязательно обученный;
                      клонируется для каждого фолда).
        X:            DataFrame с признаками (DatetimeIndex для PurgedKFold).
        y:            Целевые метки.
        cv:           BaseCrossValidator. По умолчанию PurgedKFold(n_splits=5).
        scoring:      Метрика ("accuracy", "roc_auc", ...).
        groups:       t1 Series для PurgedKFold purging.
        random_state: Seed для воспроизводимости перемешивания.

    Returns:
        pd.Series[feature_name -> mean_decrease_accuracy], отсортированный по убыванию.
    """
    if cv is None:
        cv = PurgedKFold(n_splits=5)

    rng = np.random.default_rng(random_state)
    scorer = check_scoring(model, scoring=scoring)
    feature_names = list(X.columns)

    # accumulate fold decreases: shape (n_splits, n_features)
    decreases: list[np.ndarray] = []

    for train_idx, test_idx in cv.split(X, y, groups=groups):
        X_train = X.iloc[train_idx]
        y_train = y.iloc[train_idx]
        X_test = X.iloc[test_idx].copy()
        y_test = y.iloc[test_idx]

        est = clone(model)
        est.fit(X_train, y_train)
        baseline = scorer(est, X_test, y_test)

        fold_decreases = np.zeros(len(feature_names))
        for k, feat in enumerate(feature_names):
            original_col = X_test[feat].values.copy()
            X_test.loc[:, feat] = rng.permutation(original_col)
            perm_score = scorer(est, X_test, y_test)
            fold_decreases[k] = baseline - perm_score
            X_test.loc[:, feat] = original_col  # restore

        decreases.append(fold_decreases)

    mean_decreases = np.mean(decreases, axis=0)
    result = pd.Series(mean_decreases, index=feature_names, name="mda_importance")
    return result.sort_values(ascending=False)


def sfi_importance(
    model: Any,
    X: pd.DataFrame,
    y: pd.Series,
    cv: BaseCrossValidator | None = None,
    scoring: str = "accuracy",
    groups: pd.Series | None = None,
) -> pd.Series:
    """
    Single Feature Importance — обучает модель на каждом признаке по отдельности.

    Для каждого признака вычисляет средний CV-score при обучении только на нём.
    Наименее смещено из трёх методов, но медленно: O(n_features) обучений.

    Args:
        model:   sklearn-совместимый классификатор.
        X:       DataFrame с признаками.
        y:       Целевые метки.
        cv:      BaseCrossValidator. По умолчанию PurgedKFold(n_splits=5).
        scoring: Метрика ("accuracy", "roc_auc", ...).
        groups:  t1 Series для PurgedKFold purging.

    Returns:
        pd.Series[feature_name -> mean_cv_score], отсортированный по убыванию.
    """
    if cv is None:
        cv = PurgedKFold(n_splits=5)

    feature_names = list(X.columns)
    scores: dict[str, float] = {}

    for feat in feature_names:
        X_f = X[[feat]]
        feat_scores = cross_val_score(
            model, X_f, y, cv=cv, scoring=scoring, groups=groups
        )
        scores[feat] = float(np.mean(feat_scores))

    result = pd.Series(scores, name="sfi_importance")
    return result.sort_values(ascending=False)
