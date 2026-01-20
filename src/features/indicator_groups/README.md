# Indicator Groups

This directory contains grouped technical indicators organized by category. Each module provides a function to calculate a specific group of related indicators using the pandas_ta library and custom logic where needed.

## Overview

The indicator groups are designed to:
- Organize indicators by functional category (trend, oscillators, volume, etc.)
- Provide consistent calculation interfaces
- Handle error cases gracefully with NaN fallbacks
- Support conditional calculation based on available indicator requirements

## Module Structure

Each module follows a consistent pattern:
- Main function: `calc_{group}_indicators(df: pd.DataFrame, available: set) -> dict`
- Input: DataFrame with OHLCV data and set of required indicators
- Output: Dictionary with calculated indicator values

## 📊 Calculation Order & Dependencies

The groups are calculated in a specific order to respect dependencies:

| Order | Group | Dependencies | Max Lookback | Example Indicators |
|-------|-------|--------------|--------------|-------------------|
| 1 | **overlap** | OHLC | 1 | hlc3, hl2, ohlc4, wcp |
| 2 | **ma** | OHLC | 200 | ema_8, ema_21, sma_20, sma_200 |
| 3 | **oscillators** | close, MA | 100 | rsi_14, macd, stoch_k, cci_14 |
| 4 | **volatility** | OHLC, MA | 100 | atr_14, bb_upper, bb_lower, kc |
| 5 | **volume** | volume, close | 50 | obv, cmf, vwap, mfi |
| 6 | **trend** | OHLC, ATR | 100 | adx_14, aroon, supertrend, psar |
| 7 | **candles** | OHLC | 10 | ha_open, ha_close, cdl_doji |
| 8 | **squeeze** | BB, KC | 20 | ttm_squeeze, squeeze_on |
| 9 | **statistics** | price data | 100 | skew, kurtosis, zscore |
| 10 | **performance** | close | 50 | returns, cumulative_returns |

### 🔗 Dependency Details

**Overlap** → No dependencies, direct price calculations
```
hlc3 = (high + low + close) / 3
hl2 = (high + low) / 2
```

**MA** → Depends on OHLC
```
ema_21 = EMA(close, 21)
sma_200 = SMA(close, 200)
```

**Oscillators** → Depends on close, sometimes MA
```
rsi_14 = RSI(close, 14)  # needs ~30 bars for warmup
macd = EMA(close, 12) - EMA(close, 26)  # needs 26+ bars
```

**Volatility** → Depends on OHLC, sometimes MA
```
atr_14 = ATR(high, low, close, 14)
bb = SMA(close, 20) ± 2*STD(close, 20)
```

**Volume** → Depends on volume and close
```
obv = cumsum(volume * sign(close_change))
vwap = cumsum(hlc3 * volume) / cumsum(volume)
```

**Trend** → Depends on OHLC, often uses ATR
```
adx_14 = ADX(high, low, close, 14)  # needs ~40 bars
supertrend = uses ATR + close
```

**Candles** → Depends on OHLC
```
ha_close = (O + H + L + C) / 4
cdl_doji = abs(close - open) < threshold
```

**Squeeze** → Depends on Bollinger Bands and Keltner Channels
```
squeeze_on = bb_width < kc_width
```

**Statistics** → Depends on price data
```
rolling_skew = SKEW(returns, 20)
zscore = (close - mean) / std
```

**Performance** → Depends on close
```
returns = close.pct_change()
cumulative_returns = (1 + returns).cumprod() - 1
```

## Available Groups

### 1. Moving Averages (`ma.py`)
**Function:** `calc_ma_indicators()`

Calculates various moving average indicators:
- **EMA indicators**: ema12, ema21, ema26, ema50, ema200
- **EMA Ribbon**: ema_8, ema_13, ema_21, ema_34, ema_55, ema_89, ema_144, ema_233
- **SMA indicators**: sma34, sma50, sma200

### 2. Oscillators (`oscillators.py`)
**Function:** `calc_oscillator_indicators()`

Calculates momentum and oscillator indicators:
- **RSI**: rsi14 (Relative Strength Index)
- **Stochastic**: stoch_k, stoch_d (Stochastic Oscillator)
- **StochRSI**: stochrsi_k, stochrsi_d
- **MACD**: macd, macd_signal, macd_histogram (Moving Average Convergence Divergence)
- **ADX**: adx14, adx_pos_di, adx_neg_di (Average Directional Index)

### 3. Volatility (`volatility.py`)
**Function:** `calc_volatility_indicators()`

Calculates volatility-based indicators:
- **Bollinger Bands**: bb_upper, bb_middle, bb_lower
- **Keltner Channels**: kc_upper, kc_middle, kc_lower
- **ATR**: atr14 (Average True Range)

### 4. Volume (`volume.py`)
**Function:** `calc_volume_indicators()`

Calculates volume-based indicators:
- **OBV**: obv (On-Balance Volume)
- **CMF**: cmf (Chaikin Money Flow)
- **VWAP**: vwap (Volume Weighted Average Price)
- **Volume Profile**: vp_value_area_high, vp_value_area_low, vp_point_of_control
- **Volume SMA**: volume_sma20

### 5. Trend (`trend.py`)
**Function:** `calc_trend_indicators()`

Calculates trend-following indicators:
- **Ichimoku**: ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b, ichimoku_chikou
- **ADX**: adx14, adx_pos_di, adx_neg_di
- **Supertrend**: supertrend, supertrend_direction, supertrend_long, supertrend_short
- **PSAR**: psar, psar_direction, psar_long, psar_short
- **Aroon**: aroon_up, aroon_down, aroon_osc

### 6. Squeeze (`squeeze.py`)
**Function:** `calc_squeeze_indicators()`

Calculates TTM Squeeze indicators:
- **TTM Squeeze**: ttm_squeeze_on, ttm_squeeze_value, ttm_squeeze_hist

### 7. Candles (`candles.py`)
**Function:** `calc_candles_indicators()`

Calculates candle-derived series and simple patterns:
- **Heikin-Ashi**: ha_open, ha_high, ha_low, ha_close
- **Patterns**: cdl_doji (0/1), cdl_inside (0/1)

## Usage Example

### New API (recommended)
```python
from src.features.core import compute_features

# Calculate indicators through unified API
features = compute_features(
    df,
    specs=['ema_21', 'sma_50', 'rsi_14', 'macd', 'bb_upper', 'bb_lower']
)
```

### Direct group usage (advanced)
```python
from src.features.indicator_groups import (
    calc_ma_indicators,
    calc_oscillator_indicators,
    calc_volatility_indicators
)

# Calculate moving averages
ma_indicators = calc_ma_indicators(df, {'ema_21', 'sma_50'})

# Calculate oscillators
oscillator_indicators = calc_oscillator_indicators(df, {'rsi_14', 'macd'})

# Calculate volatility indicators
volatility_indicators = calc_volatility_indicators(df, {'bb_upper', 'bb_lower'})
```

## Error Handling

All modules include robust error handling:
- Returns NaN-filled Series when calculations fail
- Logs warnings for debugging
- Gracefully handles missing data or calculation errors
- Maintains DataFrame index consistency

## Dependencies

- `pandas`: Data manipulation
- `pandas_ta`: Technical analysis library
- `numpy`: Numerical operations
- `logging`: Error logging (where applicable)

## Integration

These indicator groups are used by:
- **Core API**: `src.features.core.compute_features()`
- **Domain Layer**: `src.features.domain.calculator`
- **Application Layer**: `src.features.application.batch_processor`
- Signal calculation engine
- Backtesting framework
- Real-time analysis systems
- Combination analysis tools

## Adding New Indicators

To add new indicators to an existing group:

1. **Add specification** in `src/features/specs.py`
2. **Add to registry** in appropriate `src/features/registry/*.py`
3. **Implement calculation** in the appropriate `indicator_groups/*.py` module
4. **Include proper error handling** and NaN fallbacks
5. **Update documentation** and function docstrings
6. **Test with various market conditions**

### Example:
```python
# 1. Add to specs.py
FeatureSpec(
    name="new_indicator",
    type="oscillator",
    parameters={"period": 14},
    requires=["close"],
    description="New oscillator indicator"
)

# 2. Add to registry/oscillators.py
OSC_INDICATORS.append("new_indicator")
OSC_CONFIG["new_indicator"] = {
    "period": 14,
    "description": "New oscillator indicator",
    "requires": ["close"]
}

# 3. Implement in indicator_groups/oscillators.py
def calc_oscillator_indicators(df: pd.DataFrame, available: set) -> dict:
    # ... existing code ...
    if "new_indicator" in available:
        _put_or_nan("new_indicator", ta.new_indicator(df["close"], length=14))
```

## Notes

- All indicators use standard pandas_ta parameters
- Calculations are optimized for performance
- Results maintain time series alignment with input data
- NaN values are used consistently for missing/invalid data
