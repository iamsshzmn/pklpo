#!/usr/bin/env bash
# R3 Acceptance Proof — end-to-end delivery path validation
#
# Checks all 5 R3 acceptance criteria:
#   1. Airflow task writes JSON log to volume that Alloy reads
#   2. Loki query by run_id returns events for a concrete Airflow run
#   3. OBSERVABILITY_PROMETHEUS_ENABLED=true is visible inside Airflow runtime
#   4. Pushgateway received pklpo_pipeline_candle_lag_seconds + a swap/feature metric
#   5. Prometheus scrapes pushgateway; Docker network = pklpo_network
#
# Usage:
#   bash scripts/validate_r3_acceptance.sh [--loki-url URL] [--prometheus-url URL]
#                                          [--pushgateway-url URL] [--airflow-url URL]
#   All URLs default to localhost ports exposed by docker-compose.
#
# Output:
#   Pass/fail per criterion.  Exit code = number of failed checks (0 = all pass).
#
# Prereqs:
#   docker, curl, jq  — must be on PATH.
#   Monitoring stack must be running: docker compose -f ops/monitoring/docker-compose.monitoring.yml up -d
#   Airflow stack must be running:    docker compose -f ops/airflow/docker-compose.airflow.yml up -d
# ---------------------------------------------------------------------------
set -euo pipefail

LOKI_URL="${LOKI_URL:-http://localhost:3100}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
PUSHGATEWAY_URL="${PUSHGATEWAY_URL:-http://localhost:9091}"
AIRFLOW_URL="${AIRFLOW_URL:-http://localhost:8080}"
AIRFLOW_USER="${AIRFLOW_USER:-admin}"
AIRFLOW_PASS="${AIRFLOW_PASS:-admin}"

PASS="✅"
FAIL="❌"
SKIP="⏭ "

failures=0

_check() {
    local id="$1" desc="$2"
    shift 2
    echo ""
    echo "── CHECK $id: $desc"
}

_pass() { echo "   $PASS PASS: $*"; }
_fail() { echo "   $FAIL FAIL: $*"; (( failures++ )) || true; }
_info() { echo "   ℹ  $*"; }

# ---------------------------------------------------------------------------
# CHECK 1 — Airflow JSON logs in shared volume, readable by Alloy
# ---------------------------------------------------------------------------
_check 1 "Airflow task writes JSON log to shared volume (Alloy-readable)"

AIRFLOW_LOG_VOLUME="pklpo-airflow-logs"
ALLOY_CONTAINER="pklpo-alloy"

# 1a. Volume exists
if docker volume inspect "$AIRFLOW_LOG_VOLUME" &>/dev/null; then
    _pass "Docker volume '$AIRFLOW_LOG_VOLUME' exists"
else
    _fail "Docker volume '$AIRFLOW_LOG_VOLUME' not found. Create it by starting the Airflow stack."
fi

# 1b. Alloy container is running and has the volume mounted
ALLOY_MOUNTS=$(docker inspect "$ALLOY_CONTAINER" --format '{{json .Mounts}}' 2>/dev/null || echo "[]")
if echo "$ALLOY_MOUNTS" | jq -e '.[] | select(.Name == "'"$AIRFLOW_LOG_VOLUME"'")' &>/dev/null; then
    _pass "Alloy container has '$AIRFLOW_LOG_VOLUME' mounted"
else
    _fail "Alloy container '$ALLOY_CONTAINER' does not have '$AIRFLOW_LOG_VOLUME' mounted"
fi

# 1c. Check that log files exist in the volume (requires at least one DAG run)
AIRFLOW_CONTAINER=$(docker ps --filter "name=pklpo-airflow-scheduler" --format '{{.Names}}' | head -1)
if [[ -n "$AIRFLOW_CONTAINER" ]]; then
    LOG_COUNT=$(docker exec "$AIRFLOW_CONTAINER" sh -c 'ls /var/log/pklpo/*.log 2>/dev/null | wc -l' 2>/dev/null || echo "0")
    if [[ "$LOG_COUNT" -gt 0 ]]; then
        _pass "Found $LOG_COUNT log file(s) in /var/log/pklpo/ inside Airflow container"
        # 1d. Verify JSON format
        FIRST_LINE=$(docker exec "$AIRFLOW_CONTAINER" sh -c 'head -1 $(ls /var/log/pklpo/*.log | head -1) 2>/dev/null' 2>/dev/null || echo "")
        if echo "$FIRST_LINE" | jq . &>/dev/null 2>&1; then
            _pass "Log file is JSON-formatted"
        else
            _fail "Log file does not appear to be JSON. First line: ${FIRST_LINE:0:120}"
        fi
    else
        _fail "No log files in /var/log/pklpo/ — trigger a DAG run first (e.g. pipeline_monitoring)"
    fi
else
    _fail "Airflow scheduler container not found"
fi

# ---------------------------------------------------------------------------
# CHECK 2 — Loki query by run_id returns events
# ---------------------------------------------------------------------------
_check 2 "Loki query by run_id returns structured events for an Airflow run"

# Trigger pipeline_monitoring DAG run and capture run_id
_info "Triggering pipeline_monitoring DAG run to generate a known run_id..."
TRIGGER_RESP=$(curl -s -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
    -X POST "$AIRFLOW_URL/api/v1/dags/pipeline_monitoring/dagRuns" \
    -H "Content-Type: application/json" \
    -d '{}' 2>/dev/null || echo "{}")

DAG_RUN_ID=$(echo "$TRIGGER_RESP" | jq -r '.dag_run_id // empty' 2>/dev/null || echo "")

if [[ -z "$DAG_RUN_ID" ]]; then
    _fail "Could not trigger pipeline_monitoring run. Response: ${TRIGGER_RESP:0:200}"
    _info "MANUAL: trigger pipeline_monitoring manually, then run Loki query:"
    _info "  {job=~\"pklpo_app|pklpo_airflow\"} | json | run_id=\"<YOUR_RUN_ID>\""
else
    _info "Triggered run: $DAG_RUN_ID. Waiting 90s for task to complete..."
    sleep 90

    # URL-encode the LogQL query
    LOGQL='{job=~"pklpo_app|pklpo_airflow"} | json | run_id=`'"$DAG_RUN_ID"'`'
    ENCODED_QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$LOGQL'''))" 2>/dev/null \
        || echo "")

    if [[ -n "$ENCODED_QUERY" ]]; then
        LOKI_RESP=$(curl -s \
            "$LOKI_URL/loki/api/v1/query_range?query=${ENCODED_QUERY}&limit=10&since=5m" \
            2>/dev/null || echo "{}")
        RESULT_COUNT=$(echo "$LOKI_RESP" | jq '.data.result | length' 2>/dev/null || echo "0")
        if [[ "$RESULT_COUNT" -gt 0 ]]; then
            _pass "Loki returned $RESULT_COUNT stream(s) for run_id='$DAG_RUN_ID'"
        else
            _fail "Loki returned 0 results for run_id='$DAG_RUN_ID'"
            _info "Query: $LOGQL"
            _info "Loki response: ${LOKI_RESP:0:300}"
        fi
    else
        _fail "python3 not available for URL encoding; skipping Loki query"
    fi
fi

# ---------------------------------------------------------------------------
# CHECK 3 — OBSERVABILITY_PROMETHEUS_ENABLED=true visible in Airflow runtime
# ---------------------------------------------------------------------------
_check 3 "OBSERVABILITY_PROMETHEUS_ENABLED=true visible inside Airflow runtime"

AIRFLOW_SCHED=$(docker ps --filter "name=pklpo-airflow-scheduler" --format '{{.Names}}' | head -1)
if [[ -n "$AIRFLOW_SCHED" ]]; then
    ENV_VAL=$(docker exec "$AIRFLOW_SCHED" \
        sh -c 'echo $OBSERVABILITY_PROMETHEUS_ENABLED' 2>/dev/null | tr -d '[:space:]' || echo "")
    case "${ENV_VAL,,}" in
        1|true|yes)
            _pass "OBSERVABILITY_PROMETHEUS_ENABLED='$ENV_VAL' (enabled)"
            ;;
        "")
            _fail "OBSERVABILITY_PROMETHEUS_ENABLED is empty/unset inside Airflow scheduler"
            ;;
        *)
            _fail "OBSERVABILITY_PROMETHEUS_ENABLED='$ENV_VAL' — expected true/1"
            ;;
    esac

    PGW_VAL=$(docker exec "$AIRFLOW_SCHED" \
        sh -c 'echo $OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL' 2>/dev/null | tr -d '[:space:]' || echo "")
    if [[ -n "$PGW_VAL" ]]; then
        _pass "OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL='$PGW_VAL'"
    else
        _fail "OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL is unset inside Airflow scheduler"
    fi
else
    _fail "Airflow scheduler container not found"
fi

# ---------------------------------------------------------------------------
# CHECK 4 — Pushgateway received pklpo_pipeline_candle_lag_seconds + swap/feature metric
# ---------------------------------------------------------------------------
_check 4 "Pushgateway received pklpo_pipeline_candle_lag_seconds + swap/feature metric"

PGW_METRICS=$(curl -s "$PUSHGATEWAY_URL/metrics" 2>/dev/null || echo "")

if echo "$PGW_METRICS" | grep -q "pklpo_pipeline_candle_lag_seconds"; then
    _pass "pklpo_pipeline_candle_lag_seconds found in Pushgateway"
else
    _fail "pklpo_pipeline_candle_lag_seconds NOT found in Pushgateway. Run pipeline_monitoring DAG first."
fi

if echo "$PGW_METRICS" | grep -qE "pklpo_swap_sync_|pklpo_features_"; then
    FOUND=$(echo "$PGW_METRICS" | grep -oE "pklpo_(swap_sync|features)_[a-z_]+" | head -1)
    _pass "Swap/feature metric found: $FOUND"
else
    _fail "No swap/feature metric (pklpo_swap_sync_* or pklpo_features_*) in Pushgateway. Run okx_swap_ohlcv_sync_v2 or features_calc_short."
fi

# ---------------------------------------------------------------------------
# CHECK 5 — Prometheus scrapes pushgateway; network = pklpo_network
# ---------------------------------------------------------------------------
_check 5 "Prometheus scrapes pushgateway; network = pklpo_network"

# 5a. pklpo_network exists
if docker network inspect pklpo_network &>/dev/null; then
    _pass "Docker network 'pklpo_network' exists"
else
    _fail "Docker network 'pklpo_network' not found. Create it: docker network create pklpo_network"
fi

# 5b. pushgateway container is on pklpo_network
PGW_CONTAINER="pklpo-pushgateway"
PGW_NETWORKS=$(docker inspect "$PGW_CONTAINER" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null || echo "{}")
if echo "$PGW_NETWORKS" | jq -e '.pklpo_network' &>/dev/null; then
    _pass "Pushgateway container is on 'pklpo_network'"
else
    _fail "Pushgateway container '$PGW_CONTAINER' is NOT on 'pklpo_network'"
fi

# 5c. Prometheus has a scrape target for pushgateway and it's UP
PROM_TARGETS=$(curl -s "$PROMETHEUS_URL/api/v1/targets" 2>/dev/null || echo "{}")
PGW_UP=$(echo "$PROM_TARGETS" | jq -r \
    '[.data.activeTargets[] | select(.labels.job == "pushgateway") | .health] | first // "unknown"' \
    2>/dev/null || echo "unknown")
if [[ "$PGW_UP" == "up" ]]; then
    _pass "Prometheus pushgateway scrape target health = up"
elif [[ "$PGW_UP" == "unknown" ]]; then
    _fail "No pushgateway scrape target in Prometheus. Check prometheus.yml."
else
    _fail "Prometheus pushgateway scrape target health = '$PGW_UP'"
fi

# 5d. pklpo_pipeline_candle_lag_seconds is queryable in Prometheus
PROM_QUERY=$(curl -s \
    "$PROMETHEUS_URL/api/v1/query?query=pklpo_pipeline_candle_lag_seconds" \
    2>/dev/null || echo "{}")
PROM_RESULT_COUNT=$(echo "$PROM_QUERY" | jq '.data.result | length' 2>/dev/null || echo "0")
if [[ "$PROM_RESULT_COUNT" -gt 0 ]]; then
    _pass "pklpo_pipeline_candle_lag_seconds queryable in Prometheus ($PROM_RESULT_COUNT series)"
else
    _fail "pklpo_pipeline_candle_lag_seconds not yet in Prometheus. Scrape interval is 15s — wait and retry after pipeline_monitoring runs."
fi

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
echo ""
echo "══════════════════════════════════════════════════════"
if [[ "$failures" -eq 0 ]]; then
    echo "R3 ACCEPTANCE PROOF: $PASS ALL CHECKS PASSED"
else
    echo "R3 ACCEPTANCE PROOF: $FAIL $failures CHECK(S) FAILED — do not proceed to Stage 2 dashboard"
fi
echo "══════════════════════════════════════════════════════"
echo ""

exit "$failures"
