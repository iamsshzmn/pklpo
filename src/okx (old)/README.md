# OKX API Client

Асинхронный клиент для работы с API биржи OKX с поддержкой rate limiting, управления сессиями и обработки ошибок.

## 🚀 Возможности

### ✅ **Асинхронная архитектура**
- Полностью асинхронный клиент на основе `aiohttp`
- Поддержка контекстных менеджеров (`async with`)
- Автоматическое управление сессиями

### ✅ **Rate Limiting**
- **Публичные запросы**: 90 запросов в секунду
- **Аккаунт запросы**: 450 запросов в секунду
- **Инструмент-специфичные**: 27 запросов в секунду на символ
- Автоматическое соблюдение лимитов OKX API

### ✅ **Обработка ошибок**
- Автоматическая проверка кодов ответа OKX
- Логирование ошибок с детальной информацией
- Debug режим с сохранением ответов в JSON

### ✅ **Гибкая конфигурация**
- Поддержка переменных окружения
- Настраиваемые таймауты и базовые URL
- Возможность использования внешних сессий

## Структура

```
src/okx/
├── __init__.py          # Основной пакет
├── README.md           # Документация
├── client.py           # Базовый клиент OKX
├── market.py           # Рыночные данные
└── orders.py           # Торговые операции
```

## Компоненты

### 1. Базовый клиент (`client.py`)

**`OKXClient`** - основной класс для работы с API OKX:

#### Инициализация
```python
from src.okx.client import OKXClient

# Базовое использование
client = OKXClient()

# С настройками
client = OKXClient(
    timeout=30,
    base_url="https://www.okx.com",
    session=external_session  # опционально
)
```

#### Контекстный менеджер
```python
async with OKXClient() as client:
    # Автоматическое создание/закрытие сессии
    data = await client._request("GET", "/api/v5/public/instruments")
```

#### Rate Limiting
```python
# Автоматическое соблюдение лимитов
async with client._public_limiter:  # 90 req/s
    pass

async with client._account_limiter:  # 450 req/s
    pass

async with client.get_instrument_limiter("BTC-USDT"):  # 27 req/s
    pass
```

### 2. Рыночные данные (`market.py`)

**`OKXMarket`** - класс для получения рыночных данных:

#### Получение инструментов
```python
from src.okx.market import OKXMarket

async with OKXMarket() as market:
    # Все фьючерсы
    futures = await market.get_instruments("FUTURES")

    # SPOT инструменты с USDT
    spot_usdt = await market.get_usdt_spot()

    # С дополнительными параметрами
    instruments = await market.get_instruments(
        inst_type="SPOT",
        uly="BTC-USDT"
    )
```

#### Получение свечей (OHLCV)
```python
async with OKXMarket() as market:
    # Базовый запрос
    candles = await market.get_candles(
        inst_id="BTC-USDT",
        bar="1m",
        limit=300
    )

    # С временными границами
    candles = await market.get_candles(
        inst_id="BTC-USDT",
        bar="1D",
        limit=100,
        after="1753526400000",  # timestamp в миллисекундах
        before="1753612800000"
    )
```

#### Формат данных свечей
```python
[
    {
        "ts": 1753526400000,      # timestamp в миллисекундах
        "open": "43250.1",
        "high": "43280.5",
        "low": "43200.0",
        "close": "43245.3",
        "volume": "1234.56",
        "volCcy": "53456789.12",  # объем в валюте котировки
        "volUsd": "53456789.12"   # объем в USD (если доступен)
    },
    # ...
]
```

### 3. Торговые операции (`orders.py`)

**`OKXOrders`** - класс для торговых операций:

#### Batch размещение ордеров
```python
from src.okx.orders import OKXOrders

async with OKXOrders() as orders:
    # Подготовка ордеров
    order_batch = [
        {
            "instId": "BTC-USDT",
            "tdMode": "cash",
            "side": "buy",
            "ordType": "market",
            "sz": "0.001"
        },
        {
            "instId": "ETH-USDT",
            "tdMode": "cash",
            "side": "sell",
            "ordType": "limit",
            "sz": "0.01",
            "px": "2500.0"
        }
    ]

    # Размещение batch ордеров
    result = await orders.place_orders_batch(order_batch)
```

## Конфигурация

### Переменные окружения

Создайте файл `.env` в корне проекта:

```env
# API ключи OKX (для приватных запросов)
OKX_API_KEY=your_api_key
OKX_API_SECRET=your_api_secret
OKX_API_PASSPHRASE=your_passphrase

# Базовый URL (опционально)
OKX_BASE_URL=https://www.okx.com
```

### Rate Limiting

Лимиты настраиваются при инициализации клиента:

```python
from aiolimiter import AsyncLimiter

client = OKXClient(
    public_limiter=AsyncLimiter(90, 1),      # 90 req/s
    account_limiter=AsyncLimiter(450, 1),    # 450 req/s
    instrument_limiter={
        "BTC-USDT": AsyncLimiter(27, 1)      # 27 req/s на символ
    }
)
```

## Использование

### Базовый пример

```python
import asyncio
from src.okx.market import OKXMarket

async def main():
    async with OKXMarket() as market:
        # Получаем USDT SPOT инструменты
        instruments = await market.get_usdt_spot()
        print(f"Найдено {len(instruments)} USDT инструментов")

        # Получаем свечи BTC-USDT
        candles = await market.get_candles(
            inst_id="BTC-USDT",
            bar="1m",
            limit=10
        )

        for candle in candles:
            print(f"Время: {candle['ts']}, Цена: {candle['close']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Синхронизация свечей

```python
import asyncio
from src.okx.market import OKXMarket

async def sync_candles(symbol: str, timeframe: str, limit: int = 300):
    async with OKXMarket() as market:
        candles = await market.get_candles(
            inst_id=symbol,
            bar=timeframe,
            limit=limit
        )

        # Обработка и сохранение в БД
        for candle in candles:
            # Ваша логика сохранения
            pass

        return len(candles)

# Использование
result = await sync_candles("BTC-USDT", "1m", 1000)
print(f"Синхронизировано {result} свечей")
```

### Batch торговля

```python
import asyncio
from src.okx.orders import OKXOrders

async def place_multiple_orders():
    async with OKXOrders() as orders:
        # Подготовка ордеров
        order_batch = [
            {
                "instId": "BTC-USDT",
                "tdMode": "cash",
                "side": "buy",
                "ordType": "market",
                "sz": "0.001"
            }
        ]

        # Размещение
        result = await orders.place_orders_batch(order_batch)
        return result

# Использование
result = await place_multiple_orders()
print(f"Результат размещения: {result}")
```

## Обработка ошибок

### Автоматическая обработка

```python
async with OKXMarket() as market:
    try:
        candles = await market.get_candles("INVALID-SYMBOL", "1m")
    except RuntimeError as e:
        print(f"Ошибка OKX: {e}")
        # Ошибки автоматически логируются
```

### Debug режим

Клиент автоматически сохраняет ответы в `debug_okx_response.json`:

```python
# После любого запроса создается файл debug_okx_response.json
# с полным ответом от OKX API
```

## Лимиты API

### Публичные эндпоинты
- **Rate Limit**: 90 запросов в секунду
- **Эндпоинты**: `/api/v5/public/*`, `/api/v5/market/*`

### Приватные эндпоинты
- **Rate Limit**: 450 запросов в секунду
- **Эндпоинты**: `/api/v5/trade/*`, `/api/v5/account/*`

### Инструмент-специфичные
- **Rate Limit**: 27 запросов в секунду на символ
- **Применяется**: к запросам с указанием `symbol`

## Расширение

### Добавление новых методов

```python
from src.okx.client import OKXClient

class CustomOKXClient(OKXClient):
    async def get_ticker(self, inst_id: str):
        """Получение тикера"""
        return await self._request(
            "GET",
            "/api/v5/market/ticker",
            params={"instId": inst_id},
            symbol=inst_id,
            is_public=True
        )

    async def get_orderbook(self, inst_id: str, depth: int = 20):
        """Получение стакана"""
        return await self._request(
            "GET",
            "/api/v5/market/books",
            params={"instId": inst_id, "sz": depth},
            symbol=inst_id,
            is_public=True
        )
```

### Кастомные лимитеры

```python
from aiolimiter import AsyncLimiter

# Создание кастомных лимитеров
custom_public_limiter = AsyncLimiter(50, 1)  # 50 req/s
custom_account_limiter = AsyncLimiter(200, 1)  # 200 req/s

client = OKXClient(
    public_limiter=custom_public_limiter,
    account_limiter=custom_account_limiter
)
```

## Требования

- Python 3.8+
- aiohttp
- aiolimiter
- python-dotenv

## Установка зависимостей

```bash
pip install aiohttp aiolimiter python-dotenv
```

## Логирование

Клиент использует стандартный Python logging:

```python
import logging

# Настройка уровня логирования
logging.basicConfig(level=logging.INFO)

# В логах будут отображаться:
# - Ошибки OKX API
# - Rate limiting информация
# - Debug информация (если включено)
```
