# Logs Runbook — Grafana / Loki

> Область: `OB2`. Только log aggregation. Prometheus metrics — отдельный тред.

## Стек

```
pklpo app / Airflow tasks
    ↓  JSON lines → /var/log/pklpo/*.log
Alloy (grafana/alloy:v1.8.3, scrapes files, read-only)
    ↓  push
Loki (http://loki:3100)
    ↓  datasource
Grafana (http://localhost:3001) → Explore → Loki
```

> **Примечание:** Promtail заменён Alloy (Promtail EOL март 2026).
> Конфиг: `ops/monitoring/alloy/config.alloy`. Контейнер: `pklpo-alloy`.

## Запуск

```bash
docker compose -f ops/monitoring/docker-compose.monitoring.yml up -d loki alloy grafana
```

Grafana открывается на http://localhost:3001 (admin / admin).  
Loki datasource провижинится автоматически из `grafana/provisioning/datasources/loki.yml`.

## Local tools

- `jq` — useful for reading Loki, Airflow, and Docker JSON responses.
- `gh` — optional; useful for GitHub PR/CI investigation.

## Поиск по run_id

Найти все события одного logical run:

```logql
{job=~"pklpo_app|pklpo_airflow"} | json | run_id = "abc123def456"
```

Заменить `abc123def456` на реальный run_id из CLI output или из Airflow log.

## run_id -> trace_id -> Tempo

`run_id` remains the primary incident key. Use it first to find the complete
Loki timeline. For log lines where `trace_id` is not `"-"`, Grafana Explore shows
a derived `trace_id` link to datasource UID `Tempo`.

1. Search Loki by `run_id`.
2. Open a log line with a non-empty `trace_id`.
3. Click the `trace_id` derived field link.
4. Grafana opens the matching Tempo trace for the Airflow task span.

If the log line has `trace_id: "-"`, that code path ran outside an active span.
Continue using the `run_id` timeline as the authoritative investigation view.

## Поиск по symbol

Все события для инструмента за последние 24 часа:

```logql
{job=~"pklpo_app|pklpo_airflow", symbol="BTC-USDT-SWAP"}
```

С фильтром по уровню:

```logql
{job=~"pklpo_app|pklpo_airflow", symbol="BTC-USDT-SWAP", level="ERROR"}
```

## Поиск по error_type

Найти все lock_conflict события:

```logql
{job=~"pklpo_app|pklpo_airflow", error_type="lock_conflict"}
```

Другие типы (полный список `ErrorType`): `db_error`, `api_error`, `timeout_error`,
`rate_limit_error`, `validation_error`, `eligibility_error`, `data_quality_error`,
`permission_error`, `lock_conflict`, `unexpected_error`.

## Поиск по component

Все события repair-компонента с ошибками:

```logql
{job=~"pklpo_app|pklpo_airflow", component="swap_repair", level="ERROR"}
```

Доступные компоненты: `swap_sync`, `swap_repair`, `features`, `market_selection`, `pipeline`.

## Timeline failed run (< 1 минуты)

1. Взять `run_id` из Airflow task log или CLI stderr.
2. Открыть Grafana → Explore → Loki.
3. Ввести:
   ```logql
   {job=~"pklpo_app|pklpo_airflow"} | json | run_id = "<RUN_ID>" | line_format "{{.timestamp}} [{{.level}}] {{.component}} {{.message}}"
   ```
4. Выбрать временной диапазон ±30 минут вокруг предполагаемого времени запуска.
5. Результат — хронологический timeline всех событий для данного run.

## Быстрый health-check

Проверить что Loki получает свежие логи:

```logql
{job="pklpo_app"} [5m]
```

Если пусто — проверить:
- `docker logs pklpo-alloy` — есть ли scrape ошибки
- `docker logs pklpo-loki` — есть ли ingestion ошибки
- Путь `/var/log/pklpo/*.log` существует внутри alloy контейнера
- UI Alloy: http://localhost:12345 → Components → `loki.source.file.*`

## Ограничения OB2

- Этот runbook описывает **только log aggregation**. Metrics dashboard — Prometheus/Grafana отдельно.
- Loki хранит логи 30 дней (`retention_period: 720h` в `loki-config.yml`; compactor включён с `retention_enabled: true`).
- Host-specific collectors (journald, Windows Event Log) не используются. Единственный путь — repo-local JSON files.
