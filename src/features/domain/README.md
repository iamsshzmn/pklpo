# Domain Layer

## 🧠 Обзор

Domain Layer содержит бизнес-логику и спецификации индикаторов. Этот слой не зависит от внешних систем и содержит только чистую бизнес-логику.

## 📁 Структура

```
domain/
├── calculator.py         # Фасад для расчета индикаторов
├── indicator_specs.py    # Спецификации индикаторов
├── protocols.py          # Абстракции и протоколы
└── README.md            # Эта документация
```

## 🔧 Компоненты

### `calculator.py`

Фасад для расчета индикаторов, предоставляющий доменный интерфейс над core API.

#### Основные функции:

```python
from src.features.domain.calculator import calculate_batch

# Расчет индикаторов через доменный фасад
features = calculate_batch(
    df_ohlcv=df,
    available={"rsi_14", "atr_14"},
    volatility_normalize=False
)
```

#### Параметры:
- `df_ohlcv`: DataFrame с OHLCV данными
- `available`: Множество доступных индикаторов
- `specs`: Список спецификаций индикаторов
- `volatility_normalize`: Нормализация волатильности

### `indicator_specs.py`

Фасад над `specs.py`, предоставляющий стабильную точку доступа к спецификациям индикаторов.

#### Основные функции:

```python
from src.features.domain.indicator_specs import (
    FEATURE_SPECS,
    FEATURE_GROUPS,
    get_features_by_type,
    get_required_features,
    validate_feature_specs
)

# Получение спецификаций по типу
trend_features = get_features_by_type("trend")
oscillator_features = get_features_by_type("oscillator")

# Валидация спецификаций
validate_feature_specs(feature_specs)
```

#### Экспортируемые объекты:
- `FEATURE_SPECS`: Словарь всех спецификаций индикаторов
- `FEATURE_GROUPS`: Группировка индикаторов по типам
- `get_features_by_type()`: Получение индикаторов по типу
- `get_required_features()`: Получение обязательных индикаторов
- `validate_feature_specs()`: Валидация спецификаций

### `protocols.py`

Абстракции и протоколы для типизации индикаторов.

#### Протоколы:

```python
from src.features.domain.protocols import IndicatorCalculator, BatchIndicatorCalculator

# Протокол для одного индикатора
class MyIndicator(IndicatorCalculator):
    def calculate(self, df_ohlcv: pd.DataFrame, **params) -> pd.Series:
        # Реализация расчета
        pass

# Протокол для пакетного расчета
class MyBatchCalculator(BatchIndicatorCalculator):
    def calculate_many(self, df_ohlcv: pd.DataFrame, names: set[str], **params) -> dict[str, pd.Series]:
        # Реализация пакетного расчета
        pass
```

#### Типы протоколов:
- `IndicatorCalculator`: Расчет одного индикатора
- `BatchIndicatorCalculator`: Пакетный расчет индикаторов

## 🎯 Принципы

### 1. Чистая бизнес-логика
- Не зависит от внешних систем
- Не содержит технических деталей
- Фокус на доменных правилах

### 2. Переиспользование
- Компоненты можно использовать независимо
- Общие абстракции
- Модульность

### 3. Тестируемость
- Легко создавать unit-тесты
- Изолированные компоненты
- Предсказуемое поведение

## 🔄 Взаимодействие с другими слоями

### С Core API:
```python
# Domain использует Core API
from src.features.core import compute_features

def calculate_batch(df_ohlcv, available, **kwargs):
    return compute_features(df_ohlcv, available=available, **kwargs)
```

### С Infrastructure:
```python
# Domain не зависит от Infrastructure напрямую
# Использует абстракции через Core API
```

### С Application:
```python
# Application использует Domain
from src.features.domain.calculator import calculate_batch

# В application/batch_processor.py
features = calculate_batch(df, available_indicators)
```

## 📝 Примеры использования

### Базовое использование:

```python
from src.features.domain.calculator import calculate_batch
from src.features.domain.indicator_specs import get_features_by_type

# Получить трендовые индикаторы
trend_indicators = get_features_by_type("trend")

# Рассчитать трендовые индикаторы
features = calculate_batch(
    df_ohlcv=df,
    available=set(trend_indicators.keys()),
    volatility_normalize=True
)
```

### Создание кастомного индикатора:

```python
from src.features.domain.protocols import IndicatorCalculator
import pandas as pd

class CustomRSI(IndicatorCalculator):
    def calculate(self, df_ohlcv: pd.DataFrame, period: int = 14) -> pd.Series:
        # Кастомная реализация RSI
        close = df_ohlcv['close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

# Использование
custom_rsi = CustomRSI()
rsi_values = custom_rsi.calculate(df, period=21)
```

### Валидация спецификаций:

```python
from src.features.domain.indicator_specs import validate_feature_specs, FEATURE_SPECS

# Валидация всех спецификаций
is_valid = validate_feature_specs(list(FEATURE_SPECS.values()))

if not is_valid:
    print("Обнаружены ошибки в спецификациях")
```

## 🧪 Тестирование

### Unit тесты:

```python
import pytest
from src.features.domain.calculator import calculate_batch
from src.features.domain.indicator_specs import get_features_by_type

def test_calculate_batch():
    # Подготовка данных
    df = pd.DataFrame({
        'ts': [1, 2, 3],
        'open': [100, 101, 102],
        'high': [102, 103, 104],
        'low': [99, 100, 101],
        'close': [101, 102, 103],
        'volume': [1000, 1100, 1200]
    })

    # Тест расчета
    features = calculate_batch(df, available={"rsi_14"})

    assert "rsi_14" in features.columns
    assert len(features) == len(df)

def test_get_features_by_type():
    trend_features = get_features_by_type("trend")

    assert isinstance(trend_features, dict)
    assert len(trend_features) > 0
```

## 🔧 Расширение

### Добавление нового доменного сервиса:

```python
# domain/custom_service.py
class CustomDomainService:
    def __init__(self):
        self.calculator = calculate_batch

    def process_indicators(self, df, indicators):
        # Доменная логика обработки индикаторов
        features = self.calculator(df, available=indicators)
        # Дополнительная доменная обработка
        return features
```

### Добавление нового протокола:

```python
# domain/protocols.py
@runtime_checkable
class CustomIndicatorProtocol(Protocol):
    def calculate_custom(self, df_ohlcv: pd.DataFrame, **params) -> pd.Series:
        ...

    def validate_input(self, df_ohlcv: pd.DataFrame) -> bool:
        ...
```

## 📚 Дополнительные ресурсы

- [ARCHITECTURE.md](../reports/ARCHITECTURE.md) - Общая архитектура
- [README.md](../README.md) - Общая документация
- [QUICKSTART.md](../reports/QUICKSTART.md) - Быстрый старт

---

**Domain Layer обеспечивает чистую бизнес-логику и стабильные абстракции для работы с индикаторами.**
