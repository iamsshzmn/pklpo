# Specs Layer

**Спецификации индикаторов**

## Обзор

Specs Layer содержит определения всех 177 технических индикаторов: их параметры, зависимости и метаданные. Это единый источник правды о доступных индикаторах.

## Структура

```
specs/
├── __init__.py       # FEATURE_SPECS, экспорты
├── candles.py        # Свечные паттерны (ha_open, cdl_doji, ...)
├── ma.py             # Скользящие средние (ema_21, sma_50, ...)
├── oscillators.py    # Осцилляторы (rsi_14, macd, stoch_k, ...)
├── overlap.py        # Базовые расчёты (hlc3, hl2, ohlc4, ...)
├── performance.py    # Показатели (returns, sharpe, drawdown, ...)
├── statistics.py     # Статистика (zscore, skew, kurtosis, ...)
├── trend.py          # Трендовые (adx, supertrend, psar, ...)
├── utils.py          # Утилиты для создания спецификаций
├── volatility.py     # Волатильность (atr, bb_upper, kc_lower, ...)
├── volume.py         # Объёмные (obv, vwap, cmf, mfi, ...)
└── README.md
```

## Использование

### Доступ к спецификациям

```python
from src.features.specs import FEATURE_SPECS, FeatureSpec

# Все 177 спецификаций
print(f"Total specs: {len(FEATURE_SPECS)}")  # 177

# Получить конкретную спецификацию
rsi_spec = FEATURE_SPECS["rsi_14"]
print(rsi_spec.name)      # "rsi_14"
print(rsi_spec.type)      # "oscillator"
print(rsi_spec.params)    # {"period": 14}
print(rsi_spec.requires)  # ["close"]
```

### Структура FeatureSpec

```python
@dataclass
class FeatureSpec:
    name: str           # Уникальное имя (rsi_14)
    type: str           # Тип/группа (oscillator, trend, ...)
    params: dict        # Параметры расчёта
    requires: list      # Зависимости (close, high, low, ...)
    description: str    # Описание
    outputs: list       # Выходные колонки (для multi-output)
```

### Фильтрация по типу

```python
from src.features.specs import FEATURE_SPECS

# Получить все осцилляторы
oscillators = {k: v for k, v in FEATURE_SPECS.items() if v.type == "oscillator"}
print(f"Oscillators: {len(oscillators)}")  # ~40

# Получить трендовые
trends = {k: v for k, v in FEATURE_SPECS.items() if v.type == "trend"}
```

## Группы индикаторов

| Группа | Файл | Кол-во | Примеры |
|--------|------|--------|---------|
| overlap | overlap.py | 5 | hlc3, hl2, ohlc4, wcp |
| ma | ma.py | 30+ | ema_8/12/21/50/200, sma_20/50/200 |
| oscillators | oscillators.py | 40+ | rsi_14, macd, stoch_k/d, cci |
| volatility | volatility.py | 20+ | atr_14, bb_upper/lower, kc_upper |
| volume | volume.py | 15+ | obv, vwap, cmf, mfi |
| trend | trend.py | 40+ | adx_14, supertrend, psar, aroon |
| candles | candles.py | 10+ | ha_open/close, cdl_doji |
| statistics | statistics.py | 20+ | zscore, skew, kurtosis, median |
| performance | performance.py | 15+ | returns, sharpe, max_drawdown |

## Добавление нового индикатора

1. Добавить спецификацию в соответствующий файл:

```python
# specs/oscillators.py
OSCILLATOR_SPECS["new_osc"] = FeatureSpec(
    name="new_osc",
    type="oscillator",
    params={"period": 14},
    requires=["close"],
    description="New oscillator indicator"
)
```

2. Реализовать расчёт в `indicator_groups/`:

```python
# indicator_groups/oscillators.py
if "new_osc" in available:
    result["new_osc"] = ta.custom_osc(df["close"], length=14)
```

3. Добавить тест:

```python
# tests/test_new_indicator.py
def test_new_osc():
    df = create_test_ohlcv()
    result = compute_features(df, specs=["new_osc"])
    assert "new_osc" in result.columns
```

## Тестирование

```bash
pytest tests/features/tests/test_core.py -v
pytest tests/features/tests/test_schema.py -v
```
