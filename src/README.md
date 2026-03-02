# Trading System - Main Source Directory

Основная директория торговой системы, содержащая все ключевые компоненты для работы с криптовалютными рынками. Система обеспечивает полный цикл: от получения данных с биржи до генерации торговых сигналов.

## Обзор

Директория `src` содержит:
- Основные модули системы торговых сигналов
- Интеграцию с биржей OKX
- Систему управления базой данных
- Расчет технических индикаторов
- Генерацию торговых сигналов
- Бэктестинг и оценку стратегий
- Систему уведомлений и визуализации

## Структура директории

### Основные файлы:

#### 1. Точки входа (`main.py`, `main_with_options.py`)

##### `main.py`
Основной файл системы - полный цикл работы:
- Миграции базы данных
- Загрузка инструментов
- Синхронизация свечей
- Расчет индикаторов
- Генерация сигналов

```python
# Запуск полного цикла
python src/main.py
```

##### `main_with_options.py`
Гибкий интерфейс с опциями командной строки:

```bash
# Только синхронизация свечей
python src/main_with_options.py --candles

# Только расчет индикаторов
python src/main_with_options.py --indicators

# Только сигналы для конкретного символа
python src/main_with_options.py --signals --symbol BTC-USDT

# Все этапы
python src/main_with_options.py --all
```

#### 2. База данных (`database.py`, `models.py`)

##### `database.py`
Конфигурация подключения к PostgreSQL:
- Асинхронное подключение через SQLAlchemy
- Настройка через переменные окружения
- Сессии для работы с базой данных

##### `models.py`
SQLAlchemy модели данных:

**Основные таблицы:**
- `Instrument` - торговые инструменты
- `OHLCV` - данные свечей
- `Indicator` - технические индикаторы
- `Signal` - базовые сигналы
- `SignalDetailed` - детализированные сигналы
- `CombinationResult` - результаты комбинаций

#### 3. Утилиты и конфигурация

##### `logging_config.py`
Настройка системы логирования:
- Ротация логов
- Форматирование сообщений
- Разные уровни логирования

##### `limiter.py`
Управление лимитами API:
- Ограничение запросов к бирже
- Предотвращение блокировок
- Асинхронные лимитеры

### Поддиректории:

#### `alerts/` - Система уведомлений
- Slack интеграция
- Алерты о сигналах
- Ежедневные сводки

#### `backtest/` - Бэктестинг
- Оценка качества сигналов
- Расчет метрик производительности
- Анализ стратегий

#### `candles/` - Данные свечей
- Синхронизация OHLCV данных
- Загрузка с биржи OKX
- Управление историческими данными

#### `db/` - Управление базой данных
- Миграции схемы
- Утилиты для работы с БД
- Создание и обновление таблиц

#### `indicators/` - Технические индикаторы
- Расчет индикаторов
- Группировка по типам
- Комбинации индикаторов

#### `okx/` - Интеграция с биржей
- API клиент для OKX
- Рыночные данные
- Управление ордерами

#### `signals/` - Торговые сигналы
- Генерация сигналов
- Правила торговли
- Детализированные сигналы

#### `tuning/` - Оптимизация параметров
- Grid search оптимизация
- Оптимизация весов
- Подбор параметров

#### `visual/` - Визуализация
- Dash приложения
- Интерактивные графики
- Анализ данных

## Использование

### Быстрый старт:

```bash
# 1. Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл

# 2. Запуск полного цикла
python src/main.py

# 3. Или гибкий запуск с опциями
python src/main_with_options.py --all
```

### Поэтапный запуск:

```bash
# 1. Миграции и инструменты
python src/main_with_options.py --migrations --instruments

# 2. Синхронизация данных
python src/main_with_options.py --candles

# 3. Расчет индикаторов
python src/main_with_options.py --indicators

# 4. Генерация сигналов
python src/main_with_options.py --signals

# 5. Комбинации индикаторов
python src/main_with_options.py --combinations
```

### Работа с конкретными символами:

```bash
# Обработка только BTC-USDT
python src/main_with_options.py --signals --symbol BTC-USDT

# Обработка нескольких символов
python src/main_with_options.py --signals --symbol ETH-USDT
```

## Конфигурация

### Переменные окружения:

```bash
# База данных
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_database
DB_HOST=localhost
DB_PORT=5432

# OKX API (опционально)
OKX_API_KEY=your_api_key
OKX_SECRET_KEY=your_secret_key
OKX_PASSPHRASE=your_passphrase

# Slack уведомления (опционально)
SLACK_WEBHOOK_URL=your_webhook_url
```

### Структура базы данных:

#### Основные таблицы:
- `instruments` - торговые инструменты
- `ohlcv` - данные свечей
- `indicators` - технические индикаторы
- `signals` - базовые сигналы
- `signals_detailed` - детализированные сигналы
- `combination_results` - результаты комбинаций

## Архитектура системы

### Поток данных:

```
OKX API → Candles → Indicators → Signals → Backtest → Alerts
   ↓         ↓         ↓         ↓         ↓         ↓
Database ← Database ← Database ← Database ← Database ← Slack
```

### Основные компоненты:

1. **Data Layer** - получение и хранение данных
2. **Analysis Layer** - расчет индикаторов и анализ
3. **Signal Layer** - генерация торговых сигналов
4. **Evaluation Layer** - бэктестинг и оценка
5. **Notification Layer** - уведомления и алерты
6. **Visualization Layer** - визуализация данных

## Интеграция с модулями

### Связи между компонентами:

#### Candles → Indicators:
```python
from src.candles.sync_candles import fetch_and_sync_candles
from src.indicators.calc_indicators import main as calc_indicators

# Синхронизация данных
await fetch_and_sync_candles()
# Расчет индикаторов
await calc_indicators()
```

#### Indicators → Signals:
```python
from src.signals.calculator.signal_calculator_detailed import SignalCalculatorDetailed

calculator = SignalCalculatorDetailed()
await calculator.calculate_signals_for_symbol("BTC-USDT", "1m")
```

#### Signals → Backtest:
```python
from src.backtest import SignalEvaluator

evaluator = SignalEvaluator()
results = await evaluator.evaluate_symbol("BTC-USDT")
```

#### Signals → Alerts:
```python
from src.alerts import create_slack_notifier

notifier = create_slack_notifier()
notifier.send_signal_alert(symbol, signal, score, reason)
```

## Рекомендации по использованию

### Производительность:

#### Оптимизация запросов:
- Используйте индексы в базе данных
- Группируйте операции в батчи
- Кэшируйте часто используемые данные

#### Управление ресурсами:
- Ограничивайте количество одновременных запросов
- Используйте асинхронные операции
- Мониторьте использование памяти

### Надежность:

#### Обработка ошибок:
- Всегда обрабатывайте исключения
- Используйте retry механизмы
- Логируйте все ошибки

#### Резервное копирование:
- Регулярно делайте бэкапы базы данных
- Сохраняйте конфигурационные файлы
- Документируйте изменения

### Масштабирование:

#### Горизонтальное масштабирование:
- Разделите нагрузку между несколькими инстансами
- Используйте очереди для обработки задач
- Настройте балансировку нагрузки

#### Вертикальное масштабирование:
- Увеличьте ресурсы сервера
- Оптимизируйте запросы к базе данных
- Используйте более мощное оборудование

## Примеры использования

### Создание пользовательского скрипта:

```python
import asyncio
from src.database import get_async_session
from src.signals.calculator.signal_calculator_detailed import SignalCalculatorDetailed

async def custom_signal_analysis():
    calculator = SignalCalculatorDetailed()

    # Анализ конкретного символа
    symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT"]

    for symbol in symbols:
        signals_count = await calculator.calculate_signals_for_symbol(
            symbol, "1m", recalculate=True
        )
        print(f"{symbol}: {signals_count} сигналов")

if __name__ == "__main__":
    asyncio.run(custom_signal_analysis())
```

### Мониторинг системы:

```python
import asyncio
from src.database import get_async_session
from sqlalchemy import text

async def system_status():
    async for session in get_async_session():
        # Проверяем количество записей
        tables = ['instruments', 'ohlcv', 'indicators', 'signals']

        for table in tables:
            query = text(f"SELECT COUNT(*) FROM {table}")
            result = await session.execute(query)
            count = result.scalar()
            print(f"{table}: {count} записей")
        break

asyncio.run(system_status())
```

### Интеграция с внешними системами:

```python
from src.alerts import create_slack_notifier
from src.backtest import SignalEvaluator

async def external_integration():
    # Оценка производительности
    evaluator = SignalEvaluator()
    results = await evaluator.evaluate_all_symbols(days_back=7)

    # Отправка уведомлений
    notifier = create_slack_notifier()
    if notifier and results:
        notifier.send_performance_alert(results[0])

asyncio.run(external_integration())
```

## Устранение неполадок

### Частые проблемы:

#### Ошибки подключения к базе данных:
```bash
# Проверьте переменные окружения
echo $POSTGRES_USER
echo $POSTGRES_PASSWORD
echo $POSTGRES_DB

# Проверьте доступность базы
psql -h localhost -U your_user -d your_database
```

#### Ошибки API OKX:
```python
# Проверьте лимиты
from src.limiter import AsyncLimiter
limiter = AsyncLimiter(90, 1)  # 90 запросов в секунду
```

#### Проблемы с памятью:
```python
# Используйте генераторы для больших данных
async def process_large_dataset():
    async for session in get_async_session():
        # Обрабатывайте данные порциями
        batch_size = 1000
        # ...
```

## Разработка

### Добавление новых компонентов:

1. Создайте модуль в соответствующей директории
2. Добавьте импорты в `__init__.py`
3. Обновите документацию
4. Добавьте тесты

### Структура нового модуля:

```
new_module/
├── __init__.py
├── main.py
├── utils.py
├── tests/
└── README.md
```

### Стиль кода:

- Используйте type hints
- Документируйте функции
- Следуйте PEP 8
- Добавляйте логирование
