# MTF Phase 3 Configuration Files

Централизованные конфигурационные файлы для всех модулей MTF Phase 3.

## 📁 Структура конфигураций

```
config/
├── mtf_phase3.yaml              # Основная конфигурация
├── mtf_phase3_production.yaml   # Продакшн конфигурация
├── mtf_phase3_development.yaml  # Конфигурация для разработки
└── README.md                    # Документация конфигураций
```

## 🎯 Назначение файлов

### `mtf_phase3.yaml`
- **Основная конфигурация** для всех модулей
- Сбалансированные настройки для общего использования
- Рекомендуется для тестирования и staging

### `mtf_phase3_production.yaml`
- **Продакшн конфигурация** с оптимизированными настройками
- Более строгие пороги и валидация
- Улучшенная производительность и мониторинг
- Повышенная безопасность

### `mtf_phase3_development.yaml`
- **Конфигурация для разработки** с упрощенными настройками
- Мягкие пороги для быстрого тестирования
- Отключенные внешние зависимости
- Расширенное логирование

## 🔧 Использование конфигураций

### Загрузка основной конфигурации

```python
from src.mtf.context import ContextConfig
from src.mtf.triggers import TriggersConfig
from src.mtf.consensus import ConsensusConfig
from src.mtf.pipeline import PipelineConfig
from src.mtf.integration import IntegrationConfig

# Загрузка из основного файла
context_config = ContextConfig.from_yaml("config/mtf_phase3.yaml")
triggers_config = TriggersConfig.from_yaml("config/mtf_phase3.yaml")
consensus_config = ConsensusConfig.from_yaml("config/mtf_phase3.yaml")
pipeline_config = PipelineConfig.from_yaml("config/mtf_phase3.yaml")
integration_config = IntegrationConfig.from_yaml("config/mtf_phase3.yaml")
```

### Загрузка продакшн конфигурации

```python
# Загрузка продакшн конфигурации
context_config = ContextConfig.from_yaml("config/mtf_phase3_production.yaml")
```

### Загрузка конфигурации для разработки

```python
# Загрузка конфигурации для разработки
context_config = ContextConfig.from_yaml("config/mtf_phase3_development.yaml")
```

## 📊 Основные секции конфигурации

### Context Builder
```yaml
context:
  timeframes: ["1Mutc", "1Wutc", "1Dutc", "4H", "1H"]
  validity_thresholds:
    "1Mutc": 0.4
    "1Wutc": 0.35
    # ...
  trend_weights:
    ema_trend: 0.4
    adx_strength: 0.25
    # ...
```

### Triggers Builder
```yaml
triggers:
  timeframes: ["15m", "5m", "1m"]
  reversal_weights:
    "15m":
      rsi: 0.25
      macd: 0.25
      # ...
  noise_filter_thresholds:
    "15m":
      min_volume_ratio: 0.8
      max_atr_ratio: 2.0
      # ...
```

### Consensus Builder
```yaml
consensus:
  horizons: ["intraday", "swing", "week"]
  horizon_weights:
    intraday:
      "1Dutc": 0.4
      "4H": 0.3
      # ...
  decision_thresholds:
    intraday:
      context_min: 0.15
      trigger_p_min: 0.55
      # ...
```

### Pipeline Orchestrator
```yaml
pipeline:
  context_timeframes: ["1Mutc", "1Wutc", "1Dutc", "4H", "1H"]
  trigger_timeframes: ["15m", "5m", "1m"]
  consensus_horizons: ["intraday", "swing", "week"]
  max_retries: 3
  timeout_seconds: 300.0
  parallel_processing: true
  max_workers: 4
```

### Integration Module
```yaml
integration:
  features_settings:
    enabled: true
    module_path: "src.features.core"
    function_name: "compute_features"
    default_specs:
      - "ema_21"
      - "ema_55"
      # ...
  database_settings:
    enabled: true
    connection_string: "postgresql://user:pass@localhost:5432/dbname"
    pool_size: 10
```

## 🔄 Переменные окружения

### Продакшн конфигурация
```yaml
security:
  encryption_key: "${ENCRYPTION_KEY}"  # Из переменных окружения
```

### Использование переменных окружения
```bash
export ENCRYPTION_KEY="your-production-encryption-key"
export DB_PASSWORD="your-database-password"
export API_KEY="your-api-key"
```

## 📈 Настройки производительности

### Development
- Меньше таймфреймов и горизонтов
- Мягкие пороги валидации
- Отключенное параллельное выполнение
- Расширенное логирование

### Production
- Полный набор таймфреймов и горизонтов
- Строгие пороги валидации
- Параллельное выполнение
- Оптимизированное логирование
- Увеличенные лимиты ресурсов

## 🛡️ Настройки безопасности

### Development
```yaml
security:
  enable_encryption: false
  enable_audit_log: false
  rate_limit_requests_per_minute: 1000
```

### Production
```yaml
security:
  enable_encryption: true
  encryption_key: "${ENCRYPTION_KEY}"
  enable_audit_log: true
  rate_limit_requests_per_minute: 200
```

## 📊 Мониторинг и алерты

### Development
```yaml
monitoring:
  enable_alerts: false
  alert_thresholds:
    error_rate: 0.3
    response_time_ms: 10000
```

### Production
```yaml
monitoring:
  enable_alerts: true
  alert_thresholds:
    error_rate: 0.05
    response_time_ms: 3000
```

## 🔧 Кастомизация конфигураций

### Создание собственной конфигурации

```python
# Создание кастомной конфигурации
from src.mtf.context import ContextConfig

custom_config = ContextConfig(
    timeframes=["1Dutc", "4H"],
    validity_thresholds={
        "1Dutc": 0.3,
        "4H": 0.25
    },
    trend_weights={
        "ema_trend": 0.5,
        "adx_strength": 0.3,
        "rsi_momentum": 0.2
    }
)
```

### Переопределение настроек

```python
# Загрузка базовой конфигурации и переопределение
base_config = ContextConfig.from_yaml("config/mtf_phase3.yaml")

# Переопределение отдельных параметров
base_config.validity_thresholds["1Dutc"] = 0.5
base_config.trend_weights["ema_trend"] = 0.6
```

## 🧪 Тестирование конфигураций

### Валидация конфигурации

```python
def validate_config(config_path: str) -> bool:
    """Валидация конфигурационного файла"""
    try:
        config = ContextConfig.from_yaml(config_path)

        # Проверка обязательных полей
        assert config.timeframes, "timeframes is required"
        assert config.validity_thresholds, "validity_thresholds is required"
        assert config.trend_weights, "trend_weights is required"

        # Проверка значений
        for tf in config.timeframes:
            assert tf in config.validity_thresholds, f"Missing threshold for {tf}"

        return True
    except Exception as e:
        print(f"Config validation failed: {e}")
        return False

# Валидация всех конфигураций
configs = [
    "config/mtf_phase3.yaml",
    "config/mtf_phase3_production.yaml",
    "config/mtf_phase3_development.yaml"
]

for config_path in configs:
    is_valid = validate_config(config_path)
    print(f"{config_path}: {'✓' if is_valid else '✗'}")
```

## 📝 Рекомендации

### Для разработки
1. Используйте `mtf_phase3_development.yaml`
2. Отключите внешние зависимости
3. Уменьшите пороги валидации
4. Включите расширенное логирование

### Для тестирования
1. Используйте `mtf_phase3.yaml`
2. Проверьте все модули
3. Настройте мониторинг
4. Протестируйте производительность

### Для продакшна
1. Используйте `mtf_phase3_production.yaml`
2. Настройте переменные окружения
3. Включите все проверки безопасности
4. Настройте алерты и мониторинг

## 🔄 Обновление конфигураций

### Версионирование
- Используйте семантическое версионирование
- Сохраняйте обратную совместимость
- Документируйте изменения

### Миграция
- Создавайте скрипты миграции
- Тестируйте изменения на staging
- Планируйте откат изменений
