# Исправление проблем запуска Airflow

## Проблемы, которые были исправлены

### 1. Ошибка монтирования volumes в Windows/WSL2

**Проблема:**
```
Error response from daemon: error while creating mount source path '/run/desktop/mnt/host/d/projects/pklpo/ops/airflow/dags': mkdir /run/desktop/mnt/host/d: file exists
```

**Решение:**
- Убрано монтирование volumes для dags, src, scripts
- DAGs и код уже скопированы в образ при сборке через Dockerfile
- Для разработки нужно пересобрать образ после изменения DAGs

### 2. Scheduler не может подключиться к PostgreSQL

**Проблема:**
```
sqlalchemy.exc.OperationalError: connection to server at "postgres" (172.21.0.6), port 5432 failed: Connection refused
```

**Решение:**
- Добавлен `condition: service_healthy` для `depends_on` postgres
- Теперь scheduler и webserver ждут, пока postgres станет healthy
- Добавлен `restart: unless-stopped` для автоматического перезапуска

## Изменения в docker-compose.airflow.yml

1. **Убраны проблемные volumes:**
   - `./dags:/opt/airflow/dags` - закомментировано
   - `../../src:/opt/airflow/project/src` - убрано
   - `../../scripts:/opt/airflow/project/scripts` - убрано
   - `../../pyproject.toml` и `../../requirements.txt` - убрано

2. **Добавлены health checks:**
   - `depends_on` с `condition: service_healthy` для всех сервисов

3. **Добавлен restart policy:**
   - `restart: always` для webserver и scheduler (автоматический перезапуск при падении)
   - `restart: always` для postgres

## Текущий статус

Все контейнеры должны быть запущены:
- ✅ `pklpo-airflow-postgres` - PostgreSQL для Airflow
- ✅ `pklpo-airflow-airflow-webserver-1` - Webserver на порту 8080
- ✅ `pklpo-airflow-airflow-scheduler-1` - Scheduler

## Проверка работоспособности

### 1. Проверить статус контейнеров:
```bash
cd D:\projects\pklpo
docker-compose -f ops/airflow/docker-compose.airflow.yml ps
```

### 2. Проверить логи:
```bash
# Scheduler
docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-scheduler --tail=50

# Webserver
docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-webserver --tail=50
```

### 3. Открыть веб-интерфейс:
- URL: http://localhost:8080
- Логин: `admin`
- Пароль: `admin` (или из переменной `AIRFLOW_ADMIN_PASSWORD`)

### 4. Проверить DAGs:
В веб-интерфейсе должны быть видны:
- `features_calc`
- `okx_swap_ohlcv_sync`

## Важные замечания

### Для разработки DAGs:

Если нужно изменить DAGs, есть два варианта:

1. **Пересобрать образ** (рекомендуется):
   ```bash
   cd D:\projects\pklpo
   docker-compose -f ops/airflow/docker-compose.airflow.yml build
   docker-compose -f ops/airflow/docker-compose.airflow.yml up -d
   ```

2. **Временно раскомментировать volumes** (если проблема с путями решена):
   - Раскомментировать `volumes` в docker-compose.airflow.yml
   - Убедиться, что Docker Desktop настроен правильно для File Sharing

### Для изменения кода проекта:

Код проекта (`src/`) уже скопирован в образ. Для применения изменений нужно пересобрать образ.

## Команды для управления

### Быстрое исправление и запуск:
```powershell
.\scripts\fix_airflow.ps1
```
Скрипт автоматически:
- Проверяет Docker
- Создаёт сеть, если нужно
- Запускает остановленные контейнеры
- Проверяет доступность webserver

### Запуск:
```bash
cd D:\projects\pklpo
docker-compose -f ops/airflow/docker-compose.airflow.yml up -d
```

### Остановка:
```bash
docker-compose -f ops/airflow/docker-compose.airflow.yml down
```

### Перезапуск:
```bash
docker-compose -f ops/airflow/docker-compose.airflow.yml restart
```

### Просмотр логов:
```bash
# Все сервисы
docker-compose -f ops/airflow/docker-compose.airflow.yml logs --tail=100 -f

# Только scheduler
docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-scheduler -f
```

## Решение проблемы "каждый день нужно исправлять"

### Проблема
Контейнеры останавливаются после перезагрузки или остановки Docker Desktop.

### Решение
1. **Изменён restart policy на `always`** — контейнеры автоматически перезапускаются
2. **Создан скрипт `scripts/fix_airflow.ps1`** — для быстрого исправления и запуска
3. **Настроить автозапуск** (см. [AUTOSTART_SETUP.md](AUTOSTART_SETUP.md)):
   - Включить автозапуск Docker Desktop
   - Добавить задачу в планировщик Windows для запуска `scripts/start_airflow.ps1`

### Ежедневное использование
Если контейнеры остановились, просто выполните:
```powershell
.\scripts\fix_airflow.ps1
```

## Если проблемы остались

См. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) для подробной диагностики.
