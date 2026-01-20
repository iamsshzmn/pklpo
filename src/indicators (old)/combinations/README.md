# Combinations Module

Модуль для анализа комбинаций технических индикаторов. Предоставляет инструменты для изучения корреляций и взаимодействий между различными техническими индикаторами.

## Назначение

Модуль предназначен для:
- Анализа корреляций между техническими индикаторами
- Выявления сильных и слабых комбинаций индикаторов
- Генерации торговых рекомендаций на основе комбинаций
- Оценки производительности различных комбинаций

## Структура модуля

### Основные файлы

- **`calculator.py`** - Основной калькулятор комбинаций
- **`analyzer.py`** - Анализатор сигналов индикаторов
- **`recommendations.py`** - Генератор рекомендаций
- **`performance.py`** - Анализатор производительности
- **`cli.py`** - Командный интерфейс для работы с комбинациями

### Файлы комбинаций

- **`pairs.py`** - Комбинации из двух индикаторов
- **`trios.py`** - Комбинации из трех индикаторов
- **`quartets.py`** - Комбинации из четырех индикаторов

## Доступные комбинации

### Пары (Pairs)

| Название | Индикаторы | Роли | Описание |
|----------|------------|------|----------|
| `macd_rsi` | MACD, RSI14 | Импульс, Перекуп/перепрод | MACD + RSI: импульс + перекуп/перепрод |
| `macd_ichimoku` | MACD, Ichimoku | Импульс, Тренд-структура | MACD + Ichimoku: тренд-структура облака + импульс |
| `ema_adx` | EMA12/26/50/200, ADX14 | Направление тренда, Сила тренда | EMA + ADX: направление тренда + его сила |
| `sma_stoch` | SMA34/200, Stochastic | Долгосрочный тренд, Краткосрочный импульс | 34/200-SMA cross + Stochastic |
| `rsi_obv` | RSI14, OBV | Импульс цены, Подтверждение объёмом | RSI + OBV: импульс цены + подтверждение объёмом |
| `rsi_cmf` | RSI14, CMF | Импульс цены, Денежный поток | RSI + CMF: импульс цены + денежный поток |
| `rsi_vwap_vp` | RSI14, VWAP, Volume Profile | Импульс, Объём-ориентированный уровень | RSI + VWAP/Volume Profile |
| `obv_macd` | OBV, MACD | Объём-давление, Импульс | OBV + MACD: объём-давление + импульс |
| `macd_bbands` | MACD, Bollinger Bands | Импульс, Волатильность-канал | MACD + Bollinger Bands |

## Основные классы

### CombinationCalculator

Основной класс для расчета комбинаций индикаторов.

```python
from src.indicators.combinations import CombinationCalculator

calculator = CombinationCalculator()

# Анализ конкретной комбинации
result = calculator.calculate_combination(df, "macd_rsi")

# Анализ всех комбинаций
results = calculator.calculate_all_combinations(df)

# Получение лучших комбинаций
best = calculator.get_best_combinations(df, limit=5)
```

### SignalAnalyzer

Анализатор сигналов различных индикаторов.

```python
from src.indicators.combinations import SignalAnalyzer

analyzer = SignalAnalyzer()

# Анализ всех сигналов
signals = analyzer.analyze_all_signals(df)

# Анализ конкретного индикатора
rsi_signal = analyzer.analyze_rsi(df)
macd_signal = analyzer.analyze_macd(df)
```

### PerformanceAnalyzer

Анализатор производительности комбинаций.

```python
from src.indicators.combinations import PerformanceAnalyzer

perf_analyzer = PerformanceAnalyzer()

# Анализ производительности
performance = perf_analyzer.analyze_performance(df, "macd_rsi")
```

## Использование через CLI

### Анализ комбинаций

```bash
# Анализ всех комбинаций для символа
python -m src.indicators.combinations.cli analyze --symbol BTC-USDT --timeframe 1m

# Анализ конкретной комбинации
python -m src.indicators.combinations.cli analyze --symbol BTC-USDT --timeframe 1m --combination macd_rsi
```

### Анализ производительности

```bash
# Анализ производительности комбинации
python -m src.indicators.combinations.cli performance --symbol BTC-USDT --timeframe 1m --combination macd_rsi --periods 100
```

### Список доступных комбинаций

```bash
python -m src.indicators.combinations.cli list
```

## Структура результатов

### CombinationResult

```python
@dataclass
class CombinationResult:
    combination_name: str          # Название комбинации
    indicators: List[str]          # Список индикаторов
    correlation_matrix: pd.DataFrame  # Корреляционная матрица
    signal_strength: float         # Сила сигнала (0-1)
    conflict_count: int           # Количество конфликтов
    agreement_count: int          # Количество согласий
    recommendation: str           # Торговая рекомендация
    timestamp: int               # Временная метка
```

## Примеры использования

### Базовый анализ

```python
import pandas as pd
from src.indicators.combinations import CombinationCalculator

# Загрузка данных индикаторов
df = pd.read_csv('indicators_data.csv')

# Создание калькулятора
calculator = CombinationCalculator()

# Анализ комбинации MACD + RSI
result = calculator.calculate_combination(df, "macd_rsi")

if result:
    print(f"Сила сигнала: {result.signal_strength}")
    print(f"Рекомендация: {result.recommendation}")
    print(f"Корреляция: {result.correlation_matrix.loc['macd', 'rsi14']:.3f}")
```

### Экспорт результатов

```python
# Получение всех результатов
results = calculator.calculate_all_combinations(df)

# Экспорт в DataFrame
export_df = calculator.export_combination_analysis(results)
export_df.to_csv('combination_analysis.csv', index=False)
```

## Требования

- pandas
- numpy
- sqlalchemy (для работы с базой данных)
- asyncio (для CLI)

## Логирование

Модуль использует стандартное логирование Python. Для настройки логирования:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Примечания

- Все комбинации предопределены в файлах `pairs.py`, `trios.py`, `quartets.py`
- Для корректной работы требуется наличие всех индикаторов в DataFrame
- Минимальное количество данных для анализа: 10 строк
- Результаты кэшируются для оптимизации производительности
