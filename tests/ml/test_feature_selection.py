"""
Тесты для src/ml/feature_selection/importance.py и reduction.py.

Все тесты работают на синтетических данных без подключения к БД.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier

from src.ml.feature_selection.importance import (
    mda_importance,
    mdi_importance,
    sfi_importance,
)
from src.ml.feature_selection.reduction import select_features
from src.ml.validation.purged_kfold import PurgedKFold

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_dataset(
    n: int = 200,
    n_noise: int = 5,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Синтетический датасет: 2 сигнальных признака + n_noise шумовых.

    y = 1 если (signal_0 + signal_1) > 0, иначе 0.
    signal_* имеют высокую важность; noise_* — низкую.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")

    signal = rng.standard_normal((n, 2))
    noise = rng.standard_normal((n, n_noise))
    cols = ["signal_0", "signal_1"] + [f"noise_{i}" for i in range(n_noise)]
    X = pd.DataFrame(np.hstack([signal, noise]), index=idx, columns=cols)
    y = pd.Series((signal[:, 0] + signal[:, 1] > 0).astype(int), index=idx)

    return X, y


def _make_t1(X: pd.DataFrame, horizon: int = 10) -> pd.Series:
    """t1 Series для PurgedKFold: каждая метка «живёт» horizon баров вперёд."""
    n = len(X)
    exit_indices = np.minimum(np.arange(n) + horizon, n - 1)
    return pd.Series(X.index[exit_indices], index=X.index)


# ---------------------------------------------------------------------------
# MDI
# ---------------------------------------------------------------------------


def test_mdi_importance_ranking() -> None:
    """Сигнальные признаки ранжируются выше шумовых по MDI."""
    X, y = _make_dataset(n=500, n_noise=5)
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)

    importance = mdi_importance(model, list(X.columns))

    assert isinstance(importance, pd.Series)
    assert set(importance.index) == set(X.columns)
    assert importance.is_monotonic_decreasing
    np.testing.assert_allclose(importance.sum(), 1.0, atol=1e-9)

    # Хотя бы один сигнальный признак в топ-3
    top_3 = set(importance.index[:3])
    signal_feats = {"signal_0", "signal_1"}
    assert len(top_3 & signal_feats) >= 1, (
        f"Топ-3 MDI {top_3} не содержат сигнальных {signal_feats}"
    )


def test_mdi_importance_shape() -> None:
    """MDI возвращает Series той же длины, что и feature_names."""
    X, y = _make_dataset(n=100, n_noise=3)
    model = RandomForestClassifier(n_estimators=10, random_state=0)
    model.fit(X, y)

    importance = mdi_importance(model, list(X.columns))
    assert len(importance) == len(X.columns)
    assert importance.name == "mdi_importance"


def test_mdi_importance_no_feature_importances_raises() -> None:
    """Модель без feature_importances_ вызывает AttributeError."""
    model = DummyClassifier(strategy="most_frequent")
    model.fit([[0], [1]], [0, 1])

    with pytest.raises(AttributeError):
        mdi_importance(model, ["f1"])


# ---------------------------------------------------------------------------
# MDA
# ---------------------------------------------------------------------------


def test_mda_importance_with_purged_kfold() -> None:
    """MDA с PurgedKFold: сигнальные признаки имеют высокое среднее снижение."""
    X, y = _make_dataset(n=300, n_noise=3)
    t1 = _make_t1(X)

    cv = PurgedKFold(n_splits=3, embargo_pct=0.0)
    model = RandomForestClassifier(n_estimators=30, random_state=42)

    importance = mda_importance(model, X, y, cv=cv, scoring="accuracy", groups=t1)

    assert isinstance(importance, pd.Series)
    assert set(importance.index) == set(X.columns)
    assert importance.is_monotonic_decreasing

    # Хотя бы один сигнальный признак в топ-3
    top_3 = set(importance.index[:3])
    signal_feats = {"signal_0", "signal_1"}
    assert len(top_3 & signal_feats) >= 1, (
        f"Топ-3 MDA {top_3} не содержат сигнальных {signal_feats}"
    )


def test_mda_importance_shape() -> None:
    """MDA возвращает Series правильного размера и с правильным name."""
    X, y = _make_dataset(n=120, n_noise=2)
    model = RandomForestClassifier(n_estimators=10, random_state=0)
    cv = PurgedKFold(n_splits=3, embargo_pct=0.0)

    importance = mda_importance(model, X, y, cv=cv)

    assert len(importance) == len(X.columns)
    assert importance.name == "mda_importance"
    assert set(importance.index) == set(X.columns)


def test_mda_importance_default_cv() -> None:
    """MDA без явного cv использует PurgedKFold(n_splits=5) по умолчанию."""
    X, y = _make_dataset(n=200, n_noise=2)
    model = RandomForestClassifier(n_estimators=10, random_state=0)

    # Не должно падать
    importance = mda_importance(model, X, y)
    assert len(importance) == len(X.columns)


# ---------------------------------------------------------------------------
# SFI
# ---------------------------------------------------------------------------


def test_sfi_importance_shape() -> None:
    """SFI возвращает Series правильного размера, отсортированный по убыванию."""
    X, y = _make_dataset(n=120, n_noise=2)
    model = RandomForestClassifier(n_estimators=10, random_state=0)
    cv = PurgedKFold(n_splits=3, embargo_pct=0.0)

    importance = sfi_importance(model, X, y, cv=cv)

    assert isinstance(importance, pd.Series)
    assert len(importance) == len(X.columns)
    assert set(importance.index) == set(X.columns)
    assert importance.is_monotonic_decreasing
    assert importance.name == "sfi_importance"


# ---------------------------------------------------------------------------
# select_features — mda
# ---------------------------------------------------------------------------


def test_select_features_reduces_dim() -> None:
    """select_features(method='mda') уменьшает число признаков до n_features."""
    X, y = _make_dataset(n=200, n_noise=8)
    n_select = 4

    cv = PurgedKFold(n_splits=3, embargo_pct=0.0)
    model = RandomForestClassifier(n_estimators=20, random_state=0)

    selected = select_features(
        X, y, method="mda", n_features=n_select, cv=cv, model=model
    )

    assert isinstance(selected, list)
    assert len(selected) == n_select
    assert all(f in X.columns for f in selected)
    assert len(selected) == len(set(selected)), "Дублирующиеся имена признаков"


def test_select_features_mda_at_most_n_cols() -> None:
    """n_features >= len(X.columns) возвращает все признаки."""
    X, y = _make_dataset(n=100, n_noise=2)  # 4 признака итого
    cv = PurgedKFold(n_splits=3, embargo_pct=0.0)
    model = RandomForestClassifier(n_estimators=10, random_state=0)

    selected = select_features(X, y, method="mda", n_features=100, cv=cv, model=model)
    assert len(selected) == len(X.columns)


# ---------------------------------------------------------------------------
# select_features — mutual_info
# ---------------------------------------------------------------------------


def test_select_features_mutual_info() -> None:
    """select_features(method='mutual_info') отбирает корректное число признаков."""
    X, y = _make_dataset(n=200, n_noise=8)
    n_select = 3

    selected = select_features(X, y, method="mutual_info", n_features=n_select)

    assert isinstance(selected, list)
    assert len(selected) == n_select
    assert all(f in X.columns for f in selected)


# ---------------------------------------------------------------------------
# select_features — pca_variance
# ---------------------------------------------------------------------------


def test_select_features_pca() -> None:
    """
    select_features(method='pca_variance') возвращает n_components признаков,
    соответствующих числу PCA-компонент, которые покрывают >= threshold дисперсии.
    """
    from sklearn.decomposition import PCA

    X, y = _make_dataset(n=200, n_noise=8)
    threshold = 0.95

    # Ожидаемое число компонент
    pca = PCA().fit(X)
    cumvar = np.cumsum(pca.explained_variance_ratio_)
    expected_n = int(np.searchsorted(cumvar, threshold) + 1)

    selected = select_features(
        X, y, method="pca_variance", pca_variance_threshold=threshold
    )

    assert isinstance(selected, list)
    assert len(selected) == expected_n
    assert all(f in X.columns for f in selected)
    assert len(selected) == len(set(selected)), "Дублирующиеся имена признаков"


def test_select_features_pca_coverage() -> None:
    """
    Число компонент, возвращённых PCA-методом, >= 1 и <= n_features.
    """
    X, y = _make_dataset(n=150, n_noise=5)

    selected = select_features(
        X, y, method="pca_variance", n_features=50, pca_variance_threshold=0.90
    )

    assert 1 <= len(selected) <= min(50, len(X.columns))


# ---------------------------------------------------------------------------
# select_features — ошибки
# ---------------------------------------------------------------------------


def test_select_features_invalid_method() -> None:
    """Неизвестный метод вызывает ValueError."""
    X, y = _make_dataset(n=50, n_noise=2)

    with pytest.raises(ValueError, match="Неизвестный метод"):
        select_features(X, y, method="unknown")  # type: ignore[arg-type]
