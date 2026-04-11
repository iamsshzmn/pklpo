# Документация DAG-ов PKLPO

Обзор всех DAG-ов в проекте PKLPO для Airflow.

## Содержание

- [okx_swap_ohlcv_sync_v2](#okx_swap_ohlcv_sync_v2) - Синхронизация OHLCV данных
- [features_calc_short](#features_calc_short) - Расчёт коротких фичей
- [market_selection](#market_selection) - Выбор торговых пар
- [features_calc](#features_calc) - Расчёт всех фичей
- [indicators_partition_maintenance](#indicators_partition_maintenance) - Обслуживание monthly partitions
- [Общие настройки](#общие-настройки)
- [Тестирование](#тестирование)

---

## okx_swap_ohlcv_sync_v2

**DAG ID:** `okx_swap_ohlcv_sync_v2`

**Назначение:**
- Сбор и загрузка OHLCV свечей для SWAP-инструментов OKX в таблицу `swap_ohlcv_p`
- Дополнительно, при `extra_data=True`, подтягиваются `funding_rate` и `open_interest`

**Расписание:** `*/5 * * * *` (каждые 5 минут)

**Состав задач:**
1. `refresh_okx_meta` - обновляет справочник инструментов (CLI: load-instruments) условно
2. `swap_sync` - вызывает canonical entrypoint `src.candles.interfaces.swap_sync.sync_swap_candles` и возвращает статистику в XCom
3. `smoke_validate` - быстрая проверка наличия записей и доли заполнения `funding_rate`/`open_interest`

**Параметры запуска (через `dag_run.conf`):**

```json
{
  "mode": "fast",              // "fast" | "slow" | "ext" | "bootstrap"
  "extra_data": false,         // bool, подтягивать funding_rate/open_interest
  "timeframes": ["1m", "5m"],  // list[str], переопределяет режим
  "symbols": ["BTC-USDT-SWAP"], // list[str], опционально; иначе используется curated repo list
  "refresh_instruments": false, // bool, принудительное обновление инструментов
  "max_concurrent_symbols": 10  // int, опционально
}
```

**Режимы работы:**

| Режим     | Таймфреймы                          | extra_data | Использование                    |
| --------- | ----------------------------------- | ---------- | -------------------------------- |
| fast      | 1m, 5m                              | false      | Live ingest (каждые 5 минут)     |
| slow      | 15m, 30m, 1H, 4H, 12H, 1D, 1W, 1M | false      | Старшие ТФ (0, 15, 30, 45 минут) |
| ext       | 1m, 5m                              | true       | Ручной запуск с extra_data       |
| bootstrap | все                                 | true       | Первичная загрузка истории       |

**Авто-слоты:**
- При scheduled запуске в минуты 0, 15, 30, 45 автоматически выбирается режим `slow`
- В остальные минуты - режим `fast`

**Freshness gate:**
- Для scheduled запусков: пропускает выполнение, если данные свежие (lag < 2 мин для fast, < 15 мин для slow)
- Для ручных запусков: всегда выполняет синхронизацию

**Примеры запуска:**

```bash
# Fast режим (по умолчанию)
airflow dags trigger okx_swap_ohlcv_sync_v2 --conf '{}'

# Slow режим
airflow dags trigger okx_swap_ohlcv_sync_v2 --conf '{"mode":"slow"}'

# Ext режим с конкретным символом
airflow dags trigger okx_swap_ohlcv_sync_v2 --conf '{"mode":"ext","symbols":["BTC-USDT-SWAP"]}'

# Bootstrap режим
airflow dags trigger okx_swap_ohlcv_sync_v2 --conf '{"mode":"bootstrap","refresh_instruments":true}'
```

**Логирование:**
- Лог-файл: `/tmp/pklpo/market_meta.log`
- XCom у `swap_sync`: ключ `return_value` содержит статистику sync run, включая `mode`, `timeframes`, `symbols_count`, `total_symbols_processed`, `rows_upserted_total`, `endpoint_stats`, `today_fill` и `sync_run`
- `validate_swap_sync_xcom` валит non-skipped run только при total failure: `rows_upserted_total == 0` или `total_symbols_processed == 0`; `errors_count` остаётся диагностикой partial issues

**Настройки:**
- `max_active_runs=1` - только один активный запуск
- `retries=3`, `retry_delay=2 минуты`
- `execution_timeout=2 часа`

---

## features_calc_short

**DAG ID:** `features_calc_short`

**Назначение:**
- Расчёт только features_calc_short индикаторов (24 фичи) с инкрементальным обновлением
- Глобальный freshness gate на старт DAG
- Параллелизм по символам с ограничением для CPU-bound операций

**Расписание:** `*/15 * * * *` (каждые 15 минут)

**Состав задач:**
1. `features_calc_short_run` - основной расчёт индикаторов
2. `features_calc_short_validate` - проверка наличия записей после расчёта

**Параметры запуска (через `dag_run.conf`):**

```json
{
  "symbols": ["BTC-USDT-SWAP"],  // list[str] | null (все символы)
  "timeframes": ["1m", "5m", "15m", "30m", "1H", "4H", "1D"],  // list[str]
  "max_concurrent_symbols": 3     // int, ограничение параллелизма
}
```

**Особенности:**
- Инкрементальный расчёт: обрабатывает только новые данные относительно watermark
- Глобальный freshness gate: пропускает DAG, если все таймфреймы свежие (lag < 240s для fast ТФ, < 1200s для slow ТФ)
- Параллелизм: ограничен до 3 символов одновременно (CPU-bound операции)
- Таймаут: 300 секунд на расчёт одного таймфрейма

**Логирование:**
- Логи в stdout Airflow
- Статистика в return_value: total_symbols, successful, failed, rows_saved_total, duration_seconds

**Настройки:**
- `max_active_runs=1` - только один активный запуск
- `retries=2`, `retry_delay=5 минут`
- `execution_timeout=2 часа`

---

## market_selection

**DAG ID:** `market_selection`

**Назначение:**
- Выбор торговых пар на основе Data Quality, Pair Metrics, Global Regime
- Запускается после успешного завершения DAG `features_calc_short` (ожидает задачу `features_calc_short_validate`)
- Результат: таблица `market_universe` с top-N парами; при непустом universe триггерится DAG `features_calc`

**Расписание:** `0 */4 * * *` (каждые 4 часа)

**Состав задач:**
1. `wait_for_features_calc_short` - ExternalTaskSensor (external_dag_id=features_calc_short, external_task_id=features_calc_short_validate)
2. `run_migrations` - идемпотентные миграции таблиц market_*
3. `run_pipeline` - основной pipeline выбора пар
4. `validate_universe` - валидация опубликованного universe
5. `prepare_features_calc_trigger` - подготовка списка символов для features_calc (XCom: universe_symbols)
6. `branch_skip_or_trigger` - ветвление: при пустом universe не запускать features_calc
7. `skip_features_calc_trigger` - EmptyOperator (ветка при пустом universe)
8. `trigger_features_calc` - TriggerDagRunOperator (ветка при непустом universe)
9. `cleanup_old_data` - очистка старых записей по retention

**Параметры запуска (через `dag_run.conf`):**

```json
{
  "top_n": 30,        // количество пар в universe
  "force_run": false  // зарезервировано (игнорировать freshness check)
}
```

**Требования:** Airflow Connection `pklpo_db` обязателен (см. [Общие настройки](#общие-настройки)).

**Настройки:**
- `retries=2`, `retry_delay=5 минут`
- Сенсор: timeout=3600 с, poke_interval=60 с

**Если DAG не виден в UI:** DAG-файлы попадают в образ при сборке. После изменений в `market_selection.py` пересоберите образ и перезапустите scheduler/webserver (см. [TROUBLESHOOTING.md](../TROUBLESHOOTING.md), раздел «DAGs не отображаются»). Проверка ошибок импорта: `airflow dags list-import-errors`.

---

## features_calc

**DAG ID:** `features_calc`

**Назначение:**
- Запуск расчёта технических индикаторов (этап Features) через CLI `src.cli.main features`
- Production режим: расчёт для всех символов из swap_ohlcv_p по всем доступным свечам
- Поддержка фильтрации: можно указать конкретные символы через параметр symbols

**Расписание:** `None` (ручной запуск)

**Состав задач:**
1. `features_run` - запускает расчёт индикаторов без лимита (все доступные бары)
2. `smoke_validate_features` - проверяет наличие записей в таблице `indicators` после расчёта
3. `combinations_run` - расчёт комбинаций фичей

**Параметры запуска (через `dag_run.conf` или `params`):**

```json
{
  "symbols": null,              // null | "none" = все символы, иначе конкретный символ или список
  "timeframes": "1m,5m,15m,30m,1H,4H,12H,1D,1W,1M",  // строка через запятую
  "limit": null                 // null | "none" = все свечи, иначе число = последние N свечей
}
```

**Особенности:**
- Использует CLI команду `features` для расчёта
- Поддержка alerting (FEAT-002): уведомления при ошибках и SLA пропусках
- Потоковое логирование вывода CLI в реальном времени

**Логирование:**
- Логи печатаются в stdout Airflow
- Детальные логи CLI: `/tmp/pklpo/features.log`
- Метрики в stdout: `[features_calc] METRICS {...}`

**Настройки:**
- `retries=2`, `retry_delay=5 минут`
- `execution_timeout=2 часа`
- `sla=1 час` - задачи должны завершиться в течение часа
- Email уведомления при ошибках (если настроен SMTP)

---

## indicators_partition_maintenance

**DAG ID:** `indicators_partition_maintenance`

**Назначение:**
- Поддерживает готовый горизонт monthly partitions для `indicators_p`
- Создаёт отсутствующие partition tables заранее, не дожидаясь первого INSERT нового месяца
- Проверяет, что текущий месяц и следующие месяцы доступны для записи

**Расписание:** `0 1 * * *` (ежедневно в 01:00 UTC)

**Состав задач:**
1. `ensure_indicators_partitions` - создаёт недостающие partitions в окне обслуживания
2. `validate_partition_horizon` - валидирует, что горизонт вперёд покрыт

**Параметры запуска (через `dag_run.conf`):**

```json
{
  "months_back": 1,
  "months_ahead": 3,
  "reference_dt": null,
  "require_parent_pk": true
}
```

**Особенности:**
- DAG идемпотентен: повторный запуск не создаёт дубликаты
- `reference_dt` нужен только для ручной отладки или проверки исторического окна
- `require_parent_pk=true` проверяет prereq для UPSERT: на `indicators_p` должен быть PK/UNIQUE по `(symbol, timeframe, timestamp)`
- DAG вызывает interface entrypoint `src.platform_ops.interfaces.*`, а не SQL/DB adapter напрямую

**Ручной operational path (CLI):**

```bash
# Безопасный preview по умолчанию (dry-run)
python -m src.cli.main indicators-partitions

# Preview для конкретного окна
python -m src.cli.main indicators-partitions --months-back 1 --months-ahead 3 --reference-dt 2026-03-07T00:00:00Z

# Применить изменения явно
python -m src.cli.main indicators-partitions --apply

# Применить и сразу провалидировать horizon
python -m src.cli.main indicators-partitions --apply --validate
```

**Важно:**
- ручной CLI path по умолчанию не меняет схему
- для реального apply нужен явный `--apply`
- `--skip-parent-pk-check` допустим только для bootstrap/диагностического сценария

**Логирование:**
- В stdout Airflow логируется окно обслуживания, число созданных и уже существующих partitions

---

## Общие настройки

### Airflow Connection

**Обязательно настроить:**
- `pklpo_db` (Conn Id: pklpo_db, Type: Postgres) - подключение к БД

```bash
airflow connections add pklpo_db \
    --conn-type postgres \
    --conn-host pklpo_db \
    --conn-schema pklpo \
    --conn-login pklpo_user \
    --conn-password strongpassword \
    --conn-port 5432
```

### Airflow Variables (опционально)

- `pklpo_database_ssl` (default: "disable")
- `market_meta_log_file` (default: "/tmp/pklpo/market_meta.log")
- `market_meta_file_log` (default: "true")
- `market_meta_log_level` (default: "DEBUG")
- `market_meta_data_dir` (default: "/tmp/pklpo/data")
- `instruments_cache_dir` (default: "/tmp/pklpo") - runtime cache directory for refreshed catalog fallback; default symbol universe for `swap_sync` without explicit `symbols` comes from repo-local `src/candles/instruments_list.json`

### Временные директории

Все DAG-ы создают и используют:
- `/tmp/pklpo` - основная директория для кэшей и логов
- `/tmp/pklpo/data` - директория для данных

---

## Тестирование

### Базовые проверки

```bash
# Проверить, что DAG виден Airflow
airflow dags list | grep <dag_id>

# Проверить DAG на ошибки импорта
airflow dags list-import-errors

# Показать граф DAG-а
airflow dags show <dag_id>

# Список задач
airflow tasks list <dag_id>
```

### Тестирование задач

```bash
# Запуск задачи БЕЗ scheduler (для отладки)
airflow tasks test <dag_id> <task_id> <execution_date>

# Примеры:
airflow tasks test okx_swap_ohlcv_sync_v2 swap_sync 2025-01-01
airflow tasks test features_calc_short features_calc_short_run 2025-01-01
```

**Важно:** `tasks test` игнорирует schedule, не пишет состояние в БД Airflow, но XCom работает.

### Запуск с параметрами

```bash
# Trigger DAG с конфигурацией
airflow dags trigger <dag_id> --conf '{"mode":"fast","symbols":["BTC-USDT-SWAP"]}'

# Trigger indicators partition maintenance
airflow dags trigger indicators_partition_maintenance --conf '{"months_back":1,"months_ahead":3}'
```

### Проверка синтаксиса

```bash
# Проверка синтаксиса Python
python -m py_compile ops/airflow/dags/<dag_file>.py
```

### Подробная документация по тестированию

См. [TESTING.md](./TESTING.md) для детальной инструкции по тестированию DAG `okx_swap_ohlcv_sync_v2`.

---

## Зависимости между DAG-ами

```
okx_swap_ohlcv_sync_v2 (OHLCV данные)
    ↓
features_calc_short (короткие фичи, каждые 15 мин)
    ↓
features_calc (полный расчёт, ручной запуск)
```

**Рекомендации:**
- Не запускать `features_calc` одновременно с `okx_swap_ohlcv_sync_v2`
- `features_calc_short` может работать параллельно с ingest, но лучше избегать пиковых нагрузок

---

## Мониторинг

### XCom статистика

После выполнения задач проверяйте XCom для получения статистики:

- `okx_swap_ohlcv_sync_v2.swap_sync`: mode, timeframes, symbols_count, total_symbols_processed, duration_sec, rows_upserted_total, api_429_count, today_fill
- `features_calc_short.features_calc_short_run`: total_symbols, successful, failed, rows_saved_total, duration_seconds

### Логи

- OHLCV sync: `/tmp/pklpo/market_meta.log`
- Features calc: `/tmp/pklpo/features.log`
- Airflow UI: логи задач доступны в интерфейсе

---

## Troubleshooting

### DAG не загружается

```bash
airflow dags list-import-errors
python -m py_compile ops/airflow/dags/<dag_file>.py
```

### Connection не найден

```bash
airflow connections list | grep pklpo_db
# Если нет - создать (см. раздел "Общие настройки")
```

### Ошибки выполнения

1. Проверить логи задачи в Airflow UI
2. Проверить XCom для статистики
3. Проверить свежесть данных (freshness gate может пропускать выполнение)
4. Для ручных запусков использовать `{"mode":"..."}` в conf

---

## Устаревшие DAG-ы

- `okx_swap_ohlcv_sync` - старая версия, заменена на `okx_swap_ohlcv_sync_v2`
