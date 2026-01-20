# Быстрое исправление Airflow

## Проблема: localhost:8080 не работает

### Решение (1 команда):
```powershell
.\scripts\fix_airflow.ps1
```

Скрипт автоматически:
- ✅ Проверяет Docker
- ✅ Создаёт сеть, если нужно
- ✅ Запускает остановленные контейнеры
- ✅ Проверяет доступность webserver

### Альтернатива (вручную):
```powershell
docker-compose -f ops/airflow/docker-compose.airflow.yml up -d
```

## Проверка

1. **Статус контейнеров:**
   ```powershell
   docker-compose -f ops/airflow/docker-compose.airflow.yml ps
   ```
   Все должны быть в статусе `Up`

2. **Открыть веб-интерфейс:**
   - URL: http://localhost:8080
   - Логин: `admin`
   - Пароль: `admin`

## Почему это происходит?

Контейнеры останавливаются после:
- Перезагрузки Windows
- Остановки Docker Desktop
- Сбоя контейнеров

## Постоянное решение

Настроить автозапуск (см. [AUTOSTART_SETUP.md](AUTOSTART_SETUP.md)):
1. Включить автозапуск Docker Desktop
2. Добавить задачу в планировщик Windows

После настройки контейнеры будут запускаться автоматически.
