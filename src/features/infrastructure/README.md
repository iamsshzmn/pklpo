# Infrastructure Layer

**Работа с внешними системами и данными**

## Обзор

Infrastructure Layer изолирует внешние зависимости: базу данных, файловую систему, внешние API. Предоставляет стабильные интерфейсы для работы с данными.

## Структура

```
infrastructure/
├── __init__.py              # Экспорты
├── alerts.py                # Система алертов и уведомлений
├── database.py              # Базовые DB операции (entry point)
├── db_operations.py         # Чтение данных (fetch_ohlcv_df, fetch_latest_ts)
├── diagnostics.py           # Диагностика и отладка
├── indicator_registry.py    # Legacy wrapper над registry/specs surfaces
├── insert_indicators.py     # Entry point для вставки
├── upsert_builder.py        # Построение UPSERT запросов
├── upsert_optimizer.py      # Оптимизация batch операций
├── versioning.py            # Версионирование схемы и алгоритмов
├── persistence/             # Подмодуль персистентности
│   ├── __init__.py
│   ├── inserter.py          # Основная логика вставки
│   ├── data_transformer.py  # Трансформация данных
│   ├── schema_cache.py      # Кэширование схемы
│   └── upsert_executor.py   # Исполнение UPSERT
└── README.md
```

## Ключевые компоненты

### `database.py` + `db_operations.py`

Чтение и базовые операции с БД.

```python
from src.features.infrastructure.database import insert_indicators
from src.features.infrastructure.db_operations import (
    fetch_latest_ts,
    fetch_ohlcv_df,
    get_symbol_timeframes_to_update
)

# Получить последний timestamp
latest_ts = await fetch_latest_ts(session, "BTC-USDT-SWAP", "1D")

# Загрузить OHLCV данные
df = await fetch_ohlcv_df(session, "BTC-USDT-SWAP", "1D", since_ts=latest_ts)

# Вставить индикаторы
count = await insert_indicators(session, df_features, "BTC-USDT-SWAP", "1D")
```

### `upsert_builder.py`

Построение UPSERT запросов с санитизацией.

```python
from src.features.infrastructure.upsert_builder import (
    build_upsert_statement,
    sanitize_value,
    filter_columns_by_schema
)

# NaN/Inf → NULL
clean_value = sanitize_value(float('nan'))  # None

# Фильтрация по схеме
valid_cols = filter_columns_by_schema(df.columns, schema_columns)

# Построение UPSERT
stmt = build_upsert_statement(table, columns, values)
```

### `src.utils.retry`

Локальный `src.features.infrastructure.retry` удалён. Для retry используется
общий project-wide слой `src.utils.retry`.

```python
from src.utils.retry import get_db_retry, retry_sync

@get_db_retry()
async def save_data(session, data):
    await session.execute(...)

@retry_sync(max_attempts=3, base_delay=1.0)
def load_local_cache():
    ...
```

### `versioning.py`

Версионирование схемы и алгоритмов.

```python
from src.features.infrastructure.versioning import (
    FeaturesVersionManager,
    get_current_version
)

manager = FeaturesVersionManager()
version = get_current_version()
# VersionInfo(schema_version='v2.0', algo_version='2.0.0', ...)
```

### `indicator_registry.py`

Узкий legacy wrapper для старых import sites. Для нового кода источник истины
по списку индикаторов — `src.features.specs.FEATURE_SPECS`.

```python
from src.features.specs import FEATURE_SPECS

print(f"Available: {len(FEATURE_SPECS)} indicators")
print("rsi_14" in FEATURE_SPECS)
```

### `alerts.py`

Observer-based система алертов для Airflow/monitoring сценариев.

```python
from src.features.infrastructure.alerts import (
    AlertContext,
    AlertDispatcher,
    AlertLevel,
    LogAlertObserver,
)

dispatcher = AlertDispatcher()
dispatcher.subscribe(LogAlertObserver())
dispatcher.notify_all(
    AlertContext(
        dag_id="features_calc",
        task_id="quality_gate",
        execution_date="2026-03-06T00:00:00Z",
        run_id="manual__2026-03-06",
        try_number=1,
        error_message="Low fill rate detected",
        level=AlertLevel.WARNING,
    )
)
```

## Политика схемы

Схема БД управляется миграциями (Alembic). Динамическое создание колонок в runtime отключено.

```
INSERT ... ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE
SET col1 = EXCLUDED.col1, col2 = EXCLUDED.col2, ...
```

## Принципы

1. **Изоляция** - внешние системы инкапсулированы
2. **Retry** - transient ошибки обрабатываются через `src.utils.retry`
3. **Санитизация** - NaN/Inf → NULL перед записью
4. **Idempotency** - UPSERT безопасен для повторных запусков

## Тестирование

```bash
pytest tests/features/tests/test_database_integration.py -v
pytest tests/features/tests/test_retry.py -v
```

## Update 2026-03-06

- Для retry внутри `features` используется общий `src.utils.retry`; локальный retry-модуль удалён.
- Для application-layer сохранения добавлен adapter `src.features.infrastructure.persistence.repository.SqlAlchemyIndicatorRepository`.
- Вызовы из `application/save.py` теперь идут через `IndicatorRepository`, а не через прямой вызов `insert_indicators()`.
