# Контракт данных: market_data_ext

> Версия: 1.0.0
> Дата: 2025-12-18
> Статус: DRAFT

---

## 1. Источник истины для баров

**Выбор:** `swap_ohlcv_p` для всех таймфреймов (1m, 5m, 15m, 1H).

**Правила:**
- Нормализовать и агрегировать можно только по тем `bar_ts`, которые реально существуют в `swap_ohlcv_p`
- Если нет бара в `swap_ohlcv_p` для минуты — в ext тоже не должно появляться записи
- Канонический ключ: `(symbol, bar_ts, timeframe)`
- `bar_ts` — начало периода (округление вниз)

---

## 2. Схема данных

### 2.1 Raw-слой: `market_data_ext_raw`

Хранит сырые данные от OKX без трансформации.

```sql
CREATE TABLE market_data_ext_raw (
    symbol      TEXT NOT NULL,
    data_type   TEXT NOT NULL CHECK (data_type IN ('funding', 'oi', 'l2')),
    ts          TIMESTAMPTZ NOT NULL,
    payload     JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source      TEXT NOT NULL DEFAULT 'okx',

    PRIMARY KEY (symbol, data_type, ts)
);

-- Индекс для выборки по времени
CREATE INDEX idx_raw_ts ON market_data_ext_raw (ts);
CREATE INDEX idx_raw_data_type_symbol_ts ON market_data_ext_raw (data_type, symbol, ts);
```

**Payload примеры:**

```json
// funding
{"fundingRate": "0.0001", "fundingTime": "1702900800000", "instId": "BTC-USDT-SWAP"}

// oi
{"oi": "12345.67", "oiCcy": "12345.67", "ts": "1702900800000", "instId": "BTC-USDT-SWAP"}

// l2
{"bids": [["42000.5", "1.5", "0", "3"], ...], "asks": [...], "ts": "1702900800000"}
```

### 2.2 Normalized-слой: `market_data_ext`

Данные, нормализованные к сетке баров OHLCV.

```sql
CREATE TABLE market_data_ext (
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,  -- '1m', '5m', '15m', '1H'
    bar_timestamp   TIMESTAMPTZ NOT NULL,

    -- Funding
    funding_rate    NUMERIC(10, 8),
    funding_ts      TIMESTAMPTZ,

    -- Open Interest
    open_interest   NUMERIC(20, 8),
    oi_ts           TIMESTAMPTZ,

    -- L2 признаки
    bid_imbalance   NUMERIC(10, 6),  -- доля bid объёма (0-1)
    ask_imbalance   NUMERIC(10, 6),  -- доля ask объёма (0-1)
    spread_bps      NUMERIC(10, 2),  -- спред в базисных пунктах
    l2_ts           TIMESTAMPTZ,

    -- Трассировка
    algo_version    TEXT NOT NULL,
    run_id          TEXT NOT NULL,
    params_hash     TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (symbol, timeframe, bar_timestamp)
);

CREATE INDEX idx_ext_symbol_ts ON market_data_ext (symbol, bar_timestamp);
```

### 2.3 Sync State (watermark)

```sql
CREATE TABLE sync_state (
    pipeline    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    data_type   TEXT NOT NULL,
    last_ts     TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (pipeline, symbol, data_type)
);
```

---

## 3. Правила нормализации к 1m

### 3.1 Общее правило

- Целевая сетка минут: только те `bar_ts`, которые есть в `swap_ohlcv_p` для `timeframe='1m'`
- Метод: **Last Known Value (LKV)** на конец минуты

### 3.2 Funding Rate

```
Для минуты m (bar_ts = начало минуты):
  funding_rate = последнее значение с ts <= m + 59.999s
  funding_ts   = ts выбранного события

Если значений до конца минуты нет → NULL
```

### 3.3 Open Interest

```
Для минуты m:
  open_interest = последнее значение с ts <= m + 59.999s
  oi_ts         = ts выбранного события

Если значений до конца минуты нет → NULL
```

### 3.4 L2 признаки

```
Для минуты m:
  Берём последний снимок с ts <= m + 59.999s

  Из payload вычисляем:
    bid_volume = sum(size) по всем bids
    ask_volume = sum(size) по всем asks
    total = bid_volume + ask_volume

    bid_imbalance = bid_volume / total  (или 0.5 если total=0)
    ask_imbalance = ask_volume / total  (или 0.5 если total=0)
    spread_bps    = (best_ask - best_bid) / mid_price * 10000
    l2_ts         = ts снимка
```

---

## 4. Правила агрегации 1m → 5m/15m/1H

### 4.1 Сетка агрегатов

Агрегировать только по тем `bar_ts`, которые существуют в `swap_ohlcv_p` для целевого таймфрейма.

### 4.2 Funding / OI

**Метод: LAST** — значение на последней минуте окна.

```
Для 5m-бара [00:00, 00:05):
  funding_rate  = funding_rate из 1m-бара 00:04
  open_interest = open_interest из 1m-бара 00:04
```

### 4.3 L2 признаки

**Метод: LAST** — значение на последней минуте окна.

```
Для 5m-бара [00:00, 00:05):
  bid_imbalance = bid_imbalance из 1m-бара 00:04
  ask_imbalance = ask_imbalance из 1m-бара 00:04
  spread_bps    = spread_bps из 1m-бара 00:04
```

---

## 5. Проверки качества

### 5.1 Coverage 1m

```sql
-- Ожидаемое количество записей
SELECT COUNT(*) as expected
FROM swap_ohlcv_p
WHERE timeframe = '1m'
  AND ts BETWEEN :start AND :end;

-- Фактическое количество
SELECT COUNT(*) as actual
FROM market_data_ext
WHERE timeframe = '1m'
  AND bar_timestamp BETWEEN :start AND :end;

-- Coverage = actual / expected
```

### 5.2 Fill Rate по полям

```sql
SELECT
    symbol,
    COUNT(*) as total,
    COUNT(funding_rate) * 100.0 / COUNT(*) as funding_fill_pct,
    COUNT(open_interest) * 100.0 / COUNT(*) as oi_fill_pct,
    COUNT(spread_bps) * 100.0 / COUNT(*) as l2_fill_pct
FROM market_data_ext
WHERE timeframe = '1m'
  AND bar_timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY symbol;
```

### 5.3 Lag

```sql
SELECT
    symbol,
    MAX(bar_timestamp) as last_bar,
    NOW() - MAX(bar_timestamp) as lag
FROM market_data_ext
WHERE timeframe = '1m'
GROUP BY symbol
HAVING NOW() - MAX(bar_timestamp) > INTERVAL '5 minutes';
```

---

## 6. Трассировка

Каждая запись содержит:

| Поле | Описание | Пример |
|------|----------|--------|
| `algo_version` | Версия алгоритма нормализации | `"1.0.0"` |
| `run_id` | ID запуска Airflow | `"manual__2025-12-18T10:00:00"` |
| `params_hash` | SHA256 от параметров | `"a1b2c3..."` |
| `updated_at` | Время последнего обновления | `2025-12-18 10:05:00+00` |

---

## 7. Идемпотентность

- Все операции записи — **UPSERT** по PK
- Повторный запуск с теми же данными не создаёт дубликатов
- При изменении `algo_version` или `params_hash` — перезапись с новыми значениями

---

## Changelog

| Версия | Дата | Изменения |
|--------|------|-----------|
| 1.0.0 | 2025-12-18 | Начальная версия контракта |
