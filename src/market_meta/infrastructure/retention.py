"""
Retention политика для market_data_ext.

Управление очисткой старых данных с разными retention периодами
для разных типов данных.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from .logging_config import get_logger

logger = get_logger("market_data_retention")


class MarketDataExtRetention:
    """
    Управление retention для market_data_ext.

    Разные retention периоды для разных типов данных:
    - L2: 7 дней (высокая частота, низкая ценность старых данных)
    - OI: 90 дней (достаточно для анализа трендов)
    - Funding: 730 дней (2 года, исторические данные важны)
    """

    def __init__(self, engine):
        """
        Инициализация retention сервиса.

        Args:
            engine: SQLAlchemy engine для подключения к БД
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
        Удаляет старые данные согласно retention политике.

        Args:
            dry_run: Если True, только показывает что будет удалено, без фактического удаления
            l2_retention_days: Retention период для L2 данных (дни)
            oi_retention_days: Retention период для OI данных (дни)
            funding_retention_days: Retention период для Funding данных (дни)

        Returns:
            Словарь с количеством удалённых записей по типам
        """
        logger.info(f"Запуск очистки market_data_ext (dry_run={dry_run})...")

        deleted: dict[str, int] = {
            "l2": 0,
            "oi": 0,
            "funding": 0,
        }

        # Определяем cutoff даты
        now = datetime.now(UTC)
        l2_cutoff = now - timedelta(days=l2_retention_days)
        oi_cutoff = now - timedelta(days=oi_retention_days)
        funding_cutoff = now - timedelta(days=funding_retention_days)

        if dry_run:
            logger.info(f"Dry run: L2 cutoff: {l2_cutoff}, OI cutoff: {oi_cutoff}, Funding cutoff: {funding_cutoff}")
            # В dry_run режиме считаем количество записей, которые будут удалены
            with self.engine.connect() as conn:
                # L2
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

                # OI
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

                # Funding
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

            logger.info(f"Dry run завершен. Было бы удалено: {deleted}")
            return deleted

        # Фактическое удаление
        with self.engine.begin() as conn:
            # Удаление L2 данных
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
            logger.info(f"Удалено {deleted['l2']} старых L2 записей.")

            # Удаление OI данных
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
            logger.info(f"Удалено {deleted['oi']} старых OI записей.")

            # Удаление Funding Rates данных
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
            logger.info(f"Удалено {deleted['funding']} старых Funding Rates записей.")

        # VACUUM ANALYZE для освобождения места
        with self.engine.connect() as conn:
            conn.execute(text("VACUUM ANALYZE market_data_ext"))
            conn.commit()
        logger.info("VACUUM ANALYZE market_data_ext выполнен.")

        return deleted
