#!/usr/bin/env bash
# LGTM observability acceptance gate.
#
# Stage 1 checks (mandatory):
#   - v1 acceptance is delegated, not duplicated.
#   - Tempo /ready responds.
#   - Grafana has the Tempo datasource provisioned.
#   - run_id, trace_id, and span_id are not promoted to Loki labels.
#
# Stage 3+ trace checks can be enabled with --require-trace once tracing emits
# at least one real trace.
#
# Stage 5 checks (mandatory after Mimir is introduced):
#   - Mimir datasource file exists with UID Mimir and correct URL.
#   - Mimir /ready responds (runtime).
#   - Grafana exposes datasource UID Mimir (runtime).
#   - A pklpo_ metric is queryable via Mimir query API (--require-mimir-metric).

set -euo pipefail

TEMPO_URL="${TEMPO_URL:-http://localhost:3200}"
MIMIR_URL="${MIMIR_URL:-http://localhost:9009}"
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"
SAMPLE_TRACE_ID="${SAMPLE_TRACE_ID:-}"

SKIP_V1=false
SKIP_RUNTIME=false
REQUIRE_TRACE=false
REQUIRE_MIMIR_METRIC=false

for arg in "$@"; do
    case "$arg" in
        --skip-v1) SKIP_V1=true ;;
        --skip-runtime) SKIP_RUNTIME=true ;;
        --require-trace) REQUIRE_TRACE=true ;;
        --require-mimir-metric) REQUIRE_MIMIR_METRIC=true ;;
        *)
            echo "Unknown argument: $arg" >&2
            exit 2
            ;;
    esac
done

failures=0

check() { echo ""; echo "-- CHECK $1: $2"; }
pass() { echo "   PASS: $*"; }
fail() { echo "   FAIL: $*"; (( failures++ )) || true; }
info() { echo "   INFO: $*"; }
skip() { echo "   SKIP: $*"; }

# ---------------------------------------------------------------------------
# Static checks (always run)
# ---------------------------------------------------------------------------

check 1 "v1 acceptance is delegated"
if $SKIP_V1; then
    skip "v1 delegated check skipped by --skip-v1"
elif [[ -f scripts/validate_v1_acceptance.sh ]]; then
    v1_args=()
    if $SKIP_RUNTIME; then
        v1_args+=(--skip-runtime)
    fi
    if bash scripts/validate_v1_acceptance.sh "${v1_args[@]}"; then
        pass "v1 acceptance passed"
    else
        fail "v1 acceptance failed"
    fi
else
    fail "scripts/validate_v1_acceptance.sh is missing"
fi

check 2 "Tempo datasource is provisioned statically"
if [[ -f ops/monitoring/grafana/provisioning/datasources/tempo.yml ]]; then
    if grep -q "uid: Tempo" ops/monitoring/grafana/provisioning/datasources/tempo.yml \
        && grep -q "url: http://tempo:3200" ops/monitoring/grafana/provisioning/datasources/tempo.yml; then
        pass "Tempo datasource UID and URL are stable"
    else
        fail "Tempo datasource does not expose UID Tempo and URL http://tempo:3200"
    fi
else
    fail "Tempo datasource file is missing"
fi

check 3 "High-cardinality fields are not Loki labels (Alloy config)"
# Alloy config: verify run_id, trace_id, span_id are in stage.structured_metadata, NOT stage.labels.
# Strategy: extract the stage.labels block and check it does not contain the forbidden keys.
if [[ -f ops/monitoring/alloy/config.alloy ]]; then
    if python3 - << 'PYCHECK'
import re, sys
content = open("ops/monitoring/alloy/config.alloy").read()
# Find all stage.labels blocks
blocks = re.findall(r'stage\.labels\s*\{([^}]*)\}', content, re.DOTALL)
forbidden_pattern = "run_id|trace_id|span_id"
forbidden = set(forbidden_pattern.split("|"))
found = []
for block in blocks:
    for key in forbidden:
        if re.search(r'\b' + key + r'\s*=', block):
            found.append(key)
if found:
    print("FOUND:", found, file=sys.stderr)
    sys.exit(0)  # exit 0 means "found" (awk convention: 0 = match)
sys.exit(1)   # exit 1 means "not found" = pass
PYCHECK
    then
        fail "run_id, trace_id, or span_id appears in stage.labels block in Alloy config"
    else
        pass "run_id, trace_id, and span_id are not configured as Loki labels in Alloy config"
    fi
else
    fail "Alloy config not found: ops/monitoring/alloy/config.alloy"
fi

check 7 "Mimir datasource is provisioned statically (Stage 5)"
if [[ -f ops/monitoring/grafana/provisioning/datasources/mimir.yml ]]; then
    if grep -q "uid: Mimir" ops/monitoring/grafana/provisioning/datasources/mimir.yml \
        && grep -q "url: http://mimir:9009/prometheus" ops/monitoring/grafana/provisioning/datasources/mimir.yml; then
        pass "Mimir datasource UID and URL are stable"
    else
        fail "Mimir datasource does not have UID Mimir and URL http://mimir:9009/prometheus"
    fi
else
    fail "Mimir datasource file is missing"
fi

check 8 "Prometheus remote_write to Mimir is configured"
if grep -q "remote_write" ops/monitoring/prometheus/prometheus.yml \
    && grep -q "mimir:9009" ops/monitoring/prometheus/prometheus.yml; then
    pass "prometheus.yml has remote_write pointing to Mimir"
else
    fail "prometheus.yml is missing remote_write block for Mimir"
fi

# ---------------------------------------------------------------------------
# Runtime checks
# ---------------------------------------------------------------------------

if $SKIP_RUNTIME; then
    check 4 "runtime checks"
    skip "runtime checks skipped by --skip-runtime"
else
    check 4 "Tempo /ready responds"
    if curl -fsS "$TEMPO_URL/ready" >/dev/null; then
        pass "Tempo ready endpoint responds at $TEMPO_URL/ready"
    else
        fail "Tempo ready endpoint is not reachable at $TEMPO_URL/ready"
    fi

    check 5 "Grafana exposes Tempo datasource"
    datasource_resp=$(curl -fsS -u "$GRAFANA_USER:$GRAFANA_PASS" \
        "$GRAFANA_URL/api/datasources/uid/Tempo" 2>/dev/null || true)
    if echo "$datasource_resp" | grep -q '"uid":"Tempo"'; then
        pass "Grafana API returns datasource UID Tempo"
    else
        fail "Grafana API did not return datasource UID Tempo"
    fi

    check 6 "sample trace is queryable when required"
    if $REQUIRE_TRACE; then
        if [[ -z "$SAMPLE_TRACE_ID" ]]; then
            fail "SAMPLE_TRACE_ID is required with --require-trace"
        elif curl -fsS "${TEMPO_URL}/api/traces/${SAMPLE_TRACE_ID}" >/dev/null; then
            pass "Sample trace is queryable: $SAMPLE_TRACE_ID"
        else
            fail "Sample trace is not queryable: $SAMPLE_TRACE_ID"
        fi
    else
        skip "sample trace check disabled; pass --require-trace to enable"
    fi

    check 9 "Mimir /ready responds"
    if curl -fsS "$MIMIR_URL/ready" >/dev/null; then
        pass "Mimir ready endpoint responds at $MIMIR_URL/ready"
    else
        fail "Mimir ready endpoint is not reachable at $MIMIR_URL/ready"
    fi

    check 10 "Grafana exposes Mimir datasource"
    mimir_ds_resp=$(curl -fsS -u "$GRAFANA_USER:$GRAFANA_PASS" \
        "$GRAFANA_URL/api/datasources/uid/Mimir" 2>/dev/null || true)
    if echo "$mimir_ds_resp" | grep -q '"uid":"Mimir"'; then
        pass "Grafana API returns datasource UID Mimir"
    else
        fail "Grafana API did not return datasource UID Mimir"
    fi

    check 11 "pklpo_ metric queryable via Mimir"
    if $REQUIRE_MIMIR_METRIC; then
        mimir_query_resp=$(curl -fsS \
            "$MIMIR_URL/prometheus/api/v1/query?query=up" 2>/dev/null || true)
        if echo "$mimir_query_resp" | grep -q '"status":"success"'; then
            pass "Mimir query API returns success for up{}"
        else
            fail "Mimir query API did not return success; check remote_write lag"
        fi
    else
        skip "pklpo_ metric check disabled; pass --require-mimir-metric to enable"
    fi
fi

echo ""
if [[ "$failures" -eq 0 ]]; then
    echo "LGTM ACCEPTANCE: PASS"
else
    echo "LGTM ACCEPTANCE: FAIL ($failures checks failed)"
fi

exit "$failures"
