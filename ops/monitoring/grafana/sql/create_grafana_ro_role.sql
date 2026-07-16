\set ON_ERROR_STOP on

\if :{?grafana_ro_password}
\else
  \echo 'Required psql variable missing: grafana_ro_password'
  \echo 'Usage: psql -U <admin> -d pklpo -v grafana_ro_password=<password> -f ops/monitoring/grafana/sql/create_grafana_ro_role.sql'
  \quit 1
\endif

SELECT format('CREATE ROLE grafana_ro LOGIN PASSWORD %L', :'grafana_ro_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro')
\gexec

SELECT format('ALTER ROLE grafana_ro LOGIN PASSWORD %L', :'grafana_ro_password')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'grafana_ro')
\gexec

GRANT CONNECT ON DATABASE pklpo TO grafana_ro;
GRANT USAGE ON SCHEMA public TO grafana_ro;
GRANT USAGE ON SCHEMA ops TO grafana_ro;

-- Operational exception only (§12.3, consumer_writer_cutover_matrix_2026-07-02.md
-- "Raw writers and operational direct-read allowlist"): kept for the raw
-- candle-coverage dashboard (pklpo-candle-coverage.json), which intentionally
-- stays on public.swap_ohlcv_p as an operational ingest-health panel, not an
-- analytical one. Do not add new analytical dashboards against this grant —
-- point them at core.v_ohlcv_facade below instead (Task 5.5, §12.12 п.12-13).
GRANT SELECT ON TABLE public.swap_ohlcv_p TO grafana_ro;

GRANT SELECT ON TABLE ops.pipeline_recovery_decisions TO grafana_ro;

-- Analytical BI access (Task 5.5): identity-aware facade view (Task 4.3),
-- PIT-adjusted, gap-aware, keyed by series_id/segment_id. New analytical
-- Grafana dashboards must read this, not public.swap_ohlcv_p.
GRANT USAGE ON SCHEMA core TO grafana_ro;
GRANT SELECT ON TABLE core.v_ohlcv_facade TO grafana_ro;
