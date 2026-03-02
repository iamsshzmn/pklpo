# Context Builder Module

Модуль для построения контекста рынка с regime detection.

## 🎯 Назначение

Context Builder анализирует рыночные данные на различных таймфреймах и определяет:
- **Trend Score** - сила и направление тренда
- **Regime Detection** - тип режима рынка (trend/range, bull/bear)
- **Validity** - валидность контекстных данных
- **Confidence** - уверенность в анализе

## 🏗️ Архитектура

```
src/mtf/context/
├── __init__.py          # Экспорты модуля
├── builder.py           # Основной построитель контекста
├── engine.py            # Движок расчета контекста
├── validator.py         # Валидация контекстных данных
├── models.py            # Модели данных контекста
├── algorithms.py        # Алгоритмы regime detection
├── config.py            # Конфигурация контекста
└── README.md            # Документация модуля
```

## 🚀 Быстрый старт

### Базовое использование

```python
from src.mtf.context import ContextBuilder, ContextConfig

# Создание построителя с конфигурацией по умолчанию
builder = ContextBuilder()

# Построение контекста для символа
result = await builder.build_context("BTC-USDT", ["1Dutc", "4H", "1H"])

print(f"Overall Score: {result.overall_score}")
print(f"Dominant Regime: {result.dominant_regime}")
print(f"Confidence: {result.confidence}")
```

### Кастомная конфигурация

```python
from src.mtf.context import ContextBuilder, ContextConfig

# Создание кастомной конфигурации
config = ContextConfig(
    timeframes=["1Mutc", "1Wutc", "1Dutc"],
    validity_thresholds={
        "1Mutc": 0.4,
        "1Wutc": 0.35,
        "1Dutc": 0.3
    },
    trend_weights={
        "ema_trend": 0.5,
        "adx_strength": 0.3,
        "rsi_momentum": 0.2
    }
)

builder = ContextBuilder(config)
result = await builder.build_context("ETH-USDT", config.timeframes)
```

### Пакетная обработка

```python
# Обработка нескольких символов
symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT"]
results = await builder.build_context_batch(symbols)

for symbol, result in results.items():
    print(f"{symbol}: {result.overall_score:.3f} ({result.dominant_regime.value})")
```

## 📊 Модели данных

### ContextResult

```python
@dataclass
class ContextResult:
    symbol: str
    timestamp: datetime
    contexts: Dict[str, ContextData]  # timeframe -> ContextData
    overall_score: float              # [-1, 1]
    dominant_regime: RegimeType       # trend_bull/bear, range_bull/bear
    confidence: float                 # [0, 1]
    validation_result: ValidationResult
    created_at: datetime
```

### ContextData

```python
@dataclass
class ContextData:
    symbol: str
    timeframe: str
    timestamp: datetime
    score: float                      # [-1, 1]
    valid: bool                       # |score| >= threshold
    regime: RegimeType
    meta: Dict[str, Any]             # Детальные данные
    created_at: datetime
```

### RegimeType

```python
class RegimeType(Enum):
    TREND_BULL = "trend_bull"        # Сильный восходящий тренд
    TREND_BEAR = "trend_bear"        # Сильный нисходящий тренд
    RANGE_BULL = "range_bull"        # Боковое движение с бычьим уклоном
    RANGE_BEAR = "range_bear"        # Боковое движение с медвежьим уклоном
    UNKNOWN = "unknown"              # Неопределенный режим
```

## 🔧 Конфигурация

### YAML конфигурация

```yaml
context:
  timeframes: ["1Mutc", "1Wutc", "1Dutc", "4H", "1H"]
  validity_thresholds:
    "1Mutc": 0.4
    "1Wutc": 0.35
    "1Dutc": 0.3
    "4H": 0.3
    "1H": 0.25
  trend_weights:
    ema_trend: 0.4
    adx_strength: 0.25
    rsi_momentum: 0.15
    macd_signal: 0.1
    volume_confirmation: 0.1
  regime_thresholds:
    trend_min_score: 0.3
    range_max_score: 0.2
    bull_min_score: 0.1
    bear_max_score: -0.1
```

### Загрузка из файла

```python
config = ContextConfig.from_yaml("config/mtf_phase3.yaml")
builder = ContextBuilder(config)
```

## 🧮 Алгоритмы

### Trend Score Calculation

Trend score рассчитывается на основе взвешенной комбинации:

1. **EMA Trend** (40%) - разность EMA21 и EMA55
2. **ADX Strength** (25%) - сила тренда по ADX
3. **RSI Momentum** (15%) - импульс по RSI
4. **MACD Signal** (10%) - сигнал MACD
5. **Volume Confirmation** (10%) - подтверждение объемом

### Regime Detection

Режим определяется на основе:
- **Trend Strength** - сила тренда (|score|)
- **ADX Level** - уровень ADX (>= 25 для сильного тренда)
- **Volatility** - уровень волатильности
- **Volume Profile** - профиль объема

### Validity Check

Контекст считается валидным если:
- `|score| >= threshold` для данного таймфрейма
- Достаточно данных для анализа
- Отсутствуют критические ошибки

## ✅ Валидация

### OHLCV Data Validation

- Проверка наличия обязательных колонок
- Проверка логики OHLC данных
- Обнаружение аномальных значений
- Проверка пропущенных значений

### Context Result Validation

- Проверка score в диапазоне [-1, 1]
- Проверка confidence в диапазоне [0, 1]
- Проверка timestamp
- Проверка валидности контекстов

## 🔗 Интеграция

### С Features Module

```python
# Интеграция с src.features.core.compute_features
from src.features.core import compute_features

features = compute_features(ohlcv_data, specs=context_specs)
```

### С Database

```python
# Сохранение в mtf.context таблицу
await save_context_to_db(context_result)
```

## 🧪 Тестирование

### Unit тесты

```python
import pytest
from src.mtf.context import ContextBuilder

@pytest.mark.asyncio
async def test_build_context():
    builder = ContextBuilder()
    result = await builder.build_context("BTC-USDT", ["1Dutc"])

    assert result.symbol == "BTC-USDT"
    assert -1.0 <= result.overall_score <= 1.0
    assert 0.0 <= result.confidence <= 1.0
```

### Property тесты

```python
def test_no_lookahead_bias():
    # Проверка отсутствия look-ahead bias
    pass

def test_score_bounds():
    # Проверка границ score
    pass
```

## 📈 Мониторинг

### Метрики

- Время расчета контекста
- Количество обработанных символов
- Процент валидных результатов
- Распределение режимов

### Алерты

- Критические ошибки валидации
- Низкое качество данных
- Превышение времени выполнения

## 🔄 Эволюция

### Версионирование

- Семантическое версионирование
- Обратная совместимость API
- Миграционные скрипты

### Расширяемость

- Добавление новых индикаторов
- Кастомные алгоритмы regime detection
- Настраиваемые веса и пороги
