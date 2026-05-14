# ADR: swap_ohlcv_p UTC Storage Calendar

Date: 2026-05-14

## Status

Accepted

## Decision

`swap_ohlcv_p.timestamp` uses a UTC storage model and is the source of truth for
repair planning, gap detection, verification, and repository expected timestamp
calculations.

Storage contract:

- `1H`: UTC hourly opens
- `4H`: UTC 4-hour opens
- `1D`: 00:00 UTC
- `1W`: Monday 00:00 UTC
- `1M`: month start 00:00 UTC

Retention and guarantee contract:

- `1m` is a hot-only operational timeframe. It is allowed for sync heartbeat,
  freshness checks, short operational features, and quality monitoring.
  Historical completeness is not guaranteed for `1m`.
- `1m` is not part of historical SLA, last-200 guarantees, long-term
  repair/backfill guarantees, or long retention policy.
- Historical guarantees apply to `1H`, `4H`, `1D`, `1W`, and `1M`.
- Operational freshness and historical completeness are separate contracts.

Retention matrix:

| Timeframe | Retention | Historical SLA |
| --- | ---: | --- |
| `1m` | 2 days | No |
| `5m` | 7 days | No |
| `15m` | 14 days | No |
| `30m` | 30 days | No |
| `1H` | 14 days | Yes, last 200 closed bars |
| `4H` | 60 days | Yes, last 200 closed bars |
| `1D` | 400 days | Yes, last 200 closed bars |
| `1W` | infinite | Yes, last 200 closed bars |
| `1M` | infinite | Yes, last 200 closed bars |

Raw exchange calendars are a separate concept. OKX classic raw opens may use
CST-aligned daily, weekly, or monthly bars and must not be injected into repair
or storage gap detection.

## Consequences

- Repair uses `StorageCalendar`.
- OKX raw open semantics are represented separately by `OKXRawCalendar` /
  `ExchangeRawCalendar`.
- OKX history fetches request UTC variants for storage daily/weekly/monthly
  bars (`1Dutc`, `1Wutc`, `1Mutc`) when those storage timeframes are fetched.
- Classic `okx_swap_repair_v1` temporarily supports only `1H` and `4H` until
  higher timeframe normalization is proven end to end.
- Existing historical DB timestamps must not be migrated to CST.
- `swap_ohlcv_p` cleanup is policy-driven by
  `swap_ohlcv_retention_policy`; `NULL retention_days` means infinite
  retention.
- Cleanup must run as scheduled maintenance, not as an `AFTER INSERT` trigger on
  candle writes.
