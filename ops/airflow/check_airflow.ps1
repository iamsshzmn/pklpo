# Скрипт диагностики и исправления проблем Airflow

Write-Host "=== Диагностика Airflow ===" -ForegroundColor Cyan

# Проверка статуса контейнеров
Write-Host "`n1. Проверка статуса контейнеров:" -ForegroundColor Yellow
docker-compose -f ops/airflow/docker-compose.airflow.yml ps

# Проверка сети
Write-Host "`n2. Проверка сети:" -ForegroundColor Yellow
docker network inspect pklpo_pklpo_network 2>$null | Select-String -Pattern "Name|Containers" | Select-Object -First 10

# Проверка подключения к postgres
Write-Host "`n3. Проверка подключения к postgres:" -ForegroundColor Yellow
$postgresContainer = docker ps --filter "name=pklpo-airflow-postgres" --format "{{.Names}}"
if ($postgresContainer) {
    Write-Host "Postgres контейнер найден: $postgresContainer" -ForegroundColor Green
    docker exec $postgresContainer pg_isready -U airflow
} else {
    Write-Host "Postgres контейнер не найден!" -ForegroundColor Red
}

# Проверка логов scheduler
Write-Host "`n4. Последние ошибки scheduler:" -ForegroundColor Yellow
docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-scheduler --tail=20 2>&1 | Select-String -Pattern "error|Error|ERROR|failed|Failed" | Select-Object -Last 5

# Проверка логов webserver
Write-Host "`n5. Последние ошибки webserver:" -ForegroundColor Yellow
docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-webserver --tail=20 2>&1 | Select-String -Pattern "error|Error|ERROR|failed|Failed" | Select-Object -Last 5

Write-Host "`n=== Конец диагностики ===" -ForegroundColor Cyan
