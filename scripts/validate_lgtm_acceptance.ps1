param(
    [switch]$SkipV1,
    [switch]$SkipRuntime,
    [switch]$RequireTrace,
    [string]$TempoUrl = "http://localhost:3200",
    [string]$GrafanaUrl = "http://localhost:3001",
    [string]$GrafanaUser = "admin",
    [string]$GrafanaPass = "admin",
    [string]$SampleTraceId = ""
)

$ErrorActionPreference = "Stop"
$Failures = 0

function Write-Check([int]$Id, [string]$Message) {
    Write-Host ""
    Write-Host "-- CHECK $Id`: $Message"
}

function Write-Pass([string]$Message) {
    Write-Host "   PASS: $Message"
}

function Write-Fail([string]$Message) {
    $script:Failures += 1
    Write-Host "   FAIL: $Message"
}

function Write-Skip([string]$Message) {
    Write-Host "   SKIP: $Message"
}

function Get-BasicAuthHeader([string]$User, [string]$Pass) {
    $token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Pass}"))
    return @{ Authorization = "Basic $token" }
}

Write-Host "PKLPO LGTM - Windows Acceptance Check"
Write-Host ([DateTime]::UtcNow.ToString("yyyy-MM-dd HH:mm:ss UTC"))

Write-Check 1 "v1 acceptance is delegated"
if ($SkipV1) {
    Write-Skip "v1 delegated check skipped by -SkipV1"
} elseif (Test-Path "scripts/validate_v1_acceptance.ps1") {
    $v1Args = @{ SkipStatic = $true }
    if ($SkipRuntime) {
        $v1Args["SkipRuntime"] = $true
    }
    & "scripts/validate_v1_acceptance.ps1" @v1Args
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "v1 acceptance passed"
    } else {
        Write-Fail "v1 acceptance failed"
    }
} else {
    Write-Fail "scripts/validate_v1_acceptance.ps1 is missing"
}

Write-Check 2 "Tempo datasource is provisioned statically"
$tempoDatasource = "ops/monitoring/grafana/provisioning/datasources/tempo.yml"
if (Test-Path $tempoDatasource) {
    $content = Get-Content -Raw $tempoDatasource
    if ($content -match "uid:\s*Tempo" -and $content -match "url:\s*http://tempo:3200") {
        Write-Pass "Tempo datasource UID and URL are stable"
    } else {
        Write-Fail "Tempo datasource does not expose UID Tempo and URL http://tempo:3200"
    }
} else {
    Write-Fail "Tempo datasource file is missing"
}

Write-Check 3 "High-cardinality fields are not Loki labels"
$promtailConfig = "ops/monitoring/promtail/promtail-config.yml"
$labelViolation = $false
if (Test-Path $promtailConfig) {
    $inLabels = $false
    foreach ($line in Get-Content $promtailConfig) {
        if ($line -match "^\s*-\s*labels:\s*$") {
            $inLabels = $true
            continue
        }
        if ($line -match "^\s*-\s*[A-Za-z_]+:\s*$") {
            $inLabels = $false
        }
        if ($inLabels -and $line -match "^\s+(run_id|trace_id|span_id):\s*$") {
            $labelViolation = $true
        }
    }
    if ($labelViolation) {
        Write-Fail "run_id, trace_id, or span_id appears under a Loki labels stage"
    } else {
        Write-Pass "run_id, trace_id, and span_id are not configured as Loki labels"
    }
} else {
    Write-Fail "promtail-config.yml is missing"
}

if ($SkipRuntime) {
    Write-Check 4 "runtime checks"
    Write-Skip "runtime checks skipped by -SkipRuntime"
} else {
    Write-Check 4 "Tempo /ready responds"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri "$TempoUrl/ready" -TimeoutSec 10 | Out-Null
        Write-Pass "Tempo ready endpoint responds at $TempoUrl/ready"
    } catch {
        Write-Fail "Tempo ready endpoint is not reachable at $TempoUrl/ready: $($_.Exception.Message)"
    }

    Write-Check 5 "Grafana exposes Tempo datasource"
    try {
        $headers = Get-BasicAuthHeader $GrafanaUser $GrafanaPass
        $response = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "$GrafanaUrl/api/datasources/uid/Tempo" `
            -Headers $headers `
            -TimeoutSec 10
        $datasource = $response.Content | ConvertFrom-Json
        if ($datasource.uid -eq "Tempo") {
            Write-Pass "Grafana API returns datasource UID Tempo"
        } else {
            Write-Fail "Grafana API returned unexpected datasource UID: $($datasource.uid)"
        }
    } catch {
        Write-Fail "Grafana API did not return datasource UID Tempo: $($_.Exception.Message)"
    }

    Write-Check 6 "sample trace is queryable when required"
    if ($RequireTrace) {
        if ([string]::IsNullOrWhiteSpace($SampleTraceId)) {
            Write-Fail "SampleTraceId is required with -RequireTrace"
        } else {
            try {
                Invoke-WebRequest -UseBasicParsing -Uri "$TempoUrl/api/traces/$SampleTraceId" -TimeoutSec 10 | Out-Null
                Write-Pass "Sample trace is queryable: $SampleTraceId"
            } catch {
                Write-Fail "Sample trace is not queryable: $SampleTraceId"
            }
        }
    } else {
        Write-Skip "sample trace check disabled until Stage 3 emits traces"
    }
}

Write-Host ""
if ($Failures -eq 0) {
    Write-Host "LGTM ACCEPTANCE: PASS"
} else {
    Write-Host "LGTM ACCEPTANCE: FAIL ($Failures checks failed)"
}

exit $Failures
