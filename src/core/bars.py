"""
Dollar bars and time bars adapter for Quant Stack.

Dollar bars aggregate market microstructure activity by traded value (not time),
producing bars with roughly equal information content per bar.

Reference: Lopez de Prado, "Advances in Financial Machine Learning", Ch. 2

Volume unit handling (OKX SWAP specifics):
  - "contracts": volume in contract units. turnover = volume * contract_val * close
  - "base":      volume in base currency (BTC, ETH, ...). turnover = volume * close
  - "quote":     volume in quote currency (USDT, USD). turnover = volume
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

VolumeUnit = Literal["contracts", "base", "quote"]
BarsSource = Literal["tick", "fallback_minute"]


@dataclass(frozen=True)
class BarsConfig:
    """
    Конфигурация генерации долларовых баров.

    Attributes:
        dollar_value: Целевой оборот (USD) на бар. Бар закрывается при достижении.
        volume_unit: Единица измерения volume в источнике данных.
            - "contracts": контракты (OKX SWAP). Нужен contract_val.
            - "base":      base currency (BTC, ETH, ...).
            - "quote":     quote currency (USDT, USD) — volume уже в USD.
        contract_val: Стоимость одного контракта в base currency.
            Пример OKX BTC-USDT-SWAP: contract_val=0.01 (1 контракт = 0.01 BTC).
            Игнорируется при volume_unit != "contracts".
        min_trades: Минимальное число входных строк для закрытия бара.
            Предотвращает бары из единственной строки при высоком обороте.
        bars_source: Маркировка источника данных ("tick" или "fallback_minute").
    """

    dollar_value: float
    volume_unit: VolumeUnit = "base"
    contract_val: float = 1.0
    min_trades: int = 1
    bars_source: BarsSource = "fallback_minute"

    def __post_init__(self) -> None:
        if self.dollar_value <= 0:
            raise ValueError(
                f"dollar_value должен быть > 0, получен {self.dollar_value}"
            )
        if self.contract_val <= 0:
            raise ValueError(
                f"contract_val должен быть > 0, получен {self.contract_val}"
            )
        if self.min_trades < 1:
            raise ValueError(
                f"min_trades должен быть >= 1, получен {self.min_trades}"
            )
        if self.volume_unit == "contracts" and self.contract_val == 1.0:
            warnings.warn(
                "volume_unit='contracts' с contract_val=1.0 может быть неточным. "
                "Укажите реальный contract_val для инструмента (напр., 0.01 для BTCUSDT SWAP).",
                UserWarning,
                stacklevel=3,
            )


def build_dollar_bars(df: pd.DataFrame, config: BarsConfig) -> pd.DataFrame:
    """
    Генерирует долларовые бары из OHLCV DataFrame.

    Алгоритм: накапливаем оборот построчно; как только суммарный оборот
    достигает config.dollar_value (и прошло >= config.min_trades строк),
    закрываем текущий бар.

    Частичный последний бар (оборот < dollar_value) включается в результат
    с маркировкой — он необходим для look-ahead тестов.

    Args:
        df: DataFrame с колонками open, high, low, close, volume.
            Индекс — DatetimeIndex (UTC) с монотонно возрастающими timestamp.
        config: Конфигурация долларовых баров.

    Returns:
        DataFrame с колонками:
            open, high, low, close, volume, turnover, volume_unit,
            ts_start, duration_s, trades_count, bars_source

        Индекс — DatetimeIndex (ts_end каждого бара, name="timestamp").
        Пустой DataFrame с правильной схемой если df пустой.

    Raises:
        ValueError: Если отсутствуют обязательные колонки или индекс немонотонный.
    """
    _validate_input(df)

    if len(df) == 0:
        return _empty_bars_df()

    turnover = _compute_turnover(
        df["volume"], df["close"], config.volume_unit, config.contract_val
    )

    bars_raw = _aggregate_bars(df, turnover, config)

    if len(bars_raw) == 0:
        return _empty_bars_df()

    bars_raw["volume_unit"] = config.volume_unit
    bars_raw["bars_source"] = config.bars_source

    logger.debug(
        "build_dollar_bars: %d строк -> %d баров (dollar_value=%.0f, unit=%s)",
        len(df),
        len(bars_raw),
        config.dollar_value,
        config.volume_unit,
    )
    return bars_raw


def _compute_turnover(
    volume: pd.Series,
    close: pd.Series,
    volume_unit: VolumeUnit,
    contract_val: float,
) -> pd.Series:
    """
    Вычисляет оборот (USD) для каждой строки.

    Формулы по volume_unit:
    - contracts: turnover = volume * contract_val * close
    - base:      turnover = volume * close
    - quote:     turnover = volume
    """
    if volume_unit == "contracts":
        return volume * contract_val * close
    if volume_unit == "base":
        return volume * close
    # quote
    return volume.copy()


def _aggregate_bars(
    df: pd.DataFrame,
    turnover: pd.Series,
    config: BarsConfig,
) -> pd.DataFrame:
    """
    Итеративная агрегация строк в долларовые бары. O(N).

    Использует явный флаг bar_is_new для корректной инициализации open/high/low
    в первой строке каждого нового бара без предварительной загрузки следующего
    элемента (что нарушает read-once семантику).
    """
    timestamps = df.index
    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    volumes = df["volume"].to_numpy(dtype=float)
    turnovers = turnover.to_numpy(dtype=float)

    n = len(df)
    bars: list[dict[str, object]] = []

    # State
    bar_open: float = 0.0
    bar_high: float = 0.0
    bar_low: float = 0.0
    bar_close: float = 0.0
    bar_volume: float = 0.0
    bar_turnover: float = 0.0
    bar_trades: int = 0
    bar_ts_start = timestamps[0]
    bar_is_new: bool = True

    for i in range(n):
        if bar_is_new:
            # Первая строка нового бара: инициализация open/high/low
            bar_open = opens[i]
            bar_high = highs[i]
            bar_low = lows[i]
            bar_ts_start = timestamps[i]
            bar_is_new = False
        else:
            bar_high = max(bar_high, highs[i])
            bar_low = min(bar_low, lows[i])

        bar_close = closes[i]
        bar_volume += volumes[i]
        bar_turnover += turnovers[i]
        bar_trades += 1

        # Закрытие бара: достигли порога оборота И минимального числа строк
        if bar_turnover >= config.dollar_value and bar_trades >= config.min_trades:
            ts_end = timestamps[i]
            bars.append(
                {
                    "open": bar_open,
                    "high": bar_high,
                    "low": bar_low,
                    "close": bar_close,
                    "volume": bar_volume,
                    "turnover": bar_turnover,
                    "ts_start": bar_ts_start,
                    "ts_end": ts_end,
                    "duration_s": int((ts_end - bar_ts_start).total_seconds()),
                    "trades_count": bar_trades,
                }
            )
            # Сброс для следующего бара
            bar_volume = 0.0
            bar_turnover = 0.0
            bar_trades = 0
            bar_is_new = True

    # Частичный последний бар (не добрал до порога)
    if bar_trades > 0:
        ts_end = timestamps[n - 1]
        bars.append(
            {
                "open": bar_open,
                "high": bar_high,
                "low": bar_low,
                "close": bar_close,
                "volume": bar_volume,
                "turnover": bar_turnover,
                "ts_start": bar_ts_start,
                "ts_end": ts_end,
                "duration_s": int((ts_end - bar_ts_start).total_seconds()),
                "trades_count": bar_trades,
            }
        )
        logger.debug(
            "Частичный последний бар: оборот=%.2f < порог=%.2f, строк=%d",
            bar_turnover,
            config.dollar_value,
            bar_trades,
        )

    if not bars:
        return _empty_bars_df()

    result = pd.DataFrame(bars)
    result.index = pd.DatetimeIndex(result.pop("ts_end"), name="timestamp")
    return result


def _validate_input(df: pd.DataFrame) -> None:
    """Валидирует входной DataFrame перед генерацией баров."""
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Отсутствуют обязательные колонки: {sorted(missing)}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(
            "Индекс DataFrame должен быть DatetimeIndex. "
            f"Получен: {type(df.index).__name__}"
        )

    if len(df) > 1 and not df.index.is_monotonic_increasing:
        raise ValueError(
            "Индекс DataFrame должен быть монотонно возрастающим "
            "(временной ряд без дубликатов)."
        )


def _empty_bars_df() -> pd.DataFrame:
    """Пустой DataFrame с корректной схемой для dollar bars."""
    return pd.DataFrame(
        columns=[
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover",
            "ts_start",
            "duration_s",
            "trades_count",
            "volume_unit",
            "bars_source",
        ],
        index=pd.DatetimeIndex([], name="timestamp"),
    )


def time_bars_passthrough(df: pd.DataFrame) -> pd.DataFrame:
    """
    Адаптер: возвращает тайм-бары с добавлением NULL-колонок quant полей.

    Используется при bars_mode="time" — сохраняет совместимость интерфейса
    с dollar bars pipeline. NULL-значения quant-колонок соответствуют
    семантике расширенной схемы ohlcv_p (bars_mode=time => NULL).

    Args:
        df: Стандартный OHLCV DataFrame.

    Returns:
        DataFrame с оригинальными данными + None-колонки quant полей.
    """
    result = df.copy()
    result["bars_mode"] = "time"
    result["bars_source"] = None
    result["turnover"] = None
    result["volume_unit"] = None
    result["ts_start"] = None
    result["duration_s"] = None
    result["trades_count"] = None
    return result
