# Script to split large changes into logical commits
# Usage: .\scripts\commit_in_chunks.ps1 [-DryRun]

param(
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

Write-Host "`n=== Splitting changes into logical commits ===" -ForegroundColor Cyan
$mode = if ($DryRun) { "DRY-RUN (check)" } else { "APPLY" }
Write-Host "Mode: $mode`n" -ForegroundColor $(if ($DryRun) { 'Yellow' } else { 'Green' })

# Check we're in git repo
if (-not (Test-Path ".git")) {
    Write-Host "ERROR: .git not found. Run script from repo root." -ForegroundColor Red
    exit 1
}

# Step 1: Remove files from index that should be in .gitignore
Write-Host "`n[1/9] Removing ignored files from index..." -ForegroundColor Yellow
$filesToRemove = @(".cursorrules", ".env.backup")
$oldErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$hasChanges = $false
foreach ($file in $filesToRemove) {
    # Check if file is tracked in HEAD
    $null = git ls-tree HEAD $file 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        if ($DryRun) {
            Write-Host "  [DRY-RUN] git rm --cached $file" -ForegroundColor Gray
            $hasChanges = $true
        } else {
            git rm --cached $file 2>&1 | Out-Null
            Write-Host "  OK: Removed from git: $file" -ForegroundColor Green
            $hasChanges = $true
        }
    } else {
        Write-Host "  Skip: $file not tracked" -ForegroundColor Gray
    }
}
$ErrorActionPreference = $oldErrorAction
if ($hasChanges) {
    if ($DryRun) {
        Write-Host "  [DRY-RUN] git commit -m 'chore: remove ignored files from git'" -ForegroundColor Gray
    } else {
        git commit -m "chore: remove ignored files from git"
        Write-Host "  OK: Commit created" -ForegroundColor Green
    }
}

# Step 2: Dev tools and configs
Write-Host "`n[2/9] Dev tools and configs..." -ForegroundColor Yellow
$configFiles = @(
    ".editorconfig",
    ".gitignore",
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "requirements.txt",
    ".github/workflows/ci.yml"
)
if ($DryRun) {
    Write-Host "  [DRY-RUN] git add $($configFiles -join ' ')" -ForegroundColor Gray
    Write-Host "  [DRY-RUN] git commit -m 'chore: update dev tools and configs'" -ForegroundColor Gray
} else {
    git add $configFiles
    git commit -m "chore: update dev tools and configs"
    Write-Host "  OK: Commit created" -ForegroundColor Green
}

# Step 3: Root documentation
Write-Host "`n[3/9] Root documentation..." -ForegroundColor Yellow
$docsRoot = @(
    "README.md",
    "config/README.md",
    "src/README.md"
)
if ($DryRun) {
    Write-Host "  [DRY-RUN] git add $($docsRoot -join ' ')" -ForegroundColor Gray
    Write-Host "  [DRY-RUN] git commit -m 'docs: update root documentation'" -ForegroundColor Gray
} else {
    git add $docsRoot
    git commit -m "docs: update root documentation"
    Write-Host "  OK: Commit created" -ForegroundColor Green
}

# Step 4: MTF configs
Write-Host "`n[4/9] MTF configs..." -ForegroundColor Yellow
$mtfConfigs = @(
    "config/mtf_phase3.yaml",
    "config/mtf_phase3_development.yaml",
    "config/mtf_phase3_production.yaml"
)
if ($DryRun) {
    Write-Host "  [DRY-RUN] git add $($mtfConfigs -join ' ')" -ForegroundColor Gray
    Write-Host "  [DRY-RUN] git commit -m 'config: update MTF phase3 configs'" -ForegroundColor Gray
} else {
    git add $mtfConfigs
    git commit -m "config: update MTF phase3 configs"
    Write-Host "  OK: Commit created" -ForegroundColor Green
}

# Step 5: Docker and Airflow
Write-Host "`n[5/9] Docker and Airflow..." -ForegroundColor Yellow
if ($DryRun) {
    Write-Host "  [DRY-RUN] git add docker/ ops/airflow/" -ForegroundColor Gray
    Write-Host "  [DRY-RUN] git commit -m 'ops: update Docker and Airflow configs'" -ForegroundColor Gray
} else {
    git add docker/ ops/airflow/
    git commit -m "ops: update Docker and Airflow configs"
    Write-Host "  OK: Commit created" -ForegroundColor Green
}

# Step 6: Planning docs
Write-Host "`n[6/9] Planning docs..." -ForegroundColor Yellow
if ($DryRun) {
    Write-Host "  [DRY-RUN] git add plan/" -ForegroundColor Gray
    Write-Host "  [DRY-RUN] git commit -m 'docs: update planning documents'" -ForegroundColor Gray
} else {
    git add plan/
    git commit -m "docs: update planning documents"
    Write-Host "  OK: Commit created" -ForegroundColor Green
}

# Step 7: Source code (split into subcategories)
Write-Host "`n[7/9] Source code (splitting into parts)..." -ForegroundColor Yellow

# 7a: CLI and utilities
Write-Host "  [7a] CLI and utilities..." -ForegroundColor Cyan
$cliFiles = @(
    "src/cli/",
    "src/utils/",
    "src/logging_config.py",
    "src/database.py"
)
if ($DryRun) {
    Write-Host "    [DRY-RUN] git add $($cliFiles -join ' ')" -ForegroundColor Gray
    Write-Host "    [DRY-RUN] git commit -m 'refactor: update CLI and utilities'" -ForegroundColor Gray
} else {
    git add $cliFiles
    git commit -m "refactor: update CLI and utilities"
    Write-Host "    OK: Commit created" -ForegroundColor Green
}

# 7b: Features module
Write-Host "  [7b] Features module..." -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "    [DRY-RUN] git add src/features/" -ForegroundColor Gray
    Write-Host "    [DRY-RUN] git commit -m 'refactor: update features module'" -ForegroundColor Gray
} else {
    git add src/features/
    git commit -m "refactor: update features module"
    Write-Host "    OK: Commit created" -ForegroundColor Green
}

# 7c: Remaining src modules
Write-Host "  [7c] Remaining modules..." -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "    [DRY-RUN] git add src/" -ForegroundColor Gray
    Write-Host "    [DRY-RUN] git commit -m 'refactor: update remaining source modules'" -ForegroundColor Gray
} else {
    git add src/
    git commit -m "refactor: update remaining source modules"
    Write-Host "    OK: Commit created" -ForegroundColor Green
}

# Step 8: Scripts
Write-Host "`n[8/9] Scripts..." -ForegroundColor Yellow
if ($DryRun) {
    Write-Host "  [DRY-RUN] git add scripts/" -ForegroundColor Gray
    Write-Host "  [DRY-RUN] git commit -m 'chore: update scripts'" -ForegroundColor Gray
} else {
    git add scripts/
    git commit -m "chore: update scripts"
    Write-Host "  OK: Commit created" -ForegroundColor Green
}

# Step 9: New untracked files
Write-Host "`n[9/9] New files..." -ForegroundColor Yellow
$newFiles = @(
    ".cursorignore",
    "GIT_WORKFLOW.md",
    "scripts/cleanup_git_tracked.ps1",
    "scripts/commit_in_chunks.ps1"
)
if ($DryRun) {
    Write-Host "  [DRY-RUN] git add $($newFiles -join ' ')" -ForegroundColor Gray
    Write-Host "  [DRY-RUN] git commit -m 'chore: add git workflow helpers'" -ForegroundColor Gray
} else {
    git add $newFiles
    git commit -m "chore: add git workflow helpers"
    Write-Host "  OK: Commit created" -ForegroundColor Green
}

Write-Host "`n=== Done ===" -ForegroundColor Green
if ($DryRun) {
    Write-Host "`nTo apply run: .\scripts\commit_in_chunks.ps1" -ForegroundColor Yellow
} else {
    Write-Host "`nCheck result: git log --oneline -10" -ForegroundColor Yellow
    Write-Host "If OK, push: git push" -ForegroundColor Yellow
}
