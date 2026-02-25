"""
Тесты для src/ml/validation/purged_kfold.py и src/ml/validation/cpcv.py.

Все тесты работают на синтетических данных без подключения к БД.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import cross_val_score

from src.ml.validation.cpcv import CombinatorialPurgedCV
from src.ml.validation.purged_kfold import PurgedKFold

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_dataset(n: int = 200, n_features: int = 3, seed: int = 42):
    """
    Создаёт синтетический dataset с DatetimeIndex и соответствующий t1.

    Returns:
        X:  DataFrame[n x n_features] с DatetimeIndex UTC
        y:  Series[n] с метками 0/1
        t1: Series[entry_ts -> exit_ts], горизонт = 10 баров
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    X = pd.DataFrame(rng.standard_normal((n, n_features)), index=idx)
    y = pd.Series(rng.integers(0, 2, n), index=idx, dtype=int)

    # t1: каждая метка «живёт» 10 баров вперёд
    horizon = 10
    exit_indices = np.minimum(np.arange(n) + horizon, n - 1)
    t1 = pd.Series(idx[exit_indices], index=idx)

    return X, y, t1


# ---------------------------------------------------------------------------
# PurgedKFold: базовые свойства
# ---------------------------------------------------------------------------


def test_purged_kfold_split_count() -> None:
    """Число сплитов = n_splits."""
    X, y, t1 = _make_dataset(n=100)
    cv = PurgedKFold(n_splits=5)

    splits = list(cv.split(X, y, groups=t1))
    assert len(splits) == 5


def test_purged_kfold_get_n_splits() -> None:
    """get_n_splits() возвращает корректное значение."""
    cv = PurgedKFold(n_splits=4)
    assert cv.get_n_splits() == 4


def test_purged_kfold_test_covers_all_data() -> None:
    """Тестовые индексы покрывают весь датасет ровно один раз."""
    n = 100
    X, y, t1 = _make_dataset(n=n)
    cv = PurgedKFold(n_splits=5)

    all_test = np.concatenate([test for _, test in cv.split(X, y, groups=t1)])
    assert np.array_equal(np.sort(all_test), np.arange(n))


# ---------------------------------------------------------------------------
# PurgedKFold: no leakage
# ---------------------------------------------------------------------------


def test_purged_kfold_no_leakage() -> None:
    """
    После purge ни один тренировочный образец не имеет t1 >= test_start.
    (т.е. label-span не перекрывает тестовую выборку)
    """
    X, y, t1 = _make_dataset(n=200)
    cv = PurgedKFold(n_splits=5, embargo_pct=0.0)

    for train_idx, test_idx in cv.split(X, y, groups=t1):
        if len(train_idx) == 0 or len(test_idx) == 0:
            continue

        test_start_ts = X.index[test_idx[0]]
        test_end_ts = X.index[test_idx[-1]]

        # Тренировочные образцы ДО тестовой выборки не должны иметь t1 >= test_start
        before_test = train_idx[train_idx < test_idx[0]]
        for j in before_test:
            t1_j = t1.iloc[j]
            assert t1_j < test_start_ts, (
                f"Утечка: train[{j}].t1={t1_j} >= test_start={test_start_ts}"
            )


def test_purged_kfold_embargo() -> None:
    """
    После embargo n_embargo образцов сразу после теста отсутствуют в train.
    """
    n = 100
    embargo_pct = 0.05  # 5% = 5 образцов при n=100
    X, y, t1 = _make_dataset(n=n)
    cv = PurgedKFold(n_splits=5, embargo_pct=embargo_pct)

    n_embargo = int(np.ceil(embargo_pct * n))  # = 5

    for train_idx, test_idx in cv.split(X, y, groups=t1):
        test_end = test_idx[-1]
        embargo_zone = np.arange(test_end + 1, min(test_end + 1 + n_embargo, n))

        # Зона embargo не должна содержаться в тренировочной выборке
        overlap = np.intersect1d(train_idx, embargo_zone)
        assert len(overlap) == 0, (
            f"Embargo zone {embargo_zone} найдена в train: {overlap}"
        )


# ---------------------------------------------------------------------------
# PurgedKFold: sklearn совместимость
# ---------------------------------------------------------------------------


def test_purged_kfold_sklearn_compat() -> None:
    """
    cross_val_score с PurgedKFold завершается без ошибок и возвращает n_splits оценок.
    """
    X, y, t1 = _make_dataset(n=200)
    cv = PurgedKFold(n_splits=5)
    model = DummyClassifier(strategy="most_frequent")

    scores = cross_val_score(model, X, y, cv=cv, groups=t1, scoring="accuracy")

    assert len(scores) == 5
    assert np.all(np.isfinite(scores))


def test_purged_kfold_train_test_disjoint() -> None:
    """Train и test индексы не пересекаются ни в одном сплите."""
    X, y, t1 = _make_dataset(n=100)
    cv = PurgedKFold(n_splits=5)

    for train_idx, test_idx in cv.split(X, y, groups=t1):
        overlap = np.intersect1d(train_idx, test_idx)
        assert len(overlap) == 0, f"Train и test пересекаются: {overlap}"


def test_purged_kfold_no_t1_acts_as_kfold() -> None:
    """
    Без t1 (groups=None) PurgedKFold действует как обычный KFold по времени
    (нет purge, только embargo).
    """
    X, y, _ = _make_dataset(n=100)
    cv = PurgedKFold(n_splits=5, embargo_pct=0.0)

    splits = list(cv.split(X, y, groups=None))
    assert len(splits) == 5
    # Все тестовые наборы не перекрываются
    all_test = np.concatenate([test for _, test in splits])
    assert len(all_test) == len(np.unique(all_test))


def test_purged_kfold_invalid_n_splits() -> None:
    """n_splits < 2 вызывает ValueError при создании."""
    with pytest.raises(ValueError, match="n_splits"):
        PurgedKFold(n_splits=1)


def test_purged_kfold_invalid_embargo() -> None:
    """embargo_pct >= 0.5 вызывает ValueError при создании."""
    with pytest.raises(ValueError, match="embargo_pct"):
        PurgedKFold(embargo_pct=0.5)


# ---------------------------------------------------------------------------
# CPCV: базовые свойства
# ---------------------------------------------------------------------------


def test_cpcv_paths_count() -> None:
    """Число путей = C(n_groups, n_test_groups)."""
    from math import comb

    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
    X, y, t1 = _make_dataset(n=120)

    splits = list(cv.split(X, y, groups=t1))
    expected = comb(6, 2)  # = 15
    assert len(splits) == expected
    assert cv.get_n_splits() == expected


def test_cpcv_max_paths_limit() -> None:
    """
    C(n_groups, n_test_groups) > max_paths вызывает ValueError при split().
    """
    # C(10, 3) = 120 > max_paths=50
    cv = CombinatorialPurgedCV(n_groups=10, n_test_groups=3, max_paths=50)
    X, y, t1 = _make_dataset(n=200)

    with pytest.raises(ValueError, match="max_paths"):
        list(cv.split(X, y, groups=t1))


def test_cpcv_no_overlap() -> None:
    """Тренировочные и тестовые индексы не пересекаются ни в одном пути."""
    X, y, t1 = _make_dataset(n=120)
    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2, embargo_pct=0.0)

    for train_idx, test_idx in cv.split(X, y, groups=t1):
        overlap = np.intersect1d(train_idx, test_idx)
        assert len(overlap) == 0, f"Пересечение train/test: {overlap}"


def test_cpcv_all_data_covered() -> None:
    """
    Каждый индекс (без учёта embargo) покрыт как тестовый хотя бы в одном пути.

    Это ключевое свойство CPCV: все точки данных в итоге попадают в тест.
    """
    n = 120
    X, y, t1 = _make_dataset(n=n)
    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2, embargo_pct=0.0)

    covered = set()
    for _, test_idx in cv.split(X, y, groups=t1):
        covered.update(test_idx.tolist())

    # Все индексы должны быть покрыты
    assert len(covered) == n, (
        f"Не все индексы покрыты: {n - len(covered)} пропущено"
    )


def test_cpcv_invalid_n_test_groups() -> None:
    """n_test_groups >= n_groups вызывает ValueError при создании."""
    with pytest.raises(ValueError, match="n_test_groups"):
        CombinatorialPurgedCV(n_groups=4, n_test_groups=4)


def test_cpcv_get_path_metrics() -> None:
    """
    get_path_metrics() возвращает DataFrame с score для каждого пути.
    """
    from math import comb

    X, y, t1 = _make_dataset(n=120)
    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
    model = DummyClassifier(strategy="most_frequent")

    metrics_df = cv.get_path_metrics(model, X, y, scoring="accuracy", groups=t1)

    expected_paths = comb(6, 2)  # 15
    assert len(metrics_df) == expected_paths
    assert "score" in metrics_df.columns
    assert "path_id" in metrics_df.columns
    assert "n_train" in metrics_df.columns
    assert "n_test" in metrics_df.columns
    assert metrics_df["score"].notna().all()
    assert (metrics_df["n_train"] > 0).all()
    assert (metrics_df["n_test"] > 0).all()


def test_cpcv_var_sr_from_bootstrap() -> None:
    """
    var_sr из CPCV path metrics — положительное конечное число.
    Демонстрирует интеграцию CPCV → DSR.
    """
    from src.backtest.metrics import deflated_sharpe_ratio

    X, y, t1 = _make_dataset(n=120)
    cv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
    model = DummyClassifier(strategy="most_frequent")

    metrics_df = cv.get_path_metrics(model, X, y, scoring="accuracy", groups=t1)

    var_sr = float(metrics_df["score"].var())
    assert var_sr >= 0.0  # Может быть 0 если все оценки одинаковы (DummyClassifier)

    # Проверяем только если var_sr > 0
    if var_sr > 0:
        dsr, p_value = deflated_sharpe_ratio(
            sr_observed=float(metrics_df["score"].mean()),
            n_trials=len(metrics_df),
            var_sr=var_sr,
            T=X.shape[0],
        )
        assert 0.0 <= dsr <= 1.0
        assert np.isclose(dsr + p_value, 1.0, atol=1e-9)
