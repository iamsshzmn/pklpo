# Features Module

Практическая документация по модулю `src/features`.

Назначение файла:

- показать текущий рабочий путь данных для `features`
- зафиксировать контракты, которые нельзя ломать
- дать команды для запуска, проверки и диагностики
- показать, где искать код по слоям

См. также:

- `D:\projects\pklpo\ENGINEERING_GUIDE.md`
- `D:\projects\pklpo\DATA_FLOW.md`
- `D:\projects\pklpo\ARCHITECTURE_GUIDE.md`
- `D:\projects\pklpo\ARCHITECTURE.md`

---

## 1. Scope

Модуль `features` отвечает за:

- расчёт индикаторов по OHLCV
- валидацию входных и выходных данных
- сохранение результатов в `indicators_p`
- short-run расчёт через preset `features_calc_short`
- синхронизацию схемы индикаторов с декларативным реестром

Модуль `features` не отвечает за:

- ingest OHLCV с биржи
- orchestration Airflow вне своих DAG/use case entrypoints
- downstream-логику `mtf_context`, `signals`, `risk`, `positions`

---

## 2. Current Runtime Path

Текущий operational path для features:

```text
swap_ohlcv_p
  -> features application / CLI
  -> compute_features(...)
  -> save_batch(...) / save_parquet_to_pg(...)
  -> indicators_p
```

Для scheduled short-path используется:

```text
swap_ohlcv_p
  -> application/features_calc_short_service.py
  -> presets/features_calc_short_v1.py
  -> indicators_p
```

Источник правды по общему data flow:

- `D:\projects\pklpo\DATA_FLOW.md`

---

## 3. Storage Contracts

### 3.1 Source table

Текущий источник OHLCV для features:

- `swap_ohlcv_p`

Не опирайся на legacy `ohlcv` как на основной runtime source.

### 3.2 Target table

Текущая таблица записи:

- `indicators_p`

### 3.3 Identity key

Запись индикаторов должна оставаться идемпотентной по ключу:

```text
(symbol, timeframe, timestamp)
```

### 3.4 Canonical storage metadata

Канонический контракт хранения находится в:

- `src/features/storage_contract.py`

Важные поля контракта:

- `table_name = "indicators_p"`
- `identity_fields = ("symbol", "timeframe", "timestamp")`
- `service_fields = ("symbol", "timeframe", "timestamp", "calculated_at")`

### 3.5 Timestamp contract

Не менять без явной миграции и проверки всех call sites:

- storage contract использует `timestamp` в `milliseconds`
- часть внутренних DataFrame path всё ещё использует `ts`
- на границе чтения/сохранения timestamp должен быть явно нормализован

Если работаешь с чтением из БД, сохранением parquet или watermark-логикой, сначала проверь:

- `D:\projects\pklpo\DATA_FLOW.md` -> `Timestamp Contract`

---

## 4. Input Contract

Для расчёта индикаторов DataFrame должен содержать:

- `open`
- `high`
- `low`
- `close`
- `volume`

Для большинства save path также нужен один из временных столбцов:

- `ts`
- `timestamp`

Минимальные ожидания:

- DataFrame не пустой
- обязательные OHLCV-колонки существуют
- обязательные OHLCV-колонки не состоят целиком из `NaN`

Код:

- `src/features/application/feature_service.py`
- `src/features/validation/data_validator.py`
- `src/features/validation/feature_validator.py`

---

## 5. Output Contract

Результат расчёта:

- pandas DataFrame
- исходные OHLCV-поля сохраняются
- добавляются рассчитанные feature columns

Перед сохранением persistence path ожидает:

- `symbol`
- `timeframe`
- `timestamp`
- feature columns, допустимые схемой `indicators_p`

Код:

- `src/features/application/save.py`
- `src/features/infrastructure/persistence/repository.py`
- `src/features/infrastructure/persistence/inserter.py`
- `src/features/infrastructure/upsert_builder.py`

---

## 6. Module Layout

```text
src/features/
├── __init__.py
├── __main__.py
├── bootstrap.py
├── container.py
├── storage_contract.py
├── application/
├── cli/
├── config/
├── core/
├── domain/
├── indicator_groups/
├── infrastructure/
├── observability/
├── ports/
├── presets/
├── schema/
├── specs/
├── ta_safe/
├── utils/
└── validation/
```

### 6.1 `core/`

Используй для чистого расчёта.

Основные файлы:

- `src/features/core/calculation.py`
- `src/features/core/dependency_graph.py`
- `src/features/core/group_calculation.py`
- `src/features/core/merging.py`
- `src/features/core/normalization.py`

Главная функция:

- `src.features.core.compute_features`

### 6.2 `application/`

Используй для orchestration use cases.

Основные файлы:

- `src/features/application/feature_service.py`
- `src/features/application/save.py`
- `src/features/application/features_calc_short_service.py`
- `src/features/application/backfill.py`
- `src/features/application/sync_indicator_schema.py`

### 6.3 `ports/`

Если меняешь взаимодействие application <-> infrastructure, сначала смотри порты:

- `src/features/ports/persistence.py`
- `src/features/ports/save.py`
- `src/features/ports/storage.py`

Ключевые протоколы:

- `IndicatorRepository`
- `FeatureSaveValidator`
- `FeatureSaveObserver`
- `FeatureStorageGateway`
- `FeatureSaveDependenciesFactory`

### 6.4 `infrastructure/`

Здесь находятся concrete adapters:

- чтение из БД
- schema-aware save
- UPSERT helpers
- schema synchronizer

Основные файлы:

- `src/features/infrastructure/db_operations.py`
- `src/features/infrastructure/indicator_schema_synchronizer.py`
- `src/features/infrastructure/persistence/repository.py`
- `src/features/infrastructure/persistence/inserter.py`

### 6.5 `schema/`

Используй для registry/sync схемы индикаторов.

Основные файлы:

- `src/features/schema/schema_manager.py`
- `src/features/schema/indicators_schema.yml`
- `src/features/schema/indicators_schema_clean.yml`
- `src/features/schema/indicators_schema_complete.yml`

### 6.6 `specs/`

Декларативный реестр индикаторов.

Точка входа:

- `src/features/specs/__init__.py`

Основные exports:

- `FEATURE_SPECS`
- `FEATURE_GROUPS`

Текущее количество:

- `177` индикаторов

### 6.7 `presets/`

Short-run preset:

- `src/features/presets/features_calc_short_v1.py`

Текущий preset `FEATURES_CALC_SHORT_SPECS`:

- используется в scheduled short path
- содержит `24` индикатора

---

## 7. Dependency Rules

Следовать общим правилам проекта:

- `domain` не должен зависеть от `infrastructure`
- `application` не должен зависеть от concrete DB/SQL деталей
- concrete persistence wiring должен идти через `bootstrap.py`
- новые cross-layer зависимости должны идти через `ports`

Практическое правило для изменений:

- меняешь orchestration -> начинай с `application/`
- меняешь контракт взаимодействия -> сначала `ports/`
- меняешь конкретную реализацию сохранения/чтения -> `infrastructure/`
- меняешь формулы/реестр индикаторов -> `core/`, `indicator_groups/`, `specs/`

---

## 8. Main Entry Points

### 8.1 Pure calculation

```python
from src.features import compute_features

df_features = compute_features(
    df_ohlcv,
    specs=["ema_21", "rsi_14", "macd"],
    volatility_normalize=False,
)
```

### 8.2 Service API

```python
from src.features.application.feature_service import create_feature_service

service = create_feature_service()
df_features = service.calculate(df_ohlcv, specs=["ema_21", "rsi_14"])
```

### 8.3 Save wiring

```python
from src.features.bootstrap import create_feature_save_dependencies

save_deps = create_feature_save_dependencies(session)
```

### 8.4 Schema sync

```python
from src.features.application.sync_indicator_schema import SyncIndicatorSchemaUseCase
from src.features.infrastructure.indicator_schema_synchronizer import IndicatorSchemaSynchronizer

use_case = SyncIndicatorSchemaUseCase(IndicatorSchemaSynchronizer())
result = await use_case.execute(session)
```

---

## 9. CLI

### 9.1 Local features CLI

Команды:

```bash
python -m src.features calculate input.csv output.parquet --symbol BTC-USDT-SWAP --timeframe 1H
python -m src.features save output.parquet --symbol BTC-USDT-SWAP --timeframe 1H
python -m src.features validate output.parquet --data-type features
python -m src.features test-parquet output.parquet
python -m src.features test-database
python -m src.features pipeline input.csv output.parquet --symbol BTC-USDT-SWAP --timeframe 1H
python -m src.features snapshots-list
python -m src.features snapshots-show <snapshot_id>
```

### 9.2 Main project CLI

```bash
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m 5m 15m
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1H --normalize
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1D --limit 1000
```

Важно:

- `python -m src.features` умеет перенаправлять вызов в `src.cli.commands.features`
- scheduled short path и full/manual path не одно и то же

---

## 10. Validation Rules

### 10.1 Gate validation

По умолчанию `GateValidator` использует:

- `min_rows = 20`
- `min_fill_rate = 0.5`
- `max_nan_ratio = 0.1`
- `max_outlier_ratio = 0.05`

Код:

- `src/features/validation/gate_validator.py`

### 10.2 Pre-save validation

Перед save orchestration проверяется:

- пустой ли DataFrame
- есть ли `ts`
- есть ли feature columns
- отсутствуют ли критичные признаки `hlc3`, `ema_8`, `sma_20`

Код:

- `src/features/application/save_validation.py`

### 10.3 Что не ломать

Если меняешь validation/save path, проверь:

- что пустой DataFrame не уходит в persistence
- что `NaN`/`Inf` корректно нормализуются для БД
- что schema filtering не выкидывает нужные колонки
- что idempotent key остаётся `(symbol, timeframe, timestamp)`

---

## 11. Save Path

Текущий save path:

```text
application.save
  -> observer.observe(...)
  -> validator.validate_save_dataframe(...)
  -> repository.save_batch_from_df(...)
  -> commit / rollback
```

Где смотреть:

- `src/features/application/save.py`
- `src/features/application/save_observer.py`
- `src/features/application/save_validation.py`
- `src/features/infrastructure/persistence/repository.py`

Порядок изменений:

1. Сначала проверь, меняется ли контракт порта.
2. Если да, сначала обнови `ports/`.
3. Потом обнови `application/`.
4. Только потом меняй `infrastructure/`.

---

## 12. Short Path vs Full Path

Не смешивать эти сценарии в документации и коде:

### 12.1 `features_calc_short`

Используется для scheduled path.

Особенности:

- читает `swap_ohlcv_p`
- сравнивает latest OHLCV с последним feature timestamp
- берёт окно с `warmup_bars=500`
- считает только `FEATURES_CALC_SHORT_SPECS`
- сохраняет в `indicators_p`

Код:

- `src/features/application/features_calc_short_service.py`
- `src/features/presets/features_calc_short_v1.py`

### 12.2 Full/manual path

Используется для CLI/manual перерасчёта.

Код:

- `src/cli/commands/features.py`
- `ops/airflow/dags/features_calc.py`

---

## 13. Schema Sync

Если меняешь набор индикаторов или имена колонок:

1. Обнови `specs/` или `schema/*.yml`.
2. Проверь alias/name normalization.
3. Проверь schema manager.
4. Проверь synchronizer/use case.
5. После этого проверь persistence path.

Основные файлы:

- `src/features/schema/schema_manager.py`
- `src/features/domain/indicator_schema_registry.py`
- `src/features/infrastructure/indicator_schema_synchronizer.py`
- `src/features/application/sync_indicator_schema.py`

---

## 14. Observability

Логирование и метрики не должны попадать в доменную логику.

Использовать:

- `src.logging` для нового кода
- `src/features/observability/*` для feature-specific metrics/traceability

Основные файлы:

- `src/features/observability/metrics.py`
- `src/features/observability/traceability.py`
- `src/features/observability/error_handling.py`

Основные env:

- `FEATURES_LOG_VERBOSITY`
- `FEATURES_LOG_FORMAT`
- `FEATURES_LOG_CATEGORIES`

---

## 15. Commands for Checks

### 15.1 Быстрые проверки

```bash
python -m src.features test-database
python -m src.features test-parquet output.parquet
```

### 15.2 Проверка реестра индикаторов

```bash
@'
from src.features.specs import FEATURE_SPECS
print(len(FEATURE_SPECS))
print("rsi_14" in FEATURE_SPECS)
'@ | python -
```

### 15.3 Тесты

```bash
pytest tests/features/tests/test_core.py -v
pytest tests/features/tests/test_validators.py -v
pytest tests/features/tests/test_database_integration.py -v
pytest tests/features/tests/test_metrics.py -v
```

Если меняешь imports, contracts или layering, дополнительно сверяйся с:

- `D:\projects\pklpo\ENGINEERING_GUIDE.md`
- `D:\projects\pklpo\ARCHITECTURE_GUIDE.md`

---

## 16. Common Change Scenarios

### Добавить новый индикатор

1. Добавь spec в `src/features/specs/`.
2. Добавь реализацию в нужную группу `src/features/indicator_groups/`.
3. Проверь dependency graph и group calculation path.
4. При необходимости обнови schema files.
5. Проверь save path.
6. Добавь/обнови тесты.

### Изменить сохранение в БД

1. Проверь `storage_contract.py`.
2. Проверь `ports/persistence.py`.
3. Проверь `application/save.py`.
4. Проверь `infrastructure/persistence/*`.
5. Проверь idempotency key и timestamp normalization.

### Изменить short scheduled path

1. Проверь `features_calc_short_service.py`.
2. Проверь preset `features_calc_short_v1.py`.
3. Проверь freshness gate / watermark behavior.
4. Проверь, что scheduled path не начинает использовать full/manual assumptions.

---

## 17. File Map

Если нужно быстро найти точку изменения:

| Что нужно изменить | Куда смотреть |
|--------------------|---------------|
| Формулы индикаторов | `src/features/indicator_groups/`, `src/features/core/` |
| Реестр индикаторов | `src/features/specs/` |
| Чистый API расчёта | `src/features/core/calculation.py`, `src/features/__init__.py` |
| Save orchestration | `src/features/application/save.py` |
| Save validator | `src/features/application/save_validation.py` |
| DB repository | `src/features/infrastructure/persistence/repository.py` |
| UPSERT/sanitize/schema filtering | `src/features/infrastructure/upsert_builder.py`, `src/features/infrastructure/persistence/` |
| Short scheduled path | `src/features/application/features_calc_short_service.py` |
| Schema sync | `src/features/application/sync_indicator_schema.py`, `src/features/schema/`, `src/features/infrastructure/indicator_schema_synchronizer.py` |
| Layer contracts | `src/features/ports/` |

---

Последнее обновление: `2026-03-18`
