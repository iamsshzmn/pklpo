param(
    [switch]$SkipTests,
    [switch]$SkipTypecheck,
    [switch]$SkipCli,
    [switch]$SkipPreCommit
)

$ErrorActionPreference = "Stop"
$failures = @()
$env:PRE_COMMIT_HOME = Join-Path $PSScriptRoot "..\\.pre-commit-cache"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
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
        $script:failures += $Name
        Write-Host "  FAIL: $_" -ForegroundColor Red
    }
}

Write-Host "[check-before-commit] Running repository-backed validation commands" -ForegroundColor Cyan

Invoke-Step "ruff check" { ruff check src tests }
Invoke-Step "black --check" { black --check src tests }

if (-not $SkipTypecheck) {
    Invoke-Step "mypy src" { mypy src }
}

if (-not $SkipTests) {
    Invoke-Step 'pytest --no-cov -m "not slow and not integration"' {
        pytest --no-cov -m "not slow and not integration"
    }
}

if (-not $SkipCli) {
    Invoke-Step "python -m src.cli.main --help" {
        python -m src.cli.main --help
    }
}

if (-not $SkipPreCommit) {
    Invoke-Step "pre-commit run --all-files" {
        pre-commit run --all-files
    }
}

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($failures.Count -gt 0) {
    Write-Host "[FAIL] Validation failed:" -ForegroundColor Red
    foreach ($failure in $failures) {
        Write-Host "  - $failure" -ForegroundColor Red
    }
    exit 1
}

Write-Host "[SUCCESS] Validation passed." -ForegroundColor Green
