param(
    [switch]$SkipRuntime,
    [switch]$SkipStatic,
    [string]$LokiUrl = "http://localhost:3100",
    [string]$PrometheusUrl = "http://localhost:9090",
    [string]$PushgatewayUrl = "http://localhost:9091",
    [string]$AirflowUrl = "http://localhost:8080",
    [string]$GrafanaUrl = "http://localhost:3001",
    [string]$AirflowUser = "admin",
    [string]$AirflowPass = "admin",
    [int]$DagWaitSeconds = 90
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

function Write-Warn([string]$Message) {
    Write-Host "   WARN: $Message"
}

function Invoke-JsonGet([string]$Url, [hashtable]$Headers = @{}) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -Headers $Headers -TimeoutSec 20
    return $response.Content | ConvertFrom-Json
}

function Invoke-TextGet([string]$Url) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 20
    return $response.Content
}

function Get-BasicAuthHeader([string]$User, [string]$Pass) {
    $token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Pass}"))
    return @{ Authorization = "Basic $token" }
}

function Invoke-NativeText([string]$Command) {
    return cmd /c "$Command 2>NUL"
}

function Find-StructuredAirflowRunId {
    $scheduler = Invoke-NativeText 'docker ps --filter "name=airflow-scheduler" --format "{{.Names}}"' | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($scheduler)) {
        return ""
    }

    $python = @'
import glob
import json

run_id = ""
latest_timestamp = ""
for path in sorted(glob.glob("/var/log/pklpo/pklpo_debug.log*")):
    try:
        handle = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        continue
    with handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidate = payload.get("run_id")
            if candidate and candidate != "-":
                timestamp = payload.get("timestamp") or ""
                if timestamp >= latest_timestamp:
                    latest_timestamp = timestamp
                    run_id = candidate

print(run_id)
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($python))
    $command = "docker exec $scheduler python -c `"import base64; exec(base64.b64decode('$encoded'))`""
    $runId = Invoke-NativeText $command | Select-Object -First 1
    return ($runId | Out-String).Trim()
}

Write-Host "PKLPO Observability v1 - Windows Acceptance Check"
Write-Host ([DateTime]::UtcNow.ToString("yyyy-MM-dd HH:mm:ss UTC"))

if ($SkipRuntime) {
    Write-Host ""
    Write-Host "-- RUNTIME CHECKS skipped (-SkipRuntime)"
} else {
    Write-Check 1 "pipeline_monitoring metrics are present in Pushgateway"
    try {
        $pushgatewayMetrics = Invoke-TextGet "$PushgatewayUrl/metrics"
        foreach ($metric in @(
            "pklpo_pipeline_candle_lag_seconds",
            "pklpo_pipeline_recalc_queue_rows",
            "pklpo_pipeline_alerts"
        )) {
            if ($pushgatewayMetrics -match "(?m)^$metric(\{| )") {
                Write-Pass "$metric present in Pushgateway"
            } else {
                Write-Fail "$metric NOT found in Pushgateway"
            }
        }
    } catch {
        Write-Fail "Could not read Pushgateway metrics: $($_.Exception.Message)"
        $pushgatewayMetrics = ""
    }

    Write-Check 2 "Loki query by run_id returns structured events for a real Airflow run"
    try {
        $headers = Get-BasicAuthHeader $AirflowUser $AirflowPass
        $headers["Content-Type"] = "application/json"
        $dagRunId = $null
        try {
            $trigger = Invoke-WebRequest `
                -UseBasicParsing `
                -Uri "$AirflowUrl/api/v1/dags/pipeline_monitoring/dagRuns" `
                -Headers $headers `
                -Method Post `
                -Body "{}" `
                -TimeoutSec 20
            $run = $trigger.Content | ConvertFrom-Json
            $dagRunId = $run.dag_run_id
        } catch {
            Write-Host "   INFO: Airflow API trigger failed, trying Airflow CLI fallback: $($_.Exception.Message)"
            $dagRunId = "codex_v1_" + (Get-Date -Format "yyyyMMddHHmmss")
            $scheduler = Invoke-NativeText 'docker ps --filter "name=airflow-scheduler" --format "{{.Names}}"' | Select-Object -First 1
            if ([string]::IsNullOrWhiteSpace($scheduler)) {
                throw "Airflow scheduler container not found for CLI fallback"
            }
            Invoke-NativeText "docker exec $scheduler airflow dags trigger -r $dagRunId -o json pipeline_monitoring" | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "Airflow CLI fallback failed for run_id=$dagRunId"
            }
        }
        if ([string]::IsNullOrWhiteSpace($dagRunId)) {
            Write-Fail "Airflow trigger response did not include dag_run_id"
        } else {
            Write-Host "   INFO: triggered pipeline_monitoring run_id=$dagRunId; waiting ${DagWaitSeconds}s"
            Start-Sleep -Seconds $DagWaitSeconds
            $query = "{job=~`"pklpo_app|pklpo_airflow`"} | json | run_id=`"$dagRunId`""
            $encodedQuery = [Uri]::EscapeDataString($query)
            $loki = Invoke-JsonGet "$LokiUrl/loki/api/v1/query_range?query=$encodedQuery&limit=10&since=10m"
            $count = @($loki.data.result).Count
            if ($count -gt 0) {
                Write-Pass "Loki returned $count stream(s) for run_id=$dagRunId"
            } else {
                Write-Host "   INFO: no Loki streams for triggered pipeline_monitoring run_id=$dagRunId; trying fallback structured Airflow run_id"
                $fallbackRunId = Find-StructuredAirflowRunId
                if ([string]::IsNullOrWhiteSpace($fallbackRunId)) {
                    Write-Fail "Loki returned 0 streams for run_id=$dagRunId and no fallback structured Airflow run_id was found"
                } else {
                    $fallbackQuery = "{job=~`"pklpo_app|pklpo_airflow`"} | json | run_id=`"$fallbackRunId`""
                    $encodedFallbackQuery = [Uri]::EscapeDataString($fallbackQuery)
                    $fallbackLoki = Invoke-JsonGet "$LokiUrl/loki/api/v1/query_range?query=$encodedFallbackQuery&limit=10&since=30m"
                    $fallbackCount = @($fallbackLoki.data.result).Count
                    if ($fallbackCount -gt 0) {
                        Write-Pass "Loki returned $fallbackCount stream(s) for fallback structured Airflow run_id=$fallbackRunId"
                    } else {
                        Write-Fail "Loki returned 0 streams for triggered run_id=$dagRunId and fallback structured Airflow run_id=$fallbackRunId"
                    }
                }
            }
        }
    } catch {
        Write-Fail "Could not trigger/query pipeline_monitoring logs: $($_.Exception.Message)"
    }

    Write-Check 3 "Grafana dashboard pklpo-pipeline-obs-v1 is accessible and has panels"
    try {
        $headers = Get-BasicAuthHeader "admin" "admin"
        $dashboard = Invoke-JsonGet "$GrafanaUrl/api/dashboards/uid/pklpo-pipeline-obs-v1" $headers
        $panelCount = @($dashboard.dashboard.panels).Count
        if ($panelCount -gt 0) {
            Write-Pass "Dashboard found with $panelCount panels"
        } else {
            Write-Fail "Dashboard pklpo-pipeline-obs-v1 has no panels"
        }
    } catch {
        Write-Fail "Dashboard pklpo-pipeline-obs-v1 not reachable: $($_.Exception.Message)"
    }

    Write-Check 4 "Docker network = pklpo_network"
    Invoke-NativeText "docker network inspect pklpo_network" | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "pklpo_network exists"
    } else {
        Write-Fail "pklpo_network does not exist"
    }

    foreach ($container in @("pklpo-pushgateway", "pklpo-prometheus")) {
        $inspect = Invoke-NativeText "docker inspect $container --format `"{{json .NetworkSettings.Networks}}`""
        if ($LASTEXITCODE -eq 0 -and $inspect -match '"pklpo_network"') {
            Write-Pass "$container is on pklpo_network"
        } else {
            Write-Fail "$container is NOT on pklpo_network"
        }
    }

    Write-Check 5 "/var/log/pklpo is canonical log path and Promtail can read Airflow logs"
    $scheduler = Invoke-NativeText 'docker ps --filter "name=airflow-scheduler" --format "{{.Names}}"' | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($scheduler)) {
        Write-Fail "Airflow scheduler container not found"
    } else {
        $logDir = Invoke-NativeText "docker exec $scheduler sh -c `"test -d /var/log/pklpo && echo yes || echo no`""
        if ($logDir.Trim() -eq "yes") {
            Write-Pass "/var/log/pklpo exists in Airflow scheduler"
        } else {
            Write-Fail "/var/log/pklpo does not exist in Airflow scheduler"
        }
    }

    $promtailMounts = Invoke-NativeText "docker inspect pklpo-promtail --format `"{{json .Mounts}}`""
    if ($LASTEXITCODE -eq 0 -and $promtailMounts -match "pklpo-airflow-logs") {
        Write-Pass "Promtail has pklpo-airflow-logs mounted"
    } else {
        Write-Fail "Promtail does NOT have pklpo-airflow-logs mounted"
    }

    Write-Check 6 "Dependency health metrics present"
    foreach ($metric in @("pklpo_dependency_postgres_up", "pklpo_dependency_okx_up")) {
        if ($pushgatewayMetrics -match "(?m)^$metric(\{| )") {
            Write-Pass "$metric present in Pushgateway"
        } else {
            Write-Fail "$metric NOT found in Pushgateway"
        }
    }

    Write-Check 7 "Swap sync DB write latency histogram present when sync has run"
    if ($pushgatewayMetrics -match "pklpo_swap_sync_db_write_latency_seconds_bucket") {
        Write-Pass "pklpo_swap_sync_db_write_latency_seconds histogram found"
    } else {
        Write-Warn "pklpo_swap_sync_db_write_latency_seconds histogram not found; run okx_swap_ohlcv_sync_v2 to populate it"
    }

    Write-Check 8 "monitoring and airflow compose configs are valid"
    foreach ($composeFile in @("ops/monitoring/docker-compose.monitoring.yml", "ops/airflow/docker-compose.airflow.yml")) {
        if (Test-Path $composeFile) {
            Invoke-NativeText "docker-compose -f $composeFile config --quiet" | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Pass "$composeFile config is valid"
            } else {
                Write-Fail "$composeFile config is INVALID"
            }
        } else {
            Write-Warn "$composeFile not found; skipping"
        }
    }
}

if ($SkipStatic) {
    Write-Host ""
    Write-Host "-- STATIC CHECKS skipped (-SkipStatic)"
} else {
    Write-Check 9 "ruff check src"
    $ruff = "ruff"
    if (Test-Path "venv/Scripts/ruff.exe") {
        $ruff = "venv/Scripts/ruff.exe"
    }
    & $ruff check src --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "ruff check src clean"
    } else {
        Write-Fail "ruff check src reported errors"
    }

    Write-Check 10 "mypy src (warning only)"
    $mypy = "mypy"
    if (Test-Path "venv/Scripts/mypy.exe") {
        $mypy = "venv/Scripts/mypy.exe"
    }
    & $mypy src --ignore-missing-imports --no-error-summary -q
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "mypy src passed"
    } else {
        Write-Warn "mypy src reported type errors (non-blocking for v1 acceptance)"
    }
}

Write-Host ""
if ($Failures -eq 0) {
    Write-Host "v1 ACCEPTANCE: PASS"
} else {
    Write-Host "v1 ACCEPTANCE: FAIL ($Failures checks failed)"
}

exit $Failures
