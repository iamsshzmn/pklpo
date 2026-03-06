# Indicator Groups

**Расчёт индикаторов по группам**

## Обзор

Indicator Groups содержит реализации расчёта технических индикаторов, организованные по категориям. Каждый модуль рассчитывает группу связанных индикаторов с backend chain `TA-Lib -> pandas_ta -> Python fallback`.

## Структура

```
indicator_groups/
├── __init__.py       # Экспорты всех calc_*_indicators
├── candles.py        # Свечные паттерны
├── data_cleaner.py   # Очистка данных
├── ma.py             # Скользящие средние
├── oscillators.py    # Осцилляторы
├── overlap.py        # Базовые расчёты
├── performance.py    # Показатели эффективности
├── squeeze.py        # TTM Squeeze
├── statistics.py     # Статистика
├── trend.py          # Трендовые индикаторы
├── volatility.py     # Волатильность
├── volume.py         # Объёмные индикаторы
└── README.md
```

## API

Каждый модуль экспортирует функцию:

```python
def calc_{group}_indicators(df: pd.DataFrame, available: set) -> dict[str, pd.Series]
```

**Параметры:**
- `df` - DataFrame с OHLCV данными
- `available` - множество индикаторов для расчёта

**Возвращает:**
- Словарь `{indicator_name: pd.Series}`

## Порядок расчёта

Группы рассчитываются в определённом порядке для соблюдения зависимостей:

| # | Группа | Lookback | Зависит от | Примеры |
|---|--------|----------|------------|---------|
| 1 | **overlap** | 1 | — | hlc3, hl2, ohlc4, wcp |
| 2 | **ma** | 200 | overlap | ema_8/21/50/200, sma_20/50/200 |
| 3 | **oscillators** | 100 | close, ma | rsi_14, macd, stoch_k, cci |
| 4 | **volatility** | 100 | OHLC, ma | atr_14, bb_upper/lower, kc |
| 5 | **volume** | 50 | volume, close | obv, vwap, cmf, mfi |
| 6 | **trend** | 100 | OHLC, ATR | adx_14, supertrend, psar |
| 7 | **candles** | 10 | OHLC | ha_open/close, cdl_doji |
| 8 | **squeeze** | 20 | BB, KC | ttm_squeeze_on, ttm_squeeze_value |
| 9 | **statistics** | 100 | price data | zscore, skew, kurtosis |
| 10 | **performance** | 50 | close | returns, sharpe, max_drawdown |

## Использование

### Через Core API (рекомендуется)

```python
from src.features.core import compute_features

df_result = compute_features(
    df_ohlcv,
    specs=['ema_21', 'rsi_14', 'atr_14', 'obv']
)
```

### Прямой вызов групп (advanced)

```python
from src.features.indicator_groups import (
    calc_ma_indicators,
    calc_oscillator_indicators,
    calc_volatility_indicators
)

# Скользящие средние
ma_result = calc_ma_indicators(df, {'ema_21', 'sma_50'})

# Осцилляторы
osc_result = calc_oscillator_indicators(df, {'rsi_14', 'macd'})

# Волатильность
vol_result = calc_volatility_indicators(df, {'atr_14', 'bb_upper'})
```

## Группы

### 1. Overlap (`overlap.py`)

Базовые ценовые расчёты:
- `hlc3` = (high + low + close) / 3
- `hl2` = (high + low) / 2
- `ohlc4` = (open + high + low + close) / 4
- `wcp` = (high + low + 2*close) / 4

### 2. Moving Averages (`ma.py`)

- **EMA Ribbon**: ema_8, ema_13, ema_21, ema_34, ema_55, ema_89, ema_144, ema_233
- **EMA**: ema_12, ema_26, ema_50, ema_200
- **SMA**: sma_20, sma_34, sma_50, sma_200
- **Другие**: hma_20, wma_20, tema_20, dema_20, kama_20

### 3. Oscillators (`oscillators.py`)

- **RSI**: rsi_14
- **MACD**: macd, macd_signal, macd_histogram
- **Stochastic**: stoch_k, stoch_d, stochrsi_k, stochrsi_d
- **Другие**: cci_20, willr, mfi, mom_10, roc_10

### 4. Volatility (`volatility.py`)

- **ATR**: atr_14, natr_14
- **Bollinger**: bb_upper, bb_middle, bb_lower, bb_width, bb_percent
- **Keltner**: kc_upper, kc_middle, kc_lower
- **Donchian**: dc_upper, dc_middle, dc_lower

### 5. Volume (`volume.py`)

- `obv` - On Balance Volume
- `vwap` - Volume Weighted Average Price
- `cmf` - Chaikin Money Flow
- `mfi` - Money Flow Index
- `ad` - Accumulation/Distribution
- `volume_sma20` - Volume SMA

### 6. Trend (`trend.py`)

- **ADX**: adx_14, adx_pos_di, adx_neg_di
- **Supertrend**: supertrend, supertrend_direction
- **PSAR**: psar, psar_direction
- **Aroon**: aroon_up, aroon_down, aroon_osc
- **Ichimoku**: ichimoku_tenkan, ichimoku_kijun, senkou_a/b, chikou

### 7. Candles (`candles.py`)

- **Heikin-Ashi**: ha_open, ha_high, ha_low, ha_close
- **Patterns**: cdl_doji, cdl_inside

### 8. Squeeze (`squeeze.py`)

- `ttm_squeeze_on` - Squeeze активен
- `ttm_squeeze_value` - Значение momentum
- `ttm_squeeze_hist` - Гистограмма

### 9. Statistics (`statistics.py`)

- `zscore_20` - Z-score
- `skew_20` - Асимметрия
- `kurtosis_20` - Эксцесс
- `median_20` - Медиана
- `stdev_20` - Стандартное отклонение

### 10. Performance (`performance.py`)

- `log_return` - Логарифмическая доходность
- `percent_return` - Процентная доходность
- `sharpe_20` - Коэффициент Шарпа
- `max_drawdown_20` - Максимальная просадка

## Error Handling

Все модули используют паттерн "graceful degradation":

```python
def _put_or_nan(name: str, series):
    """Добавить серию или NaN при ошибке"""
    if series is None or (hasattr(series, 'isna') and series.isna().all()):
        result[name] = pd.Series(np.nan, index=df.index)
    else:
        result[name] = series
```

## Тестирование

```bash
pytest tests/features/tests/test_core.py -v
pytest tests/features/tests/test_comprehensive.py -v
```
