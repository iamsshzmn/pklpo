Скрипт автозапуска Airflow при старте системы
# Использование: добавить в планировщик задач Windows с триггером "При входе в систему"

param(
    [switch]$WaitForDocker = $true,
    [int]$MaxWaitSeconds = 60  # 0 = ждать бесконечно
)

$ErrorActionPreference = "Stop"
$script:ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== Автозапуск Airflow ===" -ForegroundColor Cyan
Write-Host "Проект: $script:ProjectRoot" -ForegroundColor Gray

# Функция проверки доступности Docker
function Test-DockerAvailable {
    try {
        $null = docker info 2>&1
        return $true
    }
    catch {
        return $false
    }
}

# Ожидание запуска Docker
if ($WaitForDocker) {
    Write-Host "Ожидание запуска Docker..." -ForegroundColor Yellow
    if ($MaxWaitSeconds -eq 0) {
        Write-Host "  Ожидание бесконечно (запустите Docker Desktop вручную)" -ForegroundColor Gray
    }
    else {
        Write-Host "  Максимальное время ожидания: $MaxWaitSeconds секунд" -ForegroundColor Gray
    }

    $waited = 0
    while (-not (Test-DockerAvailable)) {
        if ($MaxWaitSeconds -gt 0 -and $waited -ge $MaxWaitSeconds) {
            Write-Host "Docker не запустился за $MaxWaitSeconds секунд" -ForegroundColor Red
            Write-Host "Запустите Docker Desktop вручную и выполните: .\scripts\fix_airflow.ps1" -ForegroundColor Yellow
            exit 1
        }
        Start-Sleep -Seconds 2
        $waited += 2
        if ($MaxWaitSeconds -gt 0) {
            Write-Host "  Ожидание... ($waited/$MaxWaitSeconds сек)" -ForegroundColor Gray
        }
        else {
            if (($waited % 10) -eq 0) {
                Write-Host "  Ожидание... ($waited сек) - запустите Docker Desktop" -ForegroundColor Gray
            }
        }
    }
    Write-Host "Docker запущен" -ForegroundColor Green
}

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
}

# Запуск Airflow
Write-Host "Запуск Airflow контейнеров..." -ForegroundColor Yellow
Push-Location $script:ProjectRoot
try {
    docker-compose -f ops/airflow/docker-compose.airflow.yml up -d
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Ошибка запуска контейнеров" -ForegroundColor Red
        exit 1
    }
    Write-Host "Airflow запущен успешно" -ForegroundColor Green

    # Проверка статуса через 5 секунд
    Start-Sleep -Seconds 5
    Write-Host "`nСтатус контейнеров:" -ForegroundColor Cyan
    docker-compose -f ops/airflow/docker-compose.airflow.yml ps
}
finally {
    Pop-Location
}

Write-Host "`n=== Завершено ===" -ForegroundColor Cyan
