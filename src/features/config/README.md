# Config Layer

**Конфигурация модуля features**

## Обзор

Config Layer управляет настройками модуля: размеры батчей, параметры streaming, retry политики и feature flags.

## Структура

```
config/
├── __init__.py    # Экспорты (FeaturesSettings)
├── settings.py    # Конфигурация и фабрики
└── README.md
```

## Использование

### Через централизованную конфигурацию (рекомендуется)

```python
from src.config import get_settings

settings = get_settings()
features_config = settings.features

print(features_config.chunk_size)      # 200000
print(features_config.overlap_size)    # 200
print(features_config.batch_size)      # 50000
```

### FeaturesSettings

```python
@dataclass
class FeaturesSettings:
    # Streaming
    chunk_size: int = 200_000        # Размер чанка для streaming
    max_lookback: int = 200          # Максимальный lookback индикаторов
    overlap_size: int = 200          # Перекрытие между чанками

    # Database
    batch_size: int = 50_000         # Размер батча для UPSERT
    insert_chunk_size: int = 50_000  # Размер чанка для вставки

    # Quality
    min_fill_rate: float = 0.5       # Минимальный fill rate
    validate_results: bool = True    # Валидировать результаты

    # Normalization
    volatility_normalize: bool = True  # Нормализация волатильности
    normalize_window: int = 20         # Окно нормализации

    # Performance
    parallel_workers: int = 4        # Параллельные воркеры
    batch_timeout: int = 300         # Таймаут батча (сек)
    force_gc_after_chunk: bool = True  # GC после чанка

    # Retry
    max_retries: int = 3             # Максимум повторов
    retry_delay: float = 1.0         # Базовая задержка
    retry_backoff_factor: float = 2.0  # Множитель backoff

    # Database optimizations
    use_copy_from: bool = True       # Использовать COPY FROM
    temp_table_prefix: str = "temp_indicators_"

    # Debug
    log_memory: bool = True          # Логировать память
    verbose: bool = False            # Подробные логи
```

### Фабрики конфигурации

```python
from src.features.config.settings import (
    create_streaming_config,
    create_database_config,
    create_feature_config
)

# Конфиг для streaming (большие датасеты)
streaming = create_streaming_config(
    chunk_size=500_000,
    overlap=300
)

# Конфиг для БД
db_config = create_database_config(
    batch_size=100_000,
    use_copy_from=True
)

# Конфиг расчёта
feature_config = create_feature_config(
    volatility_normalize=True,
    normalize_window=30
)
```

### Environment Variables

```python
from src.features.config.settings import load_config_from_env

config = load_config_from_env()
# Читает: FEATURES_CHUNK_SIZE, FEATURES_BATCH_SIZE, ...
```

| Variable | Default | Описание |
|----------|---------|----------|
| FEATURES_CHUNK_SIZE | 200000 | Размер чанка |
| FEATURES_BATCH_SIZE | 50000 | Размер батча |
| FEATURES_OVERLAP | 200 | Перекрытие |
| FEATURES_NORMALIZE | true | Нормализация |
| FEATURES_VERBOSE | false | Подробные логи |

## Тестирование

```bash
pytest tests/features/tests/test_core.py -v
```
