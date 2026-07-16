"""
Тесты для src/ml/validation/lookahead.py — Look-Ahead Bias Detector.

Маркированы @pytest.mark.lookahead для запуска как отдельный CI gate:
    pytest -m lookahead

Все тесты работают на синтетических данных без подключения к БД.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.ml.validation.lookahead import LookaheadResult, check_lookahead

# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Синтетический OHLCV DataFrame с DatetimeIndex UTC."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(0, 0.1, n))
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    volume = rng.uniform(1000, 5000, n)
    return pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


# ---------------------------------------------------------------------------
# Чистый pipeline (без look-ahead)
# ---------------------------------------------------------------------------


@pytest.mark.lookahead
def test_lookahead_clean_pipeline() -> None:
    """
    Корректный pipeline (SMA) проходит look-ahead тест.

    SMA использует только прошлые данные: result_A и result_B должны совпасть
    на общих временных метках.
    """
    df = _make_ohlcv(n=300)

    def clean_pipeline(df_: pd.DataFrame) -> pd.Series:
        return df_["close"].rolling(20).mean()

    result = check_lookahead(clean_pipeline, df, n_trim=50)

    assert isinstance(result, LookaheadResult)
    assert result.passed, f"Чистый pipeline не прошёл: {result}"
    assert result.max_diff == 0.0
    assert result.n_compared > 0


@pytest.mark.lookahead
def test_lookahead_clean_pipeline_ema() -> None:
    """EMA (экспоненциальная скользящая средняя) — без look-ahead."""
    df = _make_ohlcv(n=300)

    def ema_pipeline(df_: pd.DataFrame) -> pd.Series:
        return df_["close"].ewm(span=20).mean()

    result = check_lookahead(ema_pipeline, df, n_trim=50)
    assert result.passed, f"EMA pipeline не прошёл: {result}"


# ---------------------------------------------------------------------------
# Leaky pipeline (с look-ahead)
# ---------------------------------------------------------------------------


@pytest.mark.lookahead
def test_lookahead_leaky_pipeline() -> None:
    """
    Pipeline с утечкой данных из будущего не проходит тест.

    Используем shift(-1): значение текущей метки = следующий close.
    Это классический look-ahead bias.
    """
    df = _make_ohlcv(n=300)

    def leaky_pipeline(df_: pd.DataFrame) -> pd.Series:
        # Смотрит на следующий close (будущее!)
        return df_["close"].shift(-1)

    result = check_lookahead(leaky_pipeline, df, n_trim=50)

    assert not result.passed, "Leaky pipeline ошибочно прошёл тест!"
    assert result.max_diff > 0.0


@pytest.mark.lookahead
def test_lookahead_leaky_future_max() -> None:
    """Rolling max по будущим данным — грубая look-ahead утечка."""
    df = _make_ohlcv(n=300)

    def leaky_future_max(df_: pd.DataFrame) -> pd.Series:
        # max следующих N баров — явная утечка
        return df_["close"].rolling(10, min_periods=1).max().shift(-5)

    result = check_lookahead(leaky_future_max, df, n_trim=50)
    assert not result.passed, "Future max pipeline ошибочно прошёл тест!"


# ---------------------------------------------------------------------------
# Dollar bars (сравнение по общим timestamps)
# ---------------------------------------------------------------------------


@pytest.mark.lookahead
def test_lookahead_with_dollar_bars() -> None:
    """
    Dollar bars pipeline — сравнивается только по общим timestamps.

    Dollar bars при усечении дают другие границы ближе к концу,
    но ранние бары должны совпадать.
    """
    from src.core.bars import BarsConfig, build_dollar_bars

    df = _make_ohlcv(n=1000)
    config = BarsConfig(dollar_value=50_000.0, volume_unit="base")

    def dollar_bar_close(df_: pd.DataFrame) -> pd.Series:
        bars = build_dollar_bars(df_, config)
        return bars["close"]

    # При достаточном n_trim ранние бары должны совпасть
    result = check_lookahead(dollar_bar_close, df, n_trim=200)

    # Dollar bars не должны иметь look-ahead: ранние бары стабильны
    assert result.passed, f"Dollar bars pipeline не прошёл look-ahead тест: {result}"


# ---------------------------------------------------------------------------
# Triple-Barrier Labels
# ---------------------------------------------------------------------------


@pytest.mark.lookahead
def test_lookahead_with_triple_barrier() -> None:
    """
    Triple-barrier labeling — метки в «безопасной» зоне не меняются.

    Бары в начале датасета, где горизонт max_h полностью укладывается
    в usечённый датасет, должны давать идентичные метки.
    """
    from src.ml.labeling.triple_barrier import triple_barrier_labels
    from src.ml.models import BarrierConfig

    df = _make_ohlcv(n=500)
    config = BarrierConfig(profit_take=0.02, stop_loss=0.01, max_horizon=20)

    def tb_pipeline(df_: pd.DataFrame) -> pd.Series:
        labels_df = triple_barrier_labels(df_, config)
        return labels_df["label"].astype(float)

    # Усекаем больше max_horizon, чтобы "безопасная" зона гарантированно совпала
    result = check_lookahead(tb_pipeline, df, n_trim=50)
    assert result.passed, f"Triple-barrier labels имеют look-ahead bias: {result}"


# ---------------------------------------------------------------------------
# Stochastic model с фиксированным random_state
# ---------------------------------------------------------------------------


@pytest.mark.lookahead
def test_lookahead_stochastic_model() -> None:
    """
    RF с фиксированным random_state: предсказания детерминированы
    при одинаковых обучающих данных → look-ahead тест проходит.
    """
    df = _make_ohlcv(n=400)

    def rf_pipeline(df_: pd.DataFrame) -> pd.Series:
        n = len(df_)
        # Признаки: returns + rolling std
        returns = df_["close"].pct_change().fillna(0.0)
        vol = returns.rolling(10).std().fillna(0.0)
        X = pd.DataFrame({"ret": returns, "vol": vol})
        y = (returns.shift(-1).fillna(0.0) > 0).astype(int)

        # Обучаем на первых 70%
        split = int(n * 0.7)
        model = RandomForestClassifier(n_estimators=10, random_state=0)
        model.fit(X.iloc[:split], y.iloc[:split])

        # Предсказываем на всех
        proba = model.predict_proba(X)[:, 1]
        return pd.Series(proba, index=df_.index)

    # При одинаковых первых 70% train split, предсказания должны совпасть
    # Trim=50 гарантирует одинаковый train split (400*0.7=280, 350*0.7=245 — разные!)
    # Поэтому используем pipeline, который фиксирует split по index
    def rf_fixed_split(df_: pd.DataFrame) -> pd.Series:
        returns = df_["close"].pct_change().fillna(0.0)
        vol = returns.rolling(10).std().fillna(0.0)
        X = pd.DataFrame({"ret": returns, "vol": vol})
        y = (returns.shift(-1).fillna(0.0) > 0).astype(int)

        # Фиксированная точка разбиения по первым 200 барам
        split_ts = df_.index[min(200, len(df_) - 1)]
        X_train = X.loc[X.index < split_ts]
        y_train = y.loc[y.index < split_ts]

        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X_train, y_train)

        proba = model.predict_proba(X)[:, 1]
        return pd.Series(proba, index=df_.index)

    result = check_lookahead(rf_fixed_split, df, n_trim=50, atol=1e-9)
    assert result.passed, f"RF с фиксированным random_state не прошёл: {result}"


# ---------------------------------------------------------------------------
# DataFrame pipeline (несколько признаков)
# ---------------------------------------------------------------------------


@pytest.mark.lookahead
def test_lookahead_dataframe_pipeline() -> None:
    """Pipeline возвращающий DataFrame (несколько признаков) — проходит тест."""
    df = _make_ohlcv(n=300)

    def features_pipeline(df_: pd.DataFrame) -> pd.DataFrame:
        returns = df_["close"].pct_change().fillna(0.0)
        sma = df_["close"].rolling(10).mean()
        vol = returns.rolling(10).std().fillna(0.0)
        return pd.DataFrame(
            {"returns": returns, "sma": sma, "vol": vol},
            index=df_.index,
        )

    result = check_lookahead(features_pipeline, df, n_trim=50)
    assert result.passed, f"DataFrame features pipeline не прошёл: {result}"


# ---------------------------------------------------------------------------
# Граничные условия и ошибки
# ---------------------------------------------------------------------------


def test_lookahead_invalid_n_trim_too_large() -> None:
    """n_trim >= len(df) вызывает ValueError."""
    df = _make_ohlcv(n=100)
    pipeline = lambda df_: df_["close"].rolling(5).mean()  # noqa: E731

    with pytest.raises(ValueError, match="n_trim"):
        check_lookahead(pipeline, df, n_trim=100)


def test_lookahead_invalid_n_trim_zero() -> None:
    """n_trim < 1 вызывает ValueError."""
    df = _make_ohlcv(n=100)
    pipeline = lambda df_: df_["close"].rolling(5).mean()  # noqa: E731

    with pytest.raises(ValueError, match="n_trim"):
        check_lookahead(pipeline, df, n_trim=0)


def test_lookahead_result_str() -> None:
    """LookaheadResult.__str__ содержит статус и max_diff."""
    result = LookaheadResult(passed=True, max_diff=0.0, n_compared=100)
    s = str(result)
    assert "PASSED" in s
    assert "max_diff" in s
