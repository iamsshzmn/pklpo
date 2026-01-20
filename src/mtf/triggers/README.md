# Triggers Builder Module

Модуль для генерации триггеров с анти-шум фильтрацией.

## 🎯 Назначение

Triggers Builder анализирует рыночные данные на коротких таймфреймах и генерирует:
- **Reversal Probabilities** - вероятности разворота (p_up, p_down)
- **Acceleration** - ускорение движения (-1/0/+1)
- **Micro Filter** - проверка ликвидности и качества сигнала
- **Noise Filter** - анти-шум фильтрация с кластерным подтверждением

## 🏗️ Архитектура

```
src/mtf/triggers/
├── __init__.py          # Экспорты модуля
├── builder.py           # Основной построитель триггеров
├── engine.py            # Движок расчета триггеров
├── validator.py         # Валидация триггерных данных
├── models.py            # Модели данных триггеров
├── algorithms.py        # Алгоритмы расчета триггеров
├── filters.py           # Анти-шум фильтрация
├── config.py            # Конфигурация триггеров
└── README.md            # Документация модуля
```

## 🚀 Быстрый старт

### Базовое использование

```python
from src.mtf.triggers import TriggersBuilder, TriggersConfig

# Создание построителя с конфигурацией по умолчанию
builder = TriggersBuilder()

# Построение триггеров для символа
result = await builder.build_triggers("BTC-USDT", ["15m", "5m", "1m"])

print(f"Overall P_UP: {result.overall_p_up}")
print(f"Overall P_DOWN: {result.overall_p_down}")
print(f"Dominant Acceleration: {result.dominant_acceleration}")
print(f"Micro Filter Passed: {result.micro_filter_passed}")
```

### Кастомная конфигурация

```python
from src.mtf.triggers import TriggersBuilder, TriggersConfig

# Создание кастомной конфигурации
config = TriggersConfig(
    timeframes=["15m", "5m"],
    reversal_weights={
        "15m": {
            "rsi": 0.3,
            "macd": 0.3,
            "bollinger": 0.2,
            "stochastic": 0.1,
            "volume": 0.05,
            "momentum": 0.05
        }
    },
    noise_filter_thresholds={
        "15m": {
            "min_volume_ratio": 0.9,
            "max_atr_ratio": 1.5,
            "min_adx": 20,
            "cluster_confirmation": 3
        }
    }
)

builder = TriggersBuilder(config)
result = await builder.build_triggers("ETH-USDT", config.timeframes)
```

### Пакетная обработка

```python
# Обработка нескольких символов
symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT"]
results = await builder.build_triggers_batch(symbols)

for symbol, result in results.items():
    print(f"{symbol}: P_UP={result.overall_p_up:.3f}, P_DOWN={result.overall_p_down:.3f}")
```

## 📊 Модели данных

### TriggersResult

```python
@dataclass
class TriggersResult:
    symbol: str
    timestamp: datetime
    triggers: Dict[str, TriggerData]  # timeframe -> TriggerData
    overall_p_up: float              # [0, 1]
    overall_p_down: float            # [0, 1]
    dominant_acceleration: int       # -1/0/+1
    micro_filter_passed: bool
    noise_filter_effectiveness: float # [0, 1]
    validation_result: ValidationResult
    created_at: datetime
```

### TriggerData

```python
@dataclass
class TriggerData:
    symbol: str
    timeframe: str
    timestamp: datetime
    p_up: float                      # [0, 1]
    p_down: float                    # [0, 1]
    accel: int                       # -1/0/+1
    micro_ok: bool
    features: Dict[str, Any]         # Детальные данные
    noise_filtered: bool
    cluster_confirmed: bool
    created_at: datetime
```

### AccelerationType

```python
class AccelerationType(Enum):
    BULLISH = 1      # Бычье ускорение
    NEUTRAL = 0      # Нейтральное
    BEARISH = -1     # Медвежье ускорение
```

## 🔧 Конфигурация

### YAML конфигурация

```yaml
triggers:
  timeframes: ["15m", "5m", "1m"]
  reversal_weights:
    "15m":
      rsi: 0.25
      macd: 0.25
      bollinger: 0.2
      stochastic: 0.15
      volume: 0.1
      momentum: 0.05
  noise_filter_thresholds:
    "15m":
      min_volume_ratio: 0.8
      max_atr_ratio: 2.0
      min_adx: 15
      cluster_confirmation: 2
  micro_filter_settings:
    liquidity_threshold: 0.5
    spread_threshold: 0.001
    volume_threshold: 0.3
    volatility_threshold: 0.02
```

### Загрузка из файла

```python
config = TriggersConfig.from_yaml("config/mtf_phase3.yaml")
builder = TriggersBuilder(config)
```

## 🧮 Алгоритмы

### Reversal Probabilities Calculation

Вероятности разворота рассчитываются на основе взвешенной комбинации:

1. **RSI Signal** (25%) - сигналы перепроданности/перекупленности
2. **MACD Signal** (25%) - пересечения MACD и сигнальной линии
3. **Bollinger Bands** (20%) - позиция цены относительно полос
4. **Stochastic** (15%) - сигналы стохастика
5. **Volume** (10%) - подтверждение объемом
6. **Momentum** (5%) - импульс относительно EMA

### Acceleration Calculation

Ускорение определяется на основе:
- **MACD Acceleration** - ускорение MACD
- **RSI Acceleration** - ускорение RSI
- **Volume Confirmation** - подтверждение объемом
- **Momentum Confirmation** - подтверждение импульсом

### Micro Filter

Микро-фильтр проверяет:
- **Liquidity** - ликвидность рынка
- **Spread** - размер спреда
- **Volume** - достаточность объема
- **Volatility** - уровень волатильности

### Noise Filter

Анти-шум фильтр применяется при:
- **Low Volume** - низкий объем относительно среднего
- **High Volatility** - высокая волатильность
- **Low ADX** - слабый тренд
- **No Cluster Confirmation** - отсутствие кластерного подтверждения

## ✅ Валидация

### OHLCV Data Validation

- Проверка наличия обязательных колонок
- Проверка логики OHLC данных
- Обнаружение аномальных значений
- Проверка пропущенных значений (более мягкая для триггеров)

### Triggers Result Validation

- Проверка вероятностей в диапазоне [0, 1]
- Проверка ускорения в диапазоне [-1, 1]
- Проверка суммы вероятностей
- Проверка timestamp

## 🔗 Интеграция

### С Features Module

```python
# Интеграция с src.features.core.compute_features
from src.features.core import compute_features

trigger_specs = ["rsi_14", "macd", "macd_signal", "bb_upper", "bb_lower",
                "stoch_k", "stoch_d", "volume", "obv", "atr_14", "adx_14"]
features = compute_features(ohlcv_data, specs=trigger_specs)
```

### С Database

```python
# Сохранение в mtf.triggers таблицу
await save_triggers_to_db(triggers_result)
```

## 🧪 Тестирование

### Unit тесты

```python
import pytest
from src.mtf.triggers import TriggersBuilder

@pytest.mark.asyncio
async def test_build_triggers():
    builder = TriggersBuilder()
    result = await builder.build_triggers("BTC-USDT", ["15m"])

    assert result.symbol == "BTC-USDT"
    assert 0.0 <= result.overall_p_up <= 1.0
    assert 0.0 <= result.overall_p_down <= 1.0
    assert result.dominant_acceleration in [-1, 0, 1]
```

### Property тесты

```python
def test_probability_bounds():
    # Проверка границ вероятностей
    pass

def test_acceleration_bounds():
    # Проверка границ ускорения
    pass
```

## 📈 Мониторинг

### Метрики

- Время расчета триггеров
- Эффективность анти-шум фильтрации
- Распределение вероятностей
- Кластерное подтверждение

### Алерты

- Критические ошибки валидации
- Низкое качество данных
- Превышение времени выполнения
- Низкая эффективность фильтрации

## 🔄 Эволюция

### Версионирование

- Семантическое версионирование
- Обратная совместимость API
- Миграционные скрипты

### Расширяемость

- Добавление новых индикаторов
- Кастомные алгоритмы фильтрации
- Настраиваемые пороги и веса
- Новые типы ускорения
