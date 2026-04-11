"""
CalibratedMetaLabeler: MetaLabeler с явными параметрами калибровки.

В отличие от MetaLabeler(calibrate=True), который использует дефолтные
sigmoid/cv=5, CalibratedMetaLabeler даёт прямой доступ к:
  - методу калибровки: "sigmoid" (Platt scaling) или "isotonic" regression
  - числу фолдов CV для калибровки
  - Brier score и reliability curve для оценки надёжности вероятностей

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
    MetaLabeler с явной конфигурацией калибровки вероятностей.

    Расширяет MetaLabeler, добавляя:
      - выбор метода калибровки ("sigmoid" | "isotonic")
      - выбор числа фолдов CV для CalibratedClassifierCV
      - метод ``calibration_score()`` — Brier score для оценки надёжности
      - метод ``reliability_curve()`` — данные для reliability diagram

    Args:
        base_model:          sklearn-совместимый классификатор.
        calibration_method:  Метод калибровки: "sigmoid" или "isotonic".
        cv:                  Число фолдов для CalibratedClassifierCV (>= 2).
        feature_selector:    Callable[[X, y], list[str]] для отбора признаков.

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
                f"calibration_method должен быть 'sigmoid' или 'isotonic', "
                f"получен {calibration_method!r}"
            )
        if cv < 2:
            raise ValueError(f"cv должен быть >= 2, получен {cv}")

        # calibrate=True принудительно — смысл этого класса
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
        Обучает модель с явными параметрами калибровки.

        Переопределяет родительский fit для использования
        calibration_method и cv.

        Args:
            X:             Матрица признаков.
            y:             Целевые метки.
            sample_weight: Опциональные веса образцов.

        Returns:
            self (для цепочки вызовов).
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
        Вычисляет Brier score для оценки надёжности калибровки.

        Brier score = mean((p_i - y_i)^2). Меньше = лучше.
        Случайный классификатор ≈ 0.25 (при 50/50 классах).

        Args:
            X: Матрица признаков (тест).
            y: Истинные метки (тест).

        Returns:
            float в диапазоне [0.0, 1.0]. 0.0 — идеальная калибровка.

        Raises:
            RuntimeError: если модель не обучена.
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
        Возвращает данные для reliability diagram (calibration curve).

        Args:
            X:      Матрица признаков (тест).
            y:      Истинные метки.
            n_bins: Число бинов (влияет на гранулярность кривой).

        Returns:
            Кортеж (fraction_of_positives, mean_predicted_value):
              - fraction_of_positives: истинная доля положительных в каждом бине.
              - mean_predicted_value:  средняя предсказанная вероятность в бине.

        Raises:
            RuntimeError: если модель не обучена.
        """
        proba = self.predict_proba(X)
        frac, pred = calibration_curve(y, proba[:, 1], n_bins=n_bins)
        return np.asarray(frac), np.asarray(pred)
