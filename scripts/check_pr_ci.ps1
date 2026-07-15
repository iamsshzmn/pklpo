param(
    [string]$Python = "python",
    [string]$BaseRef = "origin/main",
    [switch]$SkipMigrationGuard,
    [switch]$SkipLint,
    [switch]$SkipFastTests,
    [switch]$SkipLookahead,
    [switch]$SkipSmoke,
    [switch]$SkipCandlesDod,
    [switch]$IncludeNonBlocking,
    [switch]$StopOnFailure
)

$ErrorActionPreference = "Stop"
$failures = @()

$env:FEATURES_TA_BACKEND = "pandas_ta"
$env:ENVIRONMENT = "test"
$env:POSTGRES_USER = "pklpo_ci"
$env:POSTGRES_PASSWORD = "ci_dummy"
$env:POSTGRES_DB = "pklpo_ci"
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"

$FormatExcludes = @(
    "src/db/migrations/migrate_add_operational_reliability.py",
    "src/db/migrations/migrate_backfill_partitioned.py",
    "src/db/migrations/migrate_phase3_quant_tables.py",
    "src/db/migrations/migrate_validate_swap_ohlcv_constraints.py"
)

$MigrationAllowlist = @(
    "src/db/migrations/migrate_create_ops_feature_eligibility.py",
    "src/db/migrations/migrate_create_ops_feature_eligibility_transitions.py",
    "src/db/migrations/migrate_drop_redundant_swap_ohlcv_indexes.py"
)

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action,
        [switch]$NonBlocking
    )

    Write-Host ""
    Write-Host "[$Name]" -ForegroundColor Yellow

    try {
        & $Action
        if ($LASTEXITCODE -ne 0) {
            throw "Command exited with code $LASTEXITCODE"
        }
        Write-Host "  OK" -ForegroundColor Green
    } catch {
        if ($NonBlocking) {
            Write-Host "  NON-BLOCKING FAIL: $_" -ForegroundColor DarkYellow
            return
        }

        $script:failures += $Name
        Write-Host "  FAIL: $_" -ForegroundColor Red

        if ($StopOnFailure) {
            throw
        }
    }
}

function Test-MigrationGuard {
    $paths = @(
        "src/market_selection/migrations/*.sql",
        "src/candles/migrations/*.sql",
        "src/*/migrations/*.sql",
        "src/db/migrations/*.py"
    )

    $changed = @(git diff --name-status $BaseRef HEAD -- $paths 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "git diff failed. Ensure '$BaseRef' exists locally or pass -BaseRef."
    }

    $filtered = @()
    foreach ($line in $changed) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $parts = $line -split "`t"
        $path = $parts[-1]
        if ($MigrationAllowlist -contains $path) {
            continue
        }

        $filtered += $line
    }

    if ($filtered.Count -eq 0) {
        Write-Host "  No migration changes."
        return
    }

    Write-Host "  Changed migration files:"
    foreach ($line in $filtered) {
        Write-Host "    $line"
    }

    foreach ($line in $filtered) {
        $status = ($line -split "`t")[0]
        if ($status -match "^(M|D|R|C|T|U)") {
            throw "Existing migration files are immutable; add a new migration file instead."
        }
    }

    Write-Host "  Only new migration files - OK."
}

function Invoke-RuffFormatCheck {
    $args = @("format", "--check", "src", "tests")
    foreach ($exclude in $FormatExcludes) {
        $args += @("--exclude", $exclude)
    }

    & $Python -m ruff @args
}

Write-Host "[check-pr-ci] Running local equivalent of blocking GitHub PR gates" -ForegroundColor Cyan
Write-Host "Python: $Python"
Write-Host "BaseRef: $BaseRef"

if (-not $SkipMigrationGuard) {
    Invoke-Step "migration immutability guard" { Test-MigrationGuard }
}

if (-not $SkipLint) {
    Invoke-Step "ruff check src tests" {
        & $Python -m ruff check src tests
    }
    Invoke-Step "ruff format --check src tests" {
        Invoke-RuffFormatCheck
    }
}

if (-not $SkipFastTests) {
    Invoke-Step 'pytest -m "not slow and not integration"' {
        & $Python -m pytest -m "not slow and not integration" --override-ini addopts="" -q --tb=short
    }
}

if (-not $SkipLookahead) {
    Invoke-Step "pytest -m lookahead" {
        & $Python -m pytest -m lookahead --override-ini addopts="" -q --tb=short
    }
}

if (-not $SkipSmoke) {
    Invoke-Step "python -m src.cli.main --help" {
        & $Python -m src.cli.main --help
    }
}

if (-not $SkipCandlesDod) {
    Invoke-Step "candles DoD" {
        & $Python scripts/run_candles_dod.py --cov-fail-under=50
    }
}

if ($IncludeNonBlocking) {
    Invoke-Step "mypy src (non-blocking in CI)" {
        & $Python -m mypy src
    } -NonBlocking

    Invoke-Step "pytest benchmark (non-blocking in CI)" {
        & $Python -m pytest tests/features/benchmarks/bench_pipeline.py -q --benchmark-json=benchmarks/results/pytest_benchmark.json --override-ini addopts=""
    } -NonBlocking

    Invoke-Step "features group benchmark (non-blocking in CI)" {
        & $Python scripts/run_features_group_benchmark.py
    } -NonBlocking
}

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($failures.Count -gt 0) {
    Write-Host "[FAIL] Blocking PR validation failed:" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "  - $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host "[SUCCESS] Blocking PR validation passed." -ForegroundColor Green
