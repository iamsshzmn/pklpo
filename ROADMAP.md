# PKLPO Roadmap 2.0

## Цель
Собрать единый, исполнимый и проверяемый план развития платформы PKLPO на основе текущих документов `plan/ROADMAP.md`, `plan/quantitative_plan.md`, `plan/implementation_check.md`, `plan/tech_recommendations.md` и `plan/recommendatuion`.

Ключевые цели версии 2.0:
- закрепить архитектуру и границы модулей;
- закрыть незавершённые критичные блоки (shadow-live, deployment, единый CostModel, расширенный backtest);
- выстроить инженерную дисциплину по OOP, DoP, DRY, KISS, SOLID;
- обеспечить измеримый прогресс через гейты, метрики и Definition of Done.

## Текущее состояние (сводка)

### 📍 Текущая позиция: Фаза 4 (Unified Execution & CostModel)

| Фаза | Название | Статус | Прогресс |
|------|----------|--------|----------|
| 0 | Platform Baseline | ✅ DONE | 100% |
| 1 | Data & Ingest Hardening | 🟡 IN PROGRESS | ~75% |
| 2 | Features & Performance | 🟡 IN PROGRESS | ~80% |
| 3 | Quant Stack | ✅ DONE | 100% |
| 4 | Unified Execution & CostModel | 🟡 IN PROGRESS | ~0% |
| 5 | Risk & OMS Maturity | ⚪ PLANNED | 0% |
| 6 | Shadow-Live | ⚪ PLANNED | 0% |
| 7 | Deployment & Operations | ⚪ PLANNED | 0% |

**Ближайшие приоритеты:**
1. Фаза 4 Блок A: `src/execution/` — ExecutionPort + CostModel + BacktestExecutor
2. Фаза 4 Блок B: BacktestEngine + CLI `backtest`

По текущему `ROADMAP.md` и проверкам:
- реализовано ядро ingest/features/MTF/signals/risk/storage/testing/monitoring;
- частично реализованы Market Data++ и CostModel;
- критично не завершены Shadow-Live и промышленный Deployment;
- есть потенциал улучшений по конфигурации, retry/backoff, observability, типизации и унификации документации.



## Целевая карта модулей
- `market_data`: ingest, quality checks, store, freshness/SLA.
- `features`: вычисление индикаторов и feature sets.
- `context_mtf`: MTF context, triggers, consensus.
- `signals`: signal generation + rationale.
- `risk`: sizing, limits, guards, kill-switch.
- `execution`: единый исполнителm (fees/spread/slippage/%ADV/latency).
- `positions`: position store, pnl lifecycle.
- `backtest`: WF/OOS, CPCV, DSR, отчеты.
- `monitoring`: metrics/logs/alerts/runbook.
- `platform`: config, migrations, CI/CD, orchestration.

## Фазы Roadmap 2.0

### Фаза 0. Platform Baseline (1-2 недели) — ✅ DONE
Цель: стабилизировать основу перед функциональными изменениями.

Задачи:
- ✅ Централизовать конфигурацию (`pydantic-settings`) и убрать дубли env/YAML/code.
- ✅ Формализовать retry policy (exponential backoff + jitter) для внешних API.
- ✅ Зафиксировать единые coding standards: ruff + mypy + pytest + pre-commit.
- ✅ Ввести DoD/DoR для всех задач roadmap.

Гейт:
- ✅ 100% runtime-конфигурации читается из единого слоя settings.
- ✅ Все внешние клиенты используют стандартную retry policy.
- ✅ CI зеленый по lint/type/test.

### Фаза 1. Data & Ingest Hardening (2-3 недели) — 🟡 IN PROGRESS (~75%)
Цель: надежный и измеримый data pipeline.

Задачи:
- 🟡 **SLO/SLA freshness monitoring**
  - ✅ Thresholds (`quality.py`: warn=5min, critical=15min) + `check_freshness()` реализованы
  - ✅ Persisting в `ops.data_quality_metrics` через `QualityMetricsRepository`
  - ✅ DAG gate в `okx_swap_ohlcv_sync_v2.py` (пропуск если lag < threshold)
  - ❌ Dashboard для визуализации freshness метрик
  - ❌ Автоматические alerts (Slack/email) при freshness violations

- 🟡 **Метрики качества данных (holes/fill-rate/coverage)**
  - ✅ `check_fill_rate()` — funding_rate, open_interest, L2 (warn=95%, critical=80%)
  - ✅ `check_coverage_1m()` — покрытие market_data_ext vs OHLCV (warn=90%, critical=70%)
  - ✅ `check_smoke_10m()` — детектирование gaps (min 8 баров за 10 мин)
  - ✅ Smoke validation task в DAG после синхронизации
  - ❌ Duplicate detection как явная метрика (только через ON CONFLICT на уровне БД)
  - ❌ Dashboard и алерты на нарушения quality метрик

- ✅ **Idempotency и дедупликация** (`symbol, timeframe, timestamp`)
  - ✅ Бизнес-ключ + `INSERT ... ON CONFLICT DO UPDATE` с COALESCE policy (`upsert_builder.py`)
  - ✅ Watermark-based incremental sync (`sync_state.py`)
  - ✅ Защита от overwrite NULL over non-NULL

- 🟡 **Batch strategy оптимизация**
  - ✅ Per-timeframe adaptive limits: 1m=15000 bars, 5m=10000, 1D=1000 (`features_calc_short.py`)
  - ✅ Mode-based throughput: fast/slow/ext/bootstrap режимы
  - ✅ Per-TF adaptive timeouts (10 min для 1m, 4 min для 1H)
  - ❌ Динамический runtime batch-size (по нагрузке CPU/mem или API latency)

- ⬜ **[LIBRARY] Заменить `sync_swap_candles.py` на `ccxt`** (🔴 Высокий приоритет)
  - ccxt покрывает OKX полностью: `fetch_ohlcv`, `fetch_funding_rate`, `fetch_open_interest`
  - Удалить ~600 строк кастомного HTTP-кода с ручными URL/retry/backoff
  - Получить поддержку 100+ бирж без изменений архитектуры
  - Что остаётся кастомным: логика UPSERT в PostgreSQL, батч-сохранение
  - Подробнее: `docs/ideas/library_replacement_recommendations.md` §1

Гейт:
- 🟡 Достигаются target freshness и data-quality thresholds (thresholds заданы и enforcement есть; подтверждение через dashboard — ❌).
- ✅ Нет неидемпотентных повторных запусков.

### Фаза 2. Features & Performance (2-4 недели) — 🟡 IN PROGRESS (~80%)
Цель: ускорить вычисление и управляемость фичей.

**SOLID рефакторинг (см. `src/features/REFACTORING_PROGRESS.md`):**
- ✅ LSP: Унификация типов возврата групп индикаторов
- ✅ SRP: Разделение GroupCalculator на 4 компонента
- ✅ DIP: Устранение hard-coded импортов (injection)
- ✅ OCP: Вынос конфигурации в settings
- ✅ Инкапсуляция GroupRegistry
- ❌ Разделение batch_builder (SRP)
- ❌ Тесты и документация

Задачи:
- ✅ Ввести профилирование по группам индикаторов.
- ✅ Добавить timing metrics по feature groups.
- ⚪ При необходимости внедрить Polars/DuckDB в hot paths (по метрикам, не «вслепую»).
- ✅ Ужесточить типизацию в критичных модулях features.
- ⬜ **[LIBRARY] Добавить TA-Lib как второй backend для `ta_safe/`** (🟡 Средний приоритет)
  - TA-Lib в 5–20x быстрее pandas-реализаций (чистый C, 150+ индикаторов)
  - Добавить в `ta_safe/bridge.py`, убрать `fallback.py` (~300 строк)
  - TTM Squeeze оставить кастомным — в TA-Lib нет
  - Альтернатива без C-зависимостей: `ta` (чистый Python поверх pandas)
  - Подробнее: `docs/ideas/library_replacement_recommendations.md` §2

Гейт:
- 🟡 Падение p95 времени расчета фичей минимум на 20% или подтвержденная достаточность текущей производительности.
- ❌ Покрытие тестами feature contracts.

### Фаза 3. Quant Stack (3-5 недель) — 🟡 IN PROGRESS (~25%)
Цель: закрыть количественный контур из `quantitative_plan.md`.
Детальный план: `plan/phase3_quant_stack_plan.md`

Задачи:
- ✅ Scaffold: `src/core/`, `src/ml/`, `RunContext`, `QuantSettings`, `tests/ml/conftest.py` (Блок A)
- ✅ Dollar bars: `src/core/bars.py` + тесты 10/10 + CLI `build-bars` + миграция БД (Блок B)
- ❌ Triple-barrier labeling + sample weights (Блок C)
- ❌ Purged K-Fold + Embargo и CPCV + unified Sharpe/DSR (Блок D)
- ❌ Feature selection (MDI/MDA/PCA) (Блок E)
- ❌ Metalabeling pipeline (Блок F)
- ❌ Look-ahead test как обязательный quality gate (Блок G)
- ❌ Отчёт и метрики CLI (Блок H)
- ⬜ **[LIBRARY] Рассмотреть `mlfinlab`/`skfolio` для `ml/labeling/` и `ml/validation/`** (🟡 Средний приоритет)
  - Официальная реализация AFML: triple barrier, CPCV, purged K-Fold, MDI/MDA/SFI
  - Текущие кастомные реализации корректны (есть тесты) — замена снижает бремя поддержки
  - skfolio — более современный sklearn-совместимый API
  - Что оставить: `deflated_sharpe_ratio()`, meta-labeling (специфика стратегии)
  - Подробнее: `docs/ideas/library_replacement_recommendations.md` §5
- ⬜ **[LIBRARY] Добавить `hmmlearn`/`ruptures` для детекции рыночных режимов** (🟡 Средний приоритет)
  - hmmlearn: HMM для статистически строгой детекции режимов (trend/range/volatile)
  - ruptures: change point detection по волатильности
  - Альтернатива / дополнение к текущей реализации `mtf/context/algorithms.py`
  - Подробнее: `docs/ideas/library_replacement_recommendations.md` §8

Гейт:
- 🟡 Все новые модули покрыты unit/integration тестами (bars.py: 85% ✅).
- ❌ Look-ahead тест стабильно проходит.
- ❌ CPCV/DSR добавлены в финальный отчет.

### Фаза 4. Unified Execution & CostModel (3-5 недель) — 🟡 IN PROGRESS (~0%)
Цель: исключить расхождения между backtest/paper/live.
Детальный план: `plan/phase4_unified_execution_plan.md`

Задачи:
- ⬜ **Блок A:** `src/execution/` — ExecutionPort + CostModel (commission, IS, %ADV) + BacktestExecutor + ExecutionSettings + DB (trades, execution_runs)
- ⬜ **Блок B:** `src/backtest/engine.py` — BacktestEngine (bar-by-bar, walk-forward, RunContext) + CLI `backtest` + deprecate SignalEvaluator
- ⬜ **Блок C:** IS/reject_rate в BacktestReport + operational алерты + e2e тест
- ⬜ **Блок D:** PositionEventStore (equity curve, PnL lifecycle) + интеграция в BacktestEngine
- ⬜ **[LIBRARY] `vectorbt` → заменить `calc_pnl`, интегрировать в BacktestEngine (Блок B)** (🔴 Высокий приоритет)
  - 100–1000x быстрее iterrows-симуляции; Portfolio с leverage/fees/slippage/%ADV
  - Встроенные метрики (Sharpe, Sortino, MaxDD, Calmar, Omega, Win Rate)
  - Параметрическая оптимизация и Plotly-визуализация из коробки
  - Подробнее: `docs/ideas/library_replacement_recommendations.md` §3
- ⬜ **[LIBRARY] `quantstats` → заменить `calc_metrics` + `report.py`** (🔴 Высокий приоритет)
  - 50+ метрик: Sharpe, Sortino, Calmar, Omega, VaR, CVaR, Skew, Kurtosis
  - Полный HTML-отчёт (заменяет `report.py`), бенчмаркинг против индексов
  - Сохранить кастомный `deflated_sharpe_ratio()` — в QuantStats его нет
  - Подробнее: `docs/ideas/library_replacement_recommendations.md` §4

Гейт:
- ❌ Backtest и paper используют один и тот же execution path (ExecutionPort).
- ❌ Метрики IS/latency/reject-rate доступны в BacktestReport.
- ❌ Все trades привязаны к run_id.

### Фаза 5. Risk & OMS Maturity (2-3 недели) — ⚪ PLANNED
Цель: повысить устойчивость торговли в production.

Задачи:
- ❌ Доработать portfolio limits/guard policies.
- ❌ Ввести сценарии деградации: partial-fill, timeout, cancel-all, kill-switch flows.
- ❌ Формализовать stress-tests и failover runbook.

Гейт:
- ❌ Guard coverage для ключевых risk-сценариев.
- ❌ Runbook покрывает критические инциденты end-to-end.

### Фаза 6. Shadow-Live (критично, 2-4 недели) — ⚪ PLANNED
Цель: сравнить expected vs actual без реального риска капитала.

Задачи:
- ❌ Запуск shadow-live режима для целевых инструментов.
- ❌ Сравнение сигналов и исполнений с backtest baseline.
- ❌ Еженедельный drift-анализ по PnL drivers/latency/IS.

Гейт:
- ❌ Минимум 2-4 недели стабильной работы shadow-live.
- ❌ Drift находится в допустимом диапазоне.

### Фаза 7. Deployment & Operations (критично, 2-3 недели) — ⚪ PLANNED
Цель: production-ready контур развертывания.

Задачи:
- ❌ CI/CD пайплайн с миграциями и rollback strategy.
- ❌ Release policy: canary, rollback, version pinning.
- ❌ Набор операционных SLO/alerts + on-call runbook.

Гейт:
- ❌ Повторяемый deployment без ручных ad-hoc шагов.
- ❌ Подтвержденный rollback за ограниченное время.

## Definition of Done (единый)
Задача считается завершенной только если:
- есть тесты (unit/integration; где нужно property-based);
- есть типизация публичных контрактов;
- есть метрики/логи для нового behavior;
- есть обновление документации и runbook;
- есть миграция/совместимость схемы данных (если затрагивается БД);
- есть запись в changelog или release notes.

## Technical Debt Backlog (приоритет)
P0:
- Shadow-live.
- Deployment automation.
- Unified CostModel/execution parity.

P1:
- ~~Централизация конфигурации.~~ ✅
- ~~Retry/backoff унификация.~~ ✅
- Observability расширение (timing metrics, pool metrics).

P2:
- Стандартизация языка документации.
- Переход части hot-path на Polars/DuckDB после профилирования.
- Повышение strictness mypy поэтапно.

### Library Migration Backlog

> Полный анализ и примеры кода: `docs/ideas/library_replacement_recommendations.md`
> Порядок внедрения: Шаг 1 (ccxt + quantstats) → Шаг 2 (vectorbt) → Шаг 3 (mlfinlab + TA-Lib) → Шаг 4 (hmmlearn + alembic + riskfolio-lib)

| Приоритет | Библиотека | Заменяет | Выигрыш | Фаза |
|-----------|------------|---------|---------|------|
| 🔴 P0 | `ccxt` | `candles/sync_swap_candles.py` | −600 строк HTTP, поддержка 100+ бирж | 1 |
| 🔴 P0 | `vectorbt` | `backtest/metrics.py` (calc_pnl) | 100–1000x скорость, реальная симуляция | 4 |
| 🔴 P0 | `quantstats` | `backtest/metrics.py` + `report.py` | 50+ метрик, HTML-отчёты | 4 |
| 🟡 P1 | `TA-Lib` / `ta` | `features/ta_safe/fallback.py` | 5–20x скорость, −300 строк | 2 |
| 🟡 P1 | `mlfinlab` / `skfolio` | `ml/labeling/`, `ml/validation/` | Официальный AFML, больше алгоритмов | 3 |
| 🟡 P1 | `hmmlearn`, `ruptures` | `mtf/context/algorithms.py` | Статистически строгие режимы рынка | 3 |
| 🟡 P1 | `alembic` | `database/migrate_*.py` | Стандарт SQLAlchemy, rollback, автогенерация | platform |
| 🟢 P2 | `pybreaker` | `risk/guards/circuit_breaker.py` | Чище, но теряем DB-persistence | 5 |
| 🟢 P2 | `riskfolio-lib` | `risk/limits/` | Открывает HRP/CVaR оптимизацию | 5 |
| 🟢 P2 | `stamina` | `utils/retry.py` | Современный async API, tenacity работает | — |

**Что НЕ нужно заменять:** `src/signals/`, `src/mtf/consensus/`, `src/positions/calculator.py`,
`src/risk/guards/sla_guards.py`, `deflated_sharpe_ratio()`, `src/ml/metalabeling/`, `src/features/indicator_groups/`.

## KPI Roadmap 2.0
- Reliability: доля успешных DAG run, MTTR, % idempotent reruns.
- Data: freshness, hole-rate, dup-rate, fill-rate.
- Performance: p95 feature-calc, p95 execution latency.
- Trading quality: IS bps, reject-rate, slippage drift.
- Research quality: доля стратегий, прошедших CPCV/DSR gates.
- Engineering: test coverage критичных модулей, type coverage публичных интерфейсов.

## Порядок внедрения (30-60-90)
- 0-30 дней: Фазы 0-1, старт Фазы 2.
- 30-60 дней: завершение Фаз 2-4.
- 60-90 дней: Фазы 5-7, выход на controlled production.

## Контроль исполнения
- Еженедельный review roadmap с обновлением статусов: `planned/in_progress/blocked/done`.
- Каждый блокирующий риск фиксируется с owner и датой mitigation.
- Любое отклонение от OOP/DoP/DRY/KISS/SOLID документируется и проходит архитектурный review.

## Легенда статусов

| Символ | Значение |
|--------|----------|
| ✅ | Завершено |
| 🟡 | В работе / частично |
| ❌ | Не начато |
| ⚪ | Запланировано |
| 🔴 | Заблокировано |

---
*Последнее обновление: 2026-03-01*
