# Инструкция по тестированию DAG okx_swap_ohlcv_sync_v2

> **Примечание:** Общая документация по всем DAG-ам находится в [README.md](./README.md)

## Тестирование через Airflow CLI (основной способ)

**Это нормальный, правильный способ проверять DAG из терминала.**

### 1. Проверить, что DAG виден Airflow

```bash
airflow dags list | grep okx_swap_ohlcv_sync
```

Если DAG не в списке — проблема в импорте или синтаксисе.

### 2. Проверить DAG на ошибки импорта (важно)

```bash
airflow dags list-import-errors
```

Если здесь ошибки — **DAG вообще не запускается**, ни из UI, ни из CLI.

### 3. Прогнать конкретную задачу (БЕЗ scheduler)

Это самый полезный режим для отладки.

**Синтаксис:**
```bash
airflow tasks test <dag_id> <task_id> <execution_date>
```

**Примеры:**

#### Проверить refresh инструментов
```bash
airflow tasks test okx_swap_ohlcv_sync refresh_okx_meta 2025-01-01
```

#### Проверить основной sync
```bash
airflow tasks test okx_swap_ohlcv_sync swap_sync 2025-01-01
```

#### Проверить smoke validate
```bash
airflow tasks test okx_swap_ohlcv_sync smoke_validate 2025-01-01
```

**Что важно:**
- `tasks test` **игнорирует schedule**
- **не пишет состояние в БД Airflow**
- **XCom работает**
- код выполняется почти так же, как в реальном запуске

Это идеальный режим для дебага.

**Ограничения `tasks test` (что НЕ проверяет):**
- ❌ Параллельные запуски (`max_active_runs`)
- ❌ Блокировки БД при конкурентном доступе
- ❌ Реальное поведение scheduler (retry, timeout, backfill)
- ❌ Взаимодействие с другими DAG-ами

Для проверки этих аспектов используй `dags trigger` или реальный scheduler.

### 4. Запуск с `dag_run.conf` (режимы fast / slow / ext)

Через `tasks test` **нельзя** передать `dag_run.conf`.

Чтобы проверить конфигурацию, нужен **trigger**.

#### Через CLI trigger

```bash
# Fast режим (по умолчанию)
airflow dags trigger okx_swap_ohlcv_sync --conf '{"mode":"fast"}'

# Slow режим
airflow dags trigger okx_swap_ohlcv_sync --conf '{"mode":"slow"}'

# Ext режим с конкретным символом
airflow dags trigger okx_swap_ohlcv_sync --conf '{"mode":"ext","symbols":["BTC-USDT-SWAP"]}'

# Bootstrap режим
airflow dags trigger okx_swap_ohlcv_sync --conf '{"mode":"bootstrap","refresh_instruments":true}'
```

После этого:
- смотри логи тасков через UI или CLI
- DAG выполнится полностью, как в бою

### Режимы работы DAG

| Режим     | Как запускается              | Для чего                    |
| --------- | ---------------------------- | --------------------------- |
| fast      | schedule (каждую минуту)     | live ingest (1m, 5m)        |
| slow      | auto-slot (0, 15, 30, 45) / manual | старшие TF (15m+)           |
| ext       | manual                       | shortlist с extra_data      |
| bootstrap | manual                       | первичная загрузка истории  |

### 5. Проверить render шаблонов и context

```bash
airflow tasks render okx_swap_ohlcv_sync swap_sync 2025-01-01
```

Полезно, если используешь templates или хочешь увидеть context.

### 6. Проверка без запуска кода (статическая)

```bash
airflow dags show okx_swap_ohlcv_sync
```

Покажет граф DAG-а, зависимости, имена тасков.

### 7. Список задач

```bash
airflow tasks list okx_swap_ohlcv_sync
```

## Быстрая проверка синтаксиса

```bash
# Проверка синтаксиса Python
python -m py_compile ops/airflow/dags/okx_swap_ohlcv_sync_v2.py
```

## Тестирование функций (без Airflow)

```bash
# Запуск тестов функций
python ops/airflow/dags/test_dag_functions.py
```

### 3. Тестирование с моками (в pytest)

```bash
# Запуск pytest тестов (требует установки airflow в тестовом окружении)
pytest ops/airflow/dags/test_okx_swap_ohlcv_sync_v2.py -v
```

## Что НЕ получится через CLI

❌ Нельзя:
- через CLI проверить `schedule` "как будто прошло время"
- передать `dag_run.conf` в `tasks test` (используй `dags trigger`)
- эмулировать scheduler полностью одной командой

Для этого нужен реально работающий scheduler.

## Ручное тестирование в Airflow UI

### 1. Подготовка

- Убедитесь, что настроен Airflow Connection `pklpo_db`
- Убедитесь, что DAG виден в UI

### 2. Тест режима fast (по умолчанию)

1. В Airflow UI: Trigger DAG `okx_swap_ohlcv_sync`
2. Config: `{}` (пустой)
3. Ожидаемое поведение:
   - `refresh_okx_meta`: пропустит обновление (если кэш свежий)
   - `swap_sync`: синхронизирует `["1m", "5m"]` без extra_data
   - `smoke_validate`: проверит данные

### 3. Тест режима slow

1. Trigger DAG with config: `{"mode": "slow"}`
2. Ожидаемое поведение:
   - `swap_sync`: синхронизирует старшие таймфреймы
   - `smoke_validate`: проверит данные

### 4. Тест режима ext

1. Trigger DAG with config: `{"mode": "ext", "symbols": ["BTC-USDT-SWAP"]}`
2. Ожидаемое поведение:
   - `swap_sync`: синхронизирует с extra_data=True
   - `smoke_validate`: проверит fill-rate для funding_rate/open_interest

### 5. Тест условного refresh_instruments

1. Trigger DAG with config: `{"refresh_instruments": true}`
2. Ожидаемое поведение:
   - `refresh_okx_meta`: выполнит обновление инструментов

### 6. Проверка XCom

После выполнения `swap_sync`:
1. Откройте XCom для задачи `swap_sync`
2. Проверьте, что `return_value` содержит:
   - `mode`, `timeframes`, `symbols_count`
   - `duration_sec`, `rows_upserted_total`
   - `api_429_count`, `api_timeout_count`
   - `today_fill`

## Проверка авто-слотов (для scheduled запусков)

Если установить `schedule="*/1 * * * *"`:

1. DAG будет запускаться каждую минуту
2. В минуты, кратные 15 (0, 15, 30, 45) - режим `slow`
3. В остальные минуты - режим `fast`

Проверка:
```bash
# Запустить DAG вручную в разные минуты и проверить логи
# В логах должно быть: "starting swap-sync in mode=slow" или "mode=fast"
```

## Практическая рекомендация (рабочий процесс)

1. **После правок:**
```bash
airflow dags list-import-errors
```

2. **Проверяешь логику тасков:**
```bash
airflow tasks test okx_swap_ohlcv_sync swap_sync 2025-01-01
```

3. **Проверяешь режимы:**
```bash
airflow dags trigger okx_swap_ohlcv_sync --conf '{"mode":"fast"}'
```

4. **Только потом включаешь `schedule`.**

## Чеклист тестирования

- [ ] DAG загружается без ошибок (`airflow dags list-import-errors`)
- [ ] Все задачи видны в UI (`airflow tasks list okx_swap_ohlcv_sync`)
- [ ] Зависимости между задачами корректны (`airflow dags show okx_swap_ohlcv_sync`)
- [ ] Режим `fast` работает (пустой config)
- [ ] Режим `slow` работает
- [ ] Режим `ext` работает с extra_data
- [ ] Режим `bootstrap` работает
- [ ] Условный `refresh_instruments` работает
- [ ] XCom содержит ожидаемую статистику
- [ ] Smoke validate корректно проверяет данные
- [ ] Retry работает при ошибках
- [ ] `max_active_runs=1` предотвращает параллельные запуски

## Чек-лист: DAG готов к автономной работе

Перед включением `schedule="*/1 * * * *"` убедись:

### Базовые проверки
- [ ] `airflow dags list-import-errors` — нет ошибок
- [ ] `airflow dags list | grep okx_swap_ohlcv_sync` — DAG виден
- [ ] Airflow Connection `pklpo_db` настроен и работает
- [ ] Все Airflow Variables настроены (или дефолты приемлемы)

### Функциональность
- [ ] `airflow tasks test okx_swap_ohlcv_sync refresh_okx_meta 2025-01-01` — проходит
- [ ] `airflow tasks test okx_swap_ohlcv_sync swap_sync 2025-01-01` — проходит
- [ ] `airflow tasks test okx_swap_ohlcv_sync smoke_validate 2025-01-01` — проходит

### Режимы работы
- [ ] Fast режим работает: `airflow dags trigger okx_swap_ohlcv_sync --conf '{"mode":"fast"}'`
- [ ] Slow режим работает: `airflow dags trigger okx_swap_ohlcv_sync --conf '{"mode":"slow"}'`
- [ ] Авто-слоты работают (проверить логи при разных execution_date)

### Безопасность и стабильность
- [ ] `max_active_runs=1` установлен (предотвращает параллельные запуски)
- [ ] `execution_timeout` установлен (защита от зависших задач)
- [ ] Retry настроен (`retries=3`, `retry_delay=timedelta(minutes=2)`)
- [ ] Обработка ошибок работает (проверить при сбоях БД/API)

### Мониторинг
- [ ] XCom статистика корректна (проверить `return_value` у `swap_sync`)
- [ ] Логи читаемы и информативны
- [ ] Smoke validate корректно детектирует проблемы

### Производительность
- [ ] Fast режим укладывается в 1 минуту (для `schedule="*/1 * * * *"`)
- [ ] Slow режим укладывается в 15 минут
- [ ] Нет утечек памяти/соединений (проверить после нескольких запусков)

### Красные флаги (НЕ включать schedule, если есть)

❌ **Критичные проблемы:**
- `swap_sync` в fast-режиме > 60 секунд (не укладывается в интервал)
- Lag по 1m таймфрейму > 120 секунд (данные устаревают)
- Регулярные 429 в XCom stats (`api_429_count` > 10% от запросов)
- DAG падает чаще 1 раза в сутки при стабильной инфраструктуре
- Ошибки БД (connection pool exhausted, deadlocks)
- Memory leaks (рост потребления памяти после 10+ запусков)

⚠️ **Предупреждения (требуют внимания, но не блокируют):**
- Периодические таймауты API (< 5% запросов)
- Задержки refresh_instruments (не критично, если кэш свежий)
- Временные проблемы сети (самовосстанавливающиеся)

### После включения schedule
- [ ] Мониторить первые 5-10 запусков
- [ ] Проверить, что авто-слоты работают (slow в 0, 15, 30, 45 минут)
- [ ] Убедиться, что нет конфликтов с другими DAG-ами

## Отладка

### Проблема: DAG не загружается

```bash
# Проверить логи Airflow
airflow dags list-import-errors

# Проверить синтаксис
python -m py_compile ops/airflow/dags/okx_swap_ohlcv_sync_v2.py
```

### Проблема: Connection не найден

```bash
# Проверить connections
airflow connections list | grep pklpo_db

# Создать connection
airflow connections add pklpo_db \
    --conn-type postgres \
    --conn-host pklpo_db \
    --conn-schema pklpo \
    --conn-login pklpo_user \
    --conn-password strongpassword \
    --conn-port 5432
```

### Проблема: Функции не работают

Проверить логи задачи в Airflow UI:
- Открыть задачу
- Посмотреть Logs
- Проверить ошибки и предупреждения
