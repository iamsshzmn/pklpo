# MTF Architecture v2.0 - Промышленная система анализа

## Обзор

MTF v2.0 - это полностью переработанная промышленная система анализа мультитаймфреймовых сигналов с акцентом на:

- **Версионирование и контракты данных** - четкие схемы с версиями
- **Мониторинг качества данных** - проверка свежести, валидности, отсутствие look-ahead
- **Система алертов** - Slack, Telegram, логирование
- **Трассировка выполнения** - run_id, метрики, производительность
- **Риск-менеджмент** - лимиты, корреляции, стопы
- **Конфигурационное управление** - централизованные настройки

## Архитектура

```
MTF v2.0
├── config/          # Конфигурация и настройки
│   └── settings.py  # Централизованная конфигурация
├── monitoring/      # Мониторинг и алерты
│   ├── data_quality.py  # Мониторинг качества данных
│   └── alerts.py        # Система алертов
├── models/          # Схемы данных
│   └── schema.py    # SQLAlchemy модели с версионированием
├── utils/           # Утилиты
│   └── run_tracker.py  # Трассировка выполнения
├── etl/             # ETL процессы
│   ├── context_loader.py    # Загрузка контекста
│   ├── trigger_loader.py    # Загрузка триггеров
│   └── consensus_writer.py  # Запись консенсуса
├── risk/            # Риск-менеджмент (планируется)
├── signals/         # Генерация сигналов (планируется)
├── backtest/        # Бэктестинг (планируется)
└── cli/             # Командные интерфейсы
    └── cli_enhanced.py  # Расширенный CLI
```

## Основные компоненты

### 1. Конфигурация (`config/settings.py`)

Централизованное управление всеми настройками:

```python
from src.mtf import mtf_config

# Настройки таймфреймов
timeframes = mtf_config.get_all_timeframes()

# Настройки риск-менеджмента
max_position_size = mtf_config.risk.max_position_size
daily_loss_limit = mtf_config.risk.daily_loss_limit

# Настройки качества данных
max_data_age = mtf_config.data_quality.max_data_age_minutes
```

### 2. Мониторинг качества данных (`monitoring/data_quality.py`)

Проверка свежести, валидности и отсутствия look-ahead:

```python
from src.mtf import check_data_quality, quality_monitor

# Проверка конкретного символа
metrics = await check_data_quality("BTC-USDT")
print(f"Статус: {metrics.status.value}")
print(f"Возраст данных: {metrics.data_age_minutes:.1f} мин")

# Сводка по всем символам
summary = await check_data_quality()
print(f"Общий статус: {summary['overall_status']}")
```

### 3. Система алертов (`monitoring/alerts.py`)

Многоканальные алерты (Slack, Telegram, логирование):

```python
from src.mtf import alert_manager

# Отправка алертов
await alert_manager.send_critical_alert(
    "Критическая ошибка",
    "Описание проблемы",
    source="MTF System"
)

# Тестирование каналов
results = await alert_manager.test_all_channels()
```

### 4. Трассировка выполнения (`utils/run_tracker.py`)

Уникальные run_id и метрики производительности:

```python
from src.mtf import run_tracker, track_run, run_context

# Автоматический трекинг
@track_run("mtf_analysis")
async def analyze_symbol(symbol: str):
    # Ваш код здесь
    pass

# Ручной трекинг
async with run_context("custom_operation") as run_id:
    # Ваш код здесь
    run_tracker.update_metrics(run_id, rows_processed=100)
```

### 5. Схемы данных (`models/schema.py`)

Версионированные таблицы с контрактами:

```python
from src.mtf import MTFContext, MTFTriggers, MTFConsensus

# Валидация данных
errors = validate_data_contract(data, "mtf_context")
if errors:
    print(f"Ошибки валидации: {errors}")

# Получение версии схемы
schema_version = get_schema_version()
```

## Быстрый старт

### 1. Установка и настройка

```bash
# Клонирование репозитория
git clone <repository>
cd pklpo

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
export SLACK_WEBHOOK_URL="your_slack_webhook"
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

### 2. Создание таблиц

```python
from src.mtf.models.schema import get_migration_scripts
from src.database import get_async_session

async def create_tables():
    async with get_async_session() as session:
        migration_script = get_migration_scripts()["v1"]
        await session.execute(text(migration_script))
        await session.commit()
```

### 3. Первый запуск

```python
from src.mtf import run_mtf_analysis, check_data_quality

# Проверка качества данных
quality = await check_data_quality("BTC-USDT")
print(f"Качество данных: {quality.status.value}")

# Запуск анализа
result = await run_mtf_analysis("BTC-USDT")
print(f"Результат: {result}")
```

## CLI команды

### Основные команды

```bash
# Запуск анализа
python src/mtf/cli_enhanced.py run --symbol BTC-USDT

# Проверка качества данных
python src/mtf/cli_enhanced.py quality --symbol BTC-USDT
python src/mtf/cli_enhanced.py quality --summary

# Получение сигналов
python src/mtf/cli_enhanced.py signals --horizon intraday --limit 5

# Тестирование алертов
python src/mtf/cli_enhanced.py test-alerts

# Мониторинг выполнения
python src/mtf/cli_enhanced.py monitor --hours 24

# Управление конфигурацией
python src/mtf/cli_enhanced.py config --show
python src/mtf/cli_enhanced.py config --save

# Статус системы
python src/mtf/cli_enhanced.py status --detailed
```

### Примеры вывода

```bash
$ python src/mtf/cli_enhanced.py quality --summary

🔍 Проверка качества данных...
📊 Получение сводки качества...

📈 Сводка качества данных:
📊 Всего символов: 50
🎯 Общий статус: good

📊 Статусы по категориям:
  excellent: 35
  good: 12
  warning: 2
  critical: 1
  unknown: 0

🚨 Критические проблемы:
  - ETH-USDT
```

## Конфигурация

### Основные настройки

```yaml
# config/mtf_config.yaml
version: "2.0.0"
schema_version: "v1"

consensus:
  mode: "hybrid"
  min_agreement: 0.6
  veto_threshold: 0.8

risk:
  max_position_size: 0.02  # 2%
  daily_loss_limit: 0.05   # 5%
  max_leverage: 3.0

data_quality:
  max_data_age_minutes: 30
  min_valid_rate: 0.95
  max_nan_rate: 0.05

exchange:
  name: "OKX"
  maker_fee: 0.0008
  taker_fee: 0.001
```

### Переменные окружения

```bash
# Алерты
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=-1001234567890

# База данных
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# Логирование
LOG_LEVEL=INFO
```

## Мониторинг и алерты

### Качество данных

Система автоматически проверяет:

- **Свежесть данных** - возраст последнего обновления
- **Валидность** - процент валидных записей
- **Look-ahead защита** - отсутствие данных из будущего
- **Аномалии** - спайки объема, расширение спредов

### Алерты

Автоматические алерты при:

- Критических проблемах качества данных
- Ошибках выполнения
- Превышении лимитов
- Аномалиях рынка

### Метрики

Система собирает метрики:

- Время выполнения операций
- Количество обработанных записей
- Успешность операций
- Статистика алертов

## Разработка

### Добавление новых компонентов

1. **Создание модуля**:
```python
# src/mtf/new_module/__init__.py
from .component import NewComponent

__all__ = ['NewComponent']
```

2. **Обновление основного __init__.py**:
```python
# src/mtf/__init__.py
from .new_module import NewComponent
```

3. **Добавление в CLI**:
```python
# src/mtf/cli_enhanced.py
def cmd_new_component(args):
    # Реализация команды
    pass
```

### Тестирование

```python
import pytest
from src.mtf import check_data_quality, run_mtf_analysis

@pytest.mark.asyncio
async def test_data_quality():
    metrics = await check_data_quality("BTC-USDT")
    assert metrics.status.value in ["excellent", "good", "warning", "critical"]

@pytest.mark.asyncio
async def test_mtf_analysis():
    result = await run_mtf_analysis("BTC-USDT", dry_run=True)
    assert result["status"] == "completed"
```

## Миграция с v1

### Основные изменения

1. **Новые таблицы**: `mtf_context`, `mtf_triggers`, `mtf_consensus`
2. **Версионирование**: все таблицы имеют `schema_version`, `algo_version`
3. **Качество данных**: автоматические проверки и алерты
4. **Трассировка**: уникальные `run_id` для каждого запуска

### Миграция данных

```python
from src.mtf.etl.context_loader import ContextLoader
from src.mtf.etl.trigger_loader import TriggerLoader
from src.mtf.etl.consensus_writer import ConsensusWriter

# Миграция существующих данных
async def migrate_v1_to_v2():
    # Загрузка контекста
    await ContextLoader().load_context_for_all_symbols()

    # Загрузка триггеров
    await TriggerLoader().load_triggers_for_all_symbols()

    # Запись консенсуса
    await ConsensusWriter().write_consensus_for_all_symbols()
```

## Планы развития

### Этап 2: Риск-менеджмент

- [ ] Модуль `risk/` с позиционным менеджментом
- [ ] Корреляционный анализ
- [ ] Динамическое плечо
- [ ] Стоп-лоссы и take-profit

### Этап 3: Торговые сигналы

- [ ] Модуль `signals/` с генерацией сигналов
- [ ] Валидация с биржевыми метаданными
- [ ] Управление позициями
- [ ] Интеграция с OKX API

### Этап 4: Бэктестинг

- [ ] Модуль `backtest/` с историческим тестированием
- [ ] Walk-forward анализ
- [ ] Оптимизация параметров
- [ ] Отчеты производительности

### Этап 5: Дашборд

- [ ] Веб-интерфейс для мониторинга
- [ ] Графики и метрики
- [ ] Управление конфигурацией
- [ ] Алерты в реальном времени

## Поддержка

### Логирование

Все операции логируются с контекстом:

```python
from src.mtf import get_run_logger

async with run_context("my_operation") as run_id:
    logger = get_run_logger(run_id)
    logger.info("Начало операции")
    logger.warning("Предупреждение")
    logger.error("Ошибка")
```

### Отладка

```python
# Включение отладочного режима
import logging
logging.getLogger("src.mtf").setLevel(logging.DEBUG)

# Проверка статуса системы
from src.mtf import run_tracker, quality_monitor
print(f"Активные запуски: {len(run_tracker.get_active_runs())}")
```

### Мониторинг

```python
# Получение статистики
stats = run_tracker.get_run_stats(24)
print(f"Успешность: {stats['success_rate']:.1%}")

# Проверка алертов
alert_stats = alert_manager.get_alert_stats(24)
print(f"Критических алертов: {alert_stats['critical']}")
```

## Заключение

MTF v2.0 предоставляет промышленную основу для анализа мультитаймфреймовых сигналов с акцентом на надежность, мониторинг и масштабируемость. Система готова для использования в продакшене и может быть расширена дополнительными модулями по мере необходимости.
