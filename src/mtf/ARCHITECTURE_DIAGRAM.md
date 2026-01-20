# Архитектурная диаграмма Фазы 3

## 🏗️ Общая архитектура

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MTF Phase 3 Architecture                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────────┐ │
│  │   Context       │    │   Triggers      │    │      Consensus             │ │
│  │   Builder       │    │   Builder       │    │      Builder               │ │
│  │                 │    │                 │    │                            │ │
│  │ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────────────────┐ │ │
│  │ │   Engine    │ │    │ │   Engine    │ │    │ │       Engine            │ │ │
│  │ │             │ │    │ │             │ │    │ │                         │ │ │
│  │ │ • Trend     │ │    │ │ • Reversal  │ │    │ │ • Weighted              │ │ │
│  │ │   Score     │ │    │ │   Probs     │ │    │ │   Aggregation           │ │ │
│  │ │ • Regime    │ │    │ │ • Accel     │ │    │ │ • Decision              │ │ │
│  │ │   Detection │ │    │ │ • Micro     │ │    │ │   Rules                 │ │ │
│  │ │ • Volatility│ │    │ │   Filter    │ │    │ │ • Veto                  │ │ │
│  │ │   Score     │ │    │ │ • Cluster   │ │    │ │   Logic                 │ │ │
│  │ └─────────────┘ │    │ │   Confirm   │ │    │ └─────────────────────────┘ │ │
│  │                 │    │ └─────────────┘ │    │                            │ │
│  │ ┌─────────────┐ │    │                 │    │ ┌─────────────────────────┐ │ │
│  │ │  Validator  │ │    │ ┌─────────────┐ │    │ │      Validator          │ │ │
│  │ │             │ │    │ │  Validator  │ │    │ │                         │ │ │
│  │ │ • OHLCV     │ │    │ │             │ │    │ │ • Context               │ │ │
│  │ │   Data      │ │    │ │ • OHLCV     │ │    │ │   Data                  │ │ │
│  │ │ • Context   │ │    │ │   Data      │ │    │ │ • Trigger               │ │ │
│  │ │   Result    │ │    │ │ • Triggers  │ │    │ │   Data                  │ │ │
│  │ └─────────────┘ │    │ │   Result    │ │    │ │ • Consensus             │ │ │
│  └─────────────────┘    │ └─────────────┘ │    │ │   Result                │ │ │
│                         └─────────────────┘    │ └─────────────────────────┘ │ │
│                                                 └─────────────────────────────┘ │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                           Integration Layer                                     │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        Pipeline Orchestrator                               │ │
│  │                                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────────┐ │ │
│  │  │Orchestrator │  │Coordinator  │  │            Monitor                  │ │ │
│  │  │             │  │             │  │                                     │ │ │
│  │  │ • Full      │  │ • Module    │  │ • Execution                         │ │ │
│  │  │   Pipeline  │  │   Coord     │  │   Metrics                           │ │ │
│  │  │ • Error     │  │ • Data      │  │ • Performance                       │ │ │
│  │  │   Handling  │  │   Flow      │  │   Stats                             │ │ │
│  │  │ • Retry     │  │ • Dependencies│  │ • Alerts                           │ │ │
│  │  │   Logic     │  │             │  │                                     │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                        External Integrations                               │ │
│  │                                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────────┐ │ │
│  │  │  Features   │  │ Market Meta │  │            Database                  │ │ │
│  │  │  Adapter    │  │   Adapter   │  │            Adapter                  │ │ │
│  │  │             │  │             │  │                                     │ │ │
│  │  │ • OHLCV     │  │ • Order     │  │ • Context                           │ │ │
│  │  │   Data      │  │   Validation│  │   Storage                           │ │ │
│  │  │ • Features  │  │ • Risk      │  │ • Triggers                          │ │ │
│  │  │   Calc      │  │   Limits    │  │   Storage                           │ │ │
│  │  │ • Indicators│  │ • Liquidity │  │ • Consensus                         │ │ │
│  │  │             │  │   Check     │  │   Storage                           │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                            Database Layer                                       │
│                                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────────────┐ │
│  │ mtf.context │  │mtf.triggers │  │            mtf.consensus                │ │
│  │             │  │             │  │                                         │ │
│  │ • symbol    │  │ • symbol    │  │ • symbol                                │ │
│  │ • timeframe │  │ • timeframe │  │ • horizon                               │ │
│  │ • ts        │  │ • ts        │  │ • ts                                    │ │
│  │ • score     │  │ • p_up      │  │ • side                                  │ │
│  │ • valid     │  │ • p_down    │  │ • score                                 │ │
│  │ • regime    │  │ • accel     │  │ • input_data                            │ │
│  │ • meta      │  │ • micro_ok  │  │                                         │ │
│  │             │  │ • features  │  │                                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Поток данных

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   OHLCV     │    │  Features   │    │  Context    │    │  Triggers   │
│   Data      │───▶│  Module     │───▶│  Builder    │    │  Builder    │
│             │    │             │    │             │    │             │
│ • Symbol    │    │ • Indicators│    │ • Trend     │    │ • Reversal  │
│ • Timeframe │    │ • Features  │    │   Score     │    │   Probs     │
│ • OHLCV     │    │ • Validation│    │ • Regime    │    │ • Accel     │
│ • Volume    │    │             │    │ • Valid     │    │ • Micro     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                    │
                                                                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Consensus  │◀───│  Consensus  │◀───│  Context    │    │  Triggers   │
│  Result     │    │  Builder    │    │  Data       │    │  Data       │
│             │    │             │    │             │    │             │
│ • Symbol    │    │ • Weighted  │    │ • Symbol    │    │ • Symbol    │
│ • Horizon   │    │   Aggregation│   │ • Timeframe │    │ • Timeframe │
│ • Side      │    │ • Decision  │    │ • Score     │    │ • p_up      │
│ • Score     │    │   Rules     │    │ • Valid     │    │ • p_down    │
│ • Input     │    │ • Veto      │    │ • Regime    │    │ • Accel     │
│   Data      │    │   Logic     │    │             │    │ • Micro_ok  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 🧩 Модульная структура

### Context Module
```
src/mtf/context/
├── builder.py          # Основной построитель
├── engine.py           # Движок расчета
├── validator.py        # Валидация данных
├── algorithms.py       # Алгоритмы regime detection
├── models.py           # Модели данных
├── config.py           # Конфигурация
└── tests/              # Тесты модуля
```

### Triggers Module
```
src/mtf/triggers/
├── builder.py          # Основной построитель
├── engine.py           # Движок расчета
├── validator.py        # Валидация данных
├── algorithms.py       # Алгоритмы триггеров
├── filters.py          # Анти-шум фильтрация
├── models.py           # Модели данных
├── config.py           # Конфигурация
└── tests/              # Тесты модуля
```

### Consensus Module
```
src/mtf/consensus/
├── builder.py          # Основной построитель
├── engine.py           # Движок расчета
├── validator.py        # Валидация данных
├── algorithms.py       # Алгоритмы консенсуса
├── veto.py             # Veto логика
├── models.py           # Модели данных
├── config.py           # Конфигурация
└── tests/              # Тесты модуля
```

### Pipeline Module
```
src/mtf/pipeline/
├── orchestrator.py     # Оркестратор пайплайна
├── coordinator.py      # Координатор модулей
├── monitor.py          # Мониторинг выполнения
├── config.py           # Конфигурация пайплайна
└── tests/              # Тесты модуля
```

### Integration Module
```
src/mtf/integration/
├── features_adapter.py     # Адаптер features модуля
├── market_meta_adapter.py  # Адаптер market_meta модуля
├── database_adapter.py     # Адаптер базы данных
├── config.py               # Конфигурация интеграции
└── tests/                  # Тесты модуля
```

## 🔧 Конфигурация

### YAML Configuration
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

### Test Structure
```
tests/
├── unit/                    # Unit тесты
│   ├── context/
│   │   ├── test_builder.py
│   │   ├── test_engine.py
│   │   ├── test_validator.py
│   │   └── test_algorithms.py
│   ├── triggers/
│   │   ├── test_builder.py
│   │   ├── test_engine.py
│   │   ├── test_validator.py
│   │   ├── test_algorithms.py
│   │   └── test_filters.py
│   ├── consensus/
│   │   ├── test_builder.py
│   │   ├── test_engine.py
│   │   ├── test_validator.py
│   │   ├── test_algorithms.py
│   │   └── test_veto.py
│   └── pipeline/
│       ├── test_orchestrator.py
│       ├── test_coordinator.py
│       └── test_monitor.py
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

## 📊 Мониторинг

### Metrics Collection
```
┌─────────────────────────────────────────────────────────────────┐
│                        Monitoring Layer                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  Context    │  │  Triggers   │  │      Consensus          │ │
│  │  Metrics    │  │  Metrics    │  │      Metrics            │ │
│  │             │  │             │  │                         │ │
│  │ • Calc      │  │ • Calc      │  │ • Calc                  │ │
│  │   Time      │  │   Time      │  │   Time                  │ │
│  │ • Valid     │  │ • Noise     │  │ • Decision              │ │
│  │   Rate      │  │   Filter    │  │   Rate                  │ │
│  │ • Regime    │  │   Effect    │  │ • Veto                  │ │
│  │   Dist      │  │ • Cluster   │  │   Rate                  │ │
│  │             │  │   Confirm   │  │ • Horizon               │ │
│  └─────────────┘  └─────────────┘  │   Dist                  │ │
│                                     └─────────────────────────┘ │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Pipeline Metrics                         │ │
│  │                                                             │ │
│  │ • Execution Time                                            │ │
│  │ • Success Rate                                              │ │
│  │ • Error Rate                                                │ │
│  │ • Throughput                                                │ │
│  │ • Latency                                                   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Развертывание

### Deployment Flow
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Prepare    │    │   Test      │    │  Validate   │    │  Deploy     │
│             │    │             │    │             │    │             │
│ • DB Schema │───▶│ • Unit      │───▶│ • Test      │───▶│ • Production│
│ • Config    │    │   Tests     │    │   Data      │    │ • Monitor   │
│ • Dependencies│   │ • Integration│   │ • E2E       │    │ • Alerts    │
│             │    │   Tests     │    │   Tests     │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

Эта архитектурная диаграмма показывает полную структуру Фазы 3 с модульной архитектурой, четкими границами ответственности и интеграционными слоями.
