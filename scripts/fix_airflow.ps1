# Скрипт для быстрого исправления и запуска Airflow
# Использование: .\scripts\fix_airflow.ps1

$ErrorActionPreference = "Continue"
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== Исправление и запуск Airflow ===" -ForegroundColor Cyan
Write-Host "Проект: $script:ProjectRoot" -ForegroundColor Gray

# Функция проверки доступности Docker
function Test-DockerAvailable {
    try {
        $null = docker info 2>&1 | Out-Null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

# Проверка Docker
if (-not (Test-DockerAvailable)) {
    Write-Host "Docker не запущен! Запустите Docker Desktop и повторите попытку." -ForegroundColor Red
    exit 1
}
Write-Host "Docker запущен" -ForegroundColor Green

# Проверка сети
Write-Host "Проверка сети pklpo_pklpo_network..." -ForegroundColor Yellow
$networkExists = docker network ls --format "{{.Name}}" | Select-String -Pattern "^pklpo_pklpo_network$"
if (-not $networkExists) {
    Write-Host "Создание сети pklpo_pklpo_network..." -ForegroundColor Yellow
    docker network create pklpo_pklpo_network
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Ошибка создания сети" -ForegroundColor Red
        exit 1
    }
    Write-Host "Сеть создана" -ForegroundColor Green
}
else {
    Write-Host "Сеть существует" -ForegroundColor Green
}

# Проверка статуса контейнеров
Write-Host "`nПроверка текущего статуса контейнеров..." -ForegroundColor Yellow
Push-Location $script:ProjectRoot
try {
    $status = docker-compose -f ops/airflow/docker-compose.airflow.yml ps --format json 2>&1 | ConvertFrom-Json

    $stopped = @()
    foreach ($container in $status) {
        if ($container.State -ne "running") {
            $stopped += $container.Name
        }
    }

    if ($stopped.Count -gt 0) {
        Write-Host "Остановленные контейнеры: $($stopped -join ', ')" -ForegroundColor Yellow
        Write-Host "Запуск контейнеров..." -ForegroundColor Yellow
        docker-compose -f ops/airflow/docker-compose.airflow.yml up -d

        if ($LASTEXITCODE -ne 0) {
            Write-Host "Ошибка запуска контейнеров" -ForegroundColor Red
            exit 1
        }

        Write-Host "Ожидание запуска (10 секунд)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
    else {
        Write-Host "Все контейнеры уже запущены" -ForegroundColor Green
    }

    # Финальная проверка
    Write-Host "`nФинальный статус контейнеров:" -ForegroundColor Cyan
    docker-compose -f ops/airflow/docker-compose.airflow.yml ps

    # Проверка доступности webserver
    Write-Host "`nПроверка доступности webserver..." -ForegroundColor Yellow
    $response = try {
        Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        $true
    }
    catch {
        $false
    }

    if ($response) {
        Write-Host "Webserver доступен: http://localhost:8080" -ForegroundColor Green
    }
    else {
        Write-Host "Webserver не отвечает. Проверьте логи:" -ForegroundColor Yellow
        Write-Host "  docker-compose -f ops/airflow/docker-compose.airflow.yml logs airflow-webserver --tail=50" -ForegroundColor Gray
    }

}
finally {
    Pop-Location
}

Write-Host "`n=== Завершено ===" -ForegroundColor Cyan
Write-Host "Если проблемы остались, проверьте логи:" -ForegroundColor Yellow
Write-Host "  docker-compose -f ops/airflow/docker-compose.airflow.yml logs" -ForegroundColor Gray
