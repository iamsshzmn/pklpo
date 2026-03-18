# Market Selection Module

**Версия:** 1.0.0 | **Статус:** Production Ready

Модуль автоматического выбора торгового universe (top-N символов) на основе качества данных, метрик пары, глобального режима рынка и multi-timeframe scoring.

---

## 1. Purpose

Выбор актуального торгового universe для downstream pipeline (полный расчёт фич, сигналы, позиции) с гарантиями:

- **No look-ahead bias** — `ts_eval` привязан к последнему закрытому бару
- **Idempotency** — повторный запуск с теми же данными даёт идентичный результат; UPSERT по составным ключам
- **Fallback safety** — при любом сбое universe не становится пустым; всегда возвращается предыдущая версия
- **Write-lock** — конкурентная безопасность через PostgreSQL advisory lock
- **Reproducibility** — `config_hash` записывается во все таблицы, позволяет точно воспроизвести запуск

**Ключевые возможности:**

- Multi-timeframe scoring по 4 TF (5m, 15m, 1H, 4H)
- Глобальный режим рынка (TREND_UP / TREND_DOWN / RANGE / VOLATILE) влияет на веса метрик
- Quality gate с per-TF порогами + systemic outage detection
- Hysteresis — стабильные символы удерживаются в universe дольше

---

## 2. Inputs

### 2.1 Источники данных

| Источник | Описание | Формат |
|----------|----------|--------|
| PostgreSQL `indicators_p` | Short feature set для scoring (adx_14, atr_14, ema_21, ema_55, volume и др.) | Partitioned table |
| PostgreSQL `ohlcv_p` | OHLCV данные для basket regime detection | Partitioned table |
| PostgreSQL `market_universe_versions` | Предыдущий universe для hysteresis / fallback | Table |
| `MarketSelectionConfig` | Конфигурация всех порогов, весов и параметров | Python dataclass |

### 2.2 Требования к входным данным

| Параметр | Требование |
|----------|------------|
| `short_feature_set` | Колонки: `adx_14`, `atr_14`, `close`, `ema_21`, `ema_55`, `volume` и др. |
| Минимум баров | ≥ `warmup_min_bars` (default: 280) для eligible символа |
| Таймфреймы | `5m`, `15m`, `1H`, `4H` для scoring; `1H`, `4H`, `1D` для regime |
| Максимальный лаг данных | 15 / 45 / 180 / 720 мин (5m / 15m / 1H / 4H) |

### 2.3 Контекстные параметры (MarketSelectionConfig)

| Параметр | Класс | Описание |
|----------|-------|----------|
| `top_n` | `UniverseConfig` | Целевой размер universe |
| `basket_k` | `RegimeConfig` | Top-K символов для режимной basket |
| `fill_min`, `gap_max` | `QualityConfig` | Пороги quality gate |
| `base_weights` | `ScoringConfig` | Веса 5 метрик |
| `whitelist`, `blacklist` | `UniverseConfig` | Принудительные включение/исключение символов |

---

## 3. Outputs

### 3.1 Sink (куда пишем)

| Таблица | Описание |
|---------|----------|
| `market_scores_tf` | Score по `(symbol, timeframe, ts_eval)` + raw/normalized метрики + quality/regime metadata |
| `market_universe` | Итоговые символы версии с `final_score`, рангом, stability |
| `market_universe_versions` | Версия universe со статусом, статистикой запуска и `config_hash` |
| `market_regime_history` | История глобального режима, `stale`-флаг, корзина символов |

### 3.2 Ключи идемпотентности

| Таблица | Ключ |
|---------|------|
| `market_scores_tf` | `(symbol, timeframe, ts_eval)` |
| `market_universe` | `(ts_version, symbol)` |
| `market_universe_versions` | `ts_version` |
| `market_regime_history` | `ts_eval` |

### 3.3 Статусы universe version

| Статус | Описание |
|--------|----------|
| `building` | Pipeline запущен, запись не завершена |
| `published` | Успешно опубликован |
| `fallback_prev` | Скопирован из предыдущей версии |
| `failed` | Сбой без возможности fallback |

---

## 4. Data Flow

### 4.1 Краткое описание

```
indicators_p / ohlcv_p → Quality Gate → Pair Metrics → Scoring (per-TF) → MTF Aggregation → Universe Selection → UPSERT
```

### 4.2 Детальная схема

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INPUT                                           │
│  indicators_p (short feature set)  +  ohlcv_p (basket regime)               │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STEP 1 — RESOLVE ts_eval                            │
│  MarketSelectionDB.resolve_ts_eval()                                        │
│  • Последний закрытый бар по indicators_p                                   │
│  • Проверка наличия short_feature_set                                       │
│  • При missing > max_missing → SHORT_FEATURE_MISMATCH                      │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STEP 2 — GLOBAL REGIME                              │
│  RegimeClassifier.classify_regime()                                         │
│  • Basket top-K символов по медианному объёму                              │
│  • Классификация per-TF: 1D, 4H, 1H                                        │
│  • Агрегация с весами 1D:0.5 / 4H:0.3 / 1H:0.2                            │
│  • При stale: последний валидный режим из market_regime_history             │
│  • Запись в market_regime_history                                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 3 — PER-TF PROCESSING (×4 TF)                       │
│  Для каждого TF из {5m, 15m, 1H, 4H}:                                      │
│                                                                              │
│  DataQualityGate.evaluate()                                                 │
│  • fill_rate, gap_rate, data_lag, warmup_min_bars, volume_present           │
│  • quality_score = f(fill_rate, gap_rate) как множитель при scoring        │
│        ↓                                                                    │
│  PairMetricsCalculator.calculate_all()                                      │
│  • 5 сырых метрик: vol, trend_q, noise, stability, liq                     │
│        ↓                                                                    │
│  ScoringEngine.normalize_metrics() + calculate_tf_scores()                 │
│  • Нормализация: percentile-rank (или z-score→sigmoid при n<20)            │
│  • Взвешенная сумма с режимными дельтами                                   │
│  • score_tf = score_tf_base × quality_score                                 │
│  • VOLATILE-фильтр: liq_score < volatile_min_liq_score → excluded          │
│        ↓                                                                    │
│  UPSERT → market_scores_tf                                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 4 — SYSTEMIC OUTAGE CHECK                           │
│  Если >30% символов не прошли 1H/4H gate → fallback_prev                   │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 5 — MTF AGGREGATION                                  │
│  ScoringEngine.aggregate_mtf_scores()                                       │
│  • Веса: 4H:0.40 / 1H:0.30 / 15m:0.20 / 5m:0.10                           │
│  • Штрафы за отсутствие TF: ×0.92 (4H), ×0.90 (1H), −0.03 (15m/5m)       │
│  • Исключение символов без обоих 4H и 1H (MISSING_SENIOR_TF)              │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 6 — UNIVERSE SELECTION                               │
│  UniverseManager.select_universe()                                          │
│  • Фильтрация blacklist                                                     │
│  • Primary / buffer разбивка по стабильности (std_7d, история ≥ 7 дней)   │
│  • Top-N из primary                                                         │
│  • Hysteresis: символы из предыдущего universe + buffer (до 10 мест)       │
│  • Whitelist: принудительное включение (при наличии 1H/4H)                 │
│  • Переназначение рангов                                                    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 7 — FALLBACK CHECK                                   │
│  universe_size < soft_min (10) → fallback_prev                             │
│  universe_size < hard_min (5)  → failed                                    │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 8 — PUBLISH (with write-lock)                        │
│  pg_try_advisory_xact_lock (timeout: 10 000 мс)                            │
│  UPSERT → market_universe + market_universe_versions                        │
│  status = 'published'                                                       │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUT                                          │
│  market_scores_tf / market_universe / market_universe_versions              │
│  market_regime_history                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Architecture

#### Layers & Responsibilities

| Слой | Ответственность | Ключевые модули |
|------|-----------------|-----------------|
| **Interfaces** | CLI-команды, DAG entry point | `interfaces/commands.py`, `ops/airflow/dags/market_selection.py` |
| **Application** | Оркестрация pipeline, сборка конфига, шаги | `application/pipeline.py`, `steps.py`, `config_projection.py` |
| **Domain** | Чистая бизнес-логика без внешних зависимостей | `domain/quality_gate.py`, `metrics.py`, `regime.py`, `scoring.py`, `universe.py` |
| **Ports** | Protocol-абстракции для инфраструктуры | `ports/db.py`, `ports/persistence.py`, `ports/monitoring.py` |
| **Infrastructure** | DB-запросы, UPSERT, мониторинг, factory wiring | `infrastructure/database.py`, `persistence.py`, `monitoring.py`, `factory.py` |

#### Dependency Direction Rules

Зависимости направлены **строго внутрь**:

```
Interfaces
    ↓
Application
    ↓
Domain  ←────────────────────  Infrastructure
(stdlib only)                   (через ports/protocols)

Ports — определены в domain-границе, реализованы в infrastructure
```

**Запрещённые зависимости:**

| Нарушение | Почему запрещено |
|-----------|-----------------|
| `domain/` → `config.py` (MarketSelectionConfig) | Domain зависит только от stdlib |
| `domain/` → SQL / БД | Domain не знает о способе хранения |
| `infrastructure/` → `application/` | Infra — только адаптеры, не оркестратор |

#### Invariants

| Инвариант | Описание |
|-----------|----------|
| **No look-ahead bias** | `ts_eval` всегда ≤ последнего закрытого бара |
| **Idempotent writes** | Повторный запуск не меняет результат; UPSERT по составным ключам |
| **Non-empty universe** | При любом сбое возвращается предыдущая версия (`fallback_prev`) |
| **Config reproducibility** | `config_hash` в каждой строке позволяет точно воспроизвести запуск |
| **Concurrent safety** | Только один writer одновременно через PostgreSQL advisory lock |

---

## 5. Dependencies & Triggering

### 5.1 Внешние зависимости

| Компонент | Назначение |
|-----------|------------|
| PostgreSQL 14+ | Все таблицы модуля, advisory locks |
| SQLAlchemy 2.0+ | Async ORM |
| asyncpg | PostgreSQL async driver |
| pandas / numpy | Расчёт метрик и scoring в domain |
| prometheus_client | Опциональные метрики (если установлен) |

### 5.2 Внутренние зависимости

```
src/market_selection/
├── infrastructure/  →  src/database.py (AsyncSession, engine)
├── interfaces/      →  src/market_selection/config.py + infrastructure/factory.py
└── application/     →  domain/* (через ports/protocols, без конкретных классов)
```

### 5.3 Triggering (запуск)

| Способ | Описание | Частота |
|--------|----------|---------|
| **Airflow DAG** `market_selection` | Production scheduling | После завершения `features_calc_short` |
| **CLI** `pklpo market-selection run` | Ручной запуск | Ad-hoc |
| **Python API** `build_market_selection_pipeline()` | Программный вызов | По требованию |

### 5.4 DAG-топология

```
ohlcv_sync  →  features_calc_short  →  market_selection  →  features_calc_full
```

`market_selection` читает `indicators_p` (short set) и публикует universe, который `features_calc_full` использует для отбора символов.

---

## 6. Storage Details

### 6.1 Таблица market_scores_tf

| Параметр | Значение |
|----------|----------|
| **Primary Key** | `(symbol, timeframe, ts_eval)` |
| **Ключевые поля** | `score_tf`, `quality_score`, `fill_rate`, `gap_rate`, `eligible`, `reason_flags` |
| **Метрики** | `vol_score`, `trend_q_score`, `noise_score`, `stability_score`, `liq_score` |

### 6.2 Таблица market_universe

| Параметр | Значение |
|----------|----------|
| **Primary Key** | `(ts_version, symbol)` |
| **Ключевые поля** | `final_score`, `rank`, `best_tf`, `worst_tf`, `score_4h`, `score_1h`, `score_15m`, `score_5m` |
| **Мета** | `reason_flags`, `penalty_applied`, `global_regime_at_time` |

### 6.3 Таблица market_universe_versions

| Параметр | Значение |
|----------|----------|
| **Primary Key** | `ts_version` |
| **Ключевые поля** | `ts_eval`, `status`, `universe_size`, `global_regime`, `global_strength` |
| **Мета** | `execution_time_seconds`, `config_hash`, `created_at` |

### 6.4 UPSERT стратегия

```sql
-- market_scores_tf
INSERT INTO market_scores_tf (symbol, timeframe, ts_eval, score_tf, ...)
VALUES ($1, $2, $3, $4, ...)
ON CONFLICT (symbol, timeframe, ts_eval)
DO UPDATE SET score_tf = EXCLUDED.score_tf, ...;

-- market_universe
INSERT INTO market_universe (ts_version, symbol, final_score, ...)
VALUES ($1, $2, $3, ...)
ON CONFLICT (ts_version, symbol)
DO UPDATE SET final_score = EXCLUDED.final_score, ...;
```

### 6.5 Retention Policy

| Таблица | Retention |
|---------|-----------|
| `market_scores_tf` | 180 дней |
| `market_universe` / `market_universe_versions` | 90 дней |
| `market_regime_history` | Без автоматического удаления |

---

## 7. Data Quality & Failure Modes

### 7.1 Quality Gate Thresholds

| Проверка | 5m | 15m | 1H | 4H |
|----------|----|-----|----|----|
| `fill_rate ≥` | 0.97 | 0.98 | 0.99 | 0.99 |
| `gap_rate ≤` | 0.015 | 0.010 | 0.005 | 0.005 |
| `data_lag_seconds ≤` | 900 | 2 700 | 10 800 | 43 200 |
| `valid_bars ≥ warmup_min_bars` | 280 | 280 | 280 | 280 |
| `volume_present` | да | да | да | да |

`quality_score` (множитель для scoring):
```
quality_score = clamp((fill_rate - fill_min) / (1 - fill_min), 0, 1)
              × clamp(1 - gap_rate / gap_max, 0, 1)
```

### 7.2 ReasonFlag — перечень флагов исключения

| Флаг | Причина |
|------|---------|
| `LOW_FILL` | fill_rate ниже порога |
| `HIGH_GAPS` | gap_rate выше порога |
| `INSUFFICIENT_WARMUP` | мало баров для прогрева |
| `NO_VOLUME` | нет данных об объёме |
| `STALE_DATA` | данные слишком старые |
| `MISSING_METRIC_INPUT` | < 90% баров имеют все ключевые фичи |
| `SHORT_FEATURE_MISMATCH` | отсутствуют ожидаемые колонки |
| `LOW_LIQ_IN_VOLATILE` | недостаточная ликвидность в VOLATILE режиме |
| `MISSING_SENIOR_TF` | нет ни 1H, ни 4H — символ исключён |
| `MISSING_4H_SOFT` | нет 4H — штраф ×0.92 |
| `MISSING_1H_SOFT` | нет 1H — штраф ×0.90 |
| `SHORT_HISTORY` | < 7 дней истории оценок |
| `UNIVERSE_FALLBACK_PREV` | universe взят из предыдущей версии |
| `SYSTEMIC_SENIOR_OUTAGE` | системный отказ старших TF (>30% символов) |

### 7.3 Fallback-триггеры

| Триггер | Действие |
|---------|---------|
| Системный отказ 1H/4H (`> 30%` символов) | `fallback_prev` |
| `universe_size < soft_min (10)` | `fallback_prev` |
| `universe_size < hard_min (5)` | `failed` + fallback |
| Нет final scores | `fallback_prev` |
| Нет предыдущей версии | `failed` |

При `fallback_prev`: предыдущий universe копируется в новую `ts_version`.

### 7.4 Режимы сбоев

| Сбой | Поведение | Recovery |
|------|-----------|----------|
| **DB connection lost** | Ошибка pipeline, статус `failed` | Следующий запуск |
| **Stale regime data** | Берётся последний валидный режим, `stale=True` | Автоматический |
| **Systemic TF outage** | Fallback на предыдущий universe | Автоматический |
| **Advisory lock timeout** | `LockTimeoutError` после 10 000 мс | Следующий запуск |
| **Short feature mismatch** | `SHORT_FEATURE_MISMATCH`, pipeline abort | Требует вмешательства |

---

## 8. Performance Notes

### 8.1 Характеристики

| Этап | Ориентировочное время |
|------|-----------------------|
| Resolve ts_eval | < 1 с |
| Global regime (basket 50 символов) | 2–5 с |
| Per-TF processing (500 символов, 4 TF) | 10–30 с |
| MTF aggregation + universe selection | < 1 с |
| Write-lock + UPSERT | 1–3 с |
| **Итого (500 символов)** | **~15–40 с** |

### 8.2 DB-конфигурация

| Параметр | Значение |
|----------|----------|
| **Advisory lock timeout** | 10 000 мс |
| **Connection pool** | SQLAlchemy default (pool_size=5, max_overflow=10) |
| **Batch UPSERT** | По `(symbol, timeframe, ts_eval)` — один запрос на TF |

### 8.3 Ограничения

- Минимум `warmup_min_bars` (280) для участия символа в scoring
- Режимная basket требует basket_k символов с актуальными данными в ohlcv_p
- Scoring нормализация переключается на z-score→sigmoid при n_eligible < 20

---

## 9. Observability

### 9.1 Логирование

**Уровень:** Application и Infrastructure (domain-слой — без логирования).

| Событие | Level | Что логируется |
|---------|-------|----------------|
| Начало pipeline | INFO | `ts_eval`, конфиг |
| Завершение TF-шага | INFO | `timeframe`, `eligible_count`, `duration` |
| Quality gate fail | INFO | `symbol`, `timeframe`, `reason_flags` |
| Systemic outage | WARNING | `outage_rate`, TF |
| Fallback активирован | WARNING | `trigger`, `prev_ts_version` |
| Universe published | INFO | `universe_size`, `status`, `regime`, `execution_time` |
| Ошибка | ERROR | full traceback |

**Формат:** `%(asctime)s | %(name)s | %(levelname)s | key=value`

### 9.2 Метрики (infrastructure/monitoring.py)

```python
from src.market_selection.infrastructure.monitoring import get_metrics

metrics = get_metrics()
metrics.get_summary()           # total_runs, success_rate, avg_execution_time
metrics.get_recent_history(n)   # последние N запусков
metrics.get_eligible_counts()   # количество eligible символов по TF
metrics.get_regime_distribution()  # распределение режимов
```

**Prometheus-метрики** (опционально, если установлен `prometheus_client`):

| Метрика | Тип | Описание |
|---------|-----|----------|
| `market_selection_universe_size` | Gauge | Текущий размер universe |
| `market_selection_execution_seconds` | Histogram | Время выполнения pipeline |
| `market_selection_errors_total` | Counter | Количество ошибок |

### 9.3 config_hash

SHA-256 (16 hex) канонического JSON конфига. Записывается в `market_universe_versions.config_hash`. Позволяет однозначно воспроизвести запуск или сравнить конфигурации запусков.

---

## 10. Runbook

### 10.1 Запуск pipeline

**CLI:**

```bash
# Запустить pipeline с top-30
pklpo market-selection run --top-n 30

# Dry-run (только вычисления, без записи)
pklpo market-selection run --dry-run

# Применить миграции БД
pklpo market-selection migrate
```

**Airflow:**

```bash
airflow dags trigger market_selection
```

**Python API:**

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_engine
from src.market_selection.config import MarketSelectionConfig
from src.market_selection.infrastructure.factory import build_market_selection_pipeline

engine = get_async_engine()
async with AsyncSession(engine) as session:
    config = MarketSelectionConfig()
    config.universe.top_n = 30
    pipeline = build_market_selection_pipeline(session, config)
    result = await pipeline.run()
    print(result.universe_size, result.status.value, result.global_regime)
```

### 10.2 Проверка результатов

**CLI:**

```bash
# Статус последних версий
pklpo market-selection status

# Текущий universe
pklpo market-selection universe --limit 30 --format table
pklpo market-selection universe --format json

# Текущий режим рынка
pklpo market-selection regime

# История запусков
pklpo market-selection metrics --history 10

# Детальный scoring для символа
pklpo market-selection explain BTCUSDT
```

**SQL проверка:**

```sql
-- Последняя версия universe
SELECT ts_version, ts_eval, status, universe_size, global_regime, execution_time_seconds
FROM market_universe_versions
ORDER BY ts_version DESC
LIMIT 5;

-- Топ-символы текущего universe
SELECT mu.symbol, mu.final_score, mu.rank, mu.best_tf
FROM market_universe mu
JOIN market_universe_versions muv ON mu.ts_version = muv.ts_version
WHERE muv.status IN ('published', 'fallback_prev')
ORDER BY muv.ts_version DESC, mu.rank
LIMIT 30;

-- Распределение eligible символов по TF
SELECT timeframe, COUNT(*) AS total, SUM(eligible::int) AS eligible
FROM market_scores_tf
WHERE ts_eval = (SELECT MAX(ts_eval) FROM market_scores_tf)
GROUP BY timeframe;

-- История режима рынка
SELECT ts_eval, global_regime, global_strength, regime_confidence, basket_size
FROM market_regime_history
ORDER BY ts_eval DESC
LIMIT 10;
```

### 10.3 Диагностика проблем

**Проблема: universe пустой / fallback**

```bash
# 1. Проверить статус
pklpo market-selection status

# 2. Проверить eligible символы
pklpo market-selection metrics --history 5

# 3. Проверить качество данных по TF в БД
# (SQL выше: распределение eligible по TF)

# 4. Детально по символу
pklpo market-selection explain BTCUSDT
```

**Проблема: нет текущего режима**

```bash
# Проверить свежесть данных ohlcv_p для basket
SELECT symbol, MAX(timestamp) as last_ts,
       NOW() - to_timestamp(MAX(timestamp)) as lag
FROM ohlcv_p
WHERE timeframe = '1H'
GROUP BY symbol
ORDER BY lag DESC
LIMIT 10;
```

**Проблема: lock timeout**

Означает, что другой pipeline-процесс держит lock. Подождать завершения или проверить зависший процесс:

```sql
SELECT pid, query, state, wait_event_type, wait_event
FROM pg_stat_activity
WHERE query LIKE '%advisory%';
```

### 10.4 Типичные операции

| Операция | Команда |
|----------|---------|
| Применить миграции | `pklpo market-selection migrate` |
| Запустить pipeline | `pklpo market-selection run --top-n 30` |
| Проверить universe | `pklpo market-selection universe` |
| Проверить режим | `pklpo market-selection regime` |
| Метрики запусков | `pklpo market-selection metrics` |
| Объяснить символ | `pklpo market-selection explain BTCUSDT` |
| Запустить тесты | `pytest tests/market_selection/ -q` |

### 10.5 Environment Variables

| Variable | Default | Описание |
|----------|---------|----------|
| `POSTGRES_USER` | — | DB user |
| `POSTGRES_PASSWORD` | — | DB password |
| `POSTGRES_DB` | — | DB name |
| `DB_HOST` | localhost | DB host |
| `DB_PORT` | 5432 | DB port |

---

## Appendix A: Структура модуля

```
src/market_selection/
├── __init__.py                    # Версия v1.0.0
├── config.py                      # MarketSelectionConfig (entry-point конфиг)
├── application/
│   ├── pipeline.py                # MarketSelectionPipeline — главный оркестратор
│   ├── steps.py                   # Приватные шаги pipeline
│   ├── config_projection.py       # Проекция MarketSelectionConfig → domain-конфиги
│   └── models.py                  # Application-level DTO (PipelineResult и др.)
├── domain/
│   ├── config.py                  # Stdlib-only dataclass-конфиги для domain
│   ├── quality_gate.py            # DataQualityGate, ReasonFlag, QualityResult
│   ├── metrics.py                 # PairMetricsCalculator, PairMetrics
│   ├── regime.py                  # RegimeClassifier, GlobalRegime, RegimeType
│   ├── scoring.py                 # ScoringEngine, TFScore, FinalScore
│   └── universe.py                # UniverseManager, UniverseEntry, UniverseVersion
├── ports/
│   ├── db.py                      # MarketSelectionDBPort (Protocol)
│   ├── persistence.py             # PersistencePort (Protocol)
│   └── monitoring.py              # MonitoringPort (Protocol)
├── infrastructure/
│   ├── database.py                # MarketSelectionDB — запросы к БД
│   ├── persistence.py             # MarketSelectionPersistence — upserts, write-lock
│   ├── monitoring.py              # In-memory / Prometheus метрики
│   └── factory.py                 # build_market_selection_pipeline() — DI wiring
├── interfaces/
│   └── commands.py                # CLI-команды (pklpo market-selection)
└── migrations/                    # SQL-миграции 001–004
```

---

## Appendix B: Domain-логика в деталях

### Pair Metrics

| Метрика | Формула | Направление |
|---------|---------|-------------|
| **vol** | `median(atr_14 / close)` | выше = лучше |
| **trend_q** | `(median(adx_14) / 100) × abs(ema_slope / median(close))` | выше = лучше |
| **noise** | `std(|log_return|) / median(|log_return|)` | **ниже = лучше** |
| **stability** | `dominance × (1 − switch_rate)` по локальным bar-режимам | выше = лучше |
| **liq** | `median(volume) / (cv(volume) + 1)` | выше = лучше |

### Базовые веса метрик (scoring)

| Метрика | Базовый вес |
|---------|-------------|
| `trend_q` | 0.30 |
| `vol` | 0.25 |
| `noise` | 0.20 |
| `stability` | 0.15 |
| `liq` | 0.10 |

Веса корректируются дельтами согласно текущему `RegimeType`. Итоговые веса нормализуются к 1.0.

### MTF-веса и штрафы

| TF | Вес | При отсутствии |
|----|-----|----------------|
| `4H` | 0.40 | `final_score × 0.92` |
| `1H` | 0.30 | `final_score × 0.90` |
| `15m` | 0.20 | `final_score − 0.03` |
| `5m` | 0.10 | `final_score − 0.03` |

Без обоих 4H и 1H: символ исключается (`MISSING_SENIOR_TF`).

### Режимы рынка

| Тип | Условие классификации |
|-----|----------------------|
| `VOLATILE` | `atr/close > 80th percentile` (проверяется первым) |
| `TREND_UP` | `adx ≥ 25` и `ema_slope > 0` |
| `TREND_DOWN` | `adx ≥ 25` и `ema_slope < 0` |
| `RANGE` | `adx < 18` |

Агрегация по TF: `1D:0.5 / 4H:0.3 / 1H:0.2 → direction_score → GlobalRegime`.

---

**Версия:** 1.0.0
**Последнее обновление:** 2026-03-06
**Статус:** Production Ready
