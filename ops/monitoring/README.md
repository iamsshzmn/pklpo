# PKLPO Monitoring Stack

Prometheus + Pushgateway + Grafana for data quality monitoring.

## Quick Start

```bash
# Ensure pklpo_network exists
docker network create pklpo_pklpo_network 2>/dev/null || true

# Start monitoring stack
cd ops/monitoring
docker compose -f docker-compose.monitoring.yml up -d
```

## Access

| Service     | URL                      | Default Credentials |
|-------------|--------------------------|---------------------|
| Grafana     | http://localhost:3001     | admin / admin       |
| Prometheus  | http://localhost:9090     | -                   |
| Pushgateway | http://localhost:9091     | -                   |

## Enable Metrics in Pipeline

Set environment variables before running the pipeline:

```bash
export OBSERVABILITY_PROMETHEUS_ENABLED=true
export OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL=http://localhost:9091
```

Or in `.env`:
```
OBSERVABILITY_PROMETHEUS_ENABLED=true
OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL=http://localhost:9091
```

For Docker (Airflow), use the internal hostname:
```
OBSERVABILITY_PROMETHEUS_PUSHGATEWAY_URL=http://pushgateway:9091
```

## Dashboard

The **PKLPO Data Quality** dashboard is auto-provisioned and includes:

1. Freshness Lag by timeframe (with SLA threshold lines)
2. Fill Rate (target: 99.5%)
3. Hole Rate / missing bars (target: <0.1%)
4. Duplicate detection rate
5. UPSERT duration percentiles (p50/p95/p99)
6. Batch size distribution
7. Data quality score gauge
8. Calculation duration + UPSERT throughput/failures

## Alerts

Provisioned alert rules:

| Alert                  | Condition             | Severity |
|------------------------|-----------------------|----------|
| Freshness Lag Warning  | lag > 900s for 5m     | warning  |
| Freshness Lag Critical | lag > 2700s for 5m    | critical |
| Fill Rate Low          | < 99.5% for 10m       | warning  |
| Fill Rate Critical     | < 95% for 10m         | critical |
| Hole Rate High         | > 0.1% for 10m        | warning  |
| Duplicates Detected    | rate > 0 for 5m       | warning  |
| UPSERT Failures        | rate > 0 for 5m       | critical |

Configure notification channels in Grafana UI (Alerting > Contact points).

## Data Retention

Prometheus retains 30 days of metrics (`--storage.tsdb.retention.time=30d`).

## Volumes

- `pklpo-prometheus-data` — Prometheus TSDB
- `pklpo-grafana-data` — Grafana state (users, annotations)
