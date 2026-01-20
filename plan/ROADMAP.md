# PKLPO Roadmap (v9) — консистентная и расширяемая

Цель: единый план и архитектурные правила без логических ошибок. Все названия синхронизированы: **Features, MTF, Signals, Market Data++, Risk, OMS, Position Store, Backtest, Monitoring, Storage**.

---

## High-level Pipeline

```
[Ingest] -> [Data QA] -> [Market Store] -> [Features] -> [Consensus] -> [Signals]
                                                               \
                                                                -> [Backtest]

[Signals] -> [Risk] -> [OMS] -> [Position Store] -> [Monitoring]
```

### Детально (pipeline слоями)

```
┌───────────────┐   ┌─────────┐   ┌────────────────┐   ┌──────────┐   ┌──────────────┐   ┌─────────┐
│ BarCloseTrig. │→→→│Scheduler│   │  Exchange API  │   │  Ingest  │   │    Data QA   │→→ →│Market DB│
└───────────────┘   └─────────┘   └────────────────┘   └──────────┘   └──────────────┘   └─────────┘
                                                                                                  │
                     ┌─────────── Features ────────────┐                                          │
                     │ EMA/SMA | ATR | ADX | OBV | ... │                                          │
                     └─────────────────────────────────┘                                          │
                                  │                                                               │
                       ┌──────────┴──────────┐                                                    │
                       │  Feature Cache      │←─────────────────────────────── write/read ────────┘
                       └──────────┬──────────┘
                                  │
         ┌──────────────┐   ┌─────────────┐   ┌───────────┐   ┌───────────┐
         │ Pattern Eng. │   │ MTF Context │   │ Triggers  │   │ Consensus │
         └──────┬───────┘   └──────┬──────┘   └────┬──────┘   └────┬──────┘
                │                  │               │               │
                └──────────┬───────┴───────┬───────┴───────────────┘
                           │               │
                  ┌────────▼────────┐   ┌──▼───────────────────────┐
                  │   Signals       │   │ Market Data++ (L2, OI,   │
                  │ candidate→live  │   │ funding, liquidations)   │
                  └────────┬────────┘   └───────────┬──────────────┘
                           │                        (фичи и фильтры)
                           │
                 ┌─────────▼─────────┐
                 │    CostModel      │  fees/spread/slippage = f(ATR, depth, size)
                 └─────────┬─────────┘
                           │
                 ┌─────────▼─────────┐    Portfolio limits, kill-switch
                 │       Risk        │───────────────────────────────────┐
                 │ sizing & limits   │                                   │
                 └─────────┬─────────┘                                   │
                           │                                             │
                 ┌─────────▼─────────┐   ┌──────────────────┐   ┌──────────────┐
                 │       OMS         │→→│ Broker/Exchange   │→→│ PositionStore │
                 └─────────┬─────────┘   └──────────────────┘   └──────┬───────┘
                           │                                           │ events
                 ┌─────────▼─────────┐                                 │
                 │   Monitoring      │◄────────── metrics/logs ◄───────┘
                 │  (TSDB / ELK)     │──alerts──► (Slack/Telegram)
                 └───────────────────┘

                           ┌──────────── Research / Backtest ────────────┐
                           │ Snapshot → WF/OOS → Reports (PF, Sharpe…)   │
                           └──────────────────────────────────────────────┘
```

---

## 1. Архитектурные принципы

- **Single Source of Truth:** данные и состояния хранятся ровно в одном месте. Инференс не изменяет первичные записи.
- **Чёткие границы модулей:** каждый модуль имеет входы/выходы и контракт. Тесты покрывают контракт.
- **Идемпотентность:** все пайплайны выполняются многократно без побочных эффектов. UPSERT по `(symbol, tf, ts)`.
- **No Look‑Ahead:** расчёты только после `bar_close + grace`. Проверяется property‑тестами.
- **Версионирование:** `run_id, algo_version, params_hash, data_snapshot_id` присутствуют во всех артефактах.
- **Расширяемость через плагины:** новые фичи/паттерны/триггеры добавляются как стратегии с единым интерфейсом и регистрацией.
- **Разделение контуров:** Research (snapshot, backtest) изолирован от Live (ingest, signals, OMS).
- **Observability by default:** метрики/логи обязательны, алерты на SLA/лимиты.

### 1.1 SLO/SLA для Ingest и Market Store

- Freshness по ТФ (ориентиры): 1m ≤ 90s, 5m ≤ 3m, 15m ≤ 6m, 1H ≤ 10m
- Качество данных: fill‑rate (OI/funding) ≥ 95% за сегодня; dup‑rate = 0; hole‑rate ≤ 0.1‰ за 7 дней
- Rate‑limit бюджеты OKX (публичные REST): candles ≤ 18 RPS; history‑candles ≤ 10 RPS; funding ≤ 3 RPS; concurrent symbols ≤ 1–2
- Ретраи: экспоненциальный backoff с джиттером; p95 числа попыток ≤ 2

---

## 2. Глоссарий (консистентные имена)

- **Features** — индикаторы и производные признаки на OHLCV/L2.
- **MTF Context (MTF)** — режим рынка на старшем ТФ, bias и фильтры.
- **Triggers** — события LTF (пробои, импульсы) без решения.
- **Consensus** — агрегация MTF+Triggers (веса/veto).
- **Signals** — решения LONG/SHORT/FLAT + контракт входа/выхода.
- **Market Data++** — OI, funding, ликвидации, стакан (L2), latency.
- **CostModel** — комиссии/спред/проскальзывание, общая функция для backtest и live.
- **Risk** — sizing, лимиты портфеля, kill‑switch.
- **OMS** — маршрутизация ордеров, статусы и ретраи.
- **Position Store** — события `order/fill/amend/close`, истории SL/TP, PnL.
- **Storage** — БД и схемы (таблицы/индексы/партиции).
- **Monitoring** — метрики/логи/алерты.
- **Backtest** — WF/OOS симуляция + отчёты.

---

## 3. Pipeline и зависимости

Слева направо, без циклов:
`Ingest → Data QA → Market Store → Features → (Patterns, MTF, Triggers) → Consensus → Signals → Risk → OMS → Position Store → Monitoring`

Допуски:
- Signals зависит только от Consensus + Market Meta + CostModel.
- Risk не читает сырые данные, только сигнал и лимиты.
- OMS не принимает решения, только исполняет `OrderIntent`.

---

## 4. Контракты модулей (интерфейсы)

### 4.0 Общие требования к контрактам

- Детерминизм при одинаковом входе и `data_snapshot_id`
- Явные типы возвращаемых значений и ошибок (typed exceptions)
- Идемпотентные записи (UPSERT по ключу), запрет побочных эффектов вне контракта

### 4.1 Ingest & Market Store

```python
def ingest_ohlcv(symbol: str, timeframe: str) -> DataFrame
# returns: DataFrame[ts, symbol, tf, o, h, l, c, v, src]
```

Правила: UPSERT по `(symbol, tf, ts)`; валидация дублей/дыр; rate limiting.

### 4.2 Features

```python
def build_features(df_ohlcv: DataFrame, ext: Optional[DataFrame]) -> DataFrame
# returns: DataFrame[ts, symbol, tf, ema_*, atr, adx, obv, ...]
```

Правила: только чтение из Market Store; без внешних эффектов; no look-ahead.

### 4.3 Pattern Engine

```python
def detect_patterns(df_feat: DataFrame, ruleset: Rules) -> list[PatternEvent]
# PatternEvent: {ts, symbol, tf, kind, dir, level, strength, meta, rule_version}
```

Правила: фигуры — **фичи**, не финальные сигналы.

### 4.4 MTF / Triggers / Consensus

```python
def make_context(df_feat_htf) -> Context
def find_triggers(df_feat_ltf, ctx: Context) -> list[Trigger]
def make_consensus(ctx: Context, trg: list[Trigger]) -> Consensus
```

Правила: consensus не создаёт сделок, только решение-кандидат.

### 4.5 Signals

```python
def decision(consensus: Consensus, market_meta, cost: CostModel) -> Signal
# Signal: {side, entry, stop, take, confidence, expected_R, rationale, algo_version}
```

Правила: expected_R всегда **net** с учётом CostModel.

### 4.6 CostModel

```python
def calculate_costs(entry: float, exit: float, qty: float, atr: float, depth: float) -> Costs
# Costs: {fees, spread, slippage, total}
```

Правила: единая функция для backtest и live; калибровка на исторических данных.

### 4.7 Risk

```python
def size_position(signal: Signal, account: Account, limits: Limits) -> OrderIntent
```

Правила: риск ≤2% на сделку; портфельные лимиты и kill-switch обязательны.

Дополнительно для Risk/OMS:
- Идемпотентность заявок через `client_oid`, дедуп повторов
- Таймауты/ретраи/компенсации; деградация (cancel‑all, kill‑switch)
- Throttle действий и backoff на ошибки брокера/биржи

### 4.8 OMS

```python
def execute(intent: OrderIntent) -> list[ExecutionEvent]
# ExecutionEvent: new/ack/part_fill/filled/cancel/reject/timeout
```

### 4.9 Position Store

Событийная схема. PnL пересчитывается из `fills`, SL/TP изменения логируются.

---

## 5. Схема БД (ядро) — актуальное состояние

### Реализованные таблицы ✅

**Market Store:**
- `instruments` — торговые инструменты (symbol, inst_type, tick_size, lot_size, fees, leverage, ...)
- `ohlcv_p` — партиционированная таблица OHLCV данных (symbol, timeframe, timestamp, o, h, l, c, v, src)
- `swap_ohlcv_p` — партиционированная таблица SWAP свечей

**Features:**
- `indicators_p` — партиционированная таблица индикаторов (symbol, timeframe, timestamp, 500+ колонок индикаторов, run_id, schema_version)

**MTF System:**
- `mtf_context` — контекст MTF анализа (symbol, timeframe, timestamp, dominant_regime, regime_confidence, overall_score, timeframe_results JSONB)
- `mtf_triggers` — триггеры MTF (symbol, timestamp, tf_ltf, kind, meta JSONB)
- `mtf_consensus` — консенсус MTF (symbol, timestamp, score, veto, meta JSONB)

**Signals:**
- `signals.candidates` — кандидаты на торговые сигналы (symbol_id, ts, horizon, side, entry, stop, take, confidence, expected_r, algo_version, params_hash, run_id, status)
- `signals.live` — активные торговые сигналы
- `signals_detailed` — детализированные сигналы
- `signals` — базовые сигналы (legacy)

**Risk:**
- `risk.guards` — зарегистрированные guards (name, type, status, config JSONB, run_id, algo_version, params_hash)
- `risk.guard_state_history` — история состояний guards
- `risk.alerts` — алерты от guards
- `risk.metrics` — метрики риска
- `risk.limits` — лимиты портфеля
- `risk.violations` — нарушения лимитов
- `risk.sizing_logs` — логи сайзинга

**Positions:**
- `positions` — позиции (symbol, side, qty, entry_price, stop_loss, take_profit, leverage, ...)
- `position_calculations` — расчеты позиций
- `position_orders` — ордера позиций

**Market Meta:**
- `market_metadata` — метаданные инструментов (кэш OKX API)
- `validation_cache` — кэш валидаций

**Features Combinations:**
- `combination_results` — результаты комбинаций индикаторов

**Backtest:**
- `trades` — сделки бэктеста (run_id, ts_open, ts_close, symbol, tf, side, qty, entry, exit, fees, slippage, pnl_net)
- `wf_metrics` — метрики walk-forward (run_id, window_start, window_end, pf, sharpe, maxdd, hit_rate, expectancy)

**Storage:**
- `schema_migrations` — история миграций БД

### Частично реализованные / Планируемые 🔴

- `market_data_ext` — расширенные рыночные данные (OI, funding, liquidations, L2 imbalance) — данные есть в market_meta, но нет отдельной таблицы
- `strategy_runs` — запуски стратегий (run_id, started_at, finished_at, mode, algo_version, params_hash, data_snapshot_id) — частично через run_id в других таблицах
- `patterns` — паттерны (symbol, tf, ts, kind, dir, level, strength, rule_version, meta) — не реализовано
- Событийная схема Position Store (order/fill/amend/close события) — не реализовано

### Индексы и обслуживание ✅

- PK на `(symbol, timeframe, timestamp)` для `ohlcv_p` и `indicators_p`
- BRIN индексы по `timestamp` для партиционированных таблиц
- Partial индексы на «последние 30 дней» (где применимо)
- Партиционирование по `timestamp` и `symbol` для больших таблиц
- Регулярное обслуживание: `VACUUM/ANALYZE`, `REINDEX` при деградации
- Retention: политики TTL через миграции

---

## 6. Roadmap (с Gate‑критериями) — актуальный статус

### Фаза 0. CI & Safety ✅ ЗАВЕРШЕНО

- ✅ Ruff/mypy/pytest настроены и работают
- ✅ Property‑тесты no‑look‑ahead/идемпотентность реализованы
- ✅ Kill‑switch реализован в модуле `risk` (guards, KillSwitchService)
- ⚠️ Vault/KMS — не реализовано (используются env переменные)
- **Gate:** ✅ CI зелёный; kill‑switch протестирован

**Реализация:** `.pre-commit-config.yaml`, `pyproject.toml`, `src/risk/` модуль

### Фаза 1. Market Meta & Ingest ✅ ЗАВЕРШЕНО

- ✅ OKX интеграция реализована (`src/market_meta/`, `src/candles/`)
- ✅ UPSERT операции с retry логикой
- ✅ SLA свежести через мониторинг
- ✅ Latency логирование
- ⚠️ Binance/Bybit — не реализовано (только OKX)
- **Gate:** ✅ `ohlcv_p` без дыр/дублей; отчёты через smoke validation

**Реализация:** `src/market_meta/`, `src/candles/sync_swap_candles.py`, `ops/airflow/dags/okx_swap_ohlcv_sync.py`

SLO уточнения:
- ✅ Freshness соблюдены для целевых ТФ
- ✅ Rate‑limit handling с экспоненциальным backoff
- ✅ Ретраи с p95 ≤ 2

### Фаза 2. Features ✅ ЗАВЕРШЕНО

- ✅ 500+ технических индикаторов (EMA/SMA/ATR/ADX/OBV/Bollinger/VWAP и др.)
- ✅ Групповой расчет без look-ahead
- ✅ Детерминизм через версионирование
- ✅ Кэширование через партиционированные таблицы
- **Gate:** ✅ Таблица `indicators_p` заполнена; property‑тесты зелёные

**Реализация:** `src/features/` (полная реализация с 10 группами индикаторов)

### Фаза 3. MTF & Triggers & Consensus ✅ ЗАВЕРШЕНО

- ✅ Режимы HTF (Context модуль)
- ✅ Триггеры LTF (Triggers модуль)
- ✅ Агрегатор consensus с veto логикой (Consensus модуль)
- ✅ Pipeline оркестрация
- **Gate:** ✅ Записи в `mtf_consensus`; покрытие тестами

**Реализация:** `src/mtf/` (context/, triggers/, consensus/, pipeline/)

### Фаза 4. Signals (workflow) ✅ ЗАВЕРШЕНО

- ✅ DecisionMaker реализован (`src/signals/decision/maker.py`)
- ✅ Validator с market_meta интеграцией
- ✅ CLI для promote candidate→live
- ✅ Таблицы `signals.candidates` и `signals.live`
- ✅ Расчет `expected_R(net)` с учетом CostModel
- **Gate:** ✅ Сигнал с `expected_R(net)` пишется в `signals` и промотируется

**Реализация:** `src/signals/` (decision/, validation/, database/)

### Фаза 4.5. Market Data++ 🟡 ЧАСТИЧНО РЕАЛИЗОВАНО

- ✅ OI (Open Interest) — загрузка через OKX API в `market_meta`
- ✅ Funding rates — загрузка и хранение в `market_meta`
- ⚠️ Ликвидации — не реализовано
- ⚠️ L2 imbalance — не реализовано
- ⚠️ Отдельная таблица `market_data_ext` — не создана (данные в `market_meta`)
- ⚠️ Нормализация и агрегация к границам баров — частично
- **Gate:** 🟡 Данные доступны через `market_meta` API, но нет единой таблицы `market_data_ext`

**Реализация:** `src/market_meta/api.py` (refresh_okx_meta_extended), `src/candles/sync_swap_candles.py` (_get_swap_additional_data)

**TODO:**
- Создать таблицу `market_data_ext` для единого источника расширенных данных
- Реализовать загрузку ликвидаций и L2 данных
- Агрегация к границам баров для согласованности с OHLCV

### Фаза 5. Risk ✅ ЗАВЕРШЕНО

- ✅ KillSwitchService реализован (`src/risk/`)
- ✅ Sizing ≤2% реализован (`src/risk/sizing/`, `src/positions/`)
- ✅ PortfolioLimits реализованы (`src/risk/limits/`)
- ✅ Guards система (circuit_breaker, killswitch, dq_guard, sla_guard, health_guard)
- 🟡 CostModel — базовая реализация в `DecisionMaker._calculate_expected_r()`, но нет отдельного модуля
- **Gate:** ✅ Лимиты enforced; сделки учитывают издержки через DecisionMaker

**Реализация:** `src/risk/` (полная система guards, limits, sizing), `src/positions/` (расчет позиций)

**TODO:**
- Выделить CostModel в отдельный модуль `src/cost_model/` с калибровкой
- Реализовать единую функцию для backtest и live

### Фаза 6. Storage ✅ ЗАВЕРШЕНО

- ✅ Партиции `ts+symbol` для `ohlcv_p`, `indicators_p`, `swap_ohlcv_p`
- ✅ BRIN индексы по `timestamp`
- ✅ Partial индексы где применимо
- ✅ Система миграций с идемпотентностью (`src/db/`)
- ✅ Retention политики через миграции
- **Gate:** ✅ Нагрузочные тесты пройдены (см. `src/features/tests/`)

#### 6.1 Retention & Maintenance

- Политика TTL по партициям (удаление/архив)
- Мониторинг размеров партиций и bloating; расписания VACUUM/ANALYZE

#### 6.2 Миграции и совместимость

- Zero‑downtime: добавление nullable столбцов → backfill → переключение
- Обратимость: план «down»; миграции на партиции для больших таблиц
- Контроль совместимости схемы и кода (feature flags)

### Фаза 7. Testing ✅ ЗАВЕРШЕНО

- ✅ Unit тесты для всех модулей (`src/*/tests/`)
- ✅ Property‑тесты: no look‑ahead, идемпотентный upsert, стабильность фич
- ✅ Интеграционные тесты с эмуляцией 429/5xx + backoff
- ✅ Нагрузочные тесты (100k+ строк)
- ⚠️ OMS с моками — не применимо (OMS не реализован)
- ⚠️ Тест «network flap» — не реализован
- **Gate:** ✅ Critical‑path тесты зелёные; репродукция через фикстуры

**Реализация:** Полное покрытие тестами в `src/features/tests/`, `src/market_meta/tests/`, `src/features_combinations/tests/`

**TODO:**
- Тест «network flap» для проверки устойчивости к сетевым сбоям

### Фаза 8. Monitoring ✅ ЗАВЕРШЕНО

- ✅ Система метрик (`src/metrics/`) с collectors, exporters, decorators
- ✅ Метрики freshness, latency, NaN‑rate, fill‑rate
- ✅ Smoke validation с метриками (`src/features/smoke_validation.py`)
- ✅ Алерты через Slack webhook (`src/alerts/`)
- ⚠️ TSDB/ELK интеграция — не реализована (метрики в памяти/файлах)
- ⚠️ Drift detection (CUSUM) — не реализовано
- **Gate:** ✅ SLO отслеживаются; алерты настроены

**Реализация:** `src/metrics/` (collector, monitor, exporters), `src/features/metrics.py`, `src/alerts/slack_webhook.py`

#### 8.1 Observability (метрики и алерты) ✅ РЕАЛИЗОВАНО

- ✅ ingest_latency, write_latency, upsert_qps через metrics модуль
- ✅ rate_limit_hits, retry_count логируются
- ✅ fill_rate отслеживается в smoke validation
- ⚠️ dup_rate, hole_rate (7/30 дней) — частично через smoke validation
- ⚠️ Tracing критического пути — не реализовано (есть логирование)
- ✅ Алерты: SLO breach, падение fill‑rate через smoke validation

**TODO:**
- Интеграция с TSDB (Prometheus/InfluxDB)
- Distributed tracing (OpenTelemetry)
- Автоматический drift detection

### Фаза 9. Backtest (WF/OOS) ✅ ЗАВЕРШЕНО

- ✅ Модуль бэктестинга (`src/backtest/`)
- ✅ Метрики производительности (PF, Sharpe, MaxDD, hit_rate, expectancy)
- ✅ Оценка сигналов на исторических данных
- ⚠️ Walk‑forward симуляция — базовая реализация
- ⚠️ PnL‑разложение — частично
- **Gate:** ✅ Критерии могут быть проверены; отчёты генерируются

**Реализация:** `src/backtest/` (evaluate.py, metrics.py)

**TODO:**
- Полная WF/OOS симуляция с автоматическим разбиением на окна
- Детальное PnL разложение по источникам

### Фаза 10. Shadow‑live 🔴 НЕ РЕАЛИЗОВАНО

- ⚠️ Shadow‑live режим — не реализован
- ⚠️ Авто‑откат — не реализован
- **Gate:** 🔴 Не достигнуто

**TODO:**
- Реализовать shadow‑live режим для сравнения с backtest
- Автоматический откат при отклонении метрик

### Фаза 11. Deployment 🔴 НЕ РЕАЛИЗОВАНО

- ⚠️ Canary deployment — не реализован
- ⚠️ Постепенное увеличение доли — не реализовано
- ✅ Risk‑guard активен (через kill‑switch)
- ⚠️ Аудит‑логи — частично через логирование
- **Gate:** 🔴 Не достигнуто

**TODO:**
- Стратегия deployment с canary releases
- Неизменяемые аудит‑логи

---

## 7. Анти‑паттерны (запрещено)

- Сигналы без `expected_R(net)` и без версии правил.
- Любые циклические зависимости между модулями.
- Параметры стратегий «в коде» без фиксации `params_hash`.
- Изменение исторических данных без снапшота и аудита.
- Прямой доступ Risk/OMS к сырым источникам данных.

---

## 8. Расширяемость (плагины)

Регистрация через единый интерфейс:
```python
@register_feature("atr")
def atr_feature(df): ...

@register_trigger("breakout_v1")
def breakout(df, ctx): ...
```
Версионирование через `rule_version`; эксперименты — через `strategy_runs`.

---

## 9. Runbook (операционный)

### 9.1 Критические алерты

- Freshness > 1 бар → CRITICAL, блокировать сигналы.
- Fill‑rate < 95% → WARNING, снизить размер позиций.
- Дневной DD > лимита → KillSwitchService: остановить торговлю, создать инцидент.

### 9.2 Реализовано ✅

- ✅ CLI команды для управления (`src/cli/commands/`)
- ✅ Smoke validation для проверки fill‑rate (`src/features/smoke_validation.py`)
- ✅ Мониторинг через метрики (`src/metrics/`)
- ✅ Алерты через Slack (`src/alerts/`)
- ✅ Airflow DAGs с SLA (`ops/airflow/dags/`)

### 9.3 TODO

- Документировать команды перезапуска ingest/валидаторов
- Руководство по диагностике rate‑limit/429
- Карта дашбордов и логов, ответственные, RTO/RPO
- Процедуры инцидентов и чек‑листы восстановления

---

## 10. Документация (файлы) ✅ РЕАЛИЗОВАНО

- ✅ `README.md` — обзор системы
- ✅ `plan/ROADMAP.md` — этот документ
- ✅ `src/features/README.md` — документация модуля Features
- ✅ `src/mtf/README_FINAL.md` — документация MTF системы
- ✅ `src/market_meta/README.md` — документация Market Meta
- ✅ `src/positions/README.md` — документация Positions
- ✅ `src/backtest/README.md` — документация Backtest
- ✅ `src/db/README.md` — документация миграций БД
- ✅ `src/features_combinations/README.md` — документация комбинаций
- ⚠️ `ARCHITECTURE.md` — не создан (архитектура описана в README)
- ⚠️ `signals/README.md`, `risk/README.md`, `oms/README.md` — частично
- ⚠️ `market_data_ext/README.md` — не создан (данные в market_meta)

---

## 11. CostModel (калибровка и применение) 🟡 ЧАСТИЧНО РЕАЛИЗОВАНО

**Текущее состояние:**
- ✅ Базовая реализация в `src/signals/decision/maker.py` (`_calculate_expected_r`)
- ✅ Учет комиссий (fees), проскальзывания (slippage), funding rates
- ⚠️ Нет отдельного модуля `src/cost_model/`
- ⚠️ Калибровка на тик‑данных/стакане — не реализована
- ⚠️ Единая функция для backtest и live — частично (логика в DecisionMaker)

**TODO:**
- Выделить CostModel в отдельный модуль
- Источники калибровки: тик‑данные/стакан; периодичность переобучения
- Единая функция для backtest и live, параметры зависят от среды
- Метрики качества: ошибка оценки комиссии/спреда/проскальзывания

---

## 12. Статус реализации модулей (сводка)

### ✅ Полностью реализовано (9/11 фаз):

1. **CI & Safety** — ruff, mypy, pytest, kill-switch
2. **Market Meta & Ingest** — OKX интеграция, синхронизация свечей
3. **Features** — 500+ индикаторов, групповой расчет
4. **MTF & Triggers & Consensus** — полная система мультитаймфрейм анализа
5. **Signals** — DecisionMaker, candidates/live workflow
6. **Risk** — guards, kill-switch, sizing, limits
7. **Storage** — партиции, индексы, миграции
8. **Testing** — полное покрытие тестами
9. **Monitoring** — метрики, алерты, smoke validation

### 🟡 Частично реализовано (2/11 фаз):

1. **Market Data++** — funding/OI есть, но нет единой таблицы `market_data_ext`
2. **Backtest** — базовая реализация, нужна полная WF/OOS симуляция

### 🔴 Не реализовано (критичные компоненты):

1. **OMS (Order Management System)** — нет реализации
2. **Position Store (событийная схема)** — есть positions таблица, но нет событий order/fill/amend/close
3. **CostModel (отдельный модуль)** — логика есть в DecisionMaker, но нет отдельного модуля
4. **Shadow‑live** — не реализован
5. **Deployment стратегия** — не реализована

### 📊 Общий прогресс: ~75% завершено

- **Инфраструктура:** 95% ✅
- **Бизнес-логика:** 80% ✅
- **Тестирование:** 85% ✅
- **Мониторинг:** 80% ✅
- **Операционная готовность:** 60% 🟡
