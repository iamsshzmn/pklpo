"""
CLI helpers for local testing and debugging of features module.

This module provides command-line interfaces for testing features calculation,
validation, and database operations locally.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from .calc import compute_and_dump_parquet, validate_parquet_file
from .logging_config import get_features_logger
from .save import save_parquet_to_pg, validate_database_connection
from .validation import check_data_consistency, validate_data_quality

logger = get_features_logger("features.cli")


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def cmd_calculate(args):
    """Calculate indicators and save to parquet."""
    try:
        # Load OHLCV data
        if args.input.endswith(".parquet"):
            df_ohlcv = pd.read_parquet(args.input)
        else:
            df_ohlcv = pd.read_csv(args.input)

        logger.info(f"Loaded {len(df_ohlcv)} rows from {args.input}")

        # Calculate and save
        if args.legacy:
            logger.info("Using legacy (non-streaming) calculation method")
            # Use legacy method - direct calculation without streaming
            from .core import compute_features

            features_df = compute_features(
                df_ohlcv, volatility_normalize=args.volatility_normalize
            )
            features_df.to_parquet(args.output)
            result = {
                "output_path": args.output,
                "result_rows": len(features_df),
                "feature_count": len(
                    [
                        col
                        for col in features_df.columns
                        if col not in ["ts", "open", "high", "low", "close", "volume"]
                    ]
                ),
                "file_size_mb": Path(args.output).stat().st_size / 1024 / 1024,
            }
        else:
            logger.info("Using streaming calculation method")
            result = compute_and_dump_parquet(
                df_ohlcv=df_ohlcv,
                symbol=args.symbol,
                timeframe=args.timeframe,
                output_path=args.output,
                volatility_normalize=args.volatility_normalize,
            )

        print(
            f"✅ Successfully calculated indicators for {args.symbol} {args.timeframe}"
        )
        print(
            f"📊 Result: {result['result_rows']} rows, {result['feature_count']} features"
        )
        print(f"💾 Saved to: {result['output_path']}")
        print(f"📁 File size: {result['file_size_mb']:.2f} MB")

        # Show fill rates
        if "fill_rates" in result:
            print("\n📈 Fill rates:")
            for feature, rate in result["fill_rates"].items():
                print(f"   {feature}: {rate:.1f}%")

        return 0

    except Exception as e:
        logger.error(f"Calculation failed: {e}")
        print(f"❌ Error: {e}")
        return 1


def cmd_save(args):
    """Save parquet file to database."""

    async def _save():
        from src.database import get_async_session

        async for session in get_async_session():
            # Validate connection
            validation = await validate_database_connection(session)
            if not validation["valid"]:
                print(f"❌ Database validation failed: {validation}")
                return 1

            # Save parquet file
            result = await save_parquet_to_pg(
                session=session,
                parquet_path=args.parquet,
                symbol=args.symbol,
                timeframe=args.timeframe,
                batch_size=args.batch_size,
                validate_before_save=args.validate,
            )

            if result["success"]:
                print(f"✅ Successfully saved {args.symbol} {args.timeframe}")
                print(f"📊 Rows processed: {result['rows_processed']}")
                print(f"💾 Rows saved: {result['rows_saved']}")
                print(f"📁 Batches: {result['batches_processed']}")
                return 0
            print(f"❌ Failed to save: {result['error']}")
            return 1
        return None

    try:
        return asyncio.run(_save())
    except Exception as e:
        logger.error(f"Save failed: {e}")
        print(f"❌ Error: {e}")
        return 1


def cmd_validate(args):
    """Validate data quality."""
    try:
        # Load data
        if args.input.endswith(".parquet"):
            df = pd.read_parquet(args.input)
        else:
            df = pd.read_csv(args.input)

        logger.info(f"Loaded {len(df)} rows from {args.input}")

        # Validate data
        is_valid, result = validate_data_quality(df, args.data_type, args.strict)

        print(f"Validation result: {'✅ VALID' if is_valid else '❌ INVALID'}")
        print(f"Errors: {len(result['errors'])}")
        print(f"Warnings: {len(result['warnings'])}")

        if result["errors"]:
            print("\n❌ Errors:")
            for error in result["errors"]:
                print(f"   - {error}")

        if result["warnings"]:
            print("\n⚠️  Warnings:")
            for warning in result["warnings"]:
                print(f"   - {warning}")

        # Show statistics
        if "stats" in result:
            stats = result["stats"]
            print("\n📊 Statistics:")
            print(f"   Rows: {stats.get('row_count', 'N/A')}")
            print(f"   Columns: {stats.get('column_count', 'N/A')}")
            if "feature_count" in stats:
                print(f"   Features: {stats['feature_count']}")

        # Consistency check
        consistency = check_data_consistency(df)
        print(f"\n🔍 Quality score: {consistency['quality_score']:.2f}")

        if consistency["issues"]:
            print("Issues found:")
            for issue in consistency["issues"]:
                print(f"   - {issue}")

        return 0 if is_valid else 1

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"❌ Error: {e}")
        return 1


def cmd_test_parquet(args):
    """Test parquet file."""
    try:
        validation = validate_parquet_file(args.parquet)

        if validation.get("validation_failed", False):
            print(
                f"❌ Parquet file validation failed: {validation.get('error', 'Unknown error')}"
            )
            return 1

        print("✅ Parquet file is valid")
        print(f"📊 Rows: {validation['rows']}")
        print(f"📁 File size: {validation['file_size_mb']:.2f} MB")
        print(f"🔧 Columns: {len(validation['columns'])}")

        if validation["has_metadata"]:
            print(f"📋 Metadata: {validation['metadata']}")

        if validation["has_data"]:
            print(f"📈 Features: {validation['feature_count']}")

            # Show null rates for first few features
            if "null_rates" in validation:
                print("\n📊 Null rates (first 5 features):")
                for i, (feature, rate) in enumerate(validation["null_rates"].items()):
                    if i >= 5:
                        break
                    print(f"   {feature}: {rate:.1f}%")

        return 0

    except Exception as e:
        logger.error(f"Parquet test failed: {e}")
        print(f"❌ Error: {e}")
        return 1


def cmd_test_database(args):
    """Test database connection and structure."""

    async def _test():
        from src.database import get_async_session

        async for session in get_async_session():
            validation = await validate_database_connection(session)

            if validation["valid"]:
                print("✅ Database connection successful")
                print(f"📊 Table exists: {validation['table_exists']}")
                print(f"🔧 Columns: {len(validation['columns'])}")

                if validation["columns"]:
                    print("\n📋 Table structure:")
                    for col in validation["columns"][:10]:  # Show first 10 columns
                        print(f"   {col['name']}: {col['type']}")
                    if len(validation["columns"]) > 10:
                        print(f"   ... and {len(validation['columns']) - 10} more")

                return 0
            print(f"❌ Database validation failed: {validation}")
            return 1
        return None

    try:
        return asyncio.run(_test())
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        print(f"❌ Error: {e}")
        return 1


def cmd_full_pipeline(args):
    """Run full pipeline: calculate -> validate -> save."""
    try:
        print("🚀 Starting full pipeline...")

        # Step 1: Calculate
        print("\n📊 Step 1: Calculating indicators...")
        calc_result = cmd_calculate(args)
        if calc_result != 0:
            return calc_result

        # Step 2: Validate parquet
        print("\n🔍 Step 2: Validating parquet file...")
        parquet_args = argparse.Namespace(parquet=args.output)
        parquet_result = cmd_test_parquet(parquet_args)
        if parquet_result != 0:
            return parquet_result

        # Step 3: Save to database
        print("\n💾 Step 3: Saving to database...")
        save_args = argparse.Namespace(
            parquet=args.output,
            symbol=args.symbol,
            timeframe=args.timeframe,
            batch_size=getattr(args, "batch_size", 1000),
            validate=getattr(args, "validate", True),
        )
        save_result = cmd_save(save_args)
        if save_result != 0:
            return save_result

        print("\n✅ Full pipeline completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Full pipeline failed: {e}")
        print(f"❌ Error: {e}")
        return 1


def cmd_snapshots_list(args):
    """List calculation snapshots (FEAT-001)."""

    async def _list_snapshots():
        from src.database import get_async_session

        from .versioning import snapshot_manager

        async for session in get_async_session():
            snapshots = await snapshot_manager.list_snapshots(
                session,
                limit=args.limit,
                status=args.status,
                algorithm_version=args.version,
            )

            if not snapshots:
                print("No snapshots found")
                return 0

            print(f"\n📸 Found {len(snapshots)} snapshot(s):\n")
            print(
                f"{'ID':<25} {'Created':<20} {'Status':<12} {'Version':<12} {'Rows':<10}"
            )
            print("=" * 85)

            for s in snapshots:
                created = s["created_at"][:19]  # Trim timestamp
                print(
                    f"{s['snapshot_id']:<25} {created:<20} {s['status']:<12} {s['algorithm_version']:<12} {s['rows_calculated']:<10}"
                )

            print()
            return 0
        return None

    return asyncio.run(_list_snapshots())


def cmd_snapshots_show(args):
    """Show snapshot details (FEAT-001)."""

    async def _show_snapshot():
        import json

        from src.database import get_async_session

        from .versioning import snapshot_manager

        async for session in get_async_session():
            snapshot = await snapshot_manager.get_snapshot(session, args.snapshot_id)

            if not snapshot:
                print(f"❌ Snapshot not found: {args.snapshot_id}")
                return 1

            print(f"\n📸 Snapshot: {snapshot['snapshot_id']}\n")
            print(f"Status: {snapshot['status']}")
            print(f"Created: {snapshot['created_at']}")
            print(f"Completed: {snapshot['completed_at'] or 'N/A'}")
            print(f"Algorithm Version: {snapshot['algorithm_version']}")
            print(f"Module Version: {snapshot['module_version']}")
            print(f"Rows Calculated: {snapshot['rows_calculated']:,}")
            if snapshot["execution_duration_seconds"]:
                print(f"Duration: {snapshot['execution_duration_seconds']:.2f}s")

            print(
                f"\nSymbols ({len(snapshot['symbols'])}): {', '.join(snapshot['symbols'][:5])}"
            )
            if len(snapshot["symbols"]) > 5:
                print(f"  ... and {len(snapshot['symbols']) - 5} more")

            print(
                f"\nTimeframes ({len(snapshot['timeframes'])}): {', '.join(snapshot['timeframes'])}"
            )

            if snapshot.get("error_message"):
                print(f"\n❌ Error: {snapshot['error_message']}")

            if args.show_config and snapshot["config"]:
                print("\n📝 Configuration:")
                config = snapshot["config"]
                print(json.dumps(config, indent=2))

            print()
            return 0
        return None

    return asyncio.run(_show_snapshot())


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Features module CLI tools")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Calculate command
    calc_parser = subparsers.add_parser(
        "calculate", help="Calculate indicators and save to parquet"
    )
    calc_parser.add_argument("input", help="Input CSV or parquet file")
    calc_parser.add_argument("output", help="Output parquet file path")
    calc_parser.add_argument("--symbol", required=True, help="Trading symbol")
    calc_parser.add_argument("--timeframe", required=True, help="Timeframe")
    calc_parser.add_argument(
        "--volatility-normalize",
        action="store_true",
        help="Apply volatility normalization",
    )
    calc_parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy (non-streaming) calculation method",
    )
    calc_parser.set_defaults(func=cmd_calculate)

    # Save command
    save_parser = subparsers.add_parser("save", help="Save parquet file to database")
    save_parser.add_argument("parquet", help="Parquet file path")
    save_parser.add_argument("--symbol", required=True, help="Trading symbol")
    save_parser.add_argument("--timeframe", required=True, help="Timeframe")
    save_parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for database operations",
    )
    save_parser.add_argument(
        "--validate", action="store_true", help="Validate data before saving"
    )
    save_parser.set_defaults(func=cmd_save)

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate data quality")
    val_parser.add_argument("input", help="Input CSV or parquet file")
    val_parser.add_argument(
        "--data-type",
        choices=["ohlcv", "features"],
        default="ohlcv",
        help="Type of data to validate",
    )
    val_parser.add_argument(
        "--strict", action="store_true", help="Use strict validation"
    )
    val_parser.set_defaults(func=cmd_validate)

    # Test parquet command
    test_parquet_parser = subparsers.add_parser(
        "test-parquet", help="Test parquet file"
    )
    test_parquet_parser.add_argument("parquet", help="Parquet file path")
    test_parquet_parser.set_defaults(func=cmd_test_parquet)

    # Test database command
    test_db_parser = subparsers.add_parser(
        "test-database", help="Test database connection"
    )
    test_db_parser.set_defaults(func=cmd_test_database)

    # Full pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run full pipeline")
    pipeline_parser.add_argument("input", help="Input CSV or parquet file")
    pipeline_parser.add_argument("output", help="Output parquet file path")
    pipeline_parser.add_argument("--symbol", required=True, help="Trading symbol")
    pipeline_parser.add_argument("--timeframe", required=True, help="Timeframe")
    pipeline_parser.add_argument(
        "--volatility-normalize",
        action="store_true",
        help="Apply volatility normalization",
    )
    pipeline_parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for database operations",
    )
    pipeline_parser.add_argument(
        "--validate", action="store_true", help="Validate data before saving"
    )
    pipeline_parser.set_defaults(func=cmd_full_pipeline)

    # Snapshots list command (FEAT-001)
    snapshots_list_parser = subparsers.add_parser(
        "snapshots-list", help="List calculation snapshots"
    )
    snapshots_list_parser.add_argument(
        "--limit", type=int, default=50, help="Maximum number of snapshots to show"
    )
    snapshots_list_parser.add_argument(
        "--status",
        choices=["in_progress", "completed", "failed", "cancelled"],
        help="Filter by status",
    )
    snapshots_list_parser.add_argument("--version", help="Filter by algorithm version")
    snapshots_list_parser.set_defaults(func=cmd_snapshots_list)

    # Snapshots show command (FEAT-001)
    snapshots_show_parser = subparsers.add_parser(
        "snapshots-show", help="Show snapshot details"
    )
    snapshots_show_parser.add_argument("snapshot_id", help="Snapshot ID")
    snapshots_show_parser.add_argument(
        "--show-config", action="store_true", help="Show configuration details"
    )
    snapshots_show_parser.set_defaults(func=cmd_snapshots_show)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Setup logging
    setup_logging(args.verbose)

    # Execute command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
