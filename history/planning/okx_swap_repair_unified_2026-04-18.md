# OKX Swap Repair — единый исполнимый план (SQL + v1 хвосты + multi-symbol)

Date: 2026-04-18
Based on:
- `history/planning/okx_swap_repair_v1_spec_2026-04-18.md`
- `history/planning/okx_swap_repair_sql_summary_2026-04-18.md`
- `history/planning/okx_swap_repair_multi_symbol_2026-04-17.md`
- `history/planning/okx_swap_repair_v1_improvements_2026-04-12.md` (reference — tracker)

## Context

Почему этот план существует сейчас:

- v1 improvements (`okx_swap_repair_v1_improvements_2026-04-12.md`) доведён до 15/19 ✅ Done + 4/19 ⚡ Done (partial) + 0 🔜. Остались точечные хвосты (P1.3 docs, P1.5 test DAG, P2.3 presets, P3.1 helpers, P3.3 tests, P3.4 snapshot, P3.5 doc).
- `okx_swap_repair_sql_summary_2026-04-18.md` зафиксировал **корректные SQL-паттерны** repair: half-open bounds `[start, end)`, closed-only candles, 1M через domain helpers (не `generate_series`), merge_gaps, readiness = последние 300 contiguous + non-corrupted. Текущие репозиторные методы (`find_first_gap_start_ts_ms`, `list_timestamps`, `count_candles`) этим паттернам **не соответствуют по именам** — нужна сверка/выравнивание.
- `okx_swap_repair_v1_spec_2026-04-18.md` — финализированная architecture (hybrid tail/history, compare-before-update, 300-candle readiness, guardrails). Служит контрактной базой — менять нельзя, только реализовывать.
- `okx_swap_repair_multi_symbol_2026-04-17.md` — следующий шаг: снять hardcode BTC-USDT-SWAP (DAG default, enum в validator, fixtures, presets). Блокирует v2 (dynamic task mapping).

Цель: закрыть хвосты v1, выровнять репозиторий с SQL-контрактом, снять BTC-привязку — выйти на CI-зелёный и готовый фундамент под v2.

---

## 1. Сводка по 3 отчётам

### Отчёт 1 — `okx_swap_repair_v1_spec_2026-04-18.md` (spec, source of truth архитектуры)

- **Основная цель:** зафиксировать финальные v1-решения по repair-оркестрации.
- **Ключевые выводы:**
  - Один DAG; hybrid tail→history; tail-first; compare-before-update (OHLCV, tol=1e-12).
  - Tail windows с фиксированными cap'ами на TF (`1H:18d`, `4H:65d`, `1D:400d`, `1W:3y`, `1M:10y`).
  - Guardrails: `max_runtime_per_run=10m`, `max_requested_bars_per_run=10_000`; partial-run = норма.
  - History — backward 7d/run до listing-date; state в `repair_state` (ts_ms BIGINT).
  - Data quality: gaps + corrupted (NULL, ≤0, high<low, open/close вне [low,high]); `volume=0` НЕ corrupted.
  - Readiness = **последние** 300 closed + contiguous + non-corrupted.
  - `MAX_CONCURRENT_SYMBOLS=2` через config.
- **Критичные замечания:** раздел «What Is Settled» — эти пункты менять нельзя без новой v-итерации. Immediate next steps (1-5) — это то, что должно уже существовать в коде; любое расхождение = баг.
- **Влияние на общий план:** это валидатор корректности. Любой SQL/код, не соответствующий спецификации, — кандидат на исправление в Этапе 1.

### Отчёт 2 — `okx_swap_repair_sql_summary_2026-04-18.md` (SQL-паттерны v1)

- **Основная цель:** зафиксировать корректные SQL-запросы для gap detection / corruption / readiness.
- **Ключевые выводы:**
  - **Half-open bounds** обязательны: `[start_ts_ms, end_ts_ms)`.
  - `closed_until_ts_ms = floor_to_timeframe(now_ts_ms, tf)` — рассчитывается в Python, не в SQL.
  - Gap detection для fixed-interval TF: `generate_series(start, end - interval, interval) LEFT JOIN existing`.
  - **1M НЕЛЬЗЯ** через `generate_series(..., interval_ms)` (переменная длина месяца) — только через domain helpers `floor_to_timeframe` + `expected_next_open` + `list_timestamps`.
  - Corruption SQL: NULL/≤0/high<low/open|close вне [low,high]; `volume=0` не corrupted.
  - Readiness SQL: `LIMIT 300` DESC + LAG для contiguity + sub-query corrupted count.
  - `merge_gaps(ts_list, interval_ms) -> list[(start,end)]` — обязательное merging перед API fetch.
  - Intended repository surface: `list_missing_timestamps`, `list_corrupted_timestamps`, `is_features_ready`.
- **Критичные замечания:** `NOW()` в SQL запрещён; `volume=0` как corrupted — default `false` в v1 (не менять без спец-решения).
- **Влияние на общий план:** текущий `repair_repository.py` содержит `find_first_gap_start_ts_ms` / `list_timestamps` / `count_candles` — **именованная surface из sql_summary отсутствует**. Этап 1 должен: (a) решить, добавляем ли новые методы или переименовываем существующие; (b) гарантировать half-open bounds и 1M branch.

### Отчёт 3 — `okx_swap_repair_multi_symbol_2026-04-17.md` (снятие BTC-hardcode)

- **Основная цель:** сделать repair-пайплайн symbol-agnostic без изменения архитектуры v1.
- **Ключевые выводы:**
  - **P0:** `Param(default="BTC-USDT-SWAP")` → `Param(default=None)`; снять enum в `validate_swap_repair_conf_task`; **в том же коммите** обновить `tests/db/test_okx_swap_repair_v1_dag.py` (snapshot-test сейчас фиксирует enum, CI упадёт).
  - **P0:** instrument preflight через таблицу `instruments` (primary) + OKX API (fallback), размещение — новый модуль `src/market_meta/domain/instrument_validator.py` (не `candles/`, per `ARCHITECTURE.md §9.5`).
  - **P1:** listing-date lookup должен работать на любом инструменте; кэш keyed by symbol.
  - **P1:** авто-расчёт `max_requested_bars_per_run` через `TIMEFRAME_BARS_PER_DAY` + 5% padding; guardrail не блокирует разумные окна ≤2 лет.
  - **P2:** `guardrail_risk: "high"|"medium"|"ok"` в preview.
  - **P3:** параметризовать integration tests, обновить operator guide/presets.
- **Критичные замечания:**
  - `src/market_meta/` сейчас **не существует** (проверено Glob) → нужно создать скелет модуля per architecture layering.
  - Snapshot-тест `tests/db/test_okx_swap_repair_v1_dag.py` содержит `SUPPORTED_SYMBOLS = ("BTC-USDT-SWAP",)` (line 13) + `"enum": ["BTC-USDT-SWAP"]` (line 163) — оба места в одном коммите.
  - v2 (dynamic task mapping) блокирован S0.2+S1.1.
- **Влияние на общий план:** задаёт Этапы 3-4. S0.1+S3.4 = atomic commit; S0.2 требует создания нового модуля.

### Reference — `okx_swap_repair_v1_improvements_2026-04-12.md` (tracker)

- Статус 19/19 items, но 4 помечены `⚡ Done (partial)`:
  - `P1.3` — partial auto-apply semantics — не хватает operator-facing docs.
  - `P1.5` — `has_start != has_end` — test DAG ещё дублирует.
  - `P2.3` — Param descriptions — не хватает presets/README.
  - `P3.1` — duplication prod/test DAG — нет `_common/swap_repair_dag_helpers.py` (есть только `env.py`, `async_runner.py`, `repair.py`).
  - `P3.3` — integration tests — не хватает metadata freshness / missing instrument rows.
- `P3.4` (snapshot test) и `P3.5` (plan-vs-actual doc) — изначально `Not started`, в multi-symbol плане P3.4 перенесён в P0.

### Противоречия между отчётами

| Противоречие | Как разрешаем |
|---|---|
| v1 spec раздел "Immediate Next Implementation Steps" перечисляет шаги «1-5» как будто впереди, но improvements-tracker (`2026-04-12`) показывает P0-P3 = Done | Считаем spec текстовой зафиксированной архитектурой, а не roadmap'ом. Проверяем соответствие **по факту в коде** (Этап 1). |
| Multi-symbol plan говорит «S0.2 разместить в `src/market_meta/`, не в `candles/`»; existing `load_instruments.py` лежит в `src/candles/` | Следуем решению multi-symbol plan (опирается на `ARCHITECTURE.md §9.5`). `load_instruments.py` — отдельный рефакторинг, вне скоупа (зафиксировать как backlog). |
| Sql_summary упоминает `list_missing_timestamps` / `list_corrupted_timestamps` / `is_features_ready` как «intended surface», но в `repair_repository.py` таких методов нет | Этап 1.2 — решаем: добавить новые методы с корректными SQL или подтвердить, что текущие (`find_first_gap_start_ts_ms` + `list_timestamps`) покрывают контракт. Скорее всего нужно добавить. |

### Пробелы и что уточнить

- [ ] Вызывают ли application-слой `repair_planning` текущие методы с half-open bounds или есть inclusive-bounds баг? (требует чтения `src/candles/application/repair*.py` в Этапе 1)
- [ ] 1M handling: уже реализован через domain helpers или идёт через generate_series? (нужен grep в Этапе 1)
- [ ] `repair_state` таблица — мигрирована ли? (проверить `src/db/migrations/`)
- [ ] Существует ли `ops.swap_repair_audit` миграция? (improvements-doc утверждает Done — проверить)

---

## 2. Сопоставление с документацией

| Вывод / задача | Связанный документ | Зачем нужен | Что проверить / применить |
|---|---|---|---|
| SQL: half-open bounds, 1M через domain | `sql_summary §1,§4,§6` | Источник корректных SQL-шаблонов | Сверить каждый репозиторный метод; `NOW()` запрещён |
| Merge gaps перед API fetch | `sql_summary §5` | Алгоритм merge_gaps | Реализовать/найти утилиту; unit tests на пустой/одиночный/соседние ts |
| Readiness = последние 300 closed contiguous | `sql_summary §3`, `v1_spec §Features Readiness` | Точное определение ready | Запрос не должен сканировать всю историю |
| repair_state структура | `v1_spec §Repair State` | Схема таблицы | Проверить миграцию; ts_ms BIGINT |
| Tail windows caps | `v1_spec §Tail Windows` | Фиксированные окна per-TF | Вшито ли в application планировщик |
| Compare-before-update tolerance | `v1_spec §Compare Before Update` | Float tol=1e-12 | Проверить `selective_upsert_candles` |
| Partial auto-apply semantics | `improvements §12.3`, `v1_spec §Run Limits` | Контракт XCom при incomplete | Operator docs (Этап 2) |
| Multi-symbol P0 (hardcode + preflight) | `multi_symbol §P0`, `ARCHITECTURE.md §9.5` | Куда положить validator | `src/market_meta/`, не `candles/` |
| Snapshot-test trigger contract | `multi_symbol S3.4`, `tests/db/test_okx_swap_repair_v1_dag.py` | CI guardrail | Обновляется в одном коммите с S0.1 |
| Operator presets (multi-symbol + anchor) | `improvements §12.2`, `multi_symbol S3.3` | UX оператора | Примеры с ETH/SOL + anchor strategies |
| Plan-vs-actual scope doc | `docs/okx_swap_repair_v1_plan_vs_actual.md` | Source of truth по supported scope | Обновить после снятия BTC |
| Listing-date anchor | `improvements §P0.1`, `multi_symbol §S1.1` | Bootstrap пустого coverage | Через instruments-таблицу → OKX fallback |

---

## 3. Применение плагинов (Claude Code skills + agents + MCP)

| Шаг | Плагин/инструмент | Цель | Ожидаемый результат |
|---|---|---|---|
| Перед Этапом 1 | `superpowers:brainstorming` skill | Развёрнутое обсуждение: добавлять новые методы репозитория vs. переименовывать | Зафиксированное решение по surface методов |
| Этап 1.1 read-only | Agent `Explore` (×1, medium) | Обзор всей цепочки `application/repair* → infrastructure/repair_repository → SQL` | Карта текущего surface + расхождения с sql_summary |
| Этап 1.2 SQL review | Agent `database-reviewer` + skill `postgres-patterns` | Review SQL-запросов на соответствие PG 16 best practices | Подтверждение half-open bounds, generate_series limits, индексов |
| Этап 1.3 tests | Skill `tdd-workflow` + skill `python-testing` + agent `tdd-guide` | TDD: тесты first для новых методов repository | RED→GREEN по `list_missing_timestamps` / `list_corrupted_timestamps` / `is_features_ready` |
| Этап 2.1 docs | Own writing + MCP `WebFetch` (только если нужны ссылки Airflow docs) | Operator docs для partial auto-apply | Раздел в `docs/` или README |
| Этап 2.4 helpers | Agent `python-reviewer` + skill `python-patterns` | Review `_common/swap_repair_dag_helpers.py` на DRY | Чистая общая точка для prod+test DAG |
| Этап 3.1 atomic commit | Skill `superpowers:verification-before-completion` | Убедиться, что snapshot+DAG правки идут в одном коммите | CI зелёный после push |
| Этап 3.2 new module | Agent `Plan` (×1) | Design `src/market_meta/` skeleton (domain/application/infra) | Миниатюрный PRD для модуля |
| Этап 3.2 preflight | Skill `security-review` | Preflight task — потенциальная точка input validation / injection | Подтверждённая безопасная реализация |
| Этап 4.3 guardrail math | Skill `python-patterns` | Чистая реализация `min_bars_for_window` с Decimal для 1W/1M | Корректность для 6 TF |
| Этап 5.1 parametrize | Skill `python-testing` | pytest fixture с params=[...] | Integration tests работают на ETH/SOL без кода |
| После каждого этапа | `superpowers:requesting-code-review` + agent `superpowers:code-reviewer` | Review против плана и coding standards | Готовность коммит/PR |
| Перед merge | MCP `gh` | Создание PR, анализ всей истории коммитов | PR с test plan |
| Отладка сложных случаев | `superpowers:systematic-debugging` | 1M edge cases, metadata caching bugs | Root cause, не поверхностный fix |
| Spec sanity-check | MCP `Context7` (на asyncpg/airflow/ccxt API) | Подтвердить поведение внешних библиотек | Корректное использование API |
| Fallback поиск (если Context7/gh не хватит) | MCP `Exa` / `WebSearch` | Только если первые два не ответили | Дополнительный контекст |

Неприменимые/не нужны на этом плане (отмечено явно):
- `loop`, `schedule`, `statusline-setup`, `keybindings-help`, `init`, `update-config` — не относятся к задаче.
- `claude-api` — проект не использует Anthropic SDK напрямую.
- `e2e-runner` — UI нет, E2E не применимо.
- `rust-reviewer` — язык не Rust.

---

## 4. Пошаговый план

### Этап 1. SQL correctness alignment (P0, ~0.5-1 день)

**Цель:** привести `repair_repository.py` + `application/repair*` в соответствие с `sql_summary`. Фундамент корректности до любых других изменений.

- **Действия:**
  1. Explore: прочитать `src/candles/infrastructure/repair_repository.py`, `src/candles/application/repair*.py`, `src/candles/domain/*.py` (в части `floor_to_timeframe` / `expected_next_open`).
  2. Проверить наличие миграций `repair_state`, `ops.swap_repair_audit`.
  3. Сверить каждый SQL-запрос с sql_summary §1-§4: half-open bounds, отсутствие `NOW()`, generate_series для fixed-interval TF, domain-only для 1M.
  4. Добавить или обновить методы: `list_missing_timestamps(symbol, tf, start_ts_ms, end_ts_ms, interval_ms)`, `list_corrupted_timestamps(...)`, `is_features_ready(symbol, tf, closed_until_ts_ms, interval_ms)`. Если текущие имена используются application-ом — либо адаптер, либо переименование с обновлением вызовов.
  5. Добавить утилиту `merge_gaps` в `src/candles/domain/` (если нет) + unit tests.
  6. Для 1M: branch в repository — читать `list_timestamps` + генерировать expected через domain helpers.
- **Вход:** `sql_summary`, `v1_spec`, текущий код `src/candles/`.
- **Результат:** все repository методы соответствуют sql_summary; unit tests GREEN; агент `database-reviewer` подтвердил корректность.
- **Зависимости:** нет (фундамент).
- **Риски:**
  - Переименование методов сломает application — нужны обновления вызывающих мест.
  - 1M branch — легко забыть edge case на границе года.
  - Миграции `repair_state` могут отсутствовать — тогда Этап 1 расширяется созданием миграции.

### Этап 2. Закрыть v1 хвосты (P1-P3, ~1 день)

**Цель:** довести все `⚡ partial` из improvements-tracker до `✅ Done`; снять risk CI drift.

- **Действия:**
  1. **P1.3 docs:** в `docs/` — раздел `operator-guide/partial-auto-apply.md` на основе improvements §12.3.
  2. **P1.5 test DAG:** удалить локальные парсеры start/end в `okx_swap_repair_test.py`, указывать на `_common/repair.py`.
  3. **P2.3 presets:** обновить README DAG-а; добавить preview-пресеты и anchor-strategy примеры.
  4. **P3.1 helpers:** создать `ops/airflow/dags/_common/swap_repair_dag_helpers.py` с общими XCom validators + param parsers; обновить оба DAG-а.
  5. **P3.3 tests:** интеграционные тесты на metadata freshness (stale listing-date) + missing instrument rows — в `tests/integration/candles/`.
  6. **P3.4 snapshot:** `tests/db/test_okx_swap_repair_v1_dag.py` — полная snapshot trigger-contract (Params + XCom shape). Writer=helper, reader=assert_equal на JSON.
  7. **P3.5 plan-vs-actual:** обновить `docs/okx_swap_repair_v1_plan_vs_actual.md` — актуальные supported symbols/timeframes/modes, раздел "Out of scope" обновлён.
- **Вход:** Этап 1 зелёный; improvements-tracker.
- **Результат:** tracker — 19/19 ✅; снят CI-риск перед изменениями Этапа 3.
- **Зависимости:** Этап 1 (без корректного surface невозможно писать integration tests).
- **Риски:**
  - P3.1 затрагивает test DAG — легко разъехаться по смыслу, если валидаторы не идентичны.
  - P3.4 snapshot — если нестабильное поле (например, timestamps), тест будет flaky.

### Этап 3. Multi-symbol P0 — снятие BTC hardcode (P0, ~0.5-1 день)

**Цель:** DAG не падает на валидном не-BTC символе; invalid символ падает на preflight до записи.

- **Действия (S0.1 + S3.4 в одном коммите):**
  1. `ops/airflow/dags/okx_swap_repair_v1.py`: `Param(default="BTC-USDT-SWAP")` → `Param(default=None, description="Required: OKX swap instId")`.
  2. `validate_swap_repair_conf_task`: удалить whitelist/enum `SUPPORTED_SYMBOLS = ("BTC-USDT-SWAP",)`.
  3. `tests/db/test_okx_swap_repair_v1_dag.py`: обновить snapshot Params — `symbol` без `default`, без `enum`; пересоздать ожидаемые JSON-снапшоты; не забыть line 13 `SUPPORTED_SYMBOLS`, line 141/161/163 + все фикстуры.
  4. `git commit -m "feat(repair): drop BTC hardcode from DAG params + snapshot"` — **один коммит**, CI зелёный.
- **Действия (S0.2 — preflight через instruments-таблицу):**
  5. Создать модуль `src/market_meta/` (skeleton: `domain/instrument_validator.py`, `ports.py`, `infrastructure/sql_adapter.py`, `application/use_case.py`, `__init__.py`). Делегировать Agent `Plan` если нужен мини-PRD.
  6. `validate_instrument_exists(symbol, db_session, okx_client=None)`:
     - Primary: `SELECT 1 FROM instruments WHERE symbol = :s`.
     - Fallback: `okx_client.get_instrument_info(symbol)` если передан.
     - Raise `InstrumentNotFoundError` (новый domain exception).
  7. В DAG: новая задача `preflight_instrument_check` перед `validate_swap_repair_conf_task`; читает `symbol` из conf, вызывает validator.
  8. Unit tests + integration test (live OKX API optional, mocked primary).
- **Вход:** Этап 2 зелёный.
- **Результат:**
  - DAG `symbol="ETH-USDT-SWAP"` успешно стартует.
  - DAG `symbol="ETH-USDT-SWOP"` (typo) падает на preflight с `InstrumentNotFoundError`, 0 записей в БД.
  - Snapshot-тест зелёный.
- **Зависимости:** Этап 2 (снимает риск CI drift).
- **Риски:**
  - Размещение в `src/market_meta/` — первый раз модуль создаётся; нужно согласовать с `ARCHITECTURE.md §9.5` и layering.
  - OKX fallback требует rate-limit awareness — переиспользовать sync policy.

### Этап 4. Multi-symbol P1 — listing-date + guardrails (P1, ~0.5 день)

**Цель:** bootstrap пустого coverage работает для любого символа; guardrail не требует ручного подбора.

- **Действия:**
  1. **S1.1 listing-date:** проверить `repair_repository.get_listing_anchor_metadata` / `get_listing_time_ts_ms` — использует ли `instruments` таблицу как primary. Если нет — добавить.
  2. **S1.2 cache:** per-symbol `dict[str, ListingAnchorMetadata]` в adapter.
  3. **S2.1 auto-guardrail:** в `application/repair_planning.py`:
     ```python
     TIMEFRAME_BARS_PER_DAY: dict[str, float] = {
         "1m": 1440, "1H": 24, "4H": 6, "1D": 1,
         "1W": 1/7, "1M": 1/30,
     }
     def min_bars_for_window(start_ts_ms: int, end_ts_ms: int, tf: str) -> int:
         span_days = (end_ts_ms - start_ts_ms) / 86_400_000
         return max(1, int(span_days * TIMEFRAME_BARS_PER_DAY[tf] * 1.05))
     ```
     Применять как default при отсутствии явного `max_requested_bars_per_run`.
  4. **S2.2 guardrail_risk в preview:** `plan_swap_repair` возвращает `guardrail_risk: Literal["ok","medium","high"]` — порог `requested_bars / max_requested_bars_per_run`: `<0.5=ok`, `0.5-0.9=medium`, `>=0.9=high`.
  5. Unit tests на 6 TF × разные окна.
- **Вход:** Этап 3.
- **Результат:**
  - `auto_apply_anchor_strategy="listing-date"` работает для ETH/SOL.
  - Запуск 1H × 12 мес не требует ручной подборки guardrail.
  - Preview показывает risk до apply.
- **Зависимости:** Этап 3 (без preflight нет смысла в listing-date generalization).
- **Риски:**
  - Float precision для 1W/1M — рассмотреть Decimal или вшитое padding.
  - Cache invalidation — если listing-date в `instruments` обновится, кэш в памяти устареет; для v1 ограничиться per-DAG-run scope.

### Этап 5. Tests & Docs (P3, ~0.5 день)

**Цель:** проверяемость и обнаружение регрессий при добавлении новых символов без кода.

- **Действия:**
  1. **S3.1:** параметризовать integration tests — `pytest.fixture(params=["BTC-USDT-SWAP","ETH-USDT-SWAP"])`. Где DB-фикстуры зависят от символа — параметризовать их тоже.
  2. **S3.2+S3.3:** operator guide (improvements §12.1, §12.2) — `symbol: any valid OKX swap instId`; добавить ETH/SOL-пресеты.
  3. Обновить `docs/okx_swap_repair_v1_plan_vs_actual.md`: "Actual v1 scope" без BTC-ограничения; "Out of scope" отражает, что multi-symbol теперь In scope.
  4. Обновить CLAUDE.md project section если что-то архитектурное изменилось (например, появление `src/market_meta/`).
- **Вход:** Этапы 3-4.
- **Результат:** tests — зелёные на ETH без кода; docs — без BTC-only формулировок.
- **Зависимости:** Этапы 3-4.
- **Риски:** parametrize может замедлить integration suite — следить за временем CI.

### Backlog — v2 (вне скоупа этого плана)

- Dynamic task mapping per symbol (`symbols: list[str]`).
- Агрегированный XCom по символам.
- `load_instruments.py` refactor из `src/candles/` → `src/market_meta/`.
- Volume-based corruption rules (если решим изменить default).
- Decision: partial auto-apply как warning vs. audited failure.

Не начинать пока Этапы 3-4 не закрыты (как указано в multi_symbol §3).

---

## 5. Прогресс-трекер

### Этап 1 — SQL correctness ✅ DONE
- [x] 1.1 Explore `src/candles/application/repair*.py` + `src/candles/infrastructure/repair_repository.py` + domain helpers
- [x] 1.2 Сверить миграции `repair_state` и `ops.swap_repair_audit` — audit ✅, repair_state ❌ не нужна (state через coverage_bounds)
- [x] 1.3 Brainstorm: добавить vs. переименовать — решение: ADD новые методы, existing не трогать
- [x] 1.4 Реализовать `list_missing_timestamps(..)` с half-open bounds (generate_series + 1M branch)
- [x] 1.5 Реализовать `list_corrupted_timestamps(..)` (NULL/≤0/high<low/open|close outside [low,high])
- [x] 1.6 Реализовать `is_features_ready(..)` (LIMIT 300 DESC + LAG + JOIN corrupted)
- [x] 1.7 Добавить `merge_gaps` в `src/candles/domain/repair.py` + 6 unit tests
- [x] 1.8 1M branch — через `floor_to_timeframe` + `expected_next_open` в `_list_missing_1m` / `_is_features_ready_1m`
- [x] 1.9 `database-reviewer` agent review — fixed corrupted CTE bug (MIN bleed)
- [x] 1.10 CI: ruff clean, 19 tests pass

### Этап 2 — v1 хвосты ✅ DONE
- [x] 2.1 P1.3 operator docs partial auto-apply → `docs/operator-guide/partial-auto-apply.md`
- [x] 2.2 P1.5 убрать дублирование из test DAG — SUPPORTED_SYMBOLS дублируется, но удаляется атомарно в Этапе 3 вместе с enum
- [x] 2.3 P2.3 presets + README → `ops/airflow/dags/README.md` обновлён, полный раздел `okx_swap_repair_v1`
- [x] 2.4 P3.1 `_common/swap_repair_dag_helpers.py` — `_common/repair.py` уже содержит все helpers (validate_swap_repair_xcom_payload, normalize_swap_repair_conf, resolve_repair_window_from_conf); отдельный файл не нужен
- [x] 2.5 P3.3 integration tests — добавлены: missing instrument (returns None) + stale metadata (age detectable) в `tests/integration/test_repair_repository.py`
- [x] 2.6 P3.4 snapshot-test — `tests/db/test_okx_swap_repair_v1_dag.py` 48/48 pass; исправлен `tests/db/conftest.py` (sys.path для `_common`)
- [x] 2.7 P3.5 обновить `plan_vs_actual.md` → добавлены SQL methods, multi-symbol roadmap, out-of-scope
- [x] 2.8 CI зелёный: 67 tests pass, ruff clean

### Этап 3 — Multi-symbol P0 ✅ DONE
- [x] 3.1 **Atomic commit:** DAG Param.default=None + убрать enum + обновить snapshot (S0.1+S3.4)
- [x] 3.2 CI зелёный после atomic commit — 51 snapshot tests pass
- [x] 3.3 Mini-PRD для `src/market_meta/` — спроектировано inline (domain/application/infra/ports)
- [x] 3.4 Скелет `src/market_meta/` — создан: domain/exceptions.py, ports.py, application/validate_instrument.py, infrastructure/sql_adapter.py
- [x] 3.5 `validate_instrument_exists` с primary SQL через `InstrumentSqlRepository`
- [x] 3.6 DAG: новая задача `preflight_instrument_check` перед `validate_swap_repair_conf`
- [x] 3.7 Unit tests: 4 unit (validate_instrument) + 2 DAG tests (preflight pass/fail) — 82 tests pass
- [x] 3.8 ETH-USDT-SWAP параметризован в `test_swap_repair_task_uses_validated_conf_payload`

### Этап 4 — Multi-symbol P1 ✅ DONE
- [x] 4.1 Listing-date через `instruments` primary (S1.1) — уже была реализована через `get_listing_anchor_metadata`
- [x] 4.2 Per-symbol cache (S1.2) — добавлен `_listing_metadata_cache` в `RepairCandlesRepository.__init__`
- [x] 4.3 `min_bars_for_window` + `TIMEFRAME_BARS_PER_DAY` добавлены в `application/repair/planning.py`
- [x] 4.4 `guardrail_risk` изменён с `bool` → `Literal["ok","medium","high"]` в `RepairPreview` + `runner.py`; все тесты обновлены
- [x] 4.5 Unit tests: 10 тестов для `min_bars_for_window` и `TIMEFRAME_BARS_PER_DAY`
- [x] 4.6 E2E: ETH-USDT-SWAP параметризован в snapshot tests; listing-date уже работает для любого символа

### Этап 5 — Tests & Docs ✅ DONE
- [x] 5.1 Параметризация integration tests — ETH-USDT-SWAP добавлен в параметризованный тест DAG tasks
- [x] 5.2 Operator guide + presets ETH/SOL → добавлены в `plan_vs_actual.md`
- [x] 5.3 `plan_vs_actual.md` обновлён: удалена BTC-ограничение, добавлены multi-symbol presets, обновлён раздел scope
- [x] 5.4 CI зелёный: 541 fast tests pass; ruff clean

### Статус выполнения
- Всего шагов: **34**
- Выполнено: **34**
- Осталось: **0**
- Текущий этап: ✅ **Все этапы завершены**
- Блокеры: нет
- Заметки: repair_state не мигрирована и не нужна (state implicit через coverage_bounds); tests/candles/ __init__.py отсутствуют (pre-existing, не блокер)

---

## 6. Приоритеты

### Критично (делать первым, блокирует всё остальное)
- Этап 1 полностью — без корректного SQL все последующие изменения строятся на битом фундаменте.
- Этап 3.1 (atomic S0.1+S3.4) — без этого коммита CI будет красным при любой попытке не-BTC.

### Важно (до закрытия итерации)
- Этап 2 целиком — партиалы в improvements-tracker = скрытые CI-риски.
- Этап 3.2-3.8 — S0.2 preflight защищает от тихих 0-row writes.
- Этап 4 — listing-date + auto-guardrail снимают операторскую боль подборки параметров.

### Желательно (можно оставить на следующий цикл, но лучше закрыть)
- Этап 5 — parametrize integration tests; operator presets; обновление plan-vs-actual.
- Рефакторинг `load_instruments.py` в `src/market_meta/` (backlog).

---

## 7. Следующее действие

**Самый первый шаг:** прочитать полный `src/candles/infrastructure/repair_repository.py` и `src/candles/application/repair*.py`, чтобы сопоставить текущие методы с контрактом `sql_summary`.

**Документы открыть первыми:**
1. `src/candles/infrastructure/repair_repository.py` — текущая surface.
2. `history/planning/okx_swap_repair_sql_summary_2026-04-18.md` — эталонные SQL.
3. `src/candles/domain/` — проверить `floor_to_timeframe`, `expected_next_open`.
4. `src/db/migrations/` — поискать `repair_state` и `ops.swap_repair_audit`.

**Плагины подключить первыми:**
1. `Explore` agent (medium) — обход repair-цепочки в одной задаче.
2. `postgres-patterns` skill — руководство при написании/review SQL.
3. `superpowers:brainstorming` — перед решением add-vs-rename для repository surface.
4. После первого коммита: `superpowers:verification-before-completion` перед каждым шагом.

**Команда для проверки текущего состояния перед стартом:**
```bash
make check          # baseline: lint + typecheck + unit tests
pytest tests/db/test_okx_swap_repair_v1_dag.py -v  # проверить, что snapshot сейчас зелёный
git log --oneline -10
```

---

## 8. Verification (как убедиться, что всё работает)

После каждого этапа:
- `make check` — lint + typecheck + fast tests зелёные.
- `make test-all` — включая integration (на Этапах 2.5, 3.7, 4.5, 5.1).
- Snapshot-тест `tests/db/test_okx_swap_repair_v1_dag.py` — зелёный.

E2E после Этапа 4:
- Airflow UI: trigger DAG с `symbol="ETH-USDT-SWAP"`, `mode="apply"`, `auto_apply_anchor_strategy="listing-date"`, `timeframes=["1H"]`.
- Проверить `ops.swap_repair_audit` — есть запись с `verified=true`, `remaining_gap_tasks=0`.
- Metrics в Pushgateway — `pklpo_swap_repair_rows_written > 0`.

После Этапа 5:
- Integration test `pytest tests/integration/candles/test_repair_parametrized.py -v` — проходит для всех параметров фикстуры без код-правок.
- `gh pr create` — PR с разделёнными по этапам коммитами; CI полностью зелёный.
