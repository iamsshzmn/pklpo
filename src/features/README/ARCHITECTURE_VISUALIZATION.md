# Визуализация Архитектуры Модуля Features

## 📋 Содержание
- [Обзор](#обзор)
- [Слоистая Архитектура](#слоистая-архитектура)
- [Компоненты Системы](#компоненты-системы)
- [Поток Данных](#поток-данных)
- [Зависимости Модулей](#зависимости-модулей)
- [Группы Индикаторов](#группы-индикаторов)
- [Инфраструктурные Компоненты](#инфраструктурные-компоненты)
- [Диаграммы Последовательности](#диаграммы-последовательности)

---

## 🎯 Обзор

Модуль `features` - это комплексная система для расчета технических индикаторов с поддержкой:
- ✅ Online/Offline паритета (одинаковые результаты в реальном времени и исторических расчетах)
- ✅ Предотвращения Look-Ahead Bias (отсутствие заглядывания в будущее)
- ✅ Streaming обработки больших данных
- ✅ Batch и Group расчетов
- ✅ Интеграции с Airflow
- ✅ Quality Gates и валидаций

**Ключевые принципы:**
- Clean Architecture (слоистая архитектура)
- Разделение ответственности
- Dependency Inversion
- Модульность и расширяемость

---

## 🏗️ Слоистая Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         API LAYER                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  core.py: compute_features()                             │   │
│  │  - Главная точка входа для пользователей                 │   │
│  │  - Унифицированный интерфейс расчета                     │   │
│  │  - Online/Offline parity                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  application/batch_processor.py                          │   │
│  │  - Оркестрация процессов обработки                       │   │
│  │  - Координация между Domain и Infrastructure             │   │
│  │  - Управление жизненным циклом операций                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  calc.py: Streaming Processing                           │   │
│  │  - Потоковая обработка больших объемов                   │   │
│  │  - Chunk-based calculation с overlap                     │   │
│  │  - Memory-efficient операции                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  calc_indicators.py: Legacy Integration                  │   │
│  │  - Интеграция с существующей системой                    │   │
│  │  - Airflow DAG integration                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  group_calculation.py: Group-based Calculation           │   │
│  │  - Групповой расчет по типам индикаторов                 │   │
│  │  - Batch persistence после каждой группы                 │   │
│  │  - Соблюдение порядка зависимостей                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                       DOMAIN LAYER                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  domain/calculator.py                                    │   │
│  │  - Бизнес-логика расчета индикаторов                     │   │
│  │  - Facade для compute_features                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  domain/protocols.py                                     │   │
│  │  - Абстракции и протоколы                                │   │
│  │  - IndicatorCalculator, BatchIndicatorCalculator         │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  domain/indicator_specs.py                               │   │
│  │  - Спецификации индикаторов                              │   │
│  │  - Бизнес-правила для каждого индикатора                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   INFRASTRUCTURE LAYER                           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  infrastructure/database.py                              │   │
│  │  - Работа с базой данных                                 │   │
│  │  - Database connection management                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  infrastructure/db_operations.py                         │   │
│  │  - CRUD операции: чтение OHLCV, metadata                 │   │
│  │  - fetch_latest_ts, fetch_ohlcv_df                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  infrastructure/insert_indicators.py                     │   │
│  │  - Запись индикаторов в БД                               │   │
│  │  - UPSERT logic, sanitize NaN/Inf                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  infrastructure/upsert_builder.py                        │   │
│  │  - Построение UPSERT запросов                            │   │
│  │  - SQL generation, batch optimization                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  infrastructure/indicator_registry.py                    │   │
│  │  - Реестр доступных индикаторов                          │   │
│  │  - Метаданные и маппинг имен                             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    CALCULATION LAYER                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  indicator_groups/                                       │   │
│  │  ├── ma.py              - Moving Averages                │   │
│  │  ├── oscillators.py     - RSI, MACD, Stochastic          │   │
│  │  ├── volatility.py      - ATR, Bollinger, Keltner        │   │
│  │  ├── volume.py          - OBV, VWAP, CMF, MFI            │   │
│  │  ├── trend.py           - ADX, Aroon, Ichimoku           │   │
│  │  ├── squeeze.py         - TTM Squeeze                    │   │
│  │  ├── candles.py         - Heikin-Ashi, Doji             │   │
│  │  ├── overlap.py         - Overlapping indicators         │   │
│  │  ├── statistics.py      - Statistical indicators         │   │
│  │  └── performance.py     - Performance metrics            │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      SUPPORT LAYER                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  specs.py - Спецификации всех индикаторов (500+)        │   │
│  │  models.py - Data models (FeatureSpec, FeatureError)    │   │
│  │  validators.py - Валидация спецификаций и данных        │   │
│  │  validation.py - Data quality validation                │   │
│  │  gate_validation.py - Quality gates перед записью       │   │
│  │  code_validations.py - Дополнительные проверки          │   │
│  │  metrics.py - Метрики расчетов (fill rate, quality)     │   │
│  │  time_utils.py - Временные операции и валидация         │   │
│  │  utils.py - Утилиты (volatility normalization, etc)     │   │
│  │  error_handling.py - Обработка ошибок                   │   │
│  │  logging_config.py - Конфигурация логирования           │   │
│  │  config.py - Конфигурация системы                       │   │
│  │  name_mapping.py - Маппинг имен индикаторов             │   │
│  │  versioning.py - Версионирование расчетов               │   │
│  │  save.py - Сохранение результатов в parquet             │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Компоненты Системы

### 1. API Layer: `core.py`

**Главная точка входа для всех пользователей модуля.**

```python
# Основная функция
compute_features(
    df_ohlcv: pd.DataFrame,      # OHLCV данные
    specs: list[str] = None,     # Список индикаторов
    available: set[str] = None,  # Доступные колонки в БД
    volatility_normalize: bool = False  # Нормализация по волатильности
) -> pd.DataFrame
```

**Ответственность:**
- Унифицированный интерфейс расчета
- Валидация входных данных
- Координация между группами индикаторов
- Quality gates перед возвратом результатов
- Online/Offline parity

**Зависимости:**
- `validators` - валидация данных и спецификаций
- `time_utils` - работа со временными метками
- `gate_validation` - Quality gates
- `metrics` - сбор метрик
- `group_calculation` - групповой расчет
- `indicator_groups/*` - расчет индикаторов

---

### 2. Calculation Strategy: Group-based Calculation

```
┌────────────────────────────────────────────────────────────┐
│          GROUP CALCULATION ARCHITECTURE                    │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Порядок расчета (с учетом зависимостей):                 │
│                                                            │
│  1. overlap      → Base calculations                      │
│       ↓                                                    │
│  2. ma           → Moving Averages (SMA, EMA, WMA...)     │
│       ↓                                                    │
│  3. oscillators  → RSI, MACD, Stochastic (depend on MA)   │
│       ↓                                                    │
│  4. volatility   → ATR, BB, Keltner (depend on MA)        │
│       ↓                                                    │
│  5. volume       → OBV, VWAP, CMF, MFI                    │
│       ↓                                                    │
│  6. trend        → ADX, Aroon, Ichimoku                   │
│       ↓                                                    │
│  7. candles      → Heikin-Ashi, patterns                  │
│       ↓                                                    │
│  8. squeeze      → TTM Squeeze (depend on BB, Keltner)    │
│       ↓                                                    │
│  9. statistics   → Rolling stats, advanced metrics        │
│       ↓                                                    │
│  10. performance → Returns, Sharpe, Drawdown              │
│                                                            │
│  После каждой группы: Batch Persistence в БД              │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Преимущества:**
- ✅ Соблюдение зависимостей между индикаторами
- ✅ Нет look-ahead bias
- ✅ Batch persistence снижает нагрузку на БД
- ✅ Возможность частичного восстановления при сбоях
- ✅ Оптимизация памяти

---

### 3. Indicator Groups

```
indicator_groups/
├── ma.py              │ 30+ индикаторов │ EMA, SMA, WMA, HMA, KAMA, TEMA...
├── oscillators.py     │ 40+ индикаторов │ RSI, MACD, Stochastic, StochRSI, Williams %R...
├── volatility.py      │ 20+ индикаторов │ ATR, Bollinger Bands, Keltner, Donchian...
├── volume.py          │ 15+ индикаторов │ OBV, VWAP, CMF, MFI, AD...
├── trend.py           │ 40+ индикаторов │ ADX, Aroon, Ichimoku, PSAR, Vortex...
├── squeeze.py         │ 10+ индикаторов │ TTM Squeeze, Squeeze Momentum...
├── candles.py         │ 80+ индикаторов │ Heikin-Ashi, Doji, Hammer, Engulfing...
├── overlap.py         │ 10+ индикаторов │ Base overlapping calculations
├── statistics.py      │ 20+ индикаторов │ Rolling median, std, variance, skew, kurtosis...
└── performance.py     │ 15+ индикаторов │ Returns, volatility, Sharpe, Sortino, drawdown...
```

**Общая структура группы:**

```python
def calc_<group>_indicators(
    df: pd.DataFrame,
    available_cols: set[str],
    logger
) -> pd.DataFrame:
    """
    Расчет индикаторов группы <group>.

    Args:
        df: DataFrame с OHLCV данными и результатами предыдущих групп
        available_cols: Множество доступных колонок в БД
        logger: Logger для записи событий

    Returns:
        DataFrame с добавленными индикаторами группы
    """
    # 1. Проверка требуемых колонок
    # 2. Расчет каждого индикатора группы
    # 3. Обработка ошибок и NaN
    # 4. Возврат результатов
```

---

### 4. Infrastructure Layer

#### 4.1 Database Module

```
infrastructure/
├── database.py           # Connection management, schema constants
├── db_operations.py      # Read operations (fetch OHLCV, metadata)
├── insert_indicators.py  # Write operations (UPSERT indicators)
├── upsert_builder.py     # SQL generation, sanitization
├── indicator_registry.py # Registry facade
└── diagnostics.py        # Health checks, schema validation
```

**Архитектура database layer:**

```
┌─────────────────────────────────────────────────────────┐
│                    database.py                          │
│  - INDICATOR_COLUMNS (schema definition)                │
│  - REQUIRED_FIELDS = {timestamp, symbol, timeframe}     │
│  - Connection management helpers                        │
└─────────────────────────────────────────────────────────┘
                         ↓
        ┌────────────────┴────────────────┐
        ↓                                 ↓
┌──────────────────────┐      ┌──────────────────────┐
│  db_operations.py    │      │ insert_indicators.py │
│  READ operations     │      │ WRITE operations     │
│                      │      │                      │
│  - fetch_latest_ts   │      │ - insert_indicators  │
│  - fetch_ohlcv_df    │      │ - batch UPSERT       │
│  - ensure_columns    │      │ - sanitize NaN/Inf   │
└──────────────────────┘      └──────────────────────┘
                                        ↓
                              ┌──────────────────────┐
                              │  upsert_builder.py   │
                              │                      │
                              │  - Build UPSERT SQL  │
                              │  - Batch optimization│
                              │  - Value sanitization│
                              └──────────────────────┘
```

#### 4.2 UPSERT Strategy

```sql
-- Пример UPSERT запроса, генерируемого upsert_builder.py
INSERT INTO app.indicators (
    symbol, timeframe, timestamp,
    ema_12, ema_26, rsi_14, atr_14, ...
)
VALUES
    ('BTC/USDT', '1h', '2024-01-01 00:00:00', 45000.5, 44800.2, 65.4, 1200.3, ...),
    ...
ON CONFLICT (symbol, timeframe, timestamp)
DO UPDATE SET
    ema_12 = EXCLUDED.ema_12,
    ema_26 = EXCLUDED.ema_26,
    rsi_14 = EXCLUDED.rsi_14,
    ...
    calculated_at = NOW();
```

##### 4.2.1 Async-совместимость UPSERT
- Используется `AsyncSession` и `create_async_engine` (asyncpg).
- Не вызывается `stmt.compile()` — синхронная компиляция в async-контексте приводит к MissingGreenlet.
- Исключено рефлективное `autoload_with` в runtime; таблица берётся как `Indicator.__table__`.
- Для результатов запросов применяются async-методы: `result.all()`/`result.scalar()` вместо `.fetchall()`.
- Коммит выполняется на уровне контекст-менеджера `get_db_session()`; внутри UPSERT нет `session.commit()`.

#### 4.3 Управление схемой (Schema)
- Источник истины — миграции Alembic. Никаких DDL-изменений схемы в runtime.
- `SchemaManager` используется для валидации и маппинга имён, но не для изменения БД.
- Если в DataFrame есть колонки, которых нет в БД, они логируются и отфильтровываются перед UPSERT.
- Требуемые поля задаются в схеме; отсутствие — ошибка валидации до обращения к БД.

#### 4.4 Диагностика вставки (insert_indicators)
Вставка сопровождается подробной диагностикой, пишущейся в логи:
- Проверка наличия уникального индекса на `(symbol, timeframe, timestamp)`.
- Проверка схемы таблицы и `search_path` в текущей сессии.
- Нормализация `timestamp` в миллисекундах, проверка обязательных полей.
- Снимки состояния БД до/после UPSERT (COUNT, MAX(timestamp)) для быстрой верификации результата.
- Санитизация числовых значений, фильтрация проблемных полей (например, `ics_26`, `rma_20`, `t3_20`).

**Особенности:**
- ✅ Batch UPSERT (5000-10000 строк за запрос)
- ✅ Sanitization: NaN/Inf → NULL
- ✅ Conflict resolution по (symbol, timeframe, timestamp)
- ✅ Автоматическое обновление calculated_at

---

### 5. Validation & Quality Gates

```
┌─────────────────────────────────────────────────────────┐
│                  VALIDATION PIPELINE                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  INPUT: df_ohlcv                                        │
│     ↓                                                   │
│  1. validators.py: validate_ohlcv_data()                │
│     - Проверка required columns                         │
│     - Проверка типов данных                             │
│     - Базовая валидация значений                        │
│     ↓                                                   │
│  2. validators.py: validate_phase_requirements()        │
│     - Проверка минимального количества строк            │
│     - Проверка временных диапазонов                     │
│     ↓                                                   │
│  3. time_utils.py: strict_timestamp_validation()        │
│     - Монотонность временных меток                      │
│     - Отсутствие дубликатов                             │
│     - Корректность форматов                             │
│     ↓                                                   │
│  4. CALCULATION PHASE                                   │
│     ↓                                                   │
│  5. code_validations.py: CodeValidator                  │
│     - Проверка на аномалии                              │
│     - Проверка на выбросы                               │
│     - Shadow NaN detection                              │
│     ↓                                                   │
│  6. gate_validation.py: validate_data_gate()            │
│     - Final quality gate перед возвратом/записью        │
│     - min_fill_rate check                               │
│     - max_nan_ratio check                               │
│     - Timestamp consistency                             │
│     ↓                                                   │
│  OUTPUT: validated DataFrame                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Quality Gates (gate_validation.py):**

```python
def validate_data_gate(
    df: pd.DataFrame,
    min_rows: int = 20,
    min_fill_rate: float = 0.5,  # 50% заполненность
    max_nan_ratio: float = 0.1,   # 10% NaN максимум
    strict_mode: bool = False
) -> tuple[bool, list[str], dict]:
    """
    Проверяет качество данных перед записью/возвратом.

    Returns:
        (is_valid, errors, metadata)
    """
```

---

## 📊 Поток Данных

### Основной Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                   MAIN CALCULATION PIPELINE                      │
└──────────────────────────────────────────────────────────────────┘

1. USER CALL
   compute_features(df_ohlcv, specs=['ema_12', 'rsi_14', ...])
          ↓
2. VALIDATION PHASE
   ├─ validate_ohlcv_data()          # Required columns, types
   ├─ validate_phase_requirements()  # Min rows, completeness
   ├─ ensure_ts_column()             # Timestamp handling
   └─ strict_timestamp_validation()  # Monotonicity, no duplicates
          ↓
3. PREPARATION PHASE
   ├─ Parse specs → FeatureSpec objects
   ├─ Group specs by type (ma, oscillators, volatility, ...)
   └─ Initialize result DataFrame
          ↓
4. GROUP CALCULATION PHASE (sequential)
   ├─ Group 1: overlap
   │    ├─ calc_overlap_indicators(df, available_cols)
   │    └─ Add results to df
   ├─ Group 2: ma
   │    ├─ calc_ma_indicators(df, available_cols)
   │    └─ Add results to df
   ├─ Group 3: oscillators (can use MA results)
   │    ├─ calc_oscillator_indicators(df, available_cols)
   │    └─ Add results to df
   ├─ Group 4: volatility (can use MA results)
   │    ├─ calc_volatility_indicators(df, available_cols)
   │    └─ Add results to df
   ├─ ... (continue for all groups)
   └─ Group 10: performance (can use all previous results)
        ├─ calc_performance_indicators(df, available_cols)
        └─ Add results to df
          ↓
5. POST-PROCESSING PHASE
   ├─ Calculate fill rates per indicator
   ├─ Calculate quality scores
   ├─ Apply volatility normalization (if requested)
   └─ Log metrics
          ↓
6. QUALITY GATE
   validate_data_gate(df, min_fill_rate=0.5, max_nan_ratio=0.1)
          ↓
7. RETURN / SAVE
   ├─ Return DataFrame to user, OR
   └─ insert_indicators(session, df) → Database
          ↓
8. METRICS & LOGGING
   ├─ record_fill_rate(indicator, fill_rate)
   ├─ record_quality_metrics(df)
   └─ finish_calculation_metrics(start_time, row_count)
```

---

### Streaming Pipeline (calc.py)

```
┌──────────────────────────────────────────────────────────────────┐
│              STREAMING CALCULATION PIPELINE                      │
└──────────────────────────────────────────────────────────────────┘

1. LARGE DATASET INPUT
   df_ohlcv (millions of rows)
          ↓
2. CHUNK READER
   ├─ Split into chunks (5000-10000 rows)
   ├─ Add overlap (max_lookback period)
   └─ yield chunk_df
          ↓
3. PROCESS EACH CHUNK
   for chunk in chunks:
       ├─ compute_features(chunk)
       ├─ Remove overlap rows
       └─ yield processed_chunk
          ↓
4. SAVE TO PARQUET (streaming)
   ├─ Write chunk to parquet file
   └─ Continue with next chunk
          ↓
5. FINAL AGGREGATION (optional)
   ├─ Read all parquet files
   └─ Combine into final result
```

**Преимущества Streaming:**
- ✅ Memory-efficient (обрабатываем по частям)
- ✅ Поддержка очень больших датасетов
- ✅ Возможность остановки/возобновления
- ✅ Параллельная обработка чанков

---

## 🔗 Зависимости Модулей

### Internal Dependencies

```
core.py
├── models.py (FeatureSpec, FeatureError)
├── specs.py (FEATURE_SPECS)
├── validators.py (validate_*)
├── time_utils.py (ensure_ts_column, validate_timestamp_consistency)
├── gate_validation.py (validate_data_gate)
├── metrics.py (record metrics)
├── group_calculation.py (compute_features_grouped)
└── indicator_groups/
    ├── ma.py
    ├── oscillators.py
    ├── volatility.py
    ├── volume.py
    ├── trend.py
    ├── squeeze.py
    ├── candles.py
    ├── overlap.py
    ├── statistics.py
    └── performance.py

group_calculation.py
├── logging_config.py
├── models.py (FeatureError)
├── time_utils.py
├── gate_validation.py
├── metrics.py
├── upsert_optimizer.py
└── code_validations.py

calc.py
├── core.py (compute_features)
├── logging_config.py
├── utils/memlog.py (memory monitoring)
├── config.py (StreamingConfig)
└── strategy.py (get_max_lookback_for_strategies)

application/batch_processor.py
├── domain/calculator.py (calculate_batch)
└── infrastructure/database.py (fetch_*, insert_*)

infrastructure/insert_indicators.py
└── infrastructure/upsert_builder.py
```

### External Dependencies

```
pandas       # DataFrame operations
numpy        # Numerical computations
pandas_ta    # Technical analysis indicators (via ta_safe.py)
sqlalchemy   # Database ORM
psycopg2     # PostgreSQL driver
pyyaml       # Config files
```

---

## 📈 Диаграммы Последовательности

### 1. Простой расчет индикаторов

```
User                 core.py              indicator_groups/     Database
 │                      │                         │                │
 ├─ compute_features() ─►                         │                │
 │                      ├─ validate_ohlcv_data()  │                │
 │                      ├─ parse specs            │                │
 │                      │                         │                │
 │                      ├─ calc_ma_indicators() ─►│                │
 │                      │◄─ return df_with_ma ────┤                │
 │                      │                         │                │
 │                      ├─ calc_oscillators() ───►│                │
 │                      │◄─ return df_with_osc ───┤                │
 │                      │                         │                │
 │                      ├─ ... other groups       │                │
 │                      │                         │                │
 │                      ├─ validate_data_gate()   │                │
 │◄─ return df ─────────┤                         │                │
 │                      │                         │                │
```

### 2. Batch расчет с сохранением в БД

```
Airflow DAG    calc_indicators.py    batch_processor.py    Domain    Infrastructure
     │                 │                     │               │              │
     ├─ trigger ──────►│                     │               │              │
     │                 ├─ get symbols/TF ────┼──────────────►│              │
     │                 │                     │               ├─ fetch() ───►│
     │                 │                     │               │◄─ data ──────┤
     │                 │                     │               │              │
     │                 ├─ process_single_pair() ───────────►│              │
     │                 │                     ├─ fetch OHLCV ┴─────────────►│
     │                 │                     │◄─ df_ohlcv ──────────────────┤
     │                 │                     │               │              │
     │                 │                     ├─ calculate_batch() ─────────►│
     │                 │                     │               ├─ compute() ─►│
     │                 │                     │               │◄─ df_ind ────┤
     │                 │                     │               │              │
     │                 │                     ├─ insert() ───┴─────────────►│
     │                 │                     │◄─ success ────────────────────┤
     │                 │◄─ result ───────────┤               │              │
     │◄─ success ──────┤                     │               │              │
     │                 │                     │               │              │
```

### 3. Group Calculation с Batch Persistence

```
core.py          group_calculation.py    indicator_groups/    Database
   │                     │                       │               │
   ├─ compute_grouped() ►│                       │               │
   │                     ├─ Group 1: overlap ───►│               │
   │                     │◄─ df_overlap ─────────┤               │
   │                     ├─ persist_batch() ──────┼──────────────►│
   │                     │◄─ success ────────────────────────────┤
   │                     │                       │               │
   │                     ├─ Group 2: ma ────────►│               │
   │                     │◄─ df_ma ──────────────┤               │
   │                     ├─ persist_batch() ──────┼──────────────►│
   │                     │◄─ success ────────────────────────────┤
   │                     │                       │               │
   │                     ├─ ... other groups     │               │
   │                     │                       │               │
   │                     ├─ Group 10: performance►│               │
   │                     │◄─ df_performance ─────┤               │
   │                     ├─ persist_batch() ──────┼──────────────►│
   │                     │◄─ success ────────────────────────────┤
   │◄─ complete ─────────┤                       │               │
   │                     │                       │               │
```

---

## 🗂️ Файловая структура с описаниями

```
src/features/
│
├── 📄 __init__.py                    # Экспорт публичного API
├── 📄 __main__.py                    # CLI entry point
│
├── 🎯 API LAYER
│   ├── 📄 core.py                    # ⭐ Главный API: compute_features()
│   ├── 📄 cli.py                     # CLI commands
│   └── 📄 demo.py                    # Demo и примеры использования
│
├── 📦 APPLICATION LAYER
│   ├── 📁 application/
│   │   ├── 📄 batch_processor.py    # Orchestration для batch обработки
│   │   └── 📄 README.md
│   ├── 📄 calc.py                    # ⭐ Streaming calculation с overlap
│   ├── 📄 calc_indicators.py         # Legacy integration, Airflow entry point
│   ├── 📄 group_calculation.py       # ⭐ Group-based calculation
│   └── 📄 backfill.py                # Backfill missing data
│
├── 🧠 DOMAIN LAYER
│   ├── 📁 domain/
│   │   ├── 📄 calculator.py          # Domain calculator facade
│   │   ├── 📄 protocols.py           # ⭐ Abstractions (Protocol definitions)
│   │   ├── 📄 indicator_specs.py     # Business rules for indicators
│   │   └── 📄 README.md
│
├── 🏗️ INFRASTRUCTURE LAYER
│   ├── 📁 infrastructure/
│   │   ├── 📄 database.py            # ⭐ Schema constants, connection management
│   │   ├── 📄 db_operations.py       # ⭐ Read operations (fetch OHLCV, metadata)
│   │   ├── 📄 insert_indicators.py   # ⭐ Write operations (UPSERT)
│   │   ├── 📄 upsert_builder.py      # ⭐ SQL generation, sanitization
│   │   ├── 📄 indicator_registry.py  # Registry facade
│   │   ├── 📄 diagnostics.py         # Health checks
│   │   └── 📄 README.md
│
├── 🔢 CALCULATION LAYER
│   ├── 📁 indicator_groups/          # ⭐ Группы индикаторов (500+ indicators)
│   │   ├── 📄 __init__.py
│   │   ├── 📄 ma.py                  # Moving Averages (30+)
│   │   ├── 📄 oscillators.py         # Oscillators (40+)
│   │   ├── 📄 volatility.py          # Volatility (20+)
│   │   ├── 📄 volume.py              # Volume (15+)
│   │   ├── 📄 trend.py               # Trend (40+)
│   │   ├── 📄 squeeze.py             # TTM Squeeze (10+)
│   │   ├── 📄 candles.py             # Candle patterns (80+)
│   │   ├── 📄 overlap.py             # Overlapping (10+)
│   │   ├── 📄 statistics.py          # Statistics (20+)
│   │   ├── 📄 performance.py         # Performance (15+)
│   │   ├── 📄 data_cleaner.py        # Data cleaning utilities
│   │   ├── 📄 ta_safe.py             # Safe wrappers for pandas_ta
│   │   └── 📄 README.md
│
├── 🛡️ VALIDATION & QUALITY LAYER
│   ├── 📄 validators.py              # ⭐ Spec & data validation
│   ├── 📄 validation.py              # Data quality validation
│   ├── 📄 gate_validation.py         # ⭐ Quality gates перед записью
│   ├── 📄 code_validations.py        # Additional code-level checks
│   ├── 📄 smoke_validation.py        # Smoke tests для production
│
├── 📊 METRICS & MONITORING LAYER
│   ├── 📄 metrics.py                 # ⭐ Calculation metrics (fill rate, quality)
│   ├── 📄 logging_config.py          # ⭐ Logging configuration
│   ├── 📄 indicators_logging.py      # Indicator-specific logging
│   ├── 📄 error_handling.py          # Error handling utilities
│
├── ⚙️ CONFIGURATION & SPECS LAYER
│   ├── 📄 specs.py                   # ⭐ All indicator specifications (500+)
│   ├── 📄 models.py                  # ⭐ Data models (FeatureSpec, FeatureError)
│   ├── 📄 config.py                  # System configuration
│   ├── 📄 name_mapping.py            # Indicator name mapping
│   ├── 📄 versioning.py              # Version management
│
├── 🔧 UTILITIES LAYER
│   ├── 📄 utils.py                   # ⭐ Utilities (volatility normalization)
│   ├── 📄 time_utils.py              # ⭐ Time operations, validation
│   ├── 📁 utils/
│   │   ├── 📄 memlog.py              # Memory monitoring utilities
│   │   └── 📄 __init__.py
│   ├── 📄 upsert_optimizer.py        # UPSERT optimization
│   ├── 📄 save.py                    # Save to parquet
│   ├── 📄 ta_safe.py                 # Safe pandas_ta wrappers
│   ├── 📄 indicator_utils.py         # Misc indicator utilities
│
├── 🗄️ SCHEMA LAYER
│   ├── 📁 schema/
│   │   ├── 📄 indicators_schema.yml             # Main schema
│   │   ├── 📄 indicators_schema_clean.yml       # Clean version
│   │   ├── 📄 indicators_schema_complete.yml    # Complete version
│   │   └── 📄 schema_manager.py                 # Schema management
│
├── 🧪 TESTING LAYER
│   ├── 📁 tests/
│   │   ├── 📄 test_core.py                      # Core functionality tests
│   │   ├── 📄 test_integration.py               # Integration tests
│   │   ├── 📄 test_database_integration.py      # DB integration tests
│   │   ├── 📄 test_memory_optimization.py       # Memory tests
│   │   ├── 📄 test_streaming_equivalence.py     # Streaming tests
│   │   ├── 📄 test_production_readiness.py      # Production readiness
│   │   ├── 📄 test_comprehensive.py             # Comprehensive tests
│   │   └── ... (20+ test files)
│
├── 📚 DOCUMENTATION LAYER
│   ├── 📁 README/
│   │   ├── 📄 README.md                         # Main documentation
│   │   ├── 📄 COMPREHENSIVE_DOCUMENTATION.md    # Detailed docs
│   │   ├── 📄 README_name_mapping.md            # Name mapping docs
│   │   └── 📄 db_inidicators_description.md     # DB schema docs
│   ├── 📁 reports/
│   │   ├── 📄 ARCHITECTURE.md                   # Architecture report
│   │   ├── 📄 MEMORY_OPTIMIZATION_REPORT.md     # Memory optimization
│   │   ├── 📄 PRODUCTION_READINESS_CHECKLIST.md
│   │   ├── 📄 SMOKE_TESTING_REPORT.md
│   │   └── ... (15+ report files)
│
├── 🗃️ LEGACY/DEPRECATED LAYER
│   ├── 📁 registry/                  # ⚠️ Legacy registry (deprecated)
│   │   ├── 📄 README.md
│   │   └── ... (legacy modules)
│
├── 🛠️ TOOLING LAYER
│   ├── 📁 cli/
│   │   ├── 📄 check_database_setup.py           # DB setup checker
│   │   └── 📄 schema_check.py                   # Schema checker
│   ├── 📄 audit_cli.py                          # Audit CLI
│   ├── 📄 audit_simple.py                       # Simple audit
│   ├── 📄 database_indexes.py                   # Index management
│   └── 📄 calc_combinations.py                  # Indicator combinations
│
└── 📄 strategy.py                    # Trading strategy utilities
```

---

## 🔑 Ключевые принципы

### 1. Clean Architecture

```
┌─────────────────────────────────────────────────────┐
│  Outer Layers зависят от Inner Layers               │
│  Inner Layers НЕ знают о Outer Layers               │
│                                                     │
│  Infrastructure → Domain → Application → API       │
│                                                     │
│  ✅ Domain не зависит от Infrastructure            │
│  ✅ Application координирует Domain + Infrastructure│
│  ✅ API - тонкая обертка над Application           │
└─────────────────────────────────────────────────────┘
```

### 2. Dependency Inversion

```python
# Domain определяет Protocol (абстракцию)
class IndicatorCalculator(Protocol):
    def calculate(self, df: pd.DataFrame, **params) -> pd.Series:
        ...

# Infrastructure реализует Protocol
class PandasTACalculator:
    def calculate(self, df: pd.DataFrame, **params) -> pd.Series:
        return ta.rsi(df['close'], length=params['period'])
```

### 3. Single Responsibility

Каждый модуль имеет одну ответственность:
- `core.py` - API для пользователей
- `validators.py` - только валидация
- `metrics.py` - только сбор метрик
- `insert_indicators.py` - только запись в БД

### 4. No Look-Ahead Bias

```python
# ❌ ПЛОХО: использование будущих данных
df['ma'] = df['close'].rolling(20).mean()  # использует все данные сразу

# ✅ ХОРОШО: расчет только на основе прошлых данных
# Group calculation гарантирует последовательность
# Streaming calculation с overlap гарантирует правильный контекст
```

### 5. Online/Offline Parity

```python
# Один и тот же код для:
# 1. Historical backfill (offline)
compute_features(historical_df, specs=['ema_12'])

# 2. Real-time calculation (online)
compute_features(last_100_candles, specs=['ema_12'])
# Результат последней строки будет идентичен!
```

---

## 📝 Использование

### Базовый пример

```python
from features import compute_features

# 1. Подготовка данных
df_ohlcv = pd.DataFrame({
    'timestamp': [...],
    'open': [...],
    'high': [...],
    'low': [...],
    'close': [...],
    'volume': [...]
})

# 2. Расчет индикаторов
df_indicators = compute_features(
    df_ohlcv=df_ohlcv,
    specs=['ema_12', 'ema_26', 'rsi_14', 'atr_14', 'macd']
)

# 3. Результат
# df_indicators содержит все OHLCV + рассчитанные индикаторы
print(df_indicators[['timestamp', 'close', 'ema_12', 'rsi_14']])
```

### Streaming обработка

```python
from features.calc import calculate_features_streaming

# Обработка большого датасета по частям
result_path = calculate_features_streaming(
    csv_path='large_dataset.csv',
    output_dir='./output',
    symbol='BTC/USDT',
    timeframe='1h',
    available_indicators={'ema_12', 'ema_26', 'rsi_14'},
    chunk_size=5000
)
```

### Интеграция с Airflow

```python
# В Airflow DAG
from features.calc_indicators import calculate_indicators_for_pairs

# Task definition
calculate_task = PythonOperator(
    task_id='calculate_features',
    python_callable=calculate_indicators_for_pairs,
    op_kwargs={
        'symbol_timeframes': [
            ('BTC/USDT', '1h'),
            ('ETH/USDT', '1h'),
        ]
    }
)
```

---

## 🎯 Выводы

### Сильные стороны архитектуры

✅ **Модульность**: Четкое разделение по слоям и ответственности
✅ **Расширяемость**: Легко добавлять новые индикаторы и группы
✅ **Тестируемость**: Каждый компонент можно тестировать изолированно
✅ **Масштабируемость**: Поддержка streaming и batch обработки
✅ **Надежность**: Multiple validation layers, quality gates
✅ **Performance**: Memory-efficient, batch operations, optimized SQL
✅ **Maintainability**: Clean code, good documentation, clear structure

### Области для улучшения

🔄 **Legacy код**: registry/ - deprecated, можно удалить
🔄 **Дублирование**: ta_safe.py существует в двух местах
🔄 **Тесты**: Можно расширить покрытие edge cases
🔄 **Docs**: Некоторые модули требуют больше docstrings

---

## 📚 Дополнительные ресурсы

- **README.md** - Основная документация модуля
- **COMPREHENSIVE_DOCUMENTATION.md** - Детальная документация
- **reports/ARCHITECTURE.md** - Отчет по архитектуре
- **reports/PRODUCTION_READINESS_CHECKLIST.md** - Production readiness
- **tests/** - Примеры использования в тестах

---

**Документ создан:** 2025-10-27
**Версия модуля:** 1.0.0
**Автор:** Architecture Visualization Team
