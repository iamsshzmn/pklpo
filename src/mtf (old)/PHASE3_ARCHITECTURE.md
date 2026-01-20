# Фаза 3 - Context/Triggers/Consensus: Архитектурный дизайн

## 🎯 Цель Фазы 3

Создать улучшенную систему построения контекста, триггеров и консенсуса с интеграцией готового `features` модуля и продвинутыми алгоритмами анализа.

## 🏗️ Архитектурные принципы

### 1. **Модульность и изоляция**
- Каждый компонент решает только свою задачу
- Четкие API контракты между модулями
- Минимизация связей между компонентами

### 2. **Интеграция с готовыми модулями**
- Использование `features` модуля для расчета индикаторов
- Интеграция с `market_meta` для валидации
- Совместимость с существующими схемами БД

### 3. **Продвинутые алгоритмы**
- Улучшенная regime detection
- Анти-шум фильтрация с кластерным подтверждением
- Взвешенная агрегация с veto логикой

### 4. **Тестируемость и надежность**
- Полное покрытие unit тестами
- Property тесты для критических компонентов
- Интеграционные тесты E2E

## 📋 Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────────┐
│                    Фаза 3 - MTF Enhanced                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   Context       │    │   Triggers      │    │  Consensus   │ │
│  │   Builder       │    │   Builder       │    │  Builder     │ │
│  │                 │    │                 │    │              │ │
│  │ • Regime        │    │ • Anti-noise    │    │ • Weighted   │ │
│  │   Detection     │    │   Filtering     │    │   Aggregation│ │
│  │ • Trend Score   │    │ • Cluster       │    │ • Veto Logic │ │
│  │ • Validation    │    │   Confirmation  │    │ • Metrics    │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                       │     │
│           └───────────────────────┼───────────────────────┘     │
│                                   │                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                MTF Pipeline                                 │ │
│  │                                                             │ │
│  │ • Orchestration                                             │ │
│  │ • Error Handling                                            │ │
│  │ • Monitoring                                                │ │
│  │ • Validation                                                │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                   │                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                Integration Layer                            │ │
│  │                                                             │ │
│  │ • Features Module Integration                               │ │
│  │ • Market Meta Integration                                  │ │
│  │ • Database Schema Compatibility                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 Детальная архитектура компонентов

### 1. Context Builder

#### **Назначение**
Построение контекстных данных с улучшенной regime detection и интеграцией features модуля.

#### **Архитектура**
```python
class ContextBuilder:
    """Улучшенный построитель контекста"""

    # Конфигурация
    CONTEXT_TFS = ["1Mutc", "1Wutc", "1Dutc", "4H", "1H", "15m"]
    VALIDITY_THRESHOLDS = {...}
    TREND_WEIGHTS = {...}

    # Основные методы
    async def build_context_for_symbol(symbol: str) -> bool
    async def build_context_for_all_symbols() -> Dict[str, bool]

    # Внутренние методы
    async def _get_ohlcv_data(session, symbol: str) -> Dict[str, pd.DataFrame]
    async def _build_single_context(session, symbol: str, timeframe: str, df_ohlcv: pd.DataFrame) -> Optional[Dict]

    # Алгоритмы
    def _calculate_enhanced_trend_score(features: Dict) -> float
    def _determine_enhanced_regime(features: Dict, trend_score: float, timeframe: str) -> str
    def _calculate_volatility_score(features: Dict) -> float
    def _calculate_momentum_score(features: Dict) -> float
```

#### **Интеграция с Features**
```python
# Использование готового features модуля
features_df = compute_features(
    df_ohlcv,
    specs=CONTEXT_FEATURES,
    volatility_normalize=True,
    normalize_window=20
)
```

#### **Улучшенная Regime Detection**
```python
def _determine_enhanced_regime(features: Dict, trend_score: float, timeframe: str) -> str:
    """Многоуровневая логика определения режима"""

    # 1. Базовые компоненты
    adx_14 = features.get('adx_14', 0)
    rsi_14 = features.get('rsi_14', 50)
    bb_upper = features.get('bb_upper')
    bb_lower = features.get('bb_lower')

    # 2. Определение силы тренда
    trend_strength = "strong" if adx_14 > 25 else "weak"

    # 3. Определение направления
    direction = "bull" if trend_score > 0.1 else "bear" if trend_score < -0.1 else "neutral"

    # 4. Определение волатильности
    volatility = "high" if bb_width > 0.05 else "medium" if bb_width > 0.02 else "low"

    # 5. Формирование режима
    regime = f"{trend_strength}_{direction}_{volatility}"

    return regime
```

### 2. Triggers Builder

#### **Назначение**
Построение триггерных данных с анти-шум фильтрацией и кластерным подтверждением.

#### **Архитектура**
```python
class TriggersBuilder:
    """Построитель триггеров с анти-шум фильтрацией"""

    # Конфигурация
    TRIGGER_TFS = ["15m", "5m", "1m"]
    REVERSAL_WEIGHTS = {...}
    NOISE_FILTER_THRESHOLDS = {...}

    # Основные методы
    async def build_triggers_for_symbol(symbol: str) -> bool
    async def build_triggers_for_all_symbols() -> Dict[str, bool]

    # Анти-шум фильтрация
    def _apply_noise_filter(features_df: pd.DataFrame, timeframe: str) -> Optional[pd.DataFrame]
    def _calculate_cluster_confirmation(features_df: pd.DataFrame, timeframe: str) -> int

    # Алгоритмы
    def _calculate_enhanced_reversal_probabilities(features: Dict, timeframe: str) -> Tuple[float, float]
    def _calculate_enhanced_acceleration(features_df: pd.DataFrame) -> int
    def _calculate_enhanced_micro_filter(features: Dict, features_df: pd.DataFrame) -> bool
```

#### **Анти-шум фильтрация**
```python
def _apply_noise_filter(features_df: pd.DataFrame, timeframe: str) -> Optional[pd.DataFrame]:
    """Применяет анти-шум фильтрацию"""

    thresholds = self.NOISE_FILTER_THRESHOLDS.get(timeframe, {})

    # 1. Фильтр по объему
    volume_filter = volume_ratio >= thresholds.get('min_volume_ratio', 0.5)

    # 2. Фильтр по ATR (волатильность)
    atr_filter = atr_ratio <= thresholds.get('max_atr_ratio', 3.0)

    # 3. Фильтр по ADX (сила тренда)
    adx_filter = adx_14 >= thresholds.get('min_adx', 10)

    # 4. Комбинированный фильтр
    combined_filter = volume_filter & atr_filter & adx_filter

    return features_df[combined_filter]
```

#### **Кластерное подтверждение**
```python
def _calculate_cluster_confirmation(features_df: pd.DataFrame, timeframe: str) -> int:
    """Рассчитывает кластерное подтверждение сигнала"""

    # Проверяем последние N баров на согласованность
    recent_data = features_df.tail(required_confirmation + 2)

    confirmations = 0

    # 1. RSI кластер
    if all(rsi_values > 50) or all(rsi_values < 50):
        confirmations += 1

    # 2. MACD кластер
    if all(macd_values > 0) or all(macd_values < 0):
        confirmations += 1

    # 3. Stochastic кластер
    if k_above_d >= required_confirmation or k_below_d >= required_confirmation:
        confirmations += 1

    return min(confirmations, 3)
```

### 3. Consensus Builder

#### **Назначение**
Построение консенсуса с взвешенной агрегацией и veto логикой.

#### **Архитектура**
```python
class ConsensusBuilder:
    """Построитель консенсуса с взвешенной агрегацией"""

    # Конфигурация
    HORIZONS = ["intraday", "swing", "week"]
    HORIZON_WEIGHTS = {...}
    DECISION_THRESHOLDS = {...}
    SCORE_WEIGHTS = {...}

    # Основные методы
    async def build_consensus_for_symbol(symbol: str) -> bool
    async def build_consensus_for_all_symbols() -> Dict[str, bool]

    # Алгоритмы
    def _calculate_weighted_context_score(horizon: str, context_data: Dict) -> float
    def _calculate_trigger_score(trigger_data: Dict) -> float
    def _determine_bias(context_score: float, trigger_score: float) -> str
    def _apply_enhanced_decision_rules(...) -> Tuple[int, float]
    def _check_veto_conditions(...) -> bool
    def _calculate_consensus_metrics(...) -> Dict
    def _calculate_enhanced_final_score(...) -> float
```

#### **Взвешенная агрегация**
```python
def _calculate_weighted_context_score(horizon: str, context_data: Dict) -> float:
    """Рассчитывает взвешенный context score для горизонта"""

    weights = self.HORIZON_WEIGHTS.get(horizon, {})
    context_score = 0.0
    total_weight = 0.0

    for tf, weight in weights.items():
        if tf in context_data and context_data[tf].get("valid", False):
            score = context_data[tf].get("score", 0.0)
            context_score += score * weight
            total_weight += weight

    return context_score / total_weight if total_weight > 0 else 0.0
```

#### **Veto логика**
```python
def _check_veto_conditions(horizon: str, context_data: Dict, trigger_data: Dict, bias: str) -> bool:
    """Проверяет условия для veto"""

    # 1. Проверка конфликтов в контексте
    conflicts = 0
    total_weight = 0

    for tf, data in context_data.items():
        if data.get("valid", False):
            score = data.get("score", 0.0)
            weight = 1.0

            if bias == "long" and score < -0.1:
                conflicts += abs(score) * weight
            elif bias == "short" and score > 0.1:
                conflicts += abs(score) * weight

            total_weight += weight

    # 2. Проверка микро-фильтра
    if horizon in ["intraday"]:
        micro_ok = trigger_data.get("1m", {}).get("micro_ok", True)
        if not micro_ok:
            return True

    return (conflicts / total_weight) > veto_threshold if total_weight > 0 else False
```

### 4. MTF Pipeline

#### **Назначение**
Оркестрация всех компонентов в единый пайплайн с мониторингом и обработкой ошибок.

#### **Архитектура**
```python
class MTFPipeline:
    """Интеграционный пайплайн для MTF системы"""

    def __init__(self):
        self.context_builder = ContextBuilder()
        self.triggers_builder = TriggersBuilder()
        self.consensus_builder = ConsensusBuilder()

    # Основные методы
    async def run_full_pipeline(symbols: List[str] = None) -> Dict[str, Any]
    async def run_context_only(symbols: List[str] = None) -> Dict[str, bool]
    async def run_triggers_only(symbols: List[str] = None) -> Dict[str, bool]
    async def run_consensus_only(symbols: List[str] = None) -> Dict[str, bool]

    # Мониторинг
    async def get_pipeline_status() -> Dict[str, Any]
    async def validate_pipeline_data(symbol: str) -> Dict[str, Any]
```

## 🔗 Интеграция с готовыми модулями

### 1. Features Module Integration

```python
# В ContextBuilder и TriggersBuilder
from src.features.core import compute_features
from src.features.specs import FEATURE_SPECS
from src.features.validators import validate_ohlcv_data

# Использование готового API
features_df = compute_features(
    df_ohlcv,
    specs=CONTEXT_FEATURES,
    volatility_normalize=True,
    normalize_window=20
)
```

### 2. Market Meta Integration

```python
# Валидация с биржевыми метаданными
from src.market_meta.validators import validate_order, validate_risk

# Проверка ликвидности
liquidity_ok = validate_liquidity(spread_bps, vol_usdt, book_depth)
```

### 3. Database Schema Compatibility

```python
# Совместимость с существующими схемами
# Использование существующих таблиц mtf.context, mtf.triggers, mtf.consensus
# Добавление новых полей без нарушения существующих контрактов
```

## 🧪 Тестирование

### 1. Unit Tests

```python
# test_context_builder.py
class TestContextBuilder:
    def test_calculate_enhanced_trend_score()
    def test_determine_enhanced_regime()
    def test_calculate_volatility_score()
    def test_calculate_momentum_score()

# test_triggers_builder.py
class TestTriggersBuilder:
    def test_calculate_enhanced_reversal_probabilities()
    def test_apply_noise_filter()
    def test_calculate_cluster_confirmation()
    def test_calculate_enhanced_acceleration()

# test_consensus_builder.py
class TestConsensusBuilder:
    def test_calculate_weighted_context_score()
    def test_calculate_trigger_score()
    def test_check_veto_conditions()
    def test_calculate_consensus_metrics()
```

### 2. Integration Tests

```python
# test_mtf_pipeline.py
class TestMTFPipeline:
    @pytest.mark.asyncio
    async def test_run_full_pipeline()
    @pytest.mark.asyncio
    async def test_integration_with_features()
    @pytest.mark.asyncio
    async def test_error_handling()
```

### 3. Property Tests

```python
# test_property.py
def test_no_lookahead_bias()
def test_online_offline_parity()
def test_deterministic_results()
```

## 📊 Конфигурация

### 1. Параметры алгоритмов

```yaml
# config/phase3_config.yaml
context:
  validity_thresholds:
    "1Mutc": 0.4
    "1Wutc": 0.35
    "1Dutc": 0.3
    "4H": 0.3
    "1H": 0.25
    "15m": 0.2

  trend_weights:
    ema_trend: 0.4
    adx_strength: 0.25
    rsi_momentum: 0.15
    macd_signal: 0.1
    volume_confirmation: 0.1

triggers:
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

consensus:
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
```

## 🚀 План реализации

### Этап 1: Context Builder (1-2 дня)
- [ ] Создание ContextBuilder класса
- [ ] Интеграция с features модулем
- [ ] Реализация улучшенной regime detection
- [ ] Unit тесты

### Этап 2: Triggers Builder (1-2 дня)
- [ ] Создание TriggersBuilder класса
- [ ] Реализация анти-шум фильтрации
- [ ] Кластерное подтверждение
- [ ] Unit тесты

### Этап 3: Consensus Builder (1-2 дня)
- [ ] Создание ConsensusBuilder класса
- [ ] Взвешенная агрегация
- [ ] Veto логика
- [ ] Unit тесты

### Этап 4: MTF Pipeline (1 день)
- [ ] Создание MTFPipeline класса
- [ ] Оркестрация компонентов
- [ ] Мониторинг и валидация
- [ ] Integration тесты

### Этап 5: CLI и документация (1 день)
- [ ] Расширенный CLI интерфейс
- [ ] Документация
- [ ] Примеры использования

## 📈 Ожидаемые результаты

### 1. Улучшенное качество сигналов
- Более точная regime detection
- Снижение ложных сигналов через анти-шум фильтрацию
- Лучшая агрегация через взвешенные алгоритмы

### 2. Повышенная надежность
- Интеграция с проверенными модулями
- Полное покрытие тестами
- Обработка ошибок и мониторинг

### 3. Лучшая производительность
- Оптимизированные алгоритмы
- Эффективная обработка данных
- Масштабируемость

### 4. Упрощенная поддержка
- Модульная архитектура
- Четкие API контракты
- Подробная документация

## 🔄 Миграция с текущей версии

### 1. Обратная совместимость
- Сохранение существующих API
- Постепенная миграция
- Fallback на старые алгоритмы

### 2. Миграция данных
- Обновление существующих записей
- Валидация целостности
- Откат при ошибках

### 3. Тестирование
- A/B тестирование алгоритмов
- Сравнение результатов
- Постепенное внедрение

---

**Эта архитектура обеспечивает надежную, масштабируемую и тестируемую систему для Фазы 3 с полной интеграцией готовых модулей.**
