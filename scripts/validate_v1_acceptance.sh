#!/usr/bin/env bash
# v1 Observability Acceptance Check — full Stage 0-4 validation
#
# Checks all 5 Stage-5 acceptance criteria PLUS static and Stage 3 additions:
#
#   Runtime checks (require live stack):
#     1. pipeline_monitoring run publishes candle_lag_seconds, recalc_queue_rows, pipeline_alerts
#     2. Loki query by run_id returns structured events for a real Airflow run
#     3. Grafana dashboard pklpo-pipeline-obs-v1 is accessible and has panels
#     4. Docker network = pklpo_network (not pklpo_pklpo_network)
#     5. /var/log/pklpo is canonical log path; readable by Promtail
#
#   Stage 3 additions (require live stack):
#     6. Dependency health metrics present in Pushgateway
#     7. DB write latency histogram series present in Pushgateway
#     8. compose config validity (docker compose config)
#
#   Static checks (no live stack required):
#     9.  ruff check passes on src/
#     10. mypy passes on src/ (optional — warns, does not fail)
#
# Usage:
#   bash scripts/validate_v1_acceptance.sh [--skip-runtime] [--skip-static]
#   --skip-runtime   Run only static checks (useful in CI without Docker)
#   --skip-static    Run only runtime checks
#
# Environment variables (all have localhost defaults):
#   LOKI_URL, PROMETHEUS_URL, PUSHGATEWAY_URL, AIRFLOW_URL,
#   GRAFANA_URL, AIRFLOW_USER, AIRFLOW_PASS
#
# Exit code = number of failed checks (0 = all pass → close Stage 5).
# ---------------------------------------------------------------------------
set -euo pipefail

LOKI_URL="${LOKI_URL:-http://localhost:3100}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
PUSHGATEWAY_URL="${PUSHGATEWAY_URL:-http://localhost:9091}"
AIRFLOW_URL="${AIRFLOW_URL:-http://localhost:8080}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
AIRFLOW_USER="${AIRFLOW_USER:-admin}"
AIRFLOW_PASS="${AIRFLOW_PASS:-admin}"

SKIP_RUNTIME=false
SKIP_STATIC=false

for arg in "$@"; do
    case "$arg" in
        --skip-runtime) SKIP_RUNTIME=true ;;
        --skip-static)  SKIP_STATIC=true  ;;
    esac
done

PASS="✅"
FAIL="❌"
SKIP_ICON="⏭ "
WARN="⚠️ "

failures=0

_check() { echo ""; echo "── CHECK $1: $2"; }
_pass()  { echo "   $PASS PASS: $*"; }
_fail()  { echo "   $FAIL FAIL: $*"; (( failures++ )) || true; }
_warn()  { echo "   $WARN WARN: $*"; }
_info()  { echo "   ℹ  $*"; }
_skip()  { echo "   $SKIP_ICON SKIP: $*"; }

echo "══════════════════════════════════════════════════════"
echo "  PKLPO Observability v1 — Final Acceptance Check"
echo "  $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "══════════════════════════════════════════════════════"

# ===========================================================================
# RUNTIME CHECKS
# ===========================================================================

if $SKIP_RUNTIME; then
    echo ""
    echo "── RUNTIME CHECKS skipped (--skip-runtime)"
else

# ---------------------------------------------------------------------------
# CHECK 1 — pipeline_monitoring publishes candle_lag_seconds, recalc_queue_rows, pipeline_alerts
# ---------------------------------------------------------------------------
_check 1 "pipeline_monitoring publishes candle_lag_seconds + recalc_queue_rows + pipeline_alerts"

PGW_METRICS=$(curl -s "$PUSHGATEWAY_URL/metrics" 2>/dev/null || echo "")

for metric in pklpo_pipeline_candle_lag_seconds pklpo_pipeline_recalc_queue_rows pklpo_pipeline_alerts; do
    if echo "$PGW_METRICS" | grep -q "^${metric}"; then
        _pass "$metric present in Pushgateway"
    else
        _fail "$metric NOT found in Pushgateway — run pipeline_monitoring DAG"
    fi
done

# ---------------------------------------------------------------------------
# CHECK 2 — Loki query by run_id returns structured events
# ---------------------------------------------------------------------------
_check 2 "Loki query by run_id returns structured events for a real Airflow run"

_info "Triggering pipeline_monitoring DAG run..."
TRIGGER_RESP=$(curl -s -u "$AIRFLOW_USER:$AIRFLOW_PASS" \
    -X POST "$AIRFLOW_URL/api/v1/dags/pipeline_monitoring/dagRuns" \
    -H "Content-Type: application/json" \
    -d '{}' 2>/dev/null || echo "{}")
DAG_RUN_ID=$(echo "$TRIGGER_RESP" | jq -r '.dag_run_id // empty' 2>/dev/null || echo "")

if [[ -z "$DAG_RUN_ID" ]]; then
    _fail "Could not trigger pipeline_monitoring. Response: ${TRIGGER_RESP:0:200}"
    _info "MANUAL: trigger pipeline_monitoring, then run:"
    _info "  curl '$LOKI_URL/loki/api/v1/query_range?query=\{job%3D~\"pklpo_app|pklpo_airflow\"\}+|+json+|+run_id%3D\"<RUN_ID>\"&limit=10&since=5m'"
else
    _info "Triggered: $DAG_RUN_ID. Waiting 90s..."
    sleep 90
    ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('{job=~\"pklpo_app|pklpo_airflow\"} | json | run_id=\"'"$DAG_RUN_ID"'\"'))" 2>/dev/null || echo "")
    if [[ -n "$ENCODED" ]]; then
        LOKI_RESP=$(curl -s "$LOKI_URL/loki/api/v1/query_range?query=${ENCODED}&limit=10&since=5m" 2>/dev/null || echo "{}")
        RESULT_COUNT=$(echo "$LOKI_RESP" | jq '.data.result | length' 2>/dev/null || echo "0")
        if [[ "$RESULT_COUNT" -gt 0 ]]; then
            _pass "Loki returned $RESULT_COUNT stream(s) for run_id='$DAG_RUN_ID'"
        else
            _fail "Loki returned 0 results for run_id='$DAG_RUN_ID'"
        fi
    else
        _fail "python3 unavailable; cannot URL-encode Loki query"
    fi
fi

# ---------------------------------------------------------------------------
# CHECK 3 — Grafana dashboard pklpo-pipeline-obs-v1 accessible with panels
# ---------------------------------------------------------------------------
_check 3 "Grafana dashboard pklpo-pipeline-obs-v1 is accessible and has panels"

DASH_RESP=$(curl -s "${GRAFANA_URL}/api/dashboards/uid/pklpo-pipeline-obs-v1" 2>/dev/null || echo "{}")
PANEL_COUNT=$(echo "$DASH_RESP" | jq '.dashboard.panels | length' 2>/dev/null || echo "0")

if [[ "$PANEL_COUNT" -gt 0 ]]; then
    _pass "Dashboard found with $PANEL_COUNT panels"
else
    _fail "Dashboard pklpo-pipeline-obs-v1 not found or has 0 panels (Grafana may not have provisioned it)"
    _info "Restart Grafana: docker compose restart grafana"
fi

# ---------------------------------------------------------------------------
# CHECK 4 — Docker network = pklpo_network
# ---------------------------------------------------------------------------
_check 4 "Docker network = pklpo_network (not pklpo_pklpo_network)"

if docker network inspect pklpo_network &>/dev/null; then
    _pass "pklpo_network exists"
else
    _fail "pklpo_network does not exist"
fi

# Confirm pushgateway and prometheus are on it
for container in pklpo-pushgateway pklpo-prometheus; do
    NETS=$(docker inspect "$container" --format '{{json .NetworkSettings.Networks}}' 2>/dev/null || echo "{}")
    if echo "$NETS" | jq -e '.pklpo_network' &>/dev/null; then
        _pass "$container is on pklpo_network"
    else
        _fail "$container is NOT on pklpo_network"
    fi
done

# Guard against wrong network name
if docker network inspect pklpo_pklpo_network &>/dev/null 2>&1; then
    _warn "pklpo_pklpo_network also exists — check for double-prefixed compose network"
fi

# ---------------------------------------------------------------------------
# CHECK 5 — /var/log/pklpo is canonical log path; Promtail reads it
# ---------------------------------------------------------------------------
_check 5 "/var/log/pklpo is canonical log path and is readable by Promtail"

AIRFLOW_SCHED=$(docker ps --filter "name=pklpo-airflow-scheduler" --format '{{.Names}}' | head -1)
if [[ -n "$AIRFLOW_SCHED" ]]; then
    LOG_DIR_EXISTS=$(docker exec "$AIRFLOW_SCHED" sh -c 'test -d /var/log/pklpo && echo yes || echo no' 2>/dev/null || echo no)
    if [[ "$LOG_DIR_EXISTS" == "yes" ]]; then
        _pass "/var/log/pklpo directory exists in Airflow scheduler container"
    else
        _fail "/var/log/pklpo does not exist in Airflow scheduler container"
    fi
else
    _fail "Airflow scheduler container not found"
fi

PROMTAIL_MOUNTS=$(docker inspect "pklpo-promtail" --format '{{json .Mounts}}' 2>/dev/null || echo "[]")
if echo "$PROMTAIL_MOUNTS" | jq -e '.[] | select(.Name == "pklpo-airflow-logs")' &>/dev/null; then
    _pass "Promtail has pklpo-airflow-logs volume mounted"
else
    _fail "Promtail does NOT have pklpo-airflow-logs mounted"
fi

# ---------------------------------------------------------------------------
# CHECK 6 — Dependency health metrics in Pushgateway (Stage 3, R5)
# ---------------------------------------------------------------------------
_check 6 "Dependency health metrics present (postgres_up / okx_up)"

for metric in pklpo_dependency_postgres_up pklpo_dependency_okx_up; do
    if echo "$PGW_METRICS" | grep -q "^${metric}"; then
        VAL=$(echo "$PGW_METRICS" | grep "^${metric} " | awk '{print $2}' | head -1)
        _pass "$metric = $VAL"
    else
        _fail "$metric NOT found in Pushgateway — run pipeline_monitoring DAG"
    fi
done

# ---------------------------------------------------------------------------
# CHECK 7 — DB write latency histogram series (Stage 3, R7)
# ---------------------------------------------------------------------------
_check 7 "Swap sync DB write latency histogram present in Pushgateway"

if echo "$PGW_METRICS" | grep -q "pklpo_swap_sync_db_write_latency_seconds_bucket"; then
    _pass "pklpo_swap_sync_db_write_latency_seconds histogram found in Pushgateway"
else
    _warn "pklpo_swap_sync_db_write_latency_seconds histogram NOT found — run okx_swap_ohlcv_sync_v2 first"
    _info "(Non-blocking: histogram is populated on first sync run)"
fi

# ---------------------------------------------------------------------------
# CHECK 8 — compose config validity
# ---------------------------------------------------------------------------
_check 8 "docker-compose config validation (monitoring + airflow stacks)"

MONITORING_COMPOSE="ops/monitoring/docker-compose.monitoring.yml"
AIRFLOW_COMPOSE="ops/airflow/docker-compose.airflow.yml"

for compose_file in "$MONITORING_COMPOSE" "$AIRFLOW_COMPOSE"; do
    if [[ -f "$compose_file" ]]; then
        if docker compose -f "$compose_file" config --quiet 2>/dev/null; then
            _pass "$compose_file config is valid"
        else
            _fail "$compose_file config is INVALID"
        fi
    else
        _warn "$compose_file not found (skipping compose config check)"
    fi
done

fi  # end SKIP_RUNTIME

# ===========================================================================
# STATIC CHECKS
# ===========================================================================

if $SKIP_STATIC; then
    echo ""
    echo "── STATIC CHECKS skipped (--skip-static)"
else

# ---------------------------------------------------------------------------
# CHECK 9 — ruff check src/
# ---------------------------------------------------------------------------
_check 9 "ruff check src/ (linting + format)"

if command -v ruff &>/dev/null; then
    if ruff check src/ --quiet 2>&1; then
        _pass "ruff check src/ clean"
    else
        _fail "ruff check src/ reported errors"
    fi
    if ruff format src/ --check --quiet 2>&1; then
        _pass "ruff format src/ — no unformatted files"
    else
        _fail "ruff format src/ — unformatted files found (run: ruff format src/)"
    fi
else
    _warn "ruff not found on PATH — skipping (run in venv: pip install ruff)"
fi

# ---------------------------------------------------------------------------
# CHECK 10 — mypy src/ (warn only)
# ---------------------------------------------------------------------------
_check 10 "mypy src/ (type checking — WARN only, does not fail acceptance)"

if command -v mypy &>/dev/null; then
    if mypy src/ --ignore-missing-imports --no-error-summary -q 2>&1 | tail -3; then
        _pass "mypy src/ passed"
    else
        _warn "mypy src/ reported type errors (non-blocking for v1 acceptance)"
    fi
else
    _warn "mypy not found on PATH — skipping"
fi

fi  # end SKIP_STATIC

# ===========================================================================
# SUMMARY
# ===========================================================================
echo ""
echo "══════════════════════════════════════════════════════"
if [[ "$failures" -eq 0 ]]; then
    echo "  $PASS v1 ACCEPTANCE: ALL CHECKS PASSED"
    echo "  → Close Stage 5. Observability v1 track complete."
    echo "  → Next: Phase B (scoring → recommender → signals)"
    echo "          v2 ADR: docs/adr/ADR-2026-06-08-OB4-tracing-v2-handoff.md"
else
    echo "  $FAIL v1 ACCEPTANCE: $failures CHECK(S) FAILED"
    echo "  → Fix failing checks before closing Stage 5."
    echo "  → See individual FAIL lines above."
fi
echo "══════════════════════════════════════════════════════"
echo ""

exit "$failures"
