"""
CLI for managing market metadata.

Commands:
- refresh: update metadata from OKX
- validate: validate an order
- info: get instrument info
- cache: manage cache
"""

import asyncio
import json
import os

import click

from ..application.api import (
    get_instrument_info,
    market_meta_api,
    refresh_okx_meta,
    validate_order,
)
from ..infrastructure.config import get_config, reload_config
from ..infrastructure.database import create_tables, drop_tables
from ..infrastructure.logging_config import configure_logging
from ..infrastructure.metrics import (
    get_metrics_collector,
    get_metrics_monitor,
    start_metrics_services,
    stop_metrics_services,
)


@click.group()
def market_meta():
    """Market metadata management"""
    pass


@market_meta.command()
@click.option("--force", is_flag=True, help="Force refresh")
@click.option(
    "--types", default="SPOT,SWAP,FUTURES", help="Instrument types to load"
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def refresh(force: bool, types: str, verbose: bool):
    """Refresh metadata from OKX"""
    click.echo("Refreshing OKX metadata...")

    async def _refresh():
        try:
            inst_types = [t.strip() for t in types.split(",")]

            if verbose:
                click.echo(f"Loading types: {inst_types}")

            success = await refresh_okx_meta(force=force)

            if success:
                click.echo("Metadata updated successfully")

                if verbose:
                    if market_meta_api.market_metadata:
                        total = len(market_meta_api.market_metadata.instruments)
                        click.echo(f"Loaded instruments: {total}")

                        by_type = {}
                        for (
                            instrument
                        ) in market_meta_api.market_metadata.instruments.values():
                            inst_type = instrument.inst_type.value
                            by_type[inst_type] = by_type.get(inst_type, 0) + 1

                        for inst_type, count in by_type.items():
                            click.echo(f"  {inst_type}: {count}")
            else:
                click.echo("Error updating metadata", err=True)
                return 1

        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            return 1

    return asyncio.run(_refresh())


@market_meta.command()
@click.argument("symbol")
@click.option("--price", "-p", type=float, required=True, help="Price")
@click.option("--qty", "-q", type=float, required=True, help="Quantity")
@click.option("--balance", "-b", type=float, help="Account balance")
@click.option("--order-type", default="limit", help="Order type (limit/market)")
@click.option("--side", default="buy", help="Side (buy/sell)")
@click.option("--leverage", type=float, help="Leverage")
@click.option("--margin-mode", default="isolated", help="Margin mode (isolated/cross)")
@click.option("--spread-bps", type=float, help="Spread in basis points")
@click.option("--vol-usdt", type=float, help="24h volume in USDT")
@click.option("--book-depth", type=float, help="Order book depth in USDT")
@click.option("--json", "output_json", is_flag=True, help="JSON output")
def validate(
    symbol: str,
    price: float,
    qty: float,
    balance: float | None,
    order_type: str,
    side: str,
    leverage: float | None,
    margin_mode: str,
    spread_bps: float | None,
    vol_usdt: float | None,
    book_depth: float | None,
    output_json: bool,
):
    """Validate an order"""

    if not market_meta_api.market_metadata:
        click.echo("Metadata not loaded. Run 'refresh' first", err=True)
        return 1

    violations = validate_order(
        symbol=symbol,
        price=price,
        qty=qty,
        order_type=order_type,
        side=side,
        account_balance=balance,
    )

    if leverage is not None or spread_bps is not None:
        if market_meta_api.validator:
            if leverage is not None:
                risk_result = market_meta_api.validator.validate_risk(
                    symbol, leverage, margin_mode
                )
                if not risk_result.is_valid:
                    violations.extend(risk_result.errors)

            if all(param is not None for param in [spread_bps, vol_usdt, book_depth]):
                liquidity_result = market_meta_api.validator.validate_liquidity(
                    symbol, spread_bps, vol_usdt, book_depth
                )
                if not liquidity_result.is_valid:
                    violations.extend(liquidity_result.errors)

    if output_json:
        result = {
            "symbol": symbol,
            "price": price,
            "qty": qty,
            "is_valid": len(violations) == 0,
            "violations": violations,
            "violations_count": len(violations),
        }
        click.echo(json.dumps(result, indent=2))
    else:
        if violations:
            click.echo(f"Found {len(violations)} violations:")
            for i, violation in enumerate(violations, 1):
                click.echo(f"  {i}. {violation}")
        else:
            click.echo("Order is valid")

    return 0 if not violations else 1


@market_meta.command()
@click.argument("symbol")
@click.option("--json", "output_json", is_flag=True, help="JSON output")
def info(symbol: str, output_json: bool):
    """Get instrument info"""

    if not market_meta_api.market_metadata:
        click.echo("Metadata not loaded. Run 'refresh' first", err=True)
        return 1

    info = get_instrument_info(symbol)

    if not info:
        click.echo(f"Instrument {symbol} not found", err=True)
        return 1

    if output_json:
        click.echo(json.dumps(info, indent=2))
    else:
        click.echo(f"Instrument: {symbol}")
        click.echo(f"  Type: {info['inst_type']}")
        click.echo(f"  Base currency: {info['base_ccy']}")
        click.echo(f"  Quote currency: {info['quote_ccy']}")
        click.echo(f"  Tradable: {'yes' if info['is_tradable'] else 'no'}")

        if info["tick_size"]:
            click.echo(f"  Tick size: {info['tick_size']['step']}")

        if info["lot_size"]:
            click.echo(f"  Lot size: {info['lot_size']['step']}")

        if info["contract_val"]:
            click.echo(f"  Contract value: {info['contract_val']}")

        if info["margin_mode"]:
            click.echo(f"  Margin mode: {info['margin_mode']}")

    return 0


@market_meta.command()
def cache():
    """Show metadata cache status"""
    if not market_meta_api.market_metadata:
        click.echo("Metadata not loaded")
        return 1

    status = market_meta_api.get_cache_status()

    click.echo("Metadata cache status:")
    click.echo(f"  Valid: {'yes' if status['is_valid'] else 'no'}")
    click.echo(f"  Last refresh: {status['last_refresh'] or 'never'}")
    click.echo(f"  TTL: {status['ttl_hours']:.1f}h")
    click.echo(f"  Auto-refresh: {'yes' if status['auto_refresh_enabled'] else 'no'}")
    click.echo(f"  Instruments: {status['instruments_count']}")
    return None


@market_meta.command()
@click.option("--hours", type=int, default=1, help="TTL in hours")
def set_ttl(hours: int):
    """Set cache TTL"""
    market_meta_api.set_cache_ttl(hours)
    click.echo(f"TTL set to {hours}h")


@market_meta.command()
def clear_cache():
    """Clear metadata cache"""
    market_meta_api._last_refresh = None
    click.echo("Cache cleared")


@market_meta.command()
@click.option(
    "--enable/--disable", default=True, help="Enable/disable auto-refresh"
)
def auto_refresh(enable: bool):
    """Manage auto-refresh"""
    if enable:
        market_meta_api._auto_refresh_enabled = True
        market_meta_api.start_auto_refresh()
        click.echo("Auto-refresh enabled")
    else:
        market_meta_api.stop_auto_refresh()
        click.echo("Auto-refresh disabled")


@market_meta.command()
@click.option("--drop", is_flag=True, help="Drop tables")
@click.option("--create", is_flag=True, help="Create tables")
def db(drop: bool, create: bool):
    """Manage database"""

    # TODO: get engine from config
    from sqlalchemy import create_engine

    engine = create_engine("postgresql://localhost/market_meta")

    if drop:
        click.echo("Dropping market_meta tables...")
        drop_tables(engine)
        click.echo("Tables dropped")

    if create:
        click.echo("Creating market_meta tables...")
        create_tables(engine)
        click.echo("Tables created")

    if not drop and not create:
        click.echo("Use --create to create or --drop to drop tables")


@market_meta.command()
def status():
    """Show module status"""

    click.echo("market_meta module status:")

    if market_meta_api.market_metadata:
        total = len(market_meta_api.market_metadata.instruments)
        click.echo(f"  Metadata: loaded ({total} instruments)")

        by_type = {}
        for instrument in market_meta_api.market_metadata.instruments.values():
            inst_type = instrument.inst_type.value
            by_type[inst_type] = by_type.get(inst_type, 0) + 1

        for inst_type, count in by_type.items():
            click.echo(f"    {inst_type}: {count}")
    else:
        click.echo("  Metadata: not loaded")

    if market_meta_api.validator:
        click.echo("  Validators: initialized")
    else:
        click.echo("  Validators: not initialized")

    if market_meta_api.risk_limits:
        click.echo("  Risk limits: configured")
    else:
        click.echo("  Risk limits: not configured")


@market_meta.command()
@click.option("--level", default="INFO", help="Log level")
@click.option("--file", help="Log file path")
@click.option("--console/--no-console", default=True, help="Console output")
@click.option("--file-output/--no-file-output", default=True, help="File output")
def setup_logging(level: str, file: str, console: bool, file_output: bool):
    """Configure logging"""

    configure_logging(
        level=level, log_file=file, console_output=console, file_output=file_output
    )

    click.echo("Logging configured:")
    click.echo(f"  Level: {level}")
    click.echo(f"  File: {file or 'market_meta.log'}")
    click.echo(f"  Console: {'yes' if console else 'no'}")
    click.echo(f"  File output: {'yes' if file_output else 'no'}")


@market_meta.command()
def logs():
    """Show recent logs"""

    from pathlib import Path

    log_file = Path("market_meta.log")
    if not log_file.exists():
        click.echo("Log file not found")
        return

    try:
        with open(log_file, encoding="utf-8") as f:
            lines = f.readlines()
            recent_lines = lines[-20:] if len(lines) > 20 else lines

            click.echo("Recent logs:")
            for line in recent_lines:
                click.echo(f"  {line.strip()}")

    except Exception as e:
        click.echo(f"Error reading logs: {e}")


@market_meta.command()
def clear_logs():
    """Clear log files"""

    from pathlib import Path

    log_files = [
        Path("market_meta.log"),
        Path("logs/market_meta.log"),
        Path("logs/market_meta_errors.log"),
    ]

    cleared = 0
    for log_file in log_files:
        if log_file.exists():
            try:
                log_file.unlink()
                click.echo(f"Deleted: {log_file}")
                cleared += 1
            except Exception as e:
                click.echo(f"Error deleting {log_file}: {e}")

    if cleared == 0:
        click.echo("No log files found")
    else:
        click.echo(f"Cleared {cleared} file(s)")


@market_meta.command()
@click.option("--json", "output_json", is_flag=True, help="JSON output")
@click.option("--env", is_flag=True, help="Show environment variables")
def config(output_json: bool, env: bool):
    """Show current configuration"""

    try:
        config = get_config()

        if output_json:
            click.echo(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
        else:
            click.echo("market_meta configuration:")
            click.echo(f"  Environment: {config.environment}")
            click.echo(f"  Debug mode: {'yes' if config.debug_mode else 'no'}")
            click.echo(f"  Data dir: {config.data_dir}")

            click.echo("\nOKX API:")
            click.echo(f"  URL: {config.okx.base_url}")
            click.echo(f"  Timeout: {config.okx.timeout_seconds}s")
            click.echo(f"  Rate limit: {config.okx.max_requests_per_second}/s")
            click.echo(f"  Retries: {config.okx.max_retries}")

            click.echo("\nCaching:")
            click.echo(f"  Metadata TTL: {config.cache.metadata_ttl_hours}h")
            click.echo(
                f"  Auto-refresh: {'yes' if config.cache.auto_refresh_enabled else 'no'}"
            )
            click.echo(f"  Interval: {config.cache.auto_refresh_interval_hours}h")

            click.echo("\nLogging:")
            click.echo(f"  Level: {config.logging.log_level}")
            click.echo(f"  Format: {config.logging.log_format}")
            click.echo(f"  File: {config.logging.log_file or 'market_meta.log'}")
            click.echo(
                f"  Mask API keys: {'yes' if config.logging.mask_api_keys else 'no'}"
            )

            click.echo("\nValidation:")
            click.echo(
                f"  Strict mode: {'yes' if config.validation.strict_mode else 'no'}"
            )
            click.echo(
                f"  Allow warnings: {'yes' if config.validation.allow_warnings else 'no'}"
            )
            click.echo(
                f"  Validate risk limits: {'yes' if config.validation.validate_risk_limits else 'no'}"
            )

            click.echo("\nRisk management:")
            click.echo(
                f"  Max position size: ${config.risk.max_position_size_usd:,.0f}"
            )
            click.echo(
                f"  Max total exposure: ${config.risk.max_total_exposure_usd:,.0f}"
            )
            click.echo(f"  Max leverage: {config.risk.max_leverage}x")
            click.echo(f"  Risk tolerance: {config.risk.risk_tolerance}")

            click.echo("\nMetrics:")
            click.echo(f"  Enabled: {'yes' if config.metrics.enabled else 'no'}")
            click.echo(f"  Export: {'yes' if config.metrics.export_metrics else 'no'}")
            click.echo(f"  Port: {config.metrics.metrics_port}")

        if env:
            click.echo("\nEnvironment variables:")
            env_vars = [
                "MARKET_META_ENVIRONMENT",
                "MARKET_META_DEBUG_MODE",
                "OKX_API_KEY",
                "OKX_BASE_URL",
                "MARKET_META_CACHE_TTL_HOURS",
                "MARKET_META_LOG_LEVEL",
                "MARKET_META_STRICT_VALIDATION",
                "MARKET_META_MAX_POSITION_SIZE_USD",
            ]

            for var in env_vars:
                value = os.environ.get(var, "not set")
                if var in ["OKX_API_KEY"] and value != "not set":
                    value = "***"
                click.echo(f"  {var}: {value}")

    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        return 1


@market_meta.command()
def reload_config_cmd():
    """Reload configuration from environment variables"""

    try:
        config = reload_config()
        click.echo("Configuration reloaded")
        click.echo(f"  Environment: {config.environment}")
        click.echo(f"  Debug mode: {'yes' if config.debug_mode else 'no'}")

    except Exception as e:
        click.echo(f"Error reloading configuration: {e}", err=True)
        return 1


@market_meta.command()
@click.option("--validate", is_flag=True, help="Validate configuration")
def validate_config(validate: bool):
    """Validate configuration"""

    try:
        config = get_config()

        if validate:
            errors = config.validate()
            if errors:
                click.echo("Configuration errors:")
                for error in errors:
                    click.echo(f"  - {error}")
                return 1
            click.echo("Configuration is valid")
        else:
            click.echo("Use --validate to check configuration")

    except Exception as e:
        click.echo(f"Error validating configuration: {e}", err=True)
        return 1


@market_meta.command()
@click.option("--json", "output_json", is_flag=True, help="JSON output")
@click.option("--prometheus", is_flag=True, help="Prometheus format output")
def metrics(output_json: bool, prometheus: bool):
    """Show metrics"""

    try:
        collector = get_metrics_collector()

        if prometheus:
            click.echo(collector.export_metrics("prometheus"))
        elif output_json:
            click.echo(collector.export_metrics("json"))
        else:
            summary = collector.get_metrics_summary()

            click.echo("market_meta metrics:")

            cache_hit = summary.get("cache_hit_ratio", {})
            if cache_hit.get("latest") is not None:
                click.echo(f"  Cache hit ratio: {cache_hit['latest']:.1f}%")

            validation_success = summary.get("validation_success_rate", {})
            if validation_success.get("latest") is not None:
                click.echo(
                    f"  Validation success rate: {validation_success['latest']:.1f}%"
                )

            api_latency = summary.get("api_request_duration", {})
            if api_latency.get("latest") is not None:
                click.echo(f"  API latency: {api_latency['latest']:.3f}s")

            api_success = summary.get("api_success_rate", {})
            if api_success.get("latest") is not None:
                click.echo(f"  API success rate: {api_success['latest']:.1f}%")

            okx_latency = summary.get("okx_request_duration", {})
            if okx_latency.get("latest") is not None:
                click.echo(f"  OKX latency: {okx_latency['latest']:.3f}s")

            okx_retries = summary.get("okx_retry_count", {})
            if okx_retries.get("count_5m", 0) > 0:
                click.echo(f"  OKX retries (5m): {okx_retries['count_5m']}")

            error_rate = summary.get("error_rate", {})
            if error_rate.get("latest") is not None:
                click.echo(f"  Error rate: {error_rate['latest']:.1f}%")

    except Exception as e:
        click.echo(f"Error fetching metrics: {e}", err=True)
        return 1


@market_meta.command()
@click.option("--hours", type=int, default=24, help="Hours to look back")
def alerts(hours: int):
    """Show alerts"""

    try:
        monitor = get_metrics_monitor()
        alerts = monitor.get_alerts(hours=hours)

        if not alerts:
            click.echo(f"No alerts in the last {hours}h")
            return None

        click.echo(f"Alerts in the last {hours}h:")
        for i, alert in enumerate(alerts, 1):
            click.echo(f"  {i}. {alert['type']} - {alert['timestamp']}")
            if "context" in alert:
                for key, value in alert["context"].items():
                    click.echo(f"     {key}: {value}")

    except Exception as e:
        click.echo(f"Error fetching alerts: {e}", err=True)
        return 1


@market_meta.command()
async def start_metrics():
    """Start metrics services"""

    try:
        await start_metrics_services()
        click.echo("Metrics services started")

        config = get_config()
        if config.metrics.export_metrics:
            click.echo(
                f"Metrics available at http://localhost:{config.metrics.metrics_port}/metrics"
            )
            click.echo(
                f"Health check: http://localhost:{config.metrics.metrics_port}/health"
            )

    except Exception as e:
        click.echo(f"Error starting metrics services: {e}", err=True)
        return 1


@market_meta.command()
async def stop_metrics():
    """Stop metrics services"""

    try:
        await stop_metrics_services()
        click.echo("Metrics services stopped")

    except Exception as e:
        click.echo(f"Error stopping metrics services: {e}", err=True)
        return 1


@market_meta.command()
@click.option(
    "--symbols",
    required=True,
    help="Comma-separated symbols (e.g. BTC-USDT-SWAP,ETH-USDT-SWAP)",
)
@click.option(
    "--timeframes",
    default="1m,5m,15m,1H",
    help="Comma-separated timeframes (default: 1m,5m,15m,1H)",
)
@click.option(
    "--start-time",
    default=None,
    help="Period start (ISO format, e.g. 2025-01-01T00:00:00Z)",
)
@click.option(
    "--end-time",
    default=None,
    help="Period end (ISO format, e.g. 2025-01-02T00:00:00Z)",
)
@click.option(
    "--types",
    default="funding,oi,l2",
    help="Data types to load (default: funding,oi,l2)",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def sync_market_data_ext(
    symbols: str,
    timeframes: str,
    start_time: str | None,
    end_time: str | None,
    types: str,
    verbose: bool,
):
    """
    Sync extended market data.

    Loads, normalizes, aggregates and saves data to market_data_ext.
    """
    import asyncio
    from datetime import datetime

    from sqlalchemy import create_engine

    from ..infrastructure.aggregator import MarketDataAggregator
    from ..infrastructure.data_loader import MarketDataLoader
    from ..infrastructure.database import MarketDataExtRepository
    from ..infrastructure.normalizer import MarketDataNormalizer
    from ..infrastructure.ohlcv_aligner import OHLCVAligner

    async def _sync_async():
        try:
            symbol_list = [s.strip() for s in symbols.split(",")]
            timeframe_list = [tf.strip() for tf in timeframes.split(",")]
            type_list = [t.strip() for t in types.split(",")]

            start_dt = None
            end_dt = None
            if start_time:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if end_time:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            if verbose:
                click.echo(f"Symbols: {symbol_list}")
                click.echo(f"Timeframes: {timeframe_list}")
                click.echo(f"Data types: {type_list}")
                if start_dt:
                    click.echo(f"Start: {start_dt}")
                if end_dt:
                    click.echo(f"End: {end_dt}")

            from src.config.settings import get_database_url

            database_url = get_database_url()
            if database_url.startswith("postgresql+asyncpg://"):
                database_url = database_url.replace(
                    "postgresql+asyncpg://", "postgresql://"
                )
            elif database_url.startswith("postgresql+psycopg2://"):
                database_url = database_url.replace(
                    "postgresql+psycopg2://", "postgresql://"
                )
            engine = create_engine(database_url, pool_pre_ping=True)

            aligner = OHLCVAligner(engine)
            loader = MarketDataLoader()
            normalizer = MarketDataNormalizer(aligner)
            aggregator = MarketDataAggregator(aligner)
            repo = MarketDataExtRepository(engine)

            for symbol in symbol_list:
                aligner.load_bar_timestamps(
                    symbol, "1m", start_time=start_dt, end_time=end_dt
                )

            click.echo("Loading data from OKX...")
            all_data = await loader.load_all(symbol_list, start_dt, end_dt)

            total_records = 0

            for data_type in type_list:
                if data_type not in all_data:
                    continue

                records = all_data[data_type]
                if not records:
                    continue

                click.echo(f"Processing {data_type}: {len(records)} records")

                normalized_1m = []
                for symbol in symbol_list:
                    symbol_records = [r for r in records if r.get("symbol") == symbol]
                    if symbol_records:
                        normalized = normalizer.normalize_to_1m_bars(
                            symbol_records, symbol
                        )
                        normalized_1m.extend(normalized)

                if not normalized_1m:
                    continue

                saved_1m = repo.upsert_records(normalized_1m)
                total_records += saved_1m
                click.echo(f"Saved {saved_1m} 1m records for {data_type}")

                import pandas as pd

                df_1m = pd.DataFrame(normalized_1m)
                if not df_1m.empty and "bar_timestamp" in df_1m.columns:
                    for tf in timeframe_list:
                        if tf == "1m":
                            continue

                        click.echo(f"Aggregating {data_type} {tf}...")

                        all_agg_records = []
                        for symbol in symbol_list:
                            df_symbol = df_1m[df_1m["symbol"] == symbol].copy()
                            if df_symbol.empty:
                                continue

                            df_agg = aggregator.aggregate_1m_to_timeframe(
                                df_symbol, symbol, tf, start_dt, end_dt
                            )

                            if not df_agg.empty:
                                agg_records = df_agg.reset_index().to_dict("records")
                                for rec in agg_records:
                                    if "symbol" not in rec:
                                        rec["symbol"] = symbol
                                all_agg_records.extend(agg_records)

                        if all_agg_records:
                            saved_agg = repo.upsert_records(all_agg_records)
                            total_records += saved_agg
                            click.echo(
                                f"Saved {saved_agg} {tf} records for {data_type}"
                            )

            click.echo(f"Total saved: {total_records} records")

        except Exception as e:
            click.echo(f"Error: {e}", err=True)
            if verbose:
                import traceback

                traceback.print_exc()
            return 1

    return asyncio.run(_sync_async())


@market_meta.command("cleanup-market-data-ext")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be deleted without deleting",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def cleanup_market_data_ext(dry_run: bool, verbose: bool):
    """
    Clean up old extended market data per retention policies.

    L2: 7 days, OI: 90 days, Funding: 730 days.
    """

    from sqlalchemy import create_engine

    from ..infrastructure.retention import MarketDataExtRetention

    try:
        from src.config.settings import get_database_url

        database_url = get_database_url()
        if database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
        elif database_url.startswith("postgresql+psycopg2://"):
            database_url = database_url.replace(
                "postgresql+psycopg2://", "postgresql://"
            )
        engine = create_engine(database_url, pool_pre_ping=True)

        retention_service = MarketDataExtRetention(engine)
        deleted_counts = retention_service.cleanup_old_data(dry_run=dry_run)

        if dry_run:
            click.echo(f"Dry run complete. Would delete: {deleted_counts}")
        else:
            click.echo(f"Cleanup complete. Deleted: {deleted_counts}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    market_meta()
