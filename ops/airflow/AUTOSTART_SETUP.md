# Настройка автозапуска Airflow при перезагрузке ПК

## Проблема

Airflow не запускается автоматически после перезагрузки Windows, потому что:
1. Docker Desktop может не запускаться автоматически
2. Контейнеры не стартуют, если Docker был остановлен

## Решение

### Вариант 1: Без автозапуска Docker (рекомендуется)

**Если вы не хотите, чтобы Docker запускался автоматически:**

1. **НЕ включайте** автозапуск Docker Desktop
2. Настройте автозапуск только Airflow (см. ниже)
3. Скрипт будет ждать, пока вы запустите Docker Desktop вручную

**Преимущества:**
- Docker не запускается автоматически (экономия ресурсов)
- Airflow запустится автоматически, как только вы откроете Docker Desktop
- Полный контроль над запуском Docker

**Недостатки:**
- Нужно вручную запустить Docker Desktop перед использованием Airflow

### Вариант 2: С автозапуском Docker

**Если хотите, чтобы всё запускалось автоматически:**

1. Включить автозапуск Docker Desktop:
   - Открыть Docker Desktop
   - Settings → General → "Start Docker Desktop when you log in" (включить)
   - Сохранить
2. Настроить автозапуск Airflow (см. ниже)

**Преимущества:**
- Полностью автоматический запуск
- Airflow доступен сразу после входа в систему

**Недостатки:**
- Docker всегда запущен (потребление ресурсов)

---

### Настройка автозапуска Airflow через планировщик задач

#### Вариант A: Через GUI

1. Открыть "Планировщик задач" (Task Scheduler)
2. Создать задачу:
   - Имя: `PKLPO Airflow Autostart`
   - Триггер: "При входе в систему" (At log on)
   - Действие: "Запустить программу"
     - Программа: `powershell.exe`
     - Аргументы: `-ExecutionPolicy Bypass -File "D:\projects\pklpo\scripts\start_airflow.ps1"`
     - Рабочая папка: `D:\projects\pklpo`
   - Условия:
     - ✅ "Запускать только при подключении к сети электропитания"
     - ✅ "Пробуждать компьютер для выполнения задачи"
   - Параметры:
     - ✅ "Выполнять задачу немедленно, если запланированный запуск был пропущен"
     - ✅ "Если задача не удалась, перезапускать каждые: 5 минут" (макс. 3 раза)

#### Вариант B: Через PowerShell (администратор)

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"D:\projects\pklpo\scripts\start_airflow.ps1`"" `
    -WorkingDirectory "D:\projects\pklpo"

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName "PKLPO Airflow Autostart" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Автозапуск Airflow при входе в систему"
```

### 3. Настройка времени ожидания Docker (опционально)

По умолчанию скрипт ждёт Docker 60 секунд. Если нужно изменить:

**Через GUI планировщика:**
- В аргументах добавить: `-MaxWaitSeconds 120` (например, для 2 минут)

**Через PowerShell:**
```powershell
-Argument "-ExecutionPolicy Bypass -File `"D:\projects\pklpo\scripts\start_airflow.ps1`" -MaxWaitSeconds 120"
```

**Для бесконечного ожидания** (скрипт будет ждать, пока Docker не запустится):
```powershell
-Argument "-ExecutionPolicy Bypass -File `"D:\projects\pklpo\scripts\start_airflow.ps1`" -MaxWaitSeconds 0"
```

### 4. Проверка

**Вариант 1 (без автозапуска Docker):**
1. После входа в систему запустить Docker Desktop вручную
2. Скрипт автоматически запустит Airflow контейнеры
3. Проверить: `docker-compose -f ops/airflow/docker-compose.airflow.yml ps`
4. Все контейнеры должны быть в статусе `Up`

**Вариант 2 (с автозапуском Docker):**
1. После перезагрузки ПК подождать 1-2 минуты
2. Проверить: `docker-compose -f ops/airflow/docker-compose.airflow.yml ps`
3. Все контейнеры должны быть в статусе `Up`

### 5. Ручной запуск

Если нужно запустить вручную:
```powershell
.\scripts\start_airflow.ps1
```

Или использовать скрипт быстрого исправления:
```powershell
.\scripts\fix_airflow.ps1
```

## Как это работает

### Вариант 1 (без автозапуска Docker):

1. Вы входите в систему
2. Планировщик задач запускает `start_airflow.ps1`
3. Скрипт проверяет Docker — не запущен
4. Скрипт ждёт до 60 секунд (или настроенное время)
5. Вы запускаете Docker Desktop вручную
6. Скрипт обнаруживает Docker и запускает контейнеры Airflow

**Важно:** Если вы не запустите Docker в течение времени ожидания, скрипт завершится с ошибкой. Но вы можете запустить его вручную позже через `.\scripts\fix_airflow.ps1`.

### Вариант 2 (с автозапуском Docker):

1. Вы входите в систему
2. Docker Desktop запускается автоматически
3. Планировщик задач запускает `start_airflow.ps1`
4. Скрипт проверяет Docker — запущен
5. Скрипт сразу запускает контейнеры Airflow

## Изменения в docker-compose.airflow.yml

- Добавлен `restart: always` для всех сервисов

Это гарантирует, что контейнеры перезапустятся, если Docker был перезапущен.
