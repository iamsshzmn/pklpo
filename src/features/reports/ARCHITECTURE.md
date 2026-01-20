# Features Module - Архитектура

## 🏗️ Обзор архитектуры

Модуль `features/` использует **слоистую архитектуру** (Layered Architecture) для обеспечения разделения ответственности, тестируемости и поддерживаемости кода.

## 📐 Принципы архитектуры

### 1. Разделение ответственности (Separation of Concerns)
- **Domain Layer**: Бизнес-логика и спецификации
- **Infrastructure Layer**: Внешние зависимости (БД, реестры)
- **Application Layer**: Оркестрация процессов
- **Core API**: Единая точка входа

### 2. Инверсия зависимостей (Dependency Inversion)
- Высокоуровневые модули не зависят от низкоуровневых
- Абстракции не зависят от деталей
- Детали зависят от абстракций

### 3. Единая ответственность (Single Responsibility)
- Каждый модуль имеет одну причину для изменения
- Четкое разделение между расчетом, валидацией и персистентностью

## 🏛️ Структура слоев

```
src/features/
├── core.py                    # 🎯 Core API - единая точка входа
├── domain/                    # 🧠 Domain Layer - бизнес-логика
│   ├── calculator.py         # Фасад для расчета индикаторов
│   ├── indicator_specs.py    # Спецификации индикаторов
│   └── protocols.py          # Абстракции и протоколы
├── infrastructure/           # 🔧 Infrastructure Layer - внешние зависимости
│   ├── database.py          # Работа с БД
│   └── indicator_registry.py # Реестр индикаторов
├── application/             # 🎭 Application Layer - оркестрация
│   └── batch_processor.py   # Обработка батчей
├── indicator_groups/        # 📊 Группы индикаторов
├── registry/                # 📋 Legacy реестр (deprecated)
├── indicator_utils.py       # ⚠️ Deprecated wrapper
└── tests/                   # 🧪 Тесты
```

## 🎯 Core API Layer

### Назначение
Единая точка входа для всех операций с индикаторами.

### Компоненты
- `core.compute_features()` — основной API для расчета индикаторов

### Принципы
- Простой и понятный интерфейс
- Обратная совместимость
- Валидация входных данных
- Обработка ошибок

### Пример использования
```python
from src.features.core import compute_features

# Основной API
features = compute_features(
    df_ohlcv,
    specs=["rsi_14", "atr_14"],
    volatility_normalize=True
)
```

## 🧠 Domain Layer

### Назначение
Содержит бизнес-логику и спецификации индикаторов.

### Компоненты

#### `domain/calculator.py`
- Фасад для расчета индикаторов
- Абстракция над core API
- Бизнес-логика расчета

```python
from src.features.domain.calculator import calculate_batch

# Доменный фасад
features = calculate_batch(df_ohlcv, available={"rsi_14", "atr_14"})
```

#### `domain/indicator_specs.py`
- Спецификации индикаторов
- Фасад над specs.py
- Доменные модели

```python
from src.features.domain.indicator_specs import FEATURE_SPECS, get_features_by_type

# Получение спецификаций
trend_features = get_features_by_type("trend")
```

#### `domain/protocols.py`
- Абстракции и протоколы
- Интерфейсы для индикаторов
- Типизация

```python
from src.features.domain.protocols import IndicatorCalculator, BatchIndicatorCalculator

# Протоколы для типизации
class MyIndicator(IndicatorCalculator):
    def calculate(self, df_ohlcv, **params):
        # Реализация расчета
        pass
```

### Принципы
- Не зависит от внешних систем
- Содержит только бизнес-логику
- Легко тестируется
- Переиспользуемый

## 🔧 Infrastructure Layer

### Назначение
Обеспечивает работу с внешними системами и данными.

### Компоненты

#### `infrastructure/database.py`
- Работа с базой данных
- Извлечение OHLCV данных
- Сохранение индикаторов

```python
from src.features.infrastructure.database import (
    fetch_ohlcv_df,
    insert_indicators,
    ensure_columns_exist
)

# Работа с БД
df = await fetch_ohlcv_df(session, symbol, timeframe)
await insert_indicators(session, features_df, symbol, timeframe)
```

#### `infrastructure/indicator_registry.py`
- Реестр доступных индикаторов
- Конфигурация индикаторов
- Фабрики для создания индикаторов

```python
from src.features.infrastructure.indicator_registry import (
    AVAILABLE_INDICATORS,
    INDICATOR_CONFIG
)

# Доступ к реестру
print(f"Доступно индикаторов: {len(AVAILABLE_INDICATORS)}")
```

### Принципы
- Изолирует внешние зависимости
- Легко заменяется (например, на моки в тестах)
- Содержит техническую логику
- Не содержит бизнес-логики

## 🎭 Application Layer

### Назначение
Оркестрирует процессы и координирует работу слоев.

### Компоненты

#### `application/batch_processor.py`
- Обработка батчей данных
- Оркестрация расчета и сохранения
- Управление жизненным циклом

```python
from src.features.application.batch_processor import process_single_pair

# Обработка одной пары
success, count, time, errors = await process_single_pair(
    session, symbol, timeframe, available_indicators
)
```

### Принципы
- Координирует работу слоев
- Содержит workflow логику
- Обрабатывает транзакции
- Управляет ошибками

## 📊 Indicator Groups

### Назначение
Содержит логику расчета конкретных групп индикаторов.

### Структура
```
indicator_groups/
├── ma.py              # Moving Averages
├── oscillators.py     # Oscillators (RSI, MACD, etc.)
├── volatility.py      # Volatility indicators (BB, ATR, etc.)
├── volume.py          # Volume indicators (OBV, VWAP, etc.)
├── trend.py           # Trend indicators (Ichimoku, ADX, etc.)
├── squeeze.py         # TTM Squeeze indicators
├── candles.py         # Candlestick patterns
├── overlap.py         # Overlap indicators
├── statistics.py      # Statistical indicators
└── performance.py     # Performance indicators
```

### Принципы
- Каждая группа отвечает за свой тип индикаторов
- Единообразный интерфейс
- Обработка ошибок
- Возврат NaN при ошибках

## 🔄 Поток данных

### 1. Входные данные
```
OHLCV DataFrame → Core API → Domain Layer
```

### 2. Расчет индикаторов
```
Domain Layer → Indicator Groups → pandas_ta → Results
```

### 3. Валидация и обработка
```
Results → Domain Layer → Validation → Core API
```

### 4. Сохранение (опционально)
```
Core API → Application Layer → Infrastructure Layer → Database
```

## 🧪 Тестирование архитектуры

### Unit тесты
- Каждый слой тестируется изолированно
- Моки для внешних зависимостей
- Фокус на бизнес-логике

### Integration тесты
- Тестирование взаимодействия слоев
- Реальные данные
- Проверка end-to-end сценариев

### Property тесты
- Проверка свойств (например, отсутствие look-ahead)
- Случайные данные
- Математические свойства

## 📈 Преимущества архитектуры

### 1. Поддерживаемость
- Четкое разделение ответственности
- Легко найти и изменить код
- Понятная структура

### 2. Тестируемость
- Изолированные компоненты
- Легко создавать моки
- Фокус на бизнес-логике

### 3. Расширяемость
- Легко добавлять новые индикаторы
- Новые источники данных
- Новые способы расчета

### 4. Переиспользование
- Компоненты можно использовать независимо
- Общие абстракции
- Модульность

## 🔧 Миграция с legacy

### Legacy структура
```
src/features/
├── indicator_utils.py    # Монолитный модуль
├── calc_indicators.py    # Большой файл с разной логикой
└── registry/             # Простой реестр
```

### Новая структура
```
src/features/
├── core.py               # Единый API
├── domain/               # Бизнес-логика
├── infrastructure/       # Внешние зависимости
├── application/          # Оркестрация
└── indicator_groups/     # Расчеты
```

### Обратная совместимость
- `indicator_utils.py` остается как deprecated wrapper
- `calc_indicators.py` использует новую архитектуру
- Постепенная миграция

## 🚀 Будущие улучшения

### 1. Асинхронность
- Асинхронные расчеты
- Параллельная обработка
- Неблокирующие операции

### 2. Кэширование
- Кэш результатов расчетов
- Инвалидация кэша
- Оптимизация производительности

### 3. Плагины
- Динамическая загрузка индикаторов
- Пользовательские индикаторы
- Расширяемость

### 4. Мониторинг
- Метрики производительности
- Логирование операций
- Отслеживание ошибок

## 📚 Дополнительные ресурсы

- [README.md](README.md) - Общая документация
- [QUICKSTART.md](QUICKSTART.md) - Быстрый старт
- [MIGRATION.md](MIGRATION.md) - Руководство по миграции
- [TESTING.md](TESTING.md) - Тестирование
- [INDEX.md](INDEX.md) - Индекс документации

---

**Архитектура модуля `features/` обеспечивает высокое качество кода, легкую поддерживаемость и возможность расширения функциональности.**
