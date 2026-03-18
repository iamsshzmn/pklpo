# Candles Module

**Р’РµСЂСЃРёСЏ:** 2.1.0 | **РЎС‚Р°С‚СѓСЃ:** Production Ready

РњРѕРґСѓР»СЊ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё OHLCV-СЃРІРµС‡РµР№ Рё СЂС‹РЅРѕС‡РЅС‹С… РјРµС‚Р°РґР°РЅРЅС‹С… РґР»СЏ OKX SWAP-РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ СЃ РёРґРµРјРїРѕС‚РµРЅС‚РЅРѕР№ Р·Р°РїРёСЃСЊСЋ РІ PostgreSQL, РїРѕРґРґРµСЂР¶РєРѕР№ `ccxt`/legacy-Р°РґР°РїС‚РµСЂРѕРІ, Airflow entrypoints Рё operational CLI.

---

## 1. Purpose

`src/candles` РѕС‚РІРµС‡Р°РµС‚ Р·Р° Р·Р°РіСЂСѓР·РєСѓ Рё РѕР±РЅРѕРІР»РµРЅРёРµ СЃРІРµС‡РµР№ РїРѕ SWAP USDT-РёРЅСЃС‚СЂСѓРјРµРЅС‚Р°Рј OKX СЃ РіР°СЂР°РЅС‚РёРµР№:

- **Incremental sync** - РґР°РЅРЅС‹Рµ РґРѕРіСЂСѓР¶Р°СЋС‚СЃСЏ СЃС‚СЂР°РЅРёС†Р°РјРё С‡РµСЂРµР· `before`-pagination Рё РїСЂРѕРґРѕР»Р¶Р°СЋС‚СЃСЏ РѕС‚ РїРѕСЃР»РµРґРЅРµРіРѕ СЃРѕС…СЂР°РЅС‘РЅРЅРѕРіРѕ `timestamp`
- **Idempotent writes** - РїРѕРІС‚РѕСЂРЅС‹Рµ Р·Р°РїСѓСЃРєРё Р±РµР·РѕРїР°СЃРЅС‹ Р±Р»Р°РіРѕРґР°СЂСЏ `UPSERT` РїРѕ `(symbol, timeframe, timestamp)`
- **Adapter isolation** - runtime-Р°РґР°РїС‚РµСЂ РІС‹Р±РёСЂР°РµС‚СЃСЏ С‡РµСЂРµР· factory, Р° application-СЃР»РѕР№ СЂР°Р±РѕС‚Р°РµС‚ С‡РµСЂРµР· РїРѕСЂС‚С‹
- **Operational flexibility** - РјРѕРґСѓР»СЊ Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ РёР· Python API, CLI Рё Airflow use cases
- **Graceful degradation** - СЃР±РѕР№ primary adapter РЅРµ Р»РѕРјР°РµС‚ РѕР±С‰РёР№ pipeline, РµСЃР»Рё РґРѕСЃС‚СѓРїРµРЅ fallback

**РљР»СЋС‡РµРІС‹Рµ РІРѕР·РјРѕР¶РЅРѕСЃС‚Рё:**

- СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ С‚Р°Р№РјС„СЂРµР№РјРѕРІ `1m`, `5m`, `15m`, `30m`, `1H`, `4H`, `12H`, `1D`, `1W`, `1M`
- РїР°СЂР°Р»Р»РµР»СЊРЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° СЃРёРјРІРѕР»РѕРІ СЃ РѕРіСЂР°РЅРёС‡РµРЅРёРµРј `max_concurrent_symbols`
- retry/backoff РґР»СЏ `429`, `50011`, `Too Many Requests` Рё РІСЂРµРјРµРЅРЅС‹С… РѕС€РёР±РѕРє API
- РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ sync РёРґС‘С‚ Р±РµР· extra data; `funding_rate` Рё `open_interest` РІРєР»СЋС‡Р°СЋС‚СЃСЏ РѕС‚РґРµР»СЊРЅРѕ
- Airflow-СЂРµР¶РёРјС‹ `fast`, `slow`, `ext`, `bootstrap`
- refresh РєР°С‚Р°Р»РѕРіР° РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ Рё metadata-facing API РІ С‚РѕРј Р¶Рµ РїР°РєРµС‚Рµ
- parity-check РјРµР¶РґСѓ `legacy` Рё `ccxt` Р°РґР°РїС‚РµСЂР°РјРё

---

## 2. Inputs

### 2.1 РСЃС‚РѕС‡РЅРёРєРё РґР°РЅРЅС‹С…

| РСЃС‚РѕС‡РЅРёРє | РћРїРёСЃР°РЅРёРµ | Р¤РѕСЂРјР°С‚ |
|----------|----------|--------|
| OKX market adapter | РћСЃРЅРѕРІРЅРѕР№ РёСЃС‚РѕС‡РЅРёРє СЃРІРµС‡РµР№, funding rate Рё open interest | async adapter protocol |
| Cache file `instruments_list.json` | РљРµС€ СЃРїРёСЃРєР° РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ | JSON array |
| PostgreSQL `instruments` | Fallback-РёСЃС‚РѕС‡РЅРёРє СЃРїРёСЃРєР° SWAP USDT СЃРёРјРІРѕР»РѕРІ | DB table |
| Runtime config | РЈРїСЂР°РІР»РµРЅРёРµ СЂРµР¶РёРјРѕРј sync Рё РїРѕР»РёС‚РёРєР°РјРё retry/concurrency | `dict[str, Any]` |
| Airflow `dag_run.conf` | РџРµСЂРµРѕРїСЂРµРґРµР»РµРЅРёРµ mode, symbols, timeframes, extra data | mapping |

### 2.2 Р’С…РѕРґРЅРѕР№ Python API

```python
from src.candles.interfaces.swap_sync import sync_swap_candles

stats = await sync_swap_candles(
    symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],  # optional
    timeframes=["1m", "5m", "1H"],              # optional
    config={                                    # optional
        "adapter": "ccxt",
        "extra_data": True,
        "batch_size": 300,
    },
)
```

| РџР°СЂР°РјРµС‚СЂ | РўРёРї | РћРїРёСЃР°РЅРёРµ |
|----------|-----|----------|
| `symbols` | `list[str] | None` | РЇРІРЅС‹Р№ СЃРїРёСЃРѕРє РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ; РµСЃР»Рё РЅРµ РїРµСЂРµРґР°РЅ, СЃРїРёСЃРѕРє СЂРµР·РѕР»РІРёС‚СЃСЏ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё |
| `timeframes` | `list[str] | None` | РЇРІРЅС‹Р№ РЅР°Р±РѕСЂ С‚Р°Р№РјС„СЂРµР№РјРѕРІ; РµСЃР»Рё РЅРµ РїРµСЂРµРґР°РЅ, Р±РµСЂС‘С‚СЃСЏ `SWAP_BARS` |
| `config` | `dict[str, Any] | None` | Runtime-РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ sync |

### 2.3 Runtime config

Р—РЅР°С‡РµРЅРёСЏ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ Р·Р°РґР°СЋС‚СЃСЏ РІ `src.candles.domain.sync_config.DEFAULT_CONFIG`:

```python
DEFAULT_CONFIG = {
    "max_requests_per_second": 80,
    "batch_size": 300,
    "max_retries": 3,
    "retry_delay": 1.0,
    "max_concurrent_symbols": 3,
    "extra_data": False,
    "use_ccxt": True,
    "dynamic_batch_size": False,
}
```

| РљР»СЋС‡ | РўРёРї | РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ | РћРїРёСЃР°РЅРёРµ |
|------|-----|--------------|----------|
| `max_requests_per_second` | `int` | `80` | RPS limit РґР»СЏ primary adapter |
| `batch_size` | `int` | `300` | Р Р°Р·РјРµСЂ РѕРґРЅРѕР№ СЃС‚СЂР°РЅРёС†С‹ СЃРІРµС‡РµР№ |
| `max_retries` | `int` | `3` | Р›РёРјРёС‚ retry РґР»СЏ retriable-РѕС€РёР±РѕРє |
| `retry_delay` | `float` | `1.0` | Р‘Р°Р·РѕРІР°СЏ Р·Р°РґРµСЂР¶РєР° backoff |
| `max_concurrent_symbols` | `int` | `3` | РџР°СЂР°Р»Р»РµР»РёР·Рј РїРѕ СЃРёРјРІРѕР»Р°Рј |
| `extra_data` | `bool` | `False` | Р”РѕРіСЂСѓР¶Р°С‚СЊ funding/open interest |
| `use_ccxt` | `bool` | `True` | Backward-compatible РїРµСЂРµРєР»СЋС‡Р°С‚РµР»СЊ Р°РґР°РїС‚РµСЂР° |
| `adapter` | `str` | auto | РЇРІРЅС‹Р№ РІС‹Р±РѕСЂ `ccxt` РёР»Рё `legacy` |
| `legacy_adapter_factory` | `callable` | `None` | Runtime factory РґР»СЏ legacy adapter |
| `dynamic_batch_size` | `bool` | `False` | Р¤Р»Р°Рі РґР»СЏ adaptive batch policy |

РџРѕРІРµРґРµРЅРёРµ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ:

- `extra_data=False`, РїРѕСЌС‚РѕРјСѓ РѕСЃРЅРѕРІРЅРѕР№ sync РїРёС€РµС‚ С‚РѕР»СЊРєРѕ OHLCV-СЃРІРµС‡Рё
- - Р·Р°РїСЂРѕСЃС‹ `funding_rate` Рё `open_interest` РЅРµ РІС‹РїРѕР»РЅСЏСЋС‚СЃСЏ, РїРѕРєР° extra data СЏРІРЅРѕ РЅРµ РІРєР»СЋС‡РµРЅС‹
- РµСЃР»Рё `symbols` РЅРµ РїРµСЂРµРґР°РЅС‹, РјРѕРґСѓР»СЊ РІСЃС‘ СЂР°РІРЅРѕ РјРѕР¶РµС‚ РѕР±РЅРѕРІРёС‚СЊ РёР»Рё РїСЂРѕС‡РёС‚Р°С‚СЊ РєР°С‚Р°Р»РѕРі РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ РґР»СЏ СЂРµР·РѕР»РІР° СЃРїРёСЃРєР° СЃРёРјРІРѕР»РѕРІ

### 2.4 Environment variables

| Variable | Default | РћРїРёСЃР°РЅРёРµ |
|----------|---------|----------|
| `CANDLES_ADAPTER` | unset | Р’С‹Р±РѕСЂ Р°РґР°РїС‚РµСЂР°, РµСЃР»Рё `config["adapter"]` РЅРµ Р·Р°РґР°РЅ |
| `CANDLES_LEGACY_ADAPTER_FACTORY` | unset | РџСѓС‚СЊ РІРёРґР° `module.path:factory_name` РґР»СЏ legacy adapter |
| `INSTRUMENTS_CACHE_DIR` | temp dir | Р”РёСЂРµРєС‚РѕСЂРёСЏ РґР»СЏ `instruments_list.json` |

---

## 3. Outputs

### 3.1 Sink

| РўР°Р±Р»РёС†Р° | РћРїРёСЃР°РЅРёРµ |
|---------|----------|
| `swap_ohlcv_p` | РћСЃРЅРѕРІРЅР°СЏ С‚Р°Р±Р»РёС†Р° СЃРІРµС‡РµР№ SWAP-РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ |

### 3.2 РЎС…РµРјР° Р·Р°РїРёСЃРё

**Primary Key:** `(symbol, timeframe, timestamp)`

| РљРѕР»РѕРЅРєР° | РўРёРї | РћРїРёСЃР°РЅРёРµ |
|---------|-----|----------|
| `symbol` | text/varchar | РўРѕСЂРіРѕРІС‹Р№ РёРЅСЃС‚СЂСѓРјРµРЅС‚ |
| `timeframe` | text/varchar | РўР°Р№РјС„СЂРµР№Рј СЃРІРµС‡Рё |
| `timestamp` | bigint | Unix timestamp РІ ms |
| `open` | numeric | Р¦РµРЅР° РѕС‚РєСЂС‹С‚РёСЏ |
| `high` | numeric | РњР°РєСЃРёРјСѓРј |
| `low` | numeric | РњРёРЅРёРјСѓРј |
| `close` | numeric | Р¦РµРЅР° Р·Р°РєСЂС‹С‚РёСЏ |
| `volume` | numeric | Р‘Р°Р·РѕРІС‹Р№ РѕР±СЉС‘Рј |
| `vol_ccy` | numeric / null | РћР±СЉС‘Рј РІ РІР°Р»СЋС‚Рµ РєРѕС‚РёСЂРѕРІРєРё |
| `vol_usd` | numeric / null | РћР±СЉС‘Рј РІ USD |
| `funding_rate` | numeric / null | Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ СЂС‹РЅРѕС‡РЅС‹Рµ РґР°РЅРЅС‹Рµ |
| `open_interest` | numeric / null | Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ СЂС‹РЅРѕС‡РЅС‹Рµ РґР°РЅРЅС‹Рµ |
| `fetched_at` | timestamp | Р’СЂРµРјСЏ Р·Р°РїРёСЃРё |

### 3.3 Р’РѕР·РІСЂР°С‰Р°РµРјР°СЏ СЃС‚Р°С‚РёСЃС‚РёРєР°

`sync_swap_candles()` РІРѕР·РІСЂР°С‰Р°РµС‚ Р°РіСЂРµРіРёСЂРѕРІР°РЅРЅС‹Р№ СЃР»РѕРІР°СЂСЊ:

```python
{
    "total_symbols": 0,
    "total_candles_synced": 0,
    "total_symbols_processed": 0,
    "errors_count": 0,
    "duration_seconds": 0.0,
    "symbols_per_second": 0.0,
    "candles_per_second": 0.0,
    "results_by_symbol": {},
    "endpoint_stats": {},
    "today_fill": {},
    "db_write": {},
}
```

РљР»СЋС‡РµРІС‹Рµ РІР»РѕР¶РµРЅРЅС‹Рµ Р±Р»РѕРєРё:

- `results_by_symbol` - РєРѕР»РёС‡РµСЃС‚РІРѕ Р·Р°РїРёСЃР°РЅРЅС‹С… СЃРІРµС‡РµР№ РїРѕ `symbol -> timeframe`
- `endpoint_stats` - `candles`, `funding`, `open_interest`: `ok`, `retries`, `rate_limit`, `errors`
- `today_fill` - fill-rate РїРѕ `funding_rate` Рё `open_interest` Р·Р° С‚РµРєСѓС‰РёР№ РґРµРЅСЊ
- `db_write` - РєРѕР»РёС‡РµСЃС‚РІРѕ write-РѕРїРµСЂР°С†РёР№, СЃСЂРµРґРЅСЏСЏ Рё p95 latency, СЂР°Р·РјРµСЂС‹ Р±Р°С‚С‡РµР№

---

## 4. Data Flow

### 4.1 РљСЂР°С‚РєРѕРµ РѕРїРёСЃР°РЅРёРµ

```text
symbols input/cache/DB -> adapter fetch -> optional extra data -> UPSERT -> aggregated stats
```

### 4.2 Р”РµС‚Р°Р»СЊРЅР°СЏ СЃС…РµРјР°

```text
INPUT
  symbols arg OR instruments cache OR repository fallback
  timeframes arg OR all supported timeframes
  config dict + env overrides
    |
    v
SYMBOL RESOLUTION
  1. explicit symbols
  2. refresh_instruments_list()
  3. read instruments_list.json
  4. repository.list_swap_symbols() fallback
    |
    v
FETCHING
  market_data.fetch_candles(instrument_id, timeframe, limit, before)
  retry/backoff for 429 / 50011 / temporary errors
  unsupported timeframe -> warning + graceful skip
    |
    v
OPTIONAL EXTRA DATA
  fetch_funding_rates([symbol])
  fetch_open_interest([symbol])
    |
    v
PERSISTENCE
  repository.upsert_candles(...)
  INSERT ... ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE
    |
    v
AGGREGATION
  results_by_symbol
  endpoint_stats
  today_fill
  db_write latency metrics
```

### 4.3 Runtime path

```text
interfaces.swap_sync.sync_swap_candles()
  -> sync_runtime.run_sync_via_application()
  -> application.sync.run_candle_sync()
  -> runtime_adapters bridge ports to legacy repository/adapter
  -> repository.upsert_candles()
  -> legacy_stats_from_result()
```

---

## 5. Architecture

### 5.1 Layers & Responsibilities

| РЎР»РѕР№ | РћС‚РІРµС‚СЃС‚РІРµРЅРЅРѕСЃС‚СЊ | РљР»СЋС‡РµРІС‹Рµ РјРѕРґСѓР»Рё |
|------|-----------------|-----------------|
| **Interfaces** | РџСѓР±Р»РёС‡РЅС‹Рµ entrypoints РґР»СЏ Python API Рё Airflow | `interfaces/swap_sync.py`, `interfaces/airflow_sync.py` |
| **Application** | Use cases sync, metadata refresh, smoke/freshness checks | `application/sync/use_cases.py`, `application/sync_use_cases.py`, `application/metadata/use_cases.py` |
| **Domain** | РљРѕРЅС„РёРі, timeframes, quality/risk/contracts, DTO assumptions | `domain/sync_config.py`, `domain/timeframes.py`, `domain/quality.py`, `domain/contract.py` |
| **Infrastructure** | Adapter factory, runtime bridges, extra data, DB access, config, ingest helpers | `infrastructure/adapters.py`, `infrastructure/runtime_adapters.py`, `infrastructure/extra_data.py`, `infrastructure/database.py` |
| **Persistence / Read model** | UPSERT СЃРІРµС‡РµР№, latest timestamp, fill stats, CLI queries | `repository.py`, `candles_cli_service.py` |
| **CLI / Operations** | Sync, status, details, cleanup, export, parity | `swap_cli.py`, `cli/cli.py`, `parity_check.py` |
| **Observability** | Prometheus hooks, endpoint stats, db write metrics | `observability/prometheus.py`, aggregated sync stats |

### 5.2 Dependency direction

Р—Р°РІРёСЃРёРјРѕСЃС‚Рё РЅР°РїСЂР°РІР»РµРЅС‹ РІРЅСѓС‚СЂСЊ:

```text
Interfaces
  -> Application
  -> Domain

Infrastructure
  -> Domain / Application ports

Repository / Adapters
  <- runtime bridges from sync_runtime
```

РџСЂР°РєС‚РёС‡РµСЃРєРё СЌС‚Рѕ РѕР·РЅР°С‡Р°РµС‚:

- interface-СЃР»РѕР№ РЅРµ СЃРѕРґРµСЂР¶РёС‚ Р±РёР·РЅРµСЃ-Р»РѕРіРёРєРё СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё
- application-СЃР»РѕР№ РЅРµ Р·Р°РІРёСЃРёС‚ РѕС‚ РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ `ccxt` API РЅР°РїСЂСЏРјСѓСЋ
- РєРѕРЅРєСЂРµС‚РЅС‹Рµ Р°РґР°РїС‚РµСЂС‹ Рё repository РїРѕРґРєР»СЋС‡Р°СЋС‚СЃСЏ С‡РµСЂРµР· runtime bridge
- СЃС‚Р°СЂС‹Р№ sync-РєРѕРЅС‚СѓСЂ РѕСЃС‚Р°С‘С‚СЃСЏ СЃРѕРІРјРµСЃС‚РёРјС‹Рј, РЅРѕ orchestration СѓР¶Рµ РёРґС‘С‚ С‡РµСЂРµР· application use case

### 5.3 Invariants

| РРЅРІР°СЂРёР°РЅС‚ | РћРїРёСЃР°РЅРёРµ |
|-----------|----------|
| **Idempotent persistence** | РџРѕРІС‚РѕСЂРЅС‹Р№ Р·Р°РїСѓСЃРє СЃ С‚РµРјРё Р¶Рµ СЃРІРµС‡Р°РјРё РЅРµ СЃРѕР·РґР°С‘С‚ РґСѓР±Р»РёРєР°С‚С‹ |
| **Incremental backfill** | Р”РѕРіСЂСѓР·РєР° РѕСЃС‚Р°РЅР°РІР»РёРІР°РµС‚СЃСЏ, РєРѕРіРґР° РґРѕСЃС‚РёРіРЅСѓС‚ СѓР¶Рµ СЃРѕС…СЂР°РЅС‘РЅРЅС‹Р№ `timestamp` |
| **Bounded concurrency** | РџР°СЂР°Р»Р»РµР»РёР·Рј РѕРіСЂР°РЅРёС‡РµРЅ `asyncio.Semaphore(max_concurrent_symbols)` |
| **Retriable failures only** | Retry РїСЂРёРјРµРЅСЏРµС‚СЃСЏ С‚РѕР»СЊРєРѕ Рє СЂР°СЃРїРѕР·РЅР°РЅРЅС‹Рј retriable/rate-limit РѕС€РёР±РєР°Рј |
| **Adapter replaceability** | Runtime adapter РјРѕР¶РµС‚ Р±С‹С‚СЊ Р·Р°РјРµРЅС‘РЅ Р±РµР· РёР·РјРµРЅРµРЅРёСЏ application use case |
| **Extra data is optional** | РћС€РёР±РєР° funding/open interest РЅРµ РґРѕР»Р¶РЅР° Р»РѕРјР°С‚СЊ РѕСЃРЅРѕРІРЅРѕР№ candle sync |

---

## 6. Modes, Policies And Triggering

### 6.1 Airflow mode presets

`src.candles.application.sync_use_cases.MODE_CONFIGS`:

| Mode | Timeframes | Extra data | Concurrency | RPS |
|------|------------|------------|-------------|-----|
| `fast` | `1m`, `5m` | `False` | `10` | `20` |
| `slow` | `15m`, `30m`, `1H`, `4H`, `12H`, `1D`, `1W`, `1M` | `False` | `2` | `15` |
| `ext` | `1m`, `5m` | `True` | `5` | `15` |
| `bootstrap` | all supported TF | `True` | `1` | `15` |

### 6.2 Freshness gate

РџРµСЂРµРґ scheduled Airflow sync РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ `check_data_freshness()`:

- РґР»СЏ `fast` РїСЂРѕРІРµСЂСЏРµС‚СЃСЏ `1m`, max lag `120s`
- РґР»СЏ `slow` РїСЂРѕРІРµСЂСЏРµС‚СЃСЏ `15m`, max lag `900s`
- РµСЃР»Рё РґР°РЅРЅС‹Рµ РґРѕСЃС‚Р°С‚РѕС‡РЅРѕ СЃРІРµР¶РёРµ, sync РїСЂРѕРїСѓСЃРєР°РµС‚СЃСЏ
- manual runs freshness gate РЅРµ РёСЃРїРѕР»СЊР·СѓСЋС‚

### 6.3 Retry policy

| РџР°СЂР°РјРµС‚СЂ | РСЃС‚РѕС‡РЅРёРє |
|----------|----------|
| `max_retries` | request config |
| `initial_delay` | `retry_delay` |
| `backoff` | incremental bump С‡РµСЂРµР· `RetryPolicy` |
| rate limit markers | `429`, `Too Many Requests`, `50011` |

РћС‚РґРµР»СЊРЅРѕ РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚СЃСЏ РєРµР№СЃ unsupported timeframe:

- РѕС€РёР±РєР° `51000` + `Parameter bar error`
- РґР»СЏ С‚Р°РєРѕРіРѕ С‚Р°Р№РјС„СЂРµР№РјР° sync РІРѕР·РІСЂР°С‰Р°РµС‚ `0` СЃРІРµС‡РµР№ Рё РїСЂРѕРґРѕР»Р¶Р°РµС‚ СЂР°Р±РѕС‚Сѓ

### 6.4 Adapter selection

РџСЂРё Р·Р°РїСѓСЃРєРµ runtime adapter РІС‹Р±РёСЂР°РµС‚СЃСЏ РІ С‚Р°РєРѕРј РїРѕСЂСЏРґРєРµ:

1. `config["adapter"]`
2. `CANDLES_ADAPTER`
3. `config["use_ccxt"]`

Р•СЃР»Рё primary adapter РЅРµ РёРЅРёС†РёР°Р»РёР·РёСЂСѓРµС‚СЃСЏ:

- РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ fallback РЅР° `legacy`
- РµСЃР»Рё fallback С‚РѕР¶Рµ РЅРµРґРѕСЃС‚СѓРїРµРЅ, РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ `UnavailableMarketDataAdapter`
- sync Р·Р°РІРµСЂС€Р°РµС‚СЃСЏ СЏРІРЅРѕР№ runtime error СЃ РїСЂРёС‡РёРЅРѕР№ РёРЅРёС†РёР°Р»РёР·Р°С†РёРё

---

## 7. Public Surface And Core Components

### 7.1 Public entrypoints

| Entry point | РќР°Р·РЅР°С‡РµРЅРёРµ |
|-------------|------------|
| `interfaces.swap_sync.sync_swap_candles` | Canonical Python sync facade |
| `interfaces.airflow_sync.run_swap_sync` | Airflow sync use case |
| `interfaces.airflow_sync.run_catalog_refresh_job` | Airflow refresh РєР°С‚Р°Р»РѕРіР° РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ |
| `api.refresh_market_metadata` | Metadata refresh С‡РµСЂРµР· neutral API |
| `api.run_metadata_refresh_job` | Metadata refresh job facade |
| `api.validate_instrument_order` | РџСЂРѕРІРµСЂРєР° РѕСЂРґРµСЂРЅС‹С… РѕРіСЂР°РЅРёС‡РµРЅРёР№ РїРѕ market metadata |
| `swap_cli.py` | Operational CLI |

### 7.2 Core components

| РљРѕРјРїРѕРЅРµРЅС‚ | РћС‚РІРµС‚СЃС‚РІРµРЅРЅРѕСЃС‚СЊ |
|-----------|-----------------|
| `sync_runtime.py` | РЎР±РѕСЂРєР° runtime dependencies Рё bridge Рє application use case |
| `application/sync/use_cases.py` | РћСЃРЅРѕРІРЅРѕР№ orchestration sync |
| `runtime_adapters.py` | РђРґР°РїС‚Р°С†РёСЏ legacy adapter/repository Рє РЅРѕРІС‹Рј РїРѕСЂС‚Р°Рј |
| `repository.py` | UPSERT, latest timestamp, fill stats, symbol queries |
| `instruments_service.py` | Refresh Рё С‡С‚РµРЅРёРµ РєР°С‚Р°Р»РѕРіР° РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ |
| `application/sync_use_cases.py` | Airflow mode config, freshness gate, smoke validation, XCom formatting |
| `application/metadata/use_cases.py` | Refresh market metadata Рё order validation |
| `parity_check.py` | РЎСЂР°РІРЅРµРЅРёРµ payload РјРµР¶РґСѓ legacy Рё `ccxt` |
| `candles_cli_service.py` | Read-model РѕРїРµСЂР°С†РёРё РґР»СЏ `status/details/export/cleanup` |

### 7.3 CLI commands

`python -m src.candles.swap_cli ...`

| Command | РќР°Р·РЅР°С‡РµРЅРёРµ |
|---------|------------|
| `sync` | РџРѕР»РЅР°СЏ РёР»Рё РІС‹Р±РѕСЂРѕС‡РЅР°СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ |
| `status` | РЎРІРѕРґРєР° РїРѕ РґР°РЅРЅС‹Рј РІ `swap_ohlcv_p` |
| `details <symbol>` | Р”РµС‚Р°Р»Рё РїРѕ РєРѕРЅРєСЂРµС‚РЅРѕРјСѓ СЃРёРјРІРѕР»Сѓ |
| `cleanup --days N` | РЈРґР°Р»РµРЅРёРµ СЃС‚Р°СЂС‹С… РґР°РЅРЅС‹С… |
| `export <symbol> <file>` | Р­РєСЃРїРѕСЂС‚ РґР°РЅРЅС‹С… РІ JSON |
| `parity` | РЎСЂР°РІРЅРµРЅРёРµ `legacy` Рё `ccxt` Р°РґР°РїС‚РµСЂРѕРІ |

---

## 8. Runbook

### 8.1 Python API

```python
import asyncio
from src.candles.interfaces.swap_sync import sync_swap_candles

async def run() -> None:
    stats = await sync_swap_candles(
        symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        timeframes=["1m", "5m", "1H"],
        config={
            "adapter": "ccxt",
            "extra_data": True,
            "batch_size": 300,
            "max_concurrent_symbols": 3,
        },
    )
    print(stats)

asyncio.run(run())
```

### 8.2 CLI

```bash
python -m src.candles.swap_cli sync
python -m src.candles.swap_cli sync --symbols BTC-USDT-SWAP ETH-USDT-SWAP --timeframes 1m 5m 1H
python -m src.candles.swap_cli sync --config config/candles.json
python -m src.candles.swap_cli status
python -m src.candles.swap_cli details BTC-USDT-SWAP
python -m src.candles.swap_cli cleanup --days 30
python -m src.candles.swap_cli export BTC-USDT-SWAP btc_swap.json --timeframes 1m 5m
```

### 8.3 Sync Р±РµР· Рё СЃ extra data

РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ sync Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ Р±РµР· СЂС‹РЅРѕС‡РЅС‹С… РјРµС‚Р°РґР°РЅРЅС‹С…:

```python
await sync_swap_candles(
    symbols=["BTC-USDT-SWAP"],
    timeframes=["1m", "5m"],
    config={"extra_data": False},
)
```

Р§С‚РѕР±С‹ РґРѕРіСЂСѓР¶Р°С‚СЊ `funding_rate` Рё `open_interest`, РІРєР»СЋС‡РёС‚Рµ extra data СЏРІРЅРѕ:

```python
await sync_swap_candles(
    symbols=["BTC-USDT-SWAP"],
    timeframes=["1m", "5m"],
    config={
        "adapter": "ccxt",
        "extra_data": True,
    },
)
```

CLI-РІР°СЂРёР°РЅС‚ С‡РµСЂРµР· JSON config:

```json
{
  "adapter": "ccxt",
  "extra_data": true,
  "batch_size": 300,
  "max_concurrent_symbols": 3
}
```

```bash
python -m src.candles.swap_cli sync --config config/candles.json
```

Р”Р»СЏ Airflow:

- `fast` Рё `slow` СЂР°Р±РѕС‚Р°СЋС‚ СЃ `extra_data=False`
- `ext` Рё `bootstrap` СЂР°Р±РѕС‚Р°СЋС‚ СЃ `extra_data=True`

### 8.4 Parity gate

```powershell
python -m src.candles.swap_cli parity `
  --symbols BTC-USDT-SWAP ETH-USDT-SWAP `
  --timeframe 1m `
  --limit 200 `
  --max-failed-symbols 0 `
  --max-mismatch-per-symbol 0 `
  --max-missing-per-symbol 0 `
  --max-extra-per-symbol 0
```

### 8.5 Airflow-facing entrypoints

```python
from src.candles.interfaces.airflow_sync import (
    run_catalog_refresh_job,
    run_smoke_validate,
    run_swap_sync,
)
```

---

## 9. Notes And Constraints

- РїР°РєРµС‚ СЃРѕРІРјРµС‰Р°РµС‚ РґРІРµ РѕС‚РІРµС‚СЃС‚РІРµРЅРЅРѕСЃС‚Рё: candles sync Рё market metadata facade; СЌС‚Рѕ СѓР¶Рµ РѕС‚СЂР°Р¶РµРЅРѕ РІ `api.py`
- canonical sync facade РЅР°С…РѕРґРёС‚СЃСЏ РІ `interfaces/swap_sync.py`; legacy-compatible РІС‹Р·РѕРІС‹ СЃРѕС…СЂР°РЅСЏСЋС‚СЃСЏ С‡РµСЂРµР· runtime bridge
- `dynamic_batch_size` РїСЂРёСЃСѓС‚СЃС‚РІСѓРµС‚ РІ РєРѕРЅС„РёРіРµ, РЅРѕ СЂРµР°Р»СЊРЅР°СЏ orchestration РІСЃС‘ РµС‰С‘ РѕРїРёСЂР°РµС‚СЃСЏ РЅР° batch policy request limit Рё retry policy
- extra data РґРѕРіСЂСѓР¶Р°РµС‚СЃСЏ РЅР° СѓСЂРѕРІРЅРµ СЃРёРјРІРѕР»Р°, Р° РЅРµ РѕС‚РґРµР»СЊРЅРѕ РЅР° РєР°Р¶РґСѓСЋ СЃРІРµС‡Сѓ
- Р°РєС‚СѓР°Р»СЊРЅРѕСЃС‚СЊ Airflow skip logic Р·Р°РІРёСЃРёС‚ РѕС‚ СЃРІРµР¶РµСЃС‚Рё РґР°РЅРЅС‹С… РІ `swap_ohlcv_p`
- РєРµС€ РёРЅСЃС‚СЂСѓРјРµРЅС‚РѕРІ СЃС‡РёС‚Р°РµС‚СЃСЏ СЃРІРµР¶РёРј 24 С‡Р°СЃР°, РµСЃР»Рё СЏРІРЅРѕ РЅРµ СѓРєР°Р·Р°РЅ `refresh_instruments`

---

**РџРѕСЃР»РµРґРЅРµРµ РѕР±РЅРѕРІР»РµРЅРёРµ:** 2026-03-17

