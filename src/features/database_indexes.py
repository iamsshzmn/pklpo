"""
Database index management for features module.

This module provides utilities for creating and managing database indexes
to optimize performance for features calculation and querying.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .logging_config import get_features_logger

logger = get_features_logger("features.database_indexes")


class FeaturesIndexManager:
    """
    Manages database indexes for features module.
    """

    def __init__(self):
        self.logger = get_features_logger("features.database_indexes")

    async def create_core_indexes(self, session: AsyncSession) -> list[str]:
        """
        Create core indexes for features table.

        Args:
            session: Database session

        Returns:
            List of created index names
        """
        created_indexes = []

        # Core unique constraint
        unique_constraint_sql = """
        ALTER TABLE indicators
        ADD CONSTRAINT IF NOT EXISTS indicators_unique_symbol_timeframe_timestamp
        UNIQUE (symbol, timeframe, timestamp)
        """

        try:
            await session.execute(text(unique_constraint_sql))
            await session.commit()
            created_indexes.append("indicators_unique_symbol_timeframe_timestamp")
            self.logger.info(
                "Created unique constraint for (symbol, timeframe, timestamp)"
            )
        except Exception as e:
            self.logger.warning(f"Failed to create unique constraint: {e}")

        # Performance indexes
        performance_indexes = [
            {
                "name": "idx_indicators_calculated_at",
                "sql": "CREATE INDEX IF NOT EXISTS idx_indicators_calculated_at ON indicators (calculated_at)",
                "description": "Index for time-based queries",
            },
            {
                "name": "idx_indicators_symbol_timeframe",
                "sql": "CREATE INDEX IF NOT EXISTS idx_indicators_symbol_timeframe ON indicators (symbol, timeframe)",
                "description": "Index for symbol-timeframe queries",
            },
            {
                "name": "idx_indicators_symbol_calculated_at",
                "sql": "CREATE INDEX IF NOT EXISTS idx_indicators_symbol_calculated_at ON indicators (symbol, calculated_at)",
                "description": "Index for symbol-time queries",
            },
        ]

        for index_info in performance_indexes:
            try:
                await session.execute(text(index_info["sql"]))
                await session.commit()
                created_indexes.append(index_info["name"])
                self.logger.info(
                    f"Created index: {index_info['name']} - {index_info['description']}"
                )
            except Exception as e:
                self.logger.warning(f"Failed to create index {index_info['name']}: {e}")

        return created_indexes

    async def create_feature_specific_indexes(
        self, session: AsyncSession, feature_columns: list[str]
    ) -> list[str]:
        """
        Create indexes for specific feature columns.

        Args:
            session: Database session
            feature_columns: List of feature column names

        Returns:
            List of created index names
        """
        created_indexes = []

        # Create indexes for key features
        key_features = [
            "ema_8",
            "sma_20",
            "rsi_14",
            "atr_14",
            "macd",
            "obv",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "adx",
            "stoch_k",
            "stoch_d",
        ]

        for feature in key_features:
            if feature in feature_columns:
                index_name = f"idx_indicators_{feature}"
                index_sql = f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON indicators ({feature})
                WHERE {feature} IS NOT NULL
                """

                try:
                    await session.execute(text(index_sql))
                    await session.commit()
                    created_indexes.append(index_name)
                    self.logger.info(f"Created feature index: {index_name}")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to create feature index {index_name}: {e}"
                    )

        return created_indexes

    async def create_covering_indexes(self, session: AsyncSession) -> list[str]:
        """
        Create covering indexes for common query patterns.

        Args:
            session: Database session

        Returns:
            List of created index names
        """
        created_indexes = []

        # Covering index for common queries
        covering_indexes = [
            {
                "name": "idx_indicators_covering_recent",
                "sql": """
                CREATE INDEX IF NOT EXISTS idx_indicators_covering_recent
                ON indicators (symbol, timeframe, calculated_at DESC)
                INCLUDE (timestamp, ema_8, sma_20, rsi_14, atr_14, macd, obv)
                """,
                "description": "Covering index for recent data queries",
            },
            {
                "name": "idx_indicators_covering_symbol_timeframe",
                "sql": """
                CREATE INDEX IF NOT EXISTS idx_indicators_covering_symbol_timeframe
                ON indicators (symbol, timeframe, timestamp DESC)
                INCLUDE (calculated_at, ema_8, sma_20, rsi_14, atr_14, macd, obv)
                """,
                "description": "Covering index for symbol-timeframe queries",
            },
        ]

        for index_info in covering_indexes:
            try:
                await session.execute(text(index_info["sql"]))
                await session.commit()
                created_indexes.append(index_info["name"])
                self.logger.info(f"Created covering index: {index_info['name']}")
            except Exception as e:
                self.logger.warning(
                    f"Failed to create covering index {index_info['name']}: {e}"
                )

        return created_indexes

    async def analyze_index_usage(self, session: AsyncSession) -> dict[str, Any]:
        """
        Analyze index usage statistics.

        Args:
            session: Database session

        Returns:
            Index usage statistics
        """
        # Get index usage statistics
        usage_sql = """
        SELECT
            schemaname,
            tablename,
            indexname,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch
        FROM pg_stat_user_indexes
        WHERE tablename = 'indicators'
        ORDER BY idx_scan DESC
        """

        try:
            result = await session.execute(text(usage_sql))
            index_stats = result.fetchall()

            stats: dict[str, Any] = {
                "total_indexes": len(index_stats),
                "most_used": [],
                "unused": [],
                "usage_summary": {},
            }

            for row in index_stats:
                index_name = row[2]
                scan_count = row[3]

                if scan_count > 0:
                    stats["most_used"].append({"name": index_name, "scans": scan_count})
                else:
                    stats["unused"].append(index_name)

            stats["usage_summary"] = {
                "total_scans": sum(row[3] for row in index_stats),
                "avg_scans_per_index": (
                    sum(row[3] for row in index_stats) / len(index_stats)
                    if index_stats
                    else 0
                ),
            }

            self.logger.info(
                "Index usage analysis completed",
                total_indexes=stats["total_indexes"],
                most_used_count=len(stats["most_used"]),
                unused_count=len(stats["unused"]),
            )

            return stats

        except Exception as e:
            self.logger.error(f"Failed to analyze index usage: {e}")
            return {"error": str(e)}

    async def optimize_indexes(self, session: AsyncSession) -> dict[str, Any]:
        """
        Optimize database indexes.

        Args:
            session: Database session

        Returns:
            Optimization results
        """
        optimization_results: dict[str, Any] = {
            "analyzed": False,
            "recommendations": [],
            "actions_taken": [],
        }

        try:
            # Analyze table statistics
            analyze_sql = "ANALYZE indicators"
            await session.execute(text(analyze_sql))
            await session.commit()

            optimization_results["analyzed"] = True
            optimization_results["actions_taken"].append("Table statistics updated")

            # Get table size information
            size_sql = """
            SELECT
                pg_size_pretty(pg_total_relation_size('indicators')) as total_size,
                pg_size_pretty(pg_relation_size('indicators')) as table_size,
                pg_size_pretty(pg_total_relation_size('indicators') - pg_relation_size('indicators')) as index_size
            """

            result = await session.execute(text(size_sql))
            size_info = result.fetchone()

            if size_info:
                optimization_results["table_size"] = {
                    "total": size_info[0],
                    "table": size_info[1],
                    "indexes": size_info[2],
                }

            # Check for potential index optimizations
            duplicate_sql = """
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename = 'indicators'
            ORDER BY indexname
            """

            result = await session.execute(text(duplicate_sql))
            indexes = result.fetchall()

            # Check for duplicate or redundant indexes
            index_columns: dict[tuple[str, ...], str] = {}
            for index_name, index_def in indexes:
                # Extract columns from index definition
                columns = self._extract_index_columns(index_def)
                key = tuple(sorted(columns))

                if key in index_columns:
                    optimization_results["recommendations"].append(
                        {
                            "type": "duplicate_index",
                            "indexes": [index_columns[key], index_name],
                            "description": f"Potential duplicate indexes: {index_columns[key]} and {index_name}",
                        }
                    )
                else:
                    index_columns[key] = index_name

            self.logger.info(
                "Index optimization completed",
                analyzed=optimization_results["analyzed"],
                recommendations_count=len(optimization_results["recommendations"]),
            )

            return optimization_results

        except Exception as e:
            self.logger.error(f"Failed to optimize indexes: {e}")
            return {"error": str(e)}

    def _extract_index_columns(self, index_def: str) -> list[str]:
        """
        Extract column names from index definition.

        Args:
            index_def: Index definition string

        Returns:
            List of column names
        """
        # Simple extraction - would need more sophisticated parsing for complex cases
        import re

        # Extract columns from CREATE INDEX statement
        match = re.search(r"ON \w+ \((.+?)\)", index_def)
        if match:
            columns_str = match.group(1)
            # Split by comma and clean up
            return [col.strip().split()[0] for col in columns_str.split(",")]

        return []

    async def create_all_indexes(
        self, session: AsyncSession, feature_columns: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Create all recommended indexes.

        Args:
            session: Database session
            feature_columns: List of feature column names

        Returns:
            Summary of created indexes
        """
        results: dict[str, Any] = {
            "core_indexes": [],
            "feature_indexes": [],
            "covering_indexes": [],
            "total_created": 0,
        }

        try:
            # Create core indexes
            core_indexes = await self.create_core_indexes(session)
            results["core_indexes"] = core_indexes

            # Create feature-specific indexes
            if feature_columns:
                feature_indexes = await self.create_feature_specific_indexes(
                    session, feature_columns
                )
                results["feature_indexes"] = feature_indexes

            # Create covering indexes
            covering_indexes = await self.create_covering_indexes(session)
            results["covering_indexes"] = covering_indexes

            # Calculate total
            results["total_created"] = (
                len(core_indexes)
                + len(results["feature_indexes"])
                + len(covering_indexes)
            )

            self.logger.info(
                "All indexes created successfully",
                core_count=len(core_indexes),
                feature_count=len(results["feature_indexes"]),
                covering_count=len(covering_indexes),
                total=results["total_created"],
            )

            return results

        except Exception as e:
            self.logger.error(f"Failed to create all indexes: {e}")
            return {"error": str(e)}


# Global index manager instance
index_manager = FeaturesIndexManager()


async def create_database_indexes(
    session: AsyncSession, feature_columns: list[str] | None = None
) -> dict[str, Any]:
    """
    Create all database indexes for features module.

    Args:
        session: Database session
        feature_columns: List of feature column names

    Returns:
        Summary of created indexes
    """
    return await index_manager.create_all_indexes(session, feature_columns)


async def analyze_index_performance(session: AsyncSession) -> dict[str, Any]:
    """
    Analyze index performance and usage.

    Args:
        session: Database session

    Returns:
        Performance analysis results
    """
    return await index_manager.analyze_index_usage(session)


async def optimize_database_indexes(session: AsyncSession) -> dict[str, Any]:
    """
    Optimize database indexes.

    Args:
        session: Database session

    Returns:
        Optimization results
    """
    return await index_manager.optimize_indexes(session)
