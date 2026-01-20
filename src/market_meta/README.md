# Market Meta Module

Модуль метаданных рынка, валидаторов и биржевых специфик для торговой системы PKLPO.

## 🎯 Назначение


**Биржевые метаданные + валидаторы** - без этого любая торговая логика небезопасна.

Этот модуль предоставляет:

- **Метаданные инструментов** - размер тика, лот, номинальная стоимость, комиссии, плечо
- **Валидаторы времени выполнения** - проверка корректности рыночных данных и ордеров
- **Управление лимитами риска** - валидация размера позиции и общей экспозиции
- **Поддержка режимов маржи** - различные режимы маржи и параметры
- **Обработка ставок финансирования** - расчеты ставок финансирования
- **Фильтры ликвидности** - валидация ликвидности рынка
- **Расширенные рыночные данные** - Open Interest, Funding Rates, L2 Order Book метрики (market_data_ext)
- **Нормализация к барам OHLCV** - синхронизация данных с фактическими барами
- **Агрегация данных** - агрегация 1m → {5m, 15m, 1H} с реальными интервалами OHLCV
- **Retention политика** - автоматическая очистка старых данных
- **Система метрик и мониторинга** - сбор и экспорт метрик производительности
- **CLI интерфейс** - управление модулем через командную строку (20 команд)
- **Централизованная конфигурация** - настройка через переменные окружения
- **Надежная обработка ошибок** - иерархия исключений с контекстом
- **Интеграция с базой данных** - хранение метаданных, кэша валидаций и временных рядов

## 📁 Структура модуля

Модуль построен по принципам Clean Architecture с разделением на слои:

```text
src/market_meta/
├── __init__.py              # Основной пакет и экспорты
├── README.md               # Документация
├── demo.py                 # Демонстрационный скрипт
├── logging.yaml            # Конфигурация логирования
│
├── domain/                 # Domain Layer - бизнес-логика
│   ├── __init__.py
│   ├── metadata.py         # Модели метаданных инструментов
│   ├── validators.py       # Валидаторы рыночных данных и позиций
│   ├── risk_limits.py      # Управление лимитами риска
│   ├── quality.py          # Модели качества данных (Severity, Thresholds, CheckResult)
│   └── exceptions.py       # Иерархия исключений
│
├── application/            # Application Layer - оркестрация
│   ├── __init__.py
│   ├── api.py              # Основной API (MarketMetaAPI)
│   └── quality_checks.py   # Проверки качества данных (freshness, coverage, fill-rate)
│
├── infrastructure/         # Infrastructure Layer - внешние зависимости
│   ├── __init__.py
│   ├── client.py           # Базовый клиент OKX
│   ├── market.py           # OKXMarket - рыночные данные
│   ├── okx_integration.py  # OKXMetadataLoader (с retry/backoff)
│   ├── orders.py           # Торговые операции
│   ├── database.py         # Модели БД (MarketMeta, MarketDataExt, репозитории)
│   ├── metrics.py          # Сбор и экспорт метрик
│   ├── logging_config.py   # Система логирования
│   ├── config.py           # Конфигурация
│   ├── config.yaml         # Конфигурация по умолчанию
│   │
│   ├── data_loader.py          # MarketDataLoader - загрузка расширенных данных
│   ├── ohlcv_aligner.py        # OHLCVAligner - синхронизация с барами OHLCV
│   ├── normalizer.py           # MarketDataNormalizer - нормализация к барам
│   ├── aggregator.py           # MarketDataAggregator - агрегация таймфреймов
│   ├── retention.py            # MarketDataExtRetention - retention политика
│   │
│   ├── raw_ingest.py           # RawIngestor - запись сырых данных в raw слой
│   ├── sync_state.py           # SyncStateManager - watermark для инкрементальной загрузки
│   └── quality_repository.py   # QualityMetricsRepository - хранение метрик качества
│
├── cli/                    # CLI Layer - командная строка
│   ├── __init__.py
│   └── cli.py              # CLI интерфейс (20 команд)
│
├── contracts/              # Контракты данных
│   └── market_data_ext_contract.md
│
├── migrations/             # SQL миграции
│   └── 001_create_market_meta_tables.sql
│
└── tests/                  # Тесты расположены в tests/market_meta/
```

## 🚀 Быстрый старт

### Установка

```bash
# Модуль уже включен в проект PKLPO
# Убедитесь, что установлены зависимости:
pip install -r requirements.txt
```

### Базовое использование

```python
from src.market_meta import refresh_okx_meta, validate_order

# Обновление метаданных
success = await refresh_okx_meta()
if success:
    print("✅ Метаданные обновлены")

# Валидация ордера
violations = validate_order(
    symbol="BTC-USDT-SWAP",
    price=50000.0,
    qty=0.1,
    account_balance=10000.0
)

if violations:
    print("❌ Нарушения:", violations)
else:
    print("✅ Ордер валиден")
```

## 📚 Основной API

### 1. Обновление метаданных

#### Базовое обновление

```python
from src.market_meta import refresh_okx_meta

# Обновление метаданных с OKX (с retry/backoff)
success = await refresh_okx_meta()
if success:
    print("✅ Метаданные обновлены")
else:
    print("❌ Ошибка обновления метаданных")
```

#### Принудительное обновление

```python
# Принудительное обновление, игнорируя кэш
success = await refresh_okx_meta(force=True)
```

#### Расширенное обновление

```python
from src.market_meta import MarketMetaAPI

api = MarketMetaAPI()
# Загружает дополнительные данные: funding rates, mark prices, tickers, open interest
success = await api.refresh_okx_meta_extended(force=True)
```

### 2. Валидация ордеров

#### Простая валидация

```python
from src.market_meta import validate_order

# Валидация ордера с полной проверкой
violations = validate_order(
    symbol="BTC-USDT-SWAP",
    price=50000.0,
    qty=0.1,
    account_balance=10000.0
)

if violations:
    print("❌ Нарушения:")
    for violation in violations:
        print(f"  - {violation}")
else:
    print("✅ Ордер валиден")
```

#### Расширенная валидация

```python
violations = validate_order(
    symbol="BTC-USDT-SWAP",
    price=50000.0,
    qty=0.1,
    account_balance=10000.0,
    order_type="limit",          # limit или market
    side="buy",                   # buy или sell
    leverage=5.0,                 # Плечо
    margin_mode="isolated",       # isolated или cross
    spread_bps=10.0,              # Спред в базисных пунктах
    vol_usdt=1000000.0,           # Объем за 24ч в USDT
    book_depth=50000.0            # Глубина стакана в USDT
)
```

### 3. Получение информации об инструменте

```python
from src.market_meta import get_instrument_info

# Получение полной информации
info = get_instrument_info("BTC-USDT-SWAP")
if info:
    print(f"Тип: {info['inst_type']}")
    print(f"Размер тика: {info['tick_size']['step']}")
    print(f"Размер лота: {info['lot_size']['step']}")
    print(f"Номинальная стоимость: {info['contract_val']}")
    print(f"Комиссия maker: {info['fee_maker']}")
    print(f"Комиссия taker: {info['fee_taker']}")
    print(f"Макс. плечо: {info['max_leverage']}")
    print(f"Режим маржи: {info['margin_mode']}")
    print(f"Ставка финансирования: {info.get('funding_rate')}")
```

### 4. Расчет номинальной стоимости

```python
from src.market_meta import calculate_notional_value

# Расчет номинальной стоимости позиции
notional = calculate_notional_value("BTC-USDT-SWAP", 50000.0, 0.1)
print(f"Номинальная стоимость: ${notional}")
```

### 5. Получение ставки финансирования

```python
from src.market_meta import get_funding_rate

# Получение ставки финансирования
funding_rate = get_funding_rate("BTC-USDT-SWAP")
if funding_rate:
    print(f"Ставка: {funding_rate.rate}")
    print(f"Следующее финансирование: {funding_rate.next_funding_time}")
    print(f"Годовая ставка: {funding_rate.annual_rate}")
```

### 6. Получение маржевой цены

```python
from src.market_meta import get_mark_price

# Получение маржевой цены
mark_price = get_mark_price("BTC-USDT-SWAP")
if mark_price:
    print(f"Маржевая цена: {mark_price}")
```

### 7. Получение информации о ликвидности

```python
from src.market_meta import get_liquidity_info

# Получение информации о ликвидности
liquidity = get_liquidity_info("BTC-USDT-SWAP")
if liquidity:
    print(f"Минимальный объем 24ч: {liquidity['min_volume_24h']}")
    print(f"Минимальное количество сделок: {liquidity['min_trades_24h']}")
    print(f"Порог спреда: {liquidity['spread_threshold']}")
```

### 8. Получение открытого интереса

```python
from src.market_meta import get_open_interest

# Получение открытого интереса
oi = get_open_interest("BTC-USDT-SWAP")
if oi:
    print(f"Открытый интерес: {oi}")
```

### 9. Использование API класса

```python
from src.market_meta import MarketMetaAPI

# Создание экземпляра API с авто-refresh
api = MarketMetaAPI()

# Обновление метаданных
success = await api.refresh_okx_meta()

# Валидация ордера
violations = api.validate_order("BTC-USDT-SWAP", 50000.0, 0.1)

# Получение метрик риска
metrics = api.get_risk_metrics(account_balance=10000.0)
print(f"Общая экспозиция: {metrics['total_exposure_pct']:.2%}")

# Проверка алертов
alerts = api.check_risk_alerts(account_balance=10000.0)
for alert in alerts:
    print(f"🚨 {alert}")

# Управление кэшем
cache_status = api.get_cache_status()
print(f"Кэш актуален: {cache_status['is_valid']}")
print(f"Последнее обновление: {cache_status['last_refresh']}")

# Установка TTL кэша
api.set_cache_ttl(hours=2)

# Запуск авто-refresh
api.start_auto_refresh()

# Остановка авто-refresh
api.stop_auto_refresh()
```

### 10. Работа с расширенными рыночными данными (market_data_ext)

```python
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from src.market_meta.infrastructure.data_loader import MarketDataLoader
from src.market_meta.infrastructure.normalizer import MarketDataNormalizer
from src.market_meta.infrastructure.aggregator import MarketDataAggregator
from src.market_meta.infrastructure.database import MarketDataExtRepository
from src.market_meta.infrastructure.ohlcv_aligner import OHLCVAligner

# Инициализация компонентов
engine = create_engine("postgresql://...")
aligner = OHLCVAligner(engine)
loader = MarketDataLoader()
normalizer = MarketDataNormalizer(aligner)
aggregator = MarketDataAggregator(aligner)
repo = MarketDataExtRepository(engine)

# Загрузка данных
symbols = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
start_time = datetime.now() - timedelta(days=1)
end_time = datetime.now()

# Загрузка всех типов данных
data = await loader.load_all(symbols, start_time, end_time)

# Нормализация к 1m барам
normalized_funding = normalizer.normalize_to_1m_bars(
    data["funding"], symbol="BTC-USDT-SWAP"
)
normalized_oi = normalizer.normalize_to_1m_bars(
    data["oi"], symbol="BTC-USDT-SWAP"
)
normalized_l2 = normalizer.normalize_to_1m_bars(
    data["l2"], symbol="BTC-USDT-SWAP"
)

# Агрегация к 5m
import pandas as pd
df_1m = pd.DataFrame(normalized_oi)
df_5m = aggregator.aggregate_1m_to_timeframe(
    df_1m, symbol="BTC-USDT-SWAP", target_timeframe="5m"
)

# Сохранение в БД
all_records = normalized_funding + normalized_oi + normalized_l2
repo.upsert_records(all_records)

# Получение данных из БД
latest = repo.get_latest("BTC-USDT-SWAP", timeframe="1m")
historical = repo.get_by_timeframe(
    "BTC-USDT-SWAP",
    timeframe="5m",
    start_time=start_time,
    end_time=end_time,
)
```

## 📊 Расширенные рыночные данные (market_data_ext)

Модуль `market_meta` поддерживает хранение и обработку расширенных рыночных данных:

- **Open Interest (OI)** - открытый интерес
- **Funding Rates** - ставки финансирования
- **L2 Order Book метрики** - imbalance, spread

### Схема таблицы market_data_ext

```sql
CREATE TABLE market_data_ext (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,

    -- Open Interest
    open_interest DECIMAL(20, 8),
    oi_change_24h DECIMAL(20, 8),
    oi_change_pct_24h DECIMAL(10, 6),

    -- Funding Rates
    funding_rate DECIMAL(10, 8),
    next_funding_time TIMESTAMPTZ,
    funding_interval_hours INTEGER,

    -- L2 Order Book
    bid_imbalance DECIMAL(10, 6),
    ask_imbalance DECIMAL(10, 6),
    spread_bps DECIMAL(10, 2),

    -- Метаданные
    source VARCHAR(20) NOT NULL DEFAULT 'okx',
    bar_timestamp TIMESTAMPTZ,  -- Привязка к бару OHLCV
    timeframe VARCHAR(10),      -- 1m, 5m, 15m, 1H

    -- Версионирование
    run_id VARCHAR(100),
    algo_version VARCHAR(50),
    params_hash VARCHAR(64),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_market_data_ext_symbol_timeframe_bar_ts
        UNIQUE (symbol, timeframe, bar_timestamp)
);
```

### Примеры SQL запросов

#### Join с OHLCV по bar_timestamp

```sql
-- Получение OHLCV с расширенными данными
SELECT
    o.symbol,
    o.timestamp,
    o.open,
    o.high,
    o.low,
    o.close,
    o.volume,
    m.open_interest,
    m.funding_rate,
    m.bid_imbalance,
    m.ask_imbalance,
    m.spread_bps
FROM swap_ohlcv_p o
LEFT JOIN market_data_ext m
    ON o.symbol = m.symbol
    AND o.timestamp = m.bar_timestamp
    AND o.timeframe = m.timeframe
WHERE o.symbol = 'BTC-USDT-SWAP'
    AND o.timeframe = '1H'
    AND o.timestamp >= '2025-01-01'
ORDER BY o.timestamp;
```

#### Анализ funding rates

```sql
-- Средняя funding rate за период
SELECT
    symbol,
    timeframe,
    AVG(funding_rate) as avg_funding_rate,
    MAX(funding_rate) as max_funding_rate,
    MIN(funding_rate) as min_funding_rate,
    COUNT(*) as count
FROM market_data_ext
WHERE funding_rate IS NOT NULL
    AND bar_timestamp >= NOW() - INTERVAL '7 days'
GROUP BY symbol, timeframe
ORDER BY avg_funding_rate DESC;
```

#### Анализ Open Interest

```sql
-- Изменение Open Interest за 24 часа
SELECT
    symbol,
    timeframe,
    bar_timestamp,
    open_interest,
    oi_change_24h,
    oi_change_pct_24h
FROM market_data_ext
WHERE open_interest IS NOT NULL
    AND symbol = 'BTC-USDT-SWAP'
    AND timeframe = '1H'
    AND bar_timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY bar_timestamp DESC;
```

#### Анализ L2 Order Book imbalance

```sql
-- Средний imbalance за период
SELECT
    symbol,
    timeframe,
    AVG(bid_imbalance) as avg_bid_imbalance,
    AVG(ask_imbalance) as avg_ask_imbalance,
    AVG(spread_bps) as avg_spread_bps
FROM market_data_ext
WHERE bid_imbalance IS NOT NULL
    AND bar_timestamp >= NOW() - INTERVAL '1 day'
GROUP BY symbol, timeframe;
```

#### Поиск "призрачных" баров (проверка целостности)

```sql
-- Найти bar_timestamp в market_data_ext, которых нет в OHLCV
SELECT DISTINCT
    m.symbol,
    m.timeframe,
    m.bar_timestamp
FROM market_data_ext m
LEFT JOIN swap_ohlcv_p o
    ON m.symbol = o.symbol
    AND m.bar_timestamp = o.timestamp
    AND m.timeframe = o.timeframe
WHERE o.timestamp IS NULL
ORDER BY m.bar_timestamp DESC;
```

### API методы для временных рядов

#### MarketDataLoader

```python
from src.market_meta.infrastructure.data_loader import MarketDataLoader

loader = MarketDataLoader()

# Загрузка funding rates
funding = await loader.load_funding_rates(
    symbols=["BTC-USDT-SWAP"],
    start_time=datetime(2025, 1, 1),
    end_time=datetime(2025, 1, 2),
)

# Загрузка Open Interest
oi = await loader.load_open_interest(
    symbols=["BTC-USDT-SWAP"],
    start_time=datetime(2025, 1, 1),
    end_time=datetime(2025, 1, 2),
)

# Загрузка L2 Order Book
l2 = await loader.load_order_book_l2(
    symbols=["BTC-USDT-SWAP"],
    at=datetime.now(),
    depth=20,
)

# Загрузка всех типов данных
all_data = await loader.load_all(
    symbols=["BTC-USDT-SWAP"],
    start_time=datetime(2025, 1, 1),
    end_time=datetime(2025, 1, 2),
)
```

#### MarketDataNormalizer

```python
from src.market_meta.infrastructure.normalizer import MarketDataNormalizer
from src.market_meta.infrastructure.ohlcv_aligner import OHLCVAligner

aligner = OHLCVAligner(engine)
normalizer = MarketDataNormalizer(aligner)

# Нормализация к 1m барам
normalized = normalizer.normalize_to_1m_bars(
    records=data,
    symbol="BTC-USDT-SWAP",
    bar_timestamps=None,  # Автоматическая загрузка из БД
)
```

#### MarketDataAggregator

```python
from src.market_meta.infrastructure.aggregator import MarketDataAggregator
import pandas as pd

aggregator = MarketDataAggregator(aligner)

# Агрегация 1m → 5m
df_1m = pd.DataFrame(normalized_data)
df_5m = aggregator.aggregate_1m_to_timeframe(
    data=df_1m,
    symbol="BTC-USDT-SWAP",
    target_timeframe="5m",
    start_time=datetime(2025, 1, 1),
    end_time=datetime(2025, 1, 2),
)
```

#### MarketDataExtRepository

```python
from src.market_meta.infrastructure.database import MarketDataExtRepository

repo = MarketDataExtRepository(engine)

# UPSERT записей
records = [
    {
        "symbol": "BTC-USDT-SWAP",
        "timestamp": datetime.now(),
        "bar_timestamp": datetime.now(),
        "timeframe": "1m",
        "open_interest": 1000000.0,
        "source": "okx",
    }
]
repo.upsert_records(records, batch_size=1000)

# Получение последней записи
latest = repo.get_latest("BTC-USDT-SWAP", timeframe="1m")

# Получение данных за период
historical = repo.get_by_timeframe(
    symbol="BTC-USDT-SWAP",
    timeframe="5m",
    start_time=datetime(2025, 1, 1),
    end_time=datetime(2025, 1, 2),
)
```

#### Retention политика

```python
from src.market_meta.infrastructure.retention import MarketDataExtRetention

retention = MarketDataExtRetention(engine)

# Dry-run (проверка без удаления)
deleted = retention.cleanup_old_data(
    dry_run=True,
    l2_retention_days=7,
    oi_retention_days=90,
    funding_retention_days=730,
)

# Фактическая очистка
deleted = retention.cleanup_old_data(
    dry_run=False,
    l2_retention_days=7,
    oi_retention_days=90,
    funding_retention_days=730,
)
```

### Raw Ingest - запись сырых данных

```python
from sqlalchemy import create_engine
from src.market_meta.infrastructure.raw_ingest import RawIngestor

engine = create_engine("postgresql://...")
ingestor = RawIngestor(engine, source="okx")

# Запись funding rate данных
records = [
    {"symbol": "BTC-USDT-SWAP", "ts": datetime.now(), "payload": {"rate": 0.0001}},
]
# Dry-run (по умолчанию)
ingestor.ingest_funding(records, dry_run=True)

# Фактическая запись
ingestor.ingest_funding(records, dry_run=False)

# Аналогично для OI и L2
ingestor.ingest_oi(records, dry_run=False)
ingestor.ingest_l2(records, dry_run=False)
```

### Sync State - инкрементальная загрузка

```python
from src.market_meta.infrastructure.sync_state import SyncStateManager

manager = SyncStateManager(engine, safety_lag_seconds=120)

# Получить окно для синхронизации
start_ts, end_ts = manager.get_sync_window(
    pipeline="raw_ingest",
    symbol="BTC-USDT-SWAP",
    data_type="funding",
)

# После успешной загрузки - обновить watermark
manager.set_last_ts(
    pipeline="raw_ingest",
    symbol="BTC-USDT-SWAP",
    data_type="funding",
    last_ts=end_ts,
    dry_run=False,
)
```

### Quality Checks - проверки качества данных

```python
import asyncpg
from src.market_meta.application.quality_checks import (
    check_freshness,
    check_smoke_10m,
    check_coverage_1m,
    check_fill_rate,
    check_event_freshness,
    run_all_checks,
)
from src.market_meta.infrastructure.quality_repository import QualityMetricsRepository

pool = await asyncpg.create_pool("postgresql://...")

# Отдельные проверки
freshness_results = await check_freshness(pool)
smoke_results = await check_smoke_10m(pool, min_rows=8)
coverage_results = await check_coverage_1m(pool, window_minutes=60)
fill_results = await check_fill_rate(pool, window_hours=6)
event_results = await check_event_freshness(pool, window_hours=6)

# Все проверки сразу
report = await run_all_checks(pool)
print(f"Max severity: {report.max_severity}")
print(f"Critical issues: {len(report.critical_results)}")

# Сохранение метрик
repo = QualityMetricsRepository(pool)
await repo.save_results(report.results)

# Получение критических метрик
critical = await repo.get_critical_last_hour()
```

### CLI команды для market_data_ext

```bash
# Синхронизация расширенных данных
python -m src.market_meta.cli.cli sync-market-data-ext \
    --symbols "BTC-USDT-SWAP,ETH-USDT-SWAP" \
    --timeframes "1m,5m,15m" \
    --start-time "2025-01-01T00:00:00Z" \
    --end-time "2025-01-02T00:00:00Z" \
    --types "funding,oi,l2"

# Очистка старых данных
python -m src.market_meta.cli.cli cleanup-market-data-ext \
    --dry-run  # Проверка без удаления
```

### Retention политика

По умолчанию применяются следующие retention периоды:

- **L2 Order Book**: 7 дней (высокая частота, низкая ценность старых данных)
- **Open Interest**: 90 дней (достаточно для анализа трендов)
- **Funding Rates**: 730 дней (2 года, исторические данные важны)

### Quality Checks - пороги и проверки

| Проверка | Warn | Critical | Описание |
|----------|------|----------|----------|
| `freshness` | >5 мин | >15 мин | Лаг последней записи 1m |
| `smoke_10m` | <9 rows | <8 rows | Минимум записей за 10 минут |
| `coverage_1m` | <90% | <70% | Покрытие относительно OHLCV |
| `fill_rate_funding` | <95% | <80% | Заполненность funding_rate |
| `fill_rate_oi` | <95% | <80% | Заполненность open_interest |
| `fill_rate_l2` | <50% | <20% | Заполненность L2 данных |
| `event_freshness_funding` | >30 мин | >120 мин | Свежесть события funding |
| `event_freshness_oi` | >30 мин | >120 мин | Свежесть события OI |
| `event_freshness_l2` | >10 мин | >60 мин | Свежесть события L2 |

## 🔧 Конфигурация

### Переменные окружения

#### Основные настройки

```bash
# Окружение
export MARKET_META_ENVIRONMENT=production  # development, staging, production
export MARKET_META_DEBUG_MODE=false
export MARKET_META_DATA_DIR=./data
export MARKET_META_CONFIG_FILE=config.yaml
```

#### OKX API

```bash
# API ключи (опциональные для публичных эндпоинтов)
export OKX_API_KEY=your_api_key
export OKX_SECRET_KEY=your_secret_key
export OKX_PASSPHRASE=your_passphrase

# Настройки API
export OKX_BASE_URL=https://www.okx.com
export OKX_TIMEOUT_SECONDS=30

# Rate limiting
export OKX_MAX_REQUESTS_PER_SECOND=10
export OKX_MAX_REQUESTS_PER_MINUTE=600

# Retry настройки
export OKX_MAX_RETRIES=3
export OKX_BASE_DELAY_SECONDS=1.0
export OKX_MAX_DELAY_SECONDS=60.0
```

#### Кэширование

```bash
# TTL для разных типов данных
export MARKET_META_CACHE_TTL_HOURS=1
export MARKET_META_INSTRUMENT_CACHE_TTL_HOURS=1
export MARKET_META_VALIDATION_CACHE_TTL_MINUTES=5

# Авто-refresh
export MARKET_META_AUTO_REFRESH_ENABLED=true
export MARKET_META_AUTO_REFRESH_INTERVAL_HOURS=1

# Размер кэша
export MARKET_META_MAX_CACHE_SIZE_MB=100
```

#### Логирование

```bash
# Уровни логирования
export MARKET_META_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
export MARKET_META_OKX_LOG_LEVEL=INFO
export MARKET_META_VALIDATION_LOG_LEVEL=INFO

# Файлы логов
export MARKET_META_LOG_FILE=market_meta.log
export MARKET_META_MAX_LOG_SIZE_MB=10
export MARKET_META_LOG_BACKUP_COUNT=5

# Форматирование
export MARKET_META_LOG_FORMAT=json  # json или text
export MARKET_META_LOG_INCLUDE_TIMESTAMP=true

# Санитизация
export MARKET_META_MASK_API_KEYS=true
export MARKET_META_MAX_MESSAGE_LENGTH=1000
```

#### Валидация

```bash
# Строгость валидации
export MARKET_META_STRICT_VALIDATION=true
export MARKET_META_ALLOW_WARNINGS=true

# Лимиты валидации
export MARKET_META_MAX_VALIDATION_ERRORS=10
export MARKET_META_MAX_VALIDATION_WARNINGS=20

# Проверки
export MARKET_META_VALIDATE_PRICE_PRECISION=true
export MARKET_META_VALIDATE_QUANTITY_PRECISION=true
export MARKET_META_VALIDATE_RISK_LIMITS=true
export MARKET_META_VALIDATE_LIQUIDITY=false
```

#### Риск-менеджмент

```bash
# Лимиты позиций
export MARKET_META_MAX_POSITION_SIZE_USD=10000
export MARKET_META_MAX_TOTAL_EXPOSURE_USD=50000
export MARKET_META_MAX_LEVERAGE=10

# Политики риска
export MARKET_META_RISK_TOLERANCE=conservative  # conservative, moderate, aggressive
export MARKET_META_ENABLE_POSITION_LIMITS=true
export MARKET_META_ENABLE_EXPOSURE_LIMITS=true

# Алерты
export MARKET_META_RISK_ALERT_THRESHOLD=0.8  # 80% от лимита
export MARKET_META_CRITICAL_RISK_THRESHOLD=0.95  # 95% от лимита
```

#### Метрики

```bash
# Включение метрик
export MARKET_META_METRICS_ENABLED=true

# Экспорт метрик
export MARKET_META_EXPORT_METRICS=false
export MARKET_META_METRICS_PORT=9090

# Интервалы сбора
export MARKET_META_CACHE_METRICS_INTERVAL=60
export MARKET_META_VALIDATION_METRICS_INTERVAL=30
export MARKET_META_API_METRICS_INTERVAL=15

# Хранение метрик
export MARKET_META_METRICS_RETENTION_HOURS=24
```

### Загрузка конфигурации

```python
from src.market_meta import MarketMetaConfig, get_config

# Получение конфигурации (автоматически загружается из переменных окружения)
config = get_config()

# Доступ к настройкам
print(f"Окружение: {config.environment}")
print(f"OKX URL: {config.okx.base_url}")
print(f"Cache TTL: {config.cache.metadata_ttl_hours} часов")
print(f"Log Level: {config.logging.log_level}")
print(f"Max Position Size: ${config.risk.max_position_size_usd}")

# Валидация конфигурации
errors = config.validate()
if errors:
    print("Ошибки конфигурации:", errors)

# Преобразование в словарь (для логирования)
config_dict = config.to_dict()
```

## 📝 Логирование

### Настройка логирования

```python
from src.market_meta import configure_logging, get_logger

# Настройка логирования
configure_logging(
    level="INFO",                    # Уровень логирования
    log_file="market_meta.log",      # Файл логов
    console_output=True,             # Вывод в консоль
    file_output=True,                # Запись в файл
    max_size=10*1024*1024,          # Максимальный размер файла (10MB)
    backup_count=5                   # Количество файлов ротации
)

# Получение логгера
logger = get_logger(__name__)
logger.info("Модуль market_meta инициализирован")
```

### Специализированное логирование

```python
from src.market_meta import log_validation_result, log_cache_status, log_refresh_status

# Логирование результатов валидации
log_validation_result(
    symbol="BTC-USDT-SWAP",
    price=50000.0,
    qty=0.1,
    violations=["Price below minimum"],
    validation_time=0.05
)

# Логирование статуса кэша
log_cache_status(
    is_valid=True,
    last_refresh=datetime.now(),
    ttl_hours=1.0
)

# Логирование статуса обновления
log_refresh_status(
    success=True,
    instruments_count=150,
    message="Метаданные успешно обновлены"
)
```

## 📊 Метрики и мониторинг

### Сбор метрик

```python
from src.market_meta import get_metrics_collector, measure_time, measure_async_time

# Получение сборщика метрик
collector = get_metrics_collector()

# Запись метрик
collector.record_cache_hit("BTC-USDT-SWAP")
collector.record_validation_success("BTC-USDT-SWAP")
collector.record_api_latency("refresh_metadata", 0.5)

# Измерение времени выполнения (синхронное)
with measure_time("validation_operation"):
    violations = validate_order("BTC-USDT-SWAP", 50000.0, 0.1)

# Измерение времени выполнения (асинхронное)
async def my_async_function():
    async with measure_async_time("async_operation"):
        await refresh_okx_meta()
```

### Получение метрик

```python
# Получение метрик
cache_hit_ratio = collector.get_cache_hit_ratio()
validation_success_rate = collector.get_validation_success_rate()
api_latency = collector.get_api_latency("refresh_metadata")

print(f"Cache hit ratio: {cache_hit_ratio:.2%}")
print(f"Validation success rate: {validation_success_rate:.2%}")
print(f"API latency: {api_latency:.3f}s")
```

### Экспорт метрик

```python
from src.market_meta import MetricsExporter

# Создание экспортера
exporter = MetricsExporter(port=9090)

# Запуск HTTP сервера для метрик
await exporter.start_server()

# Получение метрик в формате JSON
metrics_json = exporter.export_metrics_json()

# Получение метрик в формате Prometheus
prometheus_metrics = exporter.export_prometheus()
```

### Мониторинг алертов

```python
from src.market_meta import MetricsMonitor

# Создание монитора
monitor = MetricsMonitor()

# Проверка алертов
alerts = monitor.check_alerts()
for alert in alerts:
    print(f"🚨 {alert['message']} (уровень: {alert['level']})")
```

## 🛡️ Обработка ошибок

### Иерархия исключений

```python
from src.market_meta import (
    MarketMetaError,          # Базовое исключение
    MetadataError,            # Ошибки метаданных
    MetadataStaleError,       # Устаревшие метаданные
    MetadataNotFoundError,    # Метаданные не найдены
    ValidationError,          # Ошибки валидации
    OrderValidationError,     # Ошибки валидации ордеров
    RiskError,                # Ошибки риска
    OKXIntegrationError,      # Ошибки интеграции с OKX
    OKXNetworkError,          # Сетевые ошибки OKX
    OKXRateLimitError,        # Превышение лимитов OKX
    ConfigurationError,       # Ошибки конфигурации
    CacheError,               # Ошибки кэша
    is_retryable_error        # Проверка возможности повтора
)
```

### Обработка исключений

```python
try:
    violations = validate_order("BTC-USDT-SWAP", 50000.0, 0.1)
except ValidationError as e:
    print(f"Ошибка валидации: {e}")
    print(f"Контекст: {e.context}")
    if e.context.get("violations"):
        print(f"Нарушения: {e.context['violations']}")
except MetadataError as e:
    print(f"Ошибка метаданных: {e}")
except OKXIntegrationError as e:
    print(f"Ошибка интеграции с OKX: {e}")
    if e.is_retryable():
        print("Можно повторить попытку")
```

### Проверка возможности повтора

```python
from src.market_meta import is_retryable_error

try:
    await refresh_okx_meta()
except Exception as e:
    if is_retryable_error(e):
        print("Ошибка временная, можно повторить")
        # Повторная попытка
    else:
        print("Критическая ошибка, требуется вмешательство")
```

## 🖥️ CLI команды

Модуль предоставляет 20 CLI команд для управления:

### Основные команды

```bash
# Обновление метаданных
python -m src.market_meta.cli refresh --force
python -m src.market_meta.cli refresh --types "SPOT,SWAP,FUTURES" --verbose

# Валидация ордера
python -m src.market_meta.cli validate BTC-USDT-SWAP -p 50000 -q 0.1 --balance 10000
python -m src.market_meta.cli validate BTC-USDT-SWAP -p 50000 -q 0.1 --leverage 5 --margin-mode isolated --json

# Информация об инструменте
python -m src.market_meta.cli info BTC-USDT-SWAP

# Статус модуля
python -m src.market_meta.cli status
```

### Управление кэшем

```bash
# Просмотр кэша
python -m src.market_meta.cli cache

# Установка TTL
python -m src.market_meta.cli set-ttl --hours 2

# Очистка кэша
python -m src.market_meta.cli clear-cache

# Авто-refresh
python -m src.market_meta.cli auto-refresh --enable
python -m src.market_meta.cli auto-refresh --disable
```

### Управление логированием

```bash
# Настройка логирования
python -m src.market_meta.cli setup-logging --level DEBUG --file logs/debug.log

# Просмотр логов
python -m src.market_meta.cli logs

# Очистка логов
python -m src.market_meta.cli clear-logs
```

### Конфигурация

```bash
# Просмотр конфигурации
python -m src.market_meta.cli config
python -m src.market_meta.cli config --json
python -m src.market_meta.cli config --env

# Перезагрузка конфигурации
python -m src.market_meta.cli reload-config

# Валидация конфигурации
python -m src.market_meta.cli validate-config
```

### Метрики и мониторинг

```bash
# Просмотр метрик
python -m src.market_meta.cli metrics
python -m src.market_meta.cli metrics --json

# Проверка алертов
python -m src.market_meta.cli alerts

# Запуск экспорта метрик
python -m src.market_meta.cli start-metrics --port 9090

# Остановка экспорта метрик
python -m src.market_meta.cli stop-metrics
```

### База данных

```bash
# Создание таблиц
python -m src.market_meta.cli db --create

# Удаление таблиц
python -m src.market_meta.cli db --drop
```

## 🗄️ База данных

### Модели данных

Модуль использует SQLAlchemy для работы с базой данных. Доступны следующие модели:

#### MarketMetadata

Таблица для хранения метаданных инструментов:

```python
from src.market_meta.database import MarketMetadata as MarketMetadataDB

# Поля:
# - symbol_id: Символ инструмента
# - inst_id: ID инструмента
# - inst_type: Тип инструмента (SPOT, SWAP, FUTURES, OPTIONS)
# - base_ccy, quote_ccy, settle_ccy: Валюты
# - tick_size_step, tick_size_min, tick_size_max: Размеры тика
# - lot_size_step, lot_size_min, lot_size_max: Размеры лота
# - contract_val: Номинальная стоимость
# - fee_maker, fee_taker: Комиссии
# - max_leverage: Максимальное плечо
# - margin_mode, position_mode: Режимы маржи
# - funding_rate: Ставка финансирования
# - is_tradable: Торгуется ли инструмент
# - created_at, updated_at: Временные метки
```

#### ValidationCache

Таблица для кэширования результатов валидации:

```python
from src.market_meta.database import ValidationCache

# Поля:
# - symbol_id: Символ инструмента
# - validation_type: Тип валидации (order, risk, liquidity)
# - params_hash: Хеш параметров валидации
# - result: JSON результат валидации
# - is_valid: Валиден ли результат
# - violations: JSON список нарушений
# - expires_at: Время истечения кэша
```

#### RiskLimits

Таблица для хранения лимитов риска:

```python
from src.market_meta.database import RiskLimits as RiskLimitsDB

# Поля:
# - symbol_id: Символ инструмента
# - risk_level: Уровень риска (LOW, MEDIUM, HIGH)
# - max_position_size: Максимальный размер позиции
# - max_notional_value: Максимальная номинальная стоимость
# - max_position_size_pct: Максимальный размер позиции в % от баланса
# - max_total_exposure_pct: Максимальная общая экспозиция в %
# - max_daily_loss_pct: Максимальный дневной убыток в %
```

#### ValidationLog

Таблица для логирования валидаций:

```python
from src.market_meta.database import ValidationLog

# Поля:
# - run_id: ID запуска
# - symbol_id: Символ инструмента
# - validation_type: Тип валидации
# - price, qty, leverage, margin_mode: Параметры валидации
# - is_valid: Валиден ли результат
# - violations: JSON список нарушений
# - processing_time_ms: Время обработки в миллисекундах
# - created_at: Временная метка
```

### Миграции

```bash
# Применение миграций
psql -d your_database -f src/market_meta/migrations/001_create_market_meta_tables.sql
```

### Использование моделей

```python
from sqlalchemy import create_engine
from src.market_meta.database import create_tables, MarketMetadata as MarketMetadataDB

# Создание engine
engine = create_engine("postgresql://user:password@localhost/market_meta")

# Создание таблиц
create_tables(engine)

# Использование моделей
from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
session = Session()

# Сохранение метаданных
metadata = MarketMetadataDB(
    symbol_id="BTC-USDT-SWAP",
    inst_id="BTC-USDT-SWAP",
    inst_type="SWAP",
    base_ccy="BTC",
    quote_ccy="USDT",
    tick_size_step=0.1,
    lot_size_step=0.01,
    contract_val=0.01,
    fee_maker=0.0002,
    fee_taker=0.0005,
    max_leverage=125,
    is_tradable=True
)
session.add(metadata)
session.commit()
```

## 📊 Модели данных

### InstrumentMetadata

```python
from src.market_meta import InstrumentMetadata, InstrumentType, MarginMode

@dataclass
class InstrumentMetadata:
    symbol: str                    # Символ инструмента
    inst_id: str                   # ID инструмента
    inst_type: InstrumentType      # Тип инструмента
    base_ccy: str                  # Базовая валюта
    quote_ccy: str                 # Котируемая валюта
    settle_ccy: str | None         # Валюта расчетов
    contract_val: Decimal | None  # Номинальная стоимость контракта
    tick_size: TickSize | None     # Размер тика
    lot_size: LotSize | None       # Размер лота
    min_notional: Decimal | None   # Минимальная номинальная стоимость
    fee_maker: Decimal | None      # Комиссия maker
    fee_taker: Decimal | None      # Комиссия taker
    max_leverage: int | None       # Максимальное плечо
    position_mode: str | None      # Режим позиции
    maint_margin_rate: Decimal | None  # Ставка поддержания маржи
    risk_limit_tier: int | None    # Уровень риск-лимита
    funding_rate: FundingRate | None  # Ставка финансирования
    liquidity: LiquidityParams | None  # Параметры ликвидности
    is_tradable: bool              # Торгуется ли инструмент
```

### ValidationResult

```python
from src.market_meta import ValidationResult

@dataclass
class ValidationResult:
    is_valid: bool                 # Общий результат
    errors: list[str]              # Список ошибок
    warnings: list[str]            # Список предупреждений
```

### Модель RiskLimits

```python
from src.market_meta import RiskLimits, RiskLevel, PositionLimit

@dataclass
class RiskLimits:
    max_position_size_usd: Decimal = Decimal('10000')      # Макс. размер позиции
    max_total_exposure_usd: Decimal = Decimal('50000')     # Макс. общая экспозиция
    max_leverage: int = 10                                 # Макс. плечо
    risk_tolerance: RiskLevel = RiskLevel.CONSERVATIVE     # Толерантность к риску
    position_limits: dict[str, PositionLimit] = field(default_factory=dict)
    current_positions: dict[str, Position] = field(default_factory=dict)
    position_history: list[Position] = field(default_factory=list)
```

## 🧪 Тестирование

### Запуск всех тестов

```bash
# Все тесты модуля market_meta
pytest tests/market_meta/ -v
```

### Демонстрационный режим

```bash
# Запуск демо-скрипта
python src/market_meta/demo.py
```

### Покрытие тестами

```bash
# Запуск с покрытием
pytest tests/market_meta/ --cov=src.market_meta --cov-report=html

# Просмотр отчета
open htmlcov/index.html
```

## 🏗️ Архитектура

### Диаграмма слоёв (Clean Architecture)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                                       │
│  cli.py - 20+ команд для управления модулем                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Application Layer                                   │
│  api.py - MarketMetaAPI (основной фасад)                                    │
│  quality_checks.py - проверки качества данных                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Domain Layer                                      │
│  metadata.py      - InstrumentMetadata, TickSize, LotSize, FundingRate      │
│  validators.py    - MarketValidator, PositionValidator                      │
│  risk_limits.py   - RiskLimits, PositionLimit                               │
│  quality.py       - Severity, Thresholds, CheckResult, QualityReport        │
│  exceptions.py    - MarketMetaError, ValidationError, OKXIntegrationError   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Infrastructure Layer                                  │
│                                                                              │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────────┐   │
│  │     OKX Integration     │  │          Data Pipeline                   │   │
│  │  client.py              │  │  raw_ingest.py     - Raw → raw schema    │   │
│  │  market.py              │  │  normalizer.py     - Raw → 1m bars       │   │
│  │  okx_integration.py     │  │  aggregator.py     - 1m → 5m/15m/1H      │   │
│  │  orders.py              │  │  ohlcv_aligner.py  - Sync with OHLCV     │   │
│  └─────────────────────────┘  │  data_loader.py    - Load from OKX       │   │
│                               │  retention.py      - Cleanup old data    │   │
│  ┌─────────────────────────┐  │  sync_state.py     - Watermark manager   │   │
│  │      Persistence        │  └─────────────────────────────────────────┘   │
│  │  database.py            │                                                 │
│  │  quality_repository.py  │  ┌─────────────────────────────────────────┐   │
│  └─────────────────────────┘  │       Observability                      │   │
│                               │  metrics.py         - Prometheus metrics │   │
│  ┌─────────────────────────┐  │  logging_config.py  - Structured logging │   │
│  │     Configuration       │  │  config.py          - Env-based config   │   │
│  │  config.py              │  └─────────────────────────────────────────┘   │
│  │  config.yaml            │                                                 │
│  └─────────────────────────┘                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Поток данных market_data_ext (Raw → Core)

```text
                    OKX API
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  1. RAW INGEST (raw_ingest.py)                                           │
│     - Загрузка funding/oi/l2 с OKX                                       │
│     - payload_hash для дедупликации                                      │
│     - Запись в raw.market_data_ext_raw                                   │
└──────────────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  2. NORMALIZE (normalizer.py + ohlcv_aligner.py)                         │
│     - Привязка к реальным bar_timestamp из swap_ohlcv_p                  │
│     - Forward-fill для funding (8h интервал)                             │
│     - Запись в core.market_data_ext (timeframe='1m')                     │
└──────────────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  3. AGGREGATE (aggregator.py)                                            │
│     - 1m → 5m/15m/1H с привязкой к реальным барам                        │
│     - OHLC для OI, TWAP для funding, snapshot для L2                     │
│     - Запись в core.market_data_ext (timeframe='5m'/'15m'/'1H')          │
└──────────────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  4. QUALITY CHECKS (quality_checks.py + quality_repository.py)           │
│     - freshness: лаг витрины < 15 мин                                    │
│     - coverage: покрытие относительно OHLCV > 90%                        │
│     - fill_rate: заполненность полей funding/oi/l2                       │
│     - Запись метрик в ops.data_quality_metrics                           │
└──────────────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  5. SYNC STATE (sync_state.py)                                           │
│     - Watermark в ops.sync_state                                         │
│     - Инкрементальная загрузка: from last_ts → now - safety_lag          │
│     - Защита от пропусков через overlap                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Компоненты модуля

1. **API слой** (`api.py`)
   - Основной интерфейс для работы с модулем
   - Управление кэшем и авто-refresh
   - Интеграция всех компонентов

2. **Интеграция с OKX** (`okx_integration.py`)
   - Загрузка метаданных с OKX API
   - Retry/backoff механизмы
   - Rate limiting
   - Обработка ошибок

3. **Метаданные** (`metadata.py`)
   - Модели данных для инструментов
   - Размеры тика и лота
   - Ставки финансирования
   - Параметры ликвидности

4. **Валидаторы** (`validators.py`)
   - Валидация рыночных данных
   - Валидация позиций
   - Проверка лимитов

5. **Риск-менеджмент** (`risk_limits.py`)
   - Управление лимитами риска
   - Валидация экспозиции
   - Алерты риска

6. **Качество данных** (`quality.py`, `quality_checks.py`, `quality_repository.py`)
   - Модели: Severity (ok/warn/critical), Thresholds, CheckResult, QualityReport
   - Проверки: freshness, smoke_10m, coverage_1m, fill_rate, event_freshness
   - Хранение метрик в ops.data_quality_metrics

7. **Raw Ingest** (`raw_ingest.py`)
   - Запись сырых данных в raw.market_data_ext_raw
   - payload_hash для защиты от дублей
   - Поддержка типов: funding, oi, l2

8. **Sync State** (`sync_state.py`)
   - Watermark для инкрементальной загрузки
   - safety_lag для защиты от неполных данных
   - overlap для защиты от пропусков

9. **Конфигурация** (`config.py`)
   - Централизованная конфигурация
   - Загрузка из переменных окружения
   - Валидация настроек

10. **Логирование** (`logging_config.py`)
    - Настройка логирования
    - Специализированные логгеры
    - Ротация логов

11. **Метрики** (`metrics.py`)
    - Сбор метрик
    - Экспорт в Prometheus
    - Мониторинг алертов

12. **База данных** (`database.py`)
    - Модели SQLAlchemy
    - Хранение метаданных
    - Кэш валидаций

13. **CLI** (`cli.py`)
    - 20+ команд для управления
    - Интерактивный интерфейс
    - Управление конфигурацией

### Схема БД (упрощённая)

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  raw schema                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  market_data_ext_raw                                                 │    │
│  │  - symbol, data_type, ts, payload, payload_hash, source              │    │
│  │  - PK: (symbol, data_type, ts, payload_hash)                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  core schema                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  market_data_ext                                                     │    │
│  │  - symbol, timeframe, bar_timestamp                                  │    │
│  │  - open_interest, oi_change_24h, funding_rate, next_funding_time     │    │
│  │  - bid_imbalance, ask_imbalance, spread_bps, imbalance               │    │
│  │  - funding_ts, oi_ts, l2_ts (timestamps событий)                     │    │
│  │  - UNIQUE: (symbol, timeframe, bar_timestamp)                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  ops schema                                                                  │
│  ┌─────────────────────────────┐  ┌─────────────────────────────────────┐   │
│  │  sync_state                 │  │  data_quality_metrics               │   │
│  │  - pipeline, symbol,        │  │  - ts, check_name, severity         │   │
│  │    data_type, last_ts       │  │  - symbol, timeframe, value, meta   │   │
│  │  - PK: (pipeline, symbol,   │  └─────────────────────────────────────┘   │
│  │         data_type)          │                                            │
│  └─────────────────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🚨 Безопасность

### Критические проверки

1. **Валидация размера тика** - предотвращает отклонение ордеров
2. **Валидация размера лота** - проверка минимальных/максимальных количеств
3. **Проверка номинальной стоимости** - контроль размера позиции
4. **Лимиты риска** - защита от превышения экспозиции
5. **Проверка торгуемости** - только активные инструменты
6. **Валидация плеча** - контроль максимального плеча
7. **Проверка комиссий** - валидация структуры комиссий
8. **Валидация ликвидности** - проверка достаточной ликвидности
9. **Проверка маржевых требований** - контроль маржинальных требований

### Рекомендации

- Всегда вызывайте `refresh_okx_meta()` перед началом торговли
- Проверяйте `validate_order()` перед отправкой каждого ордера
- Мониторьте метрики риска в реальном времени
- Настройте алерты для критических нарушений
- Используйте CLI команды для оперативного управления
- Настройте логирование для аудита операций
- Регулярно проверяйте актуальность метаданных
- Используйте строгий режим валидации в продакшене
- Настройте авто-refresh для поддержания актуальности данных

## 📈 Производительность

### Оптимизации

- **Кэширование метаданных** с TTL
- **Авто-refresh** в фоновом режиме
- **Retry/backoff** для надежности API
- **Rate limiting** для защиты от превышения лимитов
- **Асинхронная обработка** для высокой производительности
- **Кэш валидаций** для повторных проверок
- **Индексы базы данных** для быстрого поиска

### Метрики производительности

- **Cache hit ratio** - эффективность кэширования
- **API latency** - время отклика API
- **Validation success rate** - успешность валидации
- **Error rate** - частота ошибок
- **Memory usage** - использование памяти
- **Database query time** - время запросов к БД

## 🔮 Планы развития

### Краткосрочные (1-2 недели)

- [x] ✅ Иерархия исключений с контекстом
- [x] ✅ Retry/backoff в OKX клиенте
- [x] ✅ Конфигурация через переменные окружения
- [x] ✅ Метрики и мониторинг
- [x] ✅ CLI интерфейс (20 команд)
- [x] ✅ База данных для хранения метаданных
- [x] ✅ Расширенные рыночные данные (market_data_ext) - Фаза 4.5
  - [x] Open Interest (OI)
  - [x] Funding Rates
  - [x] L2 Order Book метрики (imbalance, spread)
  - [x] Нормализация к барам OHLCV
  - [x] Агрегация для разных таймфреймов
  - [x] Retention политика
- [ ] Интеграция market_data_ext в Features/Signals pipeline (Фаза 4.6+)
- [ ] Интеграция с системой мониторинга

### Среднесрочные (1 месяц)

- [ ] Поддержка других бирж (Binance, Bybit)
- [ ] Автоматическое обновление метаданных по расписанию
- [ ] Webhook уведомления для критических событий
- [ ] Графический интерфейс для просмотра метрик
- [ ] Интеграция с системой алертов

### Долгосрочные (2-3 месяца)

- [ ] Машинное обучение для оптимизации лимитов
- [ ] Адаптивные лимиты риска
- [ ] Интеграция с системой исполнения ордеров
- [ ] Графический интерфейс для управления
- [ ] Поддержка множественных аккаунтов

## 🏆 Готовность к продакшену

**Модуль `market_meta` полностью готов к использованию в продакшене!**

### ✅ Реализованные возможности

- [x] Полная система валидации ордеров
- [x] Интеграция с OKX API с retry/backoff
- [x] Система метрик и мониторинга
- [x] CLI интерфейс (20 команд)
- [x] Централизованная конфигурация
- [x] Система логирования
- [x] Обработка исключений
- [x] Управление лимитами риска
- [x] Кэширование метаданных
- [x] База данных для хранения метаданных
- [x] Расширенные рыночные данные (market_data_ext) - Фаза 4.5
  - [x] Загрузка OI, Funding Rates, L2 Order Book
  - [x] Нормализация к фактическим барам OHLCV
  - [x] Агрегация для разных таймфреймов
  - [x] Retention политика
- [x] Полный набор тестов
- [x] Документация

### 🚀 Рекомендации для развертывания

1. **Настройте переменные окружения** для вашего окружения
2. **Запустите CLI команды** для проверки статуса
3. **Настройте логирование** для мониторинга
4. **Запустите экспорт метрик** для наблюдаемости
5. **Протестируйте валидацию** с реальными данными
6. **Настройте авто-refresh** для поддержания актуальности
7. **Создайте таблицы БД** используя миграции
8. **Настройте алерты** для критических событий

**Модуль прошел полное тестирование и готов к развертыванию!** 🎉

## 📞 Поддержка

Для вопросов и проблем обращайтесь к команде PKLPO или создайте issue в репозитории.

## 📄 Лицензия

Модуль является частью проекта PKLPO и следует его лицензии.
