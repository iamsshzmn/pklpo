# Infrastructure Layer

## 🔧 Обзор

Infrastructure Layer обеспечивает работу с внешними системами и данными. Этот слой изолирует внешние зависимости и предоставляет стабильные интерфейсы для работы с базой данных и реестрами.

## 📁 Структура

```
infrastructure/
├── database.py              # Работа с базой данных
├── db_operations.py         # Вспомогательные операции (чтение/служебные)
├── insert_indicators.py     # Запись индикаторов (UPSERT + sanitize)
├── upsert_builder.py        # Построение UPSERT, очистка значений
├── indicator_registry.py    # Реестр индикаторов (фасад)
└── README.md                # Эта документация
```

## 🗄️ Компоненты

### `database.py`

Модуль для работы с базой данных, включая извлечение OHLCV данных и сохранение индикаторов.

#### Основные функции:

```python
from src.features.infrastructure.database import (
    fetch_ohlcv_df,
    insert_indicators,
    fetch_latest_ts,
    get_symbol_timeframes_to_update
)

# Извлечение OHLCV данных
df = await fetch_ohlcv_df(session, symbol, timeframe, since_ts=None, limit=200)

# Сохранение индикаторов
await insert_indicators(session, features_df, symbol, timeframe)

# Получение последнего timestamp
latest_ts = await fetch_latest_ts(session, symbol, timeframe)

# Получение пар для обновления
pairs = await get_symbol_timeframes_to_update(session)
```

#### Функции:

##### `fetch_ohlcv_df(session, symbol, timeframe, since_ts=None, limit=200)`
Извлекает OHLCV данные из базы данных.

**Параметры:**
- `session`: SQLAlchemy сессия
- `symbol`: Символ (например, "BTC-USDT-SWAP")
- `timeframe`: Таймфрейм (например, "1D")
- `since_ts`: Timestamp для фильтрации (в миллисекундах)
- `limit`: Максимальное количество записей

**Возвращает:**
- `pd.DataFrame` с колонками: ts, open, high, low, close, volume

**Особенности:**
- Автоматически пытается читать из таблицы 'ohlcv'
- При отсутствии данных переключается на 'swap_ohlcv_p'
- Конвертирует timestamp в секунды
- Добавляет метаданные (symbol, timeframe)

##### `insert_indicators(session, ind_df, symbol, timeframe)`
Сохраняет рассчитанные индикаторы в базу данных.

**Параметры:**
- `session`: SQLAlchemy сессия
- `ind_df`: DataFrame с индикаторами
- `symbol`: Символ
- `timeframe`: Таймфрейм

**Возвращает:**
- `int`: Количество вставленных строк

**Особенности:**
- Использует UPSERT для обновления существующих записей
- Исключает OHLCV колонки из сохранения
- Конвертирует timestamp в миллисекунды
- Обрабатывает NaN значения

### Политика управления схемой
Схема БД управляется миграциями (Alembic). Динамическое создание/изменение колонок в рантайме отключено.
В продакшн‑пути записи используется только фильтрация колонок к текущей схеме и UPSERT‑вставка.
`ensure_columns_exist` остается для совместимости и служебных задач (например, офлайн‑миграций), но не вызывается при обычной записи фичей.

##### `fetch_latest_ts(session, symbol, timeframe)`
Получает последний timestamp из таблицы indicators.

**Параметры:**
- `session`: SQLAlchemy сессия
- `symbol`: Символ
- `timeframe`: Таймфрейм

**Возвращает:**
- `int | None`: Timestamp в миллисекундах или None

##### `get_symbol_timeframes_to_update(session)`
Получает пары symbol-timeframe, для которых есть новые OHLCV данные.

**Параметры:**
- `session`: SQLAlchemy сессия

**Возвращает:**
- `list[tuple[str, str]]`: Список пар (symbol, timeframe)

### `indicator_registry.py`

Фасад над legacy registry, предоставляющий стабильную точку доступа к реестру индикаторов.

#### Основные функции:

```python
from src.features.infrastructure.indicator_registry import (
    AVAILABLE_INDICATORS,
    INDICATOR_CONFIG
)

# Получение списка всех индикаторов
print(f"Доступно индикаторов: {len(AVAILABLE_INDICATORS)}")

# Получение конфигурации индикатора
rsi_config = INDICATOR_CONFIG['rsi_14']
print(f"RSI конфигурация: {rsi_config}")
```

#### Экспортируемые объекты:
- `AVAILABLE_INDICATORS`: Список всех доступных индикаторов
- `INDICATOR_CONFIG`: Словарь конфигураций индикаторов

## 🎯 Принципы

### 1. Изоляция внешних зависимостей
- Инкапсулирует работу с БД
- Абстрагирует детали реализации
- Легко заменяется на моки в тестах

### 2. Стабильные интерфейсы
- Консистентные API
- Обратная совместимость
- Предсказуемое поведение

### 3. Обработка ошибок
- Graceful degradation
- Логирование ошибок
- Retry механизмы
 - Санитизация значений перед UPSERT: `NaN/±inf → NULL`

## 🔄 Взаимодействие с другими слоями

### С Domain Layer:
```python
# Domain не зависит от Infrastructure напрямую
# Использует абстракции через Core API
```

### С Application Layer:
```python
# Application использует Infrastructure
from src.features.infrastructure.database import fetch_ohlcv_df, insert_indicators

# В application/batch_processor.py
df = await fetch_ohlcv_df(session, symbol, timeframe)
await insert_indicators(session, features_df, symbol, timeframe)
```

### С Core API:
```python
# Core API может использовать Infrastructure
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

# В core.py
available_indicators = set(AVAILABLE_INDICATORS)
```

## 📝 Примеры использования

### Работа с базой данных:

```python
import asyncio
from src.database import get_async_session
from src.features.infrastructure.database import (
    fetch_ohlcv_df,
    insert_indicators,
    fetch_latest_ts
)

async def process_symbol(symbol: str, timeframe: str):
    async for session in get_async_session():
        # Получить последний timestamp
        latest_ts = await fetch_latest_ts(session, symbol, timeframe)

        # Получить новые данные
        df = await fetch_ohlcv_df(
            session,
            symbol,
            timeframe,
            since_ts=latest_ts,
            limit=200
        )

        if df is not None and len(df) > 0:
            # Рассчитать индикаторы (через Core API)
            from src.features.core import compute_features
            features = compute_features(df, specs=["rsi_14", "atr_14"])

            # Сохранить в БД
            await insert_indicators(session, features, symbol, timeframe)
            print(f"Обработано {len(features)} строк для {symbol} {timeframe}")

        break

# Запуск
asyncio.run(process_symbol("BTC-USDT-SWAP", "1D"))
```

### Работа с реестром:

```python
from src.features.infrastructure.indicator_registry import (
    AVAILABLE_INDICATORS,
    INDICATOR_CONFIG
)

# Получение информации об индикаторах
def get_indicator_info(indicator_name: str):
    if indicator_name not in INDICATOR_CONFIG:
        return None

    config = INDICATOR_CONFIG[indicator_name]
    return {
        'name': indicator_name,
        'description': config.get('description', ''),
        'parameters': {k: v for k, v in config.items()
                      if k not in ['description', 'requires']},
        'requires': config.get('requires', [])
    }

# Пример использования
rsi_info = get_indicator_info('rsi_14')
print(f"RSI Info: {rsi_info}")

# Фильтрация индикаторов по типу
ma_indicators = [ind for ind in AVAILABLE_INDICATORS
                if ind.startswith(('sma_', 'ema_', 'wma_', 'hma_'))]
print(f"Moving Averages: {ma_indicators}")
```

### Batch обработка:

```python
from src.features.infrastructure.database import get_symbol_timeframes_to_update

async def process_all_pairs():
    async for session in get_async_session():
        # Получить все пары для обновления
        pairs = await get_symbol_timeframes_to_update(session)

        print(f"Найдено {len(pairs)} пар для обновления")

        for symbol, timeframe in pairs:
            try:
                await process_symbol(symbol, timeframe)
            except Exception as e:
                print(f"Ошибка обработки {symbol} {timeframe}: {e}")

        break

# Запуск batch обработки
asyncio.run(process_all_pairs())
```

## 🧪 Тестирование

### Unit тесты с моками:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.features.infrastructure.database import fetch_ohlcv_df, insert_indicators

@pytest.mark.asyncio
async def test_fetch_ohlcv_df():
    # Создание мока сессии
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        MagicMock(ts=1640995200000, open=100.0, high=102.0, low=99.0, close=101.0, volume=1000)
    ]
    mock_session.execute.return_value = mock_result

    # Тест
    df = await fetch_ohlcv_df(mock_session, "BTC-USDT-SWAP", "1D")

    assert df is not None
    assert len(df) == 1
    assert 'ts' in df.columns
    assert df['ts'].iloc[0] == 1640995200  # Конвертировано в секунды

@pytest.mark.asyncio
async def test_insert_indicators():
    # Создание мока сессии
    mock_session = AsyncMock()

    # Подготовка данных
    import pandas as pd
    df = pd.DataFrame({
        'ts': [1640995200],
        'rsi_14': [50.0],
        'atr_14': [1.5]
    })

    # Тест
    result = await insert_indicators(mock_session, df, "BTC-USDT-SWAP", "1D")

    assert result == 1
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()
```

### Интеграционные тесты:

```python
import pytest
from src.database import get_async_session
from src.features.infrastructure.database import fetch_ohlcv_df, insert_indicators

@pytest.mark.asyncio
async def test_database_integration():
    async for session in get_async_session():
        # Тест извлечения данных
        df = await fetch_ohlcv_df(session, "BTC-USDT-SWAP", "1D", limit=10)

        if df is not None and len(df) > 0:
            # Тест сохранения
            test_df = df.head(1).copy()
            test_df['test_indicator'] = 42.0

            result = await insert_indicators(session, test_df, "BTC-USDT-SWAP", "1D")
            assert result == 1

        break
```

## 🔧 Расширение

### Добавление нового источника данных:

```python
# infrastructure/data_sources.py
class DataSource:
    async def fetch_data(self, symbol: str, timeframe: str, **kwargs):
        raise NotImplementedError

class DatabaseDataSource(DataSource):
    def __init__(self, session):
        self.session = session

    async def fetch_data(self, symbol: str, timeframe: str, **kwargs):
        return await fetch_ohlcv_df(self.session, symbol, timeframe, **kwargs)

class APIDataSource(DataSource):
    def __init__(self, api_client):
        self.api_client = api_client

    async def fetch_data(self, symbol: str, timeframe: str, **kwargs):
        # Реализация получения данных через API
        pass
```

### Добавление кэширования:

```python
# infrastructure/cache.py
import asyncio
from typing import Dict, Any

class Cache:
    def __init__(self, ttl: int = 300):
        self.cache: Dict[str, Any] = {}
        self.ttl = ttl

    async def get(self, key: str):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None

    async def set(self, key: str, value: Any):
        self.cache[key] = (value, time.time())

# Использование в database.py
cache = Cache(ttl=300)

async def fetch_ohlcv_df_cached(session, symbol, timeframe, **kwargs):
    cache_key = f"{symbol}_{timeframe}_{kwargs.get('since_ts', 'all')}"

    cached_data = await cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    data = await fetch_ohlcv_df(session, symbol, timeframe, **kwargs)
    if data is not None:
        await cache.set(cache_key, data)

    return data
```

## 📚 Дополнительные ресурсы

- [ARCHITECTURE.md](../reports/ARCHITECTURE.md) - Общая архитектура
- [README.md](../README.md) - Общая документация
- [Domain Layer](../domain/README.md) - Доменный слой

---

**Infrastructure Layer обеспечивает надежную работу с внешними системами и стабильные интерфейсы для доступа к данным.**
