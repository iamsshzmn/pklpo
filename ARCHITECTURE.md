# PKLPO - Архитектура системы

**Версия:** 0.3.0 | **Обновлено:** 2026-01-15

---

## Содержание

- [Обзор](#обзор)
- [Высокоуровневая архитектура](#высокоуровневая-архитектура)
- [Data Flow Pipeline](#data-flow-pipeline)
- [Компоненты системы](#компоненты-системы)
- [Схема базы данных](#схема-базы-данных)
- [Конфигурация](#конфигурация)
- [Airflow DAGs](#airflow-dags)
- [Интеграции](#интеграции)

---

## Обзор

PKLPO - enterprise-система количественной торговли криптовалютами, построенная на принципах Clean Architecture. Система обеспечивает полный цикл от получения рыночных данных до генерации торговых сигналов и управления позициями.

### Ключевые принципы

| Принцип | Описание |
|---------|----------|
| **Single Source of Truth** | Все данные хранятся в PostgreSQL |
| **Идемпотентность** | Все операции безопасны для повторного выполнения (UPSERT) |
| **No Look-Ahead Bias** | Расчеты только после закрытия бара |
| **Инкрементальность** | Watermark-based обновление (только новые данные) |
| **Observability** | Метрики и логи по умолчанию |

### Технологический стек

| Компонент | Технология |
|-----------|------------|
| Language | Python 3.11+ |
| Database | PostgreSQL 15+ |
| Async DB | asyncpg + SQLAlchemy 2.0 |
| Data | Pandas, NumPy, pandas-ta |
| Orchestration | Apache Airflow |
| Config | Pydantic Settings |
| Deployment | Docker, Docker Compose |

---

## Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   OKX API    │  │   Airflow    │  │     CLI      │  │    Slack     │    │
│  │  (Exchange)  │  │ (Scheduler)  │  │  (Commands)  │  │   (Alerts)   │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼──────────────────┼──────────┘
          │                  │                  │                  │
          ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION LAYER                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         PIPELINE ORCHESTRATOR                        │   │
│  │                                                                       │   │
│  │   Ingest → Data QA → Market Store → Features → MTF → Signals        │   │
│  │                                                                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ Candles  │ │ Features │ │   MTF    │ │ Signals  │ │Positions │         │
│  │  Sync    │ │  Calc    │ │ Analysis │ │Generator │ │Calculator│         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │   Indicator      │  │    Signal        │  │    Position      │          │
│  │   Specs          │  │    Rules         │  │    Models        │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │   Validators     │  │    Protocols     │  │   Risk Limits    │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INFRASTRUCTURE LAYER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │   PostgreSQL     │  │   OKX Client     │  │    Metrics       │          │
│  │   (asyncpg)      │  │   (REST API)     │  │   (Prometheus)   │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │   Migrations     │  │    Caching       │  │    Logging       │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Pipeline

### Основной Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   INGEST    │────▶│   DATA QA   │────▶│   MARKET    │────▶│  FEATURES   │
│  (OKX API)  │     │ (Validation)│     │   STORE     │     │   CALC      │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                   │
                   ┌───────────────────────────────────────────────┘
                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│     MTF     │────▶│  CONSENSUS  │────▶│   SIGNALS   │────▶│  POSITIONS  │
│   Context   │     │ Aggregation │     │  Generator  │     │   Sizing    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Детализация этапов

| Этап | Модуль | Вход | Выход | Таблица БД |
|------|--------|------|-------|------------|
| **Ingest** | `candles/sync_swap_candles.py` | OKX API | Raw OHLCV | `swap_ohlcv_p` |
| **Features** | `features/` | OHLCV | 500+ индикаторов | `indicators` |
| **MTF Context** | `mtf/context/` | Indicators (4H, 1H) | Market Regime | `mtf_context` |
| **MTF Triggers** | `mtf/triggers/` | Indicators (5m, 1m) | Reversal Probability | `mtf_triggers` |
| **Consensus** | `mtf/consensus/` | Context + Triggers | Weighted Score | `mtf_consensus` |
| **Signals** | `signals/` | Consensus | LONG/SHORT/FLAT | `signals` |
| **Positions** | `positions/` | Signals + Risk | Order Params | `positions` |

### Watermark-based Updates

Инкрементальное обновление через watermark:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Получить watermark: MAX(timestamp) FROM indicators         │
│     WHERE symbol = :s AND timeframe = :tf                       │
├─────────────────────────────────────────────────────────────────┤
│  2. Проверить новые данные: MAX(timestamp) FROM swap_ohlcv_p   │
│     WHERE symbol = :s AND timeframe = :tf                       │
├─────────────────────────────────────────────────────────────────┤
│  3. Если ohlcv_max > indicators_max → есть работа              │
│     Загрузить OHLCV с warmup (500 баров до watermark)          │
├─────────────────────────────────────────────────────────────────┤
│  4. Рассчитать индикаторы, UPSERT в indicators                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Компоненты системы

### 1. Candles Sync (`src/candles/`)

Синхронизация OHLCV данных с OKX.

```
src/candles/
├── sync_swap_candles.py    # Основной синхронизатор
├── load_instruments.py     # Загрузка списка инструментов
└── swap_cli.py             # CLI команды
```

**Особенности:**
- Rate limiting: 80 req/s для публичных API
- Batch size: 300 свечей за запрос
- Concurrent symbols: до 3 параллельно
- UPSERT в `swap_ohlcv_p`

### 2. Features Module (`src/features/`)

Расчёт 500+ технических индикаторов.

```
src/features/
├── core/                      # Главный API compute_features()
│   └── calculation.py
├── indicator_groups/          # 10 групп индикаторов
│   ├── ma.py                  # Moving Averages (EMA, SMA, WMA)
│   ├── oscillators.py         # RSI, Stochastic, CCI, Williams %R
│   ├── volatility.py          # ATR, Bollinger, Keltner
│   ├── volume.py              # OBV, VWAP, MFI, CMF
│   ├── trend.py               # ADX, MACD, Aroon, Supertrend
│   ├── candles.py             # Candlestick patterns, Heikin-Ashi
│   ├── squeeze.py             # TTM Squeeze indicators
│   ├── statistics.py          # Rolling stats, Z-score
│   └── performance.py         # Returns, Sharpe, Drawdown
├── infrastructure/
│   ├── db_operations.py       # fetch_ohlcv_df, fetch_latest_ts
│   ├── persistence/
│   │   └── inserter.py        # insert_indicators (UPSERT)
│   └── indicator_registry.py  # Централизованный реестр
├── presets/
│   └── features_calc_short_v1.py  # 24 основных индикатора
└── config.py                  # Конфигурация (использует src.config)
```

**Data Flow:**

```
swap_ohlcv_p ──▶ fetch_ohlcv_df() ──▶ compute_features() ──▶ insert_indicators() ──▶ indicators
     │                │                      │                      │
     │                │                      │                      │
     ▼                ▼                      ▼                      ▼
  timestamp       DataFrame             DataFrame              UPSERT
  (ms)            ts (seconds)          + indicators           to DB
                  + OHLCV               + timestamp (ms)
```

**Важно:** `fetch_ohlcv_df` конвертирует timestamp:
- Из БД: миллисекунды → секунды (в колонке `ts`)
- В `compute_features`: нужна колонка `timestamp` в миллисекундах

### 3. MTF Module (`src/mtf/`)

Мультитаймфрейм анализ с определением режимов рынка.

```
src/mtf/
├── context/           # Определение режимов рынка (старшие ТФ)
│   ├── builder.py
│   ├── engine.py
│   └── algorithms.py  # TRENDING_UP/DOWN, RANGING, VOLATILE
├── triggers/          # Генерация триггеров разворота (младшие ТФ)
│   ├── builder.py
│   ├── engine.py
│   └── filters.py
├── consensus/         # Взвешенная агрегация
│   ├── builder.py
│   ├── algorithms.py
│   └── veto.py        # Veto логика
├── pipeline/          # Оркестрация
│   └── orchestrator.py
└── integration/       # Сохранение результатов
    └── database_adapter.py
```

**Веса таймфреймов:**

| Timeframe | Weight | Роль |
|-----------|--------|------|
| 4H | 0.40 | Senior context |
| 1H | 0.30 | Senior context |
| 15m | 0.20 | Junior triggers |
| 5m | 0.10 | Junior triggers |

### 4. Risk Module (`src/risk/`)

Управление рисками портфеля.

```
src/risk/
├── limits/
│   ├── position_limits.py     # Max 5% per position
│   ├── daily_limits.py        # Max 3% daily loss
│   └── correlation_limits.py  # Correlated positions
├── guards/
│   ├── killswitch.py          # Emergency stop
│   └── circuit_breaker.py     # Circuit breaker pattern
└── config.py                  # Risk configuration
```

**Лимиты:**

| Лимит | Значение | Действие |
|-------|----------|----------|
| Max Position | 5% баланса | Reject order |
| Max Daily Loss | 3% баланса | Kill-switch |
| Max Total Exposure | 50% баланса | Kill-switch |
| Risk per Trade | 1-2% | Position sizing |

### 5. Market Meta (`src/market_meta/`)

Метаданные инструментов и расширенные данные.

```
src/market_meta/
├── domain/
│   ├── metadata.py        # Instrument metadata
│   └── validators.py      # Order validation
├── infrastructure/
│   ├── okx_integration.py # OKX API client
│   ├── data_loader.py     # OI, Funding, L2
│   └── aggregator.py      # Timeframe aggregation
└── cli/                   # CLI commands
```

---

## Схема базы данных

### Основные таблицы (актуальные)

```
┌─────────────────────┐
│    instruments      │
├─────────────────────┤
│ symbol (PK)         │──────┐
│ inst_type           │      │
│ tick_size           │      │
│ lot_size            │      │
│ max_leverage        │      │
│ mmr                 │      │
│ settle_ccy          │      │
└─────────────────────┘      │
                             │
        ┌────────────────────┘
        │
        ▼
┌─────────────────────┐     ┌─────────────────────┐
│   swap_ohlcv_p      │     │     indicators      │
├─────────────────────┤     ├─────────────────────┤
│ symbol (PK, FK)     │     │ symbol (PK, FK)     │
│ timeframe (PK)      │────▶│ timeframe (PK)      │
│ timestamp (PK) [ms] │     │ timestamp (PK) [ms] │
│ open                │     │ ema_12, ema_26      │
│ high                │     │ rsi_14, macd        │
│ low                 │     │ atr_14, adx         │
│ close               │     │ bb_upper/lower      │
│ volume              │     │ ... (500+ cols)     │
│ funding_rate        │     └──────────┬──────────┘
│ open_interest       │                │
└─────────────────────┘                │
                                       ▼
                          ┌─────────────────────┐
                          │   mtf_consensus     │
                          ├─────────────────────┤
                          │ symbol (PK)         │
                          │ timeframe (PK)      │
                          │ timestamp (PK)      │
                          │ context_regime      │
                          │ trigger_probability │
                          │ consensus_score     │
                          │ confidence          │
                          │ veto_flag           │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │      signals        │
                          ├─────────────────────┤
                          │ symbol (PK)         │
                          │ timestamp (PK)      │
                          │ signal              │
                          │ confidence          │
                          │ entry_price         │
                          └─────────────────────┘
```

### Таблицы vs Партиции

| Логическое имя | Физическая таблица | Примечание |
|----------------|-------------------|------------|
| OHLCV данные | `swap_ohlcv_p` | Партиционирована по месяцам |
| Индикаторы | `indicators` | НЕ партиционирована |
| Legacy OHLCV | `ohlcv` | Пустая (не используется) |
| Legacy Indicators | `indicators_p` | Пустая (не используется) |

**Важно:** Код использует модель `OHLCV` которая ссылается на таблицу `ohlcv` (пустая).
Фактические данные в `swap_ohlcv_p`. Функция `fetch_ohlcv_df` имеет fallback на `swap_ohlcv_p`.

---

## Конфигурация

### Централизованная конфигурация (`src/config/`)

```python
from src.config import get_settings

settings = get_settings()

# Database
db_url = settings.db.async_url
pool_size = settings.db.pool_size

# OKX API
if settings.okx.has_credentials:
    api_key = settings.okx.api_key.get_secret_value()

# Features
batch_size = settings.features.batch_size
min_fill_rate = settings.features.min_fill_rate

# Risk
max_leverage = settings.risk.max_leverage
daily_loss_limit = settings.risk.daily_loss_limit
```

### Структура Settings

```
Settings
├── db: DatabaseSettings
│   ├── host, port, user, password, name
│   ├── pool_size, pool_timeout
│   └── async_url, sync_url (properties)
├── okx: OKXSettings
│   ├── api_key, api_secret, passphrase (SecretStr)
│   ├── max_requests_per_second, max_retries
│   └── has_credentials (property)
├── features: FeaturesSettings
│   ├── chunk_size, batch_size, max_lookback
│   ├── min_fill_rate, volatility_normalize
│   └── parallel_workers, log_memory
├── risk: RiskSettings
│   ├── max_leverage, max_position_size_usd
│   ├── daily_loss_limit, weekly_loss_limit
│   └── enable_killswitch
├── cache: CacheSettings
├── logging: LoggingSettings
└── airflow: AirflowSettings
```

### Переменные окружения

Основные переменные в `.env`:

```bash
# Database
POSTGRES_DB=pklpo
POSTGRES_USER=pklpo_user
POSTGRES_PASSWORD=strongpassword
DB_HOST=localhost
DB_PORT=5432

# OKX API
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_API_PASSPHRASE=...

# Features
FEATURES_BATCH_SIZE=50000
FEATURES_MIN_FILL_RATE=0.5

# Logging
LOG_LEVEL=INFO
```

---

## Airflow DAGs

### Активные DAGs

| DAG ID | Schedule | Описание |
|--------|----------|----------|
| `okx_swap_ohlcv_sync_v2` | `*/5 * * * *` | Синхронизация OHLCV с OKX |
| `features_calc_short` | `*/15 * * * *` | Расчёт 24 основных индикаторов |

### features_calc_short

```
┌─────────────────────────────────────────────────────────────────┐
│                    features_calc_short DAG                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐     ┌─────────────────┐                    │
│  │  Freshness Gate │────▶│   Process All   │                    │
│  │  (check_has_    │     │    Symbols      │                    │
│  │   work_to_do)   │     │                 │                    │
│  └─────────────────┘     └────────┬────────┘                    │
│                                   │                              │
│                                   ▼                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Per Symbol (parallel, max 3)                 │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │   │
│  │  │ Get        │  │ Check new  │  │ Load OHLCV │          │   │
│  │  │ watermark  │─▶│ OHLCV?     │─▶│ + warmup   │          │   │
│  │  └────────────┘  └────────────┘  └─────┬──────┘          │   │
│  │                                        │                  │   │
│  │                                        ▼                  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐          │   │
│  │  │ UPSERT     │◀─│ compute_   │◀─│ Prepare    │          │   │
│  │  │ indicators │  │ features() │  │ DataFrame  │          │   │
│  │  └────────────┘  └────────────┘  └────────────┘          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────┐                                            │
│  │    Validate     │◀── Проверка lag после расчёта              │
│  └─────────────────┘                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Timeframes:** `1m`, `5m`, `15m`, `30m`, `1H`, `4H`, `1D`

**Indicators (24):** EMA(12,26), RSI(14), MACD, ATR(14), ADX, Bollinger Bands, etc.

### okx_swap_ohlcv_sync_v2

```
┌─────────────────────────────────────────────────────────────────┐
│                  okx_swap_ohlcv_sync_v2 DAG                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐     ┌─────────────────┐                    │
│  │  Load symbols   │────▶│   Sync candles  │                    │
│  │  from DB/file   │     │   (batch 300)   │                    │
│  └─────────────────┘     └────────┬────────┘                    │
│                                   │                              │
│                                   ▼                              │
│  ┌─────────────────┐     ┌─────────────────┐                    │
│  │  UPSERT to      │────▶│    Validate     │                    │
│  │  swap_ohlcv_p   │     │   (smoke test)  │                    │
│  └─────────────────┘     └─────────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Интеграции

### OKX Exchange

```
┌─────────────────┐
│    OKX API      │
├─────────────────┤
│ GET /market/candles       │◀── OHLCV data
│ GET /market/history-candles│◀── Historical data
│ GET /public/instruments    │◀── Instrument metadata
│ GET /public/funding-rate   │◀── Funding rates
│ GET /public/open-interest  │◀── Open Interest
└─────────────────┘
         │
         ▼
┌─────────────────┐
│  Rate Limiter   │  ← 80 req/s (public endpoints)
│  Retry/Backoff  │  ← Exponential backoff
│  Error Handler  │  ← Structured exceptions
└─────────────────┘
```

### PostgreSQL

```
┌─────────────────────────────────────────────────────────────────┐
│                      PostgreSQL 15+                              │
├─────────────────────────────────────────────────────────────────┤
│  Connection: asyncpg + SQLAlchemy 2.0 (async)                   │
│  Pool: size=10, max_overflow=20, timeout=30s                    │
│  Tables: swap_ohlcv_p (partitioned), indicators, instruments    │
│  Operations: UPSERT (ON CONFLICT DO UPDATE)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Известные особенности

### 1. Две таблицы OHLCV

- `ohlcv` - legacy, пустая (модель `OHLCV` ссылается на неё)
- `swap_ohlcv_p` - актуальная, с данными

Код `fetch_ohlcv_df` сначала пытается `ohlcv`, затем fallback на `swap_ohlcv_p`.

### 2. Timestamp форматы

| Место | Формат |
|-------|--------|
| `swap_ohlcv_p.timestamp` | Миллисекунды (int) |
| `indicators.timestamp` | Миллисекунды (int) |
| `fetch_ohlcv_df` возвращает `ts` | Секунды |
| `compute_features` ожидает `timestamp` | Миллисекунды |

### 3. Конфигурация

Старые модули (`features/config.py`, `risk/config.py`) используют обёртки над централизованной `src.config`.
Для нового кода рекомендуется `from src.config import get_settings`.

---

## CLI команды

```bash
# Features
python -m src.cli.main features --symbols BTC-USDT-SWAP --timeframes 1m 5m

# Sync candles
python -m src.cli.main swap-sync --symbols BTC-USDT-SWAP

# Migrations
python -m src.cli.main migrate

# Cleanup old data
python -m src.cli.main cleanup --days 90
```

---

## Дополнительные материалы

- [Features Module](src/features/README.md)
- [MTF System](src/mtf/README_FINAL.md)
- [Market Meta](src/market_meta/README.md)
- [Database Migrations](src/db/README.md)
- [Airflow DAGs](ops/airflow/dags/README.md)
- [Data Flow](DATA_FLOW.md)

---

**Последнее обновление:** 2026-01-15
