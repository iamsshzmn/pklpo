# PKLPO - Data Flow и логика обработки

**Версия:** 0.2.0 | **Обновлено:** 2025-12-18

---

## Содержание

- [Общий Data Flow](#общий-data-flow)
- [Этап 1: Ingest (Загрузка данных)](#этап-1-ingest-загрузка-данных)
- [Этап 2: Features (Расчет индикаторов)](#этап-2-features-расчет-индикаторов)
- [Этап 3: MTF Analysis](#этап-3-mtf-analysis)
- [Этап 4: Signal Generation](#этап-4-signal-generation)
- [Этап 5: Position Sizing](#этап-5-position-sizing)
- [Временные зависимости](#временные-зависимости)

---

## Общий Data Flow

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            PKLPO DATA PIPELINE                              │
└────────────────────────────────────────────────────────────────────────────┘

     OKX API                                                     PostgreSQL
        │                                                             │
        ▼                                                             │
┌───────────────┐                                                     │
│    INGEST     │ ─────────────────────────────────────────────────▶ │
│  (Candles)    │        OHLCV → ohlcv_p                             │
└───────┬───────┘                                                     │
        │                                                             │
        ▼                                                             │
┌───────────────┐                                                     │
│   FEATURES    │ ─────────────────────────────────────────────────▶ │
│  (500+ ind.)  │        Indicators → indicators_p                   │
└───────┬───────┘                                                     │
        │                                                             │
        ├─────────────────────────────┐                               │
        ▼                             ▼                               │
┌───────────────┐             ┌───────────────┐                       │
│  MTF CONTEXT  │             │ MTF TRIGGERS  │                       │
│  (Regime)     │             │ (Reversal)    │                       │
└───────┬───────┘             └───────┬───────┘                       │
        │                             │                               │
        └──────────┬──────────────────┘                               │
                   ▼                                                  │
           ┌───────────────┐                                          │
           │  CONSENSUS    │ ────────────────────────────────────────▶│
           │  (Aggregation)│        mtf_consensus                     │
           └───────┬───────┘                                          │
                   │                                                  │
                   ▼                                                  │
           ┌───────────────┐                                          │
           │   SIGNALS     │ ────────────────────────────────────────▶│
           │  (LONG/SHORT) │        signals, signals_detailed         │
           └───────┬───────┘                                          │
                   │                                                  │
                   ▼                                                  │
           ┌───────────────┐                                          │
           │  RISK CHECK   │                                          │
           │  (Limits)     │                                          │
           └───────┬───────┘                                          │
                   │                                                  │
                   ▼                                                  │
           ┌───────────────┐                                          │
           │  POSITIONS    │ ────────────────────────────────────────▶│
           │  (Sizing)     │        positions                         │
           └───────────────┘                                          │
```

---

## Этап 1: Ingest (Загрузка данных)

### Источники данных

| Источник | Endpoint | Данные | Периодичность |
|----------|----------|--------|---------------|
| OKX Candles | `/api/v5/market/candles` | OHLCV | 1 min |
| OKX Instruments | `/api/v5/public/instruments` | Metadata | 1 hour |
| OKX Funding | `/api/v5/public/funding-rate` | Funding | 8 hours |
| OKX OI | `/api/v5/public/open-interest` | Open Interest | 5 min |

### Логика загрузки свечей

```python
# Псевдокод загрузки
async def sync_candles(symbol: str, timeframe: str) -> int:
    # 1. Получить последний timestamp из БД
    last_ts = await db.get_last_timestamp(symbol, timeframe)

    # 2. Запросить новые свечи с OKX
    candles = await okx.get_candles(
        symbol=symbol,
        timeframe=timeframe,
        after=last_ts,
        limit=300  # Max per request
    )

    # 3. Валидация данных
    validated = validate_ohlcv(candles)

    # 4. UPSERT в БД (идемпотентно)
    rows = await db.upsert_candles(validated)

    return rows
```

### Валидация OHLCV

```
Проверки:
├── high >= max(open, close)
├── low <= min(open, close)
├── volume >= 0
├── timestamp монотонно возрастает
└── нет пропусков в последовательности
```

---

## Этап 2: Features (Расчет индикаторов)

### Группы индикаторов

| Группа | Количество | Примеры |
|--------|------------|---------|
| Moving Averages | 50+ | EMA, SMA, WMA, DEMA, TEMA |
| Oscillators | 30+ | RSI, Stochastic, CCI, Williams %R |
| Volatility | 20+ | ATR, Bollinger, Keltner, Donchian |
| Volume | 15+ | OBV, VWAP, MFI, A/D |
| Trend | 25+ | ADX, MACD, Aroon, Parabolic SAR |
| Candles | 60+ | Doji, Hammer, Engulfing, etc. |
| Squeeze | 5+ | TTM Squeeze, Momentum |
| Statistics | 20+ | StdDev, Variance, Correlation |
| Performance | 10+ | Sharpe, Sortino, Max DD |

### Порядок расчета (без look-ahead)

```
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE CALCULATION ORDER                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Base Indicators (no dependencies)                           │
│     ├── SMA, EMA (только OHLCV)                                 │
│     ├── ATR (только OHLCV)                                      │
│     └── Volume indicators                                        │
│                                                                  │
│  2. Derived Indicators (depend on base)                         │
│     ├── MACD (depend on EMA)                                    │
│     ├── Bollinger Bands (depend on SMA, StdDev)                 │
│     └── RSI (depend on close changes)                           │
│                                                                  │
│  3. Complex Indicators (depend on derived)                      │
│     ├── ADX (depend on +DI, -DI)                                │
│     ├── Squeeze (depend on BB, KC, ATR)                         │
│     └── Composite scores                                         │
│                                                                  │
│  4. Normalization (optional)                                     │
│     └── Volatility-adjusted values                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Пример расчета RSI

```python
def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    """
    delta = close.diff()

    gain = delta.where(delta > 0, 0)
    loss = (-delta).where(delta < 0, 0)

    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi
```

### Quality Gates

```
┌─────────────────────────────────────────────────────────────────┐
│                      QUALITY GATES                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Gate 1: NaN Ratio                                               │
│  ├── Max NaN ratio: 5% (после warmup периода)                   │
│  └── Action: FAIL если превышено                                │
│                                                                  │
│  Gate 2: Value Ranges                                            │
│  ├── RSI: 0-100                                                  │
│  ├── ADX: 0-100                                                  │
│  └── Action: WARN если выход за границы                         │
│                                                                  │
│  Gate 3: Monotonicity                                            │
│  ├── Timestamp должен быть монотонным                           │
│  └── Action: FAIL если нарушено                                 │
│                                                                  │
│  Gate 4: Fill Rate                                               │
│  ├── Min fill rate: 95%                                          │
│  └── Action: WARN если ниже                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Этап 3: MTF Analysis

### Context Module (Определение режима)

```
┌─────────────────────────────────────────────────────────────────┐
│                    REGIME DETECTION                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: Indicators на старшем ТФ (15m, 1H, 4H)                  │
│                                                                  │
│  Алгоритмы:                                                      │
│  ├── ADX-based: ADX > 25 → TRENDING, else RANGING               │
│  ├── BB Width: Narrow → SQUEEZE, Wide → VOLATILE                │
│  └── EMA Alignment: 20 > 50 > 200 → UPTREND                     │
│                                                                  │
│  Output:                                                         │
│  ├── regime: TRENDING_UP | TRENDING_DOWN | RANGING | VOLATILE   │
│  ├── strength: 0.0 - 1.0                                         │
│  └── confidence: 0.0 - 1.0                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Triggers Module (Сигналы разворота)

```
┌─────────────────────────────────────────────────────────────────┐
│                   TRIGGER DETECTION                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: Indicators на младшем ТФ (1m, 5m)                       │
│                                                                  │
│  Алгоритмы:                                                      │
│  ├── RSI Divergence: Price HH + RSI LH → Bearish                │
│  ├── MACD Cross: Signal line crossover                          │
│  ├── Candlestick: Reversal patterns                             │
│  └── Volume Spike: Abnormal volume                              │
│                                                                  │
│  Output:                                                         │
│  ├── trigger_type: BULLISH | BEARISH | NEUTRAL                  │
│  ├── probability: 0.0 - 1.0                                      │
│  └── source: [rsi_div, macd_cross, candle, volume]              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Consensus Module (Агрегация)

```
┌─────────────────────────────────────────────────────────────────┐
│                   CONSENSUS CALCULATION                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Формула:                                                        │
│  consensus_score = Σ(weight_i × signal_i × confidence_i)        │
│                                                                  │
│  Веса по таймфреймам:                                            │
│  ├── 4H: 0.4 (старший контекст)                                 │
│  ├── 1H: 0.3                                                     │
│  ├── 15m: 0.2                                                    │
│  └── 5m: 0.1 (триггеры)                                         │
│                                                                  │
│  Veto Logic:                                                     │
│  ├── Если старший ТФ STRONG противоположный → VETO              │
│  └── Если volatility > threshold → REDUCE confidence            │
│                                                                  │
│  Output:                                                         │
│  ├── score: -1.0 (STRONG SHORT) ... +1.0 (STRONG LONG)          │
│  ├── confidence: 0.0 - 1.0                                       │
│  └── veto_applied: bool                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Этап 4: Signal Generation

### Правила генерации сигналов

```
┌─────────────────────────────────────────────────────────────────┐
│                    SIGNAL RULES                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LONG Signal:                                                    │
│  ├── consensus_score > +0.5                                      │
│  ├── confidence > 0.6                                            │
│  ├── context_regime != STRONG_DOWNTREND                         │
│  └── no_veto_applied                                             │
│                                                                  │
│  SHORT Signal:                                                   │
│  ├── consensus_score < -0.5                                      │
│  ├── confidence > 0.6                                            │
│  ├── context_regime != STRONG_UPTREND                           │
│  └── no_veto_applied                                             │
│                                                                  │
│  FLAT (No Signal):                                               │
│  ├── |consensus_score| <= 0.5                                    │
│  ├── OR confidence <= 0.6                                        │
│  └── OR veto_applied                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Структура сигнала

```python
@dataclass
class Signal:
    symbol: str
    timestamp: datetime
    timeframe: str

    # Основные поля
    signal: Literal["LONG", "SHORT", "FLAT"]
    confidence: float  # 0.0 - 1.0

    # Цены
    entry_price: float
    stop_loss: float
    take_profit: float

    # Метаданные
    consensus_score: float
    context_regime: str
    trigger_sources: list[str]

    # Timestamps
    created_at: datetime
    expires_at: datetime  # Сигнал валиден N баров
```

---

## Этап 5: Position Sizing

### Формула расчета размера позиции

```
┌─────────────────────────────────────────────────────────────────┐
│                  POSITION SIZING FORMULA                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Risk Amount (сколько готовы потерять)                       │
│     risk_amount = balance × risk_percent                         │
│     Пример: $10,000 × 1% = $100                                 │
│                                                                  │
│  2. Stop Distance (расстояние до стопа)                         │
│     stop_distance = entry_price × stop_percent                   │
│     ИЛИ                                                          │
│     stop_distance = ATR × atr_multiplier                         │
│     Пример: $50,000 × 2% = $1,000                               │
│                                                                  │
│  3. Position Size (размер позиции)                              │
│     position_size = risk_amount / stop_distance                  │
│     Пример: $100 / $1,000 = 0.1 BTC                             │
│                                                                  │
│  4. Leverage Check                                               │
│     required_margin = position_value / leverage                  │
│     Проверка: required_margin <= available_balance              │
│                                                                  │
│  5. Liquidation Check                                            │
│     liq_price = entry × (1 - 1/leverage + mmr)                  │
│     Проверка: |liq_price - entry| > |stop - entry|              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Пример расчета

```
Входные данные:
├── Balance: $10,000
├── Risk per trade: 1%
├── Symbol: BTC-USDT-SWAP
├── Entry price: $50,000
├── Stop method: ATR × 2
├── ATR(14): $500
├── Max leverage: 50x
├── MMR: 0.4%

Расчет:
├── Risk amount: $10,000 × 1% = $100
├── Stop distance: $500 × 2 = $1,000 (2%)
├── Position size: $100 / $1,000 = 0.1 BTC
├── Position value: 0.1 × $50,000 = $5,000
├── Required margin (10x): $5,000 / 10 = $500
├── Liquidation price (10x): $50,000 × (1 - 0.1 + 0.004) = $45,200
├── Stop loss price: $50,000 - $1,000 = $49,000
└── Check: $49,000 > $45,200 ✓ (стоп сработает раньше ликвидации)

Итог:
├── Size: 0.1 BTC
├── Entry: $50,000
├── Stop: $49,000
├── Target: $52,000 (R:R = 1:2)
└── Risk: $100 (1% от баланса)
```

---

## Временные зависимости

### Расписание Airflow DAGs

```
┌─────────────────────────────────────────────────────────────────┐
│                    AIRFLOW SCHEDULE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Every 1 minute:                                                 │
│  └── okx_swap_ohlcv_sync                                        │
│      ├── Sync 1m candles                                         │
│      └── Sync 5m candles                                         │
│                                                                  │
│  Every 5 minutes:                                                │
│  └── features_calc                                               │
│      ├── Calculate indicators for 1m, 5m                        │
│      └── Run quality gates                                       │
│                                                                  │
│  Every 15 minutes:                                               │
│  └── mtf_analysis                                                │
│      ├── Context detection                                       │
│      ├── Trigger detection                                       │
│      └── Consensus calculation                                   │
│                                                                  │
│  Every 15 minutes (offset +2min):                               │
│  └── signal_generation                                           │
│      ├── Generate signals                                        │
│      └── Send alerts                                             │
│                                                                  │
│  Every 5 minutes:                                                │
│  └── market_data_ext_sync                                        │
│      ├── Sync Open Interest                                      │
│      ├── Sync Funding Rates                                      │
│      └── Sync Long/Short Ratio                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Зависимости между этапами

```
                    ┌─────────────────┐
                    │   ohlcv_sync    │
                    │   (1 min)       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  features_calc  │
                    │   (5 min)       │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
     │mtf_context  │ │mtf_triggers │ │market_data  │
     │  (15 min)   │ │  (15 min)   │ │  (5 min)    │
     └──────┬──────┘ └──────┬──────┘ └─────────────┘
            │               │
            └───────┬───────┘
                    ▼
           ┌─────────────────┐
           │  mtf_consensus  │
           │   (15 min)      │
           └────────┬────────┘
                    │
                    ▼
           ┌─────────────────┐
           │signal_generation│
           │   (15 min)      │
           └─────────────────┘
```

---

## Дополнительные материалы

- [Architecture Overview](./ARCHITECTURE.md)
- [Features Module](../src/features/README.md)
- [MTF System](../src/mtf/README_FINAL.md)
- [Positions Module](../src/positions/README.md)

---

**Последнее обновление:** 2025-12-18
