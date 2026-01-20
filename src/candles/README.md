# Candles Module

Модуль для синхронизации OHLCV данных (свечей) с биржи OKX. Обеспечивает загрузку исторических и текущих данных по всем поддерживаемым торговым парам и таймфреймам.

## Обзор

Модуль `candles` предназначен для:
- Загрузки OHLCV данных с биржи OKX
- Синхронизации исторических данных по всем таймфреймам
- Обновления данных в базе данных PostgreSQL
- Управления лимитами API для предотвращения блокировок

## Структура модуля

### Основной файл (`sync_candles.py`)

#### Поддерживаемые таймфреймы:
```python
BARS = ["1m", "5m", "15m", "1H", "4H", "1Dutc", "1Wutc", "1Mutc"]
```

- **1m**: 1 минута
- **5m**: 5 минут
- **15m**: 15 минут
- **1H**: 1 час
- **4H**: 4 часа
- **1Dutc**: 1 день (UTC)
- **1Wutc**: 1 неделя (UTC)
- **1Mutc**: 1 месяц (UTC)

## Основные функции

### `sync_bar(inst, bar, client)`
Синхронизация одного таймфрейма для одного инструмента:

#### Параметры:
- `inst`: объект инструмента (Instrument)
- `bar`: таймфрейм (строка)
- `client`: клиент OKX API

#### Функциональность:
- Загружает до 300 свечей за запрос
- Использует пагинацию для получения всех исторических данных
- Обрабатывает ошибки API (неподдерживаемые таймфреймы)
- Обновляет данные в базе с конфликт-резолюцией

```python
async def sync_bar(inst, bar, client):
    """Синхронизация одного таймфрейма для одного инструмента."""
    # Логика загрузки и сохранения данных
```

### `sync_symbol(inst, client)`
Синхронизация всех таймфреймов для одного инструмента:

```python
async def sync_symbol(inst, client):
    """Синхронизация всех таймфреймов для одного инструмента."""
    await asyncio.gather(*(sync_bar(inst, bar, client) for bar in BARS))
```

### `fetch_and_sync_candles(symbol=None)`
Основная функция синхронизации свечей:

#### Параметры:
- `symbol`: конкретный символ для синхронизации (опционально)

#### Функциональность:
- Настройка лимитеров API (90 запросов в секунду)
- Загрузка списка инструментов из базы данных или файла
- Синхронизация всех инструментов с прогресс-баром
- Обработка ошибок и логирование

## Использование

### Запуск синхронизации всех инструментов:

```bash
# Синхронизация всех USDT пар
python src/candles/sync_candles.py
```

### Программное использование:

```python
import asyncio
from src.candles.sync_candles import fetch_and_sync_candles

# Синхронизация всех инструментов
async def sync_all():
    await fetch_and_sync_candles()

# Синхронизация конкретного символа
async def sync_specific():
    await fetch_and_sync_candles(symbol="BTC-USDT")

if __name__ == "__main__":
    asyncio.run(sync_all())
```

### Синхронизация конкретного символа:

```python
# Синхронизация только BTC-USDT
await fetch_and_sync_candles(symbol="BTC-USDT")
```

## Конфигурация

### Источники инструментов:

#### 1. Файл `instruments_list.json`:
```json
[
    "BTC-USDT",
    "ETH-USDT",
    "ADA-USDT"
]
```

#### 2. База данных:
- Автоматический выбор всех SPOT инструментов с USDT
- Сортировка по символу

### Лимиты API:
- **Публичный лимитер**: 90 запросов в секунду
- **Инструментальный лимитер**: индивидуальный для каждого символа
- **Размер пакета**: 300 свечей за запрос

## Структура данных

### OHLCV запись:
```python
{
    "symbol": "BTC-USDT",
    "timeframe": "1m",
    "ts": 1640995200000,  # timestamp в миллисекундах
    "open": 50000.0,
    "high": 50100.0,
    "low": 49900.0,
    "close": 50050.0,
    "volume": 100.5,
    "volCcy": 5025025.0,  # объем в базовой валюте
    "volUsd": 5025025.0,  # объем в USD
    "fetched_at": datetime.utcnow()
}
```

### Конфликт-резолюция:
```python
stmt = (
    pg_insert(OHLCV)
    .values(**base_data)
    .on_conflict_do_update(
        index_elements=[OHLCV.symbol, OHLCV.timeframe, OHLCV.ts],
        set_=base_data,
    )
)
```

## Обработка ошибок

### Неподдерживаемые таймфреймы:
```python
if "51000" in str(e) and "Parameter bar error" in str(e):
    logging.warning(f"{symbol}: Таймфрейм {bar} не поддерживается")
    return
```

### Ограничения API:
- Автоматическое соблюдение лимитов
- Обработка временных ошибок
- Логирование всех проблем

## Интеграция с системой

### Зависимости:
- **OKX Market API**: получение данных с биржи
- **Database**: сохранение в PostgreSQL
- **Models**: OHLCV и Instrument модели
- **Limiter**: управление лимитами API

### Связь с другими модулями:
- **indicators/**: расчет технических индикаторов на основе OHLCV
- **signals/**: генерация торговых сигналов
- **backtest/**: бэктестинг стратегий

## Рекомендации по использованию

### Производительность:
- Запускайте синхронизацию в неактивные часы
- Используйте конкретные символы для быстрой синхронизации
- Мониторьте размер базы данных

### Надежность:
- Регулярно проверяйте целостность данных
- Делайте бэкапы перед массовой синхронизацией
- Настройте мониторинг ошибок API

### Оптимизация:
- Используйте индексы в базе данных
- Настройте партиционирование для больших объемов
- Оптимизируйте размер пакетов

## Примеры использования

### Синхронизация с прогресс-отслеживанием:

```python
import asyncio
from tqdm import tqdm
from src.candles.sync_candles import fetch_and_sync_candles

async def sync_with_progress():
    print("🚀 Начинаем синхронизацию свечей...")

    try:
        await fetch_and_sync_candles()
        print("✅ Синхронизация завершена успешно!")
    except Exception as e:
        print(f"❌ Ошибка синхронизации: {e}")

if __name__ == "__main__":
    asyncio.run(sync_with_progress())
```

### Синхронизация конкретных символов:

```python
async def sync_popular_pairs():
    popular_symbols = ["BTC-USDT", "ETH-USDT", "ADA-USDT", "SOL-USDT"]

    for symbol in popular_symbols:
        print(f"📊 Синхронизация {symbol}...")
        await fetch_and_sync_candles(symbol=symbol)
        print(f"✅ {symbol} синхронизирован")

# Запуск
asyncio.run(sync_popular_pairs())
```

### Проверка данных после синхронизации:

```python
from sqlalchemy import text
from src.database import get_async_session

async def check_sync_results():
    async for session in get_async_session():
        # Проверяем количество записей
        count_query = text("SELECT COUNT(*) FROM ohlcv")
        result = await session.execute(count_query)
        total_records = result.scalar()

        # Проверяем последние записи
        latest_query = text("""
            SELECT symbol, timeframe, MAX(ts) as latest_ts
            FROM ohlcv
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        """)
        result = await session.execute(latest_query)
        latest_records = result.fetchall()

        print(f"📊 Всего записей: {total_records}")
        print("🕒 Последние записи:")
        for record in latest_records[:10]:  # Показываем первые 10
            print(f"  {record.symbol} {record.timeframe}: {record.latest_ts}")
        break
```

## Мониторинг и логирование

### Логирование:
- Информационные сообщения о процессе синхронизации
- Предупреждения о неподдерживаемых таймфреймах
- Ошибки API и сети

### Метрики:
- Количество загруженных свечей
- Время выполнения синхронизации
- Статистика по символам и таймфреймам

### Алерты:
- Ошибки API лимитов
- Проблемы с подключением к базе данных
- Неожиданные форматы данных
