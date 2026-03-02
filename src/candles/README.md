# Candles Module

OHLCV synchronization for OKX SWAP instruments with optional extra market data.

## What is implemented

- Main sync pipeline: `sync_swap_candles.py`
- Optional CCXT-based market adapter: `ccxt_okx_adapter.py`
- Adapter factory (`infrastructure/adapters.py`) with `ccxt`/`legacy` selection
- Legacy adapter is resolved lazily via factory (no direct cross-module imports in candles)
- Incremental sync with UPSERT (`ON CONFLICT`) into `swap_ohlcv_p`
- Retry/backoff handling for API errors (including rate-limit cases)
- Adaptive runtime batch sizing (latency/rate-limit driven)
- CLI wrapper for operations and diagnostics: `swap_cli.py`

## Files

- `sync_swap_candles.py`: core sync orchestration
- `repository.py`: DB persistence for swap candles (UPSERT path)
- `sync_policy.py`: retry/backoff/batch policy
- `domain/timeframes.py`: single source of truth for timeframe conversions (`TF_TO_MS`, `TF_TO_SEC`)
- `ports.py`: adapter/repository protocols
- `infrastructure/adapters.py`: adapter factory (`ccxt`/`legacy`) + legacy factory loader
- `infrastructure/extra_data.py`: `ExtraDataFetcher` (funding/OI cache + endpoint stats)
- `instruments_service.py`: cache-file resolver and list refresh service
- `candles_cli_service.py`: read-model services for CLI diagnostics
- `swap_cli.py`: command-line utility (`sync`, `status`, `details`, `cleanup`, `export`)
- `sync_candles.py`: deprecated compatibility wrapper (delegates to `sync_swap_candles`)
- `load_instruments.py`: instrument list loading helper
- `update_instruments_list.py`: instrument list refresh helper

## Runtime flow

1. Resolve symbols (from input, cached file, or DB fallback).
2. For each symbol and timeframe, fetch candles in pages.
3. Optionally fetch extra data (`funding_rate`, `open_interest`).
4. Persist to `swap_ohlcv_p` via UPSERT by `(symbol, timeframe, timestamp)`.
5. Collect endpoint and throughput stats (`candles` + optional `funding/open_interest`).

## Configuration

`sync_swap_candles` accepts a `config` dictionary. Current keys:

- `max_requests_per_second` (int): global RPS limiter
- `batch_size` (int): initial candles per request
- `max_retries` (int): retry attempts for retriable API errors
- `retry_delay` (float): base delay for backoff
- `max_concurrent_symbols` (int): concurrent symbol workers
- `extra_data` (bool): fetch funding/open-interest
- `use_ccxt` (bool): backward-compatible switch (`True` => `ccxt`, `False` => `legacy`)
- `adapter` (str): explicit adapter name (`ccxt` or `legacy`)
- `legacy_adapter_factory` (callable): optional runtime factory for legacy adapter when `adapter=legacy`

Environment override:

- `CANDLES_ADAPTER=ccxt|legacy` selects adapter when `config["adapter"]` is not set.
- `CANDLES_LEGACY_ADAPTER_FACTORY=module.path:factory_name` registers legacy adapter factory for `legacy` mode.
- `INSTRUMENTS_CACHE_DIR=/custom/path` overrides cache file directory for `instruments_list.json`.
  If not set, resolver uses platform temp directory (`tempfile.gettempdir()`).

Default behavior:

- repository writes are idempotent by `(symbol, timeframe, timestamp)`
- retry/backoff behavior is defined in `SwapSyncPolicy`

## CCXT notes

- Dependency: `ccxt>=4.4.0,<5.0.0`
- Adapter maps internal instrument IDs like `BTC-USDT-SWAP` to CCXT symbols like `BTC/USDT:USDT`.
- Methods implemented for compatibility with existing sync code:
  - `get_candles(...)`
  - `get_funding_rates([...])`
  - `get_open_interest([...])`
  - async context manager support (`__aenter__`, `__aexit__`)

## Usage

### Python API

```python
import asyncio
from src.candles.sync_swap_candles import sync_swap_candles

async def run():
    stats = await sync_swap_candles(
        symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        timeframes=["1m", "5m", "1H"],
        config={
            "use_ccxt": True,
            "extra_data": True,
            "batch_size": 300,
        },
    )
    print(stats)

asyncio.run(run())
```

### CLI

```bash
# Full sync (all symbols from resolver)
python -m src.candles.swap_cli sync

# Sync specific symbols/timeframes
python -m src.candles.swap_cli sync --symbols BTC-USDT-SWAP ETH-USDT-SWAP --timeframes 1m 5m 1H

# Status
python -m src.candles.swap_cli status

# Symbol details
python -m src.candles.swap_cli details BTC-USDT-SWAP

# Cleanup old data
python -m src.candles.swap_cli cleanup --days 30

# Export symbol data
python -m src.candles.swap_cli export BTC-USDT-SWAP btc_swap.json --timeframes 1m 5m

# Adapter parity check (legacy vs CCXT)
python -m src.candles.swap_cli parity --symbols BTC-USDT-SWAP ETH-USDT-SWAP --timeframe 1m --limit 200

# Adapter parity check with explicit gate thresholds (non-zero exit on gate fail)
python -m src.candles.swap_cli parity \
  --symbols BTC-USDT-SWAP ETH-USDT-SWAP \
  --timeframe 1m \
  --limit 200 \
  --max-failed-symbols 0 \
  --max-mismatch-per-symbol 0 \
  --max-missing-per-symbol 0 \
  --max-extra-per-symbol 0
```

## Safety / migration note

During recent phase work, a temporary backup directory was created:

- `src/OLD_candles_YYYYMMDD_HHMM`

It is intentionally left in place for manual cleanup after final verification.

### Legacy path deprecation

- Legacy entrypoint `src.candles.sync_candles.fetch_and_sync_candles` is now a compatibility wrapper.
- It raises `DeprecationWarning` and forwards execution to `sync_swap_candles`.
- Migration target:
  - from: `from src.candles.sync_candles import fetch_and_sync_candles`
  - to: `from src.candles.sync_swap_candles import sync_swap_candles`

## Observability outputs

`sync_swap_candles` returns aggregated stats, including:

- total symbols
- total candles upserted
- errors count
- duration and throughput
- endpoint stats (`candles`, `funding`, `open_interest`)
- fill stats for today's data
- DB write metrics (`latency_avg_ms`, `latency_p95_ms`, `batch_size_avg`, `batch_size_max`)

## Failure handling

- Retriable API failures use exponential backoff with jitter.
- Unsupported timeframe responses are handled gracefully.
- DB write failures trigger rollback in current session scope.
- If extra-data fetch fails, candle sync continues (warning + endpoint error stats).

## CI DoD Gate

For Phase 1 completion, candles has an explicit CI DoD target:

```bash
python scripts/run_candles_dod.py
```

The gate includes:

- parity tests (`tests/candles/test_parity_check.py`)
- smoke imports (`-m smoke` over `tests/candles`)
- coverage gate for candles module (`--cov=src/candles --cov-fail-under=50`)
