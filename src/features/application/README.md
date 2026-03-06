# Application Layer

**Слой оркестрации и координации процессов**

## Обзор

Application Layer координирует работу других слоев, управляет workflow и обрабатывает ошибки. Не содержит бизнес-логику расчётов - делегирует её Core и Domain слоям.

## Структура

```
application/
├── __init__.py          # Экспорты модуля
├── backfill.py          # Backfill менеджер для пересчёта исторических данных
├── batch_processor.py   # Обработка батчей symbol-timeframe
├── calc.py              # Streaming расчёт и Parquet экспорт
├── save_dependencies.py # Composition-root helper для save use cases
├── save.py              # Сохранение в PostgreSQL (batch UPSERT)
└── README.md
```

## Компоненты

### `batch_processor.py`

Оркестрация обработки одной пары symbol-timeframe.

```python
from src.features.application.batch_processor import process_single_pair

success, count, time, errors = await process_single_pair(
    session, "BTC-USDT-SWAP", "1D", available_indicators
)
```

**Workflow:**
1. Получение последнего timestamp из indicators
2. Извлечение новых OHLCV данных
3. Проверка достаточности данных (min 20 строк)
4. Расчёт индикаторов через Core API
5. Сохранение с retry/backoff

### `calc.py`

Streaming обработка больших датасетов с chunking.

```python
from src.features.application.calc import process_chunks, compute_and_dump_parquet
from src.features.application.feature_service import create_feature_service
import pandas as pd

# Streaming обработка
df_ohlcv = pd.read_csv("ohlcv.csv")
reader = iter([df_ohlcv])

chunks = list(process_chunks(
    reader,
    symbol="BTC-USDT-SWAP",
    timeframe="1D",
    available_indicators={"ema_21", "rsi_14"},
    calculator=create_feature_service(),
))

# Экспорт в Parquet
compute_and_dump_parquet(
    df_ohlcv=df_ohlcv,
    symbol="BTC-USDT-SWAP",
    timeframe="1D",
    output_path="features.parquet",
    available_indicators={"ema_21", "rsi_14"},
    calculator=create_feature_service(),
)
```

**Особенности:**
- Chunk size: 200K rows (настраивается)
- Overlap: 200 rows для warmup индикаторов
- GC после каждого чанка
- Memory footprint: ~500MB для 1M+ rows

### `save.py`

Thin orchestration facade для сохранения в PostgreSQL через repository boundary.

```python
from src.features.application.save import save_parquet_to_pg, save_batch
from src.features.application.save_dependencies import (
    create_feature_save_dependencies,
)

# Composition root для save use cases
save_deps = create_feature_save_dependencies(session)

# Из Parquet файла
result = await save_parquet_to_pg(
    session,
    "features.parquet",
    "BTC-USDT-SWAP",
    "1D",
    repository=save_deps.repository,
    validator=save_deps.validator,
    observer=save_deps.observer,
)

# Batch сохранение DataFrame
result = await save_batch(
    session,
    df_features,
    "BTC-USDT-SWAP",
    "1D",
    repository=save_deps.repository,
    observer=save_deps.observer,
)
```

**Особенности:**
- Application-слой не содержит прямых SQL/DB health-check вызовов
- Default wiring для save-path вынесен в `create_feature_save_dependencies(session)`
- Persistence вызывается через `IndicatorRepository`, а не через прямой DB helper
- UPSERT и retry остаются в infrastructure adapter
- NaN/Inf → NULL и schema-aware preparation выполняются в persistence layer

### `backfill.py`

Менеджер пересчёта исторических данных.

```python
from src.features.application.backfill import FeaturesBackfillManager, BackfillConfig

manager = FeaturesBackfillManager()

config = BackfillConfig(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 12, 31),
    symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
    timeframes=["1H", "4H", "1D"],
    dry_run=True
)

# Оценка scope
scope = manager.estimate_backfill_scope(config)
print(f"Estimated records: {scope['total_estimated_records']}")

# Запуск backfill
result = await manager.run_backfill(config)
```

## Принципы

1. **Оркестрация** - координирует слои, не содержит бизнес-логику
2. **Транзакции** - управляет commit/rollback
3. **Retry** - общий retry слой через `src.utils.retry` для transient ошибок
4. **Idempotency** - UPSERT гарантирует безопасность повторных запусков

## Зависимости

```
Application Layer
├── uses → Core API (compute_features)
├── uses → Infrastructure (database, persistence)
└── uses → Domain (models, specs)
```

## Тестирование

```bash
pytest tests/features/tests/test_backfill.py -v
pytest tests/features/tests/test_comprehensive.py -v
```
