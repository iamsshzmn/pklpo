# Диагностика проблем Airflow

## Обнаруженные проблемы

### 1. Scheduler не может подключиться к PostgreSQL

**Ошибка:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "postgres" (172.21.0.6), port 5432 failed: Connection refused
```

**Причина:**
- Scheduler пытается подключиться к postgres до того, как он полностью готов
- Возможна проблема с сетью Docker

**Решение:**
1. Убедиться, что postgres контейнер запущен и healthy:
   ```bash
   docker ps --filter "name=pklpo-airflow-postgres"
   docker exec pklpo-airflow-postgres pg_isready -U airflow
   ```

2. Проверить, что контейнеры в одной сети:
   ```bash
   docker network inspect pklpo_pklpo_network
   ```

3. Перезапустить контейнеры в правильном порядке:
   ```bash
   cd D:\projects\pklpo
   docker-compose -f ops/airflow/docker-compose.airflow.yml down
   docker-compose -f ops/airflow/docker-compose.airflow.yml up -d postgres
   # Подождать 10 секунд
   docker-compose -f ops/airflow/docker-compose.airflow.yml up -d
   ```

### 2. Проблема с монтированием volumes в Windows

**Ошибка:**
```
Error response from daemon: error while creating mount source path '/run/desktop/mnt/host/d/projects/pklpo/ops/airflow/dags': mkdir /run/desktop/mnt/host/d: file exists
```

**Причина:**
- Docker Desktop на Windows использует WSL2, который может иметь проблемы с путями
- Относительные пути в docker-compose могут работать некорректно

**Решение:**
1. Использовать абсолютные пути в docker-compose.airflow.yml
2. Или использовать переменные окружения для путей
3. Проверить настройки Docker Desktop (Settings -> Resources -> File Sharing)

### 3. Контейнеры не запускаются

**Проверка:**
```bash
# Проверить статус всех контейнеров
docker-compose -f ops/airflow/docker-compose.airflow.yml ps

# Проверить логи
docker-compose -f ops/airflow/docker-compose.airflow.yml logs --tail=50
```

## Команды для диагностики

### Проверка статуса
```bash
cd D:\projects\pklpo
docker-compose -f ops/airflow/docker-compose.airflow.yml ps
```

### Проверка логов
```bash
# Все сервисы
docker-compose -f ops/airflow/docker-compose.airflow.yml logs --tail=100

# Только scheduler
docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-scheduler --tail=50

# Только webserver
docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-webserver --tail=50

# Только postgres
docker-compose -f ops/airflow/docker-compose.airflow.yml logs postgres --tail=50
```

### Проверка сети
```bash
# Проверить сеть
docker network inspect pklpo_pklpo_network

# Проверить подключение к postgres из контейнера
docker exec pklpo-airflow-postgres pg_isready -U airflow
```

### Перезапуск
```bash
# Остановить все
docker-compose -f ops/airflow/docker-compose.airflow.yml down

# Запустить только postgres
docker-compose -f ops/airflow/docker-compose.airflow.yml up -d postgres

# Подождать и запустить остальные
Start-Sleep -Seconds 10
docker-compose -f ops/airflow/docker-compose.airflow.yml up -d
```

## Частые проблемы и решения

### Проблема: Scheduler падает с ошибкой подключения к БД

**Решение:**
1. Проверить, что postgres контейнер запущен и healthy
2. Проверить переменную окружения `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`
3. Убедиться, что контейнеры в одной сети
4. Перезапустить scheduler после postgres

### Проблема: Webserver не запускается

**Решение:**
1. Проверить логи webserver
2. Проверить, что порт 8080 не занят
3. Проверить переменные окружения

### Проблема: DAGs не отображаются / DAG не виден в UI

**Если конкретный DAG (например, `market_selection`) не появляется в списке:**

1. **Ошибки импорта** — в контейнере выполнить:
   ```bash
   docker exec pklpo-airflow-airflow-scheduler-1 airflow dags list-import-errors
   ```
   Если в списке есть `market_selection` (или путь к файлу) — в столбце будет текст ошибки. Исправить импорты или зависимости.

2. **Пересобрать образ** — DAG-файлы копируются в образ при сборке (в docker-compose volume dags не монтируется). После добавления или изменения DAG нужно пересобрать:
   ```bash
   cd D:\projects\pklpo
   docker-compose -f ops/airflow/docker-compose.airflow.yml build --no-cache airflow-webserver airflow-scheduler
   docker-compose -f ops/airflow/docker-compose.airflow.yml up -d airflow-webserver airflow-scheduler
   ```

3. **Проверить наличие файла в образе:**
   ```bash
   docker exec pklpo-airflow-airflow-scheduler-1 ls -la /opt/airflow/dags/
   ```
   Должны быть файлы: `market_selection.py`, `features_calc.py`, `features_calc_short.py`, и др.

4. **Проверить синтаксис DAG:**
   ```bash
   docker exec pklpo-airflow-airflow-scheduler-1 python -m py_compile /opt/airflow/dags/market_selection.py
   ```

5. **DAG есть, но выключен (paused)** — в UI включить переключатель слева от имени DAG.

### Проблема: Задачи не выполняются

**Решение:**
1. Проверить, что scheduler запущен
2. Проверить логи scheduler
3. Проверить, что executor настроен правильно (LocalExecutor)
4. Проверить подключение к основной БД pklpo_db

## Проверка работоспособности

После запуска проверить:

1. **Webserver доступен:**
   - Открыть http://localhost:8080
   - Логин: admin, пароль: admin (или из переменной AIRFLOW_ADMIN_PASSWORD)

2. **Scheduler работает:**
   ```bash
   docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-scheduler | Select-String -Pattern "Scheduler heartbeat"
   ```

3. **DAGs загружены:**
   - В UI должны быть видны DAGs: `features_calc`, `features_calc_short`, `market_selection`, `okx_swap_ohlcv_sync`, `okx_swap_ohlcv_sync_v2`
   - Если DAG нет в списке: см. раздел «DAGs не отображаются» выше

4. **Подключение к основной БД:**
   - Проверить, что контейнеры могут подключиться к pklpo_db через сеть

## Конфигурация сети

Airflow использует внешнюю сеть `pklpo_pklpo_network` для подключения к основной БД.

Проверить сеть:
```bash
docker network ls | Select-String "pklpo"
docker network inspect pklpo_pklpo_network
```

Если сети нет, создать:
```bash
docker network create pklpo_pklpo_network
```

---

## Runbook: swap_sync DB-аварии

Этот раздел охватывает инфраструктурные инциденты вокруг `pklpo_db` и DAG `okx_swap_ohlcv_sync_v2`.

> **Важно:** DB-слой (retry, pool_pre_ping, pool_recycle) смягчает кратковременные сбои, но **не устраняет** инфраструктурную аварию. Если `pklpo_db` не запущен или scheduler не видит его по сети — это инфраструктурная проблема. Чините её на уровне Docker/Compose, а не кода.

---

### Симптом: `connection is closed` / `Connect call failed`

**Что значит:** asyncpg потерял соединение с Postgres в момент выполнения запроса.

**Диагностика:**
```bash
# 1. Проверить, запущен ли pklpo_db
docker ps --filter "name=pklpo_db"

# 2. Проверить логи pklpo_db
docker logs pklpo_db --tail=50
```

**Решение:**
- Если `pklpo_db` в статусе `Restarting` — см. симптом «pklpo_db restarting» ниже.
- Если кратковременный сбой — swap_sync сам восстановится (pool_pre_ping + retry).
- Если DB стабильна, но swap_sync всё равно падает — проверить `pool_recycle` и переподключение.

---

### Симптом: `Name or service not known` / `Temporary failure in name resolution`

**Что значит:** scheduler/worker не может разрезолвить имя `pklpo_db` через Docker DNS.

**Причина:** контейнеры находятся в разных Docker-сетях.

**Диагностика:**
```bash
# Проверить, что pklpo_db и airflow-scheduler в одной сети
docker inspect pklpo_db | grep -A10 '"Networks"'
docker inspect pklpo-airflow-airflow-scheduler-1 | grep -A10 '"Networks"'
```

Оба контейнера должны быть в `pklpo_pklpo_network`.

**Решение:**
```bash
# Если scheduler не в pklpo_pklpo_network — подключить вручную
docker network connect pklpo_pklpo_network pklpo-airflow-airflow-scheduler-1

# Или пересобрать через docker-compose (сеть прописана в docker-compose.airflow.yml)
docker compose -f ops/airflow/docker-compose.airflow.yml down
docker compose -f ops/airflow/docker-compose.airflow.yml up -d
```

---

### Симптом: `pklpo_db restarting` — контейнер не стартует

**Причина:** `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` пустые или не заданы.

**Диагностика:**
```bash
docker logs pklpo_db --tail=30
# Ищем: "error: database is uninitialized and password option is not specified"
```

**Решение:**
1. Убедиться, что `.env` содержит все три переменные.
2. Проверить `scripts/docker-compose.yml` — секция `db.environment` должна иметь безопасные дефолты:
   ```yaml
   POSTGRES_DB: ${POSTGRES_DB:-pklpo}
   POSTGRES_USER: ${POSTGRES_USER:-pklpo_user}
   POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-strongpassword}
   ```
3. Пересоздать контейнер:
   ```bash
   docker compose -f scripts/docker-compose.yml up -d --force-recreate db
   ```

---

### Симптом: `airflow-scheduler cannot resolve pklpo_db`

Полная ошибка: `Name or service not known` при попытке подключиться к `pklpo_db:5432`.

**Причина:** scheduler запустился раньше, чем `pklpo_db` присоединился к `pklpo_pklpo_network`, или Compose-сети разведены.

**Решение:** см. симптом «Name or service not known» выше.

---

### Симптом: `validate_swap_sync_xcom` падает после успешного `swap_sync`

**Диагностика:** посмотреть XCom в Airflow UI: Admin → XComs → фильтровать по `swap_sync`.

**Возможные причины:**
- `swap_sync` вернул `skipped=True` без обязательных ключей (нормально, проверяет только `mode`).
- `format_stats_for_xcom` не передала один из ключей: `mode`, `timeframes`, `symbols_count`, `total_symbols_processed`, `duration_sec`, `rows_upserted_total`, `errors_count`, `candles_per_second`, `api_429_count`, `api_timeout_count`, `today_fill`.
- Non-skipped run действительно считается total failure и падает, если `rows_upserted_total == 0` или `total_symbols_processed == 0`; `errors_count > 0` сам по себе не делает DAG красным.

---

### После DB-аварии: восстановление схемы

Если `pklpo_db` поднялся с пустой БД:
```bash
# Запустить миграции
docker exec pklpo_app python -m src.cli.main migrate

# Проверить схему
docker exec pklpo_db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt"'
```

---

### Обновление Airflow-образов после изменения кода

Код проекта вшит в образ (нет bind-mount на `/opt/airflow/project`). После изменений в `src/`:
```bash
docker compose -f ops/airflow/docker-compose.airflow.yml build --no-cache airflow-webserver airflow-scheduler
docker compose -f ops/airflow/docker-compose.airflow.yml up -d --force-recreate airflow-webserver airflow-scheduler
```
