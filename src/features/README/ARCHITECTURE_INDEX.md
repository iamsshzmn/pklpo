# Индекс Архитектурной Документации

## 📚 Навигация по документации модуля Features

---

## 🎯 Для быстрого старта

### Я новый разработчик, с чего начать?

1. **Начните здесь** → [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md)
   - Визуальные диаграммы
   - Простые схемы
   - Быстрое понимание системы

2. **Затем прочитайте** → [`README.md`](./README.md)
   - Основная документация
   - Примеры использования
   - Quick start guide

3. **Для деталей** → [`ARCHITECTURE_VISUALIZATION.md`](./ARCHITECTURE_VISUALIZATION.md)
   - Подробная архитектура
   - Все компоненты
   - Взаимодействия

4. **Детальная техническая информация** → [`COMPREHENSIVE_DOCUMENTATION.md`](./COMPREHENSIVE_DOCUMENTATION.md)
   - Полная техническая документация
   - Все модули и функции
   - Best practices

---

## 📖 Полный список документации

### Архитектурная документация (Architecture)

| Документ | Назначение | Аудитория |
|----------|-----------|-----------|
| **ARCHITECTURE_INDEX.md** (этот файл) | Навигация по документации | Все |
| **ARCHITECTURE_DIAGRAMS.md** | Визуальные диаграммы и схемы | Новые разработчики |
| **ARCHITECTURE_VISUALIZATION.md** | Подробная визуализация архитектуры | Архитекторы, Senior Dev |
| **COMPONENT_MAP.md** | Карта компонентов и зависимостей | Разработчики |
| **../reports/ARCHITECTURE.md** | Отчет по архитектуре | Tech Leads |

### Основная документация (Main Docs)

| Документ | Назначение | Аудитория |
|----------|-----------|-----------|
| **README.md** | Главная документация модуля | Все разработчики |
| **COMPREHENSIVE_DOCUMENTATION.md** | Полная техническая документация | Все разработчики |
| **README_name_mapping.md** | Маппинг имен индикаторов | Data Engineers |
| **db_indicators_description.md** | Описание БД схемы | Database Team |

### Отчеты и чеклисты (Reports)

| Документ | Назначение | Аудитория |
|----------|-----------|-----------|
| **../reports/PRODUCTION_READINESS_CHECKLIST.md** | Production readiness | DevOps, QA |
| **../reports/MEMORY_OPTIMIZATION_REPORT.md** | Оптимизация памяти | Performance Team |
| **../reports/SMOKE_TESTING_REPORT.md** | Smoke testing результаты | QA Team |
| **../reports/TESTING.md** | Руководство по тестированию | QA, Developers |
| **../reports/QUICKSTART.md** | Быстрый старт | Все |

### Миграции и изменения (Migrations & Changes)

| Документ | Назначение | Аудитория |
|----------|-----------|-----------|
| **../reports/CHANGELOG.md** | История изменений | Все |
| **../reports/MIGRATION.md** | Руководство по миграции | DevOps |

### Специализированная документация (Specialized)

| Документ | Назначение | Аудитория |
|----------|-----------|-----------|
| **../domain/README.md** | Domain layer документация | Backend Developers |
| **../application/README.md** | Application layer документация | Backend Developers |
| **../infrastructure/README.md** | Infrastructure layer документация | Infrastructure Team |
| **../indicator_groups/README.md** | Документация групп индикаторов | Quant Developers |

---

## 🗺️ Карта модуля (Module Map)

```
features/
│
├── 📘 DOCUMENTATION (Вы здесь: README/)
│   └── README/
│       ├── ARCHITECTURE_INDEX.md ◄── Вы здесь
│       ├── ARCHITECTURE_DIAGRAMS.md
│       ├── ARCHITECTURE_VISUALIZATION.md
│       ├── COMPONENT_MAP.md
│       ├── README.md
│       ├── COMPREHENSIVE_DOCUMENTATION.md
│       ├── README_name_mapping.md
│       └── db_indicators_description.md
│
├── 🎯 ENTRY POINTS
│   ├── core.py                    ← Главный API
│   ├── __init__.py                ← Python package entry
│   ├── __main__.py                ← CLI entry
│   └── cli.py                     ← CLI commands
│
├── 🏗️ LAYERS
│   ├── domain/                    ← Business logic
│   ├── application/               ← Orchestration
│   ├── infrastructure/            ← External systems
│   └── indicator_groups/          ← Calculations
│
├── 🛡️ QUALITY
│   ├── validators.py
│   ├── validation.py
│   ├── gate_validation.py
│   └── code_validations.py
│
├── ⚙️ CONFIGURATION
│   ├── specs.py                   ← 500+ indicator specs
│   ├── models.py                  ← Data models
│   └── config.py                  ← System config
│
└── 🧪 TESTS
    └── tests/                     ← 20+ test modules
```

---

## 🎓 Обучающие маршруты (Learning Paths)

### Путь 1: Я хочу использовать модуль (User Path)

```
1. README/README.md
   └─► Понять, что модуль делает и как его использовать

2. ARCHITECTURE_DIAGRAMS.md (Section: "Использование")
   └─► Увидеть примеры кода и patterns

3. Пробуйте!
   └─► Используйте compute_features() в своем коде
```

### Путь 2: Я хочу понять архитектуру (Architecture Path)

```
1. ARCHITECTURE_DIAGRAMS.md
   └─► Визуальное понимание системы

2. ARCHITECTURE_VISUALIZATION.md
   └─► Детальное понимание компонентов

3. reports/ARCHITECTURE.md
   └─► Решения и обоснования дизайна

4. Изучите код (core.py → group_calculation.py → indicator_groups/)
   └─► Практическое понимание
```

### Путь 3: Я хочу разрабатывать (Developer Path)

```
1. README/COMPREHENSIVE_DOCUMENTATION.md
   └─► Полная техническая информация

2. ARCHITECTURE_VISUALIZATION.md
   └─► Понять структуру и зависимости

3. Прочитайте READMEs в каждом слое:
   ├─► domain/README.md
   ├─► application/README.md
   ├─► infrastructure/README.md
   └─► indicator_groups/README.md

4. Изучите тесты (tests/)
   └─► Примеры использования и edge cases

5. reports/TESTING.md
   └─► Как тестировать свои изменения
```

### Путь 4: Я хочу добавить новый индикатор (Contributor Path)

```
1. indicator_groups/README.md
   └─► Понять структуру групп

2. specs.py
   └─► Изучить существующие спецификации

3. Выберите группу (ma, oscillators, volatility, etc.)
   └─► Откройте соответствующий файл в indicator_groups/

4. Добавьте спецификацию в specs.py
   └─► Определите параметры индикатора

5. Реализуйте расчет в соответствующей группе
   └─► Следуйте паттерну существующих индикаторов

6. Добавьте тесты
   └─► tests/test_<group>.py

7. reports/TESTING.md
   └─► Запустите тесты
```

### Путь 5: Я DevOps / Infrastructure (DevOps Path)

```
1. ARCHITECTURE_DIAGRAMS.md (Section: "Airflow Integration")
   └─► Понять интеграцию с Airflow

2. infrastructure/README.md
   └─► Database, deployment, infrastructure

3. reports/PRODUCTION_READINESS_CHECKLIST.md
   └─► Production requirements

4. reports/MIGRATION.md
   └─► Deployment и миграция

5. calc_indicators.py
   └─► Entry point для Airflow
```

---

## 🔍 Быстрый поиск по темам

### Расчет индикаторов (Calculation)

- **Главный API**: `core.py` → `compute_features()`
- **Групповой расчет**: `group_calculation.py`
- **Streaming**: `calc.py`
- **Индикаторы**: `indicator_groups/`
- **Спецификации**: `specs.py`

Документация:
- [`ARCHITECTURE_VISUALIZATION.md`](./ARCHITECTURE_VISUALIZATION.md) → "Поток Данных"
- [`COMPREHENSIVE_DOCUMENTATION.md`](./COMPREHENSIVE_DOCUMENTATION.md) → "Core Module"

### База данных (Database)

- **Подключение**: `infrastructure/database.py`
- **Чтение**: `infrastructure/db_operations.py`
- **Запись**: `infrastructure/insert_indicators.py`
- **UPSERT**: `infrastructure/upsert_builder.py`

Документация:
- [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md) → "Database Integration"
- [`../infrastructure/README.md`](../infrastructure/README.md)

### Валидация (Validation)

- **Схема и данные**: `validators.py`
- **Временные метки**: `time_utils.py`
- **Quality gates**: `gate_validation.py`
- **Проверки кода**: `code_validations.py`

Документация:
- [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md) → "Error Handling & Validation"
- [`ARCHITECTURE_VISUALIZATION.md`](./ARCHITECTURE_VISUALIZATION.md) → "Validation & Quality Gates"

### Метрики (Metrics)

- **Сбор метрик**: `metrics.py`
- **Логирование**: `logging_config.py`
- **Специальное логирование**: `indicators_logging.py`

Документация:
- [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md) → "Metrics & Monitoring"

### Airflow интеграция (Airflow)

- **Entry point**: `calc_indicators.py`
- **Batch processing**: `application/batch_processor.py`

Документация:
- [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md) → "Airflow Integration"
- [`COMPREHENSIVE_DOCUMENTATION.md`](./COMPREHENSIVE_DOCUMENTATION.md) → "Airflow Integration"

### Тестирование (Testing)

- **Тесты**: `tests/`
- **Smoke tests**: `smoke_validation.py`

Документация:
- [`../reports/TESTING.md`](../reports/TESTING.md)
- [`../reports/SMOKE_TESTING_REPORT.md`](../reports/SMOKE_TESTING_REPORT.md)

---

## 📊 Статистика модуля

### Размер кодовой базы

```
Модуль features:
├── Python файлов:      44+
├── Строк кода:         ~15,000
├── Групп индикаторов:  10
├── Индикаторов:        500+
├── Тестовых файлов:    25+
└── Документов:         30+
```

### Покрытие функциональности

```
✅ Moving Averages:     30+ индикаторов
✅ Oscillators:         40+ индикаторов
✅ Volatility:          20+ индикаторов
✅ Volume:              15+ индикаторов
✅ Trend:               40+ индикаторов
✅ Candles:             80+ паттернов
✅ Squeeze:             10+ индикаторов
✅ Statistics:          20+ метрик
✅ Performance:         15+ метрик
✅ Overlap:             10+ индикаторов
```

---

## 🏆 Best Practices

### При использовании модуля

1. **Всегда валидируйте входные данные**
   - Используйте `validate_ohlcv_data()` перед расчетом

2. **Учитывайте размер данных**
   - < 100k строк → используйте `compute_features()`
   - \> 100k строк → используйте streaming из `calc.py`

3. **Обрабатывайте ошибки**
   - Используйте try-except для `FeatureError`
   - Проверяйте quality gates результаты

4. **Следите за метриками**
   - Проверяйте fill_rate индикаторов
   - Мониторьте NaN ratio

### При разработке модуля

1. **Следуйте архитектуре**
   - Соблюдайте слоистую структуру
   - Не нарушайте зависимости между слоями

2. **Добавляйте тесты**
   - Unit tests для новых функций
   - Integration tests для новых групп

3. **Документируйте код**
   - Docstrings для всех публичных функций
   - Type hints везде

4. **Проверяйте качество**
   - Запускайте linters
   - Проверяйте test coverage
   - Используйте smoke tests

---

## 🆘 Получение помощи

### У меня проблема, что делать?

1. **Проверьте документацию**
   - Ищите по этому индексу
   - Читайте error messages

2. **Проверьте тесты**
   - `tests/` содержат много примеров

3. **Проверьте логи**
   - Модуль имеет подробное логирование
   - Используйте уровень DEBUG для деталей

4. **Проверьте smoke tests**
   - `smoke_validation.py` для production checks

### Часто задаваемые вопросы (FAQ)

**Q: Как добавить новый индикатор?**
A: См. "Путь 4: Contributor Path" выше

**Q: Почему расчеты медленные?**
A: Проверьте размер данных, возможно нужен streaming. См. `reports/MEMORY_OPTIMIZATION_REPORT.md`

**Q: Как работает online/offline parity?**
A: См. `ARCHITECTURE_VISUALIZATION.md` → "No Look-Ahead Bias"

**Q: Как интегрировать с Airflow?**
A: См. `ARCHITECTURE_DIAGRAMS.md` → "Airflow Integration"

**Q: Где находится схема БД?**
A: См. `README/db_indicators_description.md` и `infrastructure/database.py`

---

## 🔗 Внешние ресурсы

### Зависимости и библиотеки

- **pandas** - https://pandas.pydata.org/
- **pandas_ta** - https://github.com/twopirllc/pandas-ta
- **numpy** - https://numpy.org/
- **SQLAlchemy** - https://www.sqlalchemy.org/
- **PostgreSQL** - https://www.postgresql.org/

### Связанные проекты

- **Airflow DAGs**: `../../../ops/airflow/dags/features_calc.py`
- **Database Schema**: `../../../ops/airflow/sql/bootstrap_app_db.sql`
- **Configuration**: `../../../config/mtf_phase3*.yaml`

---

## 📝 Обратная связь

Если вы нашли проблему в документации или у вас есть предложения по улучшению:

1. Создайте issue с меткой `documentation`
2. Или отправьте Pull Request с исправлениями
3. Или обратитесь к мейнтейнерам напрямую

---

## 📅 История документации

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2025-10-27 | 1.0.0 | Создание архитектурной визуализации |
| 2025-10-27 | 1.0.0 | Добавление диаграмм и индекса |

---

**Последнее обновление:** 2025-10-27
**Версия модуля:** 1.0.0
**Статус:** ✅ Production Ready

---

## 🚀 Начните с этого

**Новый пользователь?** → [`README.md`](./README.md)

**Хотите понять архитектуру?** → [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md)

**Нужны детали?** → [`ARCHITECTURE_VISUALIZATION.md`](./ARCHITECTURE_VISUALIZATION.md)

**Карта компонентов?** → [`COMPONENT_MAP.md`](./COMPONENT_MAP.md)

**Готовы к разработке?** → [`COMPREHENSIVE_DOCUMENTATION.md`](./COMPREHENSIVE_DOCUMENTATION.md)

---

**Удачи в работе с модулем Features! 🎉**
