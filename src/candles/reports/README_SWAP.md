# Swap Candles Module

Модуль для синхронизации swap OHLCV данных с биржи OKX. Обеспечивает загрузку исторических и текущих данных по всем swap инструментам с дополнительными данными: funding rate, open interest, long/short ratios.

## 🎯 Назначение

Этот модуль расширяет возможности базового модуля `candles` для работы со swap инструментами:

- **Расширенные данные** - funding rate, open interest, long/short ratios
- **Специализированная таблица** - `swap_ohlcv_p` с партиционированием
- **Оптимизированная производительность** - параллельная загрузка с rate limiting
- **CLI интерфейс** - удобное управление через командную строку
- **Мониторинг и аналитика** - детальная статистика и экспорт данных

## 📁 Структура модуля

```
src/candles/
├── sync_candles.py          # Базовый модуль для обычных свечей
├── sync_swap_candles.py     # Новый модуль для swap свечей
├── swap_cli.py              # CLI для управления swap данными
├── README.md                # Документация базового модуля
└── README_SWAP.md           # Эта документация
```

## 🚀 Быстрый старт

### 1. Создание таблицы swap OHLCV

```bash
# Запуск миграции для создания таблицы
python src/main_v2.py --migrations
```

### 2. Синхронизация всех swap свечей

```bash
# Синхронизация всех swap инструментов
python src/candles/swap_cli.py sync

# Синхронизация конкретных символов
python src/candles/swap_cli.py sync --symbols BTC-USDT-SWAP ETH-USDT-SWAP

# Синхронизация с конкретными таймфреймами
python src/candles/swap_cli.py sync --timeframes 1H 4H 1D
```

### 3. Проверка статуса

```bash
# Общий статус swap данных
python src/candles/swap_cli.py status

# Детальная информация по символу
python src/candles/swap_cli.py details BTC-USDT-SWAP
```

## 📊 Структура данных

### Таблица `swap_ohlcv_p`

```sql
CREATE TABLE swap_ohlcv_p (
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,
    open DECIMAL(20,8) NOT NULL,
    high DECIMAL(20,8) NOT NULL,
    low DECIMAL(20,8) NOT NULL,
    close DECIMAL(20,8) NOT NULL,
    volume DECIMAL(30,8) NOT NULL,
    vol_ccy DECIMAL(30,8),           -- Объем в базовой валюте
    vol_usd DECIMAL(30,8),           -- Объем в USD
    funding_rate DECIMAL(10,8),      -- Ставка финансирования
    open_interest DECIMAL(30,8),     -- Открытый интерес
    long_short_ratio DECIMAL(10,4),  -- Соотношение лонг/шорт
    long_account_ratio DECIMAL(10,4), -- Доля лонг аккаунтов
    short_account_ratio DECIMAL(10,4), -- Доля шорт аккаунтов
    top_long_short_ratio DECIMAL(10,4), -- Топ соотношение лонг/шорт
    top_long_account_ratio DECIMAL(10,4), -- Топ доля лонг аккаунтов
    top_short_account_ratio DECIMAL(10,4), -- Топ доля шорт аккаунтов
    fetched_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY RANGE (timestamp);
```

### Поддерживаемые таймфреймы

```python
SWAP_BARS = [
    "1m", "3m", "5m", "15m", "30m",  # Минуты
    "1H", "2H", "4H", "6H", "12H",   # Часы
    "1D", "1W", "1M"                 # Дни, недели, месяцы
]
```

## 🔧 CLI команды

### Синхронизация

```bash
# Синхронизация всех swap инструментов
python src/candles/swap_cli.py sync

# Синхронизация конкретных символов
python src/candles/swap_cli.py sync --symbols BTC-USDT-SWAP ETH-USDT-SWAP

# Синхронизация с конфигурацией
python src/candles/swap_cli.py sync --config config.json

# Синхронизация с ограниченными таймфреймами
python src/candles/swap_cli.py sync --timeframes 1H 4H 1D
```

### Мониторинг

```bash
# Общий статус
python src/candles/swap_cli.py status

# Детальная информация по символу
python src/candles/swap_cli.py details BTC-USDT-SWAP
```

### Управление данными

```bash
# Очистка старых данных (старше 30 дней)
python src/candles/swap_cli.py cleanup

# Очистка данных старше N дней
python src/candles/swap_cli.py cleanup --days 60

# Экспорт данных символа
python src/candles/swap_cli.py export BTC-USDT-SWAP output.json

# Экспорт с конкретными таймфреймами
python src/candles/swap_cli.py export BTC-USDT-SWAP output.json --timeframes 1H 4H
```

## 📈 Программное использование

### Базовое использование

```python
import asyncio
from src.candles.sync_swap_candles import sync_swap_candles

async def main():
    # Синхронизация всех swap инструментов
    stats = await sync_swap_candles()
    print(f"Синхронизировано {stats['total_candles_synced']} свечей")

# Запуск
asyncio.run(main())
```

### Синхронизация конкретных символов

```python
async def sync_specific():
    symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    timeframes = ["1H", "4H", "1D"]

    stats = await sync_swap_candles(
        symbols=symbols,
        timeframes=timeframes
    )

    print(f"Результаты: {stats}")

asyncio.run(sync_specific())
```

### Кастомная конфигурация

```python
config = {
    "max_requests_per_second": 15,  # Более консервативный лимит
    "batch_size": 500,              # Больше свечей за запрос
    "max_concurrent_symbols": 3,    # Меньше параллельных запросов
    "max_retries": 5,
    "retry_delay": 2.0
}

stats = await sync_swap_candles(config=config)
```

## 🔍 Анализ данных

### SQL запросы для анализа

```sql
-- Статистика по символам
SELECT
    symbol,
    COUNT(*) as total_records,
    AVG(volume) as avg_volume,
    AVG(funding_rate) as avg_funding_rate,
    MAX(fetched_at) as last_update
FROM swap_ohlcv_p
GROUP BY symbol
ORDER BY total_records DESC;

-- Анализ funding rate
SELECT
    symbol,
    timeframe,
    AVG(funding_rate) as avg_funding_rate,
    STDDEV(funding_rate) as funding_rate_volatility,
    MIN(funding_rate) as min_funding_rate,
    MAX(funding_rate) as max_funding_rate
FROM swap_ohlcv_p
WHERE funding_rate IS NOT NULL
GROUP BY symbol, timeframe
ORDER BY avg_funding_rate DESC;

-- Анализ open interest
SELECT
    symbol,
    timeframe,
    AVG(open_interest) as avg_open_interest,
    MAX(open_interest) as max_open_interest,
    MIN(open_interest) as min_open_interest
FROM swap_ohlcv_p
WHERE open_interest IS NOT NULL
GROUP BY symbol, timeframe
ORDER BY avg_open_interest DESC;

-- Анализ long/short ratios
SELECT
    symbol,
    timeframe,
    AVG(long_short_ratio) as avg_long_short_ratio,
    AVG(long_account_ratio) as avg_long_account_ratio,
    AVG(short_account_ratio) as avg_short_account_ratio
FROM swap_ohlcv_p
WHERE long_short_ratio IS NOT NULL
GROUP BY symbol, timeframe
ORDER BY avg_long_short_ratio DESC;
```

### Представление для мониторинга

```sql
-- Использование встроенного представления
SELECT * FROM swap_ohlcv_monitoring
WHERE symbol = 'BTC-USDT-SWAP';
```

## ⚙️ Конфигурация

### Параметры по умолчанию

```python
DEFAULT_CONFIG = {
    "max_requests_per_second": 20,  # Rate limiting
    "batch_size": 300,              # Свечей за запрос
    "max_retries": 3,               # Количество повторов
    "retry_delay": 1.0,             # Задержка между повторами
    "max_concurrent_symbols": 5,    # Параллельные запросы
}
```

### Файл конфигурации

```json
{
    "max_requests_per_second": 15,
    "batch_size": 500,
    "max_retries": 5,
    "retry_delay": 2.0,
    "max_concurrent_symbols": 3
}
```

## 📊 Метрики и мониторинг

### Статистика синхронизации

```python
{
    "total_symbols": 150,
    "total_candles_synced": 1250000,
    "total_symbols_processed": 150,
    "errors_count": 2,
    "duration_seconds": 1800.5,
    "symbols_per_second": 0.083,
    "candles_per_second": 694.4,
    "results_by_symbol": {
        "BTC-USDT-SWAP": {"1H": 5000, "4H": 1200, "1D": 300},
        "ETH-USDT-SWAP": {"1H": 4800, "4H": 1150, "1D": 290}
    }
}
```

### Мониторинг производительности

```bash
# Проверка размера таблицы
SELECT
    pg_size_pretty(pg_total_relation_size('swap_ohlcv_p')) as table_size;

# Статистика по партициям
SELECT
    schemaname, tablename, partitionname,
    pg_size_pretty(pg_total_relation_size(tablename)) as size
FROM pg_partitions
WHERE tablename LIKE 'swap_ohlcv_p_%'
ORDER BY tablename;
```

## 🚨 Обработка ошибок

### Типичные ошибки и решения

1. **Rate limit exceeded**
   ```bash
   # Уменьшить количество запросов в секунду
   python src/candles/swap_cli.py sync --config slow_config.json
   ```

2. **Неподдерживаемый таймфрейм**
   ```bash
   # Проверить доступные таймфреймы
   python src/candles/swap_cli.py details BTC-USDT-SWAP
   ```

3. **Недостаточно места**
   ```bash
   # Очистить старые данные
   python src/candles/swap_cli.py cleanup --days 7
   ```

## 🔗 Интеграция с другими модулями

### Market Meta

```python
from src.market_meta import get_instrument_info

# Получение метаданных swap инструмента
info = get_instrument_info("BTC-USDT-SWAP")
print(f"Размер тика: {info['tick_size']['step']}")
print(f"Размер лота: {info['lot_size']['step']}")
```

### Мониторинг

```python
from src.db.monitoring_cli import collect_metrics

# Сбор метрик после синхронизации
await collect_metrics()
```

## 📚 Дополнительные ресурсы

- [Основная документация candles](README.md)
- [Market Meta модуль](../market_meta/README.md)
- [CLI для мониторинга](../db/monitoring_cli.py)
- [Отчеты о миграциях](../db/reports/)

---

**🎯 Помните:** Swap инструменты имеют специфические особенности (funding rate, open interest), которые важно учитывать при анализе данных!
