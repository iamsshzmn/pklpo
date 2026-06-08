# Airflow Ops Notes

## Required Pools

Create these pools before enabling the research-platform DAGs:

```bash
airflow pools set ohlcv_write_pool 1 "Serialize swap_ohlcv_p writers"
airflow pools set okx_api_pool 2 "Throttle OKX API calls"
airflow pools set compute_pool 2 "Throttle feature compute tasks"
```

Current `swap_sync`, `bootstrap_symbol_tf`, and `swap_repair` tasks combine OKX
fetching with `swap_ohlcv_p` writes, so they use `ohlcv_write_pool`. This favors
write serialization until those DAGs split API fetch and database write into
separate operators. API-only metadata refresh uses `okx_api_pool`; feature and
recalc tasks use `compute_pool`.
