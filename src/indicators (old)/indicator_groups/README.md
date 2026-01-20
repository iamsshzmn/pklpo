# Indicator Groups

This directory contains grouped technical indicators organized by category. Each module provides a function to calculate a specific group of related indicators using the pandas_ta library.

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
- **MACD**: macd, macd_signal, macd_histogram (Moving Average Convergence Divergence)
- **ADX**: adx14, adx_pos_di, adx_neg_di (Average Directional Index)

### 3. Volatility (`volatility.py`)
**Function:** `calc_volatility_indicators()`

Calculates volatility-based indicators:
- **Bollinger Bands**: bb_upper, bb_middle, bb_lower
- **ATR**: atr14 (Average True Range)

### 4. Volume (`volume.py`)
**Function:** `calc_volume_indicators()`

Calculates volume-based indicators:
- **OBV**: obv (On-Balance Volume)
- **VWAP**: vwap (Volume Weighted Average Price)

### 5. Trend (`trend.py`)
**Function:** `calc_trend_indicators()`

Calculates trend-following indicators:
- **Parabolic SAR**: psar
- **Ichimoku**: ichimoku_a, ichimoku_b, ichimoku_base, ichimoku_span_a, ichimoku_span_b

### 6. Squeeze (`squeeze.py`)
**Function:** `calc_squeeze_indicators()`

Calculates TTM Squeeze indicators:
- **TTM Squeeze**: ttm_squeeze_on, ttm_squeeze_value, ttm_squeeze_hist

## Usage Example

```python
from src.indicators.indicator_groups import (
    calc_ma_indicators,
    calc_oscillator_indicators,
    calc_volatility_indicators
)

# Calculate moving averages
ma_indicators = calc_ma_indicators(df, {'ema21', 'sma50'})

# Calculate oscillators
oscillator_indicators = calc_oscillator_indicators(df, {'rsi14', 'macd'})

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
- Signal calculation engine
- Backtesting framework
- Real-time analysis systems
- Combination analysis tools

## Adding New Indicators

To add new indicators to an existing group:

1. Add the indicator calculation logic to the appropriate module
2. Include proper error handling and NaN fallbacks
3. Update the function's docstring if needed
4. Test with various market conditions

## Notes

- All indicators use standard pandas_ta parameters
- Calculations are optimized for performance
- Results maintain time series alignment with input data
- NaN values are used consistently for missing/invalid data
