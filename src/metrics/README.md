# 📊 Система метрик и мониторинга

Модуль для сбора, хранения и экспорта метрик производительности и состояния системы.

## 🏗️ Архитектура

```
src/metrics/
├── __init__.py           # Основной интерфейс модуля
├── collector.py          # Сборщик метрик
├── monitor.py            # Мониторинг системы
├── exporters.py          # Экспортеры метрик
├── decorators.py         # Декораторы для автоматического отслеживания
└── README.md            # Документация
```

## 🚀 Быстрый старт

### Базовое использование

```python
from src.metrics import metrics_collector, MetricType

# Регистрация метрики
await metrics_collector.register_metric(
    "api_requests_total",
    MetricType.COUNTER,
    "Общее количество API запросов"
)

# Увеличение счетчика
await metrics_collector.increment_counter("api_requests_total")

# Установка значения gauge
await metrics_collector.set_gauge("active_connections", 42)

# Запись в гистограмму
await metrics_collector.observe_histogram("request_duration_seconds", 0.15)
```

### Автоматическое отслеживание с декораторами

```python
from src.metrics import track_metrics, track_performance

@track_metrics("calculate_indicators", MetricType.COUNTER)
async def calculate_indicators(symbol: str):
    # Ваш код здесь
    pass

@track_performance("database_query")
async def fetch_data():
    # Ваш код здесь
    pass
```

### Мониторинг системы

```python
from src.metrics import metrics_monitor

# Запуск автоматического мониторинга
await metrics_monitor.start_monitoring()

# Получение состояния здоровья системы
health = await metrics_monitor.get_system_health()
print(f"Статус: {health['overall_status']}")
```

## 📈 Типы метрик

### Counter (Счетчик)
Монотонно увеличивающийся счетчик.

```python
await metrics_collector.increment_counter("requests_total", 1)
```

### Gauge (Измеритель)
Значение, которое может увеличиваться и уменьшаться.

```python
await metrics_collector.set_gauge("memory_usage_mb", 512.5)
```

### Histogram (Гистограмма)
Распределение значений с возможностью вычисления перцентилей.

```python
await metrics_collector.observe_histogram("response_time_seconds", 0.25)
```

### Summary (Сводка)
Аналогично гистограмме, но с предопределенными квантилями.

```python
await metrics_collector.observe_summary("request_size_bytes", 1024)
```

## 🎯 Декораторы

### @track_metrics
Отслеживает вызовы, успешные выполнения и ошибки функции.

```python
@track_metrics("api_endpoint", MetricType.COUNTER, "API endpoint calls")
async def api_handler():
    # Ваш код
    pass
```

### @track_performance
Отслеживает время выполнения функции.

```python
@track_performance("data_processing", "Data processing time")
async def process_data():
    # Ваш код
    pass
```

### @track_database_operations
Специализированный декоратор для операций с БД.

```python
@track_database_operations("select", "users", "User queries")
async def get_users():
    # Ваш код
    pass
```

### @track_api_calls
Специализированный декоратор для API вызовов.

```python
@track_api_calls("/api/v1/users", "GET", "Get users endpoint")
async def get_users_api():
    # Ваш код
    pass
```

## 📊 Экспортеры

### ConsoleExporter
Выводит метрики в читаемом формате для консоли.

```python
from src.metrics import console_exporter

output = await console_exporter.export_metrics()
print(output)
```

### PrometheusExporter
Экспортирует метрики в формате Prometheus.

```python
from src.metrics import prometheus_exporter

prometheus_format = await prometheus_exporter.export_metrics()
print(prometheus_format)
```

### JSONExporter
Экспортирует метрики в формате JSON.

```python
from src.metrics import json_exporter

json_data = await json_exporter.export_metrics()
print(json_data)
```

## 🖥️ Мониторинг системы

### Автоматический сбор системных метрик

```python
from src.metrics import metrics_monitor

# Запуск мониторинга
await metrics_monitor.start_monitoring()

# Остановка мониторинга
await metrics_monitor.stop_monitoring()
```

### Состояние здоровья системы

```python
health = await metrics_monitor.get_system_health()
print(f"Статус: {health['overall_status']}")
print(f"Предупреждения: {health['warnings']}")
print(f"Критические проблемы: {health['critical_issues']}")
```

## 📋 Панель мониторинга

```python
from src.metrics import metrics_dashboard

dashboard = await metrics_dashboard.show_dashboard()
print(dashboard)
```

## 🔧 Контекстные менеджеры

```python
from src.metrics import MetricsContext

async with MetricsContext("data_processing", MetricType.COUNTER) as ctx:
    # Ваш код здесь
    await process_data()
```

## 📊 Сводки метрик

```python
# Получение сводки за последние 5 минут
summary = await metrics_collector.get_metric_summary("api_requests_total", 5)

if summary:
    print(f"Количество: {summary['count']}")
    print(f"Среднее: {summary['avg']:.2f}")
    print(f"Мин/Макс: {summary['min']:.2f}/{summary['max']:.2f}")

    if "percentiles" in summary:
        print(f"P95: {summary['percentiles']['95']:.2f}")
        print(f"P99: {summary['percentiles']['99']:.2f}")
```

## 🗄️ Метрики базы данных

```python
# Отслеживание метрик БД
await metrics_monitor.track_database_metrics(session)
```

## 🔄 Очистка старых метрик

```python
# Очистка метрик старше 24 часов
await metrics_collector.clear_old_metrics(24)
```

## 📝 Примеры использования

### Отслеживание API запросов

```python
@track_api_calls("/api/v1/signals", "POST", "Create trading signal")
async def create_signal(signal_data: dict):
    try:
        # Создание сигнала
        signal = await save_signal(signal_data)

        # Увеличение счетчика успешных сигналов
        await metrics_collector.increment_counter(
            "signals_created_total",
            labels={"type": signal_data.get("type", "unknown")}
        )

        return signal
    except Exception as e:
        # Увеличение счетчика ошибок
        await metrics_collector.increment_counter(
            "signals_errors_total",
            labels={"type": signal_data.get("type", "unknown")}
        )
        raise
```

### Отслеживание производительности расчетов

```python
@track_performance("indicator_calculation", "Technical indicator calculation time")
async def calculate_technical_indicators(symbol: str, timeframe: str):
    start_time = time.time()

    # Расчет индикаторов
    indicators = await process_indicators(symbol, timeframe)

    # Запись времени выполнения
    execution_time = time.time() - start_time
    await metrics_collector.observe_histogram(
        "indicator_calculation_duration_seconds",
        execution_time,
        labels={"symbol": symbol, "timeframe": timeframe}
    )

    return indicators
```

### Мониторинг состояния системы

```python
async def health_check():
    health = await metrics_monitor.get_system_health()

    if health['overall_status'] == 'critical':
        # Отправка алерта
        await send_alert("Критическое состояние системы", health['critical_issues'])

    elif health['overall_status'] == 'warning':
        # Логирование предупреждений
        logger.warning(f"Предупреждения системы: {health['warnings']}")

    return health
```

## 🚨 Алерты и уведомления

Система автоматически определяет критические состояния:

- **CPU > 95%** - Критическое использование процессора
- **Memory > 95%** - Критическое использование памяти  
- **Disk > 95%** - Критическое использование диска

## 📈 Интеграция с внешними системами

### Prometheus
```python
# Экспорт в формате Prometheus
prometheus_data = await prometheus_exporter.export_metrics()

# Отправка в Prometheus сервер
await send_to_prometheus(prometheus_data)
```

### Grafana
```python
# Экспорт в JSON для Grafana
json_data = await json_exporter.export_metrics()

# Отправка в Grafana
await send_to_grafana(json_data)
```

## 🔍 Отладка и диагностика

```python
# Получение всех метрик
all_metrics = await metrics_collector.get_all_metrics()

# Получение конкретной метрики
metric = await metrics_collector.get_metric("api_requests_total")

# Проверка наличия метрики
if metric:
    print(f"Последнее значение: {metric.values[-1].value}")
```

## ⚡ Производительность

- Асинхронная обработка всех операций
- Потокобезопасный доступ к метрикам
- Ограниченная история метрик (по умолчанию 1000 значений)
- Автоматическая очистка старых данных

## 🔧 Конфигурация

```python
# Настройка размера истории метрик
collector = MetricsCollector(max_history=2000)

# Настройка интервала мониторинга
monitor = MetricsMonitor(collector, interval_seconds=60)
```
