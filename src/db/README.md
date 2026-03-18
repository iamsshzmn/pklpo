# DB Module

**Версия:** 2.1.0 | **Статус:** Production Ready

Модуль управления миграциями PostgreSQL с поддержкой идемпотентного применения, отслеживания состояния, партиционирования и мониторинга.

---

## 1. Purpose

Централизованное управление схемой PostgreSQL для всех таблиц проекта:
- **Idempotent migrations** — безопасное повторное выполнение
- **Ordered execution** — реестр с фиксированным порядком применения
- **Schema validation** — автоматические проверки перед/после
- **Monitoring** — метрики, алерты, логи блокировок
- **Materialized views** — агрегации для аналитики

---

## 2. Architecture

### 2.1 Структура модуля

```
src/db/
├── migration_runner.py          # Движок выполнения миграций
├── migration_registry.py        # Реестр с порядком миграций
├── schema_validation.py         # Валидация схемы БД
├── db_schema_utils.py           # Утилиты для работы со схемой
├── migration_reports.py         # Генерация отчётов
├── reports_cli.py               # CLI для отчётов
├── monitoring_cli.py            # CLI для мониторинга
├── DEVELOPER_CHECKLIST.md       # Чек-лист разработчика
├── rollback_phase3_quant_tables.sql  # SQL для отката phase3
├── migrations/                  # Файлы миграций
│   ├── __init__.py
│   ├── migrate_create_schema_migrations.py
│   ├── migrate_create_ohlcv.py
│   ├── migrate_create_ohlcv_partitioned.py
│   ├── migrate_create_indicators_partitioned.py
│   └── ...                      # Остальные миграции
├── indicators_partition/        # Логика обслуживания партиций indicators_p
└── reports/                     # Артефакты отчётов
    ├── STAGES_8_9_COMPLETION_SUMMARY.md
    └── MIGRATION_TESTING_SUMMARY.md
```

### 2.2 Слои

| Слой | Файл | Ответственность |
|------|------|-----------------|
| **Runner** | `migration_runner.py` | Применение миграций, dry-run, откат |
| **Registry** | `migration_registry.py` | Упорядоченный список миграций |
| **Validation** | `schema_validation.py` | Проверка схемы БД |
| **Reports** | `migration_reports.py`, `reports_cli.py` | Статус, здоровье, статистика |
| **Monitoring** | `monitoring_cli.py` | Метрики, алерты, логи блокировок |
| **Migrations** | `migrations/*.py` | Идемпотентные DDL/DML изменения |

---

## 3. Migration Registry

Полный упорядоченный список миграций из `migration_registry.py`:

| ID | Описание | Файл |
|----|----------|------|
| `000_base_migrations_table` | Создание таблицы отслеживания `schema_migrations` | `migrate_create_schema_migrations.py` |
| `010_instruments` | Создание таблицы `instruments` | `src/migrate_create_instruments.py` |
| `020_ohlcv` | Создание таблицы `ohlcv` | `migrate_create_ohlcv.py` |
| `030_add_swap_fields` | Поля свопов | `migrate_add_swap_fields.py` |
| `040_positions` | Таблицы позиций | `migrate_create_positions.py` |
| `050_score_results` | Таблица `score_results` | `migrate_create_score_results.py` |
| `060_fix_score_precision` | Точность `score_results` | `migrate_fix_score_results_precision.py` |
| `070_add_swap_fields_to_instruments` | Поля свопов в `instruments` | `migrate_add_swap_fields_to_instruments.py` |
| `080_trade_recommendations` | Таблицы рекомендаций | `migrate_create_trade_recommendations.py` |
| `090_core_indexes` | Составные и BRIN индексы | `migrate_add_core_indexes.py` |
| `100_ohlcv_partitioned` | Партиционированная `ohlcv_p` | `migrate_create_ohlcv_partitioned.py` |
| `110_indicators_partitioned` | Партиционированная `indicators_p` | `migrate_create_indicators_partitioned.py` |
| `130_data_constraints` | Ограничения качества данных | `migrate_add_data_constraints.py` |
| `140_operational_reliability` | Функции надёжности и бэкапа | `migrate_add_operational_reliability.py` |
| `150_data_cleanup` | Очистка и нормализация данных | `migrate_data_cleanup.py` |
| `160_materialized_views` | Материализованные представления | `migrate_materialized_views.py` |
| `170_monitoring_metrics` | Система мониторинга и метрик | `migrate_monitoring_metrics.py` |
| `180_swap_ohlcv` | Партиционированная `swap_ohlcv` | `migrate_create_swap_ohlcv.py` |
| `190_features_table` | Таблица `features` для индикаторов | `migrate_create_features_table.py` |
| `210_data_retention` | Политика хранения данных (2 дня) | `migrate_add_data_retention.py` |
| `230_expand_indicators_precision` | Расширение точности до `NUMERIC(38,12)` | `migrate_expand_indicators_precision.py` |
| `240_combination_features` | Таблица `combination_features` | `migrate_create_combination_features.py` |
| `250_market_data_ext` | Таблица `market_data_ext` (OI, funding, L2) | `migrate_create_market_data_ext.py` |
| `260_market_selection` | Таблицы market selection | `migrate_create_market_selection.py` |

### 3.1 Политика нумерации

| Диапазон | Назначение |
|----------|------------|
| `000–099` | Базовая инфраструктура и схема |
| `100–199` | Партиционирование и индексы |
| `200–299` | Расширения схемы и точность |
| `300–399` | (зарезервировано) |

### 3.2 Политика для цепочки indicators_p

Одновременно присутствуют target, transition и legacy миграции:

| Тип | Миграции | Использование |
|-----|---------|---------------|
| **target bootstrap** | `110_indicators_partitioned` | Основной путь создания `indicators_p` |
| **transition-only** | `120_backfill_partitioned` | Перенос данных `indicators → indicators_p` (временная) |
| **legacy compat** | `200_unified_indicators`, `205_update_indicators`, `220_remove_ohlcv_from_indicators` | Описывают старую `indicators`, не являются целевым bootstrap path |
| **mixed** | `230_expand_indicators_precision` | Полезна для `indicators_p` и партиций, содержит legacy-ветку |

Практическое правило: для runtime-path ориентироваться на `indicators_p`. Legacy-ветки помечать явно как compatibility/transition, не выносить в основной bootstrap path.

### 3.3 Обслуживание партиций indicators_p

Routine partition maintenance (создание новых партиций, vacuum) вынесено в `src/db/indicators_partition/` и управляется отдельно:

```bash
# Preview без изменений схемы
python -m src.cli.main indicators-partitions

# Применение maintenance
python -m src.cli.main indicators-partitions --apply --validate
```

---

## 4. CLI Commands

### 4.1 Запуск миграций

```bash
# Все миграции (через CLI)
python -m src.cli.main migrate

# Dry-run через runner напрямую
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all(dry_run=True))"
```

### 4.2 Валидация схемы

```bash
python -c "import asyncio; from src.db.schema_validation import validate_schema; asyncio.run(validate_schema())"
```

### 4.3 Отчёты

```bash
# Статус миграций
python src/db/reports_cli.py status

# Детальный отчёт
python src/db/reports_cli.py report

# Здоровье системы
python src/db/reports_cli.py health

# Статистика БД
python src/db/reports_cli.py stats

# Производительность
python src/db/reports_cli.py performance
```

### 4.4 Мониторинг

```bash
# Сбор метрик
python src/db/monitoring_cli.py collect

# Просмотр метрик за 24 часа
python src/db/monitoring_cli.py metrics --hours 24

# Алерты
python src/db/monitoring_cli.py alerts

# Фильтр по уровню
python src/db/monitoring_cli.py alerts --severity error

# Логи блокировок
python src/db/monitoring_cli.py locks --hours 24

# Обновление материализованных представлений
python src/db/monitoring_cli.py refresh

# Мониторинг блокировок в реальном времени
python src/db/monitoring_cli.py monitor

# Экспорт метрик в JSON
python src/db/monitoring_cli.py export --output metrics.json

# Prometheus метрики
python src/db/monitoring_cli.py prometheus
```

---

## 5. Storage Details

### 5.1 Таблица отслеживания миграций

```sql
CREATE TABLE schema_migrations (
    migration_id  TEXT PRIMARY KEY,
    migration_name TEXT NOT NULL,
    applied_at    TIMESTAMP DEFAULT NOW(),
    duration_ms   INTEGER,
    status        TEXT DEFAULT 'success',
    error         TEXT
);
```

### 5.2 Основные таблицы

| Таблица | Описание | Партиционирование |
|---------|----------|--------------------|
| `instruments` | Метаданные торговых пар | нет |
| `ohlcv` | Рыночные свечи (legacy) | нет |
| `ohlcv_p` | Рыночные свечи (production) | по `(symbol, timeframe)` |
| `indicators_p` | Рассчитанные индикаторы | по `(symbol, timeframe)` |
| `swap_ohlcv` | Свечи для свопов | по символу |
| `score_results` | Результаты скоринга | нет |
| `positions` | Позиции | нет |
| `trade_recommendations` | Рекомендации | нет |
| `features` | Технические индикаторы (features table) | нет |
| `combination_features` | Комбинации фич (numeric-only) | нет |
| `market_data_ext` | Extended market data (OI, funding, L2) | нет |
| `market_selection_*` | Market selection (scores, universe, versions, regime) | нет |
| `schema_migrations` | История миграций | нет |

### 5.3 Мониторинговые таблицы (migration_monitoring_metrics)

| Таблица | Описание |
|---------|----------|
| `migration_logs` | Логи выполнения миграций |
| `lock_logs` | Логи блокировок и их длительности |
| `performance_metrics` | Метрики производительности БД |
| `alerts` | Система алертов (info / warning / error / critical) |

### 5.4 Материализованные представления (migration_materialized_views)

| Представление | Описание |
|---------------|----------|
| `mv_symbol_stats` | Статистика по символам и таймфреймам |
| `mv_latest_prices` | Последние цены для каждого символа |
| `mv_daily_aggregation` | Дневная агрегация OHLCV |
| `mv_volatility` | Метрики волатильности по дням |
| `mv_top_symbols` | Топ активных символов за 7 дней |
| `mv_data_quality` | Метрики качества данных |

```sql
-- Обновление всех представлений
SELECT refresh_materialized_views();
```

---

## 6. Writing Migrations

### 6.1 Idempotency — обязательно

```sql
-- Создание таблицы
CREATE TABLE IF NOT EXISTS my_table (id SERIAL PRIMARY KEY, name VARCHAR(100));

-- Добавление колонки
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'my_table' AND column_name = 'new_column'
    ) THEN
        ALTER TABLE my_table ADD COLUMN new_column VARCHAR(50);
    END IF;
END $$;

-- Создание индекса
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_my_table_name ON my_table (name);

-- Создание ENUM
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'my_enum') THEN
        CREATE TYPE my_enum AS ENUM ('value1', 'value2');
    END IF;
END $$;
```

### 6.2 Шаблон миграции

```python
import logging
from sqlalchemy import text
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_your_migration_name() -> None:
    """Описание что делает миграция."""
    logger.info("Starting migration: your_migration_name")

    async with get_db_session() as session:
        try:
            migration_q = text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'your_table' AND column_name = 'new_column'
                    ) THEN
                        ALTER TABLE your_table ADD COLUMN new_column VARCHAR(50);
                    END IF;
                END $$;
            """)
            await session.execute(migration_q)
            await session.commit()
            logger.info("Migration completed: your_migration_name")

        except Exception as e:
            await session.rollback()
            logger.error("Migration failed: %s", e)
            raise
```

### 6.3 Регистрация новой миграции

1. Создать файл в `src/db/migrations/migrate_your_name.py`
2. Добавить в `migration_registry.py`:

```python
from src.db.migrations.migrate_your_name import migrate_your_migration_name

# В get_migrations(), в конец списка:
Migration("270_your_name", "description", migrate_your_migration_name),
```

### 6.4 Использование CONCURRENTLY для индексов

```sql
-- Не блокирует таблицу (рекомендуется)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table_name (column);

-- Блокирует таблицу (избегать на production)
CREATE INDEX idx_name ON table_name (column);
```

---

## 7. Rollback

### 7.1 Автоматический откат (в рамках транзакции)

Runner выполняет `session.rollback()` при любом исключении во время миграции.

### 7.2 Ручной откат

```python
async def rollback_migration(migration_id: str) -> None:
    async with get_db_session() as session:
        try:
            # Откат изменений (например, DROP COLUMN IF EXISTS)
            await session.execute(text("ALTER TABLE my_table DROP COLUMN IF EXISTS new_column"))

            await session.execute(text("""
                UPDATE schema_migrations
                SET status = 'rolled_back', applied_at = NOW()
                WHERE migration_id = :migration_id
            """), {"migration_id": migration_id})

            await session.commit()

        except Exception as e:
            await session.rollback()
            raise
```

### 7.3 Phase3 rollback

```bash
# SQL-файл для отката phase3 таблиц
psql -d $POSTGRES_DB -f src/db/rollback_phase3_quant_tables.sql
```

---

## 8. Failure Modes & Troubleshooting

### 8.1 Частые сбои

| Сбой | Поведение | Recovery |
|------|-----------|----------|
| Миграция уже применена | Пропускается по `schema_migrations` | Автоматический |
| DDL ошибка | `session.rollback()`, запись `status='error'` | Исправить миграцию, повторить |
| Блокировка таблицы | Зависание | Найти и завершить блокирующий процесс |
| Недостаточно места | Ошибка PostgreSQL | Очистить данные или расширить диск |

### 8.2 Миграция зависла

```sql
-- Найти блокирующие запросы
SELECT pid, state, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE state != 'idle';

-- Найти незавершённые блокировки
SELECT l.pid, l.mode, l.granted, a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE NOT l.granted;

-- Завершить процесс (осторожно)
SELECT pg_terminate_backend(<pid>);
```

### 8.3 Нехватка места

```sql
-- Размер БД
SELECT pg_size_pretty(pg_database_size(current_database()));

-- Размер таблиц
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::regclass))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

---

## 9. Runbook

### 9.1 Применение миграций

```bash
# 1. Проверить текущее состояние
python src/db/reports_cli.py status

# 2. Dry-run
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all(dry_run=True))"

# 3. Применить
python -m src.cli.main migrate

# 4. Проверить результат
python src/db/reports_cli.py status
python -c "import asyncio; from src.db.schema_validation import validate_schema; asyncio.run(validate_schema())"
```

### 9.2 Добавление новой миграции

| Шаг | Действие |
|-----|----------|
| 1 | Создать `src/db/migrations/migrate_NNN_name.py` по шаблону из раздела 6.2 |
| 2 | Зарегистрировать в `migration_registry.py` (в конец списка) |
| 3 | Сделать dry-run для проверки |
| 4 | Применить на staging |
| 5 | Проверить схему через `schema_validation.py` |
| 6 | Применить на production |

### 9.3 Обновление материализованных представлений

```bash
python src/db/monitoring_cli.py refresh
```

### 9.4 Диагностика схемы

```sql
-- Список партиций
SELECT parent.relname AS parent, child.relname AS partition
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child  ON pg_inherits.inhrelid  = child.oid
ORDER BY parent.relname, child.relname;

-- Список индексов
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
```

### 9.5 Environment Variables

| Variable | Default | Описание |
|----------|---------|----------|
| `POSTGRES_USER` | — | DB user |
| `POSTGRES_PASSWORD` | — | DB password |
| `POSTGRES_DB` | — | DB name |
| `DB_HOST` | localhost | DB host |
| `DB_PORT` | 5432 | DB port |

---

## Appendix A: Аналитические запросы к материализованным представлениям

```sql
-- Символы с высокой волатильностью за 7 дней
SELECT symbol, AVG(volatility) as avg_volatility
FROM mv_volatility
WHERE day >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY symbol
HAVING AVG(volatility) > 0.05
ORDER BY avg_volatility DESC;

-- Сравнение объёмов по дням недели
SELECT
    EXTRACT(DOW FROM trade_date) as day_of_week,
    AVG(day_volume) as avg_volume
FROM mv_daily_aggregation
WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY day_of_week
ORDER BY day_of_week;

-- Символы с проблемами качества данных
SELECT table_name, total_records, negative_volumes, invalid_spreads
FROM mv_data_quality
WHERE negative_volumes > 0 OR invalid_spreads > 0;
```

---

**Версия:** 2.1.0
**Последнее обновление:** 2026-03-07
**Статус:** Production Ready
