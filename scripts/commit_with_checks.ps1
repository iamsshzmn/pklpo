# Скрипт для коммита с ручной проверкой кода
# Использование: .\scripts\commit_with_checks.ps1 "сообщение коммита"

param(
    [Parameter(Mandatory=$true)]
    [string]$Message,

    [switch]$SkipTests,
    [switch]$SkipFormat,
    [switch]$AllFiles,
    [switch]$SkipChecks
)

$ErrorActionPreference = "Stop"

if ($SkipChecks) {
    Write-Host "⚠️  Пропуск всех проверок (--SkipChecks)" -ForegroundColor Yellow
    git add -A
    git commit -m $Message
    exit $LASTEXITCODE
}

Write-Host "🔍 Запуск проверок перед коммитом..." -ForegroundColor Cyan
Write-Host ""

# Запускаем скрипт проверок
$checkScript = Join-Path $PSScriptRoot "check_before_commit.ps1"
$checkParams = @()

if ($SkipTests) {
    $checkParams += "-SkipTests"
}
if ($SkipFormat) {
    $checkParams += "-SkipFormat"
}
if ($AllFiles) {
    $checkParams += "-AllFiles"
}

& $checkScript @checkParams
$checkExitCode = $LASTEXITCODE

if ($checkExitCode -ne 0) {
    Write-Host ""
    Write-Host "❌ Проверки не пройдены. Исправьте ошибки перед коммитом." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "📝 Создание коммита..." -ForegroundColor Cyan

# Добавляем все изменения
git add -A

# Создаём коммит
git commit -m $Message
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Коммит создан успешно" -ForegroundColor Green
} else {
    Write-Host "❌ Ошибка при создании коммита" -ForegroundColor Red
    exit 1
}
