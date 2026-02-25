"""
Feature Reduction: select_features (AFML Ch.8).

Единая точка входа для отбора признаков перед обучением MetaLabeler.
Поддерживает три метода:

1. **"mda"** (Mean Decrease Accuracy) — permutation importance через CV.
   Рекомендуется по умолчанию. Интегрируется с PurgedKFold для корректной
   оценки важности на временных рядах.

2. **"mutual_info"** — взаимная информация с целевой переменной.
   Быстрее MDA, не требует CV. Хорошо для первичного отсева.

3. **"pca_variance"** — PCA с порогом объяснённой дисперсии.
   Возвращает оригинальные признаки с наибольшим вкладом в компоненты,
   покрывающие >= pca_variance_threshold дисперсии.

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch.8
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.feature_selection import mutual_info_classif
from sklearn.model_selection import BaseCrossValidator

from src.ml.feature_selection.importance import mda_importance


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
    Отбирает признаки по заданному методу.

    Args:
        X:                    DataFrame с признаками (n_samples x n_features).
        y:                    Целевая переменная (классификация).
        method:               Метод отбора: "mda", "mutual_info", "pca_variance".
        n_features:           Максимальное число отбираемых признаков.
                              Если в X меньше признаков — возвращаются все.
                              Для "pca_variance" служит верхней границей;
                              фактическое число определяется порогом дисперсии.
        cv:                   CV сплиттер для метода "mda".
                              По умолчанию PurgedKFold(n_splits=5).
        model:                sklearn-модель для метода "mda".
                              По умолчанию RandomForestClassifier(n_estimators=100).
        groups:               t1 Series для PurgedKFold purging (только "mda").
        pca_variance_threshold: Минимальная доля объяснённой дисперсии для
                              метода "pca_variance". Например, 0.95 = 95%.

    Returns:
        Список имён выбранных признаков (все — ключи X.columns).

    Raises:
        ValueError: при неизвестном значении method.
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

        # Число компонент, покрывающих >= pca_variance_threshold
        cumvar = np.cumsum(pca.explained_variance_ratio_)
        n_components = int(np.searchsorted(cumvar, pca_variance_threshold) + 1)
        n_components = min(n_components, n_features)

        # Для каждого исходного признака — сумма |загрузок| по отобранным компонентам
        # pca.components_ shape: (n_components_fitted, n_features)
        loadings = np.abs(pca.components_[:n_components])  # (n_comp, n_feat)
        feature_contribution = loadings.sum(axis=0)  # (n_feat,)

        ranked = pd.Series(feature_contribution, index=X.columns).sort_values(
            ascending=False
        )
        return [str(f) for f in ranked.index[:n_components]]

    raise ValueError(
        f"Неизвестный метод: {method!r}. "
        f"Допустимые: 'mda', 'mutual_info', 'pca_variance'."
    )
