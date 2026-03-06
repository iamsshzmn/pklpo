# Observability Layer

**Логирование, метрики и трассировка**

## Обзор

Observability Layer обеспечивает мониторинг, логирование и сбор метрик для модуля features. Основной logging API вынесен в `src.logging`, а пакет `src.features.observability` хранит metrics/error/tracing и compatibility surfaces.

## Структура

```
observability/
├── __init__.py            # Экспорты
├── error_handling.py      # Централизованная обработка ошибок
├── indicators_logging.py  # DEPRECATED compatibility helper
├── logging.py             # Compatibility path; новый код использует src.logging
├── metrics.py             # Сбор и агрегация метрик
├── traceability.py        # Трассировка расчётов
└── README.md
```

## Конфигурация через переменные окружения

| Переменная | Значения | По умолчанию | Описание |
|------------|----------|--------------|----------|
| `FEATURES_LOG_VERBOSITY` | `quiet`, `normal`, `verbose`, `debug` | `normal` | Уровень детализации логов |
| `FEATURES_LOG_FORMAT` | `text`, `json` | `text` | Формат вывода логов |
| `FEATURES_LOG_CATEGORIES` | Список через запятую | все | Фильтр категорий |

### Уровни детализации (Verbosity)

- **quiet** (0): Только ошибки и предупреждения
- **normal** (1): Сводки операций + предупреждения (production default)
- **verbose** (2): Детальный прогресс выполнения
- **debug** (3): Полная диагностика, включая per-item логи

### Категории логов (LogCategory)

| Категория | Описание | Пример использования |
|-----------|----------|---------------------|
| `GATE` | Валидация свежести данных | Проверка готовности данных для расчёта |
| `CALC` | Расчёт индикаторов | Группы индикаторов, время расчёта |
| `MERGE` | Слияние результатов | Объединение колонок в DataFrame |
| `INSERT` | Операции с БД | UPSERT, батчи, количество записей |
| `SCHEMA` | Валидация схемы | Проверка соответствия колонок |
| `DIAG` | Диагностика | Детальные проверки (только DEBUG) |
| `BATCH` | Пакетная обработка | Прогресс батчей |
| `PERF` | Метрики производительности | Время выполнения, fill rate |

## Компоненты

### `logging.py`

Основной модуль логирования с категориями и агрегацией.
Для нового кода используйте импорт из `src.logging`; compatibility path
`src.features.observability.logging` сохранён только для legacy surfaces.

```python
from src.logging import (
    # Категории и уровни
    LogCategory,
    Verbosity,
    should_log,

    # Логгеры
    get_features_logger,
    get_category_logger,

    # Контекст
    set_log_context,
    get_current_run_id,

    # Агрегация (уменьшает спам)
    LogAggregator,

    # Сводка запуска
    RunSummary,
    create_run_summary,
)

# Категорийный логгер с автоматическим префиксом
logger = get_category_logger(LogCategory.CALC)
logger.info("Computing indicators")  # [CALC] Computing indicators

# Агрегированное логирование (вместо 50+ строк - одна сводка)
with LogAggregator(LogCategory.MERGE, "columns") as agg:
    for col in columns:
        agg.add("processed", col, value=fill_rate)
    # Эмитит: [MERGE] columns: processed=26 (avg=0.87) | duration=0.45s

# Проверка уровня перед затратным логированием
if should_log(LogCategory.DIAG, Verbosity.DEBUG):
    logger.debug(f"Detailed diagnostics: {expensive_calculation()}")

# Сводка запуска
summary = create_run_summary("BTC-USDT", "1m")
summary.bars_processed = 1000
summary.indicators_computed = 24
summary.rows_saved = 950
summary.emit()  # [PERF] BTC-USDT/1m | status=ok | bars=1000 | ...
```

### Миграция с `indicators_logging.py`

`indicators_logging.py` помечен как DEPRECATED. Используйте `LogAggregator`:

```python
# Старый код (deprecated):
from src.features.observability.indicators_logging import log_indicator_calculation
log_indicator_calculation(symbol, timeframe, count, time, errors)

# Новый код:
from src.logging import LogAggregator, LogCategory

with LogAggregator(LogCategory.CALC, "indicators") as agg:
    # ... расчёт индикаторов ...
    agg.set_extra("count", count)
    if errors:
        for e in errors:
            agg.add_error(e)
```

**Логгеры:**
- `pklpo.features` - основной логгер
- `pklpo.features.{category}` - категорийные логгеры

### `metrics.py`

Сбор метрик качества и производительности.

```python
from src.features.observability.metrics import FeaturesMetricsCollector

collector = FeaturesMetricsCollector()

# Метрики качества фичи
quality = collector.collect_feature_quality(df, "rsi_14")
# FeatureQuality(fill_rate=0.95, non_null_count=950, ...)

# Метрики расчёта
calc_metrics = collector.collect_calculation_metrics(
    symbol="BTC-USDT-SWAP",
    timeframe="1H",
    bars=1000,
    features=177,
    duration_ms=1500
)
```

### `error_handling.py`

Централизованная обработка ошибок.

```python
from src.features.observability.error_handling import (
    FeatureError,
    FeatureCalculationError,
    FeatureValidationError,
    handle_calculation_error
)

try:
    result = compute_features(df)
except FeatureCalculationError as e:
    handle_calculation_error(e, symbol="BTC-USDT-SWAP")
```

**Иерархия исключений:**
```
FeatureError (base)
├── FeatureValidationError   # Ошибки валидации
├── FeatureCalculationError  # Ошибки расчёта
├── DatabaseError            # Ошибки БД
└── RetryableError           # Можно повторить
```

### `traceability.py`

Трассировка расчётов для отладки.

```python
from src.features.observability.traceability import (
    TraceContext,
    trace_calculation
)

with TraceContext(symbol="BTC-USDT-SWAP", timeframe="1H") as ctx:
    result = compute_features(df)
    ctx.record_metrics(bars=len(df), features=177)

# Получить trace
trace = ctx.get_trace()
# {"symbol": "BTC-USDT-SWAP", "duration_ms": 1500, ...}
```

### `indicators_logging.py` (DEPRECATED)

> **DEPRECATED**: Используйте `LogAggregator` из `logging.py`.

Модуль сохранён для обратной совместимости, но выдаёт DeprecationWarning при импорте.

## Формат логов

### Text формат (по умолчанию)

```
2026-02-02 13:41:27 [INFO] [run_abc123] BTC-USDT/1m pklpo.features.calc: [CALC] Computed 24 indicators | duration=0.8s
2026-02-02 13:42:26 [INFO] [run_abc123] BTC-USDT/1m pklpo.features.insert: [INSERT] upsert | saved=635 | batches_count=2 | duration=1.2s
```

### JSON формат (`FEATURES_LOG_FORMAT=json`)

```json
{"timestamp":"2026-02-02T13:41:27","level":"INFO","logger":"pklpo.features.calc","message":"[CALC] Computed 24 indicators","run_id":"run_abc123","symbol":"BTC-USDT","timeframe":"1m","category":"calc"}
```

## Ожидаемый объём логов

| Режим | Примерный объём | Использование |
|-------|-----------------|---------------|
| `quiet` | ~50-100 строк | Production с алертами |
| `normal` | ~1,000-2,000 строк | Production (рекомендуется) |
| `verbose` | ~5,000-10,000 строк | Отладка конкретных проблем |
| `debug` | ~50,000+ строк | Полная диагностика |

## Тестирование

```bash
pytest tests/features/tests/test_logging_config.py -v
pytest tests/features/tests/test_metrics.py -v
```
