# Features Module

**Версия:** 2.0.0 | **Статус:** Production Ready

Модуль расчёта 500+ технических индикаторов с онлайн/офлайн паритетом.

---

## 1. Purpose

Расчёт технических индикаторов для криптовалютных торговых пар с гарантией:
- **No look-ahead bias** — расчёт только по закрытым барам
- **Online/offline parity** — идентичные результаты в реальном времени и исторических расчётах
- **Idempotency** — повторные запуски безопасны благодаря UPSERT
- **Quality gates** — автоматическая валидация перед записью в БД

**Ключевые возможности:**
- 500+ индикаторов в 10 группах (MA, oscillators, volatility, volume, trend, candles, squeeze, overlap, statistics, performance)
- Streaming обработка для больших датасетов (200K rows/chunk)
- Интеграция с Airflow DAG `features_calc`

---

## 2. Inputs

### 2.1 Источники данных

| Источник | Описание | Формат |
|----------|----------|--------|
| PostgreSQL `ohlcv_p` | Основной источник OHLCV данных | Partitioned table |
| CSV файлы | Альтернативный источник для streaming | pandas-совместимый CSV |

### 2.2 Схема входных данных (OHLCV)

```python
# Обязательные колонки
REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

# Опциональные колонки
OPTIONAL_COLUMNS = ["timestamp"]  # Unix timestamp (секунды или ms) или datetime
```

| Колонка | Тип | Constraints |
|---------|-----|-------------|
| `timestamp` | int64 / datetime | Монотонно возрастающий, уникальный |
| `open` | float64 | > 0 |
| `high` | float64 | >= low, >= open, >= close |
| `low` | float64 | <= high, <= open, <= close |
| `close` | float64 | > 0 |
| `volume` | float64 | >= 0 |

### 2.3 Контекстные параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `symbol` | str | Торговая пара, e.g. `BTC-USDT-SWAP` |
| `timeframe` | str | Интервал: `1m`, `5m`, `15m`, `1H`, `4H`, `1D` |
| `specs` | list[str] | Список индикаторов для расчёта (опционально — все) |

---

## 3. Outputs

### 3.1 Sink (куда пишем)

| Таблица | Описание |
|---------|----------|
| `indicators_p` | PostgreSQL partitioned table с рассчитанными индикаторами |

### 3.2 Схема выходных данных

**Primary Key:** `(symbol, timeframe, timestamp)`

**Служебные поля:**

| Колонка | Тип | Описание |
|---------|-----|----------|
| `symbol` | VARCHAR | Торговая пара |
| `timeframe` | VARCHAR | Интервал |
| `timestamp` | BIGINT | Unix timestamp (секунды) |
| `calculated_at` | TIMESTAMP | Время расчёта |

**Индикаторы (200+ колонок):**

| Группа | Примеры колонок | Тип |
|--------|-----------------|-----|
| **ma** | `ema_12`, `ema_21`, `sma_50`, `hma_20` | DOUBLE PRECISION |
| **oscillators** | `rsi_14`, `macd`, `stoch_k`, `cci_14`, `willr` | DOUBLE PRECISION |
| **volatility** | `atr_14`, `bb_upper`, `bb_lower`, `kc_upper` | DOUBLE PRECISION |
| **volume** | `obv`, `vwap`, `cmf`, `mfi` | DOUBLE PRECISION |
| **trend** | `adx_14`, `supertrend`, `psar`, `aroon_up` | DOUBLE PRECISION |
| **candles** | `ha_open`, `ha_close`, `cdl_doji` | DOUBLE PRECISION |
| **squeeze** | `ttm_squeeze`, `ttm_sqzmom` | DOUBLE PRECISION |
| **statistics** | `rolling_median`, `rolling_std` | DOUBLE PRECISION |
| **performance** | `returns`, `sharpe`, `max_drawdown` | DOUBLE PRECISION |

### 3.3 Полный список индикаторов

```python
from src.features.specs import FEATURE_SPECS
print(len(FEATURE_SPECS))  # 500+
```

---

## 4. Data Flow

### 4.1 Краткое описание

```
OHLCV (БД/CSV) → Validation → Group Calculation (10 групп) → Normalization → Quality Gates → UPSERT
```

### 4.2 Детальная схема

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT                                           │
│  PostgreSQL ohlcv_p  ──или──  CSV файл                                      │
│  Columns: timestamp, open, high, low, close, volume                         │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VALIDATION LAYER                                     │
│  validators.py: validate_ohlcv_data()                                       │
│  • Проверка обязательных колонок                                            │
│  • Проверка типов данных                                                     │
│  • Проверка constraints (high >= low, volume >= 0)                          │
│  • Проверка монотонности timestamp                                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      GROUP CALCULATION LAYER                                 │
│  group_calculation.py → indicator_groups/*.py                               │
│                                                                              │
│  Порядок расчёта (зависимости соблюдены):                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  1. overlap     →  2. ma         →  3. oscillators  →  4. volatility  │ │
│  │       ↓              ↓                   ↓                  ↓          │ │
│  │  5. volume      →  6. trend      →  7. candles      →  8. squeeze     │ │
│  │       ↓              ↓                   ↓                  ↓          │ │
│  │  9. statistics  → 10. performance                                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Каждая группа: TA-Lib → pandas_ta → Python fallback                      │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                       MERGING & NORMALIZATION                                │
│  core/merging.py + core/normalization.py                                    │
│  • Объединение результатов всех групп                                       │
│  • Приведение типов к float64                                               │
│  • Волатильностная нормализация (опционально)                               │
│  • Нормализация имён колонок                                                │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         QUALITY GATES                                        │
│  gate_validation.py: GateValidator.validate_before_write()                  │
│  • min_rows >= 20                                                            │
│  • fill_rate >= 50% per group                                               │
│  • nan_ratio <= 10% per group                                               │
│  • outlier_ratio <= 5%                                                       │
│  • timestamp consistency                                                     │
│  ✗ Fail → блокировка записи + отчёт                                         │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PERSISTENCE LAYER                                       │
│  infrastructure/persistence/inserter.py                                     │
│                                                                              │
│  DataFrame → build_batch_data() → normalize_record_names()                  │
│           → filter_columns_by_schema() → normalize_numeric_columns()        │
│           → sanitize_records() → build_upsert_statement() → execute         │
│                                                                              │
│  UPSERT: INSERT ... ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                          │
│  PostgreSQL indicators_p (partitioned by symbol, timeframe)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Architecture

#### Layers & Responsibilities

| Слой | Ответственность | Ключевые модули |
|------|-----------------|-----------------|
| **Interface / Entry Points** | Запуск из CLI, DAG или Python API | `cli/main.py`, Airflow DAG `features_calc`, `__init__.py` |
| **Application** | Оркестрация batch/streaming/backfill и сохранения | `application/calc.py`, `batch_processor.py`, `backfill.py`, `save.py` |
| **Core (Calculation Engine)** | Валидация входа, граф зависимостей, расчёт групп, merge/normalize | `core/validation.py`, `dependency_graph.py`, `group_calculator.py`, `merging.py` |
| **Domain** | Контракты, модели, протоколы — без внешних зависимостей | `domain/models.py`, `protocols.py`, `strategy.py` |
| **Infrastructure** | Работа с БД, UPSERT, registry индикаторов | `infrastructure/database.py`, `upsert_builder.py`, `persistence/inserter.py` |
| **Observability** | Quality gates, метрики, логи — пассивный слой | `validation/gate_validator.py`, `observability/metrics.py`, `observability/error_handling.py` |

#### Dependency Direction Rules

Зависимости направлены **строго внутрь** — внешние слои зависят от внутренних, не наоборот:

```
Interface
    ↓
Application
    ↓
Core  ←──────────────────────  Infrastructure
    ↓                            (через domain/protocols — порты)
Domain
(нет зависимостей)

Observability — подключается пассивно на любом слое, сам ни от чего не зависит
```

**Запрещённые зависимости:**

| Нарушение | Почему запрещено |
|-----------|-----------------|
| `core/` → `infrastructure/` | Core не должен знать о БД или внешних системах |
| `core/` → `application/` | Нет обратных зависимостей вверх по слоям |
| `domain/` → любой слой | Domain — чистые модели и протоколы, ноль внешних зависимостей |
| `infrastructure/` → `application/` | Infra — только адаптеры, не оркестратор |

#### Runtime Path

```
CLI / DAG / Python API
         ↓
Application: читает OHLCV из БД или CSV
         ↓
Core: validate_ohlcv() — схема, типы, монотонность timestamps
         ↓
Core: dependency_graph → group_calculation (10 групп, строго по порядку)
         ↓
Core: merge + normalize — объединение групп, приведение типов
         ↓
Validation: quality_gate — fill_rate, nan_ratio, min_rows, consistency
         ↓ fail → блокировка записи + детальный отчёт
         ↓ pass ↓
Infrastructure: batched UPSERT → indicators_p
         ↓
Observability: метрики + логи выполнения
```

#### Invariants

Инварианты — правила, которые **никогда не нарушаются** независимо от конфигурации или режима запуска:

| Инвариант | Описание |
|-----------|----------|
| **No look-ahead bias** | Расчёт только по закрытым барам; незакрытый бар в расчёт не включается |
| **Idempotent writes** | Повторный запуск с теми же данными не меняет результат; UPSERT по `(symbol, timeframe, timestamp)` |
| **Deterministic pipeline** | Одинаковый вход → одинаковый выход; нет случайности, нет скрытых side effects |
| **Quality-first persistence** | Данные пишутся в БД только после прохождения quality gates; частичные или невалидные записи запрещены |
| **Online/offline parity** | Инкрементальный (online) и batch (offline) расчёт дают идентичные значения для одного и того же набора баров |
| **Graceful degradation** | TA-Lib → pandas_ta → Python fallback; сбой одного backend не останавливает пайплайн, деградация явная и залогированная |

---

## 5. Dependencies & Triggering

### 5.1 Внешние зависимости

| Компонент | Назначение |
|-----------|------------|
| PostgreSQL 14+ | Хранение OHLCV и индикаторов |
| TA-Lib | Основной backend для базовых технических индикаторов |
| pandas_ta | Compatibility layer для индикаторов вне покрытия TA-Lib |
| pandas / numpy | Обработка данных |
| SQLAlchemy 2.0+ | Async ORM |
| asyncpg | PostgreSQL async driver |

### 5.2 Внутренние зависимости

```
src/features/
├── core.py                    # Public API: compute_features()
├── group_calculation.py       # Depends on: indicator_groups/*
├── indicator_groups/          # Depends on: ta_safe/, specs/
├── infrastructure/            # Depends on: SQLAlchemy, asyncpg
└── gate_validation.py         # Depends on: domain/models
```

### 5.3 Triggering (запуск)

| Способ | Описание | Частота |
|--------|----------|---------|
| **Airflow DAG** `features_calc` | Production scheduling | По расписанию (cron) |
| **CLI** `python -m src.cli.main features` | Ручной запуск | Ad-hoc |
| **Python API** `compute_features()` | Программный вызов | По требованию |

### 5.4 Upstream зависимости

```
ohlcv_sync DAG (заполняет ohlcv_p) → features_calc DAG (рассчитывает indicators_p)
```

---

## 6. Storage Details

### 6.1 Таблица indicators_p

| Параметр | Значение |
|----------|----------|
| **Таблица** | `indicators_p` |
| **Partitioning** | По `(symbol, timeframe)` |
| **Primary Key** | `(symbol, timeframe, timestamp)` |
| **Индексы** | PK index, `idx_indicators_symbol_timeframe_ts` |

### 6.2 UPSERT стратегия

```sql
INSERT INTO indicators_p (symbol, timeframe, timestamp, ema_12, rsi_14, ...)
VALUES ($1, $2, $3, $4, $5, ...)
ON CONFLICT (symbol, timeframe, timestamp)
DO UPDATE SET
    ema_12 = EXCLUDED.ema_12,
    rsi_14 = EXCLUDED.rsi_14,
    ...
    calculated_at = EXCLUDED.calculated_at;
```

**Характеристики:**
- **Idempotent:** Повторные запуски безопасны
- **Batch size:** 50 rows (динамический расчёт)
- **NaN/Inf handling:** Автоматическое преобразование в NULL

### 6.3 Retention Policy

| Политика | Описание |
|----------|----------|
| **Хранение** | Без автоматического удаления |
| **Перезапись** | UPSERT обновляет существующие записи |
| **Партиции** | Создаются через Alembic миграции |

### 6.4 Типы данных PostgreSQL

| Python тип | PostgreSQL тип | Преобразование |
|------------|----------------|----------------|
| `float64` | `DOUBLE PRECISION` | Автоматическое |
| `int64` | `BIGINT` | Автоматическое |
| `NaN` | `NULL` | Автоматическое |
| `Inf` | `NULL` | Автоматическое |
| `str` (число) | `DOUBLE PRECISION` | Автоматическое |

---

## 7. Data Quality & Failure Modes

### 7.1 Quality Gates

| Gate | Threshold | При нарушении |
|------|-----------|---------------|
| **min_rows** | >= 20 | Запись блокируется |
| **fill_rate** | >= 50% per group | Запись блокируется |
| **nan_ratio** | <= 10% per group | Запись блокируется |
| **outlier_ratio** | <= 5% | Warning в логах |
| **timestamp_consistency** | Уникальность, монотонность | Запись блокируется |

### 7.2 Режимы сбоев

| Сбой | Поведение | Recovery |
|------|-----------|----------|
| **Недостаточно данных** | NaN series для индикатора | Автоматический, запись с NaN |
| **TA-Lib/pandas_ta ошибка** | Переход на следующий backend в цепочке | Автоматический |
| **DB connection lost** | Retry 3 раза с exponential backoff | Автоматический |
| **Type mismatch** | Автоматическая нормализация типов | Автоматический |
| **Quality gate fail** | Запись блокируется, детальный отчёт | Требует вмешательства |
| **Unknown column** | Колонка игнорируется (warning) | Автоматический |

### 7.3 Error Handling

```python
# Иерархия исключений
FeatureError (base)
├── FeatureValidationError   # Ошибки валидации входных данных
├── FeatureCalculationError  # Ошибки расчёта индикаторов
├── DatabaseError            # Ошибки работы с БД
└── RetryableError           # Ошибки с возможностью retry
```

### 7.4 Retry Policy

| Параметр | Значение |
|----------|----------|
| **Max retries** | 3 |
| **Base delay** | 1 секунда |
| **Max delay** | 60 секунд |
| **Backoff** | Exponential (factor=2) |

---

## 8. Performance Notes

### 8.1 Бенчмарки

| Режим | Throughput | Memory |
|-------|------------|--------|
| **Batch** (< 100K rows) | ~10,000 rows/s | ~5 GB |
| **Streaming** (> 1M rows) | ~6,000 rows/s | ~500 MB |
| **Group calculation** | ~5,000 rows/s | ~800 MB |

*Тестовое окружение: 16GB RAM, 4 cores*

### 8.2 Streaming конфигурация

| Параметр | Значение | Описание |
|----------|----------|----------|
| **CHUNK_SIZE** | 200,000 rows | Размер чанка |
| **OVERLAP_SIZE** | 200+ rows | Перекрытие между чанками |
| **DB_BATCH_SIZE** | 5-200 rows (dynamic) | Адаптивный батч для UPSERT (зависит от ширины и объема payload) |

### 8.3 Оптимизации

- **Chunk processing:** Итеративная обработка, garbage collection после каждого чанка
- **Batch UPSERT:** Минимизация round-trips к БД
- **Schema caching:** Кэширование структуры таблицы
- **Lazy evaluation:** Расчёт только запрошенных индикаторов

### 8.4 Ограничения

- Минимум 20 баров для корректного расчёта большинства индикаторов
- Некоторые индикаторы требуют 200+ баров для warmup (Ichimoku, KAMA)
- Memory footprint растёт линейно с количеством индикаторов

---

## 9. Observability

### 9.1 Логирование

| Logger | Файл | Level |
|--------|------|-------|
| `pklpo.features` | `logs/features.log` | DEBUG |
| `pklpo.features` | `logs/features_errors.log` | ERROR |
| Console | stdout | INFO |

**Формат:** `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

**Rotation:** 10MB, 5 backups

### 9.2 Ключевые точки логирования

| Событие | Level | Что логируется |
|---------|-------|----------------|
| Начало расчёта | INFO | symbol, timeframe, rows_count |
| Завершение группы | DEBUG | group_name, fill_rate, duration |
| Quality gate check | INFO | passed/failed, details |
| UPSERT | INFO | rows_inserted, batch_count |
| Ошибка | ERROR | full traceback, problematic values |

### 9.3 Метрики

```python
from src.features.metrics import FeatureMetrics

# Доступные метрики
metrics = FeatureMetrics(
    rows_written=1000,
    rows_last_24h=50000,
    upsert_failures=0,
    fill_rates={"ma": 0.95, "oscillators": 0.92},
    calculation_time_ms=1500,
    data_quality_score=0.98
)
```

### 9.4 Smoke Validation (Airflow)

```python
# DAG task: smoke_validate_features
# Метрики:
# - total_rows: общее количество записей
# - rows_last_24h: записи за последние 24 часа
# - nan_ratio_last_24h: процент NaN за 24 часа
```

### 9.5 Мониторинг критических индикаторов

Индикаторы для мониторинга fill_rate:
`rsi_14`, `macd`, `atr_14`, `obv`, `vwap`, `supertrend`, `psar`, `aroon_up`, `stochrsi_k`

---

## 10. Runbook

### 10.1 Запуск расчёта

**CLI (рекомендуется для ad-hoc):**

```bash
# Расчёт для конкретных пар и таймфреймов
python -m src.cli.main features --symbols BTC-USDT-SWAP ETH-USDT-SWAP --timeframes 1m 5m 15m

# С нормализацией
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1H --normalize

# С ограничением количества баров
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1D --limit 1000
```

**Python API:**

```python
from src.features.core import compute_features
import pandas as pd

# Загрузка OHLCV данных
df_ohlcv = pd.read_sql("SELECT * FROM ohlcv_p WHERE symbol='BTC-USDT-SWAP'", engine)

# Расчёт индикаторов
df_result = compute_features(
    df_ohlcv,
    specs=['ema_12', 'rsi_14', 'macd', 'atr_14'],
    volatility_normalize=True
)
```

**Airflow:**

```bash
# Trigger DAG
airflow dags trigger features_calc
```

### 10.2 Проверка результатов

**SQL проверка:**

```sql
-- Количество записей
SELECT symbol, timeframe, COUNT(*) as cnt,
       MIN(timestamp) as min_ts, MAX(timestamp) as max_ts
FROM indicators_p
GROUP BY symbol, timeframe;

-- Проверка fill rate
SELECT symbol, timeframe,
       COUNT(*) as total,
       COUNT(rsi_14) as rsi_filled,
       COUNT(macd) as macd_filled
FROM indicators_p
WHERE timestamp > EXTRACT(EPOCH FROM NOW() - INTERVAL '24 hours')
GROUP BY symbol, timeframe;

-- Проверка NaN ratio
SELECT symbol, timeframe,
       100.0 * SUM(CASE WHEN rsi_14 IS NULL THEN 1 ELSE 0 END) / COUNT(*) as nan_pct
FROM indicators_p
GROUP BY symbol, timeframe;
```

**Smoke test:**

```bash
# Запуск smoke теста
python scripts/run_features_smoke.py BTC-USDT-SWAP 1D --limit 200

# Диагностический режим (по одной записи)
DIAGNOSTIC_SINGLE_ROW=1 python scripts/test_upsert.py --symbols BTC-USDT-SWAP --timeframes 1m --limit 10
```

### 10.3 Диагностика проблем

**Проблема: UPSERT падает с type error**

```bash
# 1. Включить диагностический режим
DIAGNOSTIC_SINGLE_ROW=1 python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m --limit 10

# 2. Смотреть логи на предмет проблемных значений
tail -f logs/features_errors.log
```

**Проблема: Низкий fill rate**

```bash
# 1. Проверить количество входных данных
python -c "
from src.database import get_session
from sqlalchemy import text
with get_session() as s:
    r = s.execute(text(\"SELECT COUNT(*) FROM ohlcv_p WHERE symbol='BTC-USDT-SWAP'\"))
    print(r.scalar())
"

# 2. Проверить quality gates
python -c "
from src.features.gate_validation import GateValidator, GateConfig
# ... загрузка данных ...
validator = GateValidator(GateConfig())
is_valid, report = validator.validate_before_write(df, {})
print(report)
"
```

**Проблема: Индикаторы не рассчитываются**

```bash
# 1. Проверить что индикатор в реестре
python -c "
from src.features.specs import FEATURE_SPECS
print('rsi_14' in FEATURE_SPECS)
"

# 2. Проверить зависимости
python -c "
from src.features.specs import FEATURE_SPECS
spec = FEATURE_SPECS.get('rsi_14')
print(f'Requires: {spec.requires if spec else \"NOT FOUND\"}')
"
```

### 10.4 Типичные операции

| Операция | Команда |
|----------|---------|
| Пересчитать все индикаторы для пары | `python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m 1H 4H 1D` |
| Проверить доступные индикаторы | `python -m src.features list-indicators` |
| Информация об индикаторе | `python -m src.features info rsi_14` |
| Запустить тесты | `pytest tests/features/tests/` |
| Запустить с coverage | `pytest tests/features/tests/ --cov=src/features` |

### 10.5 Environment Variables

| Variable | Default | Описание |
|----------|---------|----------|
| `POSTGRES_USER` | — | DB user |
| `POSTGRES_PASSWORD` | — | DB password |
| `POSTGRES_DB` | — | DB name |
| `DB_HOST` | localhost | DB host |
| `DB_PORT` | 5432 | DB port |
| `FEATURES_TA_BACKEND` | `auto` | Backend policy: `auto = TA-Lib → pandas_ta → fallback` |
| `DIAGNOSTIC_SINGLE_ROW` | 0 | Режим диагностики (1 = включён) |

---

## Appendix A: Структура модуля

```
src/features/
├── __init__.py                 # Public API: compute_features, FEATURE_SPECS
├── core/                       # Расчётный движок (177 индикаторов)
│   ├── __init__.py             # compute_features()
│   ├── calculation.py          # Основная логика расчёта
│   ├── dependency_graph.py     # Граф зависимостей
│   ├── group_calculation.py    # Расчёт по группам
│   ├── merging.py              # Объединение результатов
│   ├── name_mapping.py         # Маппинг имён
│   ├── normalization.py        # Нормализация типов
│   ├── pipeline.py             # Pipeline обработки
│   └── validation.py           # Валидация входных данных
├── application/                # Оркестрация процессов
│   ├── backfill.py             # Backfill менеджер
│   ├── batch_processor.py      # Обработка батчей
│   ├── calc.py                 # Streaming расчёт
│   └── save.py                 # Сохранение в PostgreSQL
├── domain/                     # Бизнес-логика
│   ├── models.py               # FeatureSpec, FeatureResult
│   ├── protocols.py            # Интерфейсы
│   └── strategy.py             # Стратегии расчёта
├── infrastructure/             # Внешние системы
│   ├── database.py             # DB entry point
│   ├── db_operations.py        # Чтение данных
│   ├── alerts.py               # Система алертов
│   ├── upsert_builder.py       # Построение UPSERT
│   ├── versioning.py           # Версионирование
│   ├── indicator_registry.py   # Реестр индикаторов
│   └── persistence/            # Подмодуль персистентности
├── observability/              # Мониторинг
│   ├── logging.py              # Конфигурация логгеров
│   ├── metrics.py              # Сбор метрик
│   ├── error_handling.py       # Обработка ошибок
│   └── traceability.py         # Трассировка
├── validation/                 # Валидация
│   ├── data_validator.py       # Валидация входных данных
│   ├── feature_validator.py    # Валидация результатов
│   ├── gate_validator.py       # Quality gates
│   └── code_validator.py       # Валидация конфигурации
├── specs/                      # Спецификации (177 индикаторов)
│   ├── ma.py, oscillators.py, volatility.py, volume.py
│   ├── trend.py, candles.py, overlap.py
│   ├── statistics.py, performance.py
│   └── utils.py
├── indicator_groups/           # Реализации расчётов
│   ├── ma.py, oscillators.py, volatility.py, volume.py
│   ├── trend.py, candles.py, squeeze.py, overlap.py
│   ├── statistics.py, performance.py
│   └── data_cleaner.py
├── config/                     # Конфигурация
│   └── settings.py             # FeaturesSettings
├── utils/                      # Утилиты
│   ├── time_utils.py           # Работа с временем
│   ├── memlog.py               # Мониторинг памяти
│   └── utils.py                # Общие утилиты
└── tests/                      # Тесты
```

---

## Appendix B: Группы индикаторов

| # | Группа | Файл | Кол-во | Зависит от |
|---|--------|------|--------|------------|
| 1 | overlap | overlap.py | 5+ | — |
| 2 | ma | ma.py | 30+ | overlap |
| 3 | oscillators | oscillators.py | 40+ | overlap, ma |
| 4 | volatility | volatility.py | 20+ | overlap, ma |
| 5 | volume | volume.py | 15+ | overlap |
| 6 | trend | trend.py | 40+ | overlap, ma, volatility |
| 7 | candles | candles.py | 80+ | overlap |
| 8 | squeeze | squeeze.py | 10+ | volatility, trend |
| 9 | statistics | statistics.py | 20+ | overlap, ma |
| 10 | performance | performance.py | 15+ | overlap, ma, volatility |

---

**Версия:** 2.0.0
**Последнее обновление:** 2026-03-06
**Статус:** Production Ready
