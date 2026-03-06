# Domain Layer

**Бизнес-логика и доменные модели**

## Обзор

Domain Layer содержит бизнес-правила, модели данных и спецификации индикаторов. Не зависит от внешних систем - только чистая бизнес-логика.

## Структура

```
domain/
├── __init__.py          # Экспорты
├── calculator.py        # Фасад для расчёта индикаторов
├── indicator_specs.py   # Доступ к спецификациям
├── models.py            # Доменные модели (FeatureSpec, FeatureResult)
├── protocols.py         # Протоколы и интерфейсы
├── strategy.py          # Стратегии расчёта
└── README.md
```

## Компоненты

### `models.py`

Доменные модели для работы с индикаторами.

```python
from src.features.domain.models import FeatureSpec, FeatureResult

# Спецификация индикатора
spec = FeatureSpec(
    name="rsi_14",
    type="oscillator",
    params={"period": 14},
    requires=["close"],
    description="Relative Strength Index"
)

# Результат расчёта
result = FeatureResult(
    name="rsi_14",
    values=pd.Series([45.2, 52.1, 48.9]),
    fill_rate=0.95,
    calculation_time_ms=12.5
)
```

### `calculator.py`

Фасад для расчёта индикаторов через Core API.

```python
from src.features.domain.calculator import calculate_batch

features = calculate_batch(
    df_ohlcv=df,
    available={"rsi_14", "atr_14", "ema_21"},
    volatility_normalize=False
)
```

### `strategy.py`

Стратегии выбора и расчёта индикаторов.

```python
from src.features.domain.strategy import (
    get_indicators_for_timeframe,
    get_core_indicators,
    get_extended_indicators
)

# Базовые индикаторы для всех ТФ
core = get_core_indicators()  # rsi_14, macd, atr_14, ema_21...

# Расширенный набор для старших ТФ
extended = get_extended_indicators()  # ichimoku, supertrend...
```

### `protocols.py`

Протоколы для типизации.

```python
from src.features.domain.protocols import IndicatorCalculator

class CustomIndicator(IndicatorCalculator):
    def calculate(self, df: pd.DataFrame, **params) -> pd.Series:
        # Реализация
        pass
```

### `indicator_specs.py`

Фасад над specs модулем.

```python
from src.features.domain.indicator_specs import (
    FEATURE_SPECS,
    get_features_by_type,
    validate_feature_specs
)

# Получить осцилляторы
oscillators = get_features_by_type("oscillator")

# Валидация
is_valid = validate_feature_specs(specs_list)
```

## Принципы

1. **Чистая логика** - без внешних зависимостей (БД, API)
2. **Immutable** - модели неизменяемы после создания
3. **Тестируемость** - легко тестировать в изоляции
4. **Переиспользование** - модели используются во всех слоях

## Тестирование

```bash
pytest tests/features/tests/test_core.py -v
```
