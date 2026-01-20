# Модуль миграций базы данных

## 📋 Обзор

Модуль `src/db` представляет собой **полноценную enterprise-систему управления миграциями** для PostgreSQL с поддержкой:

### 🎯 Основные возможности
- ✅ **Идемпотентные миграции** - безопасное повторное выполнение
- ✅ **Отслеживание состояния** - полная история применения миграций
- ✅ **Тестирование и валидация** - автоматические проверки схемы
- ✅ **Мониторинг и метрики** - система алертов и производительности
- ✅ **Автоматические бэкапы** - функции резервного копирования
- ✅ **Партиционирование** - оптимизация для больших таблиц
- ✅ **Материализованные представления** - агрегации для аналитики
- ✅ **Очистка данных** - валидация и нормализация
- ✅ **Prometheus интеграция** - готовность к внешним системам мониторинга

### 🏗️ Архитектура
```
src/db/
├── migration_runner.py      # Основной движок миграций
├── migration_registry.py    # Реестр всех миграций
├── schema_validation.py     # Валидация схемы БД
├── migration_testing.py     # Тест-сьют для миграций
├── migration_reports.py     # Генерация отчётов
├── reports_cli.py          # CLI для отчётов
├── monitoring_cli.py       # CLI для мониторинга
├── migrate_*.py            # Файлы миграций (по этапам)
└── reports/                # Отчёты и документация
```

## 🚀 Быстрый старт

### 🎯 Основные команды

#### Запуск всех миграций
```bash
# Через main_v2.py (рекомендуется)
python src/main_v2.py --migrations

# Напрямую через runner
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all())"
```

#### Запуск тестов
```bash
# Полный тест-сьют
python run_migration_tests.py

# CI/CD режим
python run_migration_tests.py --ci

# С подробным отчётом
python run_migration_tests.py --report test_report.json --verbose
```

#### Dry-run (проверка без изменений)
```bash
python -c "import asyncio; from src.db.migration_runner import run_all; asyncio.run(run_all(dry_run=True))"
```

### 📊 Мониторинг и отчёты

#### Просмотр статуса миграций
```bash
python src/db/reports_cli.py status
```

#### Проверка здоровья системы
```bash
python src/db/reports_cli.py health
```

#### Сбор метрик производительности
```bash
python src/db/monitoring_cli.py collect
```

#### Просмотр алертов
```bash
python src/db/monitoring_cli.py alerts
```

### 🔧 Управление данными

#### Очистка и нормализация данных
```bash
# Автоматически выполняется при запуске миграций
python src/main_v2.py --migrations
```

#### Обновление материализованных представлений
```bash
python src/db/monitoring_cli.py refresh
```

## 📚 Политика версионирования

### Формат ID миграций
```
XXX_description_of_migration
```

**Примеры:**
- `001_create_schema_migrations` - Базовая инфраструктура
- `100_add_core_indexes` - Индексы и производительность
- `110_create_ohlcv_partitioned` - Партиционирование
- `120_backfill_partitioned` - Перенос данных
- `130_data_constraints` - Ограничения и качество данных
- `140_operational_reliability` - Операционная надежность
- `150_data_cleanup` - Очистка и нормализация данных
- `160_materialized_views` - Материализованные представления
- `170_monitoring_metrics` - Система мониторинга и метрик

### Правила нумерации
- **000-099**: Базовая инфраструктура и схема
- **100-199**: Производительность и индексы
- **200-299**: Партиционирование и масштабирование
- **300-399**: Качество данных и ограничения
- **400-499**: Операционная надежность
- **500-599**: Мониторинг и метрики
- **600-699**: Очистка и нормализация данных
- **700-799**: Материализованные представления
- **800-899**: Резервные копии и восстановление
- **900-999**: Экспериментальные функции

## 🎯 Этапы развития системы

### ✅ Этап 1: Базовая инфраструктура миграций
- [x] Система версионирования миграций
- [x] Реестр миграций с порядком выполнения
- [x] Runner для применения миграций
- [x] Dry-run режим
- [x] Логирование и отчётность

### ✅ Этап 2: Безопасность и идемпотентность
- [x] Идемпотентные миграции
- [x] Транзакционная безопасность
- [x] Обработка ошибок и откатов
- [x] Валидация схемы до/после

### ✅ Этап 3: Индексация и производительность
- [x] Партиционирование таблиц
- [x] Оптимизированные индексы
- [x] Backfill данных
- [x] Анализ производительности

### ✅ Этап 4: Качество данных и ограничения
- [x] ENUM типы и домены
- [x] PRIMARY KEY и UNIQUE ограничения
- [x] CHECK ограничения
- [x] Частичные индексы

### ✅ Этап 5: Операционная надёжность
- [x] Таймауты и лимиты
- [x] Функции резервного копирования
- [x] Мониторинг и метрики
- [x] Retry с backoff

### ✅ Этап 6: Тестирование и CI
- [x] Тест-сьют для миграций
- [x] Валидация схемы
- [x] Тесты производительности
- [x] CI/CD интеграция

### ✅ Этап 7: Документация и DX
- [x] Подробная документация
- [x] CLI для отчётов
- [x] Шаблоны миграций
- [x] Лучшие практики

### ✅ Этап 8: Миграции по содержимому
- [x] Очистка и нормализация данных
- [x] Удаление дубликатов
- [x] Валидация цен и объемов
- [x] Материализованные представления
- [x] Агрегации и статистики

### ✅ Этап 9: Мониторинг и метрики
- [x] Система логирования миграций
- [x] Мониторинг блокировок
- [x] Сбор метрик производительности
- [x] Система алертов
- [x] Prometheus-совместимые метрики
- [x] CLI для мониторинга

## 🔄 Порядок миграций

### 1. Базовая инфраструктура
```sql
-- 001: Создание таблицы отслеживания миграций
CREATE TABLE schema_migrations (
    migration_id TEXT PRIMARY KEY,
    migration_name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW(),
    duration_ms INTEGER,
    status TEXT DEFAULT 'success',
    error TEXT
);
```

### 2. Основные таблицы
```sql
-- 010: Создание таблиц данных
CREATE TABLE instruments (...);
CREATE TABLE ohlcv (...);
CREATE TABLE indicators (...);
```

### 3. Индексы и производительность
```sql
-- 100: Добавление индексов
CREATE INDEX CONCURRENTLY idx_ohlcv_symbol_timeframe_timestamp
ON ohlcv (symbol, timeframe, timestamp);
```

### 4. Партиционирование
```sql
-- 110: Создание партиционированных таблиц
CREATE TABLE ohlcv_p (
    symbol VARCHAR(50),
    timeframe VARCHAR(20),
    timestamp BIGINT,
    open DECIMAL(20,8),
    high DECIMAL(20,8),
    low DECIMAL(20,8),
    close DECIMAL(20,8),
    volume DECIMAL(30,8)
) PARTITION BY RANGE (timestamp);
```

### 5. Перенос данных
```sql
-- 120: Перенос данных в партиционированные таблицы
INSERT INTO ohlcv_p SELECT * FROM ohlcv WHERE timestamp IS NOT NULL;
```

### 6. Ограничения и качество
```sql
-- 130: Добавление ограничений
ALTER TABLE ohlcv_p ADD CONSTRAINT chk_ohlcv_p_volume_positive
CHECK (volume >= 0);
```

### 7. Операционная надежность
```sql
-- 140: Функции бэкапа и мониторинга
CREATE OR REPLACE FUNCTION create_table_backup(...);
CREATE VIEW table_size_monitoring AS ...;
```

## ✨ Как писать идемпотентные миграции

### ✅ Правильно (идемпотентно)
```sql
-- Создание таблицы
CREATE TABLE IF NOT EXISTS my_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100)
);

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
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_my_table_name
ON my_table (name);

-- Создание ENUM
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'my_enum') THEN
        CREATE TYPE my_enum AS ENUM ('value1', 'value2');
    END IF;
END $$;
```

### ❌ Неправильно (не идемпотентно)
```sql
-- Без IF NOT EXISTS
CREATE TABLE my_table (id SERIAL PRIMARY KEY);

-- Без проверки существования
ALTER TABLE my_table ADD COLUMN new_column VARCHAR(50);

-- Без IF NOT EXISTS
CREATE INDEX idx_my_table_name ON my_table (name);
```

### 🔧 Шаблон миграции
```python
async def run_migration_name() -> None:
    """
    Описание миграции.
    """
    logger.info("🔄 Начинаем миграцию...")

    async with get_db_session() as session:
        try:
            # 1. Проверяем текущее состояние
            check_q = text("SELECT COUNT(*) FROM my_table")
            result = await session.execute(check_q)
            current_count = result.scalar()
            logger.info(f"📊 Текущее количество записей: {current_count}")

            # 2. Выполняем изменения (идемпотентно)
            migration_q = text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'my_table' AND column_name = 'new_column'
                    ) THEN
                        ALTER TABLE my_table ADD COLUMN new_column VARCHAR(50);
                        RAISE NOTICE 'Column added successfully';
                    ELSE
                        RAISE NOTICE 'Column already exists';
                    END IF;
                END $$;
            """)
            await session.execute(migration_q)

            # 3. Проверяем результат
            verify_q = text("SELECT COUNT(*) FROM my_table")
            result = await session.execute(verify_q)
            new_count = result.scalar()
            logger.info(f"✅ Миграция завершена. Новое количество: {new_count}")

            await session.commit()

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка миграции: {e}")
            raise
```

## 🔙 Как откатывать миграции

### 1. Автоматический откат (в рамках транзакции)
```python
async def run_migration_with_rollback() -> None:
    """
    Миграция с автоматическим откатом при ошибке.
    """
    async with get_db_session() as session:
        try:
            # Выполняем изменения
            await session.execute(text("ALTER TABLE my_table ADD COLUMN test_col INT"))
            await session.commit()
            logger.info("✅ Миграция применена")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Миграция откачена: {e}")
            raise
```

### 2. Ручной откат (для критических изменений)
```python
async def rollback_migration(migration_id: str) -> None:
    """
    Ручной откат миграции.
    """
    logger.warning(f"⚠️ Откатываем миграцию: {migration_id}")

    async with get_db_session() as session:
        try:
            # Выполняем откат
            if migration_id == "130_data_constraints":
                await session.execute(text("ALTER TABLE ohlcv_p DROP CONSTRAINT IF EXISTS chk_ohlcv_p_volume_positive"))
                logger.info("✅ Ограничения удалены")

            # Обновляем статус в schema_migrations
            update_q = text("""
                UPDATE schema_migrations
                SET status = 'rolled_back', applied_at = NOW()
                WHERE migration_id = :migration_id
            """)
            await session.execute(update_q, {"migration_id": migration_id})

            await session.commit()
            logger.info(f"✅ Миграция {migration_id} откачена")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Ошибка отката: {e}")
            raise
```

### 3. Откат через CLI
```bash
# Откат конкретной миграции
python -c "
import asyncio
from src.db.migration_runner import rollback_migration
asyncio.run(rollback_migration('130_data_constraints'))
"
```

## 📊 Генерация отчётов

### Автоматический отчёт после миграции
```python
async def generate_migration_report(migration_id: str, duration_ms: int) -> Dict:
    """
    Генерирует отчёт о выполненной миграции.
    """
    async with get_db_session() as session:
        # Собираем статистику
        stats_q = text("""
            SELECT
                COUNT(*) as total_tables,
                SUM(pg_total_relation_size(schemaname||'.'||tablename)) as total_size_bytes
            FROM pg_tables
            WHERE schemaname = 'public'
        """)
        result = await session.execute(stats_q)
        stats = result.fetchone()

        # Проверяем индексы
        index_q = text("SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public'")
        result = await session.execute(index_q)
        index_count = result.scalar()

        return {
            "migration_id": migration_id,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
            "database_stats": {
                "total_tables": stats[0],
                "total_size_mb": round(stats[1] / 1024 / 1024, 2),
                "total_indexes": index_count
            },
            "recommendations": [
                "VACUUM ANALYZE для обновления статистики",
                "REINDEX для фрагментированных индексов",
                "Проверка размера логов"
            ]
        }
```

### Запуск отчёта
```bash
# Генерация отчёта о последней миграции
python -c "
import asyncio
from src.db.migration_runner import generate_migration_report
report = asyncio.run(generate_migration_report('140_operational_reliability', 1500))
print(report)
"
```

## 🔧 Лучшие практики

### 1. Всегда используйте транзакции
```python
async with get_db_session() as session:
    try:
        # Ваши изменения
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise
```

### 2. Проверяйте существование перед созданием
```sql
-- Для таблиц
CREATE TABLE IF NOT EXISTS my_table (...);

-- Для колонок
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE ...) THEN
        ALTER TABLE my_table ADD COLUMN new_col TYPE;
    END IF;
END $$;

-- Для индексов
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table_name (column);
```

### 3. Используйте CONCURRENTLY для индексов
```sql
-- Не блокирует таблицу
CREATE INDEX CONCURRENTLY idx_ohlcv_symbol_timeframe
ON ohlcv (symbol, timeframe);

-- Блокирует таблицу (избегайте)
CREATE INDEX idx_ohlcv_symbol_timeframe
ON ohlcv (symbol, timeframe);
```

### 4. Логируйте все операции
```python
logger.info("🔄 Начинаем миграцию...")
logger.info(f"📊 Текущее состояние: {current_stats}")
logger.info("✅ Миграция завершена успешно")
logger.error(f"❌ Ошибка: {error}")
```

### 5. Тестируйте миграции
```bash
# Запуск тестов после миграции
python run_migration_tests.py

# Проверка схемы
python -c "
import asyncio
from src.db.schema_validation import validate_schema
asyncio.run(validate_schema())
"
```

## 🚨 Частые проблемы и решения

### Проблема: Миграция зависла
```bash
# Проверка активных транзакций
SELECT pid, state, query FROM pg_stat_activity WHERE state = 'active';

# Принудительное завершение (осторожно!)
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active';
```

### Проблема: Недостаточно места
```bash
# Проверка размера БД
SELECT pg_size_pretty(pg_database_size('pklpo'));

# Очистка старых данных
DELETE FROM ohlcv WHERE timestamp < extract(epoch from now() - interval '1 year');
VACUUM ANALYZE ohlcv;
```

### Проблема: Блокировки
```sql
-- Проверка блокировок
SELECT
    l.pid,
    l.mode,
    l.granted,
    a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE NOT l.granted;
```

## 🖥️ CLI интерфейсы

### 📊 CLI для отчётов (`reports_cli.py`)

#### Статус миграций
```bash
# Общий статус
python src/db/reports_cli.py status

# Детальный отчёт
python src/db/reports_cli.py report
```

#### Здоровье системы
```bash
# Проверка здоровья
python src/db/reports_cli.py health

# Статистика БД
python src/db/reports_cli.py stats

# Метрики производительности
python src/db/reports_cli.py performance
```

### 📈 CLI для мониторинга (`monitoring_cli.py`)

#### Сбор и просмотр метрик
```bash
# Сбор метрик
python src/db/monitoring_cli.py collect

# Просмотр метрик за последние 24 часа
python src/db/monitoring_cli.py metrics --hours 24

# Экспорт метрик в JSON
python src/db/monitoring_cli.py export --output metrics.json

# Prometheus метрики
python src/db/monitoring_cli.py prometheus
```

#### Алерты и логи
```bash
# Просмотр всех алертов
python src/db/monitoring_cli.py alerts

# Фильтр по уровню важности
python src/db/monitoring_cli.py alerts --severity error

# Логи блокировок
python src/db/monitoring_cli.py locks --hours 24
```

#### Управление системой
```bash
# Мониторинг блокировок
python src/db/monitoring_cli.py monitor

# Обновление материализованных представлений
python src/db/monitoring_cli.py refresh
```

### 🧪 CLI для тестирования

#### Запуск тестов
```bash
# Полный тест-сьют
python run_migration_tests.py

# CI/CD режим
python run_migration_tests.py --ci

# С подробным отчётом
python run_migration_tests.py --report test_report.json --verbose
```

## 📞 Поддержка

### Полезные команды
```bash
# Статус миграций
python src/db/reports_cli.py status

# Проверка схемы
python -c "import asyncio; from src.db.schema_validation import validate_schema; asyncio.run(validate_schema())"

# Мониторинг
python src/db/monitoring_cli.py collect
```

### Логи и отладка
- Логи миграций: `migration_runner.log`
- Логи тестов: `migration_tests.log`
- Отчёты: `migration_test_report.json`
- Отчёты о миграциях: `src/db/reports/`

## 🆕 Новые возможности (Этапы 8-9)

### ✅ Этап 8: Миграции по содержимому

#### Очистка и нормализация данных
```bash
# Запуск очистки данных
python src/main_v2.py --migrations
```

**Возможности:**
- 🧹 Удаление дубликатов из `ohlcv_p` и `indicators_p`
- 🔧 Исправление неверных таймфреймов (`1Mutc` → `1M`)
- ✅ Валидация цен (положительные значения, корректные спреды)
- 📊 Валидация объемов (неотрицательные значения)
- 🗑️ Удаление записей с NULL timestamp
- 📈 Создание дополнительных индексов для оптимизации

#### Материализованные представления

**Доступные представления:**
```sql
-- Статистика по символам и таймфреймам
SELECT symbol, timeframe, total_records, avg_volume, avg_spread
FROM mv_symbol_stats
WHERE total_records > 1000;

-- Последние цены для каждого символа
SELECT symbol, timeframe, close, volume, timestamp
FROM mv_latest_prices
ORDER BY timestamp DESC;

-- Дневная агрегация OHLCV данных
SELECT symbol, trade_date, day_open, day_high, day_low, day_close, day_volume
FROM mv_daily_aggregation
WHERE trade_date >= CURRENT_DATE - INTERVAL '7 days';

-- Метрики волатильности по дням
SELECT symbol, timeframe, day, avg_daily_change, volatility
FROM mv_volatility
WHERE day >= CURRENT_DATE - INTERVAL '30 days';

-- Топ активных символов за последние 7 дней
SELECT symbol, total_records, total_volume, avg_volume
FROM mv_top_symbols
LIMIT 20;

-- Метрики качества данных
SELECT table_name, total_records, unique_symbols, negative_volumes, invalid_spreads
FROM mv_data_quality;
```

**Примеры аналитических запросов:**
```sql
-- Найти символы с высокой волатильностью
SELECT symbol, AVG(volatility) as avg_volatility
FROM mv_volatility
WHERE day >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY symbol
HAVING AVG(volatility) > 0.05
ORDER BY avg_volatility DESC;

-- Сравнить объемы торгов по дням недели
SELECT
    EXTRACT(DOW FROM trade_date) as day_of_week,
    AVG(day_volume) as avg_volume
FROM mv_daily_aggregation
WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY day_of_week
ORDER BY day_of_week;

-- Найти символы с проблемами качества данных
SELECT symbol,
       COUNT(*) as total_records,
       SUM(CASE WHEN volume < 0 THEN 1 ELSE 0 END) as negative_volumes
FROM ohlcv_p
GROUP BY symbol
HAVING SUM(CASE WHEN volume < 0 THEN 1 ELSE 0 END) > 0;
```

### ✅ Этап 9: Мониторинг и метрики

#### Система мониторинга
```bash
# CLI для мониторинга
python src/db/monitoring_cli.py --help

# Сбор метрик
python src/db/monitoring_cli.py collect

# Просмотр алертов
python src/db/monitoring_cli.py alerts

# Просмотр метрик
python src/db/monitoring_cli.py metrics --hours 24

# Логи блокировок
python src/db/monitoring_cli.py locks --hours 24

# Экспорт метрик
python src/db/monitoring_cli.py export --output metrics.json

# Prometheus метрики
python src/db/monitoring_cli.py prometheus

# Мониторинг блокировок
python src/db/monitoring_cli.py monitor

# Обновление представлений
python src/db/monitoring_cli.py refresh
```

#### Компоненты системы мониторинга

**Таблицы мониторинга:**
- 📊 **migration_logs** - Логи выполнения миграций с детальной информацией
- 🔒 **lock_logs** - Логи блокировок и их длительности
- 📈 **performance_metrics** - Метрики производительности БД
- 🚨 **alerts** - Система алертов с уровнями важности (info, warning, error, critical)

**Представления и функции:**
- 📊 **prometheus_metrics** - Prometheus-совместимые метрики
- 🔧 **collect_performance_metrics()** - Автоматический сбор метрик
- 🔍 **monitor_locks()** - Мониторинг блокировок в реальном времени
- 📤 **export_metrics_json()** - Экспорт метрик в JSON формат

**Автоматические алерты:**
- ❌ **Неудачные миграции** - автоматическое создание алертов при ошибках
- ⏰ **Длительные блокировки** - алерты для блокировок >30 секунд
- 📊 **Высокое потребление ресурсов** - мониторинг производительности
- 🔍 **Проблемы качества данных** - валидация целостности данных

#### Автоматические функции
```sql
-- Сбор метрик производительности
SELECT collect_performance_metrics();

-- Мониторинг блокировок
SELECT monitor_locks();

-- Обновление представлений
SELECT refresh_materialized_views();

-- Экспорт метрик в JSON
SELECT export_metrics_json();
```

#### Алерты
Система автоматически создает алерты для:
- ❌ Неудачных миграций
- ⏰ Длительных блокировок (>30 секунд)
- 📊 Высокого потребления ресурсов
- 🔍 Проблем с качеством данных

## ⚡ Производительность и оптимизация

### 🚀 Партиционирование
Система использует партиционирование по времени для оптимизации больших таблиц:

```sql
-- ohlcv_p партиционирована по дням
-- indicators_p партиционирована по месяцам
-- Автоматическое создание новых партиций
```

### 📊 Индексы
Оптимизированные индексы для быстрых запросов:

```sql
-- Составные индексы для основных запросов
CREATE INDEX CONCURRENTLY idx_ohlcv_p_symbol_timeframe_timestamp
ON ohlcv_p (symbol, timeframe, timestamp);

-- BRIN индексы для временных диапазонов
CREATE INDEX CONCURRENTLY idx_ohlcv_p_timestamp_brin
ON ohlcv_p USING BRIN (timestamp);

-- Частичные индексы для оптимизации
CREATE INDEX CONCURRENTLY idx_ohlcv_p_recent
ON ohlcv_p (symbol, timeframe)
WHERE timestamp >= extract(epoch from now() - interval '30 days');
```

### 🔄 Материализованные представления
Автоматическое обновление представлений:

```sql
-- Обновление всех представлений
SELECT refresh_materialized_views();

-- Автоматическое обновление при изменениях данных
-- Триггеры для критически важных представлений
```

### 📈 Мониторинг производительности
Постоянный мониторинг ключевых метрик:

- **Размер таблиц и индексов**
- **Cache hit ratio**
- **Активные подключения**
- **Медленные запросы**
- **Блокировки и их длительность**

## 🔧 Интеграция с внешними системами

### 📊 Prometheus
Готовность к интеграции с системами мониторинга:

```bash
# Экспорт метрик в Prometheus формате
python src/db/monitoring_cli.py prometheus

# Метрики доступны через представление prometheus_metrics
```

### 📤 JSON API
Экспорт данных для внешних систем:

```bash
# Экспорт метрик в JSON
python src/db/monitoring_cli.py export --output metrics.json

# Структурированные отчёты
python src/db/reports_cli.py report
```

### 🔗 CI/CD интеграция
Готовность к автоматизации:

```bash
# CI/CD режим тестирования
python run_migration_tests.py --ci

# Автоматическая проверка здоровья
python src/db/reports_cli.py health
```

---

**🎯 Помните: Всегда тестируйте миграции на staging перед production!**

**📚 Дополнительная документация:**
- [Отчёт о завершении Этапов 8-9](reports/STAGES_8_9_COMPLETION_SUMMARY.md)
- [Тестирование миграций](reports/MIGRATION_TESTING_SUMMARY.md)
