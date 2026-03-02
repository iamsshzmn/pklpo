# Утилиты для улучшения архитектуры

Этот модуль содержит утилиты для исправления критических проблем архитектуры проекта.

## 📁 Структура модуля

```
src/utils/
├── __init__.py
├── README.md
├── session_utils.py      # Управление async сессиями БД
├── safe_logging.py       # Безопасное логирование
├── retry.py             # Retry логика
├── validators.py        # Валидация входных данных
├── graceful_shutdown.py # Graceful shutdown
├── health_checks.py     # Health checks
├── query_optimizer.py   # Query optimization and performance analysis
└── batch_processor.py   # Батчевая обработка данных
```

## 🔧 Использование утилит

### 1. Session Utils (`session_utils.py`)

**Проблема:** Неправильное использование async session с `async for` и `break`

**Решение:** Контекстный менеджер для правильной работы с сессиями

```python
from src.utils.session_utils import get_db_session

# Правильное использование
async def check_data():
    async with get_db_session() as session:
        result = await session.execute(query)
        await session.commit()  # Автоматический commit

# С retry логикой
from src.utils.session_utils import DatabaseManager

db_manager = DatabaseManager(max_retries=3)
result = await db_manager.execute_with_retry(my_function, arg1, arg2)
```

### 2. Safe Logging (`safe_logging.py`)

**Проблема:** Чувствительная информация попадает в логи

**Решение:** Фильтр для автоматического скрытия чувствительных данных

```python
from src.utils.safe_logging import setup_safe_logging

# Настройка безопасного логирования
logger = setup_safe_logging(
    level="INFO",
    log_file="app.log"
)

# Автоматически скрывает пароли, API ключи и т.д.
logger.info("Connecting with password=secret123")  # В логе: "Connecting with password=***HIDDEN***"
```

### 3. Retry Logic (`retry.py`)

**Проблема:** Отсутствие retry логики для API и БД операций

**Решение:** Экспоненциальная задержка с jitter

```python
from src.utils.retry import retry_async

@retry_async(max_attempts=3, base_delay=1.0)
async def api_call():
    # Функция с автоматическими повторами при ошибках
    pass

# Или для синхронных функций
from src.utils.retry import retry_sync

@retry_sync(max_attempts=3)
def sync_function():
    pass
```

### 4. Validators (`validators.py`)

**Проблема:** Отсутствие валидации входных данных

**Решение:** Комплексная валидация с Pydantic моделями

```python
from src.utils.validators import SymbolValidator, TimeframeValidator, DataValidator

# Валидация символа
if SymbolValidator.validate_symbol("BTC-USDT"):
    print("Valid symbol")

# Валидация таймфрейма
if TimeframeValidator.validate_timeframe("1H"):
    print("Valid timeframe")

# Валидация OHLCV данных
try:
    validated_data = DataValidator.validate_ohlcv_data(data)
except ValidationError as e:
    print(f"Validation error: {e.message}")

# Использование Pydantic моделей
from src.utils.validators import OHLCVModel

ohlcv = OHLCVModel(**data)  # Автоматическая валидация
```

### 5. Batch Processor (`batch_processor.py`)

**Проблема:** Неэффективная обработка больших данных (по одному элементу)

**Решение:** Батчевая обработка для улучшения производительности

```python
from src.utils.batch_processor import create_batch_processor, create_db_batch_processor

# Общая батчевая обработка
processor = create_batch_processor(batch_size=100, max_workers=4)

async def process_items(items):
    return await processor.process_batches(
        items=items,
        processor_func=my_processing_function,
        save_func=my_save_function,
        progress_callback=lambda current, total: print(f"Progress: {current}/{total}")
    )

# Специализированная обработка БД
db_processor = create_db_batch_processor(batch_size=100)

async def insert_data(session, data):
    return await db_processor.batch_insert(
        session=session,
        model_class=MyModel,
        items=data
    )
```

### 6. Graceful Shutdown (`graceful_shutdown.py`)

**Проблема:** Отсутствие graceful shutdown

**Решение:** Обработка сигналов и корректное завершение

```python
from src.utils.graceful_shutdown import run_with_shutdown, add_shutdown_handler

# Добавление обработчиков shutdown
@add_shutdown_handler
async def cleanup_database():
    # Очистка ресурсов БД
    pass

# Запуск с поддержкой graceful shutdown
async def main():
    # Основная логика приложения
    pass

if __name__ == "__main__":
    asyncio.run(run_with_shutdown(main))
```

### 7. Health Checks (`health_checks.py`)

**Проблема:** Отсутствие health checks

**Решение:** Комплексные проверки состояния системы

```python
from src.utils.health_checks import run_health_checks, print_health_report

# Запуск всех проверок
health_status = await run_health_checks()

# Вывод отчета
await print_health_report()

# Добавление кастомной проверки
from src.utils.health_checks import health_checker

async def custom_check():
    # Ваша проверка
    return HealthCheckResult("Custom", True, "OK")

health_checker.add_check("Custom Check", custom_check)
```

## 🚀 Миграция существующего кода

### Шаг 1: Замена async session

**Было:**
```python
async for session in get_async_session():
    try:
        result = await session.execute(query)
        # ...
    finally:
        break
```

**Стало:**
```python
from src.utils.session_utils import get_db_session

async with get_db_session() as session:
    result = await session.execute(query)
    # Автоматический commit и close
```

### Шаг 2: Добавление валидации

**Было:**
```python
def process_data(symbol, timeframe, data):
    # Без валидации
    pass
```

**Стало:**
```python
from src.utils.validators import SymbolValidator, TimeframeValidator

def process_data(symbol, timeframe, data):
    if not SymbolValidator.validate_symbol(symbol):
        raise ValueError(f"Invalid symbol: {symbol}")

    if not TimeframeValidator.validate_timeframe(timeframe):
        raise ValueError(f"Invalid timeframe: {timeframe}")

    # Обработка данных
```

### Шаг 3: Добавление retry логики

**Было:**
```python
async def api_call():
    response = await client.request()
    return response
```

**Стало:**
```python
from src.utils.retry import retry_async

@retry_async(max_attempts=3, base_delay=1.0)
async def api_call():
    response = await client.request()
    return response
```

## 📊 Мониторинг и метрики

### Логирование операций

```python
from src.utils.safe_logging import log_database_operation, log_api_request

# Логирование операций БД
log_database_operation("SELECT", "indicators", symbol="BTC-USDT")

# Логирование API запросов
log_api_request("GET", "/api/instruments", status_code=200)
```

### Health Checks

```python
# Запуск health checks перед операциями
health_status = await run_health_checks()
if not health_status["overall_status"]:
    logger.error("System is unhealthy, aborting operation")
    return
```

## 🔒 Безопасность

### Безопасное логирование

- Автоматическое скрытие паролей, API ключей, токенов
- Фильтрация чувствительных данных в аргументах
- Безопасная обработка словарей и списков

### Валидация данных

- Проверка формата символов (BTC-USDT)
- Валидация таймфреймов
- Проверка логики OHLCV данных
- Валидация временных меток

## 🧪 Тестирование

### Unit тесты для валидаторов

```python
def test_symbol_validator():
    assert SymbolValidator.validate_symbol("BTC-USDT") == True
    assert SymbolValidator.validate_symbol("invalid") == False
    assert SymbolValidator.validate_symbol("") == False
```

### Интеграционные тесты

```python
async def test_database_session():
    async with get_db_session() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
```

## 📈 Производительность

### Connection Pooling

- Настроен пул соединений в `database.py`
- Автоматическое переиспользование соединений
- Ограничение максимального количества соединений

### Batch Processing

```python
# Обработка данных батчами
async def process_batch(data_batch):
    async with get_db_session() as session:
        for item in data_batch:
            # Обработка элемента
            pass
        await session.commit()
```

### Query Optimization

```python
from src.utils.query_optimizer import create_query_optimizer

# Анализ производительности запросов
optimizer = create_query_optimizer(session)
plan = await optimizer.analyze_query_plan(
    "SELECT * FROM indicators WHERE symbol = :symbol",
    {"symbol": "BTC-USDT"}
)

# Бенчмарк запросов
benchmark = await optimizer.benchmark_query(
    "SELECT * FROM indicators WHERE symbol = :symbol",
    {"symbol": "BTC-USDT"}
)

# Предложение индексов
suggestions = await optimizer.suggest_indexes("indicators")
```

### Query Caching

```python
from src.utils.query_optimizer import create_query_cache

# Кэширование результатов запросов
cache = create_query_cache(ttl_seconds=300)
cache.set("symbols", ["BTC-USDT", "ETH-USDT"])
cached_data = cache.get("symbols")
```

### Async Pandas Processing

```python
from src.utils.async_pandas import (
    create_dataframe_async,
    calculate_indicators_async,
    sort_values_async,
    calc_rsi_async,
    calc_macd_async
)

# Асинхронное создание DataFrame
data = [{"ts": 1000, "close": 100.0}, {"ts": 2000, "close": 101.0}]
df = await create_dataframe_async(data)

# Асинхронный расчет индикаторов
indicator_funcs = {
    'rsi': lambda df: calc_rsi_sync(df),
    'sma': lambda df: df['close'].rolling(20).mean()
}
result_df = await calculate_indicators_async(df, indicator_funcs)

# Асинхронная сортировка
sorted_df = await sort_values_async(df, 'ts')

# Асинхронный расчет RSI
rsi = await calc_rsi_async(df)

# Асинхронный расчет MACD
macd_result = await calc_macd_async(df)
```

## 🔄 Graceful Shutdown

### Обработка сигналов

- SIGINT (Ctrl+C)
- SIGTERM (завершение процесса)
- Автоматическая очистка ресурсов

### Отмена задач

```python
from src.utils.graceful_shutdown import cancel_all_tasks

@add_shutdown_handler
async def cleanup():
    await cancel_all_tasks()
    # Дополнительная очистка
```

## 📝 Логирование

### Структурированное логирование

```python
import logging
from src.utils.safe_logging import setup_safe_logging

logger = setup_safe_logging(
    level="INFO",
    log_file="app.log",
    format_string="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

### Контекстное логирование

```python
logger.info("Processing symbol", extra={
    "symbol": "BTC-USDT",
    "timeframe": "1H",
    "operation": "calculate_indicators"
})
```

## 🚨 Обработка ошибок

### Специфичные исключения

```python
from src.utils.validators import ValidationError

try:
    validated_data = DataValidator.validate_ohlcv_data(data)
except ValidationError as e:
    logger.error(f"Validation failed: {e.message} in field {e.field}")
    # Обработка ошибки валидации
```

### Retry с экспоненциальной задержкой

```python
@retry_async(max_attempts=3, base_delay=1.0, exponential_base=2.0)
async def unreliable_operation():
    # Операция, которая может временно не удаться
    pass
```

## 📋 Checklist для миграции

- [ ] Заменить все `async for session in get_async_session()` на `async with get_db_session()`
- [ ] Добавить валидацию входных данных
- [ ] Обернуть API вызовы в retry декораторы
- [ ] Настроить безопасное логирование
- [ ] Добавить health checks перед критическими операциями
- [ ] Настроить graceful shutdown
- [ ] Добавить обработку специфичных исключений
- [ ] Протестировать все изменения

## 🔧 Конфигурация

### Переменные окружения

```bash
# База данных
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_database
DB_HOST=localhost
DB_PORT=5432

# Логирование
LOG_LEVEL=INFO
LOG_FILE=app.log

# Retry настройки
MAX_RETRIES=3
RETRY_BASE_DELAY=1.0
```

### Настройка connection pooling

```python
# В database.py уже настроено:
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```

## 📚 Дополнительные ресурсы

- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [Logging Best Practices](https://docs.python.org/3/howto/logging.html)
