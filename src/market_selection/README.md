# Market Selection

Модуль выбирает торговый universe (top-N символов) на основе качества данных, метрик пары, глобального режима рынка и multi-timeframe scoring.

## DAG-интеграция

```
features_calc_short → market_selection → features_calc_full
```

Выходные таблицы используются downstream для формирования universe при расчёте полного набора фич.

## Архитектура модуля

```
src/market_selection/
├── config.py                      # Единый конфиг (MarketSelectionConfig)
├── __init__.py                    # Версия v1.0.0, публичное описание
├── application/
│   └── pipeline.py                # MarketSelectionPipeline — главный оркестратор
├── domain/
│   ├── quality_gate.py            # DataQualityGate, ReasonFlag, QualityResult
│   ├── metrics.py                 # PairMetricsCalculator, PairMetrics
│   ├── regime.py                  # RegimeClassifier, GlobalRegime, RegimeType
│   ├── scoring.py                 # ScoringEngine, TFScore, FinalScore
│   └── universe.py                # UniverseManager, UniverseEntry, UniverseVersion
├── infrastructure/
│   ├── database.py                # MarketSelectionDB — запросы к БД
│   ├── persistence.py             # MarketSelectionPersistence — upserts, write-lock
│   └── monitoring.py              # Метрики Prometheus / in-memory история
├── cli/
│   └── commands.py                # CLI-команды (market-selection)
└── migrations/                    # SQL-миграции 001–004
```

## Что делает pipeline

Основной оркестратор: `src/market_selection/application/pipeline.py` — `MarketSelectionPipeline.run()`.

Шаги выполнения:

1. **Resolve `ts_eval`** — определяет границу данных (последний закрытый бар).
2. **Validate features** — проверяет наличие `short_feature_set` в таблице `indicators`; при `missing > max_missing_features` возвращает `SHORT_FEATURE_MISMATCH`.
3. **Global regime** — вычисляет режим рынка через `RegimeClassifier` по basket top-K символов (TF: `1D`, `4H`, `1H`). При устаревших данных (`lag > threshold`) берёт последний валидный режим из `market_regime_history` с флагом `stale=True`.
4. **Per-TF processing** — для каждого TF из `selection_tfs` (`5m`, `15m`, `1H`, `4H`):
   - `DataQualityGate` — качество данных, фильтрация неeligible символов.
   - `PairMetricsCalculator` — расчёт 5 сырых метрик.
   - `ScoringEngine.normalize_metrics()` — нормализация до 0–1.
   - `ScoringEngine.calculate_tf_scores()` — взвешенная сумма с учётом режима.
   - VOLATILE-фильтр: символы с `liq_score < volatile_min_liq_score` исключаются.
   - Запись в `market_scores_tf` (upsert).
5. **Systemic outage check** — если `>30%` символов не прошли 1H/4H gate → fallback.
6. **MTF aggregation** — `ScoringEngine.aggregate_mtf_scores()` → `final_score` по всем TF с весами и штрафами за отсутствующие TF.
7. **Universe selection** — `UniverseManager.select_universe()`: top-N + буфер + hysteresis + whitelist/blacklist.
8. **Fallback check** — если `universe_size < soft/hard threshold` → fallback на предыдущую версию.
9. **Publish** — запись в `market_universe` + `market_universe_versions` через PostgreSQL advisory write-lock (`pg_try_advisory_xact_lock`). Статус `published`.

При любом сбое: `status = fallback_prev` (копируется предыдущий universe) или `failed`.

## Domain-слой

### Quality Gate (`domain/quality_gate.py`)

`DataQualityGate.evaluate()` проверяет каждый `(symbol, timeframe)`:

| Проверка | Порог (5m / 15m / 1H / 4H) |
|----------|----------------------------|
| `fill_rate = valid_bars / expected_bars` | ≥ 0.97 / 0.98 / 0.99 / 0.99 |
| `gap_rate = gaps_count / expected_bars` | ≤ 0.015 / 0.010 / 0.005 / 0.005 |
| `data_lag_seconds` | ≤ 15 / 45 / 180 / 720 мин |
| `valid_bars ≥ warmup_min_bars` | ≥ 280 баров |
| `volume_present` | должен быть ненулевой объём |

`quality_score` (используется как множитель при scoring):
```
quality_score = clamp((fill_rate - fill_min) / (1 - fill_min), 0, 1)
              × clamp(1 - gap_rate / gap_max, 0, 1)
```

**ReasonFlag** — полный перечень флагов:

| Флаг | Причина |
|------|---------|
| `LOW_FILL` | fill_rate ниже порога |
| `HIGH_GAPS` | gap_rate выше порога |
| `INSUFFICIENT_WARMUP` | мало баров для прогрева индикаторов |
| `NO_VOLUME` | нет данных об объёме |
| `STALE_DATA` | данные слишком старые |
| `MISSING_METRIC_INPUT` | < 90% баров имеют все ключевые фичи |
| `SHORT_FEATURE_MISMATCH` | отсутствуют ожидаемые колонки |
| `LOW_LIQ_IN_VOLATILE` | недостаточная ликвидность в VOLATILE режиме |
| `MISSING_SENIOR_TF` | нет ни 1H, ни 4H — символ исключён |
| `MISSING_4H_SOFT` | нет 4H — применяется штраф ×0.92 |
| `MISSING_1H_SOFT` | нет 1H — применяется штраф ×0.90 |
| `SHORT_HISTORY` | < 7 дней истории оценок |
| `UNIVERSE_FALLBACK_PREV` | universe взят из предыдущей версии |
| `SYSTEMIC_SENIOR_OUTAGE` | системный отказ старших TF |

### Pair Metrics (`domain/metrics.py`)

`PairMetricsCalculator.calculate_all()` вычисляет 5 сырых метрик по (symbol, timeframe):

| Метрика | Формула | Направление |
|---------|---------|-------------|
| **vol** (volatility) | `median(atr_14 / close)` | выше = лучше |
| **trend_q** (trend quality) | `(median(adx_14) / 100) × abs(ema_slope / median(close))` | выше = лучше |
| **noise** | `std(|log_return|) / median(|log_return|)` | **ниже = лучше** |
| **stability** | `dominance × (1 − switch_rate)` по локальным bar-режимам | выше = лучше |
| **liq** (liquidity) | `median(volume) / (cv(volume) + 1)` | выше = лучше |

`trend_q` использует `ema_slope_source` (`ema_21` или `ema_55`) с rolling regression за `slope_lookback_bars` (default: 50).

`stability` классифицирует каждый бар как TREND/RANGE/VOLATILE/NEUTRAL, считает долю доминирующего класса и частоту смены режима.

### Regime Detection (`domain/regime.py`)

`RegimeClassifier` определяет глобальный рыночный режим через basket top-K символов по медианному объёму.

**Типы режимов:**

| Тип | Условие |
|-----|---------|
| `VOLATILE` | `atr/close > 80th percentile` (проверяется первым) |
| `TREND_UP` | `adx ≥ 25` и `ema_slope > 0` |
| `TREND_DOWN` | `adx ≥ 25` и `ema_slope < 0` |
| `RANGE` | `adx < 18` |

Классификация per-TF → агрегация с весами `1D:0.5, 4H:0.3, 1H:0.2` → `direction_score` → итоговый `GlobalRegime`.

При `lag` по любому режимному TF сверх порога: берётся последний валидный режим из `market_regime_history`, флаг `stale=True`.

### Scoring Engine (`domain/scoring.py`)

**Нормализация:** percentile-rank (0–1). При `n_eligible < 20` — z-score → sigmoid. Winsorize: `(1%, 99%)`, при малом universe `(5%, 95%)`.

**Базовые веса метрик:**

| Метрика | Вес |
|---------|-----|
| `trend_q` | 0.30 |
| `vol` | 0.25 |
| `noise` | 0.20 |
| `stability` | 0.15 |
| `liq` | 0.10 |

Веса корректируются согласно текущему режиму (дельты из `regime_deltas`). Итоговые веса нормализуются к сумме 1.0.

`score_tf = score_tf_base × quality_score`

**MTF-агрегация:**

| TF | Вес |
|----|-----|
| `4H` | 0.40 |
| `1H` | 0.30 |
| `15m` | 0.20 |
| `5m` | 0.10 |

Штрафы за отсутствие TF:
- 4H missing: `final_score × 0.92`
- 1H missing: `final_score × 0.90`
- 15m/5m missing: `-0.03` каждый

Символы без обоих 4H и 1H исключаются (`MISSING_SENIOR_TF`).

### Universe Manager (`domain/universe.py`)

`UniverseManager.select_universe()`:

1. Фильтрует `blacklist`.
2. Разделяет кандидатов на **primary** (стабильные, история ≥ 7 дней, std_7d ≤ 0.12) и **buffer**.
3. Выбирает top-N из primary.
4. **Hysteresis**: символы из предыдущего universe добавляются из buffer (до `buffer_size=10` мест).
5. Whitelist-символы принудительно включаются (при наличии 1H/4H).
6. Пересортировка по `final_score`, переназначение рангов.

Fallback активируется при: `universe_size < soft_min (10)` → `fallback_prev`; `< hard_min (5)` → `failed`.

## Конфигурация

Конфиг: `src/market_selection/config.py` — единственный источник истины.

| Класс | Назначение |
|-------|-----------|
| `RegimeConfig` | basket_k, ADX/ATR пороги, веса TF, lag-пороги |
| `QualityConfig` | fill_min, gap_max, lag_max, warmup_min_bars |
| `ScoringConfig` | base_weights, regime_deltas, tf_weights, штрафы |
| `UniverseConfig` | top_n, buffer, std-пороги, whitelist, blacklist |
| `MarketSelectionConfig` | главный конфиг, объединяет все секции |

`config_hash()` — SHA-256 (16 hex) канонического JSON конфига. Записывается во все таблицы для воспроизводимости.

Синглтон: `get_config()` / `set_config()` (для тестов).

## CLI

Команда: `pklpo market-selection <action>`

| Action | Описание |
|--------|---------|
| `run [--top-n N] [--dry-run]` | Запустить pipeline |
| `status` | Статус последней версии |
| `explain <SYMBOL>` | Детали scoring для символа |
| `universe [--limit N] [--format table\|json\|csv]` | Показать текущий universe |
| `regime` | Текущий глобальный режим |
| `metrics [--history N] [--format table\|json]` | История запусков |
| `migrate` | Применить SQL-миграции |

Файл команд: `src/market_selection/cli/commands.py`.

## Схема данных

Миграции: `src/market_selection/migrations/` (001–004).

| Таблица | Описание |
|---------|---------|
| `market_scores_tf` | Score по `(symbol, timeframe, ts_eval)` + raw/normalized метрики + quality/regime metadata |
| `market_universe` | Итоговые символы версии universe с final_score, рангом, stability |
| `market_universe_versions` | Статус версии (`building` / `published` / `failed` / `fallback_prev`), статистика запуска |
| `market_regime_history` | История глобального режима, stale-флаг, корзина символов |

Ключ идемпотентности: `(symbol, timeframe, ts_eval)` для `market_scores_tf`; `(ts_version, symbol)` для `market_universe`.

## Fallback и отказоустойчивость

| Триггер | Действие |
|---------|---------|
| Системный отказ 1H/4H (`> 30%` символов) | Fallback на предыдущую версию |
| `universe_size < soft_min (10)` | Fallback |
| `universe_size < hard_min (5)` | Failed + fallback |
| Нет final scores | Fallback |
| Нет предыдущей версии | Failed |

При fallback: предыдущий universe копируется в новую `ts_version`, `status = fallback_prev`.

## Write-lock (конкурентная безопасность)

Запись итогов защищена PostgreSQL advisory lock (`pg_try_advisory_xact_lock`).
Timeout: 10 000 мс. При превышении — `LockTimeoutError`.
Реализация: `MarketSelectionPersistence.acquire_write_lock_for_ts_version()`.

## Monitoring

Реализация: `src/market_selection/infrastructure/monitoring.py`.

- In-memory история запусков (для `metrics history`).
- Опциональные Prometheus-метрики (если установлен `prometheus_client`): `market_selection_universe_size`, `market_selection_execution_seconds`, `market_selection_errors_total`.
- Функции: `record_pipeline_metrics()`, `get_metrics()`.

## Очистка данных

Реализация: `MarketSelectionPersistence` в `persistence.py`.

| Таблица | Retention |
|---------|-----------|
| `market_scores_tf` | 180 дней |
| `market_universe` / `market_universe_versions` | 90 дней |

## Быстрый старт

```bash
# 1. Применить миграции
pklpo market-selection migrate

# 2. Запустить pipeline
pklpo market-selection run --top-n 30

# 3. Проверить результат
pklpo market-selection status
pklpo market-selection universe --limit 30

# 4. Проверить режим рынка
pklpo market-selection regime
```

## Программный доступ

```python
from sqlalchemy.ext.asyncio import AsyncSession
from src.market_selection.application.pipeline import MarketSelectionPipeline
from src.market_selection.config import MarketSelectionConfig

async with AsyncSession(engine) as session:
    config = MarketSelectionConfig(universe=UniverseConfig(top_n=20))
    pipeline = MarketSelectionPipeline(session, config)
    result = await pipeline.run()
    print(result.universe_size, result.status, result.global_regime)
```
