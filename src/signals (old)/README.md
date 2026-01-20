# Система торговых сигналов

Система для генерации торговых сигналов на основе технических индикаторов с возможностями оптимизации, оценки качества и **детализированного хранения сигналов**.

## 🚀 Новые возможности

### ✅ **Детализированная система сигналов** 🆕
- **Структурированное хранение** каждого правила в отдельной колонке
- **Мощная фильтрация** по отдельным индикаторам
- **ML-готовность** с числовыми scores для каждого правила
- **Аналитика и отчеты** по эффективности отдельных индикаторов

### ✅ Параметризация правил
- Все пороги вынесены в конфигурацию
- Поддержка YAML файлов конфигурации
- CLI override для тестирования альтернативных параметров

### ✅ Оценка качества сигналов
- Бэктестинг с PnL расчетом
- Метрики: Sharpe ratio, max drawdown, win rate
- Комиссии и реалистичные условия торговли

### ✅ Оптимизация параметров
- Grid-search для порогов индикаторов
- Random search для весов правил
- Автоматический выбор лучших параметров

### ✅ Веса правил
- Настраиваемые веса для каждого правила
- Стратегии: balanced, conservative, aggressive
- Оптимизация весов по метрикам качества

### ✅ Контроль качества
- Логирование всех сигналов
- Slack уведомления
- Мониторинг производительности

## Структура

```
src/signals/
├── __init__.py              # Основной пакет
├── README.md               # Документация
├── config.py               # Конфигурация параметров
├── logging.py              # Логирование сигналов
├── rules/                  # Правила сигналов
│   ├── __init__.py         # Экспорт всех правил
│   ├── trend_rules.py      # Трендовые правила
│   ├── oscillator_rules.py # Правила осцилляторов
│   └── volume_rules.py     # Объёмные правила
├── engine/                 # Движок сигналов
│   ├── __init__.py         # Экспорт движка
│   ├── signal_engine.py    # Основной класс движка
│   └── configs.py          # Конфигурации стратегий
└── calculator/             # Калькулятор сигналов
    ├── __init__.py         # Экспорт калькулятора
    ├── signal_calculator.py # Основной класс калькулятора (устаревший)
    ├── signal_calculator_detailed.py # 🆕 Детализированный калькулятор
    ├── cli.py              # CLI интерфейс (устаревший)
    └── cli_detailed.py     # 🆕 CLI для детализированных сигналов

src/backtest/               # Бэктестинг и оценка
├── __init__.py
├── metrics.py              # Метрики качества
└── evaluate.py             # Оценка сигналов

src/tuning/                 # Оптимизация параметров
├── __init__.py
├── grid_search.py          # Grid-search оптимизация
└── opt_weights.py          # Оптимизация весов

src/alerts/                 # Система уведомлений
├── __init__.py
└── slack_webhook.py        # Slack уведомления
```

## Компоненты

### 1. Правила (`rules/`)

Модули с функциями-правилами для различных технических индикаторов:

- **`trend_rules.py`** - Трендовые индикаторы:
  - `rule_ema21_sma50()` - EMA21 vs SMA50
  - `rule_sma50_sma200()` - Золотой/мёртвый крест
  - `rule_macd()` - MACD пересечения
  - `rule_adx14()` - ADX14 с +DI/-DI
  - `rule_ichimoku()` - Ichimoku Kijun/Tenkan

- **`oscillator_rules.py`** - Осцилляторы:
  - `rule_rsi14()` - RSI14 перепроданность/перекупленность
  - `rule_bollinger()` - Bollinger Bands
  - `rule_stochastic()` - Stochastic %K/%D
  - `rule_keltner()` - Keltner Channel

- **`volume_rules.py`** - Объёмные индикаторы:
  - `rule_volume_obv_cmf()` - OBV + CMF

### 2. Движок (`engine/`)

- **`signal_engine.py`** - Основной класс `SignalEngine`:
  - Агрегация сигналов от всех правил
  - Взвешенная сумма сигналов
  - Применение порогов для финального решения

- **`configs.py`** - Конфигурации стратегий:
  - `create_signal_engine()` - Фабрика движков
  - `balanced` - Сбалансированная стратегия
  - `conservative` - Консервативная (трендовые индикаторы)
  - `aggressive` - Агрессивная (осцилляторы)

### 3. Калькулятор (`calculator/`)

#### 🆕 **Детализированный калькулятор** (рекомендуется)
- **`signal_calculator_detailed.py`** - Основной класс `SignalCalculatorDetailed`:
  - Чтение индикаторов из БД
  - Генерация сигналов через движок
  - **Сохранение в таблицу `signals_detailed`** с отдельными колонками для каждого правила
  - **Текстовые и числовые значения** для каждого индикатора

- **`cli_detailed.py`** - Командный интерфейс для детализированных сигналов:
  - Парсинг аргументов
  - Обработка символов и таймфреймов
  - Логирование

#### Устаревший калькулятор
- **`signal_calculator.py`** - Основной класс `SignalCalculator`:
  - Чтение индикаторов из БД
  - Генерация сигналов через движок
  - Сохранение сигналов в БД (старая таблица `signals`)

- **`cli.py`** - Командный интерфейс:
  - Парсинг аргументов
  - Обработка символов и таймфреймов
  - Логирование

## Использование

### 🆕 **Детализированные сигналы** (рекомендуется)

#### Python API

```python
from src.signals.calculator.signal_calculator_detailed import SignalCalculatorDetailed

# Создание детализированного калькулятора
calculator = SignalCalculatorDetailed()

# Расчет сигналов для символа
result = await calculator.calculate_signals_for_symbol(
    symbol="BTC-USDT",
    timeframe="1m",
    recalculate=True,
    limit=100
)
print(f"Создано {result} детализированных сигналов")
```

#### CLI для детализированных сигналов

```bash
# Расчет для конкретного символа
python calc_detailed_signals.py --symbol BTC-USDT --timeframe 1m

# Расчет для всех символов
python calc_detailed_signals.py --all-symbols --timeframe 5m

# С ограничением количества записей
python calc_detailed_signals.py --symbol ETH-USDT --limit 50 --recalculate

# Пересчет существующих сигналов
python calc_detailed_signals.py --symbol BTC-USDT --recalculate

# Подробный вывод
python calc_detailed_signals.py --symbol BTC-USDT --verbose
```

### Устаревший API

```python
from src.signals import SignalEngine, create_signal_engine, RULES

# Создание движка
engine = create_signal_engine('balanced')  # или 'conservative', 'aggressive'

# Генерация сигнала
result = engine.generate_signal(current_data, previous_data)
print(f"Сигнал: {result['signal']}")  # -1, 0, 1
print(f"Причина: {result['reason']}")

# Использование отдельных правил
signal, reason = RULES['rsi14'](rsi_value)
```

#### CLI (устаревший)

```bash
# Расчет для конкретного символа
python src/calc_signals.py --symbol BTC-USDT --timeframe 1m

# Расчет для всех символов
python src/calc_signals.py --all-symbols --timeframe 5m

# С конфигурацией
python src/calc_signals.py --symbol ETH-USDT --config aggressive

# Пересчет существующих сигналов
python src/calc_signals.py --symbol BTC-USDT --recalculate

# Подробный вывод
python src/calc_signals.py --symbol BTC-USDT --verbose
```

## 🆕 **Детализированная система хранения**

### Таблица `signals_detailed`

```sql
CREATE TABLE signals_detailed (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts BIGINT NOT NULL,           -- timestamp в секундах
    signal SMALLINT NOT NULL,     -- -1 = sell, 0 = hold, 1 = buy
    total_score NUMERIC,          -- Общий взвешенный score

    -- Текстовые сигналы по правилам
    sma50_sma200 TEXT,            -- "bullish", "bearish", "neutral"
    ema21_sma50 TEXT,
    macd TEXT,
    rsi14 TEXT,
    bollinger TEXT,
    stochastic TEXT,
    adx14 TEXT,
    ichimoku TEXT,
    keltner TEXT,
    volume_obv_cmf TEXT,

    -- Числовые scores для каждого правила
    sma50_sma200_score NUMERIC,
    ema21_sma50_score NUMERIC,
    macd_score NUMERIC,
    rsi14_score NUMERIC,
    bollinger_score NUMERIC,
    stochastic_score NUMERIC,
    adx14_score NUMERIC,
    ichimoku_score NUMERIC,
    keltner_score NUMERIC,
    volume_obv_cmf_score NUMERIC,

    created_at TIMESTAMP,
    PRIMARY KEY (symbol, timeframe, ts)
);
```

### Таблица `signal_rule_codes`

```sql
CREATE TABLE signal_rule_codes (
    code SMALLINT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    description TEXT
);
```

### 🎯 **Мощные возможности фильтрации**

```sql
-- Найти сигналы с бычьим трендом И перепроданностью
SELECT * FROM signals_detailed
WHERE sma50_sma200 = 'bullish' AND bollinger = 'oversold';

-- Найти сигналы с сильным ADX
SELECT * FROM signals_detailed
WHERE adx14 = 'strong_trend';

-- Комбинированные условия
SELECT * FROM signals_detailed
WHERE rsi14 = 'oversold' AND macd = 'bullish' AND keltner = 'oversold';

-- Анализ эффективности каждого правила
SELECT
    sma50_sma200, COUNT(*) as count,
    AVG(total_score) as avg_score
FROM signals_detailed
GROUP BY sma50_sma200;

-- Корреляция между правилами
SELECT
    sma50_sma200, macd, COUNT(*) as count
FROM signals_detailed
GROUP BY sma50_sma200, macd;
```

## Конфигурации стратегий

### Balanced (Сбалансированная)
- Все правила имеют вес 1.0
- Пороги: buy ≥ 3, sell ≤ -3
- Подходит для большинства случаев

### Conservative (Консервативная)
- Больше веса трендовым индикаторам (SMA50/200: 2.5, MACD: 1.8)
- Пороги: buy ≥ 4, sell ≤ -4 (более строгие)
- Меньше ложных сигналов

### Aggressive (Агрессивная)
- Больше веса осцилляторам (RSI: 1.3, Stochastic: 1.2)
- Пороги: buy ≥ 2, sell ≤ -2 (более мягкие)
- Больше сигналов

## Новые возможности

### 🆕 **Анализ детализированных сигналов**

```python
from src.models import SignalDetailed
from sqlalchemy import select, func

# Найти лучшие точки входа
async for session in get_async_session():
    query = select(SignalDetailed).where(
        SignalDetailed.sma50_sma200 == 'bullish',
        SignalDetailed.bollinger == 'oversold',
        SignalDetailed.symbol == 'BTC-USDT'
    ).order_by(SignalDetailed.ts.desc()).limit(10)

    signals = (await session.execute(query)).scalars().all()
    for signal in signals:
        print(f"Время: {signal.ts}, Score: {signal.total_score}")
```

### Оценка качества сигналов

```bash
# Оценка всех символов
python src/evaluate_signals.py

# Оценка конкретного символа
python -c "
from src.backtest.evaluate import SignalEvaluator
import asyncio

async def main():
    evaluator = SignalEvaluator()
    result = await evaluator.evaluate_symbol('BTC-USDT', days_back=7)
    print(result)

asyncio.run(main())
"
```

### Оптимизация параметров

```bash
# Полная оптимизация (grid-search + веса)
python src/optimize_parameters.py

# Только grid-search
python -c "
from src.tuning.grid_search import GridSearchOptimizer
import asyncio

async def main():
    optimizer = GridSearchOptimizer()
    result = await optimizer.optimize_parameters(['BTC-USDT'], days_back=7)
    print(result)

asyncio.run(main())
"
```

### Логирование и мониторинг

```python
from src.signals.logging import log_signal, log_session_summary, get_session_stats

# Логирование сигнала
log_signal('BTC-USDT', '1m', 1, 3.5, 'RSI oversold', 1234567890)

# Сводка сессии
log_session_summary()

# Статистика
stats = get_session_stats()
print(f"Buy: {stats['buy_signals']}, Sell: {stats['sell_signals']}")
```

### Slack уведомления

```python
from src.alerts.slack_webhook import create_slack_notifier

# Создание уведомлений (требует SLACK_WEBHOOK_URL в .env)
notifier = create_slack_notifier()

if notifier:
    # Отправка алерта о сигнале
    notifier.send_signal_alert('BTC-USDT', 1, 3.5, 'RSI oversold')

    # Ежедневная сводка
    notifier.send_daily_summary(stats)
```

## База данных

### 🆕 **Таблица `signals_detailed`** (рекомендуется)

```sql
CREATE TABLE signals_detailed (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts BIGINT NOT NULL,           -- timestamp в секундах
    signal SMALLINT NOT NULL,     -- -1 = sell, 0 = hold, 1 = buy
    total_score NUMERIC,          -- Общий взвешенный score

    -- Текстовые сигналы по правилам
    sma50_sma200 TEXT,            -- "bullish", "bearish", "neutral"
    ema21_sma50 TEXT,
    macd TEXT,
    rsi14 TEXT,
    bollinger TEXT,
    stochastic TEXT,
    adx14 TEXT,
    ichimoku TEXT,
    keltner TEXT,
    volume_obv_cmf TEXT,

    -- Числовые scores для каждого правила
    sma50_sma200_score NUMERIC,
    ema21_sma50_score NUMERIC,
    macd_score NUMERIC,
    rsi14_score NUMERIC,
    bollinger_score NUMERIC,
    stochastic_score NUMERIC,
    adx14_score NUMERIC,
    ichimoku_score NUMERIC,
    keltner_score NUMERIC,
    volume_obv_cmf_score NUMERIC,

    created_at TIMESTAMP,
    PRIMARY KEY (symbol, timeframe, ts)
);
```

### Таблица `signals` (устаревшая)

```sql
CREATE TABLE signals (
    symbol TEXT,
    timeframe TEXT,
    ts BIGINT,           -- timestamp в миллисекундах
    signal NUMERIC,      -- -1 = sell, 0 = hold, 1 = buy
    reason TEXT,         -- JSON-строка с причинами
    created_at TIMESTAMP,
    PRIMARY KEY (symbol, timeframe, ts)
);
```

## Тестирование

```bash
# Тест детализированных сигналов
python test_detailed_signals.py

# Запуск тестов
python src/test_signals.py

# Запуск примеров
python src/example_signals.py
```

## Миграция

### Создание новых таблиц

```bash
# Создание таблиц для детализированных сигналов
python src/db/migrate_create_signals_detailed.py
```

## Расширение

### Добавление нового правила

1. Создайте функцию в соответствующем модуле `rules/`:
```python
def rule_new_indicator(param1: Optional[Decimal], param2: Optional[Decimal]) -> Tuple[int, str]:
    """Описание правила"""
    if param1 is None or param2 is None:
        return 0, ""

    if condition_for_buy:
        return 1, "Причина для покупки"
    elif condition_for_sell:
        return -1, "Причина для продажи"

    return 0, ""
```

2. Добавьте правило в `rules/__init__.py`:
```python
from .new_module import rule_new_indicator

RULES = {
    # ... существующие правила
    'new_indicator': rule_new_indicator,
}
```

3. 🆕 **Обновите модель `SignalDetailed`** в `src/models.py`:
```python
class SignalDetailed(Base):
    # ... существующие поля
    new_indicator = Column(String, nullable=True)
    new_indicator_score = Column(Numeric, nullable=True)
```

4. 🆕 **Обновите `SignalCalculatorDetailed`**:
```python
def _parse_rule_results(self, engine_result: Dict) -> Dict:
    rule_mapping = {
        # ... существующие правила
        'new_indicator': 'new_indicator'
    }
    # ... остальная логика
```

### Добавление новой конфигурации

1. Добавьте веса в `engine/configs.py`:
```python
elif config == 'new_strategy':
    weights = {
        'new_indicator': 2.0,
        # ... другие веса
    }
    threshold = 0.4
```

## Логирование

Система использует стандартный Python logging. Уровни:
- `INFO` - Основные события
- `DEBUG` - Детальная информация (с флагом `--verbose`)
- `WARNING` - Предупреждения
- `ERROR` - Ошибки

## Требования

- Python 3.8+
- SQLAlchemy (async)
- PostgreSQL
- python-dotenv
