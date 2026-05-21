# PKLPO Roadmap 3.0

## Что это за документ

Roadmap 3.0 — результат discovery-аудита проекта (2026-05-20). Он заменяет
Roadmap 2.0, который описывал PKLPO как enterprise trading platform. Реальный
проект — **personal multi-timeframe research framework** для swing-трейдинга
крипто-перпов с ручным исполнением сделок. Roadmap 3.0 приводит план в
соответствие с реальным scope.

Ключевое отличие от 2.0:
- 8 фаз (включая ExecutionPort, OMS, CI/CD canary) → **3 фазы** под реальный v1;
- enterprise-DoD из 8 блоков → **5 measurable gates**;
- честный статус: код Phase 3 написан, но **не покрыт тестами** — фаза НЕ закрыта;
- всё, что обслуживает auto-execution и production-trading, отложено в **v2**.

---

## Что такое PKLPO v1

Воспроизводимый research/discovery framework для multi-timeframe анализа
крипто-перпетуалов. Система:

- собирает OHLCV с OKX автономно и без потерь;
- считает индикаторы и feature sets детерминированно, без look-ahead;
- генерирует rule-based сигналы: regime (1W) → MTF context (1D/4H) → confluence setup;
- валидирует гипотезы через walk-forward / CPCV / DSR против baseline;
- логирует сигналы и ручные решения, измеряет signal-to-trade conversion;
- доводит перспективные идеи до shadow/paper и до первой сделки на $100.

**Целевой holding period:** 7–30 дней (90 дней — экспериментальный режим).
**Primary TF:** 1D / 4H. **Higher TF context:** 1W. **Universe:** ликвидные perp.
**Исполнение в v1:** ручное (discretionary overlay поверх структурированного сигнала).

### Non-goals (v1 сознательно НЕ делает)

Multi-exchange · HFT / orderbook / tick data · опционы и сложные деривативы ·
auto-execution · portfolio optimization (HRP/CVaR/risk parity) · UI / SaaS /
multi-user · Deep Learning / RL · marketplace стратегий · production-торговля
с серьёзным капиталом.

PKLPO v1 должен доказать один путь: **data → features → signals → backtest →
shadow-live → manual decision** — и доказать, что этот путь не врёт.

---

## Текущее состояние (честная сводка, 2026-05-20)

| Слой | Состояние | Комментарий |
|------|-----------|-------------|
| Ingest / candles | ✅ работает | `ON CONFLICT` во всех репозиториях, идемпотентность ingestion есть |
| Repair / backfill | 🟡 код есть | Никогда не прогонялся против реального gap-сценария |
| Features pipeline | 🟡 работает, раздут | 158 файлов / ~28.7k строк — оценочно ×3-5 от нужного объёма |
| ML labeling / validation | 🔴 код есть, тестов 0 | 1542 строки (triple-barrier, CPCV, purged-KFold, lookahead, ...) — **не валидировано** |
| ML metalabeling | ⚪ код впереди потребности | Нет decision-log и накопленных сделок для обучения — заморожено |
| Signals | 🟡 скелет | `signals/` есть; `INSERT` без `ON CONFLICT` — риск дублей |
| signal_decisions / manual_trades | 🔴 не существует | Критичный missing piece для research-цели |
| Telegram notifier | 🔴 не существует | — |
| Backtest | 🟡 частично | Custom `calc_pnl`; план — перейти на vectorbt/quantstats |
| Research workflow | 🔴 не существует | Нет `notebooks/`, нет `runs/`, нет experiment tracking |
| Baselines | 🔴 не существует | Без baseline reject-гейты бессмысленны |
| Backup / DR | 🔴 нет бэкапов | ~70 GB на одном внешнем SSD — single point of failure |
| `make check` quality gate | 🔴 декоративный | Сконфигурирован (coverage 85%), на практике не запускался |

**Главный диагноз:** проект имеет *артефакты* инженерной строгости (DDD-слои,
registry, Protocol-контракты, coverage-таргеты) без *практики* (запускаемых
проверок, написанных тестов, используемого workflow). Приоритет №1 — закрыть
этот разрыв, а не добавлять функциональность.

### История (закрытые фазы 2.0)

| Фаза 2.0 | Статус | Примечание |
|----------|--------|------------|
| 0. Platform Baseline | ✅ DONE | pydantic-settings, retry policy, ruff/mypy/pytest |
| 1. Data & Ingest Hardening | 🟡 в основном | Repair не провалидирован прогоном |
| 2. Features & Performance | 🟡 функционально | Раздутость — теперь tech-debt (см. Prune Track) |
| 3. Quant Stack | 🔴 НЕ закрыта | Код блоков C–H написан, но без тестов = не доказан |

---

## Целевая карта модулей

- `candles` (`market_data`): ingest, quality checks, store, repair, freshness/SLA.
- `features`: индикаторы и feature sets. Целевой two-track: `research/` + `indicator_groups/`.
- `mtf` (`context_mtf`): MTF context, regime detection, triggers, consensus.
- `signals`: генерация сигналов + rationale; `signal_decisions`; `manual_trades`.
- `ml`: labeling / validation (нужно протестировать); metalabeling (заморожено до v2).
- `backtest`: walk-forward / CPCV / DSR / baselines / отчёты (миграция на vectorbt/quantstats).
- `research`: notebook workflow + `runs/` артефакты + experiment metadata.
- `risk`: sizing, limits, guards, kill-switch (в v1 — минимально, не развивать).
- `platform`: config, migrations, orchestration, backup.

Контекстов больше не плодить. Полная карта: `docs/ARCHITECTURE.md` §4–§7.

---

## Фазы Roadmap 3.0

Три фазы. Phase A — блокер всего: нельзя строить research на непроверенном
фундаменте. Phase B — ядро продукта. Phase C — выход на shadow и первую сделку.

### Фаза A — Trust & Durability (3–4 недели) — 🔴 БЛОКЕР

Цель: фундамент, которому можно доверять. Бэкапы, тесты на код, который
утверждает «бэктест честный», доказанная идемпотентность.

| ID | Задача | Приоритет |
|----|--------|-----------|
| A0 | **Бэкапы БД.** `pg_dump` по cron → второй диск + облако (Backblaze/S3). Правило 3-2-1. **Проверенный restore в чистое окружение.** | P0 — сделать первым |
| A1 | Аудит размера БД: `pg_total_relation_size` по таблицам. Понять, из чего 70 GB, почистить bloat. Прогноз роста под рост глубины/инструментов. | P0 |
| A2 | Тесты `ml/labeling` + `ml/validation` (1542 строки): numerical-equivalence против reference dataset / mlfinlab. | P0 |
| A3 | Look-ahead тест → обязательный gate в `make check`. | P0 |
| A4 | Idempotency: `ON CONFLICT` + unique constraint для `signals.candidates/live/history`; double-run тесты для каждого DAG (ingest/backfill/repair/features/signals). | P0 |
| A5 | Параметризовать SQL в `scoring_engine/processor.py:440/445` (symbol/timeframe). Allowlist для `ema_col` в `market_selection`. | P1 |
| A6 | Запустить `make check`, зафиксировать baseline, починить до зелёного. | P0 |
| A7 | Ручной тест repair: вырезать сутки данных → repair → проверить hole-rate. Заодно зафиксировать политику fail-loud. | P1 |

**Гейт A (= Success Gate 1 + 2):**
- [ ] Бэкап восстановлен из облака в чистое окружение хотя бы раз.
- [ ] `ml/labeling` + `ml/validation` покрыты тестами, проходят numerical-equivalence.
- [ ] Look-ahead тест в `make check`, стабильно зелёный.
- [ ] `make check` зелёный; coverage `candles`/`ml`/`signals` ≥ 80%.
- [ ] Все DAG: double-run тест зелёный.
- [ ] Repair прогнан против реального gap-сценария.

### Фаза B — Research Loop (4–5 недель) — ядро продукта

Цель: рабочий цикл «гипотеза → backtest → сигнал → решение → лог». Адаптировать
проверенные библиотеки вместо написания custom-кода.

| ID | Задача | Приоритет |
|----|--------|-----------|
| B1 | Схемы `signal_decisions` (accept/reject/skip/watchlist + причина), `manual_trades`/`positions` (связь с `signal_id`). Достроить `signals` до 15 полей (direction, score, entry zone, invalidation, SL/TP, holding, expiry, rationale, warnings...). | P0 |
| B2 | Telegram-бот: notification layer для сигналов + 3 алерта (DAG failed / hole-rate / disk < 15%). Source of truth остаётся в Postgres. | P0 |
| B3 | Baselines: `buy_and_hold` BTC, `buy_and_hold` asset, `momentum`, `random_signals`, `cash`. Любая гипотеза сравнивается с ними по risk-adjusted метрикам. | P0 |
| B4 | Research workflow: `notebooks/research_template.ipynb` + структура `runs/<run_id>/` (config.yaml, metrics.json, notes.md, charts/). Критичная логика — в `src/`, не в notebook. | P0 |
| B5 | Data versioning: universe snapshot persistence (список символов на дату эксперимента), feature pipeline version stamp (git commit), data window, dependency lockfile hash. | P0 |
| B6 | Backtest на **vectorbt** (заменяет `calc_pnl`) + **quantstats** (метрики/отчёт). Сохранить кастомный `deflated_sharpe_ratio()`. Адаптация, не написание custom execution layer. | P1 |
| B7 | Зафиксировать reject gates в коде: мало сделок / negative expectancy после fees+slippage / большой DD / нестабильность по WF-окнам / признаки leakage. Multiple-testing правило: число тестируемых гипотез фиксируется в `config.yaml` **до** запуска. | P0 |
| B8 | Two-track features: создать `features/research/` — голые функции на DataFrame, без registry, для быстрой итерации в notebook. Promoted-фичи переходят в `indicator_groups/` с контрактами и тестами. | P1 |

**Гейт B (= Success Gate 3 + 4, partial):**
- [ ] ≥ 10 гипотез прогнаны через единый pipeline с `runs/` артефактами.
- [ ] Каждая гипотеза сравнена с 5 baseline по risk-adjusted метрикам.
- [ ] Reject gates срабатывают автоматически.
- [ ] ≥ 1 гипотеза прошла walk-forward + CPCV + DSR с positive expectancy после fees.
- [ ] Сигнал генерируется → пишется в `signals` → уходит в Telegram.
- [ ] Решения логируются в `signal_decisions`; signal-to-trade conversion считается.
- [ ] Эксперимент воспроизводим: повторный запуск даёт те же features/labels/metrics.

### Фаза C — Shadow & First Trade (открытый период)

Цель: накопить историю сигнал → решение → результат, пройти security gate,
сделать первую сделку на $100 как validation environment.

| ID | Задача | Приоритет |
|----|--------|-----------|
| C1 | Paper logger: каждый signal → simulated execution (fee/slippage модель — функция, не пакет) → лог. Еженедельный drift-отчёт (simulated vs ожидание). | P0 |
| C2 | **Pre-Trading Security Gate** (см. ниже) — обязательный чек-лист до первого реального ордера. | P0 |
| C3 | Накопление 50–100 сделок paper. При holding 7–30 дней это **месяцы**, не недели. Closure фазы = «loop работает», а не «стратегия найдена». | — |
| C4 | Первый real trade на ~$100 как validation environment: проверка backtest ↔ shadow ↔ manual parity, operational/психологические эффекты. | P1 |

**Pre-Trading Security Gate (= Success Gate 5):**
- [ ] OKX trading key: **no-withdraw permission обязателен**, IP whitelist, отдельный ключ от read-only.
- [ ] Trading-ключи вне `.env` (OS keychain / `sops` / cloud secrets).
- [ ] Paper/live разделение режимов на уровне конфига — невозможно случайно отправить реальный ордер из research-режима.
- [ ] `cancel-all` / `close-all` flow + процедура revoke ключа задокументированы и проверены.

**Гейт C:**
- [ ] Paper logger накопил ≥ 30 сигналов с simulated execution.
- [ ] Drift simulated vs actual измерен и в допустимом диапазоне.
- [ ] Pre-Trading Security Gate полностью закрыт.
- [ ] Первая real-сделка на $100 исполнена, данные собраны.

---

## Параллельные треки (идут вдоль фаз)

### Tech-debt Prune Track

Over-engineering сам не уйдёт — нужен явный запланированный проход.

- Prune `src/features/` (158 файлов / ~28.7k строк → цель ~6–8k). Дубли `presets/` ↔ `schema/`, лишние подпакеты.
- Prune `src/market_selection/` (30+ файлов на задачу «найти 30 ликвидных perp»).
- Заморозить `src/ml/metalabeling/` — не развивать до v2.

### Determinism & Failure-mode Audit

- Прогнать feature pipeline дважды на одних данных → diff результата.
- Проверить все чтения из БД, влияющие на features/signals, на явный `ORDER BY`.
- Зафиксировать политику: data quality anomaly = terminal (fail-loud).

### Learning Track (явно отделён от critical path)

Делается ради обучения, не ради продукта — не путать learning value с business
value. Сюда относятся: Airflow (для 5 DAG достаточно cron — оставлен как
DE-навык), DDD-слои. Эти решения легитимны как обучение, но не должны
обосновываться продуктовой необходимостью.

---

## Отложено в v2

После того как хотя бы одна стратегия покажет позитивный walk-forward:

- `src/execution/` — ExecutionPort / CostModel / BacktestExecutor / `execution_runs`.
  В v1 не нужно: исполнение ручное, достаточно `simulate_fill()`-функции.
- Risk & OMS maturity: portfolio limits, partial-fill/timeout/cancel-all сценарии, stress-tests.
- ML metalabeling iteration — после накопления decision-log и 200+ сделок.
- Deployment: CI/CD canary, rollback strategy, version pinning.
- Observability stack: Grafana / Prometheus (в v1 — Telegram-алертов достаточно).
- Auto-execution, multi-exchange, рост капитала (см. Non-goals).

### Library Backlog (v2)

> Полный анализ: `docs/ideas/library_replacement_recommendations.md`

| Библиотека | Заменяет | Фаза |
|------------|----------|------|
| `vectorbt` | `backtest/metrics.py` (`calc_pnl`) | B6 (адаптация) |
| `quantstats` | `backtest/metrics.py` + `report.py` | B6 |
| `TA-Lib` / `ta` | `features/ta_safe/fallback.py` | v2 |
| `mlfinlab` / `skfolio` | `ml/labeling/`, `ml/validation/` | v2 (после A2) |
| `hmmlearn`, `ruptures` | `mtf/context/algorithms.py` | v2 |
| `alembic` | `db/migrations/migrate_*.py` | v2 |

Не заменять: `signals/`, `mtf/consensus/`, `positions/calculator.py`,
`risk/guards/sla_guards.py`, `deflated_sharpe_ratio()`, `ml/metalabeling/`,
`features/indicator_groups/`.

---

## Architecture Boundaries

Жёсткие границы, чтобы проект не разрастался обратно:

1. **Signal layer изолирован от execution.** `signals` → `signal_decisions` → `manual_trades`. Manual decision позже заменяется на paper/live без переписывания signal-слоя.
2. **domain → application → infrastructure** — соблюдать. Новые bounded-контексты не плодить.
3. **Two-track features:** `research/` (голые функции, для notebook) ↔ `indicator_groups/` (promoted, с контрактами/тестами/миграцией).
4. **Notebook ≠ production logic.** Labeling/backtest/features/signals — только в `src/`.
5. **Adopt > build для quant-математики.** vectorbt/quantstats вместо custom. Custom — только для стратегической специфики.
6. **Один источник конфигурации** — `src/config/settings.py`. Никаких россыпей `os.getenv()`.
7. **Нет `src/execution/` в v1.** Backtest execution = функция `simulate_fill(signal, bar, fee, slippage)`.
8. **Agent-output gate.** Код от агента не вливается в `main`, пока нет теста и пока автор не может объяснить, что код делает. Это граница против over-engineering.

---

## Definition of Done (единый, для задач)

Задача завершена, только если:
- есть тесты (unit/integration; где нужно — property-based / numerical-equivalence);
- публичные контракты типизированы;
- `make check` зелёный;
- есть метрики/логи для нового behavior (где применимо);
- обновлена документация;
- есть миграция при изменении схемы БД (новый файл, не правка существующего);
- автор может объяснить, что делает каждая строка.

---

## Success Criteria для v1

v1 достигнут, когда закрыты все 5 гейтов.

**Gate 1 — Data Trust:** ingest 30 дней без вмешательства; hole-rate < 0.1%,
dup-rate = 0; проверенный restore из бэкапа; double-run тесты всех DAG зелёные.

**Gate 2 — Research Integrity:** `ml/labeling`+`ml/validation` под тестами;
look-ahead тест в `make check`; `make check` зелёный, coverage критичных
модулей ≥ 80%; эксперимент воспроизводим байт-в-байт.

**Gate 3 — Research Loop:** ≥ 10 гипотез через единый pipeline с `runs/`;
сравнение с 5 baseline; reject gates автоматические; ≥ 1 гипотеза прошла
WF + CPCV + DSR с positive expectancy после fees.

**Gate 4 — Signal→Decision Loop:** сигнал → `signals` → Telegram; решения в
`signal_decisions`; signal-to-trade conversion считается; paper logger накопил
≥ 30 сигналов; drift измерен.

**Gate 5 — Pre-Trading:** OKX key no-withdraw + IP whitelist + вне `.env`;
paper/live разделение; cancel-all / revoke процедура проверена.

### Числовые пороги (зафиксировать ДО тестирования)

- **Стратегия «перспективна»:** WF Sharpe выше baseline по risk-adjusted метрикам **и** DSR > 0 **и** max DD < [TODO: порог] **и** стабильность по WF-окнам.
- **Триггеры роста капитала:** $100 → $1000 после [TODO: N] paper-сделок с positive expectancy; $1000 → $10000 после [TODO: M] real-сделок, подтверждающих paper. Целевой рабочий капитал — $10 000. **N, M, порог DD назначаются владельцем — пока не определены.**

---

## KPI

- **Reliability:** доля успешных DAG run, % idempotent reruns (доказано тестами).
- **Data:** freshness, hole-rate, dup-rate, fill-rate.
- **Reproducibility:** доля экспериментов, воспроизводимых через `runs/` артефакты.
- **Research quality:** доля гипотез, прошедших CPCV/DSR-гейты против baseline.
- **Trading quality** (с Phase C): IS bps, slippage drift, signal-to-trade conversion.
- **Engineering:** coverage критичных модулей, разрыв между написанным и протестированным кодом (цель — 0).

---

## Контроль исполнения

- Еженедельный review: обновление статусов `planned/in_progress/blocked/done`.
- Каждый блокирующий риск фиксируется с датой mitigation.
- Новый код от агента проходит agent-output gate (см. Architecture Boundaries §8).

## Легенда статусов

| Символ | Значение |
|--------|----------|
| ✅ | Завершено |
| 🟡 | В работе / частично |
| 🔴 | Не начато / блокер / критичный риск |
| ⚪ | Запланировано / заморожено |

---
*Roadmap 3.0 — результат discovery-аудита. Последнее обновление: 2026-05-20.*
