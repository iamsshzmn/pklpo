# Индекс файлов модуля `src/db`

## 📁 Структура модуля

```
src/db/
├── README.md                           # Основная документация
├── INDEX.md                            # Этот файл - индекс всех компонентов
├── __init__.py                         # Инициализация модуля
│
├── 🔧 Основные компоненты
├── migration_runner.py                 # Движок выполнения миграций
├── migration_registry.py               # Реестр всех миграций
├── schema_validation.py                # Валидация схемы БД
│
├── 📊 Отчёты и мониторинг
├── migration_reports.py                # Генерация отчётов о миграциях
├── reports_cli.py                      # CLI для работы с отчётами
├── monitoring_cli.py                   # CLI для системы мониторинга
│
├── 🧪 Тестирование
├── migration_testing.py                # Тест-сьют для миграций
├── run_migration_tests.py              # Скрипт запуска тестов
│
├── 🗄️ Миграции (по этапам)
├── migrate_create_schema_migrations.py # 001: Базовая инфраструктура
├── migrate_add_core_indexes.py         # 100: Основные индексы
├── migrate_create_ohlcv_partitioned.py # 101: Партиционирование OHLCV
├── migrate_create_indicators_partitioned.py # 102: Партиционирование индикаторов
├── migrate_backfill_partitioned.py     # 120: Перенос данных
├── migrate_add_data_constraints.py     # 130: Ограничения качества данных
├── migrate_add_operational_reliability.py # 140: Операционная надёжность
├── migrate_data_cleanup.py             # 150: Очистка и нормализация данных
├── migrate_materialized_views.py       # 160: Материализованные представления
├── migrate_monitoring_metrics.py       # 170: Система мониторинга
│
├── 📚 Устаревшие миграции (legacy)
├── migrate_create_ohlcv.py             # Старая версия OHLCV
├── migrate_create_indicators.py        # Старая версия индикаторов
├── migrate_create_mtf_v2_tables.py     # MTF таблицы
├── migrate_create_mtf_expanded.py      # Расширенные MTF таблицы
├── migrate_create_mtf_signals.py       # MTF сигналы
├── migrate_create_trade_recommendations.py # Рекомендации по торговле
├── migrate_create_score_results.py     # Результаты скоринга
├── migrate_fix_score_results_precision.py # Исправление точности
├── migrate_add_swap_fields_to_instruments.py # Поля свопов
├── migrate_create_positions.py         # Позиции
├── migrate_add_swap_fields.py          # Поля свопов (старая версия)
├── migrate_add_indexes.py              # Индексы (старая версия)
├── migrate_add_ema200.py               # EMA200
├── migrate_add_missing_columns.py      # Отсутствующие колонки
├── migrate_add_missing_ma_columns.py   # Отсутствующие MA колонки
├── migrate_add_ohlcv_to_indicators.py  # OHLCV в индикаторы
├── migrate_create_combination_results.py # Результаты комбинаций
├── migrate_create_signals.py           # Сигналы
├── migrate_create_signals_detailed.py  # Детальные сигналы
├── migrate_fix_combination_results_timezone.py # Исправление часовых поясов
├── migrate_cleanup_duplicate_columns.py # Очистка дубликатов колонок
├── migrate_fix_instrument_columns.py   # Исправление колонок инструментов
│
├── 🛠️ Утилиты
├── db_schema_utils.py                  # Утилиты для работы со схемой
│
├── 📊 Отчёты и документация
└── reports/
    ├── STAGES_8_9_COMPLETION_SUMMARY.md # Отчёт о завершении Этапов 8-9
    └── MIGRATION_TESTING_SUMMARY.md     # Отчёт о тестировании миграций
```

## 🎯 Основные компоненты

### 🔧 Ядро системы
- **`migration_runner.py`** - Основной движок для выполнения миграций
- **`migration_registry.py`** - Централизованный реестр всех миграций
- **`schema_validation.py`** - Валидация схемы базы данных

### 📊 Отчёты и мониторинг
- **`migration_reports.py`** - Генерация детальных отчётов о миграциях
- **`reports_cli.py`** - CLI для работы с отчётами (статус, здоровье, статистика)
- **`monitoring_cli.py`** - CLI для системы мониторинга (метрики, алерты, логи)

### 🧪 Тестирование
- **`migration_testing.py`** - Полный тест-сьют для миграций
- **`run_migration_tests.py`** - Скрипт для запуска тестов

## 🗄️ Миграции по этапам

### ✅ Этап 1: Базовая инфраструктура
- `migrate_create_schema_migrations.py` - Создание системы отслеживания миграций

### ✅ Этап 3: Индексация и производительность
- `migrate_add_core_indexes.py` - Основные индексы
- `migrate_create_ohlcv_partitioned.py` - Партиционирование OHLCV
- `migrate_create_indicators_partitioned.py` - Партиционирование индикаторов

### ✅ Этап 4: Качество данных и ограничения
- `migrate_add_data_constraints.py` - Ограничения качества данных

### ✅ Этап 5: Операционная надёжность
- `migrate_add_operational_reliability.py` - Функции надёжности

### ✅ Этап 8: Миграции по содержимому
- `migrate_data_cleanup.py` - Очистка и нормализация данных
- `migrate_materialized_views.py` - Материализованные представления

### ✅ Этап 9: Мониторинг и метрики
- `migrate_monitoring_metrics.py` - Система мониторинга

## 🚀 Быстрый старт

### Основные команды
```bash
# Запуск всех миграций
python src/main_v2.py --migrations

# Просмотр статуса
python src/db/reports_cli.py status

# Сбор метрик
python src/db/monitoring_cli.py collect

# Запуск тестов
python run_migration_tests.py
```

### Полезные ссылки
- [Основная документация](README.md)
- [Отчёт о завершении Этапов 8-9](reports/STAGES_8_9_COMPLETION_SUMMARY.md)
- [Тестирование миграций](reports/MIGRATION_TESTING_SUMMARY.md)

---

**📝 Примечание:** Файлы в разделе "Устаревшие миграции" сохранены для совместимости, но новые разработки должны использовать современные миграции из основных этапов.
