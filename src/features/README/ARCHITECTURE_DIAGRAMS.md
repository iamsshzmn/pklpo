# Архитектурные Диаграммы Модуля Features

## 🎨 Упрощенные визуальные диаграммы для быстрого понимания

---

## 1️⃣ High-Level Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         USERS / CLIENTS                      │
│         (Airflow, CLI, Python Scripts, Notebooks)           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                     PUBLIC API LAYER                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  compute_features(df_ohlcv, specs, available)          │  │
│  │  • Единая точка входа                                  │  │
│  │  • Валидация входных данных                            │  │
│  │  • Возврат DataFrame с индикаторами                    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                   ORCHESTRATION LAYER                        │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Batch         │  │ Streaming    │  │ Group            │  │
│  │ Processor     │  │ Calculator   │  │ Calculator       │  │
│  │               │  │              │  │                  │  │
│  │ • Process     │  │ • Chunk data │  │ • Sequential     │  │
│  │   pairs       │  │ • Overlap    │  │   groups         │  │
│  │ • Parallel    │  │ • Memory     │  │ • Batch persist  │  │
│  │   execution   │  │   efficient  │  │                  │  │
│  └───────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                   CALCULATION ENGINE                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           INDICATOR GROUPS (10 groups)                │   │
│  │                                                       │   │
│  │  overlap → ma → oscillators → volatility → volume   │   │
│  │     ↓       ↓        ↓            ↓          ↓      │   │
│  │  trend → candles → squeeze → statistics → performance│   │
│  │                                                       │   │
│  │  Total: 500+ technical indicators                    │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                  VALIDATION & QUALITY                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Pre-calc     │  │ During calc  │  │ Post-calc        │  │
│  │ Validation   │  │ Monitoring   │  │ Quality Gates    │  │
│  │              │  │              │  │                  │  │
│  │ • OHLCV      │  │ • Metrics    │  │ • Fill rate      │  │
│  │ • Timestamps │  │ • Errors     │  │ • NaN ratio      │  │
│  │ • Schema     │  │ • Memory     │  │ • Consistency    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌──────────────────────────────────────────────────────────────┐
│                   DATA PERSISTENCE                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  PostgreSQL Database (app.indicators)                │   │
│  │  • UPSERT strategy (conflict resolution)             │   │
│  │  • Batch operations (5k-10k rows)                    │   │
│  │  • NaN/Inf sanitization                              │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## 2️⃣ Data Flow Diagram

```
                    ┌─────────────────┐
                    │  Raw OHLCV Data │
                    │  (DataFrame)    │
                    └────────┬────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │  Validation     │
                    │  • Schema       │
                    │  • Timestamps   │
                    │  • Completeness │
                    └────────┬────────┘
                             │
                             ↓
        ┌────────────────────┴────────────────────┐
        │       GROUP-BASED CALCULATION           │
        │                                         │
        │  Step 1: overlap      ──────► df      │
        │  Step 2: ma           ──────► df      │
        │  Step 3: oscillators  ──────► df      │
        │  Step 4: volatility   ──────► df      │
        │  Step 5: volume       ──────► df      │
        │  Step 6: trend        ──────► df      │
        │  Step 7: candles      ──────► df      │
        │  Step 8: squeeze      ──────► df      │
        │  Step 9: statistics   ──────► df      │
        │  Step 10: performance ──────► df      │
        │                                         │
        │  After each step: Batch Persist        │
        └────────────────────┬────────────────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │  Quality Gates  │
                    │  • Fill rate    │
                    │  • NaN check    │
                    │  • Consistency  │
                    └────────┬────────┘
                             │
                             ↓
                    ┌─────────────────┐
                    │  Final Result   │
                    │  DataFrame with │
                    │  All Indicators │
                    └────────┬────────┘
                             │
                ┌────────────┴────────────┐
                ↓                         ↓
        ┌──────────────┐         ┌──────────────┐
        │ Return to    │         │ Save to      │
        │ Caller       │         │ Database     │
        └──────────────┘         └──────────────┘
```

---

## 3️⃣ Indicator Groups Dependency Graph

```
        ┌─────────────┐
        │   INPUT     │
        │   OHLCV     │
        └──────┬──────┘
               │
               ↓
        ┌─────────────┐
        │  1. overlap │  ← Base calculations
        └──────┬──────┘
               │
               ↓
        ┌─────────────┐
        │    2. ma    │  ← Moving Averages (EMA, SMA, WMA, etc.)
        └──────┬──────┘
               │
        ┌──────┴──────┐
        ↓             ↓
┌──────────────┐  ┌──────────────┐
│3. oscillators│  │4. volatility │  ← Depend on MA
│  (RSI, MACD, │  │  (BB, Keltner│
│   Stochastic)│  │   ATR)       │
└──────┬───────┘  └──────┬───────┘
       │                 │
       ↓                 ↓
┌──────────────┐  ┌──────────────┐
│  5. volume   │  │  6. trend    │  ← Can use MA + previous
│  (OBV, VWAP, │  │  (ADX, Aroon,│
│   CMF, MFI)  │  │   Ichimoku)  │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                ↓
        ┌──────────────┐
        │  7. candles  │  ← Candle patterns
        └──────┬───────┘
               │
               ↓
        ┌──────────────┐
        │  8. squeeze  │  ← Depends on BB + Keltner
        └──────┬───────┘
               │
               ↓
        ┌──────────────┐
        │9. statistics │  ← Rolling statistics
        └──────┬───────┘
               │
               ↓
        ┌──────────────┐
        │10.performance│  ← Can use all previous
        └──────┬───────┘
               │
               ↓
        ┌──────────────┐
        │    OUTPUT    │
        │  All Indicators
        └──────────────┘
```

**Ключевой принцип:** Каждая группа может использовать результаты предыдущих групп,
но не может заглядывать вперед. Это предотвращает look-ahead bias.

---

## 4️⃣ Module Dependency Graph

```
                        ┌─────────────┐
                        │   core.py   │ ← Main API
                        └──────┬──────┘
                               │
           ┌───────────────────┼───────────────────┐
           ↓                   ↓                   ↓
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │ validators  │    │   specs     │    │   models    │
    │   .py       │    │    .py      │    │    .py      │
    └─────────────┘    └─────────────┘    └─────────────┘
           │                   │  
           └───────────┬───────┘  
                       ↓  
              ┌─────────────────┐  
              │ group_calculation│  
              │       .py        │  
              └────────┬─────────┘  
                       │  
           ┌───────────┼───────────┐  
           ↓           ↓           ↓  
    ┌──────────┐ ┌──────────┐ ┌──────────┐  
    │gate_     │ │ metrics  │ │upsert_   │  
    │validation│ │   .py    │ │optimizer │  
    └──────────┘ └──────────┘ └──────────┘  
           │           │           │  
           └───────────┼───────────┘  
                       ↓  
            ┌─────────────────────┐  
            │  indicator_groups/  │  
            │  ├── ma.py          │  
            │  ├── oscillators.py │  
            │  ├── volatility.py  │  
            │  ├── volume.py      │  
            │  ├── trend.py       │  
            │  ├── squeeze.py     │  
            │  ├── candles.py     │  
            │  ├── overlap.py     │  
            │  ├── statistics.py  │  
            │  └── performance.py │  
            └─────────────────────┘  
                       │  
                       ↓  
            ┌─────────────────────┐  
            │  infrastructure/    │  
            │  ├── database.py    │  
            │  ├── db_operations  │  
            │  ├── insert_        │  
            │  │   indicators     │  
            │  └── upsert_builder │  
            └─────────────────────┘  
```

---

## 5️⃣ Streaming vs Batch Processing

### Batch Processing (Simple)

```
┌──────────────────────────────────────────────┐
│        INPUT: Complete DataFrame             │
│        (все данные в памяти)                 │
└──────────────┬───────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────┐
│   compute_features(df_complete)              │
│   • Обработка всех данных сразу              │
│   • Простой и быстрый для малых данных       │
└──────────────┬───────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────┐
│        OUTPUT: DataFrame with indicators     │
└──────────────────────────────────────────────┘
```

### Streaming Processing (Memory-Efficient)

```
┌──────────────────────────────────────────────┐
│     INPUT: Large Dataset (CSV/Database)      │
│     (слишком большой для памяти)             │
└──────────────┬───────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────┐
│          Split into Chunks                   │
│   ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐   │
│   │Chunk1│  │Chunk2│  │Chunk3│  │Chunk4│   │
│   │ 5k   │  │ 5k   │  │ 5k   │  │ 5k   │   │
│   └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘   │
└──────┼─────────┼─────────┼─────────┼────────┘
       │         │         │         │
       ↓         ↓         ↓         ↓
┌──────────────────────────────────────────────┐
│    Add Overlap (lookback period)             │
│   ┌────────┐  ┌────────┐  ┌────────┐        │
│   │Chunk1+ │  │Chunk2+ │  │Chunk3+ │        │
│   │overlap │  │overlap │  │overlap │        │
│   └───┬────┘  └───┬────┘  └───┬────┘        │
└───────┼───────────┼───────────┼──────────────┘
        │           │           │
        ↓           ↓           ↓
┌──────────────────────────────────────────────┐
│   Process Each Chunk                         │
│   compute_features(chunk_with_overlap)       │
└───────┬───────────┬───────────┬──────────────┘
        │           │           │
        ↓           ↓           ↓
┌──────────────────────────────────────────────┐
│   Remove Overlap, Keep Valid Rows            │
└───────┬───────────┬───────────┬──────────────┘
        │           │           │
        ↓           ↓           ↓
┌──────────────────────────────────────────────┐
│   Write to Parquet (streaming)               │
│   ┌──────┐  ┌──────┐  ┌──────┐              │
│   │File1 │  │File2 │  │File3 │              │
│   └──────┘  └──────┘  └──────┘              │
└──────────────┬───────────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────────┐
│   OUTPUT: Parquet files (can combine later)  │
└──────────────────────────────────────────────┘
```

---

## 6️⃣ Database Integration Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                    │
│                  (calc_indicators.py)                   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│                  READ PATH (Fetch Data)                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │  db_operations.py                                 │  │
│  │                                                   │  │
│  │  fetch_latest_ts(symbol, timeframe)              │  │
│  │    ↓                                              │  │
│  │  SELECT MAX(timestamp)                           │  │
│  │  FROM app.swap_ohlcv_p                           │  │
│  │  WHERE symbol = ? AND timeframe = ?              │  │
│  │                                                   │  │
│  │  fetch_ohlcv_df(symbol, timeframe, since_ts)     │  │
│  │    ↓                                              │  │
│  │  SELECT timestamp, open, high, low, close, vol   │  │
│  │  FROM app.swap_ohlcv_p                           │  │
│  │  WHERE timestamp > ?                             │  │
│  │  ORDER BY timestamp                              │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ↓
                  ┌──────────────┐
                  │   COMPUTE    │
                  │  FEATURES    │
                  └──────┬───────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│                 WRITE PATH (Save Results)               │
│  ┌───────────────────────────────────────────────────┐  │
│  │  insert_indicators.py                             │  │
│  │                                                   │  │
│  │  1. Sanitize NaN/Inf → NULL                      │  │
│  │  2. Build UPSERT query (upsert_builder.py)       │  │
│  │  3. Batch insert (5000-10000 rows)               │  │
│  │                                                   │  │
│  │  INSERT INTO app.indicators (...)                │  │
│  │  VALUES (?, ?, ?, ...), (?, ?, ?, ...), ...      │  │
│  │  ON CONFLICT (symbol, timeframe, timestamp)      │  │
│  │  DO UPDATE SET                                   │  │
│  │    ema_12 = EXCLUDED.ema_12,                     │  │
│  │    rsi_14 = EXCLUDED.rsi_14,                     │  │
│  │    ...                                           │  │
│  │    calculated_at = NOW()                         │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────┐
│              PostgreSQL Database                        │
│                                                         │
│  Tables:                                                │
│  • app.swap_ohlcv_p     (source OHLCV data)            │
│  • app.indicators       (calculated indicators)        │
│                                                         │
│  Indexes:                                               │
│  • PK: (symbol, timeframe, timestamp)                   │
│  • Index: (timestamp)                                   │
│  • Index: (symbol, timeframe)                           │
└─────────────────────────────────────────────────────────┘
```

---

## 7️⃣ Error Handling & Validation Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                   INPUT DATA                            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │  LEVEL 1: Schema Validation  │  ← validators.py
        │  ✓ Required columns exist    │
        │  ✓ Data types correct        │
        │  ✓ Column names valid        │
        └──────────────┬───────────────┘
                       │ PASS
                       ↓
        ┌──────────────────────────────┐
        │  LEVEL 2: Data Validation    │  ← validators.py
        │  ✓ Min rows requirement      │
        │  ✓ Value ranges valid        │
        │  ✓ No all-NaN columns        │
        └──────────────┬───────────────┘
                       │ PASS
                       ↓
        ┌──────────────────────────────┐
        │ LEVEL 3: Time Validation     │  ← time_utils.py
        │  ✓ Monotonic timestamps      │
        │  ✓ No duplicates             │
        │  ✓ Consistent format         │
        └──────────────┬───────────────┘
                       │ PASS
                       ↓
        ┌──────────────────────────────┐
        │   CALCULATION PHASE          │
        │   (with error handling)      │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │ LEVEL 4: Code Validation     │  ← code_validations.py
        │  ✓ Anomaly detection         │
        │  ✓ Outlier detection         │
        │  ✓ Shadow NaN detection      │
        └──────────────┬───────────────┘
                       │ PASS
                       ↓
        ┌──────────────────────────────┐
        │ LEVEL 5: Quality Gates       │  ← gate_validation.py
        │  ✓ Fill rate ≥ threshold     │
        │  ✓ NaN ratio ≤ threshold     │
        │  ✓ Timestamp consistency     │
        │  ✓ Value sanity checks       │
        └──────────────┬───────────────┘
                       │ PASS
                       ↓
        ┌──────────────────────────────┐
        │   VALIDATED OUTPUT           │
        └──────────────────────────────┘

        ⚠️ FAIL at any level ─────────────────┐
                                              ↓
                                    ┌─────────────────┐
                                    │  Error Handling │
                                    │  • Log error    │
                                    │  • Raise or Warn│
                                    │  • Return None  │
                                    └─────────────────┘
```

---

## 8️⃣ Metrics & Monitoring Flow

```
┌─────────────────────────────────────────────────────────┐
│              CALCULATION START                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │  start_calculation_metrics() │  ← metrics.py
        │  • Record start time         │
        │  • Log input size            │
        │  • Initialize counters       │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   INDICATOR CALCULATION      │
        │   (per group)                │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │  record_fill_rate()          │  ← metrics.py
        │  • Calculate fill rate       │
        │  • Per indicator tracking    │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │  record_quality_metrics()    │  ← metrics.py
        │  • NaN ratio                 │
        │  • Value ranges              │
        │  • Consistency checks        │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │ finish_calculation_metrics() │  ← metrics.py
        │  • Record end time           │
        │  • Calculate duration        │
        │  • Log throughput            │
        │  • Export metrics            │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   METRICS STORAGE/EXPORT     │
        │  • Logs (structured)         │
        │  • Prometheus (future)       │
        │  • Database (metadata)       │
        └──────────────────────────────┘

METRICS COLLECTED:
├── Performance
│   ├── Calculation time (per group, total)
│   ├── Throughput (rows/sec)
│   ├── Memory usage
│   └── CPU usage
├── Quality
│   ├── Fill rate per indicator
│   ├── NaN ratio
│   ├── Quality score (0-100)
│   └── Validation pass/fail
└── Business
    ├── Rows processed
    ├── Indicators calculated
    ├── Success/failure rate
    └── Error frequency
```

---

## 9️⃣ Airflow Integration Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   AIRFLOW SCHEDULER                     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   features_calc DAG          │
        │   (daily/hourly trigger)     │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   Task: calculate_features   │  ← calc_indicators.py
        └──────────────┬───────────────┘
                       │
        ┌──────────────┴───────────────┐
        ↓                              ↓
┌───────────────┐            ┌────────────────┐
│ Subtask 1:    │            │ Subtask N:     │
│ BTC/USDT-1h   │   ...      │ ETH/USDT-4h    │
└──────┬────────┘            └────────┬───────┘
       │                              │
       ↓                              ↓
┌─────────────────────────────────────────────┐
│  calculate_indicators_for_pairs()           │
│                                             │
│  For each (symbol, timeframe):             │
│  1. Fetch OHLCV data (db_operations)       │
│  2. Compute features (core.compute)        │
│  3. Insert indicators (insert_indicators)  │
│  4. Log metrics                            │
└──────────────────┬──────────────────────────┘
                   │
                   ↓
        ┌──────────────────────────────┐
        │ Task: smoke_validate_features│  ← smoke_validation.py
        │  ✓ Verify data written       │
        │  ✓ Check quality metrics     │
        │  ✓ Validate completeness     │
        └──────────────┬───────────────┘
                       │
                       ↓
        ┌──────────────────────────────┐
        │   SUCCESS / FAILURE          │
        │   • Send notifications       │
        │   • Update metadata          │
        └──────────────────────────────┘

XCOM DATA FLOW:
Task 1 ────────► [XCom] ────────► Task 2
  metrics,          │              validation
  status,           │              inputs
  row_counts        ↓
               [Airflow DB]
```

---

## 🔟 Component Interaction Matrix

```
┌──────────────┬──────┬──────┬──────┬──────┬──────┬──────┐
│  Component   │ core │ calc │group │infra │valid │indic │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ core.py      │  -   │  ○   │  ●   │  ○   │  ●   │  ●   │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ calc.py      │  ●   │  -   │  ○   │  ○   │  ○   │  ○   │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ group_calc   │  ○   │  ○   │  -   │  ○   │  ●   │  ●   │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ infra/*      │  ○   │  ○   │  ○   │  -   │  ○   │  ○   │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ validators   │  ●   │  ○   │  ●   │  ○   │  -   │  ○   │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┤
│ indicators/* │  ●   │  ○   │  ●   │  ○   │  ○   │  -   │
└──────────────┴──────┴──────┴──────┴──────┴──────┴──────┘

Legend:
● = Strong dependency (direct import, frequent use)
○ = Weak dependency (indirect, occasional use)
- = Self
```

---

## 📊 Performance Characteristics

### Memory Usage by Operation

```
┌────────────────────────────────────────────────────┐
│          MEMORY FOOTPRINT COMPARISON               │
├────────────────────────────────────────────────────┤
│                                                    │
│  Batch Processing (all data in memory):           │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 5 GB              │
│                                                    │
│  Streaming Processing (chunk by chunk):           │
│  ▓▓▓▓▓ 500 MB                                     │
│                                                    │
│  Group Calculation (sequential groups):           │
│  ▓▓▓▓▓▓▓▓ 800 MB                                  │
│                                                    │
└────────────────────────────────────────────────────┘
```

### Throughput by Strategy

```
┌────────────────────────────────────────────────────┐
│       PROCESSING THROUGHPUT (rows/second)          │
├────────────────────────────────────────────────────┤
│                                                    │
│  Simple Batch (small dataset < 100k rows):        │
│  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ 10,000 rows/s              │
│                                                    │
│  Streaming (large dataset > 1M rows):             │
│  ▓▓▓▓▓▓▓▓▓▓▓▓ 6,000 rows/s                        │
│                                                    │
│  Group Calculation (with persistence):            │
│  ▓▓▓▓▓▓▓▓▓▓ 5,000 rows/s                          │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 🎯 Key Design Patterns

### 1. Facade Pattern
```
User Code ──► core.py ──► Multiple internal modules
                (Facade)   (Hidden complexity)
```

### 2. Strategy Pattern
```
BatchProcessor ◄──┐
StreamProcessor ◄─┼── ProcessorStrategy
GroupProcessor ◄──┘
```

### 3. Pipeline Pattern
```
Input → Validate → Transform → Calculate → Validate → Output
         (Stage1)   (Stage2)   (Stage3)     (Stage4)
```

### 4. Builder Pattern
```
UpsertBuilder:
  .add_columns()
  .add_values()
  .on_conflict()
  .build() → SQL Query
```

---

**Документ создан:** 2025-10-27
**Версия:** 1.0.0
**Назначение:** Быстрая визуализация архитектуры для новых разработчиков
