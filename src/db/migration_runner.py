import logging
import time

from sqlalchemy import text

from src.db.migration_registry import get_migrations
from src.db.migration_reports import (
    generate_migration_report,
    generate_system_health_report,
)
from src.db.schema_validation import validate_schema_expectations
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def _already_applied(migration_id: str) -> bool:
    async with get_db_session() as session:
        q = text(
            "SELECT 1 FROM schema_migrations WHERE id = :id AND status = 'applied' LIMIT 1"
        )
        res = await session.execute(q, {"id": migration_id})
        return res.scalar() is not None


async def _record_status(
    migration_id: str,
    name: str,
    status: str,
    started_at: float,
    error: str | None = None,
    attempt: int = 1,
) -> None:
    duration_ms = int((time.time() - started_at) * 1000)
    async with get_db_session() as session:
        q = text(
            """
            INSERT INTO schema_migrations(id, name, applied_at, duration_ms, status, attempt, error)
            VALUES (:id, :name, :applied_at, :duration_ms, :status, :attempt, :error)
            ON CONFLICT (id) DO UPDATE SET
                applied_at = EXCLUDED.applied_at,
                duration_ms = EXCLUDED.duration_ms,
                status = EXCLUDED.status,
                attempt = schema_migrations.attempt + 1,
                error = EXCLUDED.error
            """
        )
        await session.execute(
            q,
            {
                "id": migration_id,
                "name": name,
                "applied_at": int(time.time()),
                "duration_ms": duration_ms,
                "status": status,
                "attempt": attempt,
                "error": error,
            },
        )
        await session.commit()


async def run_all(dry_run: bool = False) -> None:
    # Pre-validation
    try:
        await validate_schema_expectations()
    except Exception as e:
        logger.warning(f"⚠️ Pre-validation skipped: {e}")

    migrations = get_migrations()
    for m in migrations:
        if m.id != "000_base_migrations_table":
            # ensure table exists before we start using it
            from src.db.migrate_create_schema_migrations import (
                migrate_create_schema_migrations,
            )

            await migrate_create_schema_migrations()
            break

    for m in migrations:
        if m.id != "000_base_migrations_table" and await _already_applied(m.id):
            logger.info(f"⏭️ Пропущена миграция {m.id} ({m.name}) — уже применена")
            continue
        logger.info(f"📦 Миграция {m.id}: {m.name}")
        started = time.time()
        if dry_run:
            await _record_status(
                m.id, m.name, "planned", started, error=None, attempt=0
            )
            logger.info(f"📝 DRY-RUN: {m.id} ({m.name}) запланирована")
            continue
        try:
            await m.func()
            duration_ms = int((time.time() - started) * 1000)
            await _record_status(m.id, m.name, "applied", started)
            logger.info(f"✅ Применена {m.id} ({m.name})")

            # Генерируем отчёт о миграции
            try:
                report = await generate_migration_report(
                    m.id, duration_ms, save_file=True
                )
                report.print_summary()
            except Exception as report_error:
                logger.warning(f"⚠️ Не удалось сгенерировать отчёт: {report_error}")

        except Exception as e:
            await _record_status(m.id, m.name, "failed", started, error=str(e))
            logger.error(f"❌ Ошибка миграции {m.id}: {e}")
            raise

    # Post-validation
    try:
        await validate_schema_expectations()
    except Exception as e:
        logger.warning(f"⚠️ Post-validation skipped: {e}")

    # Генерируем отчёт о состоянии системы
    try:
        health_report = await generate_system_health_report()
        if health_report.get("overall_status") == "healthy":
            logger.info("🏥 Система в хорошем состоянии")
        else:
            logger.warning("⚠️ Система требует внимания")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось сгенерировать отчёт о состоянии: {e}")
