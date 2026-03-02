# Core Layer

**Основной расчётный движок индикаторов**

## Обзор

Core Layer содержит основную логику расчёта технических индикаторов. Это сердце модуля features - здесь происходит вычисление всех 177 индикаторов.

## Структура

```
core/
├── __init__.py          # Public API: compute_features()
├── calculation.py       # Основная логика расчёта
├── debug_utils.py       # Утилиты отладки
├── dependency_graph.py  # Граф зависимостей индикаторов
├── group_calculation.py # Расчёт по группам (10 групп)
├── merging.py           # Объединение результатов групп
├── name_mapping.py      # Маппинг имён индикаторов
├── normalization.py     # Нормализация типов и значений
├── pipeline.py          # Pipeline обработки
├── utils.py             # Вспомогательные функции
├── validation.py        # Валидация входных данных
└── README.md
```

## Public API

### `compute_features()`

Основная точка входа для расчёта индикаторов.

```python
from src.features.core import compute_features

df_result = compute_features(
    df_ohlcv,
    specs=['rsi_14', 'ema_21', 'macd', 'atr_14'],
    volatility_normalize=True,
    normalize_window=20
)
```

**Параметры:**
- `df_ohlcv` - DataFrame с колонками: open, high, low, close, volume, timestamp
- `specs` - список индикаторов для расчёта (None = все 177)
- `volatility_normalize` - нормализация волатильности (default: True)
- `normalize_window` - окно для нормализации (default: 20)

**Возвращает:**
- DataFrame с исходными колонками + рассчитанные индикаторы

## Компоненты

### `calculation.py`

Основная логика вычислений.

```python
from src.features.core.calculation import (
    calculate_features,
    calculate_single_indicator
)
```

### `group_calculation.py`

Расчёт индикаторов по группам с учётом зависимостей.

```python
from src.features.core.group_calculation import calculate_indicator_groups

# Порядок расчёта (зависимости соблюдены):
# 1. overlap  → 2. ma → 3. oscillators → 4. volatility
# 5. volume   → 6. trend → 7. candles → 8. squeeze
# 9. statistics → 10. performance
```

### `dependency_graph.py`

Граф зависимостей между индикаторами.

```python
from src.features.core.dependency_graph import (
    get_calculation_order,
    resolve_dependencies
)

order = get_calculation_order(['macd', 'rsi_14'])
# ['close', 'ema_12', 'ema_26', 'macd', 'rsi_14']
```

### `merging.py`

Объединение результатов из разных групп.

```python
from src.features.core.merging import merge_indicator_results

merged_df = merge_indicator_results(
    base_df=df_ohlcv,
    results=[ma_results, oscillator_results, ...]
)
```

### `normalization.py`

Нормализация типов и волатильности.

```python
from src.features.core.normalization import (
    normalize_types,
    volatility_normalize
)

# Приведение типов
df = normalize_types(df)  # все float64

# Волатильностная нормализация
df['rsi_14_norm'] = volatility_normalize(df['rsi_14'], window=20)
```

### `name_mapping.py`

Маппинг и нормализация имён индикаторов.

```python
from src.features.core.name_mapping import (
    normalize_indicator_name,
    check_indicator_capability
)

name = normalize_indicator_name("EMA_21")  # "ema_21"
exists = check_indicator_capability("rsi")  # True
```

### `validation.py`

Валидация входных данных.

```python
from src.features.core.validation import validate_ohlcv_dataframe

is_valid, errors = validate_ohlcv_dataframe(df)
if not is_valid:
    raise ValueError(f"Invalid OHLCV: {errors}")
```

## Порядок расчёта групп

| # | Группа | Lookback | Зависит от |
|---|--------|----------|------------|
| 1 | overlap | 1 | — |
| 2 | ma | 200 | overlap |
| 3 | oscillators | 100 | close, ma |
| 4 | volatility | 100 | OHLC, ma |
| 5 | volume | 50 | volume, close |
| 6 | trend | 100 | OHLC, ATR |
| 7 | candles | 10 | OHLC |
| 8 | squeeze | 20 | BB, KC |
| 9 | statistics | 100 | price data |
| 10 | performance | 50 | close |

## Тестирование

```bash
pytest src/features/tests/test_core.py -v
pytest src/features/tests/test_dependency_graph.py -v
```
