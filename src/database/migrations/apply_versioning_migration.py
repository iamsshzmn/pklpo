#!/usr/bin/env python3
"""
Apply versioning migration for FEAT-001.

This script applies the database migration to add versioning support
for ML reproducibility.

Usage:
    python apply_versioning_migration.py [--dry-run]
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from src.database import get_async_session

MIGRATION_SQL_PATH = Path(__file__).parent / "add_versioning.sql"


async def check_migration_status(session) -> dict:
    """Check if migration has already been applied."""
    checks = {}

    # Check if algorithm_version column exists in indicators
    result = await session.execute(
        text(
            """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'indicators'
        AND column_name = 'algorithm_version'
    """
        )
    )
    checks["indicators_algorithm_version"] = result.scalar() is not None

    # Check if calculation_metadata table exists
    result = await session.execute(
        text(
            """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'calculation_metadata'
    """
        )
    )
    checks["calculation_metadata_table"] = result.scalar() is not None

    # Check if view exists
    result = await session.execute(
        text(
            """
        SELECT table_name
        FROM information_schema.views
        WHERE table_name = 'v_calculation_summary'
    """
        )
    )
    checks["v_calculation_summary_view"] = result.scalar() is not None

    return checks


async def apply_migration(session, dry_run: bool = False):
    """Apply the migration."""
    print("=" * 80)
    print("FEAT-001: Versioning Migration")
    print("=" * 80)
    print()

    # Check current status
    print("📋 Checking current database status...")
    status = await check_migration_status(session)

    print(
        f"  - indicators.algorithm_version: {'✅ Exists' if status['indicators_algorithm_version'] else '❌ Missing'}"
    )
    print(
        f"  - calculation_metadata table: {'✅ Exists' if status['calculation_metadata_table'] else '❌ Missing'}"
    )
    print(
        f"  - v_calculation_summary view: {'✅ Exists' if status['v_calculation_summary_view'] else '❌ Missing'}"
    )
    print()

    # Check if migration is needed
    all_exist = all(status.values())
    if all_exist:
        print("✅ Migration already applied! Nothing to do.")
        return True

    # Check if partial migration
    any_exist = any(status.values())
    if any_exist:
        print("⚠️  WARNING: Partial migration detected!")
        print("   Some components exist, but not all.")
        print("   This may indicate a failed previous migration.")
        print()

        if not dry_run:
            response = input("   Continue with migration? (yes/no): ")
            if response.lower() != "yes":
                print("❌ Migration cancelled by user")
                return False

    # Load SQL
    print(f"📖 Reading migration SQL from {MIGRATION_SQL_PATH}...")
    if not MIGRATION_SQL_PATH.exists():
        print(f"❌ Error: Migration file not found: {MIGRATION_SQL_PATH}")
        return False

    with open(MIGRATION_SQL_PATH, encoding="utf-8") as f:
        migration_sql = f.read()

    print(f"   Loaded {len(migration_sql)} characters")
    print()

    if dry_run:
        print("🔍 DRY RUN MODE - Changes will NOT be committed")
        print()
        print("=" * 80)
        print("SQL to be executed:")
        print("=" * 80)
        print(migration_sql)
        print("=" * 80)
        print()
        print("✅ Dry run complete. Run without --dry-run to apply changes.")
        return True

    # Apply migration
    print("🚀 Applying migration...")
    try:
        # Split by semicolons and execute each statement
        statements = [
            s.strip()
            for s in migration_sql.split(";")
            if s.strip() and not s.strip().startswith("--")
        ]

        for i, statement in enumerate(statements, 1):
            # Skip comments
            if statement.startswith("--") or not statement:
                continue

            print(f"   Executing statement {i}/{len(statements)}...")
            await session.execute(text(statement))

        await session.commit()
        print()
        print("✅ Migration applied successfully!")
        print()

        # Verify
        print("🔍 Verifying migration...")
        status_after = await check_migration_status(session)

        if all(status_after.values()):
            print("✅ Verification passed! All components created.")

            # Show summary
            print()
            print("📊 Migration Summary:")
            print("  - Added columns to 'indicators' table")
            print("  - Created 'calculation_metadata' table")
            print("  - Created 'v_calculation_summary' view")
            print("  - Created indexes for performance")
            print()
            print("🎉 FEAT-001 migration complete!")

            return True
        print("❌ Verification failed! Some components missing:")
        for key, value in status_after.items():
            if not value:
                print(f"  - {key}: MISSING")
        return False

    except Exception as e:
        print()
        print(f"❌ Migration failed: {e}")
        print()
        await session.rollback()
        return False


async def rollback_migration(session, dry_run: bool = False):
    """Rollback the migration (for testing)."""
    print("=" * 80)
    print("FEAT-001: Versioning Migration Rollback")
    print("=" * 80)
    print()

    rollback_sql = """
    -- Rollback migration
    ALTER TABLE indicators DROP COLUMN IF EXISTS algorithm_version;
    ALTER TABLE indicators DROP COLUMN IF EXISTS snapshot_id;
    ALTER TABLE indicators DROP COLUMN IF EXISTS calculation_config;
    DROP VIEW IF EXISTS v_calculation_summary;
    DROP TABLE IF EXISTS calculation_metadata;
    """

    if dry_run:
        print("🔍 DRY RUN MODE - Changes will NOT be committed")
        print()
        print("SQL to be executed:")
        print(rollback_sql)
        print()
        return True

    print("⚠️  WARNING: This will remove all versioning data!")
    response = input("Are you sure you want to rollback? (yes/no): ")

    if response.lower() != "yes":
        print("❌ Rollback cancelled")
        return False

    try:
        await session.execute(text(rollback_sql))
        await session.commit()
        print("✅ Rollback complete")
        return True
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        await session.rollback()
        return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Apply FEAT-001 versioning migration")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without applying changes",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration (removes versioning)",
    )
    parser.add_argument(
        "--status", action="store_true", help="Check migration status only"
    )

    args = parser.parse_args()

    try:
        async for session in get_async_session():
            if args.status:
                # Just show status
                status = await check_migration_status(session)
                print("Migration Status:")
                for key, value in status.items():
                    status_icon = "✅" if value else "❌"
                    print(f"  {status_icon} {key}")
                return 0

            if args.rollback:
                # Rollback migration
                success = await rollback_migration(session, args.dry_run)
                return 0 if success else 1

            # Apply migration
            success = await apply_migration(session, args.dry_run)
            return 0 if success else 1

    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
