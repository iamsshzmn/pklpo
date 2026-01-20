# MTF Chain — Multi-Timeframe Analysis Module

> **Multi-Timeframe Chain Analysis** — расширенная система анализа рынка на основе агрегации данных с различных таймфреймов для генерации торговых сигналов LONG/SHORT/FLAT.

## 🎯 Назначение

MTF модуль создает **самостоятельную систему анализа**, которая:
- Агрегирует данные с 9 таймфреймов (1M → 1m)
- Применяет ролевую логику для каждого TF
- Генерирует сигналы для 3 горизонтов торговли
- Работает изолированно от существующих систем
- Интегрируется с модулями позиций и скоринга

## 🏗️ Архитектура

### Два режима работы

#### 1. **Базовая система** (legacy)
```
features.py → aggregator.py → trigger.py → combinations.py → writer.py
```
- Простая агрегация 1D/4H + 15m/5m
- Результат в `position_calculations`
- CLI: `src.mtf.cli`

#### 2. **Расширенная система** (новый стандарт)
```
etl/context_loader.py → etl/trigger_loader.py → etl/consensus_writer.py
```
- Полная MTF цепочка с 9 таймфреймами
- Собственная схема `mtf.*` в БД
- CLI: `src.mtf.cli_expanded`

## 📊 Таблица ролей таймфреймов

| TF | Роль | Назначение | Вес в горизонтах |
|---|---|---|---|
| **1M** | Super-Context | Фильтр экстремальных направлений | Week: 30% |
| **1W** | Macro | Подтверждение месячного фона | Swing: 20%, Week: 30% |
| **1D** | Context-Trend | Основное направление | All: 40-50% |
| **4H** | Phase | Фаза тренда | Intraday: 30%, Swing: 30% |
| **1H** | Bridge | Сглаживание конфликтов | Context only |
| **15m** | Context+Trigger | Контекст + Основной вход | Intraday: 20%, Swing: 10% |
| **5m** | Trigger-Accel | Тайминг и ускорение | All: 30% weight |
| **1m** | Micro-Filter | Ликвидность/шум | Filter only |

## 🗄️ Структура базы данных

### Схема `mtf`

```sql
-- Контекстные данные (1M, 1W, 1D, 4H, 1H)
CREATE TABLE mtf.context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    score NUMERIC,           -- trend score [-1..1]
    valid BOOLEAN,           -- |score| >= threshold
    regime TEXT,             -- trend_bull/bear, range_bull/bear
    meta JSONB,              -- исходные индикаторы
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Триггерные данные (15m, 5m, 1m)
CREATE TABLE mtf.triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    p_up NUMERIC,            -- вероятность роста
    p_down NUMERIC,          -- вероятность падения
    accel SMALLINT,          -- ускорение (-1/0/+1)
    micro_ok BOOLEAN,        -- микро-фильтр (1m)
    features JSONB,          -- триггерные индикаторы
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Финальные решения по горизонтам
CREATE TABLE mtf.consensus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,   -- intraday/swing/week
    ts TIMESTAMPTZ NOT NULL,
    side SMALLINT NOT NULL,  -- -1/0/+1 (SHORT/FLAT/LONG)
    score NUMERIC NOT NULL,  -- сила сигнала [0..1]
    input_data JSONB NOT NULL, -- все входные данные
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Представления для анализа

```sql
-- Последние решения по символам
CREATE VIEW mtf.latest_consensus AS
SELECT DISTINCT ON (symbol, horizon) *
FROM mtf.consensus
ORDER BY symbol, horizon, ts DESC;

-- Топ кандидаты по горизонтам
CREATE VIEW mtf.top_intraday AS
SELECT * FROM mtf.latest_consensus
WHERE horizon='intraday' AND side<>0
ORDER BY score DESC LIMIT 50;

CREATE VIEW mtf.top_swing AS
SELECT * FROM mtf.latest_consensus
WHERE horizon='swing' AND side<>0
ORDER BY score DESC LIMIT 50;

CREATE VIEW mtf.top_week AS
SELECT * FROM mtf.latest_consensus
WHERE horizon='week' AND side<>0
ORDER BY score DESC LIMIT 50;
```

## 🚀 Быстрый старт

### 1. Установка

```bash
# Создание схемы и таблиц
python src/db/migrate_create_mtf_expanded.py

# Проверка установки
python test_mtf_expanded.py
```

### 2. Запуск полного pipeline

```bash
# Для всех символов
python -m src.mtf.cli_expanded pipeline

# Для конкретного символа
python -m src.mtf.cli_expanded pipeline --symbol BTC-USDT

# С указанием горизонтов
python -m src.mtf.cli_expanded pipeline --horizons intraday,swing,week
```

### 3. Просмотр результатов

```bash
# Топ LONG сигналы intraday
python -m src.mtf.cli_expanded candidates --horizon intraday --side long

# Топ SHORT сигналы swing с высоким score
python -m src.mtf.cli_expanded candidates --horizon swing --side short --min-score 0.7

# Детали по символу
python -m src.mtf.cli_expanded details --symbol BTC-USDT
```

## ⚙️ Поэтапная обработка

### Этап 1: Загрузка контекста
```bash
# Загрузить контекстные данные для всех символов
python -m src.mtf.cli_expanded context --all

# Для конкретного символа
python -m src.mtf.cli_expanded context --symbol BTC-USDT
```

### Этап 2: Загрузка триггеров
```bash
# Загрузить триггерные данные
python -m src.mtf.cli_expanded triggers --all

# Для конкретного символа
python -m src.mtf.cli_expanded triggers --symbol BTC-USDT
```

### Этап 3: Расчет консенсуса
```bash
# Рассчитать решения для всех горизонтов
python -m src.mtf.cli_expanded consensus --all --horizons intraday,swing,week

# Для конкретного горизонта
python -m src.mtf.cli_expanded consensus --symbol BTC-USDT --horizons intraday
```

## 🧮 Алгоритмы

### 1. Расчет Context Score

```python
def calculate_trend_score(indicators):
    # EMA тренд
    ema_trend = math.tanh((ema21 - ema55) / ema55 * 10)

    # ADX сила тренда
    adx_factor = min(adx14 / 100.0, 1.0)

    # Волатильность (ATR)
    vol_factor = min(atr14 / 0.01, 2.0)

    # Итоговый score
    score = ema_trend * adx_factor * vol_factor
    return max(-1.0, min(1.0, score))
```

### 2. Весовые формулы по горизонтам

```python
# Intraday (внутридневной)
context_intraday = 0.5 * score_1D + 0.3 * score_4H + 0.2 * score_15m

# Swing (1-3 дня)
context_swing = 0.4 * score_1D + 0.3 * score_4H + 0.2 * score_1W + 0.1 * score_15m

# Week (недельный)
context_week = 0.4 * score_1D + 0.3 * score_1W + 0.3 * score_1M
```

### 3. Правила принятия решений

#### Intraday
- ✅ `bias_core ≠ neutral`
- ✅ `p15 ≥ 0.60`
- ✅ `p5 ≥ 0.55` или `accel_5m == ±1`
- ✅ `micro_ok == true`

#### Swing (2-3 дня)
- ✅ `bias_swing ≠ neutral`
- ✅ `p15 ≥ 0.62`
- ✅ Подтверждение N=2 закрытия 15m
- ⚠️ `micro_ok` не обязателен

#### Week
- ✅ `bias_week ≠ neutral`
- ✅ `p15 ≥ 0.65`
- ✅ Отсутствие сильных конфликтов на 4H

### 4. Расчет силы сигнала

```python
def calculate_strength(context_score, trigger_prob, volatility, liquidity, risk):
    strength = (
        0.4 * abs(context_score) +      # Контекст
        0.4 * trigger_prob +            # Триггер
        0.1 * volatility +              # Волатильность
        0.1 * liquidity -               # Ликвидность
        0.1 * risk                      # Риск
    )
    return max(0.0, min(1.0, strength))
```

## 🔗 Интеграция

### С модулем позиций

```python
from src.positions.calculator_mtf import MTFEnhancedPositionCalculator

calculator = MTFEnhancedPositionCalculator()
result = await calculator.calculate_position_with_mtf(
    position_data,
    use_mtf=True,
    mtf_weight=0.3
)
```

### Со scoring engine

```python
from src.scoring_engine.compute_mtf import MTFEnhancedScoringEngine

scoring_engine = MTFEnhancedScoringEngine()
score_result = await scoring_engine.compute_score_with_mtf(
    "BTC-USDT",
    "1m",
    timestamp,
    use_mtf=True
)
```

### Программный доступ

```python
from src.mtf.integrator import MTFIntegrator

mtf = MTFIntegrator()
signals = await mtf.get_latest_signals("BTC-USDT", "intraday")
```

## 📈 Примеры запросов

### Самые сильные сигналы

```sql
-- Топ LONG сигналы с высоким контекстом
SELECT symbol, ts, side, score,
       input_data->>'context_score' as context_score
FROM mtf.consensus
WHERE side = 1
  AND (input_data->>'context_score')::numeric >= 0.5
  AND input_data->>'micro_ok' = 'true'
ORDER BY score DESC, ts DESC
LIMIT 20;
```

### Лучшие SHORT с высоким ADX

```sql
-- Топ SHORT сигналы с подтверждением ADX
SELECT c.*, i.adx14
FROM mtf.top_swing c
LEFT JOIN LATERAL (
    SELECT adx14 FROM indicators i
    WHERE i.symbol = c.symbol AND i.timeframe = '4H'
    ORDER BY i.ts DESC LIMIT 1
) i ON TRUE
WHERE c.side = -1 AND i.adx14 >= 25
ORDER BY c.score DESC;
```

### Анализ конфликтов TF

```sql
-- Символы с конфликтами на разных TF
SELECT symbol,
       context_1d.score as score_1d,
       context_4h.score as score_4h,
       context_1h.score as score_1h
FROM mtf.context context_1d
JOIN mtf.context context_4h ON context_1d.symbol = context_4h.symbol
JOIN mtf.context context_1h ON context_1d.symbol = context_1h.symbol
WHERE context_1d.timeframe = '1Dutc'
  AND context_4h.timeframe = '4H'
  AND context_1h.timeframe = '1H'
  AND (
    (context_1d.score > 0 AND context_4h.score < 0) OR
    (context_1d.score < 0 AND context_4h.score > 0)
  )
ORDER BY ABS(context_1d.score) DESC;
```

## ⚙️ Настройка параметров

### Пороги валидности

```python
VALIDITY_THRESHOLDS = {
    "1Mutc": 0.4,   # Более строгий для месячного
    "1Wutc": 0.35,  # Строгий для недельного
    "1Dutc": 0.3,   # Стандартный для дневного
    "4H": 0.3,      # Стандартный для 4-часового
    "1H": 0.25      # Менее строгий для часового
}
```

### Веса горизонтов

```python
HORIZON_WEIGHTS = {
    "intraday": {
        "1Dutc": 0.6,
        "4H": 0.4
    },
    "swing": {
        "1Dutc": 0.5,
        "4H": 0.3,
        "1Wutc": 0.2
    },
    "week": {
        "1Dutc": 0.4,
        "1Wutc": 0.3,
        "1Mutc": 0.3
    }
}
```

## 📊 Мониторинг

### Проверка состояния

```bash
# Проверка данных индикаторов
python check_indicators_data.py

# Проверка MTF таблиц
python -m src.mtf.cli_expanded status

# Статистика по сигналам
python -m src.mtf.cli_expanded stats
```

### Логирование

```python
import logging
logging.getLogger('src.mtf').setLevel(logging.INFO)
```

## 🔧 Расширение

### Добавление новых индикаторов

1. Обновить `context_loader.py`:
```python
# Добавить новые колонки в запрос
query = text("""
    SELECT timeframe, ts, ema21, ema_55, adx14, atr14,
           sma50, sma200, rsi14, macd, macd_signal,
           NEW_INDICATOR  -- добавить новый индикатор
    FROM indicators
    WHERE symbol = :symbol
    AND timeframe = ANY(:timeframes)
    ORDER BY timeframe, ts DESC
""")

# Обновить расчет score
def _calculate_trend_score(self, indicators):
    # ... существующий код ...
    new_factor = self._calculate_new_factor(indicators.get("NEW_INDICATOR"))
    score = ema_trend * adx_factor * vol_factor * new_factor
    return max(-1.0, min(1.0, score))
```

### Создание новых горизонтов

1. Обновить `consensus_writer.py`:
```python
HORIZON_WEIGHTS = {
    # ... существующие горизонты ...
    "monthly": {
        "1Mutc": 0.5,
        "1Wutc": 0.3,
        "1Dutc": 0.2
    }
}
```

### Кастомизация алгоритмов

```python
# Переопределение в наследнике
class CustomContextLoader(ContextLoader):
    def _calculate_trend_score(self, indicators):
        # Ваша логика расчета
        pass

    def _determine_regime(self, indicators, score):
        # Ваша логика определения режима
        pass
```

## 📚 Документация

- **[README_EXPANDED.md](README_EXPANDED.md)** - Подробная документация расширенной системы
- **[QUICKSTART.md](QUICKSTART.md)** - Быстрый старт и примеры
- **[INTEGRATION_README.md](INTEGRATION_README.md)** - Документация по интеграции
- **[test_mtf_expanded.py](../../test_mtf_expanded.py)** - Тесты системы

## 🐛 Отладка

### Частые проблемы

1. **"Нет данных индикаторов"**
   ```bash
   # Проверить доступность данных
   python check_indicators_data.py
   ```

2. **"Column does not exist"**
   ```bash
   # Проверить структуру таблицы indicators
   python check_indicators_structure.py
   ```

3. **"Invalid timestamp"**
   ```bash
   # Проверить формат timestamp
   python debug_context_loader.py
   ```

### Логи отладки

```bash
# Включить подробные логи
export LOG_LEVEL=DEBUG
python -m src.mtf.cli_expanded pipeline --symbol BTC-USDT
```

## 🤝 Вклад в развитие

1. Создайте feature branch
2. Добавьте тесты для новой функциональности
3. Обновите документацию
4. Создайте pull request

---

**MTF Chain** — мощная система анализа рынка, объединяющая данные с 9 таймфреймов для генерации точных торговых сигналов. 🚀
