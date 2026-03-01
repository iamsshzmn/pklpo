#!/usr/bin/env python3
"""
CLI command for schema validation and checking.

Usage:
    python -m src.features.cli.schema_check
    python -m src.features.cli.schema_check --check-database
    python -m src.features.cli.schema_check --verbose
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Use absolute imports for CLI script compatibility
from src.features.schema.schema_manager import (
    SchemaManager,  # type: ignore[import-untyped]
)
from src.utils.session_utils import get_db_session  # type: ignore[import-untyped]


def check_schema_file() -> dict[str, Any]:
    """
    Check that schema file exists and is valid.

    Returns:
        Dictionary with check results
    """
    results = {"checks": [], "errors": [], "warnings": [], "passed": 0, "failed": 0}

    # Check 1: File exists
    schema_path = Path("src/features/schema/indicators_schema.yml")
    if schema_path.exists():
        results["checks"].append(("Schema file exists", "PASS"))
        results["passed"] += 1
    else:
        results["checks"].append(("Schema file exists", "FAIL"))
        results["errors"].append(f"Schema file not found: {schema_path}")
        results["failed"] += 1
        return results

    # Check 2: Schema loads
    try:
        schema_manager = SchemaManager()
        results["checks"].append(("Schema loads successfully", "PASS"))
        results["passed"] += 1
    except Exception as e:
        results["checks"].append(("Schema loads successfully", "FAIL"))
        results["errors"].append(f"Failed to load schema: {e}")
        results["failed"] += 1
        return results

    # Check 3: Version present
    if "version" in schema_manager.schema:
        version = schema_manager.schema["version"]
        results["checks"].append((f"Schema version present ({version})", "PASS"))
        results["passed"] += 1
    else:
        results["checks"].append(("Schema version present", "FAIL"))
        results["errors"].append("Schema missing version field")
        results["failed"] += 1

    # Check 4: Primary keys defined
    primary_keys = schema_manager.schema.get("primary_keys", [])
    if len(primary_keys) >= 3:  # symbol, timeframe, timestamp
        results["checks"].append(
            (f"Primary keys defined ({len(primary_keys)})", "PASS")
        )
        results["passed"] += 1
    else:
        results["checks"].append(("Primary keys defined", "FAIL"))
        results["errors"].append(
            f"Expected at least 3 primary keys, found {len(primary_keys)}"
        )
        results["failed"] += 1

    # Check 5: Indicators defined
    all_columns = schema_manager.get_all_columns()
    if len(all_columns) > 20:  # Should have many indicators
        results["checks"].append(
            (f"Indicators defined ({len(all_columns)} columns)", "PASS")
        )
        results["passed"] += 1
    else:
        results["checks"].append(("Indicators defined", "WARN"))
        results["warnings"].append(
            f"Only {len(all_columns)} columns defined, expected more"
        )

    # Check 6: No duplicate field names
    field_names = []
    for pk in schema_manager.schema.get("primary_keys", []):
        field_names.append(pk["name"])
    for field in schema_manager.schema.get("service_fields", []):
        field_names.append(field["name"])
    for _category, indicators in schema_manager.schema.get("indicators", {}).items():
        for indicator in indicators:
            field_names.append(indicator["name"])

    duplicates = [name for name in field_names if field_names.count(name) > 1]
    if len(duplicates) == 0:
        results["checks"].append(("No duplicate field names", "PASS"))
        results["passed"] += 1
    else:
        results["checks"].append(("No duplicate field names", "FAIL"))
        results["errors"].append(f"Found duplicate field names: {set(duplicates)}")
        results["failed"] += 1

    # Check 7: Aliases valid
    aliases = schema_manager.get_aliases()
    invalid_targets = []
    for alias, target in aliases.items():
        if target not in all_columns:
            invalid_targets.append((alias, target))

    if len(invalid_targets) == 0:
        results["checks"].append(
            (f"All aliases valid ({len(aliases)} aliases)", "PASS")
        )
        results["passed"] += 1
    else:
        results["checks"].append(("All aliases valid", "FAIL"))
        results["errors"].append(f"Invalid alias targets: {invalid_targets}")
        results["failed"] += 1

    # Check 8: Common indicators present
    common_indicators = [
        "ema_21",
        "sma_20",
        "sma_200",
        "rsi_14",
        "macd",
        "atr_14",
        "bb_upper",
        "bb_lower",
        "hlc3",
        "hl2",
    ]
    missing = [ind for ind in common_indicators if ind not in all_columns]

    if len(missing) == 0:
        results["checks"].append(("Common indicators present", "PASS"))
        results["passed"] += 1
    elif len(missing) <= 2:
        results["checks"].append(("Common indicators present", "WARN"))
        results["warnings"].append(f"Missing some common indicators: {missing}")
    else:
        results["checks"].append(("Common indicators present", "FAIL"))
        results["errors"].append(f"Missing many common indicators: {missing}")
        results["failed"] += 1

    return results


async def check_database_schema() -> dict[str, Any]:
    """
    Check database schema against schema file.

    Returns:
        Dictionary with check results
    """
    results = {"checks": [], "errors": [], "warnings": [], "passed": 0, "failed": 0}

    try:
        schema_manager = SchemaManager()

        async with get_db_session() as session:
            # Get DB columns
            db_columns = await schema_manager._get_db_columns(session)
            schema_columns = schema_manager.get_all_columns()

            # Check 1: Database accessible
            results["checks"].append(("Database accessible", "PASS"))
            results["passed"] += 1

            # Check 2: indicators table exists
            if len(db_columns) > 0:
                results["checks"].append(("indicators table exists", "PASS"))
                results["passed"] += 1
            else:
                results["checks"].append(("indicators table exists", "FAIL"))
                results["errors"].append("indicators table not found or has no columns")
                results["failed"] += 1
                return results

            # Check 3: Schema columns in database
            missing_in_db = schema_columns - db_columns
            if len(missing_in_db) == 0:
                results["checks"].append(("All schema columns in DB", "PASS"))
                results["passed"] += 1
            else:
                results["checks"].append(("All schema columns in DB", "WARN"))
                results["warnings"].append(
                    f"{len(missing_in_db)} columns missing in DB: {list(missing_in_db)[:10]}"
                )

            # Check 4: Extra columns in database
            extra_in_db = db_columns - schema_columns
            if len(extra_in_db) == 0:
                results["checks"].append(("No extra columns in DB", "PASS"))
                results["passed"] += 1
            else:
                results["checks"].append(("No extra columns in DB", "WARN"))
                results["warnings"].append(
                    f"{len(extra_in_db)} extra columns in DB: {list(extra_in_db)[:10]}"
                )

            # Check 5: Primary key columns exist
            required_pk = {"symbol", "timeframe", "timestamp"}
            missing_pk = required_pk - db_columns
            if len(missing_pk) == 0:
                results["checks"].append(("Primary key columns exist", "PASS"))
                results["passed"] += 1
            else:
                results["checks"].append(("Primary key columns exist", "FAIL"))
                results["errors"].append(f"Missing primary key columns: {missing_pk}")
                results["failed"] += 1

    except Exception as e:
        results["checks"].append(("Database check", "FAIL"))
        results["errors"].append(f"Database check failed: {e}")
        results["failed"] += 1

    return results


def print_results(results: dict[str, Any], verbose: bool = False):
    """
    Print check results in a nice format.

    Args:
        results: Results dictionary from checks
        verbose: Whether to show all details
    """
    print("\n" + "=" * 70)
    print("  SCHEMA VALIDATION RESULTS")
    print("=" * 70 + "\n")

    # Print checks
    for check, status in results["checks"]:
        if status == "PASS":
            icon = "✅"
        elif status == "FAIL":
            icon = "❌"
        else:
            icon = "⚠️ "
        print(f"{icon} {check:.<55} {status}")

    print("\n" + "-" * 70)
    print(
        f"Summary: {results['passed']} passed, {results['failed']} failed, {len(results['warnings'])} warnings"
    )
    print("-" * 70 + "\n")

    # Print errors
    if results["errors"]:
        print("❌ ERRORS:")
        for error in results["errors"]:
            print(f"  • {error}")
        print()

    # Print warnings
    if results["warnings"] and verbose:
        print("⚠️  WARNINGS:")
        for warning in results["warnings"]:
            print(f"  • {warning}")
        print()


async def async_main():
    """Async main function."""
    parser = argparse.ArgumentParser(
        description="Validate schema configuration and database"
    )
    parser.add_argument(
        "--check-database", action="store_true", help="Also check database schema"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output including warnings",
    )

    args = parser.parse_args()

    # Run schema file checks
    print("Checking schema file...")
    file_results = check_schema_file()
    print_results(file_results, args.verbose)

    # Run database checks if requested
    if args.check_database:
        print("\nChecking database schema...")
        db_results = await check_database_schema()
        print_results(db_results, args.verbose)

        # Combine results
        file_results["passed"] + db_results["passed"]
        total_failed = file_results["failed"] + db_results["failed"]
    else:
        file_results["passed"]
        total_failed = file_results["failed"]

    # Exit with appropriate code
    if total_failed > 0:
        print("\n❌ Schema validation FAILED")
        sys.exit(1)
    else:
        print("\n✅ Schema validation PASSED")
        sys.exit(0)


def main():
    """Synchronous entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
