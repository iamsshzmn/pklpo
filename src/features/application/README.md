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

# Streaming обработка
result = process_chunks(
    df_ohlcv,
    chunk_size=200_000,
    overlap=200,
    specs=['ema_21', 'rsi_14']
)

# Экспорт в Parquet
compute_and_dump_parquet(
    input_path="ohlcv.csv",
    output_path="features.parquet",
    specs=['ema_21', 'rsi_14']
)
```

**Особенности:**
- Chunk size: 200K rows (настраивается)
- Overlap: 200 rows для warmup индикаторов
- GC после каждого чанка
- Memory footprint: ~500MB для 1M+ rows

### `save.py`

Batch сохранение в PostgreSQL с UPSERT.

```python
from src.features.application.save import save_parquet_to_pg, save_batch

# Из Parquet файла
count = await save_parquet_to_pg(session, "features.parquet", "BTC-USDT-SWAP", "1D")

# Batch сохранение DataFrame
count = await save_batch(session, df_features, "BTC-USDT-SWAP", "1D")
```

**Особенности:**
- UPSERT: `ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE`
- Batch size: 50K rows
- NaN/Inf → NULL автоматически
- Schema validation перед записью

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
3. **Retry** - exponential backoff для transient ошибок
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
pytest src/features/tests/test_backfill.py -v
pytest src/features/tests/test_comprehensive.py -v
```
