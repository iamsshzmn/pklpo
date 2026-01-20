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

### Проблема: DAGs не отображаются

**Решение:**
1. Проверить, что директория dags смонтирована правильно
2. Проверить синтаксис DAG файлов:
   ```bash
   docker exec pklpo-airflow-airflow-scheduler-1 python -m py_compile /opt/airflow/dags/features_calc.py
   ```
3. Проверить логи scheduler на ошибки парсинга DAGs

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
   - В UI должны быть видны DAGs: `features_calc`, `okx_swap_ohlcv_sync`

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
