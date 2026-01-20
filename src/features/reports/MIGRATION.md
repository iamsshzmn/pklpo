# Features Module - Руководство по миграции

## 🔄 Миграция с legacy кода

### Старый способ (legacy)

```python
# Старый способ из src/indicators/
from src.indicators import calc_indicators

# Подготовка данных
df = pd.DataFrame({
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})

# Расчёт индикаторов
result = calc_indicators(df, {
    "rsi14": {"period": 14},
    "atr14": {"period": 14},
    "ema12": {"period": 12}
})

print(result)
```

### Новый способ (features v2.0)

```python
# Новый способ из src/features/ с слоистой архитектурой
from src.features.core import compute_features

# Подготовка данных (добавляем временную метку)
df = pd.DataFrame({
    'ts': [1640995200, 1640998800, 1641002400],
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})

# Расчёт индикаторов через новый API
result = compute_features(
    df,
    specs=["rsi_14", "atr_14", "ema_12"],
    volatility_normalize=True
)

print(result)
```

### Legacy API (deprecated)

```python
# DEPRECATED: используйте compute_features() вместо calc_indicators()
from src.features.indicator_utils import calc_indicators

# Подготовка данных
df = pd.DataFrame({
    'ts': [1640995200, 1640998800, 1641002400],
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})

# Расчёт индикаторов (вызовет предупреждение)
result = calc_indicators(df, {"rsi_14", "atr_14", "ema_12"})
print(result)
```

## 📊 Сравнение подходов

| Аспект | Legacy (indicators) | Новый (features v2.0) |
|--------|-------------------|------------------|
| **API** | Словарь с параметрами | Список названий индикаторов |
| **Архитектура** | Монолитная | Слоистая (Domain/Infrastructure/Application) |
| **Валидация** | Минимальная | Полная валидация OHLCV |
| **Look-ahead** | Не проверяется | Property-тесты и валидация |
| **Нормировка** | Нет | Волатильностная нормировка |
| **Тестирование** | Базовое | Полное покрытие + property-тесты |
| **CLI** | Нет | Полнофункциональный CLI |
| **Документация** | Минимальная | Полная документация |
| **Производительность** | Базовая | Оптимизированная |
| **Поддерживаемость** | Сложная | Высокая (слоистая архитектура) |

## 🔧 Пошаговая миграция

### Шаг 1: Подготовка данных

**Было:**
```python
df = pd.DataFrame({
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})
```

**Стало:**
```python
import pandas as pd
from datetime import datetime

# Добавляем временную метку
df = pd.DataFrame({
    'ts': [int(datetime(2023, 1, 1, i).timestamp()) for i in range(3)],
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})
```

### Шаг 2: Маппинг названий индикаторов

**Было:**
```python
indicators_config = {
    "rsi14": {"period": 14},
    "atr14": {"period": 14},
    "ema12": {"period": 12},
    "macd": {"fast": 12, "slow": 26, "signal": 9}
}
```

**Стало:**
```python
# Новые названия индикаторов
specs = [
    "rsi_14",      # вместо rsi14
    "atr_14",      # вместо atr14
    "ema_12",      # вместо ema12
    "macd"         # вместо macd
]
```

### Шаг 3: Расчёт индикаторов

**Было:**
```python
from src.indicators import calc_indicators

result = calc_indicators(df, indicators_config)
```

**Стало:**
```python
from src.features.core import compute_features

result = compute_features(
    df,
    specs=specs,
    volatility_normalize=True  # опционально
)
```

### Шаг 4: Обработка результатов

**Было:**
```python
# Результат - словарь с pandas Series
rsi_values = result["rsi14"]
atr_values = result["atr14"]
```

**Стало:**
```python
# Результат - pandas DataFrame
rsi_values = result["rsi_14"]
atr_values = result["atr_14"]

# Или по колонкам
feature_columns = ["rsi_14", "atr_14", "ema_12"]
selected_features = result[feature_columns]
```

## 📋 Таблица соответствия названий

| Legacy | Новый | Описание |
|--------|-------|----------|
| `rsi14` | `rsi_14` | Relative Strength Index (14 периодов) |
| `atr14` | `atr_14` | Average True Range (14 периодов) |
| `ema12` | `ema_12` | Exponential Moving Average (12 периодов) |
| `ema26` | `ema_26` | Exponential Moving Average (26 периодов) |
| `ema200` | `ema_200` | Exponential Moving Average (200 периодов) |
| `sma20` | `sma_20` | Simple Moving Average (20 периодов) |
| `macd` | `macd` | MACD Line (12, 26, 9) |
| `macd_signal` | `macd_signal` | MACD Signal Line |
| `macd_histogram` | `macd_histogram` | MACD Histogram |
| `obv` | `obv` | On Balance Volume |
| `vwap` | `vwap` | Volume Weighted Average Price |

## 🔍 Поиск новых названий

```python
from src.features.core import get_available_features
from src.features.domain.indicator_specs import get_features_by_type
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

# Все доступные индикаторы
all_features = get_available_features()
print("Доступные индикаторы:", all_features)

# Поиск по типу
trend_features = get_features_by_type("trend")
oscillator_features = get_features_by_type("oscillator")
volatility_features = get_features_by_type("volatility")
volume_features = get_features_by_type("volume")
ma_features = get_features_by_type("ma")

print("Трендовые индикаторы:", list(trend_features.keys()))
print("Осцилляторы:", list(oscillator_features.keys()))

# Прямой доступ к реестру
print(f"Всего индикаторов в реестре: {len(AVAILABLE_INDICATORS)}")
```

## 🧪 Тестирование миграции

### Сравнение результатов

```python
import pandas as pd
from src.indicators import calc_indicators  # legacy
from src.features.core import compute_features   # новый

# Подготовка данных
df = pd.DataFrame({
    'ts': [1640995200, 1640998800, 1641002400],
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})

# Legacy расчёт
legacy_result = calc_indicators(df, {
    "rsi14": {"period": 14},
    "atr14": {"period": 14}
})

# Новый расчёт
new_result = compute_features(
    df,
    specs=["rsi_14", "atr_14"],
    volatility_normalize=False
)

# Сравнение результатов
print("Legacy RSI:", legacy_result["rsi14"].values)
print("New RSI:", new_result["rsi_14"].values)

# Проверка идентичности (с допуском на численную точность)
import numpy as np
is_identical = np.allclose(
    legacy_result["rsi14"].values,
    new_result["rsi_14"].values,
    rtol=1e-10,
    atol=1e-12
)
print(f"Результаты идентичны: {is_identical}")
```

## 🚨 Потенциальные проблемы

### 1. Отсутствие временной метки

**Проблема:**
```python
# Ошибка: отсутствует колонка 'ts'
df = pd.DataFrame({
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})

result = compute_features(df, specs=["rsi_14"])  # Ошибка валидации
```

**Решение:**
```python
# Добавить временную метку
df['ts'] = range(len(df))  # или реальные временные метки
result = compute_features(df, specs=["rsi_14"])
```

### 2. Неправильные названия индикаторов

**Проблема:**
```python
# Ошибка: неизвестный индикатор
result = compute_features(df, specs=["rsi14"])  # должно быть "rsi_14"
```

**Решение:**
```python
# Использовать правильные названия
result = compute_features(df, specs=["rsi_14"])
```

### 3. Невалидные OHLCV данные

**Проблема:**
```python
# Ошибка: невалидные OHLC отношения
df = pd.DataFrame({
    'ts': [1, 2, 3],
    'open': [100, 101, 102],
    'high': [99, 100, 101],  # high < low
    'low': [102, 103, 104],  # low > high
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})

result = compute_features(df, specs=["rsi_14"])  # Ошибка валидации
```

**Решение:**
```python
# Исправить OHLC отношения
df['high'] = df[['open', 'high', 'close']].max(axis=1)
df['low'] = df[['open', 'low', 'close']].min(axis=1)
result = compute_features(df, specs=["rsi_14"])
```

## 🔧 Автоматическая миграция

### Скрипт для автоматической миграции

```python
import pandas as pd
from src.features.core import compute_features

def migrate_legacy_indicators(df, legacy_config):
    """
    Автоматическая миграция с legacy конфигурации на новый формат.

    Args:
        df: OHLCV DataFrame
        legacy_config: Словарь legacy конфигурации

    Returns:
        DataFrame с рассчитанными индикаторами
    """
    # Маппинг legacy названий на новые
    legacy_to_new = {
        "rsi14": "rsi_14",
        "atr14": "atr_14",
        "ema12": "ema_12",
        "ema26": "ema_26",
        "ema200": "ema_200",
        "sma20": "sma_20",
        "macd": "macd",
        "macd_signal": "macd_signal",
        "macd_histogram": "macd_histogram",
        "obv": "obv",
        "vwap": "vwap"
    }

    # Конвертация названий
    new_specs = []
    for legacy_name in legacy_config.keys():
        if legacy_name in legacy_to_new:
            new_specs.append(legacy_to_new[legacy_name])
        else:
            print(f"Предупреждение: неизвестный индикатор {legacy_name}")

    # Добавление временной метки, если отсутствует
    if 'ts' not in df.columns:
        df = df.copy()
        df['ts'] = range(len(df))

    # Расчёт индикаторов
    result = compute_features(df, specs=new_specs, volatility_normalize=False)

    return result

# Пример использования
legacy_config = {
    "rsi14": {"period": 14},
    "atr14": {"period": 14},
    "ema12": {"period": 12}
}

df = pd.DataFrame({
    'open': [100, 101, 102],
    'high': [102, 103, 104],
    'low': [99, 100, 101],
    'close': [101, 102, 103],
    'volume': [1000, 1100, 1200]
})

# Автоматическая миграция
result = migrate_legacy_indicators(df, legacy_config)
print(result)
```

## ✅ Чек-лист миграции

- [ ] Добавить временную метку в данные
- [ ] Обновить названия индикаторов
- [ ] Проверить валидность OHLCV данных
- [ ] Обновить обработку результатов
- [ ] Протестировать идентичность результатов
- [ ] Обновить документацию
- [ ] Обновить тесты

## 🎯 Преимущества нового подхода

1. **Безопасность**: Полная валидация данных и отсутствие look-ahead bias
2. **Производительность**: Оптимизированные алгоритмы
3. **Тестируемость**: Полное покрытие тестами
4. **Документация**: Подробная документация и примеры
5. **CLI**: Командная строка для быстрого использования
6. **Нормировка**: Встроенная волатильностная нормировка
7. **Расширяемость**: Легкое добавление новых индикаторов

## 📞 Поддержка миграции

При возникновении проблем с миграцией:

1. Проверьте [QUICKSTART.md](QUICKSTART.md) для быстрого старта
2. Изучите [examples.py](examples.py) для примеров использования
3. Запустите тесты для проверки корректности: `pytest src/features/tests/`
4. Используйте CLI для валидации данных: `python -m src.features.cli validate`
5. Обратитесь к команде разработки с описанием проблемы
