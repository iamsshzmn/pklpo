# Чек-лист разработчика модуля `src/db`

## 🚀 Быстрый старт

### ✅ Проверка состояния системы
```bash
# 1. Проверка статуса миграций
python src/db/reports_cli.py status

# 2. Проверка здоровья системы
python src/db/reports_cli.py health

# 3. Сбор метрик производительности
python src/db/monitoring_cli.py collect
```

### ✅ Запуск миграций
```bash
# Запуск всех миграций
python src/main_v2.py --migrations

# Dry-run (проверка без изменений)
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all(dry_run=True))"
```

### ✅ Тестирование
```bash
# Полный тест-сьют
python run_migration_tests.py

# CI/CD режим
python run_migration_tests.py --ci

# С подробным отчётом
python run_migration_tests.py --report test_report.json --verbose
```

## 📊 Мониторинг и отладка

### 🔍 Просмотр логов и метрик
```bash
# Просмотр алертов
python src/db/monitoring_cli.py alerts

# Просмотр метрик за последние 24 часа
python src/db/monitoring_cli.py metrics --hours 24

# Логи блокировок
python src/db/monitoring_cli.py locks --hours 24

# Prometheus метрики
python src/db/monitoring_cli.py prometheus
```

### 📈 Экспорт данных
```bash
# Экспорт метрик в JSON
python src/db/monitoring_cli.py export --output metrics.json

# Детальный отчёт о системе
python src/db/reports_cli.py report

# Статистика БД
python src/db/reports_cli.py stats
```

## 🔧 Управление данными

### 🧹 Очистка и нормализация
```bash
# Автоматически выполняется при запуске миграций
python src/main_v2.py --migrations
```

### 📊 Материализованные представления
```bash
# Обновление всех представлений
python src/db/monitoring_cli.py refresh

# Проверка представлений в БД
psql -d your_database -c "SELECT * FROM mv_symbol_stats LIMIT 5;"
psql -d your_database -c "SELECT * FROM mv_latest_prices LIMIT 5;"
psql -d your_database -c "SELECT * FROM mv_top_symbols LIMIT 5;"
```

## 🚨 Устранение неполадок

### ❌ Проблемы с миграциями
```bash
# Проверка активных транзакций
psql -d your_database -c "SELECT pid, state, query FROM pg_stat_activity WHERE state = 'active';"

# Принудительное завершение зависших процессов (осторожно!)
psql -d your_database -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active';"
```

### 💾 Проблемы с местом
```bash
# Проверка размера БД
psql -d your_database -c "SELECT pg_size_pretty(pg_database_size('your_database'));"

# Проверка размера таблиц
psql -d your_database -c "SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename)) FROM pg_tables WHERE schemaname = 'public';"
```

### 🔒 Проблемы с блокировками
```bash
# Проверка блокировок
psql -d your_database -c "
SELECT
    l.pid,
    l.mode,
    l.granted,
    a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE NOT l.granted;
"
```

## 📝 Создание новых миграций

### 🔧 Шаблон миграции
```python
#!/usr/bin/env python3
"""
Описание миграции.
"""

import logging
from sqlalchemy import text
from src.utils.session_utils import get_db_session

logger = logging.getLogger(__name__)


async def migrate_your_migration_name() -> None:
    """
    Описание что делает миграция.
    """
    logger.info("🔄 Начинаем миграцию...")

    async with get_db_session() as session:
        try:
            # 1. Проверяем текущее состояние
            check_q = text("SELECT COUNT(*) FROM your_table")
            result = await session.execute(check_q)
            current_count = result.scalar()
            logger.info(f"📊 Текущее количество записей: {current_count}")

            # 2. Выполняем изменения (идемпотентно)
            migration_q = text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'your_table' AND column_name = 'new_column'
                    ) THEN
                        ALTER TABLE your_table ADD COLUMN new_column VARCHAR(50);
                        RAISE NOTICE 'Column added successfully';
                    ELSE
                        RAISE NOTICE 'Column already exists';
                    END IF;
                END $$;
            """)
            await session.execute(migration_q)

            # 3. Проверяем результат
            verify_q = text("SELECT COUNT(*) FROM your_table")
            result = await session.execute(verify_q)
            new_count = result.scalar()
            logger.info(f"✅ Миграция завершена. Новое количество: {new_count}")

            await session.commit()

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка миграции: {e}")
            raise
```

### 📋 Регистрация миграции
1. Добавить импорт в `migration_registry.py`:
```python
from src.db.migrate_your_migration_name import migrate_your_migration_name
```

2. Добавить в список миграций:
```python
Migration("180_your_migration_name", "description of migration", migrate_your_migration_name),
```

## 🧪 Тестирование новых миграций

### ✅ Локальное тестирование
```bash
# 1. Dry-run
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all(dry_run=True))"

# 2. Запуск тестов
python run_migration_tests.py

# 3. Проверка схемы
python -c "import asyncio; from src.db.schema_validation import validate_schema; asyncio.run(validate_schema())"
```

### ✅ Проверка производительности
```bash
# Сбор метрик до и после
python src/db/monitoring_cli.py collect

# Проверка размера таблиц
python src/db/reports_cli.py stats

# Проверка индексов
psql -d your_database -c "SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public';"
```

## 📚 Полезные команды PostgreSQL

### 🔍 Диагностика
```sql
-- Проверка версии PostgreSQL
SELECT version();

-- Проверка текущей БД
SELECT current_database();

-- Проверка схем
SELECT schema_name FROM information_schema.schemata;

-- Список таблиц
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Список индексов
SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public';

-- Проверка партиций
SELECT schemaname, tablename, partitionname FROM pg_partitions WHERE schemaname = 'public';
```

### 📊 Статистика
```sql
-- Размер таблиц
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(tablename) DESC;

-- Статистика по индексам
SELECT
    indexrelname,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_tup_read DESC;
```

---

**🎯 Помните:**
- Всегда тестируйте миграции на staging перед production
- Используйте dry-run для проверки изменений
- Логируйте все операции
- Проверяйте производительность после изменений
- Документируйте новые миграции
