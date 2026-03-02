# Архитектура Фазы 3 - Context/Triggers/Consensus

## 🎯 Цели архитектуры

Создать модульную, тестируемую и масштабируемую систему для:
- **Context** - построение контекста рынка с regime detection
- **Triggers** - генерация триггеров с анти-шум фильтрацией  
- **Consensus** - взвешенная агрегация с veto логикой

## 🏗️ Принципы архитектуры

### 1. Модульность
- Каждый модуль решает только свою задачу
- Четкие границы ответственности
- Минимизация связей между компонентами

### 2. Тестируемость
- Изолированное тестирование каждого модуля
- Property-тесты для критических алгоритмов
- Моки для внешних зависимостей

### 3. Масштабируемость
- Легкое добавление новых индикаторов
- Настраиваемые пороги и веса
- Параллельная обработка

### 4. Безопасность
- Валидация входных данных
- Защита от look-ahead bias
- Обработка ошибок

## 📊 Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────────┐
│                    MTF Phase 3 Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   Context       │    │   Triggers      │    │  Consensus   │ │
│  │   Builder       │    │   Builder       │    │  Builder     │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                       │     │
│           ▼                       ▼                       ▼     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   Context       │    │   Triggers      │    │  Consensus   │ │
│  │   Engine        │    │   Engine        │    │  Engine      │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                       │     │
│           ▼                       ▼                       ▼     │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐ │
│  │   Context       │    │   Triggers      │    │  Consensus   │ │
│  │   Validator     │    │   Validator     │    │  Validator   │ │
│  └─────────────────┘    └─────────────────┘    └──────────────┘ │
│           │                       │                       │     │
│           ▼                       ▼                       ▼     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                Features Integration                         │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │   OHLCV     │  │  Features   │  │   Market Meta       │ │ │
│  │  │   Data      │  │   Module    │  │   Module            │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    Database Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐     │
│  │ mtf.context │  │mtf.triggers │  │  mtf.consensus      │     │
│  └─────────────┘  └─────────────┘  └─────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## 🧩 Детальная архитектура модулей

### 1. Context Builder

#### Структура модуля
```
src/mtf/context/
├── __init__.py              # Экспорты модуля
├── builder.py               # Основной построитель контекста
├── engine.py                # Движок расчета контекста
├── validator.py             # Валидация контекстных данных
├── models.py                # Модели данных контекста
├── algorithms.py            # Алгоритмы regime detection
├── config.py                # Конфигурация контекста
├── tests/                   # Тесты модуля
│   ├── test_builder.py
│   ├── test_engine.py
│   ├── test_validator.py
│   └── test_algorithms.py
└── README.md                # Документация модуля
```

#### Ответственности
- **Builder** - координация процесса построения контекста
- **Engine** - расчет trend score и regime detection
- **Validator** - валидация входных данных и результатов
- **Algorithms** - алгоритмы определения режимов рынка
- **Models** - структуры данных контекста

#### API контракт
```python
class ContextBuilder:
    async def build_context(self, symbol: str, timeframes: List[str]) -> ContextResult
    async def build_context_batch(self, symbols: List[str]) -> Dict[str, ContextResult]

class ContextEngine:
    def calculate_trend_score(self, features: Dict) -> float
    def determine_regime(self, features: Dict, score: float) -> str
    def calculate_volatility_score(self, features: Dict) -> float

class ContextValidator:
    def validate_ohlcv_data(self, data: pd.DataFrame) -> ValidationResult
    def validate_context_result(self, result: ContextResult) -> ValidationResult
```

### 2. Triggers Builder

#### Структура модуля
```
src/mtf/triggers/
├── __init__.py              # Экспорты модуля
├── builder.py               # Основной построитель триггеров
├── engine.py                # Движок расчета триггеров
├── validator.py             # Валидация триггерных данных
├── models.py                # Модели данных триггеров
├── algorithms.py            # Алгоритмы анти-шум фильтрации
├── filters.py               # Фильтры и кластерное подтверждение
├── config.py                # Конфигурация триггеров
├── tests/                   # Тесты модуля
│   ├── test_builder.py
│   ├── test_engine.py
│   ├── test_validator.py
│   ├── test_algorithms.py
│   └── test_filters.py
└── README.md                # Документация модуля
```

#### Ответственности
- **Builder** - координация процесса построения триггеров
- **Engine** - расчет вероятностей разворота и ускорения
- **Validator** - валидация входных данных и результатов
- **Algorithms** - алгоритмы расчета триггеров
- **Filters** - анти-шум фильтрация и кластерное подтверждение

#### API контракт
```python
class TriggersBuilder:
    async def build_triggers(self, symbol: str, timeframes: List[str]) -> TriggersResult
    async def build_triggers_batch(self, symbols: List[str]) -> Dict[str, TriggersResult]

class TriggersEngine:
    def calculate_reversal_probabilities(self, features: Dict, timeframe: str) -> Tuple[float, float]
    def calculate_acceleration(self, features: pd.DataFrame) -> int
    def calculate_micro_filter(self, features: Dict) -> bool

class TriggersValidator:
    def validate_ohlcv_data(self, data: pd.DataFrame) -> ValidationResult
    def validate_triggers_result(self, result: TriggersResult) -> ValidationResult

class NoiseFilter:
    def apply_noise_filter(self, features: pd.DataFrame, timeframe: str) -> pd.DataFrame
    def calculate_cluster_confirmation(self, features: pd.DataFrame, timeframe: str) -> int
```

### 3. Consensus Builder

#### Структура модуля
```
src/mtf/consensus/
├── __init__.py              # Экспорты модуля
├── builder.py               # Основной построитель консенсуса
├── engine.py                # Движок расчета консенсуса
├── validator.py             # Валидация консенсусных данных
├── models.py                # Модели данных консенсуса
├── algorithms.py            # Алгоритмы взвешенной агрегации
├── veto.py                  # Veto логика и проверки
├── config.py                # Конфигурация консенсуса
├── tests/                   # Тесты модуля
│   ├── test_builder.py
│   ├── test_engine.py
│   ├── test_validator.py
│   ├── test_algorithms.py
│   └── test_veto.py
└── README.md                # Документация модуля
```

#### Ответственности
- **Builder** - координация процесса построения консенсуса
- **Engine** - расчет взвешенной агрегации и метрик
- **Validator** - валидация входных данных и результатов
- **Algorithms** - алгоритмы консенсуса
- **Veto** - veto логика и проверки конфликтов

#### API контракт
```python
class ConsensusBuilder:
    async def build_consensus(self, symbol: str, horizons: List[str]) -> ConsensusResult
    async def build_consensus_batch(self, symbols: List[str]) -> Dict[str, ConsensusResult]

class ConsensusEngine:
    def calculate_weighted_context_score(self, horizon: str, context_data: Dict) -> float
    def calculate_trigger_score(self, trigger_data: Dict) -> float
    def calculate_consensus_strength(self, horizon: str, context_data: Dict, trigger_data: Dict, bias: str) -> float
    def apply_decision_rules(self, horizon: str, bias: str, context_score: float, trigger_score: float) -> Tuple[int, float]

class ConsensusValidator:
    def validate_context_data(self, data: Dict) -> ValidationResult
    def validate_trigger_data(self, data: Dict) -> ValidationResult
    def validate_consensus_result(self, result: ConsensusResult) -> ValidationResult

class VetoEngine:
    def check_veto_conditions(self, horizon: str, context_data: Dict, trigger_data: Dict, bias: str) -> bool
    def calculate_conflict_level(self, context_data: Dict, bias: str) -> float
```

## 🔗 Интеграционная архитектура

### 1. Pipeline Orchestrator

```
src/mtf/pipeline/
├── __init__.py              # Экспорты модуля
├── orchestrator.py          # Основной оркестратор пайплайна
├── coordinator.py           # Координатор между модулями
├── monitor.py               # Мониторинг выполнения
├── config.py                # Конфигурация пайплайна
├── tests/                   # Тесты модуля
│   ├── test_orchestrator.py
│   ├── test_coordinator.py
│   └── test_monitor.py
└── README.md                # Документация модуля
```

#### Ответственности
- **Orchestrator** - управление полным пайплайном
- **Coordinator** - координация между модулями
- **Monitor** - мониторинг выполнения и метрики

### 2. Integration Layer

```
src/mtf/integration/
├── __init__.py              # Экспорты модуля
├── features_adapter.py      # Адаптер для features модуля
├── market_meta_adapter.py   # Адаптер для market_meta модуля
├── database_adapter.py      # Адаптер для базы данных
├── config.py                # Конфигурация интеграции
├── tests/                   # Тесты модуля
│   ├── test_features_adapter.py
│   ├── test_market_meta_adapter.py
│   └── test_database_adapter.py
└── README.md                # Документация модуля
```

## 📋 Конфигурация

### 1. Централизованная конфигурация

```yaml
# config/mtf_phase3.yaml
version: "3.0.0"
schema_version: "v1"

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
```

## 🧪 Тестирование

### 1. Стратегия тестирования

#### Unit тесты
- Каждый модуль тестируется изолированно
- Моки для внешних зависимостей
- Покрытие >90% для критических компонентов

#### Property тесты
- Отсутствие look-ahead bias
- Монотонность валидаций
- Детерминированность результатов

#### Integration тесты
- E2E тестирование пайплайна
- Тестирование интеграции с features/market_meta
- Тестирование производительности

### 2. Структура тестов

```
tests/
├── unit/                    # Unit тесты
│   ├── context/
│   ├── triggers/
│   ├── consensus/
│   └── pipeline/
├── integration/             # Integration тесты
│   ├── test_pipeline_e2e.py
│   ├── test_features_integration.py
│   └── test_market_meta_integration.py
├── property/                # Property тесты
│   ├── test_no_lookahead.py
│   ├── test_monotonicity.py
│   └── test_determinism.py
└── performance/             # Performance тесты
    ├── test_throughput.py
    └── test_latency.py
```

## 📊 Мониторинг и метрики

### 1. Метрики модулей

#### Context Builder
- Время расчета контекста
- Количество обработанных символов
- Процент валидных результатов
- Распределение режимов

#### Triggers Builder
- Время расчета триггеров
- Эффективность анти-шум фильтрации
- Распределение вероятностей
- Кластерное подтверждение

#### Consensus Builder
- Время расчета консенсуса
- Распределение решений по горизонтам
- Эффективность veto логики
- Метрики консенсуса

### 2. Алерты

- Критические ошибки в модулях
- Превышение времени выполнения
- Низкое качество данных
- Конфликты в консенсусе

## 🚀 Развертывание

### 1. Этапы развертывания

1. **Подготовка** - создание схемы БД, настройка конфигурации
2. **Тестирование** - запуск unit и integration тестов
3. **Валидация** - проверка на тестовых данных
4. **Продакшен** - развертывание в продакшене

### 2. Миграция данных

- Миграция существующих данных в новую схему
- Валидация целостности данных
- Откат при проблемах

## 📚 Документация

### 1. Техническая документация

- API Reference для каждого модуля
- Примеры использования
- Руководство по конфигурации
- Troubleshooting guide

### 2. Пользовательская документация

- Быстрый старт
- Примеры запросов
- Мониторинг и алерты
- FAQ

## 🔄 Эволюция архитектуры

### 1. Версионирование

- Семантическое версионирование модулей
- Обратная совместимость API
- Миграционные скрипты

### 2. Расширяемость

- Плагинная архитектура для алгоритмов
- Настраиваемые конфигурации
- API для добавления новых модулей

---

Эта архитектура обеспечивает модульность, тестируемость и масштабируемость системы, следуя принципам из task project.md.
