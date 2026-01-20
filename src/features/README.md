# Features Module

## 📊 Система расчета технических индикаторов

**Версия:** 1.1.0 | **Статус:** ✅ Production Ready

Модуль расчёта технических индикаторов с онлайн/офлайн паритетом и интеграцией с Airflow. Поддерживает централизованный реестр индикаторов, групповой расчёт без look-ahead, волатильностную нормировку, smoke-валидации и метрики.

---

## 🎯 Цели и возможности

Модуль `features` - это комплексная система для расчета 500+ технических индикаторов с поддержкой:

- ✅ **Online/Offline Parity** - одинаковые результаты в реальном времени и исторических расчетах
- ✅ **No Look-Ahead Bias** - предотвращение заглядывания в будущее
- ✅ **Memory-Efficient** - потоковая обработка больших данных
- ✅ **Production Ready** - интеграция с Airflow, качественные gates, метрики
- ✅ **Clean Architecture** - слоистая архитектура, легко расширяемая
- ✅ **Централизованный реестр** - единый источник спецификаций индикаторов
- ✅ **Quality Gates** - автоматическая валидация качества результатов

---

## 🚀 Быстрый старт

### Установка

```bash
pip install -r requirements.txt
```

### Новый API (рекомендуется)

```python
import pandas as pd
from features.core import compute_features

# Подготовьте OHLCV данные
df_ohlcv = pd.DataFrame({
    'timestamp': [1640995200, 1640998800, 1641002400],  # Unix timestamp или datetime
    'open': [100.0, 101.0, 102.0],
    'high': [102.0, 103.0, 104.0],
    'low': [99.0, 100.0, 101.0],
    'close': [101.0, 102.0, 103.0],
    'volume': [1000, 1100, 1200]
})

# Рассчитайте конкретные индикаторы
df_with_indicators = compute_features(
    df_ohlcv=df_ohlcv,
    specs=['ema_12', 'ema_26', 'rsi_14', 'macd', 'atr_14']
)

# Результат содержит OHLCV + рассчитанные индикаторы
print(df_with_indicators[['timestamp', 'close', 'ema_12', 'rsi_14']])

# Рассчитать с волатильностной нормализацией
df_normalized = compute_features(
    df_ohlcv,
    specs=["rsi_14", "atr_14", "ema_12"],
    volatility_normalize=True
)

# Рассчитать все доступные индикаторы
from features.infrastructure.indicator_registry import AVAILABLE_INDICATORS
df_all_features = compute_features(df_ohlcv, available=set(AVAILABLE_INDICATORS))
```

### Legacy API (deprecated)

```python
# DEPRECATED: используйте compute_features() вместо calc_indicators()
from features.indicator_utils import calc_indicators
df_features = calc_indicators(df_ohlcv, {"rsi_14", "atr_14"})  # Вызовет предупреждение
```

### CLI использование

```bash
# Расчет для одной пары
python -m features calculate --symbol BTC/USDT --timeframe 1h

# Список доступных индикаторов
python -m features list-indicators

# Информация об индикаторе
python -m features info rsi_14

# Через общий CLI проекта
python -m src.cli.main features --timeframes 1m 5m 15m 1H 4H 1D --normalize
```

---

## 📚 Документация

### 🎓 Для начинающих

**Начните здесь:**

1. 📖 **[README/README.md](./README/README.md)** - Основная документация, примеры
2. 📊 **[README/ARCHITECTURE_DIAGRAMS.md](./README/ARCHITECTURE_DIAGRAMS.md)** - Визуальные диаграммы системы
3. 🗺️ **[README/ARCHITECTURE_INDEX.md](./README/ARCHITECTURE_INDEX.md)** - Навигация по всей документации

### 🏗️ Для архитекторов

**Понимание системы:**

1. 🏛️ **[README/ARCHITECTURE_VISUALIZATION.md](./README/ARCHITECTURE_VISUALIZATION.md)** - Подробная архитектура
2. 🗺️ **[README/COMPONENT_MAP.md](./README/COMPONENT_MAP.md)** - Карта компонентов и зависимостей
3. 📋 **[README/COMPREHENSIVE_DOCUMENTATION.md](./README/COMPREHENSIVE_DOCUMENTATION.md)** - Полная техническая документация

### 🛠️ Для разработчиков

**Разработка и расширение:**

1. 📝 **[domain/README.md](./domain/README.md)** - Domain layer
2. 🏭 **[application/README.md](./application/README.md)** - Application layer
3. 🏛️ **[infrastructure/README.md](./infrastructure/README.md)** - Infrastructure layer
4. 📊 **[indicator_groups/README.md](./indicator_groups/README.md)** - Добавление индикаторов

### 🧪 Для QA

**Тестирование:**

1. 🧪 **[reports/TESTING.md](./reports/TESTING.md)** - Руководство по тестированию
2. 🔥 **[reports/SMOKE_TESTING_REPORT.md](./reports/SMOKE_TESTING_REPORT.md)** - Smoke tests
3. ✅ **[reports/PRODUCTION_READINESS_CHECKLIST.md](./reports/PRODUCTION_READINESS_CHECKLIST.md)** - Production checklist

---

## 📦 Основные компоненты

```
features/
├── core.py                 ⭐ Главный API: compute_features()
├── specs.py                ⭐ Спецификации 500+ индикаторов
├── group_calculation.py    ⭐ Групповой расчет без look-ahead
├── calc.py                 ⭐ Streaming для больших данных
├── calc_indicators.py      ⭐ Airflow entry point
├── domain/                 - Бизнес-логика
│   ├── calculator.py      - Фасад для расчёта
│   ├── indicator_specs.py - Спецификации индикаторов
│   └── protocols.py       - Абстракции и протоколы
├── infrastructure/        - Инфраструктура
│   ├── database.py        - Работа с БД
│   ├── db_operations.py   - Read operations
│   ├── insert_indicators.py - Write operations
│   ├── indicator_registry.py - Реестр индикаторов
│   ├── upsert_builder.py  - Построение UPSERT запросов, нормализация типов
│   └── persistence/        - Персистентность данных
│       ├── inserter.py    - Вставка индикаторов в БД
│       ├── schema_checker.py - Проверка схемы, отражение типов PostgreSQL
│       ├── batch_builder.py - Построение батчей данных
│       └── normalizer.py  - Нормализация данных перед записью
├── application/           - Прикладной слой
│   └── batch_processor.py - Оркестрация процессов
├── indicator_groups/      ⭐ 10 групп индикаторов
│   ├── ma.py             - Moving Averages (30+)
│   ├── oscillators.py    - RSI, MACD, Stochastic (40+)
│   ├── volatility.py     - ATR, Bollinger, Keltner (20+)
│   ├── volume.py         - OBV, VWAP, CMF (15+)
│   ├── trend.py          - ADX, Aroon, Ichimoku (40+)
│   ├── candles.py        - Heikin-Ashi, patterns (80+)
│   ├── squeeze.py        - TTM Squeeze (10+)
│   ├── overlap.py        - Base calculations (10+)
│   ├── statistics.py     - Rolling stats (20+)
│   └── performance.py    - Returns, Sharpe (15+)
├── registry/              - Legacy реестр (deprecated)
├── validators.py          - Валидация данных
├── gate_validation.py     - Quality gates
├── metrics.py             - Метрики и мониторинг
└── tests/                 - 25+ тестовых модулей
```

---

## 🔧 Архитектура

### Слоистая структура (Clean Architecture)

```text
┌─────────────────────────────────────┐
│      API Layer (core.py)            │  ← Единый API для расчёта
├─────────────────────────────────────┤
│   Application Layer (calc.py)       │  ← Оркестрация процессов
├─────────────────────────────────────┤
│   Domain Layer (domain/)             │  ← Бизнес-логика
├─────────────────────────────────────┤
│   Infrastructure (infrastructure/)   │  ← Database, external systems
├─────────────────────────────────────┤
│   Calculation (indicator_groups/)    │  ← Расчет индикаторов
└─────────────────────────────────────┘
```

**Ключевые узлы:**
- `core.compute_features(df, specs)` — **основной API** для расчёта индикаторов
- `domain/` — бизнес-логика и спецификации
- `infrastructure/` — работа с БД и реестр индикаторов
- `application/` — оркестрация процессов
- `indicator_groups/*` — расчёт по категориям
- Airflow DAG `ops/airflow/dags/features_calc.py` — оркестрация, smoke-метрики

### Группы индикаторов (с соблюдением зависимостей)

Порядок расчета гарантирует отсутствие look-ahead bias:

```text
1. overlap      → Base calculations
2. ma           → Moving Averages (EMA, SMA, WMA, HMA, KAMA, TEMA, DEMA)
3. oscillators  → RSI, MACD, Stochastic (depend on MA)
4. volatility   → ATR, Bollinger, Keltner (depend on MA)
5. volume       → OBV, VWAP, CMF, MFI
6. trend        → ADX, Aroon, Ichimoku, PSAR, Supertrend
7. candles      → Heikin-Ashi, patterns (Doji, Hammer, Engulfing)
8. squeeze      → TTM Squeeze (depend on BB + Keltner)
9. statistics   → Rolling stats (median, std, variance)
10. performance → Returns, Sharpe, Drawdown
```

**После каждой группы:** Batch Persistence в БД

### Детальная архитектура системы

Система построена по принципам Clean Architecture с четким разделением ответственности:

```text
┌─────────────────────────────────────────────────────────────┐
│                    CLI / API Layer                          │
│  src/cli/commands/features.py                              │
│  - Парсинг аргументов                                       │
│  - Оркестрация процесса                                     │
│  - Логирование результатов                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              Application Layer                               │
│  features/core/calculation.py                               │
│  - compute_features() - главный API                         │
│  - Групповой расчёт индикаторов                             │
│  - Волатильностная нормализация                             │
│  - Quality gates валидация                                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                  Domain Layer                                │
│  features/domain/                                            │
│  - calculator.py - бизнес-логика расчёта                      │
│  - indicator_specs.py - спецификации индикаторов             │
│  - protocols.py - абстракции и интерфейсы                    │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│            Calculation Layer                                 │
│  features/indicator_groups/                                  │
│  - ma.py, oscillators.py, volatility.py, ...                │
│  - Реализация расчёта по группам                             │
│  - Соблюдение зависимостей между индикаторами                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│           Infrastructure Layer                              │
│  features/infrastructure/                                    │
│  ├── persistence/                                            │
│  │   ├── inserter.py - вставка в БД                         │
│  │   ├── schema_checker.py - проверка схемы                  │
│  │   ├── batch_builder.py - построение батчей                │
│  │   └── normalizer.py - нормализация данных                 │
│  ├── upsert_builder.py - построение UPSERT запросов         │
│  ├── database.py - работа с БД                                │
│  └── indicator_registry.py - реестр индикаторов              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL Database                            │
│  - Таблица indicators                                        │
│  - UPSERT по (symbol, timeframe, timestamp)                 │
│  - Автоматическая нормализация типов                         │
└─────────────────────────────────────────────────────────────┘
```

### Потоки данных

**1. Поток расчёта индикаторов:**

```text
OHLCV данные (БД/CSV)
    ↓
compute_features()
    ↓
Групповой расчёт (10 групп последовательно)
    ↓
Волатильностная нормализация (опционально)
    ↓
Quality gates валидация
    ↓
DataFrame с индикаторами
```

**2. Поток сохранения в БД:**

```text
DataFrame с индикаторами
    ↓
insert_indicators()
    ↓
build_batch_data() - формирование батчей
    ↓
normalize_record_names() - нормализация имён
    ↓
filter_columns_by_schema() - фильтрация по схеме
    ↓
normalize_numeric_columns() - нормализация типов
    ↓
sanitize_records() - санитизация значений
    ↓
build_upsert_statement() - построение SQL
    ↓
Нормализация типов для PostgreSQL
    ↓
Выполнение UPSERT в БД
```

---

## ⚙️ Логика выполнения работы

### Полный цикл обработки

Система выполняет расчёт и сохранение индикаторов в несколько этапов:

#### Этап 1: Инициализация и подготовка

1. **Парсинг аргументов CLI** (`src/cli/commands/features.py:handle()`)
   - Получение символов, таймфреймов, лимита баров
   - Определение списка индикаторов для расчёта (specs)
   - Настройка параметров нормализации

2. **Загрузка OHLCV данных** (`_get_ohlcv_data()`)
   - Запрос к БД через SQLAlchemy
   - Фильтрация по symbol, timeframe, limit
   - Преобразование timestamp в нужный формат
   - Валидация наличия обязательных колонок (open, high, low, close, volume)

3. **Подготовка спецификаций индикаторов**
   - Если specs не указаны - загрузка всех доступных из реестра
   - Валидация доступности индикаторов
   - Группировка по категориям для последовательного расчёта

#### Этап 2: Расчёт индикаторов

4. **Вызов compute_features()** (`features/core/calculation.py`)
   - Вход: DataFrame с OHLCV данными
   - Выход: DataFrame с OHLCV + рассчитанные индикаторы

5. **Групповой расчёт** (последовательно по 10 группам):

   ```text
   Группа 1: overlap (базовые расчёты)
   Группа 2: ma (moving averages)
   Группа 3: oscillators (RSI, MACD, Stochastic)
   Группа 4: volatility (ATR, Bollinger, Keltner)
   Группа 5: volume (OBV, VWAP, CMF)
   Группа 6: trend (ADX, Aroon, Ichimoku, Supertrend)
   Группа 7: candles (Heikin-Ashi, patterns)
   Группа 8: squeeze (TTM Squeeze)
   Группа 9: statistics (rolling stats)
   Группа 10: performance (returns, Sharpe)
   ```

6. **Волатильностная нормализация** (опционально)
   - Применяется к каждой группе после расчёта
   - Использует rolling window для нормализации
   - Метод: rolling_std или другой (настраивается)

7. **Quality Gates валидация**
   - Проверка fill rate ≥ 50%
   - Проверка NaN ratio ≤ 10%
   - Проверка минимального количества строк
   - Проверка адекватности значений

#### Этап 3: Подготовка к сохранению

8. **Формирование DataFrame для вставки** (`_process_symbol_timeframe()`)
   - Исключение OHLCV колонок (оставляем только индикаторы)
   - Добавление обязательных полей: symbol, timeframe, timestamp
   - Преобразование timestamp в нужный формат (ts в секундах)

9. **Вызов insert_indicators()** (`infrastructure/persistence/inserter.py`)
   - Вход: DataFrame с индикаторами, symbol, timeframe
   - Выход: количество сохранённых записей

#### Этап 4: Обработка данных для БД

10. **Валидация данных** (`validate_dataframe()`)
    - Проверка наличия обязательных полей
    - Проверка типов данных
    - Проверка отсутствия дубликатов по timestamp

11. **Построение батчей** (`build_batch_data()`)
    - Преобразование DataFrame в список словарей
    - Обработка каждой строки отдельно
    - Добавление служебных полей (calculated_at)
    - Обработка NaN значений

12. **Фильтрация по схеме БД** (`filter_columns_by_schema()`)
    - Загрузка списка колонок из БД
    - Удаление колонок, которых нет в схеме
    - Нормализация имён колонок (snake_case)

13. **Нормализация имён** (`normalize_record_names()`)
    - Приведение имён к формату БД
    - Удаление недопустимых символов
    - Проверка соответствия схеме

#### Этап 5: Нормализация типов данных

14. **Отражение схемы БД** (`reflect_indicators_table()`)
    - Запрос к PostgreSQL для получения типов колонок
    - Определение типов: NUMERIC, DOUBLE PRECISION, INTEGER, TIMESTAMP
    - Построение словаря типов колонок

15. **Первичная нормализация** (`normalize_numeric_columns()`)
    - Преобразование строк в числа для числовых колонок
    - Обработка numpy типов (np.float64 → float)
    - Преобразование NaN/Inf в None

16. **Дополнительная нормализация** (`sanitize_records()` в upsert_builder.py)
    - Повторная проверка всех значений
    - Преобразование строковых чисел в числа
    - Валидация типов перед построением SQL

17. **Финальная нормализация** (`build_upsert_statement()`)
    - Определение числовых колонок из схемы
    - Преобразование строк в числа по типу колонки:
      - INTEGER колонки: "123" → 123
      - DOUBLE PRECISION колонки: "123.45" → 123.45
      - NUMERIC колонки: "123.456" → Decimal("123.456")
    - Логирование проблемных значений

#### Этап 6: Выполнение UPSERT

18. **Построение SQL запроса** (`build_upsert_statement()`)
    - Генерация INSERT ... ON CONFLICT DO UPDATE
    - Подготовка параметров для batch insert
    - Формирование списка колонок для UPDATE

19. **Валидация типов перед UPSERT** (`validate_numeric_types()`)
    - Проверка всех числовых колонок на наличие строк
    - Валидация NaN/inf значений
    - Проверка контракта UPSERT (PK поля, служебные поля)
    - Логирование схемы таблицы с типами колонок

20. **Батчирование** (`build_and_execute_upsert()`)
    - Динамический расчёт размера батча на основе количества полей
    - Константа `BATCH_SIZE = 50` (настраивается)
    - Валидация типов для каждого батча отдельно
    - Режим диагностики: `DIAGNOSTIC_SINGLE_ROW=1` для обработки по одной записи

21. **Построение SQL запроса** (`build_upsert_statement()`)
    - Генерация INSERT ... ON CONFLICT DO UPDATE
    - Подготовка параметров для batch insert
    - Формирование списка колонок для UPDATE
    - Логирование SQL preview для диагностики

22. **Выполнение запроса** (`execute_upsert()`)
    - Асинхронное выполнение через SQLAlchemy
    - Batch insert всех записей одним запросом
    - Обработка конфликтов по (symbol, timeframe, timestamp)
    - Детальное логирование количества параметров и типов

23. **Обработка ошибок**
    - При ошибке - логирование полного traceback
    - Логирование проблемных записей и значений
    - SQL preview для диагностики
    - Rollback транзакции
    - Диагностика проблемных значений
    - Проброс исключения для обработки на верхнем уровне

#### Этап 7: Завершение

24. **Логирование результатов**
    - Количество обработанных баров
    - Количество рассчитанных индикаторов
    - Количество сохранённых записей
    - Метрики производительности

25. **Возврат результатов**
    - Возврат количества обработанных баров и индикаторов
    - Статистика по группам индикаторов
    - Информация о fill rate и качестве данных

### Особенности реализации

**Параллельная обработка:**
- Символы и таймфреймы обрабатываются последовательно (по одному)
- Внутри каждого символа/таймфрейма - последовательный расчёт групп
- Batch insert выполняется одним запросом для всех записей

**Обработка ошибок:**
- На каждом этапе есть try/except блоки
- Детальное логирование на каждом этапе
- Автоматический rollback при ошибках БД
- Проброс исключений для обработки в Airflow DAG

**Производительность:**
- Batch операции для минимизации запросов к БД
- Оптимизация памяти через streaming для больших датасетов
- Кэширование схемы БД для избежания повторных запросов

**Надёжность:**
- Множественные уровни валидации
- Автоматическая нормализация типов
- Quality gates перед записью
- Идемпотентность через UPSERT

---

## 💡 Примеры использования

### Простой расчет

```python
from features import compute_features

# Минимальный пример
indicators = compute_features(
    df_ohlcv,
    specs=['ema_12', 'rsi_14']
)
```

### Расчет с нормализацией

```python
# С волатильностной нормализацией
indicators = compute_features(
    df_ohlcv,
    specs=['ema_12', 'rsi_14', 'atr_14'],
    volatility_normalize=True
)
```

### Streaming для больших данных

```python
from features.calc import calculate_features_streaming

# Обработка большого датасета по частям
result = calculate_features_streaming(
    csv_path='large_dataset.csv',
    output_dir='./output',
    symbol='BTC/USDT',
    timeframe='1h',
    available_indicators={'ema_12', 'rsi_14', 'macd'},
    chunk_size=5000
)
```

### Интеграция с Airflow

```python
from features.calc_indicators import calculate_indicators_for_pairs

# В Airflow DAG
calculate_task = PythonOperator(
    task_id='calculate_features',
    python_callable=calculate_indicators_for_pairs,
    op_kwargs={
        'symbol_timeframes': [
            ('BTC/USDT', '1h'),
            ('ETH/USDT', '1h'),
        ]
    }
)
```

**Airflow DAG:** `features_calc`
- `features_run` — запускает CLI расчёт
- `smoke_validate_features` — печатает метрики: total_rows, rows_last_24h, nan_ratio_last_24h

---

## 🎨 Ключевые возможности

### 1. 500+ технических индикаторов

**Moving Averages (30+):** EMA (12, 21, 26, 50, 200), SMA (34, 50, 200), WMA, HMA, KAMA, TEMA, DEMA, ZLEMA, риббон (8..233)

**Oscillators (40+):** RSI (14), MACD, Stochastic (K, D), StochRSI (K, D), Williams %R, CCI, ADX (14, +DI, -DI)

**Volatility (20+):** ATR (14), Bollinger Bands (upper, middle, lower), Keltner Channels (upper, middle, lower), Donchian Channels

**Volume (15+):** OBV, VWAP, CMF, MFI, Accumulation/Distribution, Volume Profile (value area high/low, POC), Volume SMA (20)

**Trend (40+):** Ichimoku (tenkan, kijun, senkou_a, senkou_b, chikou), ADX, Supertrend (value, direction, long, short), PSAR (value, direction, long, short), Aroon (up, down, osc)

**Candle Patterns (80+):** Heikin-Ashi (open, high, low, close), Doji, Inside bars, Hammer, Engulfing, Morning Star...

**Squeeze (10+):** TTM Squeeze (on, hist, value)

**Statistics (20+):** Rolling median, std, variance, skewness, kurtosis

**Performance (15+):** Returns, volatility, Sharpe ratio, Sortino ratio, Drawdown

**Полный список:** см. `specs.py` и `registry/*.py`

### 2. Quality Gates

Система автоматически проверяет качество результатов перед записью:

- ✅ **Fill Rate ≥ 50%** - минимальная заполненность
- ✅ **NaN Ratio ≤ 10%** - максимум пропусков на группу
- ✅ **Min Rows = 20** - минимальное количество строк
- ✅ **Max Outlier Ratio ≤ 5%** - максимум выбросов
- ✅ **Timestamp Consistency** - монотонность, отсутствие дубликатов
- ✅ **Value Sanity Checks** - проверка адекватности значений

Встроено в `core.compute_features()`. В случае нарушения — расчёт помечается как невалидный, запись блокируется с подробным отчётом.

**Явное использование:**
```python
from features.gate_validation import GateValidator, GateConfig

cfg = GateConfig(min_rows=20, min_fill_rate=0.5)
is_valid, report = GateValidator(cfg).validate_before_write(df, feature_groups={})
```

### 3. Memory-Efficient Processing

Для больших данных используется streaming:

- 📊 **Chunk-based processing** - 5k-10k rows per chunk
- 🔄 **Overlap** - корректность расчетов на границах
- 💾 **Direct parquet write** - без загрузки всех данных в память
- 🚀 **Unlimited dataset size** - обработка любых объемов

### 4. Production-Ready

- 📝 **Детальное логирование** - структурированные логи, полный traceback при ошибках
  - Логирование DataFrame перед каждым этапом обработки
  - Логирование первой записи после каждого этапа нормализации
  - Логирование схемы таблицы с типами колонок
  - SQL preview для диагностики запросов
  - Детальная информация о проблемных значениях
- 📊 **Метрики и мониторинг** - duration, throughput, quality
- 🔥 **Smoke tests** - автоматическая проверка в production, расширенные тесты с валидацией типов
- 🛡️ **Multiple validation layers** - 5 уровней валидации, включая валидацию типов перед UPSERT
- 🔧 **Автоматическая нормализация типов** - предотвращение ошибок несоответствия типов PostgreSQL
- 🔍 **Режим диагностики** - обработка по одной записи для поиска проблемных значений
- 🐳 **Docker support** - контейнеризация
- ☁️ **Airflow integration** - оркестрация и scheduling
- 🛠️ **Устойчивость к ошибкам** - автоматический rollback, детальная диагностика проблем

---

## 🗄️ Контракты реестра

### Централизованный реестр индикаторов

```python
from features.infrastructure.indicator_registry import AVAILABLE_INDICATORS, INDICATOR_CONFIG
from features.registry import AVAILABLE_INDICATORS, INDICATOR_CONFIG  # Legacy

# Список всех доступных индикаторов
print(len(AVAILABLE_INDICATORS))  # 500+

# Конфигурация конкретного индикатора
print(INDICATOR_CONFIG['rsi_14'])
# {'period': 14, 'requires': ['close'], 'type': 'oscillator'}
```

**Контракты:**
- `AVAILABLE_INDICATORS: list[str]` — перечень доступных имён
- `INDICATOR_CONFIG: dict[str, dict]` — параметры и `requires` (набор колонок OHLCV)

---

## 🛡️ Политика записи в БД

### Безопасность и надежность

- ✅ **Только миграции** - динамическое создание колонок запрещено
- ✅ **Схема управляется** - Alembic миграции и ops‑скрипты
- ✅ **Безопасная запись** - фильтрация отсутствующих колонок
- ✅ **Санитизация** - NaN/Inf → NULL автоматически
- ✅ **UPSERT** - идемпотентность по ключу `(symbol, timeframe, timestamp)`
- ✅ **Batch operations** - батчи по 50-100 строк с динамическим расчётом размера
- ✅ **Валидация контракта** - проверка PK полей и служебных полей перед записью
- ✅ **Детальное логирование** - полная диагностика на каждом этапе обработки

### Валидность и безопасность

- 🔒 **Без look-ahead** - расчёт по бару, индексы согласованы
- 🔒 **NaN-устойчивость** - при нехватке данных возвращаются NaN-серии
- 🔒 **Совместимость типов** - выходные значения всегда числовые
- 🔒 **Quality gates** - отказ от записи при нарушениях порогов

### Нормализация типов данных

Система автоматически нормализует типы данных перед записью в PostgreSQL для предотвращения ошибок несоответствия типов:

**Поддерживаемые типы PostgreSQL:**
- `NUMERIC` / `DECIMAL` - точные числовые значения
- `DOUBLE PRECISION` / `REAL` - числа с плавающей точкой
- `INTEGER` / `BIGINT` / `SMALLINT` - целые числа
- `TIMESTAMP` / `TIMESTAMP WITHOUT TIME ZONE` - временные метки
- `VARCHAR` / `TEXT` - строковые значения

**Процесс нормализации:**

1. **Автоматическое определение типов колонок** - система отражает схему таблицы и определяет типы всех колонок
2. **Преобразование строк в числа** - строковые представления чисел автоматически преобразуются в соответствующие числовые типы:
   - Для `INTEGER` колонок: `"123"` → `123`
   - Для `DOUBLE PRECISION` колонок: `"123.45"` → `123.45`
   - Для `NUMERIC` колонок: `"123.456"` → `Decimal("123.456")`
3. **Обработка numpy типов** - numpy типы (`np.float64`, `np.int32`) преобразуются в нативные Python типы
4. **Валидация значений** - некорректные значения (NaN, Inf) преобразуются в `NULL`

**Реализация:**

Нормализация выполняется в нескольких слоях:
- `infrastructure/persistence/inserter.py` - первичная нормализация перед UPSERT
- `infrastructure/upsert_builder.py` - дополнительная нормализация в `sanitize_records()` и `build_upsert_statement()`
- `infrastructure/persistence/schema_checker.py` - корректное отражение типов PostgreSQL при создании таблицы

**Пример обработки:**

```python
# Автоматическая нормализация происходит прозрачно
record = {
    'ultosc': '5.25',        # Строка → автоматически → 5.25 (float)
    'stochrsi_k': '0.75',   # Строка → автоматически → 0.75 (float)
    'cdl_doji': '1',        # Строка → автоматически → 1 (int)
    'timestamp': 1640995200 # Остаётся как есть
}

# После нормализации все значения имеют правильные типы для PostgreSQL
```

**Валидация типов перед записью:**

Система выполняет многоуровневую валидацию типов данных:

1. **Валидация числовых колонок** (`validate_numeric_types()`) - проверяет все числовые значения перед UPSERT:
   - Обнаруживает строки в числовых колонках
   - Проверяет NaN/inf для float значений
   - Валидирует типы для каждого батча отдельно

2. **Проверка контракта UPSERT** - валидация обязательных полей:
   - PK поля (symbol, timeframe, timestamp) не должны быть NULL
   - timestamp должен быть типа int
   - Служебные поля (calculated_at, created_at, updated_at) не должны быть строками

3. **Логирование схемы** - автоматическое логирование типов всех колонок для диагностики

**Обработка ошибок:**

- Детальное логирование полного traceback при ошибках UPSERT
- Диагностика проблемных значений до нормализации
- Автоматический rollback при ошибках записи
- Предупреждения о значениях, которые не удалось преобразовать
- Логирование первой записи после каждого этапа нормализации
- SQL preview (первые 500 символов) для диагностики запросов

---

## 📊 Производительность

| Операция | Throughput | Memory |
|----------|-----------|--------|
| Batch (< 100k rows) | ~10,000 rows/s | ~5 GB |
| Streaming (> 1M rows) | ~6,000 rows/s | ~500 MB |
| Group Calculation | ~5,000 rows/s | ~800 MB |

*Benchmarks на типичном hardware (16GB RAM, 4 cores)*

---

## 🔗 Интеграции

### Database

- **PostgreSQL** для хранения OHLCV и индикаторов
- **Batch UPSERT** - 5k-10k rows за раз
- **Автоматическая sanitization** - NaN/Inf → NULL
- **Автоматическая нормализация типов** - преобразование строк в числа, numpy типов в Python типы
- **Поддержка всех типов PostgreSQL** - NUMERIC, DOUBLE PRECISION, INTEGER, TIMESTAMP, VARCHAR
- **Отражение схемы** - автоматическое определение типов колонок из БД
- **Валидация типов** - проверка всех числовых колонок перед UPSERT
- **Проверка контракта UPSERT** - валидация PK полей и служебных полей
- **Батчирование** - динамический расчёт размера батча, валидация для каждого батча
- **Режим диагностики** - обработка по одной записи для поиска проблемных значений
- **Conflict resolution** - по (symbol, timeframe, timestamp)
- **Детальное логирование ошибок** - полный traceback, SQL preview, диагностика проблемных записей

### Airflow

- **DAG `features_calc`** - регулярный расчет индикаторов
- **Smoke validation** - проверка после расчета
- **Error handling** - retry logic и алерты
- **XCom** - передача метрик между тасками

### Monitoring

- **Структурированное логирование** - JSON logs
- **Метрики расчетов** - duration, throughput, quality, fill_rate
- **Smoke метрики** - total_rows, rows_last_24h, nan_ratio_last_24h
- **Ready for Prometheus/Grafana** - экспорт метрик

**Мониторинг колонок:** `rsi_14`, `macd`, `atr_14`, `obv`, `vwap`, `supertrend`, `psar`, `aroon_up`, `stochrsi_k`

---

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
pytest tests/

# Быстрые тесты
pytest tests/test_core.py

# Интеграционные тесты
pytest tests/test_integration.py

# Интеграционные тесты с БД
pytest tests/test_db_integration_smoke.py

# Property-тесты (критически важные)
pytest tests/test_property.py

# Production readiness
pytest tests/test_production_readiness.py

# Тесты производительности
pytest tests/test_performance.py

# Coverage report
pytest --cov=features tests/
```

### Smoke-тест с реальными данными

```bash
# Проверка работы с реальными данными из БД
python scripts/run_features_smoke.py BTC-USDT-SWAP 1D --limit 200

# Тестовый скрипт для диагностики UPSERT
python scripts/test_upsert.py --symbols BTC-USDT-SWAP --timeframes 1m --limit 10

# Режим диагностики (одна строка - один запрос)
DIAGNOSTIC_SINGLE_ROW=1 python scripts/test_upsert.py --symbols BTC-USDT-SWAP --timeframes 1m --limit 10
```

**Расширенные smoke-тесты:**

- `test_upsert_full_pipeline_with_validation` - полный пайплайн от OHLCV до UPSERT с валидацией типов
- Проверка типов данных в БД после вставки
- Валидация критических полей (ultosc, stochrsi_k, cdl_doji, willr, rsi_14)

**Режим диагностики:**

Для поиска проблемных записей можно включить режим обработки по одной записи:
- Установите переменную окружения `DIAGNOSTIC_SINGLE_ROW=1`
- Система будет обрабатывать каждую запись отдельно с детальным логированием
- При ошибке будет видна конкретная проблемная запись и её значения

**Важно:** Property-тесты проверяют отсутствие look-ahead и NaN-границы

---

## 🤝 Добавление нового индикатора

### Новый способ (рекомендуется)

1. **Добавьте спецификацию** в `specs.py`:
   ```python
   "my_indicator_20": FeatureSpec(
       name="my_indicator_20",
       type="oscillator",  # или trend, volatility, volume, ma
       params={"period": 20},
       requires=["close"],
       description="My custom indicator with period 20"
   )
   ```

2. **Добавьте в реестр** в соответствующий `registry/*.py`:
   ```python
   OSCILLATOR_INDICATORS = [
       # ...
       "my_indicator_20",
   ]

   INDICATOR_PARAMS["my_indicator_20"] = {"period": 20, "requires": ["close"]}
   ```

3. **Реализуйте расчёт** в группе `indicator_groups/<group>.py`:
   ```python
   def calc_oscillator_indicators(df, available_cols, logger):
       # ...
       if 'my_indicator_20' in available_cols:
           df['my_indicator_20'] = calculate_my_indicator(df['close'], period=20)
   ```

4. **Добавьте тесты** в `tests/test_<group>.py`

5. **Обновите документацию** при необходимости

### Legacy способ (deprecated)

Используйте только если не можете использовать новый способ.

Подробнее: [indicator_groups/README.md](./indicator_groups/README.md)

---

## 📞 Поддержка

- 📧 **Email:** [your-email@example.com]
- 📝 **Issues:** [GitHub Issues]
- 📚 **Документация:** [README/](./README/)

---

## 📄 Лицензия

[Укажите вашу лицензию]

---

## 🙏 Благодарности

- **pandas_ta** - библиотека технических индикаторов
- **pandas** - работа с данными
- **numpy** - численные вычисления
- **PostgreSQL** - база данных
- **Airflow** - оркестрация
- **SQLAlchemy** - ORM

---

## 🗺️ Навигация по документации

**📚 Все документы:** [README/ARCHITECTURE_INDEX.md](./README/ARCHITECTURE_INDEX.md)

**🏃 Быстрый старт:**
- [README/README.md](./README/README.md) - Основная документация
- [README/ARCHITECTURE_DIAGRAMS.md](./README/ARCHITECTURE_DIAGRAMS.md) - Визуальные диаграммы

**🏗️ Архитектура:**
- [README/ARCHITECTURE_VISUALIZATION.md](./README/ARCHITECTURE_VISUALIZATION.md) - Подробная архитектура
- [README/COMPONENT_MAP.md](./README/COMPONENT_MAP.md) - Карта компонентов

**🛠️ Разработка:**
- [README/COMPREHENSIVE_DOCUMENTATION.md](./README/COMPREHENSIVE_DOCUMENTATION.md) - Техническая документация
- [reports/TESTING.md](./reports/TESTING.md) - Тестирование

---

**Версия:** 1.1.0
**Последнее обновление:** 2025-11-19
**Статус:** ✅ Production Ready

**Удачи в работе с модулем Features! 🚀**
