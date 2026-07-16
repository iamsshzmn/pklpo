"""
Тесты для src/ml/metalabeling/pipeline.py и calibration.py.

Все тесты работают на синтетических данных без подключения к БД.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.core.run_context import RunContext
from src.ml.feature_selection.reduction import select_features
from src.ml.metalabeling.calibration import CalibratedMetaLabeler
from src.ml.metalabeling.pipeline import MetaLabeler
from src.ml.validation.purged_kfold import PurgedKFold

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_dataset(
    n: int = 200,
    n_features: int = 5,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Синтетический датасет: 2 сигнальных признака + (n_features-2) шумовых.
    y = 1 если (signal_0 + signal_1) > 0.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    signal = rng.standard_normal((n, 2))
    noise = rng.standard_normal((n, max(0, n_features - 2)))
    cols = ["signal_0", "signal_1"] + [
        f"noise_{i}" for i in range(max(0, n_features - 2))
    ]
    X = pd.DataFrame(np.hstack([signal, noise]), index=idx, columns=cols)
    y = pd.Series((signal[:, 0] + signal[:, 1] > 0).astype(int), index=idx)
    return X, y


# ---------------------------------------------------------------------------
# MetaLabeler: базовый
# ---------------------------------------------------------------------------


def test_metalabeler_fit_predict() -> None:
    """Базовый цикл: fit → predict_proba возвращает корректные вероятности."""
    X, y = _make_dataset(n=200, n_features=5)
    labeler = MetaLabeler(calibrate=False)
    labeler.fit(X, y)

    proba = labeler.predict_proba(X)
    assert proba.shape == (len(X), 2)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-9)
    assert np.all(proba >= 0.0)
    assert np.all(proba <= 1.0)


def test_metalabeler_predict_before_fit_raises() -> None:
    """predict_proba без fit вызывает RuntimeError."""
    X, _ = _make_dataset(n=50)
    labeler = MetaLabeler()

    with pytest.raises(RuntimeError, match="fit"):
        labeler.predict_proba(X)


def test_metalabeler_with_sample_weights() -> None:
    """MetaLabeler принимает sample_weight без ошибок."""
    X, y = _make_dataset(n=200, n_features=4)
    weights = np.ones(len(X)) / len(X)

    labeler = MetaLabeler(calibrate=False)
    labeler.fit(X, y, sample_weight=weights)

    proba = labeler.predict_proba(X)
    assert proba.shape == (len(X), 2)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-9)


def test_metalabeler_with_feature_selection() -> None:
    """Feature selector встроен в pipeline и уменьшает число признаков."""
    X, y = _make_dataset(n=200, n_features=8)
    n_select = 3

    def selector(X_: pd.DataFrame, y_: pd.Series) -> list[str]:
        return select_features(X_, y_, method="mutual_info", n_features=n_select)

    model = RandomForestClassifier(n_estimators=20, random_state=0)
    labeler = MetaLabeler(base_model=model, calibrate=False, feature_selector=selector)
    labeler.fit(X, y)

    assert labeler.selected_features is not None
    assert len(labeler.selected_features) == n_select
    assert labeler.n_features_in == n_select

    # predict_proba применяет selector автоматически
    proba = labeler.predict_proba(X)
    assert proba.shape == (len(X), 2)


# ---------------------------------------------------------------------------
# MetaLabeler: save/load
# ---------------------------------------------------------------------------


def test_metalabeler_save_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Сохранённый артефакт загружается и даёт идентичные предсказания."""
    X, y = _make_dataset(n=200, n_features=5)
    ctx = RunContext.create({"test": "metalabeler_save_load"})

    model = RandomForestClassifier(n_estimators=20, random_state=0)
    labeler = MetaLabeler(base_model=model, calibrate=False)
    labeler.fit(X, y)

    artifact_path = tmp_path / "artifacts" / ctx.run_id / "model.joblib"
    labeler.save(artifact_path, ctx)

    assert artifact_path.exists()

    loaded = MetaLabeler.load(artifact_path)

    assert loaded.run_context is not None
    assert loaded.run_context.run_id == ctx.run_id
    assert loaded.selected_features == labeler.selected_features

    proba_original = labeler.predict_proba(X)
    proba_loaded = loaded.predict_proba(X)
    np.testing.assert_array_equal(proba_original, proba_loaded)


def test_metalabeler_save_before_fit_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """save() без fit вызывает RuntimeError."""
    ctx = RunContext.create()
    labeler = MetaLabeler()

    with pytest.raises(RuntimeError, match="fit"):
        labeler.save(tmp_path / "model.joblib", ctx)


# ---------------------------------------------------------------------------
# MetaLabeler: PurgedKFold интеграция
# ---------------------------------------------------------------------------


def test_metalabeler_with_purged_kfold() -> None:
    """MetaLabeler корректно обучается и предсказывает на каждом фолде PurgedKFold."""
    X, y = _make_dataset(n=300, n_features=5)
    cv = PurgedKFold(n_splits=3, embargo_pct=0.0)
    model = RandomForestClassifier(n_estimators=20, random_state=0)

    for train_idx, test_idx in cv.split(X, y):
        labeler = MetaLabeler(base_model=model, calibrate=False)
        labeler.fit(X.iloc[train_idx], y.iloc[train_idx])

        proba = labeler.predict_proba(X.iloc[test_idx])

        assert proba.shape == (len(test_idx), 2)
        np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-9)


# ---------------------------------------------------------------------------
# MetaLabeler: MetaScorer protocol
# ---------------------------------------------------------------------------


def test_meta_scorer_protocol() -> None:
    """MetaLabeler совместим с MetaScorer Protocol (predict_proba interface)."""
    X, y = _make_dataset(n=100, n_features=4)
    labeler = MetaLabeler(calibrate=False)
    labeler.fit(X, y)

    # MetaScorer требует predict_proba(X: pd.DataFrame) -> np.ndarray
    assert hasattr(labeler, "predict_proba")
    proba = labeler.predict_proba(X)
    assert isinstance(proba, np.ndarray)
    assert proba.ndim == 2
    assert proba.shape[0] == len(X)


# ---------------------------------------------------------------------------
# CalibratedMetaLabeler
# ---------------------------------------------------------------------------


def test_metalabeler_calibration() -> None:
    """
    CalibratedMetaLabeler возвращает корректные вероятности и разумный Brier score.
    """
    X, y = _make_dataset(n=300, n_features=5)
    model = RandomForestClassifier(n_estimators=30, random_state=42)
    labeler = CalibratedMetaLabeler(
        base_model=model, calibration_method="sigmoid", cv=3
    )

    n_train = 200
    labeler.fit(X.iloc[:n_train], y.iloc[:n_train])

    proba = labeler.predict_proba(X.iloc[n_train:])
    assert proba.shape == (100, 2)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0, atol=1e-9)

    # Brier score < 0.5 (лучше случайного при p=0.5 → Brier=0.25)
    brier = labeler.calibration_score(X.iloc[n_train:], y.iloc[n_train:])
    assert 0.0 <= brier <= 0.5, f"Brier score {brier:.4f} слишком высокий"


def test_calibrated_metalabeler_invalid_method() -> None:
    """Неизвестный метод калибровки вызывает ValueError."""
    with pytest.raises(ValueError, match="sigmoid"):
        CalibratedMetaLabeler(calibration_method="unknown")


def test_calibrated_metalabeler_invalid_cv() -> None:
    """cv < 2 вызывает ValueError."""
    with pytest.raises(ValueError, match="cv"):
        CalibratedMetaLabeler(cv=1)


def test_calibrated_metalabeler_reliability_curve() -> None:
    """reliability_curve возвращает массивы в диапазоне [0, 1]."""
    X, y = _make_dataset(n=300, n_features=5)
    model = RandomForestClassifier(n_estimators=20, random_state=0)
    labeler = CalibratedMetaLabeler(base_model=model, cv=3)
    labeler.fit(X.iloc[:200], y.iloc[:200])

    frac_pos, mean_pred = labeler.reliability_curve(
        X.iloc[200:], y.iloc[200:], n_bins=5
    )

    assert len(frac_pos) == len(mean_pred)
    assert np.all(frac_pos >= 0.0) and np.all(frac_pos <= 1.0)
    assert np.all(mean_pred >= 0.0) and np.all(mean_pred <= 1.0)
