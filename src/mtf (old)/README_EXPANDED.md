# MTF Chain — Расширенная логика

## Обзор

Расширенная MTF (Multi-Timeframe) система предоставляет комплексный анализ рынка на основе данных с разных таймфреймов. Система работает изолированно от существующих расчетов, используя уже рассчитанные индикаторы и формируя самостоятельные сигналы для торговли.

## Архитектура

### Таблица ролей TF

| TF      | Роль            | Назначение                       |
| ------- | --------------- | -------------------------------- |
| **1M**  | Super‑Context   | Фильтр экстремальных направлений |
| **1W**  | Macro           | Подтверждение месячного фона     |
| **1D**  | Context‑Trend   | Основное направление             |
| **4H**  | Phase           | Фаза тренда                      |
| **1H**  | Bridge          | Сглаживание конфликтов           |
| **15m** | Context+Trigger | Контекст + Основной вход         |
| **5m**  | Trigger‑Accel   | Тайминг и ускорение              |
| **1m**  | Micro‑Filter    | Ликвидность/шум                  |

### Структура базы данных

#### Схема `mtf`

```sql
-- Контекстные скоры по TF (1M,1W,1D,4H,1H,30m)
CREATE TABLE mtf.context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,            -- 1M/1W/1D/4H/1H/30m
    ts TIMESTAMPTZ NOT NULL,            -- метка бара TF
    score NUMERIC,                      -- trend_TF
    valid BOOLEAN,                      -- |score| >= τ_TF
    regime TEXT,                        -- для 1M/1W: trend/range + bull/bear
    meta JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Триггеры (15m/5m) и микро-фильтр (1m)
CREATE TABLE mtf.triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,            -- 15m/5m/1m
    ts TIMESTAMPTZ NOT NULL,
    p_up NUMERIC,                       -- для 1m допускаем NULL
    p_down NUMERIC,
    accel SMALLINT,                     -- -1/0/+1 (для 5m)
    micro_ok BOOLEAN,                   -- только для 1m
    features JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Финальное решение по горизонту (intraday/swing/week)
CREATE TABLE mtf.consensus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    horizon TEXT NOT NULL,              -- intraday/swing/week
    ts TIMESTAMPTZ NOT NULL,            -- время расчёта (обычно close 15m)
    side SMALLINT NOT NULL,             -- -1/0/+1
    score NUMERIC NOT NULL,             -- ранжирующий балл
    input_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### Представления

```sql
-- Последнее решение по каждому символу и горизонту
CREATE VIEW mtf.latest_consensus AS
SELECT DISTINCT ON (symbol, horizon)
    symbol, horizon, ts, side, score, input_data
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

## Алгоритмы

### 1. Расчет Context Score

```python
# Основные компоненты тренда
ema_trend = math.tanh((ema21 - ema55) / ema55 * 10)
adx_factor = min(adx14 / 100.0, 1.0)
vol_factor = min(vol_std_20 / 0.05, 2.0)

# Итоговый score
score = ema_trend * adx_factor * vol_factor
score = max(-1.0, min(1.0, score))
```

### 2. Весовые формулы по горизонтам

```python
context_intraday = 0.6*score_1D + 0.4*score_4H
context_swing    = 0.5*score_1D + 0.3*score_4H + 0.2*score_1W
context_week     = 0.4*score_1D + 0.3*score_1W + 0.3*score_1M
```

### 3. Правила принятия решения

#### Intraday
- `bias_core ≠ neutral`
- `p15 ≥ 0.60`
- `p5 ≥ 0.55` или `accel_5m == ±1`
- `micro_ok == true`

#### Swing (2–3 дня)
- `bias_swing ≠ neutral`
- `p15 ≥ 0.62`
- Подтверждение N=2 закрытия 15m
- `micro_ok` не обязателен

#### Week
- `bias_week ≠ neutral`
- `p15 ≥ 0.65`
- Отсутствие сильных конфликтов на 4H

### 4. Ранжирование силы сигнала

```python
strength = (
    w_ctx * |context_norm| +           # нормированный контекст по горизонту
    w_tr  * trig_prob +                # max(p_up, p_down) в сторону bias
    w_vol * vol_tail +                 # благоприятная волатильность
    w_lq  * lq_score -                 # ликвидность (объём, спред)
    w_risk* risk_penalty               # штраф за большой ATR/сложную структуру
)
```

## Установка и настройка

### 1. Создание базы данных

```bash
# Запуск миграции для создания расширенной MTF архитектуры
python src/db/migrate_create_mtf_expanded.py
```

### 2. Проверка структуры

```bash
# Проверка создания таблиц
python -c "
import asyncio
from src.database import get_async_session
from sqlalchemy import text

async def check_tables():
    async for session in get_async_session():
        result = await session.execute(text('SELECT table_name FROM information_schema.tables WHERE table_schema = \'mtf\''))
        tables = [row[0] for row in result.fetchall()]
        print('MTF таблицы:', tables)
        break

asyncio.run(check_tables())
"
```

## Использование

### CLI команды

#### 1. Полный pipeline

```bash
# Запуск полного MTF pipeline для всех символов
python src/mtf/cli_expanded.py pipeline

# Для конкретного символа
python src/mtf/cli_expanded.py pipeline --symbol BTC-USDT

# С указанием горизонтов
python src/mtf/cli_expanded.py pipeline --horizons intraday,swing,week
```

#### 2. Поэтапная обработка

```bash
# 1. Загрузка контекстных данных
python src/mtf/cli_expanded.py context --symbol BTC-USDT

# 2. Загрузка триггерных данных
python src/mtf/cli_expanded.py triggers --symbol BTC-USDT

# 3. Запись финальных решений
python src/mtf/cli_expanded.py consensus --symbol BTC-USDT --horizons intraday,swing,week
```

#### 3. Просмотр результатов

```bash
# Топ кандидаты intraday
python src/mtf/cli_expanded.py candidates --horizon intraday --side long --limit 10

# Топ кандидаты swing с минимальным score
python src/mtf/cli_expanded.py candidates --horizon swing --min-score 0.7 --limit 20

# Детали по конкретному символу
python src/mtf/cli_expanded.py details --symbol BTC-USDT
```

### Программное использование

```python
from src.mtf.etl.context_loader import context_loader
from src.mtf.etl.trigger_loader import trigger_loader
from src.mtf.etl.consensus_writer import consensus_writer

# Загрузка данных
await context_loader.load_context_for_symbol("BTC-USDT")
await trigger_loader.load_triggers_for_symbol("BTC-USDT")
await consensus_writer.write_consensus_for_symbol("BTC-USDT")

# Получение результатов
from src.database import get_async_session
from sqlalchemy import text

async for session in get_async_session():
    result = await session.execute(text("""
        SELECT * FROM mtf.top_intraday
        WHERE symbol = 'BTC-USDT'
    """))
    consensus = result.fetchone()
    print(f"Consensus: {consensus}")
    break
```

## Примеры запросов

### Самый сильный сигнал

```sql
SELECT symbol, calculated_at, side, score,
       input_data->>'context_score' as context_score,
       input_data->>'bias' as bias
FROM mtf.consensus
WHERE input_data->>'context_score'::numeric >= 0.5
  AND input_data->>'micro_ok' = 'true'
ORDER BY score DESC, calculated_at DESC
LIMIT 20;
```

### Лучшие LONG сигналы с высоким ADX

```sql
SELECT c.*, i.adx14
FROM mtf.top_intraday c
LEFT JOIN LATERAL (
    SELECT adx14 FROM indicators i
    WHERE i.symbol = c.symbol AND i.timeframe = '4H'
    ORDER BY i.ts DESC LIMIT 1
) i ON TRUE
WHERE c.side = 1 AND i.adx14 >= 20
ORDER BY c.score DESC;
```

### Анализ конфликтов

```sql
SELECT symbol, horizon, side, score,
       input_data->>'context_score' as context_score,
       input_data->>'p15_up' as p15_up,
       input_data->>'p15_down' as p15_down
FROM mtf.consensus
WHERE ABS(input_data->>'context_score'::numeric) < 0.2
  AND (input_data->>'p15_up'::numeric > 0.6 OR input_data->>'p15_down'::numeric > 0.6)
ORDER BY score DESC;
```

## Мониторинг и метрики

### Логирование

Система создает подробные логи:

```
2024-01-15 10:30:00 - src.mtf.etl.context_loader - INFO - Загружен контекст для BTC-USDT: 6 TF
2024-01-15 10:30:05 - src.mtf.etl.trigger_loader - INFO - Загружены триггеры для BTC-USDT: 3 TF
2024-01-15 10:30:10 - src.mtf.etl.consensus_writer - INFO - Записан consensus для BTC-USDT: 3 горизонтов
```

### Метрики производительности

```python
# Время выполнения pipeline
import time
start_time = time.time()
await run_full_pipeline(args)
execution_time = time.time() - start_time
print(f"Pipeline выполнен за {execution_time:.2f} секунд")

# Количество обработанных символов
async for session in get_async_session():
    result = await session.execute(text("SELECT COUNT(DISTINCT symbol) FROM mtf.consensus"))
    symbol_count = result.scalar()
    print(f"Обработано символов: {symbol_count}")
    break
```

## Интеграция с существующими системами

### Связка с модулем позиций

```python
from src.positions.calculator_mtf import MTFEnhancedPositionCalculator

# Получение MTF данных для расчета позиции
calculator = MTFEnhancedPositionCalculator()
position_data = {
    "symbol": "BTC-USDT",
    "direction": "LONG",
    "size": 1000
}

# Расчет позиции с учетом MTF
result = await calculator.calculate_position_with_mtf(
    position_data,
    use_mtf=True,
    mtf_weight=0.3
)
```

### Связка с scoring engine

```python
from src.scoring_engine.compute_mtf import MTFEnhancedScoringEngine

# Получение MTF данных для корректировки score
scoring_engine = MTFEnhancedScoringEngine()
score_result = await scoring_engine.compute_score_with_mtf(
    "BTC-USDT",
    "1m",
    timestamp,
    use_mtf=True
)
```

## Настройка параметров

### Пороги валидности

```python
# В src/mtf/etl/context_loader.py
VALIDITY_THRESHOLDS = {
    "1M": 0.4,   # Более строгий для месячного
    "1W": 0.35,  # Строгий для недельного
    "1D": 0.3,   # Стандартный для дневного
    "4H": 0.3,   # Стандартный для 4-часового
    "1H": 0.25,  # Менее строгий для часового
    "30m": 0.2   # Самый мягкий для 30-минутного
}
```

### Веса горизонтов

```python
# В src/mtf/etl/consensus_writer.py
HORIZON_WEIGHTS = {
    "intraday": {"1D": 0.6, "4H": 0.4},
    "swing": {"1D": 0.5, "4H": 0.3, "1W": 0.2},
    "week": {"1D": 0.4, "1W": 0.3, "1M": 0.3}
}
```

### Пороги принятия решений

```python
DECISION_THRESHOLDS = {
    "intraday": {
        "p15_min": 0.60,
        "p5_min": 0.55,
        "micro_required": True
    },
    "swing": {
        "p15_min": 0.62,
        "confirmations_required": 2,
        "micro_required": False
    },
    "week": {
        "p15_min": 0.65,
        "conflict_max": 0.2,
        "micro_required": False
    }
}
```

## Расширение и кастомизация

### Добавление новых индикаторов

1. Обновите `_get_latest_indicators()` в `context_loader.py`
2. Добавьте расчет в `_calculate_trend_score()`
3. Обновите метаданные в `_calculate_context()`

### Добавление новых горизонтов

1. Добавьте горизонт в `HORIZONS` в `consensus_writer.py`
2. Определите веса в `HORIZON_WEIGHTS`
3. Добавьте правила в `DECISION_THRESHOLDS`
4. Обновите CLI команды

### Кастомизация алгоритмов

```python
# Переопределение расчета trend score
def custom_trend_score(self, indicators: Dict) -> float:
    # Ваша логика расчета
    return custom_score

# Переопределение правил принятия решения
def custom_decision_rules(self, horizon: str, bias: str, ...) -> int:
    # Ваша логика принятия решений
    return custom_side
```

## Troubleshooting

### Частые проблемы

1. **Нет данных индикаторов**
   ```bash
   # Проверьте наличие данных
   python -c "
   import asyncio
   from src.database import get_async_session
   from sqlalchemy import text

   async def check_data():
       async for session in get_async_session():
           result = await session.execute(text('SELECT COUNT(*) FROM indicators WHERE timeframe = \'1D\''))
           print(f'1D индикаторы: {result.scalar()}')
           break

   asyncio.run(check_data())
   "
   ```

2. **Ошибки миграции**
   ```bash
   # Проверьте схему mtf
   python -c "
   import asyncio
   from src.database import get_async_session
   from sqlalchemy import text

   async def check_schema():
       async for session in get_async_session():
           result = await session.execute(text('SELECT table_name FROM information_schema.tables WHERE table_schema = \'mtf\''))
           tables = [row[0] for row in result.fetchall()]
           print('MTF таблицы:', tables)
           break

   asyncio.run(check_schema())
   "
   ```

3. **Медленная производительность**
   ```bash
   # Проверьте индексы
   python -c "
   import asyncio
   from src.database import get_async_session
   from sqlalchemy import text

   async def check_indexes():
       async for session in get_async_session():
           result = await session.execute(text('SELECT indexname FROM pg_indexes WHERE schemaname = \'mtf\''))
           indexes = [row[0] for row in result.fetchall()]
           print('MTF индексы:', indexes)
           break

   asyncio.run(check_indexes())
   "
   ```

## Заключение

Расширенная MTF система предоставляет мощный инструмент для анализа рынка на основе мультитаймфреймового подхода. Система полностью изолирована от существующих расчетов и может быть легко интегрирована с другими модулями проекта.

Основные преимущества:
- Изоляция от существующих систем
- Гибкая настройка параметров
- Поддержка различных торговых горизонтов
- Детальная аналитика и мониторинг
- Простота интеграции и расширения
