# Автозапуск Airflow без автозапуска Docker

## Быстрая настройка

Если вы **не хотите**, чтобы Docker Desktop запускался автоматически:

### 1. Настроить автозапуск Airflow

**Через PowerShell (администратор):**

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"D:\projects\pklpo\scripts\start_airflow.ps1`" -MaxWaitSeconds 0" `
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
    -Description "Автозапуск Airflow при входе в систему (ждёт Docker)"
```

**Важно:** `-MaxWaitSeconds 0` означает бесконечное ожидание Docker.

### 2. Как это работает

1. Вы входите в систему
2. Планировщик задач запускает скрипт
3. Скрипт ждёт, пока вы запустите Docker Desktop
4. Как только Docker запустится, скрипт автоматически запустит Airflow

### 3. Использование

1. Войти в систему
2. Запустить Docker Desktop вручную (когда будете готовы)
3. Airflow запустится автоматически через несколько секунд

### 4. Проверка

```powershell
docker-compose -f ops/airflow/docker-compose.airflow.yml ps
```

Все контейнеры должны быть в статусе `Up`.

## Альтернатива: ограниченное ожидание

Если хотите, чтобы скрипт ждал только определённое время (например, 2 минуты):

```powershell
-Argument "-ExecutionPolicy Bypass -File `"D:\projects\pklpo\scripts\start_airflow.ps1`" -MaxWaitSeconds 120"
```

Если Docker не запустится за это время, скрипт завершится. Но вы можете запустить Airflow вручную позже:

```powershell
.\scripts\fix_airflow.ps1
```

## Преимущества

- ✅ Docker не запускается автоматически (экономия ресурсов)
- ✅ Полный контроль над запуском Docker
- ✅ Airflow запускается автоматически, как только Docker готов
- ✅ Не нужно каждый раз вручную запускать Airflow
