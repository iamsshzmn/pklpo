# Карта Компонентов Модуля Features

## 🗺️ Визуальная карта всех компонентов и их взаимосвязей

---

## 📦 Структура модуля (Component Tree)

```
features/
│
├─ 🎯 PUBLIC API (Entry Points)
│  │
│  ├─ core.py ⭐⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ compute_features()         [MAIN API]
│  │  │  ├─ get_available_features()   [UTILITY]
│  │  │  ├─ get_feature_info()         [UTILITY]
│  │  │  └─ validate_feature_compatibility() [UTILITY]
│  │  │
│  │  ├─ Импортирует из:
│  │  │  ├─ models.py (FeatureError)
│  │  │  ├─ specs.py (FEATURE_SPECS)
│  │  │  ├─ validators.py
│  │  │  ├─ time_utils.py
│  │  │  ├─ gate_validation.py
│  │  │  ├─ metrics.py
│  │  │  ├─ group_calculation.py
│  │  │  └─ indicator_groups/*
│  │  │
│  │  └─ Используется в:
│  │     ├─ calc.py
│  │     ├─ domain/calculator.py
│  │     └─ application/batch_processor.py
│  │
│  ├─ __init__.py
│  │  └─ Экспортирует: compute_features
│  │
│  ├─ cli.py
│  │  ├─ CLI commands
│  │  └─ Использует: core.py
│  │
│  └─ demo.py
│     └─ Примеры использования
│
│
├─ 🏗️ APPLICATION LAYER (Orchestration)
│  │
│  ├─ application/
│  │  └─ batch_processor.py ⭐⭐⭐⭐
│  │     ├─ Функции:
│  │     │  ├─ process_dataframe()
│  │     │  ├─ process_single_pair()
│  │     │  └─ process_multiple_pairs()
│  │     │
│  │     ├─ Импортирует:
│  │     │  ├─ domain/calculator.py
│  │     │  └─ infrastructure/database.py
│  │     │
│  │     └─ Используется в:
│  │        └─ calc_indicators.py
│  │
│  ├─ calc.py ⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ process_chunks()           [STREAMING]
│  │  │  ├─ calculate_features_streaming()
│  │  │  └─ save_to_parquet()
│  │  │
│  │  ├─ Импортирует:
│  │  │  ├─ core.py (compute_features)
│  │  │  ├─ config.py (StreamingConfig)
│  │  │  └─ utils/memlog.py
│  │  │
│  │  └─ Используется в:
│  │     └─ Airflow DAGs (для больших данных)
│  │
│  ├─ calc_indicators.py ⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ calculate_indicators_for_pairs()
│  │  │  ├─ process_single_pair()
│  │  │  └─ main()
│  │  │
│  │  ├─ Импортирует:
│  │  │  ├─ application/batch_processor.py
│  │  │  └─ infrastructure/database.py
│  │  │
│  │  └─ Используется в:
│  │     └─ Airflow DAG (features_calc)
│  │
│  ├─ group_calculation.py ⭐⭐⭐⭐⭐
│  │  ├─ Классы:
│  │  │  ├─ GroupCalculationConfig
│  │  │  └─ GroupCalculator
│  │  │
│  │  ├─ Функции:
│  │  │  └─ compute_features_grouped()
│  │  │
│  │  ├─ Импортирует:
│  │  │  ├─ models.py
│  │  │  ├─ time_utils.py
│  │  │  ├─ gate_validation.py
│  │  │  ├─ metrics.py
│  │  │  ├─ upsert_optimizer.py
│  │  │  ├─ code_validations.py
│  │  │  └─ indicator_groups/*
│  │  │
│  │  └─ Используется в:
│  │     └─ core.py (для group-based calculation)
│  │
│  └─ backfill.py ⭐⭐⭐
│     ├─ Backfill missing data
│     └─ Использует: calc_indicators.py
│
│
├─ 🧠 DOMAIN LAYER (Business Logic)
│  │
│  └─ domain/
│     │
│     ├─ protocols.py ⭐⭐⭐
│     │  ├─ Протоколы:
│     │  │  ├─ IndicatorCalculator
│     │  │  └─ BatchIndicatorCalculator
│     │  │
│     │  └─ Используется в:
│     │     └─ domain/calculator.py
│     │
│     ├─ calculator.py ⭐⭐⭐
│     │  ├─ Функции:
│     │  │  └─ calculate_batch()
│     │  │
│     │  ├─ Импортирует:
│     │  │  └─ core.py (compute_features)
│     │  │
│     │  └─ Используется в:
│     │     └─ application/batch_processor.py
│     │
│     └─ indicator_specs.py ⭐⭐
│        └─ Business rules for indicators
│
│
├─ 🏛️ INFRASTRUCTURE LAYER (External Systems)
│  │
│  └─ infrastructure/
│     │
│     ├─ database.py ⭐⭐⭐⭐⭐
│     │  ├─ Константы:
│     │  │  ├─ INDICATOR_COLUMNS
│     │  │  └─ REQUIRED_FIELDS
│     │  │
│     │  ├─ Re-exports:
│     │  │  ├─ diagnostics.*
│     │  │  ├─ db_operations.*
│     │  │  └─ insert_indicators.*
│     │  │
│     │  └─ Используется везде
│     │
│     ├─ db_operations.py ⭐⭐⭐⭐
│     │  ├─ Функции:
│     │  │  ├─ fetch_latest_ts()
│     │  │  ├─ fetch_ohlcv_df()
│     │  │  ├─ ensure_columns_exist()
│     │  │  └─ get_symbol_timeframes_to_update()
│     │  │
│     │  └─ Используется в:
│     │     ├─ application/batch_processor.py
│     │     └─ calc_indicators.py
│     │
│     ├─ insert_indicators.py ⭐⭐⭐⭐⭐
│     │  ├─ Функции:
│     │  │  └─ insert_indicators()
│     │  │
│     │  ├─ Импортирует:
│     │  │  └─ upsert_builder.py
│     │  │
│     │  └─ Используется в:
│     │     ├─ application/batch_processor.py
│     │     └─ group_calculation.py
│     │
│     ├─ upsert_builder.py ⭐⭐⭐⭐
│     │  ├─ Классы:
│     │  │  └─ UpsertBuilder
│     │  │
│     │  ├─ Функции:
│     │  │  ├─ build_upsert_query()
│     │  │  ├─ sanitize_value()
│     │  │  └─ batch_upsert()
│     │  │
│     │  └─ Используется в:
│     │     └─ insert_indicators.py
│     │
│     ├─ indicator_registry.py ⭐⭐⭐
│     │  └─ Registry facade
│     │
│     └─ diagnostics.py ⭐⭐
│        ├─ Функции:
│        │  ├─ check_df_schema()
│        │  ├─ validate_schema_compat()
│        │  └─ diagnose_dataframe_issues()
│        │
│        └─ Используется в:
│           └─ database.py
│
│
├─ 🔢 CALCULATION LAYER (Indicator Groups)
│  │
│  └─ indicator_groups/
│     │
│     ├─ ma.py ⭐⭐⭐⭐⭐
│     │  ├─ calc_ma_indicators()
│     │  ├─ 30+ индикаторов
│     │  └─ EMA, SMA, WMA, HMA, KAMA, TEMA, DEMA, etc.
│     │
│     ├─ oscillators.py ⭐⭐⭐⭐⭐
│     │  ├─ calc_oscillator_indicators()
│     │  ├─ 40+ индикаторов
│     │  └─ RSI, MACD, Stochastic, StochRSI, Williams %R, etc.
│     │
│     ├─ volatility.py ⭐⭐⭐⭐⭐
│     │  ├─ calc_volatility_indicators()
│     │  ├─ 20+ индикаторов
│     │  └─ ATR, Bollinger Bands, Keltner, Donchian, etc.
│     │
│     ├─ volume.py ⭐⭐⭐⭐
│     │  ├─ calc_volume_indicators()
│     │  ├─ 15+ индикаторов
│     │  └─ OBV, VWAP, CMF, MFI, AD, etc.
│     │
│     ├─ trend.py ⭐⭐⭐⭐⭐
│     │  ├─ calc_trend_indicators()
│     │  ├─ 40+ индикаторов
│     │  └─ ADX, Aroon, Ichimoku, PSAR, Vortex, CCI, etc.
│     │
│     ├─ squeeze.py ⭐⭐⭐
│     │  ├─ calc_squeeze_indicators()
│     │  ├─ 10+ индикаторов
│     │  └─ TTM Squeeze, Squeeze Momentum, etc.
│     │
│     ├─ candles.py ⭐⭐⭐⭐
│     │  ├─ calc_candles_indicators()
│     │  ├─ 80+ паттернов
│     │  └─ Heikin-Ashi, Doji, Hammer, Engulfing, etc.
│     │
│     ├─ overlap.py ⭐⭐⭐
│     │  ├─ calc_overlap_indicators()
│     │  └─ 10+ индикаторов
│     │
│     ├─ statistics.py ⭐⭐⭐⭐
│     │  ├─ calc_statistics_indicators()
│     │  ├─ 20+ метрик
│     │  └─ Rolling stats, median, std, variance, skew, etc.
│     │
│     ├─ performance.py ⭐⭐⭐⭐
│     │  ├─ calc_performance_indicators()
│     │  ├─ 15+ метрик
│     │  └─ Returns, volatility, Sharpe, Sortino, drawdown, etc.
│     │
│     ├─ data_cleaner.py ⭐⭐
│     │  └─ Data cleaning utilities
│     │
│     └─ ta_safe.py ⭐⭐⭐⭐
│        └─ Safe wrappers for pandas_ta
│
│
├─ 🛡️ VALIDATION & QUALITY LAYER
│  │
│  ├─ validators.py ⭐⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ validate_ohlcv_data()
│  │  │  ├─ validate_feature_specs_integrity()
│  │  │  ├─ validate_phase_requirements()
│  │  │  └─ validate_specs_list()
│  │  │
│  │  └─ Используется в:
│  │     ├─ core.py
│  │     └─ group_calculation.py
│  │
│  ├─ validation.py ⭐⭐⭐
│  │  └─ Data quality validation
│  │
│  ├─ gate_validation.py ⭐⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  └─ validate_data_gate()
│  │  │
│  │  └─ Используется в:
│  │     ├─ core.py (перед возвратом)
│  │     └─ group_calculation.py (после каждой группы)
│  │
│  ├─ code_validations.py ⭐⭐⭐
│  │  ├─ Классы:
│  │  │  └─ CodeValidator
│  │  │
│  │  ├─ Функции:
│  │  │  ├─ detect_anomalies()
│  │  │  ├─ detect_outliers()
│  │  │  └─ detect_shadow_nan()
│  │  │
│  │  └─ Используется в:
│  │     └─ group_calculation.py
│  │
│  └─ smoke_validation.py ⭐⭐⭐
│     ├─ Production smoke tests
│     └─ Используется в: Airflow DAG
│
│
├─ 📊 METRICS & MONITORING LAYER
│  │
│  ├─ metrics.py ⭐⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ start_calculation_metrics()
│  │  │  ├─ finish_calculation_metrics()
│  │  │  ├─ record_fill_rate()
│  │  │  ├─ record_quality_metrics()
│  │  │  ├─ calculate_fill_rates()
│  │  │  └─ calculate_quality_score()
│  │  │
│  │  └─ Используется в:
│  │     ├─ core.py
│  │     └─ group_calculation.py
│  │
│  ├─ logging_config.py ⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ get_features_logger()
│  │  │  └─ performance_timer() [decorator]
│  │  │
│  │  └─ Используется везде
│  │
│  ├─ indicators_logging.py ⭐⭐⭐
│  │  └─ Indicator-specific logging
│  │
│  └─ error_handling.py ⭐⭐⭐
│     └─ Error handling utilities
│
│
├─ ⚙️ CONFIGURATION & SPECS LAYER
│  │
│  ├─ specs.py ⭐⭐⭐⭐⭐
│  │  ├─ Константы:
│  │  │  ├─ TREND_FEATURES
│  │  │  ├─ OSCILLATOR_FEATURES
│  │  │  ├─ VOLATILITY_FEATURES
│  │  │  ├─ VOLUME_FEATURES
│  │  │  ├─ MA_FEATURES
│  │  │  ├─ CANDLES_FEATURES
│  │  │  ├─ SQUEEZE_FEATURES
│  │  │  ├─ OVERLAP_FEATURES
│  │  │  ├─ STATISTICS_FEATURES
│  │  │  ├─ PERFORMANCE_FEATURES
│  │  │  └─ FEATURE_SPECS (500+ спецификаций)
│  │  │
│  │  └─ Используется в:
│  │     ├─ core.py
│  │     └─ indicator_groups/*
│  │
│  ├─ models.py ⭐⭐⭐⭐⭐
│  │  ├─ Классы:
│  │  │  ├─ FeatureSpec
│  │  │  ├─ FeatureResult
│  │  │  ├─ FeatureCalculationConfig
│  │  │  ├─ FeatureValidationResult
│  │  │  ├─ FeatureError
│  │  │  ├─ FeatureValidationError
│  │  │  └─ FeatureCalculationError
│  │  │
│  │  └─ Используется везде
│  │
│  ├─ config.py ⭐⭐⭐⭐
│  │  ├─ Классы:
│  │  │  └─ StreamingConfig
│  │  │
│  │  ├─ Функции:
│  │  │  └─ create_streaming_config()
│  │  │
│  │  └─ Используется в:
│  │     └─ calc.py
│  │
│  ├─ name_mapping.py ⭐⭐⭐
│  │  └─ Indicator name mapping
│  │
│  └─ versioning.py ⭐⭐
│     └─ Version management
│
│
├─ 🔧 UTILITIES LAYER
│  │
│  ├─ utils.py ⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ volatility_normalize_features()
│  │  │  ├─ normalize_by_rolling_volatility()
│  │  │  └─ calculate_rolling_volatility()
│  │  │
│  │  └─ Используется в:
│  │     └─ core.py (optional normalization)
│  │
│  ├─ time_utils.py ⭐⭐⭐⭐⭐
│  │  ├─ Функции:
│  │  │  ├─ ensure_ts_column()
│  │  │  ├─ validate_timestamp_consistency()
│  │  │  ├─ strict_timestamp_validation()
│  │  │  └─ parse_timestamp()
│  │  │
│  │  └─ Используется в:
│  │     ├─ core.py
│  │     └─ group_calculation.py
│  │
│  ├─ utils/
│  │  └─ memlog.py ⭐⭐⭐
│  │     ├─ Функции:
│  │     │  ├─ memory_monitor() [decorator]
│  │     │  ├─ log_dataframe_info()
│  │     │  └─ force_cleanup()
│  │     │
│  │     └─ Используется в:
│  │        └─ calc.py
│  │
│  ├─ upsert_optimizer.py ⭐⭐⭐
│  │  ├─ Классы:
│  │  │  ├─ UpsertConfig
│  │  │  └─ UpsertOptimizer
│  │  │
│  │  └─ Используется в:
│  │     └─ group_calculation.py
│  │
│  ├─ save.py ⭐⭐⭐
│  │  └─ Save to parquet files
│  │
│  ├─ ta_safe.py ⭐⭐⭐⭐
│  │  └─ Safe pandas_ta wrappers
│  │
│  ├─ indicator_utils.py ⭐⭐
│  │  └─ Misc indicator utilities
│  │
│  └─ strategy.py ⭐⭐⭐
│     ├─ Функции:
│     │  └─ get_max_lookback_for_strategies()
│     │
│     └─ Используется в:
│        └─ calc.py
│
│
├─ 🗄️ SCHEMA LAYER
│  │
│  └─ schema/
│     ├─ indicators_schema.yml
│     ├─ indicators_schema_clean.yml
│     ├─ indicators_schema_complete.yml
│     └─ schema_manager.py ⭐⭐
│
│
├─ 🛠️ TOOLING LAYER
│  │
│  ├─ cli/
│  │  ├─ check_database_setup.py
│  │  └─ schema_check.py
│  │
│  ├─ audit_cli.py ⭐⭐
│  ├─ audit_simple.py ⭐⭐
│  ├─ database_indexes.py ⭐⭐
│  └─ calc_combinations.py ⭐⭐
│
│
└─ 🧪 TESTING LAYER
   │
   └─ tests/
      ├─ test_core.py ⭐⭐⭐⭐⭐
      ├─ test_integration.py ⭐⭐⭐⭐
      ├─ test_database_integration.py ⭐⭐⭐⭐
      ├─ test_memory_optimization.py ⭐⭐⭐⭐
      ├─ test_streaming_equivalence.py ⭐⭐⭐⭐
      ├─ test_production_readiness.py ⭐⭐⭐⭐
      ├─ test_comprehensive.py ⭐⭐⭐
      └─ ... (20+ test files)
```

**Легенда:**
- ⭐⭐⭐⭐⭐ - Критический компонент (core functionality)
- ⭐⭐⭐⭐ - Важный компонент (key functionality)
- ⭐⭐⭐ - Стандартный компонент (standard functionality)
- ⭐⭐ - Вспомогательный компонент (support functionality)

---

## 🔗 Граф зависимостей (Dependency Graph)

### Критический путь (Critical Path)

```
USER CODE
    │
    ↓
core.py ─────────────────────┐
    │                        │
    ├─► validators.py        │
    │   └─► models.py         │
    │                        │
    ├─► specs.py ────────────┤
    │   └─► models.py         │
    │                        │
    ├─► time_utils.py        │
    │                        │
    ├─► group_calculation.py ┤
    │   │                    │
    │   ├─► metrics.py       │
    │   ├─► gate_validation  │
    │   ├─► upsert_optimizer │
    │   └─► indicator_groups/┼─┐
    │       ├─► ma.py         │ │
    │       ├─► oscillators   │ │
    │       ├─► volatility    │ │
    │       ├─► volume        │ │
    │       ├─► trend         │ │
    │       ├─► squeeze       │ │
    │       ├─► candles       │ │
    │       ├─► overlap       │ │
    │       ├─► statistics    │ │
    │       └─► performance   │ │
    │                        │ │
    ├─► gate_validation.py ◄─┘ │
    │                          │
    └─► metrics.py ◄───────────┘
```

### Инфраструктурный путь (Infrastructure Path)

```
calc_indicators.py (Airflow Entry)
    │
    ├─► application/batch_processor.py
    │       │
    │       ├─► domain/calculator.py
    │       │       │
    │       │       └─► core.py
    │       │
    │       └─► infrastructure/database.py
    │               │
    │               ├─► db_operations.py
    │               │   ├─► fetch_latest_ts()
    │               │   └─► fetch_ohlcv_df()
    │               │
    │               └─► insert_indicators.py
    │                   └─► upsert_builder.py
    │
    └─► smoke_validation.py
```

---

## 🎯 Точки расширения (Extension Points)

### Для добавления нового индикатора

```
1. specs.py
   └─► Добавить FeatureSpec в соответствующую группу
       (TREND_FEATURES, OSCILLATOR_FEATURES, etc.)

2. indicator_groups/<group>.py
   └─► Добавить расчет в calc_<group>_indicators()
       - Проверить available_cols
       - Вычислить индикатор
       - Обработать ошибки
       - Вернуть результат

3. tests/test_<group>.py
   └─► Добавить тест для нового индикатора
```

### Для добавления новой группы индикаторов

```
1. indicator_groups/new_group.py
   └─► Создать calc_new_group_indicators()

2. specs.py
   └─► Добавить NEW_GROUP_FEATURES

3. group_calculation.py
   └─► Добавить 'new_group' в calculation_order

4. core.py
   └─► Импортировать calc_new_group_indicators

5. tests/test_new_group.py
   └─► Создать тесты
```

### Для добавления нового слоя валидации

```
1. validators.py или validation.py
   └─► Добавить validate_<something>()

2. core.py или group_calculation.py
   └─► Вызвать в соответствующем месте pipeline

3. tests/test_validators.py
   └─► Добавить тесты
```

---

## 📊 Матрица использования (Usage Matrix)

| Компонент | Используется в | Частота | Критичность |
|-----------|---------------|---------|-------------|
| **core.py** | Everywhere | Постоянно | ⚠️ CRITICAL |
| **specs.py** | core, indicator_groups | Постоянно | ⚠️ CRITICAL |
| **models.py** | Everywhere | Постоянно | ⚠️ CRITICAL |
| **validators.py** | core, group_calc | Каждый расчет | ⚠️ CRITICAL |
| **gate_validation.py** | core, group_calc | Каждый расчет | ⚠️ CRITICAL |
| **metrics.py** | core, group_calc | Каждый расчет | ⚡ HIGH |
| **time_utils.py** | core, group_calc | Каждый расчет | ⚡ HIGH |
| **group_calculation.py** | core | Группов. расчет | ⚡ HIGH |
| **indicator_groups/** | core, group_calc | Каждый расчет | ⚠️ CRITICAL |
| **infrastructure/** | application, calc | БД операции | ⚡ HIGH |
| **calc.py** | Airflow, CLI | Streaming | 📊 MEDIUM |
| **calc_indicators.py** | Airflow | Batch jobs | ⚡ HIGH |
| **utils.py** | core | Optional | 📊 MEDIUM |
| **config.py** | calc | Streaming | 📊 MEDIUM |
| **save.py** | calc | Streaming | 📊 MEDIUM |

**Легенда:**
- ⚠️ CRITICAL - Критичный компонент, сбой блокирует систему
- ⚡ HIGH - Важный компонент, используется часто
- 📊 MEDIUM - Стандартный компонент
- 📝 LOW - Вспомогательный компонент

---

## 🔄 Циклы и рекурсии (Cycles & Recursion)

### ✅ Отсутствие циклических зависимостей

Модуль спроектирован без циклических зависимостей благодаря:

1. **Слоистой архитектуре** - зависимости только "вниз"
2. **Dependency Inversion** - через protocols.py
3. **Facade patterns** - database.py, calculator.py

### Пример правильного дизайна:

```
core.py ──► domain/calculator.py ──► core.py  ❌ ЦИКЛ!

Решение:
core.py ──► protocols.py ◄──── domain/calculator.py  ✅ OK!
```

---

## 💾 Data Flow через компоненты

### Input → Output Journey

```
1️⃣ RAW OHLCV DATA (User)
   ↓
2️⃣ core.py::compute_features()
   │  Validates with validators.py
   │  Checks specs with specs.py
   │  Ensures timestamps with time_utils.py
   ↓
3️⃣ group_calculation.py::compute_features_grouped()
   │  For each group in order:
   │    ├─ Call indicator_groups/<group>.py
   │    ├─ Collect results
   │    ├─ Validate with gate_validation.py
   │    └─ Record with metrics.py
   ↓
4️⃣ gate_validation.py::validate_data_gate()
   │  Check fill rates
   │  Check NaN ratios
   │  Check consistency
   ↓
5️⃣ Optional: utils.py::volatility_normalize_features()
   ↓
6️⃣ metrics.py::finish_calculation_metrics()
   ↓
7️⃣ RETURN DataFrame with Indicators (to User)
```

### Database Persistence Journey

```
1️⃣ calc_indicators.py (triggered by Airflow)
   ↓
2️⃣ application/batch_processor.py::process_single_pair()
   │  Fetch OHLCV via infrastructure/db_operations.py
   ↓
3️⃣ domain/calculator.py::calculate_batch()
   │  Calls core.py::compute_features()
   ↓
4️⃣ DataFrame with Indicators
   ↓
5️⃣ infrastructure/insert_indicators.py::insert_indicators()
   │  Sanitize NaN/Inf
   │  Build UPSERT via upsert_builder.py
   │  Execute batch insert
   ↓
6️⃣ PostgreSQL Database (app.indicators table)
   ↓
7️⃣ smoke_validation.py::validate_smoke()
   │  Verify data written
   │  Check quality
   ↓
8️⃣ SUCCESS / FAILURE (Airflow Task Result)
```

---

## 🎨 Визуальная карта важности

```
                    КРИТИЧНОСТЬ
                         ↑
                         │
    ⚠️ CRITICAL          │     core.py
                         │     specs.py
                         │     models.py
                         │     validators.py
                         │     indicator_groups/*
                         │
    ⚡ HIGH              │     gate_validation.py
                         │     metrics.py
                         │     time_utils.py
                         │     group_calculation.py
                         │     infrastructure/*
                         │
    📊 MEDIUM            │     calc.py
                         │     config.py
                         │     utils.py
                         │
    📝 LOW               │     audit_*.py
                         │     demo.py
                         │
                         └──────────────────────►
                                        ЧАСТОТА ИСПОЛЬЗОВАНИЯ
```

---

## 🚦 Статусы компонентов

| Компонент | Статус | Примечание |
|-----------|--------|-----------|
| **core.py** | ✅ Stable | Production Ready |
| **specs.py** | ✅ Stable | 500+ indicators |
| **models.py** | ✅ Stable | Well-defined |
| **validators.py** | ✅ Stable | Comprehensive |
| **indicator_groups/** | ✅ Stable | Tested |
| **infrastructure/** | ✅ Stable | Battle-tested |
| **group_calculation.py** | ✅ Stable | Optimized |
| **calc.py** | ✅ Stable | Memory-efficient |
| **registry/** | ⚠️ Deprecated | Use specs.py instead |
| **domain/** | 🚧 New | Clean Architecture layer |
| **application/** | 🚧 New | Clean Architecture layer |

**Легенда:**
- ✅ Stable - Готов к production
- 🚧 New - Новый, но работает
- ⚠️ Deprecated - Устарел, не использовать

---

## 📝 Рекомендации по работе с компонентами

### ⭐ Обязательно используйте:
- `core.py` - для всех расчетов
- `validators.py` - для валидации данных
- `gate_validation.py` - перед записью/возвратом
- `metrics.py` - для отслеживания качества
- `logging_config.py` - для логирования

### ⚠️ Осторожно с:
- `calc.py` - только для очень больших данных
- `utils.py` - volatility normalization опциональна
- Direct database access - используйте infrastructure/

### ❌ Не используйте:
- `registry/*` - deprecated, используйте `specs.py`
- Direct imports from indicator_groups - используйте через `core.py`

---

**Последнее обновление:** 2025-10-27
**Версия:** 1.0.0
**Статус:** ✅ Complete Component Map
