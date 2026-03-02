# Utils Layer

**Утилиты и вспомогательные функции**

## Обзор

Utils Layer содержит общие утилиты, используемые во всех слоях модуля: работа с временем, памятью, зависимостями индикаторов.

## Структура

```
utils/
├── __init__.py              # Экспорты
├── dependency_resolver.py   # Резолвер зависимостей индикаторов
├── indicator_utils.py       # Утилиты для работы с индикаторами
├── memlog.py                # Логирование памяти
├── time_utils.py            # Работа с временем и timestamps
├── utils.py                 # Общие утилиты
└── README.md
```

## Компоненты

### `time_utils.py`

Работа с timestamps и временем.

```python
from src.features.utils.time_utils import (
    normalize_timestamp_to_seconds,
    ensure_ts_column,
    parse_timeframe_to_minutes
)

# Нормализация timestamp
ts_sec = normalize_timestamp_to_seconds(1640995200000)  # ms → sec
# 1640995200

# Добавление колонки ts
df = ensure_ts_column(df)  # Создаёт/нормализует колонку ts

# Парсинг таймфрейма
minutes = parse_timeframe_to_minutes("4H")  # 240
```

### `memlog.py`

Мониторинг использования памяти.

```python
from src.features.utils.memlog import (
    log_memory_usage,
    MemoryTracker,
    format_bytes
)

# Логирование текущего использования
log_memory_usage("After calculation")

# Трекер памяти
with MemoryTracker("feature_calculation") as tracker:
    result = compute_features(df)

print(f"Peak memory: {tracker.peak_mb:.1f} MB")
print(f"Delta: {tracker.delta_mb:.1f} MB")
```

### `dependency_resolver.py`

Резолвинг зависимостей между индикаторами.

```python
from src.features.utils.dependency_resolver import (
    resolve_dependencies,
    get_calculation_order
)

# Резолвинг зависимостей
deps = resolve_dependencies(["macd", "supertrend"])
# {"close", "ema_12", "ema_26", "atr_14", ...}

# Порядок расчёта
order = get_calculation_order(["macd", "rsi_14"])
# ["close", "ema_12", "ema_26", "macd", "rsi_14"]
```

### `indicator_utils.py`

Утилиты для работы с индикаторами.

```python
from src.features.utils.indicator_utils import (
    get_indicator_warmup_period,
    is_indicator_available,
    filter_available_indicators
)

# Период прогрева
warmup = get_indicator_warmup_period("sma_200")  # 200

# Проверка доступности
exists = is_indicator_available("rsi_14")  # True

# Фильтрация по доступным
available = filter_available_indicators(["rsi_14", "unknown"])
# ["rsi_14"]
```

### `utils.py`

Общие утилиты.

```python
from src.features.utils.utils import (
    chunk_dataframe,
    safe_divide,
    is_valid_numeric
)

# Разбиение DataFrame на чанки
for chunk in chunk_dataframe(df, chunk_size=50000, overlap=200):
    process(chunk)

# Безопасное деление
result = safe_divide(a, b, default=0.0)  # Без ZeroDivisionError

# Проверка числового значения
is_valid = is_valid_numeric(value)  # Не NaN, не Inf
```

## Тестирование

```bash
pytest src/features/tests/test_time_utils.py -v
pytest src/features/tests/test_utils.py -v
```
