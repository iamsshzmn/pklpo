param(
    [string]$VenvPath = ".venv",
    [switch]$IncludePerformance
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py", "-3.11")
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }

    throw "Python 3.11 was not found on PATH."
}

$python = Resolve-Python

if (-not (Test-Path $VenvPath)) {
    Write-Host "[bootstrap] Creating virtual environment at $VenvPath"
    if ($python.Length -eq 1) {
        & $python[0] -m venv $VenvPath
    } else {
        & $python[0] $python[1] -m venv $VenvPath
    }
}

$venvPython = Join-Path $VenvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment is missing $venvPython"
}

Write-Host "[bootstrap] Upgrading pip"
& $venvPython -m pip install --upgrade pip

$extras = ".[dev]"
if ($IncludePerformance) {
    $extras = ".[dev,performance]"
}

Write-Host "[bootstrap] Installing project dependencies $extras"
& $venvPython -m pip install -e $extras

Write-Host ""
Write-Host "[bootstrap] Done."
Write-Host "Activate with: $VenvPath\Scripts\Activate.ps1"
