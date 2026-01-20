# Name Mapping Module

Модуль `name_mapping.py` предоставляет надежное сопоставление между именами индикаторов pandas_ta и стандартизированными именами фичей, с проверкой возможностей и обработкой ошибок.

## Основные функции

### `normalize_indicator_name(raw_name: str) -> str`
Нормализует сырые имена индикаторов pandas_ta в стандартизированные имена фичей.

**Примеры:**
```python
normalize_indicator_name("EMA_14")      # -> "ema_14"
normalize_indicator_name("MACD_12_26_9") # -> "macd"
normalize_indicator_name("BBANDS_20_2.0_U") # -> "bb_upper"
normalize_indicator_name("STOCHK_14_3_3")   # -> "stoch_k"
```

### `check_indicator_capability(indicator_name: str) -> bool`
Проверяет доступность индикатора pandas_ta.

**Пример:**
```python
check_indicator_capability("ema")  # -> True
check_indicator_capability("nonexistent")  # -> False
```

### `safe_indicator_call(indicator_name: str, *args, **kwargs) -> Optional[pd.Series]`
Безопасно вызывает индикатор pandas_ta с проверкой возможностей.

**Пример:**
```python
data = pd.Series([1, 2, 3, 4, 5])
result = safe_indicator_call("ema", data, length=3)
# Возвращает Series с результатами или None/NaN series если индикатор недоступен
```

### `get_available_indicators() -> Set[str]`
Получает множество доступных индикаторов pandas_ta.

### `validate_versions() -> bool`
Проверяет соответствие версий pandas_ta и pandas ожидаемым.

## Поддерживаемые индикаторы

### Moving Averages
- EMA, SMA, WMA, HMA, DEMA, TEMA, TRIMA, KAMA, MAMA, VWMA

### Trend Indicators  
- ADX, DMP, DMN, AROON, AROONOSC, CCI, DMI, DX, PSAR, TRIX, UO, WILLR

### Oscillators
- RSI, STOCH, STOCHF, STOCHRSI, CMO, ROC, MOM, PPO, SLOPE, STDDEV

### MACD Family
- MACD, MACDS, MACDH, MACDEXT, MACDEXT_S, MACDEXT_H

### Volatility
- ATR, NATR, TRANGE, BBANDS, KC, DC, UI, VHF

### Volume
- OBV, AD, ADOSC, CMF, FI, EOM, VWAP, MFI, NVI, PVI, PVO

### Candlestick Patterns
- CDLDOJI, CDLHAMMER, CDLENGULFING, CDLMORNINGSTAR, и многие другие

### Statistics
- CORREL, LINEARREG, STDDEV, VAR, ZSCORE

### Performance
- LOG_RETURN, PERCENT_RETURN, CUMRET

## Версионирование

Модуль закреплен на следующих версиях для стабильности:
- `pandas_ta`: 0.3.14b0
- `pandas`: 2.3.1

## Обработка ошибок

1. **Недоступные индикаторы**: Возвращает NaN series вместо падения
2. **Неверные параметры**: Логирует предупреждение и возвращает NaN series
3. **Неизвестные имена**: Fallback к snake_case конвертации

## Кэширование

Результаты проверки возможностей кэшируются для повышения производительности.

## Тестирование

Модуль покрыт 28 юнит-тестами, включающими:
- Нормализацию имен различных типов индикаторов
- Проверку возможностей
- Безопасные вызовы
- Интеграционные тесты

Запуск тестов:
```bash
python -m pytest src/features/tests/test_name_mapping.py -v
```
