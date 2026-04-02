#!/usr/bin/env python3
"""
CLI command for database setup verification.
Checks indexes, schemas, and access permissions.
"""

import asyncio
import sys
from pathlib import Path

# Add project path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sqlalchemy import text

from src.database import get_async_session
from src.features.storage_contract import IndicatorStorageContract
from src.logging import get_logger

logger = get_logger(__name__)


async def check_unique_index():
    """Check for correct unique index."""
    print("🔍 Checking unique index...")

    try:
        async for session in get_async_session():
            # Check indexes
            index_query = text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = :table_name
                AND indexdef LIKE '%UNIQUE%'
                ORDER BY indexname
            """
            )
            result = await session.execute(
                index_query,
                {"table_name": IndicatorStorageContract.table_name},
            )
            indexes = result.fetchall()

            print(f"Found {len(indexes)} unique indexes:")
            for name, definition in indexes:
                print(f"  📋 {name}: {definition}")

            # Check for correct index
            has_correct_index = any(
                "symbol" in idx[1] and "timeframe" in idx[1] and "timestamp" in idx[1]
                for idx in indexes
            )

            if has_correct_index:
                print("✅ Correct unique index found")
                return True
            print("❌ No unique index on (symbol, timeframe, timestamp)")
            print("💡 Creating unique index...")

            # Create unique index
            create_index_sql = text(
                f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_indicators_unique
                    ON {IndicatorStorageContract.table_name} (symbol, timeframe, timestamp)
                """

            )
            await session.execute(create_index_sql)
            await session.commit()

            print("✅ Unique index created")
            return True

    except Exception as e:
        print(f"❌ Failed to check/create unique index: {e}")
        return False


async def check_table_schema():
    """Check table schema."""
    print("\n🔍 Checking table schema...")

    try:
        async for session in get_async_session():
            # Check table schema
            schema_query = text(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = :table_name
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """
            )
            result = await session.execute(
                schema_query, {"table_name": IndicatorStorageContract.table_name}
            )
            columns = result.fetchall()

            print(f"Table has {len(columns)} columns:")
            for col_name, data_type, nullable, _default in columns[:10]:
                print(
                    f"  📋 {col_name}: {data_type} {'NULL' if nullable == 'YES' else 'NOT NULL'}"
                )

            if len(columns) > 10:
                print(f"  ... and {len(columns) - 10} more columns")

            # Check critical fields
            critical_fields = ["symbol", "timeframe", "timestamp"]
            col_names = [col[0] for col in columns]

            missing_critical = [
                field for field in critical_fields if field not in col_names
            ]
            if missing_critical:
                print(f"❌ Missing critical fields: {missing_critical}")
                return False
            print("✅ All critical fields present")
            return True

    except Exception as e:
        print(f"❌ Failed to check table schema: {e}")
        return False


async def check_permissions():
    """Check access permissions."""
    print("\n🔍 Checking permissions...")

    try:
        async for session in get_async_session():
            # Check table privileges
            perm_query = text(
                """
                SELECT privilege_type
                FROM information_schema.table_privileges
                WHERE table_name = :table_name
                AND table_schema = 'public'
                AND grantee = current_user
            """
            )
            result = await session.execute(
                perm_query, {"table_name": IndicatorStorageContract.table_name}
            )
            privileges = [row[0] for row in result.fetchall()]

            print(f"User privileges: {privileges}")

            required_privileges = ["INSERT", "UPDATE", "SELECT"]
            missing_privileges = [
                priv for priv in required_privileges if priv not in privileges
            ]

            if missing_privileges:
                print(f"❌ Missing privileges: {missing_privileges}")
                return False
            print("✅ All required privileges present")
            return True

    except Exception as e:
        print(f"❌ Failed to check permissions: {e}")
        return False


async def test_upsert():
    """Test UPSERT with sample data."""
    print("\n🧪 Testing UPSERT with sample data...")

    try:
        async for session in get_async_session():
            # Check current record count
            count_query = text(
                f"SELECT COUNT(*) FROM public.{IndicatorStorageContract.table_name}"
            )
            result = await session.execute(count_query)
            count_before = result.scalar()
            print(f"Records before test: {count_before}")

            # Insert test record
            test_insert = text(
                f"""
                INSERT INTO public.{IndicatorStorageContract.table_name} (symbol, timeframe, timestamp, calculated_at, rsi_14)
                VALUES ('TEST-SYMBOL', '1m', 1761044280000, NOW(), 65.5)
                    ON CONFLICT (symbol, timeframe, timestamp)
                DO UPDATE SET rsi_14 = EXCLUDED.rsi_14, calculated_at = EXCLUDED.calculated_at
            """

            )

            await session.execute(test_insert)
            await session.commit()

            # Check record count after
            result = await session.execute(count_query)
            count_after = result.scalar()
            print(f"Records after test: {count_after}")

            if count_after > count_before:
                print("✅ UPSERT test successful")

                # Clean up test record
                cleanup = text(
                    f"DELETE FROM public.{IndicatorStorageContract.table_name} WHERE symbol = 'TEST-SYMBOL'"
                )
                await session.execute(cleanup)
                await session.commit()
                print("🧹 Test data cleaned up")

                return True
            print("❌ UPSERT test failed - no records added")
            return False

    except Exception as e:
        print(f"❌ UPSERT test failed: {e}")
        return False


async def main():
    """Main database check function."""
    print("🚀 Starting database setup check...")

    checks = [
        ("Unique Index", check_unique_index),
        ("Table Schema", check_table_schema),
        ("Permissions", check_permissions),
        ("UPSERT Test", test_upsert),
    ]

    results = []
    for name, check_func in checks:
        try:
            result = await check_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} check failed: {e}")
            results.append((name, False))

    # Summary
    print("\n📊 Check Results:")
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All database checks passed!")
        return 0
    print("\n❌ Some database checks failed!")
    return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
