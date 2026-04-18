# PKLPO - Data Flow и логика обработки

**Версия:** 0.4.0 | **Обновлено:** 2026-03-18

---

## Статус документа

Этот файл теперь разделяет три разных уровня описания:

- **As-Is**: что реально существует в текущем репозитории и Airflow DAG-ах.
- **Transition**: известные несовместимости и технический долг, которые влияют на понимание потока данных.
- **Target**: целевой поток из `ARCHITECTURE.md`, который еще не полностью реализован.

Если раздел не помечен отдельно, он описывает **As-Is**.

---

## Содержание

- [Quick Reference](#quick-reference)
- [Текущее состояние (As-Is)](#текущее-состояние-as-is)
- [Контракты по этапам](#контракты-по-этапам)
- [Границы ответственности](#границы-ответственности)
- [Этап 1: Ingest](#этап-1-ingest)
- [Этап 2: Features](#этап-2-features)
- [Timestamp Contract](#timestamp-contract)
- [Временные зависимости и DAGs](#временные-зависимости-и-dags)
- [Known Inconsistencies / Technical Debt](#known-inconsistencies--technical-debt)
- [Целевой поток (Target)](#целевой-поток-target)
- [Дополнительные материалы](#дополнительные-материалы)

---

## Quick Reference

| Хочу понять... | Раздел |
|----------------|--------|
| Как данные идут от OKX до PostgreSQL | [Этап 1: Ingest](#этап-1-ingest) |
| Как сейчас считаются признаки | [Этап 2: Features](#этап-2-features) |
| Какие DAG-и реально есть | [Временные зависимости и DAGs](#временные-зависимости-и-dags) |
| Где сейчас технический долг | [Known Inconsistencies / Technical Debt](#known-inconsistencies--technical-debt) |
| Какой поток целевой | [Целевой поток (Target)](#целевой-поток-target) |

---

## Текущее состояние (As-Is)

### Коротко

На сегодня в репозитории фактически подтвержден следующий рабочий контур:

```text
OKX API
  -> ingest / candles
  -> swap_ohlcv_p
  -> features_calc_short / features CLI
  -> indicators_p
```

Также в кодовой базе присутствуют модули `mtf`, `signals`, `risk`, `positions`, но в текущем Airflow-контуре из корня `ops/airflow/dags/` нет отдельных DAG-ов `mtf_analysis` и `signal_generation`. Поэтому operational data flow в этом документе отделен от целевой схемы.

### As-Is схема

```text
┌─────────┐
│ OKX API │
└────┬────┘
     │
     ▼
┌───────────────┐
│ INGEST        │  DAG: okx_swap_ohlcv_sync_v2
│ candles/meta  │
└────┬──────────┘
     │ UPSERT
     ▼
┌───────────────┐
│ swap_ohlcv_p  │
└────┬──────────┘
     │ read with watermark + warmup
     ▼
┌──────────────────────┐
│ FEATURES             │
│ - features_calc_short│
│ - CLI features       │
└────┬─────────────────┘
     │ UPSERT
     ▼
┌───────────────┐
│ indicators_p  │
└───────────────┘
```

### Что не считается частью текущего operational потока

- `mtf_consensus`, `signals`, `signals_detailed`, `positions` не должны описываться как уже встроенные в текущий Airflow-pipeline из корня репозитория.
- Разделы про MTF / Signals / Risk / Positions допустимы только как **target** или как описание локальной бизнес-логики модулей, но не как подтвержденный текущий runtime path.

---

## Контракты по этапам

| Этап | Input | Output | Source | Target | Timestamp unit | Watermark | Idempotency key | Schedule | Owner |
|------|-------|--------|--------|--------|----------------|-----------|-----------------|----------|-------|
| Ingest | OKX candles, instruments, funding, OI | Нормализованные market rows | OKX REST API | `swap_ohlcv_p` | ms | `MAX(timestamp)` по `symbol,timeframe` | `symbol,timeframe,timestamp` | `okx_swap_ohlcv_sync_v2` = `*/5 * * * *` | `src/candles/`, `ops/airflow/dags/okx_swap_ohlcv_sync_v2.py` |
| Features short | OHLCV window + warmup | Preset features (короткий набор) | `swap_ohlcv_p` | `indicators_p` | input ms, промежуточно есть `ts` в seconds | сравнение `latest_ohlcv_ts` vs `last_feature_ts` | `symbol,timeframe,timestamp` | `features_calc_short` = `*/15 * * * *` | `src/features/application/features_calc_short_service.py` |
| Features full/manual | OHLCV без лимита или по фильтру | Расчет расширенного набора фич | `swap_ohlcv_p` | `indicators_p` | ms | зависит от CLI/limit и query-логики | `symbol,timeframe,timestamp` | `features_calc` = manual only | `src/cli/commands/features.py`, `ops/airflow/dags/features_calc.py` |

### Примечания к контрактам

- Для features используется `INDICATORS_TABLE_NAME`, который в текущем коде равен `indicators_p`.
- Для ingest и features запись должна быть идемпотентной: повторный запуск не должен приводить к дублям.
- Для features critical contract включает `warmup_bars`, чтобы производные индикаторы не считались на обрезанном окне.

---

## Границы ответственности

**Цель:** показать, какой модуль за что отвечает в текущем runtime path, и где заканчивается его зона ответственности.

| Слой | Файл / модуль | Отвечает за | Не отвечает за |
|------|----------------|-------------|----------------|
| Orchestration | `ops/airflow/dags/okx_swap_ohlcv_sync_v2.py` | schedule, task chain, env setup, XCom, retries | бизнес-логику синхронизации свечей |
| Ingest application | `src/candles/application/sync_use_cases.py` | resolve mode, freshness gate, smoke checks, orchestration helpers | прямой SQL UPSERT и HTTP-детали |
| Ingest use cases | `src/candles/application/sync/use_cases.py` | orchestration по символам, retry, статистика | детали протокола OKX, DAG wiring |
| Ingest persistence | `src/candles/repository.py` | UPSERT в `swap_ohlcv_p`, чтение timestamps | решение, какие таймфреймы запускать |
| Instruments/meta | `src/candles/load_instruments.py` | загрузка инструментов, mark-not-live, refresh cache | Airflow schedule |
| Features orchestration | `ops/airflow/dags/features_calc_short.py` | scheduled short-features pipeline | формулы индикаторов |
| Features application | `src/features/application/features_calc_short_service.py` | freshness gate, чтение окна, запуск `compute_features`, сохранение батча | schema migration, Airflow wiring |
| Features core | `src/features/core/calculation.py` | вычисление признаков без orchestration | выбор symbols/timeframes, сохранение в БД |
| Features schema | `src/features/schema/schema_manager.py` | schema registry, validation, sync columns для target indicators table | расчет признаков |
| Full features manual path | `ops/airflow/dags/features_calc.py`, `src/cli/commands/features.py` | full/manual расчет по всем символам и ТФ | scheduled short preset path |

### Ограничение этого раздела

Этот ownership map покрывает **ingest + features**, потому что именно этот контур подтвержден текущими DAG-ами. Для MTF / Signals / Risk / Positions см. `ARCHITECTURE.md` и раздел Target ниже.

---

## Этап 1: Ingest

**Цель:** забрать OHLCV свечи и связанные market meta данные с OKX и сохранить их в `swap_ohlcv_p`.

### Источники данных

| Источник | Endpoint | Данные | Использование |
|----------|----------|--------|---------------|
| OKX Candles | `/api/v5/market/candles` | OHLCV | основной ingest |
| OKX Instruments | `/api/v5/public/instruments` | instrument metadata | refresh справочника |
| OKX Funding | `/api/v5/public/funding-rate` | funding rate | только в режимах `ext` / `bootstrap` |
| OKX OI | `/api/v5/public/open-interest` | open interest | только в режимах `ext` / `bootstrap` |

### Режимы синхронизации

| Режим | Таймфреймы | Concurrency | Ext данные |
|-------|------------|-------------|-----------|
| `fast` | `1m`, `5m` | 10 symbols | нет |
| `slow` | `15m`, `30m`, `1H`, `4H`, `12H`, `1D`, `1W`, `1M` | 2 symbols | нет |
| `ext` | `1m`, `5m` | 5 symbols | funding_rate, OI |
| `bootstrap` | все ТФ | 1 symbol | funding_rate, OI |

### Логика выбора режима

```text
Manual run + dag_run.conf.mode -> использовать явно заданный mode

Scheduled run:
  minute in (0, 15, 30, 45) -> slow
  иначе                     -> fast
```

### Freshness gate

```text
Перед запуском sync:
  fast mode -> skip если лаг по 1m < 120s
  slow mode -> skip если лаг по 15m < 900s

Manual run -> gate обходится
```

### Instrument cache

```text
Кэш инструментов: 24 часа
Принудительное обновление: refresh_instruments=true в dag_run.conf
```

### Реальная DAG chain

```text
refresh_okx_meta -> swap_sync -> validate_swap_sync_xcom -> smoke_validate -> quality_pipeline
```

| Task | Что делает |
|------|-----------|
| `refresh_okx_meta` | обновляет справочник инструментов, если кэш устарел |
| `swap_sync` | выполняет синхронизацию свечей и возвращает статистику |
| `validate_swap_sync_xcom` | проверяет структуру XCom payload |
| `smoke_validate` | проверяет наличие записей и fill-rate |
| `quality_pipeline` | запускает post-check quality pipeline |

### Псевдокод потока

```python
async def sync_candles(symbol: str, timeframe: str) -> int:
    last_ts = await db.get_last_timestamp(symbol, timeframe)
    candles = await okx.get_candles(
        symbol=symbol,
        timeframe=timeframe,
        after=last_ts,
        limit=300,
    )
    validated = validate_ohlcv(candles)
    rows = await db.upsert_candles(validated)
    return rows
```

### Базовые инварианты ingest

- `high >= max(open, close)`
- `low <= min(open, close)`
- `volume >= 0`
- `timestamp` должен быть монотонным в пределах серии
- ключ записи: `symbol + timeframe + timestamp`

---

## Этап 2: Features

**Цель:** рассчитать признаки по OHLCV из `swap_ohlcv_p` и сохранить их в `indicators_p`.

### Два разных runtime path

| Path | Назначение | Запуск | Объем |
|------|------------|--------|------|
| `features_calc_short` | регулярный scheduled path | Airflow `*/15` | preset `FEATURES_CALC_SHORT_SPECS` |
| `features_calc` | manual/full path | Airflow manual only | расширенный расчет через CLI |

Это ключевое различие: scheduled path сейчас не равен полному расчету 500+ фич на каждом цикле.

### As-Is поток features

```text
swap_ohlcv_p
  -> check_has_new_ohlcv()
  -> get_ohlcv_window(last_feature_ts, warmup_bars=500)
  -> compute_features(...)
  -> save_batch(...)
  -> indicators_p
```

### Watermark и warmup

```text
1. Получить последний рассчитанный timestamp из indicators_p
2. Проверить, появились ли новые OHLCV в swap_ohlcv_p
3. Если появились:
   - загрузить окно OHLCV с warmup_bars до watermark
   - пересчитать признаки
   - сделать UPSERT только по целевым timestamp
```

### Порядок расчета

```text
1. Base indicators
   - EMA / SMA
   - ATR
   - volume-based calculations

2. Derived indicators
   - MACD
   - Bollinger Bands
   - RSI

3. Complex indicators
   - ADX
   - squeeze / composite logic

4. Validation + save
   - schema validation
   - batched UPSERT
```

### Schema management

`SchemaManager` является единым источником правды для колонок **целевой таблицы признаков**, имя которой берется из `INDICATORS_TABLE_NAME`.

| Метод | Что делает |
|-------|-----------|
| `_load_schema()` | читает YAML-реестр колонок и типов |
| `sync_database_schema(session)` | синхронизирует БД со schema registry |
| `validate_data(records)` | проверяет payload перед сохранением |
| `resolve_alias(name)` | нормализует альтернативные имена колонок |

### Quality gates

Для features важно различать два слоя проверок:

- **Внутренние checks**: NaN ratio, диапазоны значений, warmup behavior.
- **Внешние post-checks**: отдельный validate шаг в `features_calc_short`, плюс reuse `quality_pipeline` из candles application.

### Operational caveat

Нельзя описывать текущий scheduled features path как "500+ индикаторов каждые 5 минут". Это неверно по двум причинам:

- scheduled DAG для features сейчас `features_calc_short`, а не `features_calc`;
- `features_calc_short` работает по preset-списку, а не по полному набору фич.

---

## Timestamp Contract

Это обязательный operational contract для чтения и записи данных.

| Место | Формат | Комментарий |
|------|--------|-------------|
| `swap_ohlcv_p.timestamp` | milliseconds (`int`) | основной storage format |
| `indicators_p.timestamp` | milliseconds (`int`) | storage format для features |
| `fetch_ohlcv_df()` / некоторые DataFrame path | `ts` в seconds | transitional internal representation |
| `compute_features()` | ожидает OHLCV DataFrame с корректными time columns | требуется явная нормализация на границе |

### Правило

```text
Storage contract -> milliseconds
Internal DataFrame contract -> должен быть явно нормализован при переходе между слоями
```

### Почему это важно

Если timestamp policy не зафиксирован явно:

- watermark может сравниваться в разных единицах;
- часть признаков будет считаться не на том окне;
- возможны дубли или пропуски при UPSERT.

---

## Временные зависимости и DAGs

### Реально существующие DAG-и в `ops/airflow/dags`

| DAG ID | Schedule | Назначение |
|--------|----------|------------|
| `okx_swap_ohlcv_sync_v2` | `*/5 * * * *` | ingest OHLCV и quality checks |
| `features_calc_short` | `*/15 * * * *` | scheduled short-features pipeline |
| `features_calc` | `None` | manual/full recalculation path |
| `indicators_partition_maintenance` | отдельный maintenance DAG | обслуживание партиций `indicators_p` |
| `market_selection` | существует отдельно | вне основного ingest->features контекста |

### As-Is порядок зависимостей

```text
Airflow не задает жесткую cross-DAG зависимость вида:
okx_swap_ohlcv_sync_v2 -> features_calc_short -> mtf_analysis -> signal_generation

Подтверждено только:
1. ingest DAG регулярно обновляет swap_ohlcv_p
2. features_calc_short отдельно и регулярно читает swap_ohlcv_p
3. features_calc manual path запускается вручную
```

### Что было удалено из operational описания

Следующие сущности не должны фигурировать как реально существующие DAG-и текущего pipeline:

- `mtf_analysis`
- `signal_generation`

Если нужно описывать их роль, это надо делать в разделе Target.

---

## Known Inconsistencies / Technical Debt

### 1. `ohlcv` vs `swap_ohlcv_p`

- Исторически в кодовой базе есть legacy таблица `ohlcv`.
- Фактический ingest runtime path работает через `swap_ohlcv_p`.
- Документация должна считать `swap_ohlcv_p` текущим operational source of truth для market candles.

### 2. `indicators` vs `indicators_p`

- В `ARCHITECTURE.md` есть расхождение между разными разделами.
- Текущий код указывает на `INDICATORS_TABLE_NAME = "indicators_p"`.
- Пока это не унифицировано во всех docs, `DATA_FLOW.md` должен явно помечать это как transitional inconsistency.

### 3. Scheduled features path не равен full features path

- `features_calc_short` считает preset-набор.
- `features_calc` manual DAG и CLI могут считать более широкий набор.
- Нельзя смешивать эти два сценария в одной operational схеме.

### 4. Timestamp mismatch не оформлен как жесткий контракт

- storage использует milliseconds;
- часть feature-loading path работает с `ts` в seconds;
- это должно быть явно защищено assertion/validation на границе.

### 5. Воспроизводимость расчетов пока неполная

В архитектурной цели заявлены:

- `run_id`
- `algo_version`
- `params_hash`
- `snapshot_id`

Но как единый обязательный metadata contract для каждого feature/signal calculation это еще не оформлено в текущем runtime path.

### 6. MTF / Signals / Risk / Positions не встроены в текущий корневой Airflow pipeline

Эти блоки есть в проекте как модули и архитектурные направления, но operational doc не должен представлять их как уже связанный production-like DAG chain.

---

## Целевой поток (Target)

Ниже не текущее состояние, а целевая схема, согласованная с `ARCHITECTURE.md`.

```text
market_data
  -> features
  -> mtf_context / triggers / consensus
  -> signals
  -> risk
  -> execution
  -> positions
```

### Целевая схема

```text
┌─────────────┐
│ market_data │
└────┬────────┘
     ▼
┌─────────────┐
│  features   │
└────┬────────┘
     ▼
┌─────────────┐
│ mtf_context │
└────┬────────┘
     ▼
┌─────────────┐
│   signals   │
└────┬────────┘
     ▼
┌─────────────┐
│    risk     │
└────┬────────┘
     ▼
┌─────────────┐
│ execution   │
└────┬────────┘
     ▼
┌─────────────┐
│  positions  │
└─────────────┘
```

### Что должно быть выполнено, чтобы перейти от As-Is к Target

- унифицировать `swap_ohlcv_p` и `indicators_p` как source-of-truth во всех docs и моделях;
- зафиксировать timestamp contract на уровне port/API;
- отделить scheduled short features path от full backfill/manual path;
- формализовать cross-context ports между `features`, `mtf`, `signals`, `risk`;
- только после этого описывать end-to-end chain как operational reality.

---

## Дополнительные материалы

- [Architecture Overview](./ARCHITECTURE.md)
- [Planning Notes](./docs/planning/data_flow.md)
- [Features Module](./src/features/README.md)
- [MTF System](./src/mtf/README_FINAL.md)
- [Positions Module](./src/positions/README.md)

---

**Последнее обновление:** 2026-03-18
