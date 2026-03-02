
# Анализ зависимостей модуля src/features

## Структура директории src/

```
src/
├── alerts/                 # Система оповещений
├── api/                    # API интеграции
├── backtest/               # Бэктестирование
├── candles/                # Обработка свечей
├── cli/                    # Главный CLI интерфейс
├── config/                 # Централизованная конфигурация
├── data/                   # Обработка данных
├── database.py             # Инициализация БД
├── db/                     # Утилиты БД
├── features/               # ОСНОВНОЙ МОДУЛЬ
├── features_combinations/  # Комбинации индикаторов
├── logging_config.py       # Логирование
├── market_meta/            # Метаданные рынка
├── market_selection/       # Выбор рынков
├── metrics/                # Метрики
├── models.py               # SQLAlchemy ORM модели
├── mtf/                    # Multi-timeframe анализ
├── positions/              # Управление позициями
├── risk/                   # Risk management
├── scoring_engine/         # Engine для скоринга
├── settings/               # Settings модуль
├── signals/                # Генерация сигналов
├── trade_recommender/      # Recommender система
├── tuning/                 # Оптимизация параметров
├── utils/                  # Утилиты
└── visual/                 # Визуализация
```

---

## Сводная таблица зависимостей

| Модуль | Направление | Тип | Файлов | Импортов | Экспортируется |
|--------|-------------|-----|--------|----------|----------------|
| **src.config** | features ← src | Односторонняя | 3 | 5 | `FeaturesSettings, get_settings` |
| **src.models** | features ← src | Односторонняя | 4 | 4 | `Indicator, OHLCV, CalculationMetadata` |
| **src.database** | features ← src | Односторонняя | 6 | 9 | `get_async_session` |
| **src.utils** | features ← src | Односторонняя | 1 | 1 | `get_db_session` |
| **src.db** | features ← src | Односторонняя | 1 | 1 | `ensure_columns` |
| **src.cli** | features ↔ src | Двусторонняя | 2 | 6 | `compute_features, FEATURE_SPECS` |
| **src.mtf** | features → src | Односторонняя | 1 | 2 | Планируется: `compute_features` |

---

## Исходящие зависимости (features импортирует ИЗ других модулей)

### 1. src.config
- **Что импортируется**: `FeaturesSettings`, `get_settings`
- **Файлы**:
  - `src/features/application/calc.py:16`
  - `src/features/application/save.py:26`
  - `src/features/config/__init__.py:6`
  - `src/features/config/settings.py:23`

### 2. src.models
- **Что импортируется**: `Indicator`, `OHLCV`, `CalculationMetadata`
- **Файлы**:
  - `src/features/infrastructure/db_operations.py:8`
  - `src/features/application/save.py:27`
  - `src/features/infrastructure/versioning.py:386`
  - `src/features/schema/schema_manager.py:329`

### 3. src.database
- **Что импортируется**: `get_async_session`
- **Файлы**:
  - `src/features/cli/check_database_setup.py:17`
  - `src/features/cli/main.py:105, 238, 312, 353`
  - `src/features/application/save.py:757`
  - `src/features/tests/test_db_integration_smoke.py:7`
  - `src/features/tests/test_stage_a.py:9`
  - `src/features/tests/test_stage_b.py:9`

### 4. src.utils
- **Что импортируется**: `get_db_session` из `session_utils`
- **Файлы**:
  - `src/features/cli/schema_check.py:24`

### 5. src.db
- **Что импортируется**: `ensure_columns` из `db_schema_utils`
- **Файлы**:
  - `src/features/infrastructure/db_operations.py:28`

### 6. src.cli (циклическая)
- **Что импортируется**: `handle` из `src.cli.commands.features`
- **Файлы**:
  - `src/features/__main__.py:40`

---

## Входящие зависимости (кто импортирует features)

### 1. src.cli
- **Файл**: `src/cli/commands/features.py`
- **Импортирует**:
  - `compute_features` из `src.features`
  - `infrastructure.database` функции
  - `logging_config` - `get_features_logger, log_features_summary`
  - `specs.FEATURE_SPECS`

### 2. src.mtf
- **Файл**: `src/mtf/integration/features_adapter.py`
- **Импортирует** (закомментировано):
  - `src.features.core.compute_features`

---

## План проверки зависимостей

### Этап 1: Базовые зависимости (критические)

| # | Задача | Файлы | Проверка |
|---|--------|-------|----------|
| 1.1 | src.config | `features/config/settings.py`, `features/application/calc.py` | Импорт `FeaturesSettings`, `get_settings` |
| 1.2 | src.models | `features/infrastructure/db_operations.py`, `features/application/save.py` | Импорт `Indicator`, `OHLCV`, `CalculationMetadata` |
| 1.3 | src.database | `features/cli/main.py`, `features/application/save.py` | Импорт `get_async_session` |

### Этап 2: Вспомогательные зависимости

| # | Задача | Файлы | Проверка |
|---|--------|-------|----------|
| 2.1 | src.utils | `features/cli/schema_check.py` | `get_db_session` из `session_utils` |
| 2.2 | src.db | `features/infrastructure/db_operations.py` | `ensure_columns` из `db_schema_utils` |

### Этап 3: Циклические зависимости

| # | Задача | Файлы | Проверка |
|---|--------|-------|----------|
| 3.1 | features → cli | `features/__main__.py` | Ленивый импорт, отсутствие runtime циклов |
| 3.2 | cli → features | `cli/commands/features.py` | API: `compute_features`, `FEATURE_SPECS` |

### Этап 4: Входящие зависимости

| # | Задача | Файлы | Проверка |
|---|--------|-------|----------|
| 4.1 | src.cli | `cli/commands/features.py` | Корректность API |
| 4.2 | src.mtf | `mtf/integration/features_adapter.py` | Закомментированные импорты |

### Этап 5: Тестовые зависимости

| # | Задача | Файлы | Проверка |
|---|--------|-------|----------|
| 5.1 | test imports | `features/tests/test_db_integration_smoke.py`, `test_stage_a.py`, `test_stage_b.py` | Прямые импорты `src.database` |

---

## Команды проверки

```bash
# 1. Проверка импортов (синтаксис)
python -c "from src.features import compute_features"
python -c "from src.features.specs import FEATURE_SPECS"

# 2. Проверка циклических зависимостей
python -c "import src.features; import src.cli"

# 3. Запуск smoke-тестов импортов
pytest src/features/tests/test_smoke_imports.py -v

# 4. Полная проверка типов
mypy src/features/ --ignore-missing-imports

# 5. Проверка всех зависимостей (ОБНОВЛЕНО 2026-01-30)
python -c "
from src.features.application.calc import process_chunks
from src.features.application.save import save_parquet_to_pg
from src.features.core import compute_features
from src.features.specs import FEATURE_SPECS
from src.cli.commands.features import handle
print('All imports OK')
print(f'FEATURE_SPECS count: {len(FEATURE_SPECS)}')
"
```

---

## Рекомендации

1. **Избегать прямых импортов features в src.mtf** - использовать адаптер (features_adapter.py)

2. **Минимизировать импорты из src.database в features** - все DB операции через infrastructure слой

3. **Переместить testing-specific импорты** - тесты используют прямые импорты из src.database, лучше обернуть в test fixtures

4. **Документировать циклическую зависимость CLI** - добавить комментарии в features/__main__.py

---

## Диаграмма зависимостей

```
                    ┌─────────────┐
                    │  src.config │
                    └──────┬──────┘
                           │
                           ▼
┌──────────┐       ┌───────────────┐       ┌──────────┐
│ src.cli  │◄─────►│ src.features  │◄──────│ src.mtf  │
└──────────┘       └───────┬───────┘       └──────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
       ┌──────────┐ ┌────────────┐ ┌─────────┐
       │src.models│ │src.database│ │ src.db  │
       └──────────┘ └────────────┘ └─────────┘
                           │
                           ▼
                    ┌──────────┐
                    │src.utils │
                    └──────────┘
```

---

## Результаты проверки (2026-01-30)

### Этап 1: Базовые зависимости

| # | Проверка | Статус | Примечание |
|---|----------|--------|------------|
| 1.1 | `from src.features import compute_features` | OK | 177 specs загружено |
| 1.2 | `from src.features.specs import FEATURE_SPECS` | OK | |
| 1.3 | `from src.config import get_settings, FeaturesSettings` | OK | |
| 1.4 | `from src.models import Indicator, OHLCV` | OK | |
| 1.5 | `from src.database import get_async_session` | OK | |

### Этап 2: Вспомогательные зависимости

| # | Проверка | Статус | Примечание |
|---|----------|--------|------------|
| 2.1 | `from src.utils.session_utils import get_db_session` | OK | |
| 2.2 | `from src.db.db_schema_utils import ensure_columns` | OK | |

### Этап 3: Циклические зависимости

| # | Проверка | Статус | Примечание |
|---|----------|--------|------------|
| 3.1 | `import src.features; import src.cli` | OK | Нет ошибки циклического импорта |
| 3.2 | `from src.cli.commands.features import handle` | OK | Исправлено PROBLEM-001 |

### Этап 4: Входящие зависимости

| # | Проверка | Статус | Примечание |
|---|----------|--------|------------|
| 4.1 | `src.cli.commands.features` API | OK | `compute_features`, `FEATURE_SPECS`, `handle` работают |
| 4.2 | `src.mtf.integration.features_adapter` | OK | Импорт закомментирован (заглушка), ожидаемое поведение |

### Этап 5: Тестовые зависимости

| # | Проверка | Статус | Примечание |
|---|----------|--------|------------|
| 5.1 | `test_db_integration_smoke.py` | OK | |
| 5.2 | `test_stage_a.py` | OK | |
| 5.3 | `test_stage_b.py` | OK | |

---

### Исправленные проблемы

#### PROBLEM-001: Сломанный импорт в src/cli/commands/features.py [FIXED]

**Ошибка:**
```
ModuleNotFoundError: No module named 'src.features.logging_config'
```

**Причина:** Файл `src/cli/commands/features.py:24` импортировал:
```python
from src.features.logging_config import get_features_logger, log_features_summary
```

Но модуль был перемещён в:
```python
src.features.observability.logging
```

**Решение:** Обновлён импорт в `src/cli/commands/features.py`:
```python
from src.features.observability.logging import get_features_logger, log_features_summary
```

---

## Финальная проверка

```bash
# Комплексная проверка всех зависимостей
python -c "
from src.features.application.calc import process_chunks
from src.features.application.save import save_parquet_to_pg
from src.features.core import compute_features
from src.features.specs import FEATURE_SPECS
from src.cli.commands.features import handle
print('All imports OK')
print(f'FEATURE_SPECS count: {len(FEATURE_SPECS)}')
"
# Результат: All imports OK, FEATURE_SPECS count: 177
```

---

## Итоги

| Этап | Статус | Проверок | Проблем |
|------|--------|----------|---------|
| 1. Базовые зависимости | OK | 5/5 | 0 |
| 2. Вспомогательные | OK | 2/2 | 0 |
| 3. Циклические | OK | 2/2 | 1 (исправлено) |
| 4. Входящие | OK | 2/2 | 0 |
| 5. Тестовые | OK | 3/3 | 0 |
| **ИТОГО** | **OK** | **14/14** | **1 (исправлено)** |

---

*Документ создан: 2026-01-30*
*Последняя проверка: 2026-01-30*
*Все зависимости проверены и работают корректно*
