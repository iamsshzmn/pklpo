# MTF System v3.0.0 - Финальная документация

## 🎯 Обзор системы

**MTF (Multi-Timeframe) System** - это комплексная система для анализа рынка на множественных таймфреймах с использованием строгого pipeline обработки данных.

### 📊 Pipeline обработки данных

```
Features → Context → Triggers → Consensus → Integration
    ↓         ↓         ↓          ↓           ↓
  OHLCV    Regime    Reversal   Weighted    External
  Data    Detection  Probs     Aggregation  Systems
```

## 🏗️ Архитектура системы

### Основные модули

1. **Context Module** - Определение режимов рынка
2. **Triggers Module** - Генерация триггеров разворота
3. **Consensus Module** - Взвешенная агрегация сигналов
4. **Pipeline Module** - Оркестрация обработки
5. **Integration Module** - Подключение к внешним системам
6. **Control Module** - Управление системой

### Строгие зависимости

- **Features → Context**: Context нужны рассчитанные индикаторы
- **Context → Triggers**: Triggers используют результаты Context
- **Context + Triggers → Consensus**: Consensus агрегирует оба результата
- **Consensus → Integration**: Integration сохраняет финальный результат

## 🚀 Быстрый старт

### Установка

```python
# Импорт главного построителя
from src.mtf import MTFBuilder
from src.mtf.control.models import ControlConfig

# Создание конфигурации
config = ControlConfig(
    context_enabled=True,
    triggers_enabled=True,
    consensus_enabled=True,
    pipeline_enabled=True,
    integration_enabled=True,
    enable_monitoring=True,
    max_workers=4
)

# Инициализация системы
async with MTFBuilder(config) as mtf:
    # Обработка одного символа
    result = await mtf.process_symbol(
        symbol="BTC-USDT",
        timeframes=["15m", "5m"],
        features_data=your_features_data
    )

    # Пакетная обработка
    batch_result = await mtf.process_batch(
        symbols=["BTC-USDT", "ETH-USDT"],
        timeframes=["15m"],
        features_data=your_batch_data
    )
```

### Пример использования

```python
import asyncio
import pandas as pd
from src.mtf import MTFBuilder
from src.mtf.control.models import ControlConfig

async def main():
    # Конфигурация
    config = ControlConfig(
        max_workers=2,
        enable_monitoring=True
    )

    # Инициализация
    async with MTFBuilder(config) as mtf:
        # Создание тестовых данных
        features_data = {
            '15m': your_ohlcv_dataframe,
            '5m': your_ohlcv_dataframe
        }

        # Обработка
        result = await mtf.process_symbol(
            symbol="BTC-USDT",
            timeframes=["15m", "5m"],
            features_data=features_data
        )

        print(f"Результат: {result['success']}")
        print(f"Context: {result['pipeline_result']['context']}")
        print(f"Triggers: {result['pipeline_result']['triggers']}")
        print(f"Consensus: {result['pipeline_result']['consensus']}")

# Запуск
asyncio.run(main())
```

## 📋 API Reference

### MTFBuilder

#### Основные методы

```python
# Инициализация
async def initialize() -> None

# Обработка одного символа
async def process_symbol(
    symbol: str,
    timeframes: List[str],
    features_data: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]

# Пакетная обработка
async def process_batch(
    symbols: List[str],
    timeframes: List[str],
    features_data: Optional[Dict[str, Dict[str, Any]]] = None,
    max_concurrent: Optional[int] = None,
    **kwargs
) -> Dict[str, Any]

# Управление системой
async def get_system_status() -> Dict[str, Any]
async def health_check() -> Dict[str, Any]
async def get_metrics() -> Dict[str, Any]
async def configure_system(config_updates: Dict[str, Any]) -> bool
async def restart_system() -> bool
async def stop_system() -> bool
```

#### Вспомогательные методы

```python
# Информация о системе
def get_system_info() -> Dict[str, Any]
def is_system_ready() -> bool
def get_supported_timeframes() -> List[str]
def get_supported_symbols() -> List[str]

# Контекстный менеджер
async def __aenter__(self)
async def __aexit__(self, exc_type, exc_val, exc_tb)
```

## ⚙️ Конфигурация

### ControlConfig

```python
@dataclass
class ControlConfig:
    # Общие настройки
    max_workers: int = 4
    timeout_seconds: float = 30.0
    retry_attempts: int = 3

    # Настройки компонентов
    context_enabled: bool = True
    triggers_enabled: bool = True
    consensus_enabled: bool = True
    pipeline_enabled: bool = True
    integration_enabled: bool = True

    # Мониторинг
    enable_monitoring: bool = True
    monitoring_interval_seconds: int = 60

    # Алерты
    enable_alerts: bool = True
    alert_threshold_errors: int = 5
    alert_threshold_response_time: float = 10.0

    # Ресурсы
    max_memory_usage_mb: int = 1024
    max_cpu_usage_percent: float = 80.0
    max_concurrent_requests: int = 100
```

## 📊 Структура данных

### Входные данные (Features)

```python
features_data = {
    '15m': pd.DataFrame({
        'open': [...],
        'high': [...],
        'low': [...],
        'close': [...],
        'volume': [...],
        'ema_20': [...],
        'ema_50': [...],
        'rsi': [...],
        'macd': [...],
        'bb_upper': [...],
        'bb_lower': [...],
        'atr': [...],
        'adx': [...],
        'di_plus': [...],
        'di_minus': [...]
    }),
    '5m': pd.DataFrame({...})
}
```

### Результат обработки

```python
result = {
    'request_id': str,
    'symbol': str,
    'timeframes': List[str],
    'success': bool,
    'processing_time_seconds': float,
    'pipeline_result': {
        'context': ContextResult,
        'triggers': TriggersResult,
        'consensus': ConsensusResult,
        'status': str,
        'processing_stage': str
    },
    'integration_result': {
        'status': str,
        'successful': bool
    },
    'metadata': {
        'start_time': str,
        'end_time': str,
        'mtf_version': str
    }
}
```

## 🔧 Модули системы

### Context Module
- **Назначение**: Определение режимов рынка
- **Алгоритмы**: Trend score, Regime detection, Volatility analysis
- **Вход**: OHLCV данные + индикаторы
- **Выход**: Режим рынка, тренд, волатильность

### Triggers Module
- **Назначение**: Генерация триггеров разворота
- **Алгоритмы**: Reversal probabilities, Acceleration analysis
- **Фильтры**: Noise filtering, Cluster confirmation
- **Вход**: Context данные + OHLCV
- **Выход**: Вероятности разворота, ускорение

### Consensus Module
- **Назначение**: Взвешенная агрегация сигналов
- **Алгоритмы**: Weighted aggregation, Decision rules
- **Логика**: Veto logic, Conflict resolution
- **Вход**: Context + Triggers данные
- **Выход**: Финальное решение, уверенность

### Pipeline Module
- **Назначение**: Оркестрация обработки
- **Функции**: Sequential execution, Error handling
- **Параллельность**: Symbol-level parallelization
- **Вход**: Features данные
- **Выход**: Полный результат pipeline

### Integration Module
- **Назначение**: Подключение к внешним системам
- **Компоненты**: OKX API, Database, Notifications
- **Функции**: Data persistence, External APIs
- **Вход**: Pipeline результат
- **Выход**: Сохраненные данные, уведомления

### Control Module
- **Назначение**: Управление системой
- **Функции**: Start/Stop, Monitoring, Configuration
- **Мониторинг**: Health checks, Metrics, Alerts
- **Вход**: Управляющие команды
- **Выход**: Статус системы, метрики

## 📈 Производительность

### Параллельная обработка

- **Символы**: Параллельно (до max_workers)
- **Таймфреймы**: Параллельно внутри символа
- **Горизонты**: Параллельно внутри символа
- **Внешние API**: Параллельно с rate limiting

### Оптимизация

```python
# Для высокой производительности
config = ControlConfig(
    max_workers=8,
    enable_parallel_processing=True,
    max_concurrent_requests=200
)

# Для стабильности
config = ControlConfig(
    max_workers=2,
    enable_parallel_processing=True,
    max_concurrent_requests=50,
    enable_auto_recovery=True
)
```

## 🧪 Тестирование

### Запуск тестов

```bash
# Тест полной системы
python test_mtf_full_system.py

# Тест отдельных модулей
python test_context_simple.py
python test_triggers_simple.py
python test_consensus_simple.py
python test_pipeline_simple.py
python test_integration_simple.py
python test_control_simple.py
```

### Структура тестов

```
tests/
├── test_mtf_full_system.py      # Полный тест системы
├── test_context_simple.py       # Тест Context модуля
├── test_triggers_simple.py      # Тест Triggers модуля
├── test_consensus_simple.py     # Тест Consensus модуля
├── test_pipeline_simple.py      # Тест Pipeline модуля
├── test_integration_simple.py   # Тест Integration модуля
└── test_control_simple.py       # Тест Control модуля
```

## 📊 Мониторинг

### Метрики системы

- **Производительность**: Время обработки, throughput
- **Надежность**: Процент успеха, количество ошибок
- **Ресурсы**: Использование памяти, CPU
- **Компоненты**: Статус каждого модуля

### Алерты

- **Критические ошибки**: > 5 ошибок
- **Высокое время ответа**: > 10 секунд
- **Высокое использование памяти**: > 80%
- **Высокое использование CPU**: > 80%

## 🔄 Обновления

### Версия 3.0.0

- ✅ Полная реализация Phase 3
- ✅ Строгий pipeline обработки
- ✅ Control модуль для управления
- ✅ Integration модуль для внешних систем
- ✅ Параллельная обработка
- ✅ Мониторинг и алерты
- ✅ Полное тестирование

### Миграция с версии 2.0.0

```python
# Старый способ
from src.mtf.pipeline.builder import PipelineBuilder

# Новый способ
from src.mtf import MTFBuilder
```

## 📚 Дополнительные ресурсы

- **Архитектура**: `src/mtf/ARCHITECTURE_PHASE3.md`
- **Диаграммы**: `src/mtf/ARCHITECTURE_DIAGRAM.md`
- **Конфигурация**: `config/mtf_phase3.yaml`
- **Логи**: `logs/mtf/`

## 🤝 Поддержка

Для вопросов и поддержки:
- Создайте issue в репозитории
- Проверьте логи в `logs/mtf/`
- Используйте health check: `await mtf.health_check()`

---

**MTF System v3.0.0** - Полная система анализа рынка с строгим pipeline обработки данных! 🚀
