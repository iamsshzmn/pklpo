# Структура features_combinations

## Организация модуля

```
src/features_combinations/
├── domain/                    # Домейн-слой
│   ├── models.py             # CombinationRow (домейн-модель)
│   ├── registry.py           # Централизованный реестр комбинаций
│   ├── pairs.py              # Комбинации из 2 индикаторов
│   ├── trios.py              # Комбинации из 3 индикаторов
│   └── quartets.py           # Комбинации из 4 индикаторов
│
├── application/              # Application-слой
│   ├── ports.py              # Протоколы (IndicatorProvider, CombinationCalculator)
│   └── service.py            # CombinationService (оркестрация)
│
├── infrastructure/           # Infrastructure-слой
│   ├── indicator_provider.py    # PostgresIndicatorProvider
│   ├── numeric_calculator.py    # NumericCombinationCalculator
│   ├── numeric_analyzer.py       # NumericSignalAnalyzer
│   ├── repository.py            # PostgresCombinationRepository
│   └── upsert_helper.py          # Helper для UPSERT операций
│
├── cli/                      # CLI команды
│   └── main.py               # CLI интерфейс
│
├── archive/                  # Устаревший код
│   ├── analyzer.py           # Старый SignalAnalyzer (текстовые сигналы)
│   ├── calculator.py         # Старый CombinationCalculator
│   ├── performance.py        # Старый PerformanceAnalyzer
│   ├── recommendations.py    # Старый RecommendationGenerator
│   ├── cli.py                # Старый CLI
│   └── providers/           # Старые провайдеры
│
├── logging_config.py         # Конфигурация логирования
├── __init__.py               # Публичный API модуля
├── README.md                 # Документация
└── IMPLEMENTATION_ROADMAP.md # План реализации и roadmap
```

## Принципы организации

### Domain Layer
- **models.py**: Домейн-модели (CombinationRow)
- **registry.py, pairs.py, trios.py, quartets.py**: Реестр комбинаций индикаторов

### Application Layer
- **ports.py**: Протоколы (интерфейсы) для dependency injection
- **service.py**: Бизнес-логика (оркестрация расчёта и сохранения)

### Infrastructure Layer
- **indicator_provider.py**: Загрузка индикаторов из БД
- **numeric_calculator.py**: Расчёт numeric features
- **numeric_analyzer.py**: Преобразование сигналов в числа
- **repository.py**: Работа с БД (UPSERT, загрузка)
- **upsert_helper.py**: Вспомогательные функции для UPSERT

### CLI
- **cli/main.py**: Командный интерфейс для запуска расчётов

## Использование

```python
# Импорт основных компонентов
from src.features_combinations import COMBINATIONS, CombinationRow
from src.features_combinations.application import CombinationService
from src.features_combinations.infrastructure import (
    PostgresIndicatorProvider,
    NumericCombinationCalculator,
    PostgresCombinationRepository,
)

# CLI
python -m src.features_combinations.cli compute \
    --symbol BTC-USDT-SWAP \
    --timeframes 1m 5m 15m \
    --start 2025-01-01 \
    --end 2025-01-31
```

## Миграция со старой структуры

Старые файлы (analyzer.py, calculator.py, recommendations.py, performance.py) перемещены в `archive/` и больше не используются. Новый код использует numeric-only подход без текстовых рекомендаций.
