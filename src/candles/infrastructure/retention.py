"""
Retention policy for market_data_ext.

Manages cleanup of old data with different retention periods
for different data types.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from .logging_config import get_logger

logger = get_logger("market_data_retention")


class MarketDataExtRetention:
    """
    Retention management for market_data_ext.

    Different retention periods for different data types:
    - L2: 7 days (high frequency, low value of old data)
    - OI: 90 days (sufficient for trend analysis)
    - Funding: 730 days (2 years, historical data is important)
    """

    def __init__(self, engine):
        """
        Initialize retention service.

        Args:
            engine: SQLAlchemy engine for DB connection
        """
        self.engine = engine

    def cleanup_old_data(
        self,
        dry_run: bool = False,
        l2_retention_days: int = 7,
        oi_retention_days: int = 90,
        funding_retention_days: int = 730,
    ) -> dict[str, int]:
        """
        Delete old data according to retention policy.

        Args:
            dry_run: If True, only show what would be deleted without actual deletion
            l2_retention_days: Retention period for L2 data (days)
            oi_retention_days: Retention period for OI data (days)
            funding_retention_days: Retention period for Funding data (days)

        Returns:
            Dict with count of deleted records by type
        """
        logger.info("Starting market_data_ext cleanup (dry_run=%s)...", dry_run)

        deleted: dict[str, int] = {
            "l2": 0,
            "oi": 0,
            "funding": 0,
        }

        now = datetime.now(UTC)
        l2_cutoff = now - timedelta(days=l2_retention_days)
        oi_cutoff = now - timedelta(days=oi_retention_days)
        funding_cutoff = now - timedelta(days=funding_retention_days)

        if dry_run:
            logger.info(
                "Dry run: L2 cutoff: %s, OI cutoff: %s, Funding cutoff: %s",
                l2_cutoff,
                oi_cutoff,
                funding_cutoff,
            )
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM market_data_ext
                        WHERE bid_imbalance IS NOT NULL
                          AND bar_timestamp < :cutoff
                        """
                    ),
                    {"cutoff": l2_cutoff},
                )
                deleted["l2"] = result.scalar() or 0

                result = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM market_data_ext
                        WHERE open_interest IS NOT NULL
                          AND bar_timestamp < :cutoff
                        """
                    ),
                    {"cutoff": oi_cutoff},
                )
                deleted["oi"] = result.scalar() or 0

                result = conn.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM market_data_ext
                        WHERE funding_rate IS NOT NULL
                          AND bar_timestamp < :cutoff
                        """
                    ),
                    {"cutoff": funding_cutoff},
                )
                deleted["funding"] = result.scalar() or 0

            logger.info("Dry run complete. Would have deleted: %s", deleted)
            return deleted

        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    DELETE FROM market_data_ext
                    WHERE bid_imbalance IS NOT NULL
                      AND bar_timestamp < :cutoff
                    """
                ),
                {"cutoff": l2_cutoff},
            )
            deleted["l2"] = result.rowcount
            logger.info("Deleted %d old L2 records.", deleted["l2"])

            result = conn.execute(
                text(
                    """
                    DELETE FROM market_data_ext
                    WHERE open_interest IS NOT NULL
                      AND bar_timestamp < :cutoff
                    """
                ),
                {"cutoff": oi_cutoff},
            )
            deleted["oi"] = result.rowcount
            logger.info("Deleted %d old OI records.", deleted["oi"])

            result = conn.execute(
                text(
                    """
                    DELETE FROM market_data_ext
                    WHERE funding_rate IS NOT NULL
                      AND bar_timestamp < :cutoff
                    """
                ),
                {"cutoff": funding_cutoff},
            )
            deleted["funding"] = result.rowcount
            logger.info("Deleted %d old Funding Rate records.", deleted["funding"])

        with self.engine.connect() as conn:
            conn.execute(text("VACUUM ANALYZE market_data_ext"))
            conn.commit()
        logger.info("VACUUM ANALYZE market_data_ext complete.")

        return deleted
