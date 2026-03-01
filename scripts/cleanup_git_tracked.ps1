# Скрипт для удаления из Git индекса файлов, которые должны быть в .gitignore
# Использование: .\scripts\cleanup_git_tracked.ps1

Write-Host "Очистка Git индекса от файлов, которые должны быть игнорируемыми..." -ForegroundColor Yellow

# Список паттернов для удаления из индекса
$patterns = @(
    ".vscode",
    ".idea",
    ".cursorrules",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "logs",
    "ops/airflow/logs",
    "ops/airflow/dags/__pycache__",
    ".env.backup",
    "*.backup",
    "data",
    "datasets",
    "tmp",
    "backups",
    "dist",
    "build",
    "*.egg-info"
)

$removed = 0

foreach ($pattern in $patterns) {
    Write-Host "Проверка: $pattern" -ForegroundColor Cyan

    # Проверяем, есть ли такие файлы в индексе
    $files = git ls-files | Select-String -Pattern $pattern

    if ($files) {
        Write-Host "  Найдено файлов: $($files.Count)" -ForegroundColor Green

        # Удаляем из индекса, но оставляем на диске
        git rm -r --cached $pattern 2>$null

        if ($LASTEXITCODE -eq 0) {
            $removed += $files.Count
            Write-Host "  OK: Удалено из индекса" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: Ошибка или файлы не найдены в индексе" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host "  Нет файлов в индексе" -ForegroundColor Gray
    }
}

Write-Host "`nИтого удалено из индекса: $removed файлов" -ForegroundColor Green
Write-Host "`nПроверьте статус: git status --short" -ForegroundColor Yellow
Write-Host "Если всё правильно, сделайте коммит: git commit -m 'chore: remove ignored files from git index'" -ForegroundColor Yellow
