# Validation Layer

**Валидация данных и quality gates**

## Обзор

Validation Layer обеспечивает проверку входных данных, качества расчётов и соответствия требованиям перед записью в БД.

## Структура

```
validation/
├── __init__.py           # Экспорты
├── code_validator.py     # Валидация кода и конфигурации
├── data_validator.py     # Валидация входных данных
├── feature_validator.py  # Валидация рассчитанных фичей
├── gate_validator.py     # Quality gates перед записью
└── README.md
```

## Компоненты

### `data_validator.py`

Валидация входных OHLCV данных.

```python
from src.features.validation.data_validator import (
    validate_ohlcv_schema,
    validate_ohlcv_values,
    validate_timestamp_consistency
)

# Проверка схемы
is_valid, errors = validate_ohlcv_schema(df)

# Проверка значений
is_valid, errors = validate_ohlcv_values(df)
# Checks: high >= low, volume >= 0, no negative prices

# Проверка timestamps
is_valid, errors = validate_timestamp_consistency(df)
# Checks: monotonic, no gaps, no duplicates
```

### `feature_validator.py`

Валидация рассчитанных индикаторов.

```python
from src.features.validation.feature_validator import (
    validate_ohlcv_data,
    validate_feature_result,
    validate_fill_rates
)

# Валидация входных данных
validate_ohlcv_data(df)

# Валидация результата
is_valid = validate_feature_result(df_features, min_fill_rate=0.5)

# Проверка fill rates по группам
report = validate_fill_rates(df_features, threshold=0.5)
# {"oscillators": 0.95, "trend": 0.92, ...}
```

### `gate_validator.py`

Quality gates перед записью в БД.

```python
from src.features.validation.gate_validator import (
    GateValidator,
    GateConfig,
    GateResult
)

config = GateConfig(
    min_rows=20,
    min_fill_rate=0.5,
    max_nan_ratio=0.1,
    max_outlier_ratio=0.05
)

validator = GateValidator(config)
result = validator.validate_before_write(df_features, metadata)

if not result.passed:
    print(f"Gate failed: {result.failures}")
    # ["fill_rate below threshold: oscillators=0.45"]
```

**Quality Gates:**

| Gate | Threshold | Описание |
|------|-----------|----------|
| min_rows | >= 20 | Минимум строк для записи |
| fill_rate | >= 50% | Заполненность по группам |
| nan_ratio | <= 10% | Процент NaN |
| outlier_ratio | <= 5% | Процент выбросов |

### `code_validator.py`

Валидация кода и конфигурации.

```python
from src.features.validation.code_validator import (
    validate_indicator_config,
    validate_specs_integrity
)

# Проверка конфигурации индикатора
is_valid = validate_indicator_config({
    "name": "rsi_14",
    "period": 14,
    "requires": ["close"]
})

# Проверка целостности спецификаций
errors = validate_specs_integrity(FEATURE_SPECS)
```

## Использование в pipeline

```python
from src.features.validation.data_validator import validate_ohlcv_schema
from src.features.validation.gate_validator import GateValidator

# 1. Валидация входных данных
is_valid, errors = validate_ohlcv_schema(df_ohlcv)
if not is_valid:
    raise ValueError(f"Invalid input: {errors}")

# 2. Расчёт
df_features = compute_features(df_ohlcv)

# 3. Quality gates
validator = GateValidator()
result = validator.validate_before_write(df_features, {})
if not result.passed:
    raise ValueError(f"Quality gate failed: {result.failures}")

# 4. Запись в БД
await insert_indicators(session, df_features, symbol, timeframe)
```

## Тестирование

```bash
pytest tests/features/tests/test_validators.py -v
pytest tests/features/tests/test_edge_cases.py -v
```
