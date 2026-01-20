# 🗺️ Карта директорий Features Module

> Полная визуализация структуры с описанием назначения каждого файла

---

## 📊 Общая статистика

| Метрика | Значение |
|---------|----------|
| Всего файлов | 47+ |
| Python модулей | 45 |
| Строк кода | ~15,000+ |
| Документации | 3 MD файла |
| Тестов | 38 файлов |

---

## 🌳 Полная структура с описаниями

```
src/features/
│
├── 📄 __init__.py (31 строк)
│   └── Инициализация пакета, экспорт публичных API
│
├── 📄 __main__.py (12 строк)
│   └── Entry point для `python -m features`
│
├── 🎯 core.py (687 строк) ⭐ КРИТИЧНЫЙ
│   └── Главный модуль расчёта индикаторов
│   └── Функция: calculate_features() - основной пайплайн
│   └── Оркестрация всего процесса калькуляции
│
├── 📊 calc.py (339 строк)
│   └── Вспомогательные функции расчёта
│   └── Batch калькуляции, агрегация данных
│
├── 💾 save.py (700 строк) ⭐ КРИТИЧНЫЙ
│   └── Сохранение результатов в БД
│   └── Функция: save_indicators() - запись в PostgreSQL
│   └── Обработка JSONB структур
│
├── 🔄 group_calculation.py (327 строк)
│   └── Batch обработка по группам индикаторов
│   └── Функция: run_pipeline() - групповой расчёт
│   └── Параллелизация и оптимизация
│
├── 📋 specs.py (1160 строк) ⭐ КРИТИЧНЫЙ
│   └── Спецификации всех индикаторов
│   └── Метаданные: параметры, группы, описания
│   └── Single source of truth для конфигурации
│
├── 🔐 ta_safe.py (671 строк) ⭐ КРИТИЧНЫЙ
│   └── Безопасные обёртки для TA-Lib
│   └── Обработка ошибок, null-значений
│   └── Fallback логика при сбоях
│
├── ✅ validation.py (438 строк)
│   └── Валидация входных данных
│   └── Проверка качества OHLCV
│   └── Data quality gates
│
├── 🔍 validators.py (373 строк)
│   └── Дополнительные валидаторы
│   └── Схемы проверки параметров
│
├── 📈 metrics.py (318 строк)
│   └── Метрики производительности
│   └── Мониторинг времени выполнения
│   └── Memory profiling
│
├── 🔄 versioning.py (676 строк)
│   └── Версионирование индикаторов
│   └── Tracking изменений параметров
│   └── Backward compatibility
│
├── ⚙️ config.py (213 строк)
│   └── Конфигурация приложения
│   └── Загрузка из .env и YAML
│   └── Settings management
│
├── 🎨 name_mapping.py (414 строк)
│   └── Маппинг имён индикаторов
│   └── Нормализация названий
│   └── Legacy → новый формат
│
├── ⏰ time_utils.py (289 строк)
│   └── Работа с временными метками
│   └── Timezone конвертация
│   └── Timeframe utilities
│
├── 🔧 utils.py (469 строк)
│   └── Общие утилиты
│   └── Helpers для обработки данных
│
├── 🔍 traceability.py (286 строк)
│   └── Отслеживание происхождения данных
│   └── Audit trail для расчётов
│
├── 🚨 error_handling.py (443 строк)
│   └── Кастомные исключения
│   └── Error recovery стратегии
│   └── Logging ошибок
│
├── 📝 logging_config.py (203 строк)
│   └── Настройка логирования
│   └── Structured logging setup
│   └── Log rotation
│
├── 💻 cli.py (461 строк)
│   └── Command-line интерфейс
│   └── Argparse команды
│   └── User interaction
│
├── 🎮 demo.py (318 строк)
│   └── Демонстрационный режим
│   └── Примеры использования
│   └── Quick start для разработчиков
│
├── 🏗️ backfill.py (458 строк)
│   └── Backfill исторических данных
│   └── Массовый пересчёт индикаторов
│
├── 🚪 gate_validation.py (362 строк)
│   └── Gate проверки перед расчётом
│   └── Pre-flight validations
│
├── 🧪 smoke_validation.py (419 строк)
│   └── Smoke тесты
│   └── Quick health checks
│
├── 🔧 code_validations.py (386 строк)
│   └── Валидация кода и структур
│
├── 🔄 upsert_optimizer.py (289 строк)
│   └── Оптимизация upsert операций
│   └── Batch SQL генерация
│
├── 🗃️ database_indexes.py (431 строк)
│   └── Управление индексами БД
│   └── Index creation/maintenance
│
├── 📊 calc_combinations.py (648 строк)
│   └── Комбинации индикаторов
│   └── Multi-timeframe расчёты
│
├── 🗂️ models.py (185 строк)
│   └── Pydantic модели данных
│   └── Data validation schemas
│
├── 🔧 indicator_utils.py (26 строк)
│   └── Утилиты для индикаторов
│
├── 📊 indicators_logging.py (239 строк)
│   └── Специализированное логирование индикаторов
│
├── 🎭 strategy.py (252 строк)
│   └── Торговые стратегии
│   └── Signal generation
│
├── 🛠️ audit_cli.py (231 строк)
│   └── CLI для аудита
│
├── 📋 audit_simple.py (189 строк)
│   └── Упрощённый аудит
│
├── 📚 README.md (566 строк)
│   └── Главная документация модуля
│
├── 📘 README_CURSOR.md (517 строк) ⭐
│   └── Гайд для Cursor IDE
│   └── Quick start, debugging, best practices
│
├── 📊 CURSOR_IDE_SETUP_REPORT.md (283 строк) ⭐
│   └── Отчёт об улучшениях для IDE
│
├── 🗂️ PROJECT_STRUCTURE.md (345 строк) ⭐
│   └── Визуализация структуры проекта
│
└── 📊 .coverage (55 строк)
    └── Coverage отчёт (генерируется pytest)

```

---

## 📁 Поддиректории

### 🧠 domain/ - Доменная логика

```
domain/
├── __init__.py
│   └── Экспорт доменных объектов
│
├── calculator.py ⭐
│   └── Core калькулятор индикаторов
│   └── Чистая бизнес-логика без зависимостей
│   └── Pure functions для расчётов
│
├── indicator_specs.py
│   └── Domain спецификации индикаторов
│   └── Business rules и ограничения
│
├── protocols.py
│   └── Интерфейсы (Python Protocols)
│   └── Контракты для имплементаций
│
└── README.md
    └── Документация domain layer
```

**Назначение:** Бизнес-логика без внешних зависимостей. Можно тестировать изолированно.

---

### 🔄 application/ - Прикладной слой

```
application/
├── __init__.py
│   └── Экспорт application services
│
├── batch_processor.py ⭐
│   └── Batch обработка больших датасетов
│   └── Chunking, параллелизация
│   └── Memory management
│
└── README.md
    └── Документация application layer
```

**Назначение:** Use cases, оркестрация бизнес-логики, координация между слоями.

---

### 🔌 infrastructure/ - Инфраструктурный слой

```
infrastructure/
├── __init__.py
│   └── Экспорт инфраструктурных сервисов
│
├── database.py ⭐
│   └── Подключение к PostgreSQL
│   └── Connection pooling (asyncpg)
│   └── Database context managers
│
├── db_operations.py ⭐
│   └── CRUD операции
│   └── Query builders
│   └── Transaction management
│
├── upsert_builder.py ⭐ КРИТИЧНЫЙ
│   └── Генерация SQL для upsert
│   └── Функция: build_and_execute_upsert()
│   └── Обработка конфликтов, JSONB merge
│
├── alerts.py
│   └── Алерты и нотификации
│   └── Slack/Email интеграция
│
├── diagnostics.py
│   └── Диагностика состояния системы
│   └── Health checks
│
├── indicator_registry.py
│   └── Реестр доступных индикаторов
│   └── Dynamic loading
│
├── insert_indicators.py
│   └── Вставка индикаторов в БД
│   └── Bulk insert оптимизация
│
└── README.md
    └── Документация infrastructure layer
```

**Назначение:** Работа с внешними системами (БД, API, файлы). Изолирует бизнес-логику от технических деталей.

---

### 📊 indicator_groups/ - Группы индикаторов

```
indicator_groups/
├── __init__.py
│   └── Экспорт всех индикаторов
│
├── ma.py ⭐
│   └── Moving Averages (SMA, EMA, WMA, VWMA)
│   └── ~15 различных MA
│
├── oscillators.py ⭐
│   └── Осцилляторы (RSI, Stoch, CCI, Williams %R)
│   └── Momentum индикаторы
│
├── volatility.py ⭐
│   └── Волатильность (ATR, BB, Keltner, Donchian)
│   └── Range-based индикаторы
│
├── overlap.py
│   └── Overlapping индикаторы
│   └── Price-based индикаторы
│
├── trend.py
│   └── Трендовые индикаторы (ADX, MACD, Ichimoku)
│   └── Trend strength/direction
│
├── volume.py
│   └── Объёмные индикаторы (OBV, MFI, VWAP)
│   └── Volume analysis
│
├── squeeze.py
│   └── Squeeze индикаторы (TTM Squeeze)
│   └── Compression/expansion patterns
│
├── statistics.py
│   └── Статистические индикаторы
│   └── Standard deviation, Z-score
│
├── performance.py
│   └── Performance метрики
│   └── Returns, drawdown, Sharpe
│
├── candles.py
│   └── Candlestick patterns
│   └── Pattern recognition
│
├── data_cleaner.py
│   └── Очистка данных перед расчётом
│   └── Outlier detection
│
├── debug_utils.py
│   └── Утилиты для отладки
│
└── README.md
    └── Документация индикаторов
```

**Назначение:** Имплементация всех технических индикаторов. Каждый файл = группа схожих индикаторов.

---

### 💻 cli/ - Command-line интерфейс

```
cli/
├── __init__.py
│   └── CLI namespace
│
├── schema_check.py
│   └── Проверка схемы БД
│   └── Валидация структуры таблиц
│
└── check_database_setup.py
    └── Проверка настройки БД
    └── Connection test, permissions
```

**Назначение:** CLI команды для операций с БД, проверок, backfill.

---

### 🗄️ schema/ - Схемы данных

```
schema/
├── __init__.py
│   └── Schema namespace
│
├── schema_manager.py ⭐
│   └── Управление схемами
│   └── Загрузка, валидация, обновление
│
├── indicators_schema.yml
│   └── Основная схема индикаторов
│   └── YAML определения
│
├── indicators_schema_clean.yml
│   └── Очищенная версия схемы
│
└── indicators_schema_complete.yml
    └── Полная версия со всеми метаданными
```

**Назначение:** Определение структуры данных индикаторов в YAML. Single source of truth.

---

### 🧪 tests/ - Тесты

```
tests/
├── __init__.py
│   └── Test namespace
│
├── test_core.py ⭐
│   └── Тесты core.py
│   └── Основной пайплайн
│
├── test_indicators.py ⭐
│   └── Тесты индикаторов
│   └── Каждая группа индикаторов
│
├── test_ta_safe.py
│   └── Тесты ta_safe оберток
│
├── test_validation.py
│   └── Тесты валидации
│
├── test_save.py
│   └── Тесты сохранения в БД
│
├── test_upsert_builder.py ⭐
│   └── Тесты SQL генерации
│
├── test_database.py
│   └── Интеграционные тесты БД
│
├── test_batch_processor.py
│   └── Тесты batch обработки
│
└── ... (30+ других тестов)
    └── Покрытие всех модулей
```

**Назначение:** Unit, integration, smoke тесты. Минимум 85% coverage.

---

### 🔧 utils/ - Вспомогательные утилиты

```
utils/
├── __init__.py
│   └── Utils namespace
│
└── memlog.py
    └── Memory logging и profiling
    └── Track memory usage
```

**Назначение:** Общие утилиты, helpers.

---

### 🛠️ tools/ - Инструменты разработчика

```
tools/
├── __init__.py
│   └── Tools namespace
│
└── generate_schema.py
    └── Генерация schema из кода
    └── Автоматическое обновление YAML
```

**Назначение:** Dev tools, скрипты для автоматизации.

---

### 📚 README/ - Документация

```
README/
├── __init__.py (новый)
│   └── Documentation namespace
│
├── ARCHITECTURE_INDEX.md ⭐
│   └── Индекс архитектурной документации
│
├── ARCHITECTURE_DIAGRAMS.md
│   └── Диаграммы архитектуры
│
├── COMPREHENSIVE_DOCUMENTATION.md
│   └── Полная документация API
│
├── IMPLEMENTATION_ROADMAP.md
│   └── Roadmap имплементации
│
├── VERSIONING_GUIDE.md
│   └── Гайд по версионированию
│
├── AIRFLOW_ALERTING_GUIDE.md
│   └── Настройка алертов в Airflow
│
├── db_inidicators_description.md
│   └── Описание индикаторов в БД
│
├── README_name_mapping.md
│   └── Документация name mapping
│
└── ... (15+ документов)
```

**Назначение:** Вся документация проекта, гайды, roadmap.

---

### 📄 reports/ - Отчёты

```
reports/
├── __init__.py (новый)
│   └── Reports namespace
│
├── CHANGELOG.md
│   └── История изменений
│
├── FINAL_TEST_REPORT.md
│   └── Финальный отчёт по тестам
│
├── PRODUCTION_READINESS_CHECKLIST.md
│   └── Чеклист готовности к prod
│
├── SMOKE_TESTING_REPORT.md
│   └── Результаты smoke тестов
│
├── MEMORY_OPTIMIZATION_REPORT.md
│   └── Отчёт по оптимизации памяти
│
├── TODO.md
│   └── Список задач
│
└── ... (15+ отчётов)
```

**Назначение:** Отчёты по тестам, производительности, completion reports.

---

## 🔗 Связи между модулями

### Граф зависимостей (упрощённый)

```
cli.py
  └── core.py ⭐
        ├── domain/calculator.py
        ├── indicator_groups/* (все индикаторы)
        ├── ta_safe.py
        ├── validation.py
        └── save.py ⭐
              └── infrastructure/
                    ├── database.py
                    └── upsert_builder.py ⭐

group_calculation.py
  ├── core.py (использует)
  ├── application/batch_processor.py
  └── metrics.py

specs.py (используется везде)
  └── Центральный источник метаданных
```

---

## 🎯 Критичные файлы (Top-10)

| Файл | Строк | Важность | Назначение |
|------|-------|----------|------------|
| `core.py` | 687 | 🔴 Critical | Главный пайплайн |
| `save.py` | 700 | 🔴 Critical | Сохранение в БД |
| `specs.py` | 1160 | 🔴 Critical | Метаданные индикаторов |
| `ta_safe.py` | 671 | 🔴 Critical | TA-Lib обёртки |
| `upsert_builder.py` | ? | 🔴 Critical | SQL генерация |
| `versioning.py` | 676 | 🟠 High | Версионирование |
| `calc_combinations.py` | 648 | 🟠 High | MTF расчёты |
| `cli.py` | 461 | 🟠 High | CLI интерфейс |
| `backfill.py` | 458 | 🟠 High | Backfill данных |
| `error_handling.py` | 443 | 🟡 Medium | Обработка ошибок |

---

## 📊 Распределение по назначению

```
Бизнес-логика (30%)
├── domain/
├── indicator_groups/
└── core.py, calc.py

Infrastructure (20%)
├── infrastructure/
├── save.py
└── database_indexes.py

Утилиты (25%)
├── validation.py
├── validators.py
├── utils.py
├── time_utils.py
└── name_mapping.py

CLI/User Interface (10%)
├── cli.py
├── cli/
└── demo.py

Тесты (10%)
└── tests/

Документация (5%)
├── README/
└── reports/
```

---

## 🚀 Точки входа (Entry Points)

| Команда | Файл | Описание |
|---------|------|----------|
| `python -m features.core` | `__main__.py` → `core.py` | Главный расчёт |
| `python -m features.cli` | `cli.py` | CLI команды |
| `python -m features.demo` | `demo.py` | Демо режим |
| `python -m features.group_calculation` | `group_calculation.py` | Batch режим |
| `pytest tests/` | `tests/` | Запуск тестов |

---

## 🔍 Поиск по функциональности

### Хочу найти код для...

| Задача | Смотри файл |
|--------|-------------|
| Добавить новый индикатор | `indicator_groups/` + `specs.py` |
| Изменить логику расчёта | `core.py` + `domain/calculator.py` |
| Оптимизировать БД запросы | `infrastructure/upsert_builder.py` |
| Добавить валидацию | `validation.py` + `validators.py` |
| Исправить ошибку TA-Lib | `ta_safe.py` |
| Изменить схему БД | `schema/` + `database_indexes.py` |
| Добавить метрики | `metrics.py` |
| Backfill данных | `backfill.py` |
| Тестировать изменения | `tests/test_*.py` |

---

## 📈 Статистика по размеру

| Категория | Файлов | Строк кода |
|-----------|--------|------------|
| Core модули | 10 | ~4,500 |
| Indicator groups | 12 | ~3,000 |
| Infrastructure | 7 | ~2,000 |
| Validation/Utils | 15 | ~3,500 |
| Tests | 38 | ~8,000+ |
| Documentation | 30+ | ~5,000 |
| **ИТОГО** | **100+** | **~26,000** |

---

## 🎓 Для новых разработчиков

### Начни с этих файлов:

1. **README.md** - общее понимание
2. **README_CURSOR.md** - setup IDE
3. **core.py** - главная логика (читай сначала docstrings)
4. **specs.py** - метаданные (посмотри структуру)
5. **indicator_groups/ma.py** - пример индикаторов
6. **tests/test_core.py** - примеры использования

### Workflow разработки:

```
1. Понять требование
   ↓
2. Найти нужный файл (эта карта)
   ↓
3. Изучить tests/ для примеров
   ↓
4. Сделать изменения
   ↓
5. Добавить/обновить тесты
   ↓
6. Запустить валидацию (ruff, mypy, pytest)
   ↓
7. Обновить документацию
```

---

## 🔄 Последнее обновление

**Дата:** 2025-10-29
**Автор:** Development Team
**Версия:** 1.0.0

---

**Используй этот файл как навигационную карту проекта!**
