# Скрипт для ручной проверки кода перед коммитом
# Использование: .\scripts\check_before_commit.ps1

param(
    [switch]$SkipTests,
    [switch]$SkipFormat,
    [switch]$AllFiles
)

$ErrorActionPreference = "Stop"

Write-Host "[*] Запуск проверок кода..." -ForegroundColor Cyan
Write-Host ""

$errors = @()
$warnings = @()

# ============================================
# 1. Ruff lint
# ============================================
Write-Host "[1] Ruff lint..." -ForegroundColor Yellow
try {
    if ($AllFiles) {
        ruff check --fix src/ tests/
    } else {
        ruff check --fix src/
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    [OK] Ruff lint пройден" -ForegroundColor Green
    } else {
        $errors += "Ruff lint"
        Write-Host "    [FAIL] Ruff lint нашел ошибки" -ForegroundColor Red
    }
} catch {
    $errors += "Ruff lint"
    Write-Host "    [FAIL] Ошибка: $_" -ForegroundColor Red
}

# ============================================
# 2. Ruff format
# ============================================
if (-not $SkipFormat) {
    Write-Host "[2] Ruff format..." -ForegroundColor Yellow
    try {
        if ($AllFiles) {
            ruff format src/ tests/
        } else {
            ruff format src/
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    [OK] Ruff format выполнен" -ForegroundColor Green
        } else {
            $warnings += "Ruff format"
            Write-Host "    [WARN] Ruff format нашел изменения" -ForegroundColor Yellow
        }
    } catch {
        $warnings += "Ruff format"
        Write-Host "    [WARN] Ошибка: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "[2] Ruff format... пропущен (--SkipFormat)" -ForegroundColor Gray
}

# ============================================
# 3. Black (для совместимости)
# ============================================
if (-not $SkipFormat) {
    Write-Host "[3] Black format..." -ForegroundColor Yellow
    try {
        if ($AllFiles) {
            black src/ tests/ --line-length 88
        } else {
            black src/ --line-length 88
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    [OK] Black format выполнен" -ForegroundColor Green
        } else {
            $warnings += "Black format"
            Write-Host "    [WARN] Black format нашел изменения" -ForegroundColor Yellow
        }
    } catch {
        $warnings += "Black format"
        Write-Host "    [WARN] Ошибка: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "[3] Black format... пропущен (--SkipFormat)" -ForegroundColor Gray
}

# ============================================
# 4. Bandit (безопасность)
# ============================================
Write-Host "[4] Bandit (безопасность)..." -ForegroundColor Yellow
try {
    bandit -r src/ -c pyproject.toml -f json -ll
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    [OK] Bandit проверка пройдена" -ForegroundColor Green
    } else {
        $warnings += "Bandit"
        Write-Host "    [WARN] Bandit нашел предупреждения" -ForegroundColor Yellow
    }
} catch {
    $warnings += "Bandit"
    Write-Host "    [WARN] Ошибка: $_" -ForegroundColor Yellow
}

# ============================================
# 5. Быстрые unit-тесты
# ============================================
if (-not $SkipTests) {
    Write-Host "[5] Быстрые unit-тесты..." -ForegroundColor Yellow
    try {
        $env:PYTHONPATH = "."
        if ($AllFiles) {
            pytest src/ -m "not slow and not integration" -v --tb=short -x --maxfail=3
        } else {
            pytest src/ -m "not slow and not integration" -v --tb=short -x --maxfail=3 --ignore=src/features/tests/quick_test.py --ignore=scripts/
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    [OK] Тесты пройдены" -ForegroundColor Green
        } else {
            $errors += "Тесты"
            Write-Host "    [FAIL] Тесты не пройдены" -ForegroundColor Red
        }
    } catch {
        $errors += "Тесты"
        Write-Host "    [FAIL] Ошибка: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[5] Быстрые unit-тесты... пропущены (--SkipTests)" -ForegroundColor Gray
}

# ============================================
# 6. Базовые проверки (pre-commit)
# ============================================
Write-Host "[6] Базовые проверки (pre-commit)..." -ForegroundColor Yellow
try {
    if ($AllFiles) {
        pre-commit run --all-files
    } else {
        pre-commit run
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    [OK] Базовые проверки пройдены" -ForegroundColor Green
    } else {
        $errors += "Базовые проверки"
        Write-Host "    [FAIL] Базовые проверки не пройдены" -ForegroundColor Red
    }
} catch {
    $warnings += "Базовые проверки"
    Write-Host "    [WARN] Pre-commit не установлен или ошибка: $_" -ForegroundColor Yellow
}

# ============================================
# Итоги
# ============================================
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($errors.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host "[SUCCESS] Все проверки пройдены успешно!" -ForegroundColor Green
    exit 0
} elseif ($errors.Count -eq 0) {
    Write-Host "[WARN] Проверки пройдены с предупреждениями:" -ForegroundColor Yellow
    foreach ($w in $warnings) {
        Write-Host "   - $w" -ForegroundColor Yellow
    }
    exit 0
} else {
    Write-Host "[FAIL] Обнаружены ошибки:" -ForegroundColor Red
    foreach ($e in $errors) {
        Write-Host "   - $e" -ForegroundColor Red
    }
    if ($warnings.Count -gt 0) {
        Write-Host ""
        Write-Host "[WARN] Предупреждения:" -ForegroundColor Yellow
        foreach ($w in $warnings) {
            Write-Host "   - $w" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    Write-Host "Исправьте ошибки перед коммитом!" -ForegroundColor Red
    exit 1
}
