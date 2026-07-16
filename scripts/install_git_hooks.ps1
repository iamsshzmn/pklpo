param(
    [switch]$Uninstall,
    [string]$HooksPath = ".githooks"
)

$ErrorActionPreference = "Stop"

function Invoke-Git {
    param([string[]]$GitArgs)

    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') exited with code $LASTEXITCODE"
    }
}

if ($Uninstall) {
    $current = & git config --get core.hooksPath
    if ($current -eq $HooksPath) {
        Invoke-Git -GitArgs @("config", "--unset", "core.hooksPath")
        Write-Host "Removed core.hooksPath=$HooksPath" -ForegroundColor Yellow
    } else {
        Write-Host "core.hooksPath is '$current'; not changing it." -ForegroundColor Yellow
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $HooksPath -PathType Container)) {
    throw "Hooks directory not found: $HooksPath"
}

if (-not (Test-Path -LiteralPath (Join-Path $HooksPath "pre-push") -PathType Leaf)) {
    throw "pre-push hook not found under $HooksPath"
}

Invoke-Git -GitArgs @("config", "core.hooksPath", $HooksPath)

$configured = & git config --get core.hooksPath
Write-Host "Configured core.hooksPath=$configured" -ForegroundColor Green
Write-Host "Pre-push will run scripts/check_pr_ci.ps1 before git push." -ForegroundColor Green
Write-Host "Bypass intentionally with: `$env:PKLPO_SKIP_PR_CI='1'" -ForegroundColor Yellow
