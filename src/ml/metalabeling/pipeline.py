"""
MetaLabeler: pipeline для фильтрации торговых сигналов (AFML Ch.10).

Обёртка над sklearn-классификатором с:
  - Feature selection (MDI/MDA/SFI из Блока E)
  - Опциональной калибровкой вероятностей (CalibratedClassifierCV)
  - Поддержкой uniqueness sample weights (из Блока C)
  - Сохранением/загрузкой артефактов через joblib с привязкой к RunContext

Artifact storage: локальные файлы в {data_dir}/artifacts/{run_id}/.
S3 — за рамками этой фазы.

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
    Metalabeling pipeline — обучает вторичный классификатор для фильтрации сигналов.

    Принимает матрицу признаков X и метки y (из triple_barrier_labels),
    опционально отбирает признаки, обучает base_model.

    Совместим с MetaScorer Protocol (predict_proba).

    Args:
        base_model:       sklearn-совместимый классификатор.
                          По умолчанию RandomForestClassifier(n_estimators=100).
        calibrate:        Если True, оборачивает base_model в CalibratedClassifierCV.
        feature_selector: Callable[[X, y], list[str]] — функция отбора признаков.
                          Например: ``lambda X, y: select_features(X, y, method="mda")``.
                          Если None, используются все признаки.

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
        Обучает MetaLabeler на данных X, y.

        Порядок шагов:
          1. feature_selector(X, y) → отбор признаков (если задан).
          2. Построение модели (с CalibratedClassifierCV если calibrate=True).
          3. fit(X_selected, y, sample_weight).

        Args:
            X:             Матрица признаков.
            y:             Целевые метки.
            sample_weight: Опциональные веса образцов (из get_uniqueness_weights).

        Returns:
            self (для цепочки вызовов).
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
        Предсказывает вероятности классов.

        Args:
            X: Матрица признаков (должна содержать те же колонки, что при обучении).

        Returns:
            np.ndarray формы (n_samples, n_classes).

        Raises:
            RuntimeError: если модель не обучена (fit не вызван).
        """
        if self._fitted_model is None:
            raise RuntimeError("MetaLabeler не обучен. Вызовите fit() сначала.")
        if self._selected_features is not None:
            X_pred = X[self._selected_features]
        else:
            X_pred = X
        return np.asarray(self._fitted_model.predict_proba(X_pred))

    def save(self, path: Path, run_context: RunContext) -> None:
        """
        Сохраняет обученную модель как joblib-артефакт.

        Создаёт родительские директории при необходимости.

        Args:
            path:        Путь к файлу артефакта.
            run_context: RunContext для привязки артефакта к run_id.

        Raises:
            RuntimeError: если модель не обучена (fit не вызван).
        """
        if self._fitted_model is None:
            raise RuntimeError("MetaLabeler не обучен. Вызовите fit() сначала.")
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
        Загружает обученный MetaLabeler из joblib-артефакта.

        Args:
            path: Путь к файлу артефакта.

        Returns:
            MetaLabeler с восстановленной моделью и run_context.
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
        """RunContext артефакта (None если модель не сохранена)."""
        return self._run_context

    @property
    def selected_features(self) -> list[str] | None:
        """Список признаков, выбранных при обучении (None если fit не вызван)."""
        return self._selected_features

    @property
    def n_features_in(self) -> int | None:
        """Число признаков, использованных при обучении."""
        if self._selected_features is None:
            return None
        return len(self._selected_features)
