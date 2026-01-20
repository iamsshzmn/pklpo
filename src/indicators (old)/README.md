# Система технических индикаторов

Модульная система для расчета технических индикаторов на основе OHLCV данных с поддержкой pandas-ta, автоматического обновления и интеграции с базой данных.

## 🚀 Возможности

### ✅ **Модульная архитектура**
- Разделение индикаторов по группам (MA, осцилляторы, волатильность, объем, тренд, squeeze)
- Реестр доступных индикаторов с конфигурацией
- Легкое добавление новых индикаторов

### ✅ **Автоматическое обновление**
- Инкрементальное обновление только новых данных
- Batch-обработка для оптимизации производительности
- UPSERT операции для избежания дубликатов

### ✅ **Интеграция с БД**
- Автоматическое создание недостающих колонок
- Поддержка PostgreSQL с async SQLAlchemy
- Оптимизированные запросы для больших объемов данных

### ✅ **Гибкая конфигурация**
- Настраиваемые параметры для каждого индикатора
- Поддержка различных таймфреймов
- Конфигурация через реестр индикаторов

### ✅ **Комбинации индикаторов**
- Предустановленные комбинации (пары, трио, квартеты)
- Анализ корреляций между индикаторами
- Калькулятор комбинаций с оценкой силы сигналов
- CLI интерфейс для анализа комбинаций
- Оптимизация для торговых стратегий

## Структура

```
src/indicators/
├── __init__.py              # Основной пакет
├── README.md               # Документация
├── calc_indicators.py      # Основной калькулятор индикаторов
├── indicator_utils.py      # Утилиты для расчета
├── registry/               # Реестр индикаторов
│   ├── __init__.py         # Экспорт всех индикаторов
│   ├── ma.py              # Moving Average индикаторы
│   ├── oscillators.py     # Осцилляторы
│   ├── volatility.py      # Индикаторы волатильности
│   ├── volume.py          # Объемные индикаторы
│   ├── trend.py           # Трендовые индикаторы
│   └── squeeze.py         # TTM Squeeze индикаторы
├── indicator_groups/       # Группы расчета индикаторов
│   ├── __init__.py         # Экспорт групп
│   ├── ma.py              # Расчет MA индикаторов
│   ├── oscillators.py     # Расчет осцилляторов
│   ├── volatility.py      # Расчет волатильности
│   ├── volume.py          # Расчет объемных
│   ├── trend.py           # Расчет трендовых
│   └── squeeze.py         # Расчет squeeze
└── combinations/           # Комбинации индикаторов
    ├── __init__.py         # Экспорт комбинаций
    ├── pairs.py           # Пары индикаторов
    ├── trios.py           # Трио индикаторов
    ├── quartets.py        # Квартеты индикаторов
    ├── calculator.py      # Калькулятор комбинаций
    └── cli.py             # CLI интерфейс
```

## Компоненты

### 1. Основной калькулятор (`calc_indicators.py`)

**Основные функции:**

#### `get_symbol_timeframes_to_update(session)`
Находит пары (symbol, timeframe), требующие обновления индикаторов:
```python
# Находит все пары, где есть новые OHLCV данные
pairs = await get_symbol_timeframes_to_update(session)
# Возвращает: [('BTC-USDT', '1m'), ('ETH-USDT', '5m'), ...]
```

#### `fetch_ohlcv_df(session, symbol, timeframe, since_ts=None, limit=500)`
Получает OHLCV данные из БД:
```python
df = await fetch_ohlcv_df(session, "BTC-USDT", "1m", since_ts=1753526400)
# Возвращает DataFrame с колонками: ts, open, high, low, close, volume
```

#### `upsert_indicators(session, symbol, timeframe, ind_df)`
Сохраняет рассчитанные индикаторы в БД:
```python
await upsert_indicators(session, "BTC-USDT", "1m", indicators_df)
# Автоматический UPSERT с обновлением существующих записей
```

#### `main()`
Основная функция для запуска расчета:
```python
async def main():
    # Автоматически находит и обновляет все необходимые индикаторы
    # Логирует прогресс и статистику
```

### 2. Утилиты расчета (`indicator_utils.py`)

**`calc_indicators(df: pd.DataFrame, available: set) -> pd.DataFrame`**

Универсальная функция расчета всех индикаторов:

```python
from src.indicators.indicator_utils import calc_indicators
from src.indicators.registry import AVAILABLE_INDICATORS

# Расчет всех доступных индикаторов
result_df = calc_indicators(ohlcv_df, AVAILABLE_INDICATORS)

# Результат содержит:
# - OHLCV данные (open, high, low, close, volume)
# - Все рассчитанные индикаторы
# - Нормализованный timestamp в секундах
```

### 3. Реестр индикаторов (`registry/`)

#### Доступные индикаторы

**Moving Averages (`ma.py`):**
- `sma50` - Simple Moving Average 50
- `sma200` - Simple Moving Average 200
- `ema21` - Exponential Moving Average 21

**Осцилляторы (`oscillators.py`):**
- `rsi14` - Relative Strength Index 14
- `stoch_k` - Stochastic %K
- `stoch_d` - Stochastic %D
- `macd` - MACD Line
- `macd_signal` - MACD Signal
- `macd_histogram` - MACD Histogram

**Волатильность (`volatility.py`):**
- `bb_upper` - Bollinger Bands Upper
- `bb_middle` - Bollinger Bands Middle
- `bb_lower` - Bollinger Bands Lower
- `kc_upper` - Keltner Channel Upper
- `kc_middle` - Keltner Channel Middle
- `kc_lower` - Keltner Channel Lower

**Объем (`volume.py`):**
- `obv` - On Balance Volume
- `cmf` - Chaikin Money Flow

**Тренд (`trend.py`):**
- `adx14` - Average Directional Index 14
- `adx_pos_di` - ADX +DI
- `adx_neg_di` - ADX -DI
- `ichimoku_tenkan` - Ichimoku Tenkan-sen
- `ichimoku_kijun` - Ichimoku Kijun-sen

**Squeeze (`squeeze.py`):**
- `ttm_squeeze_on` - TTM Squeeze On/Off
- `ttm_squeeze_hist` - TTM Squeeze Histogram
- `ttm_squeeze_value` - TTM Squeeze Value

#### Конфигурация индикаторов

```python
from src.indicators.registry import INDICATOR_CONFIG

# Параметры для каждого индикатора
config = INDICATOR_CONFIG['rsi14']  # {'length': 14}
config = INDICATOR_CONFIG['sma50']  # {'length': 50}
```

### 4. Группы расчета (`indicator_groups/`)

Каждая группа содержит функцию расчета для своего типа индикаторов:

#### `calc_ma_indicators(df, available)`
```python
from src.indicators.indicator_groups import calc_ma_indicators

ma_indicators = calc_ma_indicators(df, {'sma50', 'ema21'})
# Возвращает: {'sma50': Series, 'ema21': Series}
```

#### `calc_oscillator_indicators(df, available)`
```python
from src.indicators.indicator_groups import calc_oscillator_indicators

osc_indicators = calc_oscillator_indicators(df, {'rsi14', 'macd'})
# Возвращает: {'rsi14': Series, 'macd': Series, 'macd_signal': Series}
```

### 5. Комбинации индикаторов (`combinations/`)

#### Пары индикаторов (`pairs.py`)
```python
from src.indicators.combinations import PAIRS

# Предустановленные пары для анализа
for pair in PAIRS:
    print(f"{pair[0]} + {pair[1]}")
```

#### Трио индикаторов (`trios.py`)
```python
from src.indicators.combinations import TRIOS

# Комбинации из трех индикаторов
for trio in TRIOS:
    print(f"{trio[0]} + {trio[1]} + {trio[2]}")
```

## Использование

### Базовый расчет индикаторов

```python
import asyncio
from src.indicators.calc_indicators import main

# Запуск полного расчета для всех символов
async def run_calculation():
    await main()

if __name__ == "__main__":
    asyncio.run(run_calculation())
```

### Расчет для конкретного символа

```python
import asyncio
import pandas as pd
from src.indicators.indicator_utils import calc_indicators
from src.indicators.registry import AVAILABLE_INDICATORS

async def calculate_for_symbol(symbol: str, timeframe: str):
    # Получение OHLCV данных
    df = await fetch_ohlcv_df(session, symbol, timeframe)

    # Расчет индикаторов
    indicators_df = calc_indicators(df, AVAILABLE_INDICATORS)

    # Сохранение в БД
    await upsert_indicators(session, symbol, timeframe, indicators_df)

    return indicators_df
```

### Добавление нового индикатора

#### 1. Добавить в реестр (`registry/ma.py`):
```python
MA_INDICATORS = [
    'sma50',
    'sma200',
    'ema21',
    'new_indicator'  # Новый индикатор
]

MA_CONFIG = {
    'sma50': {'length': 50},
    'sma200': {'length': 200},
    'ema21': {'length': 21},
    'new_indicator': {'length': 30}  # Конфигурация
}
```

#### 2. Добавить расчет в группу (`indicator_groups/ma.py`):
```python
def calc_ma_indicators(df: pd.DataFrame, available: set) -> dict:
    result = {}

    if 'new_indicator' in available:
        config = MA_CONFIG['new_indicator']
        result['new_indicator'] = df['close'].ewm(
            span=config['length']
        ).mean()

    return result
```

### Работа с комбинациями

```python
from src.indicators.combinations import CombinationCalculator, COMBINATIONS

# Создание калькулятора комбинаций
calculator = CombinationCalculator()

# Анализ всех комбинаций
results = calculator.calculate_all_combinations(df)

# Получение лучших комбинаций
best_combinations = calculator.get_best_combinations(df, limit=5)

# Экспорт результатов
analysis_df = calculator.export_combination_analysis(results)
print(analysis_df)
```

### CLI интерфейс для комбинаций

```bash
# Список всех доступных комбинаций
python src/indicators/combinations/cli.py list

# Анализ всех комбинаций для BTC-USDT 1m
python src/indicators/combinations/cli.py analyze BTC-USDT 1m

# Анализ конкретной комбинации
python src/indicators/combinations/cli.py analyze BTC-USDT 1m --combination macd_rsi

# Анализ производительности комбинации
python src/indicators/combinations/cli.py performance BTC-USDT 1m macd_rsi --periods 200
```

### Доступные комбинации

#### Пары (PAIRS)
- `macd_rsi`: MACD + RSI (импульс + перекуп/перепрод)
- `macd_ichimoku`: MACD + Ichimoku (тренд-структура + импульс)
- `ema_adx`: EMA + ADX (направление тренда + сила тренда)
- `sma_stoch`: SMA + Stochastic (долгосрочный тренд + краткосрочный импульс)
- `rsi_obv`: RSI + OBV (импульс цены + подтверждение объёмом)
- `rsi_cmf`: RSI + CMF (импульс цены + денежный поток)
- `rsi_vwap_vp`: RSI + VWAP/Volume Profile (импульс + объём-ориентированный уровень)
- `obv_macd`: OBV + MACD (объём-давление + импульс)
- `macd_bbands`: MACD + Bollinger Bands (импульс + волатильность-канал)

#### Трио (TRIOS)
- `bbands_kc_ttm`: Bollinger Bands + Keltner Channel + TTM Squeeze
- `ichimoku_macd_rsi`: Ichimoku + MACD + RSI
- `macd_rsi_bbands`: MACD + RSI + Bollinger Bands

#### Квартеты (QUARTETS)
- `macd_rsi_adx_ema200`: MACD + RSI + ADX + EMA-200
- `ema_ribbon_adx_rsi_vp_vwap`: EMA-Ribbon + ADX + RSI + VP/VWAP

## Конфигурация

### Переменные окружения

```env
# Настройки БД (в .env)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname

# Настройки расчета
BATCH_SIZE=500  # Количество свечей для обработки
```

### Настройка индикаторов

```python
from src.indicators.registry import INDICATOR_CONFIG

# Изменение параметров
INDICATOR_CONFIG['rsi14']['length'] = 21  # RSI с периодом 21
INDICATOR_CONFIG['sma50']['length'] = 100  # SMA с периодом 100
```

## Производительность

### Оптимизации

1. **Batch-обработка**: Обработка по 500 свечей за раз
2. **Инкрементальное обновление**: Только новые данные
3. **UPSERT операции**: Избежание дубликатов
4. **Индексы БД**: Оптимизированные запросы

### Мониторинг

```python
# Логирование прогресса
logging.info(f"Найдено {len(pairs)} пар для обновления")
logging.info(f"{symbol} {timeframe}: рассчитано {len(ind_df)} индикаторов")

# Статистика
count = await session.execute(select(func.count()).select_from(Indicator))
print(f"Всего записей в таблице indicators: {count}")
```

## Интеграция с сигналами

Индикаторы автоматически используются системой сигналов:

```python
from src.signals.calculator.signal_calculator_detailed import SignalCalculatorDetailed

# Калькулятор сигналов использует рассчитанные индикаторы
calculator = SignalCalculatorDetailed()
result = await calculator.calculate_signals_for_symbol("BTC-USDT", "1m")
```

## Требования

- Python 3.8+
- pandas
- pandas-ta
- SQLAlchemy (async)
- PostgreSQL
- numpy

## Установка зависимостей

```bash
pip install pandas pandas-ta sqlalchemy[async] asyncpg numpy
```

## Логирование

Система использует стандартный Python logging:

```python
import logging

# Настройка уровня логирования
logging.basicConfig(level=logging.INFO)

# В логах отображаются:
# - Прогресс расчета
# - Статистика обновлений
# - Ошибки и предупреждения
```
