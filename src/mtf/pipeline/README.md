# Pipeline Orchestrator Module

Модуль для оркестрации полного пайплайна MTF анализа.

## 🎯 Назначение

Pipeline Orchestrator координирует работу всех модулей MTF системы:
- **Context Builder** - построение контекста рынка
- **Triggers Builder** - генерация триггеров
- **Consensus Builder** - взвешенная агрегация
- **Monitoring** - мониторинг выполнения и метрики
- **Error Handling** - обработка ошибок и повторные попытки

## 🏗️ Архитектура

```
src/mtf/pipeline/
├── __init__.py          # Экспорты модуля
├── orchestrator.py      # Основной оркестратор пайплайна
├── coordinator.py       # Координатор между модулями
├── monitor.py           # Мониторинг выполнения
├── models.py            # Модели данных пайплайна
├── config.py            # Конфигурация пайплайна
└── README.md            # Документация модуля
```

## 🚀 Быстрый старт

### Базовое использование

```python
from src.mtf.pipeline import PipelineOrchestrator, PipelineConfig

# Создание оркестратора с конфигурацией по умолчанию
orchestrator = PipelineOrchestrator()

# Запуск пайплайна для одного символа
result = await orchestrator.run_pipeline("BTC-USDT")

print(f"Status: {result.status}")
print(f"Duration: {result.duration_seconds:.2f}s")
print(f"Errors: {len(result.errors)}")
print(f"Warnings: {len(result.warnings)}")
```

### Кастомная конфигурация

```python
from src.mtf.pipeline import PipelineOrchestrator, PipelineConfig

# Создание кастомной конфигурации
config = PipelineConfig(
    context_timeframes=["1Dutc", "4H", "1H"],
    trigger_timeframes=["15m", "5m"],
    consensus_horizons=["intraday", "swing"],
    max_retries=5,
    timeout_seconds=600.0,
    parallel_processing=True,
    max_workers=8,
    enable_monitoring=True
)

orchestrator = PipelineOrchestrator(config)
result = await orchestrator.run_pipeline("ETH-USDT")
```

### Пакетная обработка

```python
# Обработка нескольких символов
symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT"]
batch_result = await orchestrator.run_batch_pipeline(symbols)

print(f"Batch Status: {batch_result.status}")
print(f"Total Symbols: {len(batch_result.symbols)}")
print(f"Successful: {batch_result.execution_metrics.symbols_successful}")
print(f"Failed: {batch_result.execution_metrics.symbols_failed}")

# Анализ результатов по символам
for symbol, result in batch_result.results.items():
    print(f"{symbol}: {result.status.value} ({result.duration_seconds:.2f}s)")
```

## 📊 Модели данных

### PipelineResult

```python
@dataclass
class PipelineResult:
    run_id: str
    symbol: str
    status: PipelineStatus
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: float
    stages: Dict[str, StageResult]  # Результаты этапов
    context_result: Optional[Any]   # ContextResult
    triggers_result: Optional[Any]  # TriggersResult
    consensus_result: Optional[Any] # ConsensusResult
    execution_metrics: ExecutionMetrics
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
```

### BatchPipelineResult

```python
@dataclass
class BatchPipelineResult:
    run_id: str
    symbols: List[str]
    status: PipelineStatus
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: float
    results: Dict[str, PipelineResult]  # Результаты по символам
    execution_metrics: ExecutionMetrics
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
```

### ExecutionMetrics

```python
@dataclass
class ExecutionMetrics:
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    symbols_processed: int
    symbols_successful: int
    symbols_failed: int
    errors_count: int
    warnings_count: int
```

### PipelineStatus

```python
class PipelineStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

## 🔧 Конфигурация

### YAML конфигурация

```yaml
pipeline:
  context_timeframes: ["1Mutc", "1Wutc", "1Dutc", "4H", "1H"]
  trigger_timeframes: ["15m", "5m", "1m"]
  consensus_horizons: ["intraday", "swing", "week"]
  max_retries: 3
  retry_delay_seconds: 1.0
  timeout_seconds: 300.0
  parallel_processing: true
  max_workers: 4
  enable_monitoring: true
  enable_metrics: true
  performance_settings:
    memory_limit_mb: 1024
    cpu_limit_percent: 80
    disk_space_limit_mb: 10000
    network_timeout_seconds: 30
```

### Загрузка из файла

```python
config = PipelineConfig.from_yaml("config/mtf_phase3.yaml")
orchestrator = PipelineOrchestrator(config)
```

## 🔄 Этапы выполнения

### 1. Context Stage
- Построение контекста рынка
- Анализ трендов и режимов
- Валидация контекстных данных

### 2. Triggers Stage
- Генерация триггеров
- Расчет вероятностей разворота
- Применение анти-шум фильтров

### 3. Consensus Stage
- Взвешенная агрегация
- Применение правил принятия решений
- Veto логика

## 📈 Мониторинг

### Получение состояния здоровья

```python
health = orchestrator.get_pipeline_health()

print(f"Status: {health.status}")
print(f"Success Rate: {health.success_rate:.1%}")
print(f"Average Duration: {health.average_duration:.2f}s")
print(f"Active Runs: {health.active_runs}")
print(f"Alerts: {health.alerts}")
```

### Получение метрик выполнения

```python
metrics = orchestrator.get_execution_metrics(hours=24)

print(f"Total Runs: {metrics['total_runs']}")
print(f"Success Rate: {metrics['success_rate']:.1%}")
print(f"Average Duration: {metrics['average_duration']:.2f}s")
print(f"Memory Usage: {metrics['memory_usage_avg']:.1f} MB")
print(f"CPU Usage: {metrics['cpu_usage_avg']:.1f}%")
```

## ⚡ Производительность

### Параллельная обработка

```python
config = PipelineConfig(
    parallel_processing=True,
    max_workers=8,
    timeout_seconds=600.0
)

orchestrator = PipelineOrchestrator(config)

# Параллельная обработка символов
symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT", "SOL-USDT"]
batch_result = await orchestrator.run_batch_pipeline(symbols)
```

### Ограничения ресурсов

```python
config = PipelineConfig(
    performance_settings={
        "memory_limit_mb": 2048,
        "cpu_limit_percent": 90,
        "disk_space_limit_mb": 20000
    }
)
```

## 🛡️ Обработка ошибок

### Автоматические повторные попытки

```python
config = PipelineConfig(
    max_retries=5,
    retry_delay_seconds=2.0
)
```

### Таймауты

```python
config = PipelineConfig(
    timeout_seconds=300.0  # 5 минут на символ
)
```

### Обработка исключений

```python
result = await orchestrator.run_pipeline("BTC-USDT")

if result.status == PipelineStatus.FAILED:
    print("Pipeline failed with errors:")
    for error in result.errors:
        print(f"  - {error}")

    print("Warnings:")
    for warning in result.warnings:
        print(f"  - {warning}")
```

## 🔗 Интеграция

### С Context Builder

```python
# Автоматическая интеграция через coordinator
# context_result = await context_builder.build_context(symbol, timeframes)
```

### С Triggers Builder

```python
# Автоматическая интеграция через coordinator
# triggers_result = await triggers_builder.build_triggers(symbol, timeframes)
```

### С Consensus Builder

```python
# Автоматическая интеграция через coordinator
# consensus_result = await consensus_builder.build_consensus(symbol, horizons)
```

## 🧪 Тестирование

### Unit тесты

```python
import pytest
from src.mtf.pipeline import PipelineOrchestrator

@pytest.mark.asyncio
async def test_run_pipeline():
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run_pipeline("BTC-USDT")

    assert result.symbol == "BTC-USDT"
    assert result.status in ["completed", "failed"]
    assert result.duration_seconds >= 0
```

### Интеграционные тесты

```python
@pytest.mark.asyncio
async def test_batch_pipeline():
    orchestrator = PipelineOrchestrator()
    symbols = ["BTC-USDT", "ETH-USDT"]
    result = await orchestrator.run_batch_pipeline(symbols)

    assert len(result.results) == len(symbols)
    assert result.execution_metrics.symbols_processed == len(symbols)
```

## 📊 Алерты и мониторинг

### Критические алерты

- Высокий уровень ошибок (>10%)
- Медленное выполнение (>5 минут)
- Слишком много активных запусков (>10)
- Недостаток системных ресурсов

### Метрики производительности

- Время выполнения по этапам
- Использование памяти и CPU
- Количество обработанных символов
- Статистика успешности

## 🔄 Эволюция

### Версионирование

- Семантическое версионирование
- Обратная совместимость API
- Миграционные скрипты

### Расширяемость

- Добавление новых этапов
- Кастомные координаторы
- Плагинная архитектура
- Настраиваемые метрики
