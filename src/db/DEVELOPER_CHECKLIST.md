# Developer Checklist: src/db

## Applying Migrations

```bash
# 1. Check current status
python src/db/reports_cli.py status

# 2. Dry-run
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all(dry_run=True))"

# 3. Apply
python -m src.cli.main migrate

# 4. Validate schema
python -c "import asyncio; from src.db.schema_validation import validate_schema; asyncio.run(validate_schema())"
```

---

## Adding a New Migration

1. Create `src/db/migrations/migrate_NNN_name.py`:

```python
import logging
from sqlalchemy import text
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_your_migration_name() -> None:
    """Short description of what this migration does."""
    async with get_db_session() as session:
        try:
            await session.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'your_table' AND column_name = 'new_column'
                    ) THEN
                        ALTER TABLE your_table ADD COLUMN new_column VARCHAR(50);
                    END IF;
                END $$;
            """))
            await session.commit()
            logger.info("Migration completed: your_migration_name")
        except Exception as e:
            await session.rollback()
            logger.error("Migration failed: %s", e)
            raise
```

2. Register in `migration_registry.py` (append to the list):

```python
from src.db.migrations.migrate_your_migration_name import migrate_your_migration_name

# in get_migrations():
Migration("270_your_name", "description", migrate_your_migration_name),
```

3. Dry-run, then apply:

```bash
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all(dry_run=True))"
python -m src.cli.main migrate
```

---

## Monitoring

```bash
# Collect metrics
python src/db/monitoring_cli.py collect

# Alerts
python src/db/monitoring_cli.py alerts
python src/db/monitoring_cli.py alerts --severity error

# Metrics (last 24h)
python src/db/monitoring_cli.py metrics --hours 24

# Lock logs
python src/db/monitoring_cli.py locks --hours 24

# Refresh materialized views
python src/db/monitoring_cli.py refresh

# Export to JSON
python src/db/monitoring_cli.py export --output metrics.json

# Prometheus format
python src/db/monitoring_cli.py prometheus
```

---

## Reports

```bash
python src/db/reports_cli.py status       # migration status
python src/db/reports_cli.py health       # system health
python src/db/reports_cli.py stats        # DB statistics
python src/db/reports_cli.py report       # full report
python src/db/reports_cli.py performance  # performance metrics
```

---

## Troubleshooting

### Hung migration

```sql
-- Find blocking queries
SELECT pid, state, wait_event_type, wait_event, query
FROM pg_stat_activity WHERE state != 'idle';

-- Terminate if needed (careful)
SELECT pg_terminate_backend(<pid>);
```

### Disk space

```sql
SELECT pg_size_pretty(pg_database_size(current_database()));

SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::regclass))
FROM pg_tables WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

### Lock contention

```sql
SELECT l.pid, l.mode, l.granted, a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE NOT l.granted;
```

---

## Useful PostgreSQL Diagnostics

```sql
-- Current DB
SELECT current_database(), version();

-- List tables
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- List indexes
SELECT indexname, tablename, indexdef
FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename;

-- List partitions
SELECT parent.relname AS parent, child.relname AS partition
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child  ON pg_inherits.inhrelid  = child.oid
ORDER BY parent.relname, child.relname;

-- Index usage
SELECT indexrelname, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes ORDER BY idx_tup_read DESC;
```

---

## Indicators Partition Maintenance

```bash
# Preview
python -m src.cli.main indicators-partitions

# Apply
python -m src.cli.main indicators-partitions --apply --validate
```

---

Rules:
- Always test migrations with dry-run before applying
- All migrations must be idempotent (`IF NOT EXISTS`, `CREATE ... IF NOT EXISTS`)
- Use `CONCURRENTLY` for index creation to avoid table locks
- Log migration start and completion
