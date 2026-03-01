# Consensus Builder Module

Модуль для взвешенной агрегации контекста и триггеров с veto логикой.

## 🎯 Назначение

Consensus Builder объединяет данные контекста и триггеров для принятия финальных решений по горизонтам торговли:
- **Weighted Aggregation** - взвешенная агрегация по таймфреймам
- **Decision Rules** - правила принятия решений для каждого горизонта
- **Veto Logic** - veto логика для фильтрации конфликтующих сигналов
- **Consensus Metrics** - метрики консенсуса (coverage, disagreement, confidence)

## 🏗️ Архитектура

```
src/mtf/consensus/
├── __init__.py          # Экспорты модуля
├── builder.py           # Основной построитель консенсуса
├── engine.py            # Движок расчета консенсуса
├── validator.py         # Валидация консенсусных данных
├── models.py            # Модели данных консенсуса
├── algorithms.py        # Алгоритмы взвешенной агрегации
├── veto.py              # Veto логика и проверки
├── config.py            # Конфигурация консенсуса
└── README.md            # Документация модуля
```

## 🚀 Быстрый старт

### Базовое использование

```python
from src.mtf.consensus import ConsensusBuilder, ConsensusConfig

# Создание построителя с конфигурацией по умолчанию
builder = ConsensusBuilder()

# Построение консенсуса для символа
result = await builder.build_consensus("BTC-USDT", ["intraday", "swing", "week"])

print(f"Overall Side: {result.overall_side}")
print(f"Overall Score: {result.overall_score}")
print(f"Overall Confidence: {result.overall_confidence}")
print(f"Horizon Consistency: {result.horizon_consistency}")
```

### Кастомная конфигурация

```python
from src.mtf.consensus import ConsensusBuilder, ConsensusConfig

# Создание кастомной конфигурации
config = ConsensusConfig(
    horizons=["intraday", "swing"],
    horizon_weights={
        "intraday": {
            "1Dutc": 0.5,
            "4H": 0.3,
            "1H": 0.2
        }
    },
    decision_thresholds={
        "intraday": {
            "context_min": 0.2,
            "trigger_p_min": 0.6,
            "consensus_min": 0.7,
            "veto_threshold": 0.25
        }
    }
)

builder = ConsensusBuilder(config)
result = await builder.build_consensus("ETH-USDT", config.horizons)
```

### Пакетная обработка

```python
# Обработка нескольких символов
symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT"]
results = await builder.build_consensus_batch(symbols)

for symbol, result in results.items():
    print(f"{symbol}: Side={result.overall_side}, Score={result.overall_score:.3f}")
```

## 📊 Модели данных

### ConsensusResult

```python
@dataclass
class ConsensusResult:
    symbol: str
    timestamp: datetime
    consensus: Dict[str, ConsensusData]  # horizon -> ConsensusData
    overall_side: int                    # -1/0/+1 (SHORT/FLAT/LONG)
    overall_score: float                 # [0, 1]
    overall_confidence: float            # [0, 1]
    horizon_consistency: float           # [0, 1]
    validation_result: ValidationResult
    created_at: datetime
```

### ConsensusData

```python
@dataclass
class ConsensusData:
    symbol: str
    horizon: str
    timestamp: datetime
    side: int                    # -1/0/+1 (SHORT/FLAT/LONG)
    score: float                 # [0, 1]
    confidence: float            # [0, 1]
    coverage: float              # [0, 1] - покрытие данными
    disagreement: float          # [0, 1] - уровень разногласий
    input_data: Dict[str, Any]   # Все входные данные
    veto_applied: bool           # Применен ли veto
    veto_reason: str             # Причина veto
    created_at: datetime
```

### DecisionSide

```python
class DecisionSide(Enum):
    SHORT = -1    # Короткая позиция
    FLAT = 0      # Нейтральная позиция
    LONG = 1      # Длинная позиция
```

### HorizonType

```python
class HorizonType(Enum):
    INTRADAY = "intraday"    # Внутридневной (1-4 часа)
    SWING = "swing"          # Свинг (1-3 дня)
    WEEK = "week"            # Недельный (3-7 дней)
```

## 🔧 Конфигурация

### YAML конфигурация

```yaml
consensus:
  horizons: ["intraday", "swing", "week"]
  horizon_weights:
    intraday:
      "1Dutc": 0.4
      "4H": 0.3
      "1H": 0.2
      "15m": 0.1
  decision_thresholds:
    intraday:
      context_min: 0.15
      trigger_p_min: 0.55
      consensus_min: 0.6
      veto_threshold: 0.3
  score_weights:
    context: 0.35
    trigger: 0.35
    consensus: 0.15
    quality: 0.1
    momentum: 0.05
  veto_settings:
    micro_filter_veto: true
    context_conflict_threshold: 0.4
    trigger_conflict_threshold: 0.3
    threshold_veto_enabled: true
```

### Загрузка из файла

```python
config = ConsensusConfig.from_yaml("config/mtf_phase3.yaml")
builder = ConsensusBuilder(config)
```

## 🧮 Алгоритмы

### Weighted Aggregation

Взвешенная агрегация по таймфреймам для каждого горизонта:

#### Intraday (внутридневной)
- **1Dutc**: 40% - основной тренд
- **4H**: 30% - фаза тренда
- **1H**: 20% - сглаживание конфликтов
- **15m**: 10% - контекст + триггер

#### Swing (свинг)
- **1Dutc**: 50% - основной тренд
- **4H**: 30% - фаза тренда
- **1Wutc**: 20% - подтверждение недельного фона

#### Week (недельный)
- **1Dutc**: 40% - основной тренд
- **1Wutc**: 30% - недельный фон
- **1Mutc**: 30% - месячный фильтр

### Decision Rules

Правила принятия решений для каждого горизонта:

#### Intraday Rules
1. ✅ `bias ≠ neutral`
2. ✅ `context_score >= 0.15`
3. ✅ `trigger_probability >= 0.55`
4. ✅ `micro_ok == true`

#### Swing Rules
1. ✅ `bias ≠ neutral`
2. ✅ `context_score >= 0.2`
3. ✅ `trigger_probability >= 0.6`
4. ✅ `cluster_confirmed == true`

#### Week Rules
1. ✅ `bias ≠ neutral`
2. ✅ `context_score >= 0.25`
3. ✅ `trigger_probability >= 0.65`
4. ✅ `noise_filtered == false`

### Veto Logic

Veto применяется при:

#### Micro Filter Veto
- Менее 50% триггеров прошли микро-фильтр

#### Context Conflict Veto
- Более 40% контекстов противоречат bias

#### Trigger Conflict Veto
- Вероятности p_up и p_down слишком близки
- Конфликты в ускорении между таймфреймами

#### Threshold Veto
- Недостаточно данных контекста/триггеров
- Высокий уровень разногласий
- Низкое покрытие данными

## ✅ Валидация

### Context Data Validation

- Проверка наличия данных контекста
- Проверка минимального количества таймфреймов
- Проверка score в диапазоне [-1, 1]
- Проверка покрытия данными

### Trigger Data Validation

- Проверка наличия данных триггеров
- Проверка вероятностей в диапазоне [0, 1]
- Проверка ускорения в диапазоне [-1, 1]
- Проверка суммы вероятностей

### Consensus Result Validation

- Проверка side в диапазоне [-1, 1]
- Проверка score в диапазоне [0, 1]
- Проверка confidence в диапазоне [0, 1]
- Проверка логики решений

## 🔗 Интеграция

### С Context Builder

```python
from src.mtf.context import ContextBuilder

context_builder = ContextBuilder()
context_result = await context_builder.build_context(symbol, context_timeframes)
```

### С Triggers Builder

```python
from src.mtf.triggers import TriggersBuilder

triggers_builder = TriggersBuilder()
triggers_result = await triggers_builder.build_triggers(symbol, trigger_timeframes)
```

### С Database

```python
# Сохранение в mtf.consensus таблицу
await save_consensus_to_db(consensus_result)
```

## 🧪 Тестирование

### Unit тесты

```python
import pytest
from src.mtf.consensus import ConsensusBuilder

@pytest.mark.asyncio
async def test_build_consensus():
    builder = ConsensusBuilder()
    result = await builder.build_consensus("BTC-USDT", ["intraday"])

    assert result.symbol == "BTC-USDT"
    assert -1 <= result.overall_side <= 1
    assert 0.0 <= result.overall_score <= 1.0
    assert 0.0 <= result.overall_confidence <= 1.0
```

### Property тесты

```python
def test_decision_bounds():
    # Проверка границ решений
    pass

def test_veto_logic():
    # Проверка veto логики
    pass
```

## 📈 Мониторинг

### Метрики

- Время расчета консенсуса
- Распределение решений по горизонтам
- Эффективность veto логики
- Метрики консенсуса

### Алерты

- Критические ошибки валидации
- Низкое качество данных
- Превышение времени выполнения
- Высокий уровень разногласий

## 🔄 Эволюция

### Версионирование

- Семантическое версионирование
- Обратная совместимость API
- Миграционные скрипты

### Расширяемость

- Добавление новых горизонтов
- Кастомные правила принятия решений
- Настраиваемые veto условия
- Новые метрики консенсуса
