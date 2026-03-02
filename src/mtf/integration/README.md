# Integration Module

Модуль для интеграции с внешними системами и адаптеры для features, market_meta и database модулей.

## 🎯 Назначение

Integration Module предоставляет адаптеры для взаимодействия с внешними модулями:
- **Features Adapter** - интеграция с модулем расчета индикаторов
- **Market Meta Adapter** - интеграция с модулем рыночной метаинформации
- **Database Adapter** - интеграция с базой данных
- **Data Quality** - валидация и контроль качества данных
- **Connection Health** - мониторинг состояния подключений

## 🏗️ Архитектура

```
src/mtf/integration/
├── __init__.py              # Экспорты модуля
├── features_adapter.py      # Адаптер для features модуля
├── market_meta_adapter.py   # Адаптер для market_meta модуля
├── database_adapter.py      # Адаптер для базы данных
├── models.py                # Модели данных интеграции
├── config.py                # Конфигурация интеграции
└── README.md                # Документация модуля
```

## 🚀 Быстрый старт

### Базовое использование

```python
from src.mtf.integration import FeaturesAdapter, MarketMetaAdapter, DatabaseAdapter, IntegrationConfig

# Создание адаптеров с конфигурацией по умолчанию
config = IntegrationConfig.default()
features_adapter = FeaturesAdapter(config)
market_meta_adapter = MarketMetaAdapter(config)
database_adapter = DatabaseAdapter(config)

# Получение данных индикаторов
import pandas as pd
ohlcv_data = pd.DataFrame({'close': [50000, 50100, 50200]})
features_result = await features_adapter.get_features_data("BTC-USDT", "1Dutc", ohlcv_data)

# Получение рыночной метаинформации
market_meta_result = await market_meta_adapter.get_market_metadata("BTC-USDT")

# Сохранение результатов в базу данных
db_result = await database_adapter.save_context_result(context_result)
```

### Кастомная конфигурация

```python
from src.mtf.integration import IntegrationConfig

config = IntegrationConfig(
    features_settings={
        'enabled': True,
        'module_path': 'src.features.core',
        'function_name': 'compute_features',
        'default_specs': ['ema_21', 'rsi_14', 'macd']
    },
    market_meta_settings={
        'enabled': True,
        'cache_duration_seconds': 600,
        'validate_orders': True
    },
    database_settings={
        'enabled': True,
        'connection_string': 'postgresql://user:pass@localhost:5432/dbname',
        'pool_size': 20
    },
    timeout_settings={
        'features_timeout': 60.0,
        'market_meta_timeout': 15.0,
        'database_timeout': 30.0
    }
)

features_adapter = FeaturesAdapter(config)
```

## 📊 Модели данных

### IntegrationResult

```python
@dataclass
class IntegrationResult:
    source: DataSource
    status: ConnectionStatus
    data: Optional[Any]
    timestamp: datetime
    duration_seconds: float
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
```

### FeaturesData

```python
@dataclass
class FeaturesData:
    symbol: str
    timeframe: str
    features: pd.DataFrame
    timestamp: datetime
    source: DataSource
    specs_used: List[str]
    quality_score: float
    metadata: Dict[str, Any]
```

### MarketMetaData

```python
@dataclass
class MarketMetaData:
    symbol: str
    timestamp: datetime
    source: DataSource
    order_validation: Dict[str, Any]
    risk_limits: Dict[str, Any]
    liquidity_info: Dict[str, Any]
    quality_score: float
    metadata: Dict[str, Any]
```

### DatabaseResult

```python
@dataclass
class DatabaseResult:
    operation: str
    table: str
    status: ConnectionStatus
    rows_affected: int
    timestamp: datetime
    duration_seconds: float
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
```

### DataSource

```python
class DataSource(Enum):
    FEATURES = "features"
    MARKET_META = "market_meta"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
```

### ConnectionStatus

```python
class ConnectionStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TIMEOUT = "timeout"
```

## 🔧 Конфигурация

### YAML конфигурация

```yaml
integration:
  features_settings:
    enabled: true
    module_path: "src.features.core"
    function_name: "compute_features"
    default_specs:
      - "ema_21"
      - "ema_55"
      - "adx_14"
      - "atr_14"
      - "rsi_14"
      - "macd"
    volatility_normalize: true
  market_meta_settings:
    enabled: true
    module_path: "src.market_meta.api"
    function_name: "get_market_metadata"
    cache_duration_seconds: 300
    validate_orders: true
    check_risk_limits: true
  database_settings:
    enabled: true
    connection_string: "postgresql://user:pass@localhost:5432/dbname"
    pool_size: 10
    max_overflow: 20
    pool_timeout: 30
  timeout_settings:
    features_timeout: 30.0
    market_meta_timeout: 10.0
    database_timeout: 15.0
  retry_settings:
    max_retries: 3
    retry_delay: 1.0
    backoff_factor: 2.0
  data_quality_settings:
    min_completeness: 0.8
    max_age_minutes: 30
    outlier_threshold: 3.0
    missing_data_threshold: 0.1
```

### Загрузка из файла

```python
config = IntegrationConfig.from_yaml("config/mtf_phase3.yaml")
features_adapter = FeaturesAdapter(config)
```

## 🔗 Features Adapter

### Получение данных индикаторов

```python
# Базовое использование
features_result = await features_adapter.get_features_data(
    symbol="BTC-USDT",
    timeframe="1Dutc",
    ohlcv_data=ohlcv_dataframe
)

if features_result.status == ConnectionStatus.CONNECTED:
    features_data = features_result.data
    print(f"Quality Score: {features_data.quality_score}")
    print(f"Specs Used: {features_data.specs_used}")
    print(f"Data Points: {len(features_data.features)}")
```

### Кастомные спецификации

```python
# Использование кастомных спецификаций
custom_specs = ['ema_21', 'rsi_14', 'macd', 'bollinger_bands']
features_result = await features_adapter.get_features_data(
    symbol="ETH-USDT",
    timeframe="4H",
    ohlcv_data=ohlcv_dataframe,
    specs=custom_specs
)
```

### Проверка состояния подключения

```python
health_status = await features_adapter.check_connection_health()
print(f"Features module status: {health_status}")
```

## 🏪 Market Meta Adapter

### Получение рыночной метаинформации

```python
# Получение метаданных
market_meta_result = await market_meta_adapter.get_market_metadata("BTC-USDT")

if market_meta_result.status == ConnectionStatus.CONNECTED:
    meta_data = market_meta_result.data
    print(f"Order Validation: {meta_data.order_validation}")
    print(f"Risk Limits: {meta_data.risk_limits}")
    print(f"Liquidity Info: {meta_data.liquidity_info}")
```

### Структура метаданных

```python
# Order Validation
{
    'min_order_size': 0.001,
    'max_order_size': 1000.0,
    'tick_size': 0.01,
    'step_size': 0.001,
    'min_notional': 5.0,
    'max_notional': 1000000.0
}

# Risk Limits
{
    'max_position_size': 0.02,  # 2%
    'daily_loss_limit': 0.05,   # 5%
    'max_leverage': 3.0,
    'margin_requirement': 0.1
}

# Liquidity Info
{
    'bid_ask_spread': 0.0001,
    'volume_24h': 1000000.0,
    'liquidity_score': 0.8,
    'market_depth': 0.7
}
```

## 🗄️ Database Adapter

### Сохранение результатов

```python
# Сохранение контекста
context_db_result = await database_adapter.save_context_result(context_result)

# Сохранение триггеров
triggers_db_result = await database_adapter.save_triggers_result(triggers_result)

# Сохранение консенсуса
consensus_db_result = await database_adapter.save_consensus_result(consensus_result)

# Проверка результатов
for result in [context_db_result, triggers_db_result, consensus_db_result]:
    if result.status == ConnectionStatus.CONNECTED:
        print(f"{result.operation}: {result.rows_affected} rows affected")
    else:
        print(f"{result.operation} failed: {result.errors}")
```

### Получение исторических данных

```python
# Получение исторических данных
historical_result = await database_adapter.get_historical_data(
    symbol="BTC-USDT",
    timeframe="1Dutc",
    limit=1000
)

if historical_result.status == ConnectionStatus.CONNECTED:
    data = historical_result.data
    print(f"Records: {data['records_count']}")
```

### Пакетные операции

```python
# Выполнение пакетных операций
operations = [
    {'type': 'save_context', 'data': context_result},
    {'type': 'save_triggers', 'data': triggers_result},
    {'type': 'save_consensus', 'data': consensus_result}
]

batch_results = await database_adapter.execute_batch_operations(operations)
```

## 📊 Контроль качества данных

### Метрики качества

```python
# Получение метрик качества
quality_metrics = features_data.metadata['quality_metrics']

print(f"Completeness: {quality_metrics.completeness:.1%}")
print(f"Accuracy: {quality_metrics.accuracy:.1%}")
print(f"Timeliness: {quality_metrics.timeliness:.1%}")
print(f"Consistency: {quality_metrics.consistency:.1%}")
print(f"Overall Score: {quality_metrics.overall_score:.1%}")

# Проблемы и рекомендации
if quality_metrics.issues:
    print("Issues:")
    for issue in quality_metrics.issues:
        print(f"  - {issue}")

if quality_metrics.recommendations:
    print("Recommendations:")
    for rec in quality_metrics.recommendations:
        print(f"  - {rec}")
```

### Настройки качества

```python
config = IntegrationConfig(
    data_quality_settings={
        'min_completeness': 0.9,      # Минимум 90% полноты
        'max_age_minutes': 15,        # Данные не старше 15 минут
        'outlier_threshold': 2.5,     # Порог аномалий
        'missing_data_threshold': 0.05, # Максимум 5% пропусков
        'validate_ohlcv_logic': True,  # Проверка логики OHLCV
        'check_data_freshness': True   # Проверка свежести данных
    }
)
```

## ⚡ Производительность

### Настройки таймаутов

```python
config = IntegrationConfig(
    timeout_settings={
        'features_timeout': 60.0,     # 1 минута для features
        'market_meta_timeout': 15.0,  # 15 секунд для market_meta
        'database_timeout': 30.0,     # 30 секунд для database
        'external_api_timeout': 20.0  # 20 секунд для внешних API
    }
)
```

### Настройки повторных попыток

```python
config = IntegrationConfig(
    retry_settings={
        'max_retries': 5,             # Максимум 5 попыток
        'retry_delay': 2.0,           # Начальная задержка 2 секунды
        'backoff_factor': 1.5,        # Экспоненциальный backoff
        'retry_on_timeout': True,     # Повторять при таймауте
        'retry_on_connection_error': True  # Повторять при ошибках подключения
    }
)
```

## 🛡️ Обработка ошибок

### Проверка статуса подключения

```python
# Проверка состояния всех адаптеров
features_health = await features_adapter.check_connection_health()
market_meta_health = await market_meta_adapter.check_connection_health()
database_health = await database_adapter.check_connection_health()

print(f"Features: {features_health}")
print(f"Market Meta: {market_meta_health}")
print(f"Database: {database_health}")
```

### Обработка ошибок интеграции

```python
result = await features_adapter.get_features_data("BTC-USDT", "1Dutc", ohlcv_data)

if result.status == ConnectionStatus.ERROR:
    print("Integration failed:")
    for error in result.errors:
        print(f"  - {error}")

    for warning in result.warnings:
        print(f"  Warning: {warning}")

elif result.status == ConnectionStatus.TIMEOUT:
    print("Integration timeout")

elif result.status == ConnectionStatus.CONNECTED:
    print("Integration successful")
    data = result.data
    # Использование данных
```

## 🧪 Тестирование

### Unit тесты

```python
import pytest
from src.mtf.integration import FeaturesAdapter, IntegrationConfig

@pytest.mark.asyncio
async def test_features_adapter():
    config = IntegrationConfig.default()
    adapter = FeaturesAdapter(config)

    import pandas as pd
    ohlcv_data = pd.DataFrame({'close': [50000, 50100, 50200]})

    result = await adapter.get_features_data("BTC-USDT", "1Dutc", ohlcv_data)

    assert result.source == DataSource.FEATURES
    assert result.status in [ConnectionStatus.CONNECTED, ConnectionStatus.ERROR]
    assert result.duration_seconds >= 0
```

### Интеграционные тесты

```python
@pytest.mark.asyncio
async def test_full_integration():
    config = IntegrationConfig.default()
    features_adapter = FeaturesAdapter(config)
    market_meta_adapter = MarketMetaAdapter(config)
    database_adapter = DatabaseAdapter(config)

    # Тест полной интеграции
    features_result = await features_adapter.get_features_data("BTC-USDT", "1Dutc", ohlcv_data)
    market_meta_result = await market_meta_adapter.get_market_metadata("BTC-USDT")

    assert features_result.status == ConnectionStatus.CONNECTED
    assert market_meta_result.status == ConnectionStatus.CONNECTED
```

## 📈 Мониторинг

### Метрики интеграции

- Время выполнения запросов
- Статус подключений
- Качество данных
- Количество ошибок и предупреждений
- Использование кэша

### Алерты

- Потеря подключения к внешним модулям
- Низкое качество данных
- Превышение таймаутов
- Высокий уровень ошибок

## 🔄 Эволюция

### Версионирование

- Семантическое версионирование
- Обратная совместимость API
- Миграционные скрипты

### Расширяемость

- Добавление новых адаптеров
- Кастомные валидаторы качества данных
- Плагинная архитектура
- Настраиваемые метрики
