# features_combinations

Модуль для расчёта комбинаций технических индикаторов в **numeric-only** формате. Хранит числовые фичи комбинаций без текстовых рекомендаций — все "сигналы" и "направления" кодируются числами.

## Назначение

Модуль предназначен для:
- Расчёта числовых фичей комбинаций индикаторов
- Хранения нормализованных фичей в БД (JSONB)
- Предоставления сырых агрегатов для слоя `signals` (без принятия решений)

**Важно:** Модуль не генерирует торговые рекомендации — это делает слой `signals`. Здесь только числовые фичи.

## Контракт данных

### Таблица `combination_features`

```sql
CREATE TABLE combination_features (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp BIGINT NOT NULL,           -- epoch_ms (совпадает с indicators.timestamp)
    combination_id TEXT NOT NULL,        -- идентификатор из registry (например, "macd_rsi")
    features JSONB NOT NULL,             -- только числовые значения
    meta JSONB,                          -- отладка, dbg-значения (не для прод-логики)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, timeframe, timestamp, combination_id)
);
```

### Поле `combination_id`

Идентификатор комбинации из реестра (`domain/registry.py`). Примеры:
- `"macd_rsi"` — комбинация MACD + RSI
- `"ema_adx"` — комбинация EMA + ADX
- Полный список: `from src.features_combinations import COMBINATIONS`

### Поле `features` (JSONB)

**Только числовые значения** (float/int). Никаких строк типа "bullish/bearish".

Примеры фичей:
```json
{
  "direction_num": 1.0,          // 1 = up, -1 = down, 0 = flat
  "trend_score": 0.78,            // 0.0 - 1.0
  "signal_strength": 0.85,        // 0.0 - 1.0
  "rsi_overbought_score": 0.3,    // 0.0 - 1.0
  "macd_direction_num": 1.0,       // 1/-1/0
  "agreement_count": 3.0,          // количество согласованных сигналов
  "conflict_count": 0.0,          // количество конфликтов
  "avg_correlation": 0.65          // средняя корреляция между индикаторами
}
```

**Правила:**
- Все значения — числа (float или int)
- Направления кодируются: `1.0` (up), `-1.0` (down), `0.0` (flat/neutral)
- Силы/вероятности: `0.0` - `1.0`
- Счётчики: целые числа как float (например, `3.0`)

### Поле `meta` (JSONB, опционально)

Используется только для отладки и исследований. Не используется в прод-логике.

Пример:
```json
{
  "debug_info": "some debug data",
  "calculation_version": "1.0.0",
  "raw_signals": {...}
}
```

### Индексы

- `ux_combination_features` — UNIQUE на (symbol, timeframe, timestamp, combination_id)
- `idx_combination_features_combo_id` — для поиска по combination_id
- `idx_combination_features_timestamp` — для временных запросов
- `idx_combination_features_features_gin` — GIN индекс для JSONB features

## Архитектура модуля

Модуль построен по принципам Clean Architecture с разделением на слои:

### Слои модуля

#### Domain (Доменная логика)
- **`domain/models.py`** - `CombinationRow` (домейн-модель)
- **`domain/registry.py`** - Централизованный реестр комбинаций (`COMBINATIONS`)
- **`domain/pairs.py`** - Комбинации из двух индикаторов
- **`domain/trios.py`** - Комбинации из трех индикаторов
- **`domain/quartets.py`** - Комбинации из четырех индикаторов

#### Application (Бизнес-логика)
- **`application/ports.py`** - Протоколы (`IndicatorProvider`, `CombinationCalculator`)
- **`application/service.py`** - `CombinationService` (оркестрация расчёта и сохранения)

#### Infrastructure (Инфраструктура)
- **`infrastructure/indicator_provider.py`** - `PostgresIndicatorProvider` (загрузка индикаторов)
- **`infrastructure/numeric_calculator.py`** - `NumericCombinationCalculator` (расчёт numeric features)
- **`infrastructure/numeric_analyzer.py`** - `NumericSignalAnalyzer` (преобразование сигналов в числа)
- **`infrastructure/repository.py`** - `PostgresCombinationRepository` (работа с БД)
- **`infrastructure/upsert_helper.py`** - Helper для UPSERT операций

#### CLI
- **`cli/main.py`** - Командный интерфейс для запуска расчётов

См. также [STRUCTURE.md](./STRUCTURE.md) для подробной структуры.

### Взаимодействие компонентов

```text
┌─────────────────┐
│  Data Provider  │ (Infrastructure)
│  (File/DB)      │
└────────┬────────┘
         │ DataFrame
         ▼
┌─────────────────┐
│   Validator     │ (Infrastructure)
│  (Schema Check) │
└────────┬────────┘
         │ Validated DataFrame
         ▼
┌─────────────────┐
│   Calculator    │ (Application)
│  (Orchestrator) │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬──────────────┐
    ▼         ▼              ▼              ▼
┌────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐
│Analyzer│ │Registry  │ │Performance │ │Recommend │
│Signals │ │Combinations│ │Analyzer   │ │Generator │
└───┬────┘ └────┬──────┘ └─────┬──────┘ └────┬─────┘
    │          │               │             │
    └──────────┴───────────────┴─────────────┘
                    │
                    ▼
            ┌───────────────┐
            │CombinationResult│
            └───────────────┘
```

### Принципы архитектуры

1. **Разделение ответственности**: каждый компонент отвечает за свою область
2. **Протоколы и интерфейсы**: провайдеры данных используют протокол `IndicatorDataProvider`
3. **Централизованный реестр**: все комбинации определяются в одном месте (`registry.py`)
4. **Композиция**: калькулятор использует специализированные анализаторы
5. **Кэширование**: результаты могут кэшироваться на уровне калькулятора

## Логика работы модуля

### Поток обработки данных

#### 1. Загрузка и валидация данных

```python
# Провайдер загружает данные
df = provider.load(symbol, timeframe, limit)

# Валидация схемы (проверка наличия колонок)
df = validate_input_schema(df, ts_col="ts")
```

**Логика валидации:**

- Проверка наличия обязательных колонок
- Проверка наличия колонки временной метки
- Возврат валидированного DataFrame или исключение

#### 2. Расчет комбинации

**Алгоритм `calculate_combination`:**

1. **Проверка реестра**: комбинация должна существовать в `COMBINATIONS`
2. **Проверка данных**: все индикаторы комбинации должны присутствовать в DataFrame
3. **Фильтрация данных**:
   - Выбор только нужных колонок индикаторов
   - Удаление строк с `NaN`
   - Проверка минимального количества данных (≥10 строк)
4. **Расчет корреляций**: построение корреляционной матрицы через `pandas.corr()`
5. **Анализ сигналов**: вызов `SignalAnalyzer.analyze_all_signals()`
6. **Расчет силы сигнала**: `SignalAnalyzer.calculate_signal_strength()`
7. **Генерация рекомендации**: `RecommendationGenerator.generate_signal_recommendation()`

#### 3. Анализ сигналов индикаторов

**Класс `SignalAnalyzer`** анализирует каждый тип индикатора:

- **RSI**: пороги 30/70 для перепроданности/перекупленности
- **MACD**: знак значения (положительный = бычий, отрицательный = медвежий)
- **EMA**: порядок значений EMA (бычий/медвежий тренд)
- **Bollinger Bands**: позиция цены относительно полос
- **Stochastic**: пороги 20/80 для перепроданности/перекупленности
- **ADX**: пороги 20/25 для силы тренда
- **Объемные индикаторы** (OBV, CMF): направление изменения и денежный поток

**Алгоритм расчета силы сигнала:**

```python
def calculate_signal_strength(signals):
    # 1. Классификация сигналов на бычьи/медвежьи
    bullish_signals = count_signals_with_keywords(["бычий", "перепроданность", ...])
    bearish_signals = count_signals_with_keywords(["медвежий", "перекупленность", ...])

    # 2. Определение преобладающего направления
    agreements = max(bullish_signals, bearish_signals)
    conflicts = min(bullish_signals, bearish_signals)

    # 3. Расчет силы (0-1)
    strength = agreements / total_signals

    return strength, agreements, conflicts
```

**Формула силы сигнала:**

```
strength = agreements / total_signals
```

где:
- `agreements` - количество согласованных сигналов
- `total_signals` - общее количество сигналов
- `strength` ∈ [0, 1]

#### 4. Генерация рекомендаций

**Класс `RecommendationGenerator`** использует пороговую логику:

| Сила сигнала | Конфликты | Рекомендация |
|--------------|-----------|--------------|
| ≥ 0.8 | 0 | СИЛЬНЫЙ СИГНАЛ: Все индикаторы согласованы |
| ≥ 0.8 | > 0 | СИЛЬНЫЙ СИГНАЛ: Преобладают согласованные сигналы |
| ≥ 0.6 | - | УМЕРЕННЫЙ СИГНАЛ: Большинство индикаторов согласованы |
| ≥ 0.4 | - | СЛАБЫЙ СИГНАЛ: Смешанные сигналы |
| < 0.4 | - | КОНФЛИКТ: Индикаторы противоречат друг другу |

**Торговые рекомендации** генерируются на основе:

- Преобладающего направления (бычье/медвежье)
- Силы сигнала
- Количества согласованных индикаторов

#### 5. Анализ производительности

**Класс `PerformanceAnalyzer`** выполняет:

1. **Исторический анализ**: расчет сигналов для скользящего окна
2. **Распределение сигналов**: статистика по силе (сильные ≥0.7, умеренные 0.4-0.7, слабые <0.4)
3. **Консистентность**: анализ изменений силы сигналов во времени
4. **Метрики риска**:
   - Коэффициент вариации силы сигнала
   - Среднее количество конфликтов
   - Максимальное падение (drawdown)

**Формула общего скора производительности:**

```text
overall_score =
    0.4 × success_rate +
    0.3 × avg_strength +
    0.2 × stability_score +
    0.1 × (1 - risk_score)
```

где:
- `success_rate` - доля сильных сигналов
- `avg_strength` - средняя сила сигнала
- `stability_score` = 1 / (1 + volatility) - стабильность
- `risk_score` - композитный риск (нормализованный)

### Алгоритмы расчета

#### Корреляционная матрица

Используется стандартный метод Пирсона:
```python
correlation_matrix = df[indicators].corr()
```

#### Анализ согласованности сигналов

Сигналы классифицируются по ключевым словам:

- **Бычьи**: "бычий", "перепроданность", "растущий", "приток", "сильный тренд"
- **Медвежьи**: "медвежий", "перекупленность", "падающий", "отток", "слабый тренд"

Согласованность определяется как преобладание одного типа сигналов.

#### Оценка риска

Композитный риск рассчитывается как:

```text
risk_score = (CV + avg_conflicts/10 + max_drawdown) / 3
```

где:
- `CV` - коэффициент вариации силы сигнала
- `avg_conflicts` - среднее количество конфликтов
- `max_drawdown` - максимальное падение от пика

### Кэширование

`CombinationCalculator` использует внутренний кэш `results_cache` для оптимизации повторных расчетов. Кэш работает на уровне экземпляра калькулятора.

### Обработка ошибок

- **Отсутствие комбинации**: возврат `None` с логированием
- **Отсутствие индикаторов**: возврат `None` с логированием отсутствующих колонок
- **Недостаточно данных**: возврат `None` если после очистки `NaN` < 10 строк
- **Ошибки расчета**: логирование и пропуск комбинации при расчете всех комбинаций

## Реестр комбинаций

Все комбинации централизованы в `registry.py` через объединение `PAIRS`, `TRIOS` и `QUARTETS`:

```python
from features_combinations import COMBINATIONS

# Получить все доступные комбинации
print(COMBINATIONS.keys())

# Получить конфигурацию комбинации
config = COMBINATIONS["macd_rsi"]
# {
#     "indicators": ["macd", "rsi14"],
#     "roles": ["Импульс", "Перекуп/перепрод"],
#     "description": "MACD + RSI: импульс + перекуп/перепрод"
# }
```

### Доступные комбинации

#### Пары (Pairs)

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

Полный список комбинаций доступен через команду `python -m features_combinations.cli list`.

## Основные классы

### CombinationCalculator

Основной класс для расчета комбинаций индикаторов.

```python
from features_combinations import CombinationCalculator

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
from features_combinations import SignalAnalyzer

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
from features_combinations import PerformanceAnalyzer

perf_analyzer = PerformanceAnalyzer()

# Анализ производительности
performance = perf_analyzer.analyze_performance(df, "macd_rsi")
```

### RecommendationGenerator

Генератор торговых рекомендаций на основе анализа комбинаций.

```python
from features_combinations import RecommendationGenerator

generator = RecommendationGenerator()

# Генерация рекомендации
recommendation = generator.generate_recommendation(
    signals, conflicts=0, agreements=3
)
```

## Провайдеры данных

Модуль поддерживает загрузку данных через провайдеры, реализующие протокол `IndicatorDataProvider`.

### FileIndicatorProvider

Провайдер для загрузки данных из файлов (CSV или Parquet).

```python
from pathlib import Path
from features_combinations.providers import FileIndicatorProvider

# Инициализация провайдера
provider = FileIndicatorProvider(
    root=Path("./data/indicators"),
    file_format="parquet",  # или "csv"
    ts_col="ts"
)

# Загрузка данных
df = provider.load("BTC-USDT", "1m", limit=500)
```

Формат имени файла: `{symbol}_{timeframe}.{format}` (например, `BTC-USDT_1m.parquet`).

### Валидация данных

Провайдеры автоматически валидируют схему данных через `validate_input_schema`:

```python
from features_combinations.providers import validate_input_schema

# Валидация DataFrame
df = validate_input_schema(
    df,
    required_cols=["macd", "rsi14"],
    ts_col="ts"
)
```

## Установка и импорт

- **Локально (из исходников):** добавьте корень проекта в `PYTHONPATH` или установите модуль через `pip install -e .` после подготовки `pyproject.toml`/`setup.cfg`.
- **Импорт:** `from features_combinations import CombinationCalculator, SignalAnalyzer, PerformanceAnalyzer`.

## Использование через CLI

CLI поддерживает два режима работы:
1. **С проектной БД** - требует модули `src.database` и `src.models`
2. **С файловым провайдером** - автономный режим через CSV/Parquet файлы

### Анализ комбинаций

```bash
# Анализ всех комбинаций для символа (из БД)
python -m features_combinations.cli analyze BTC-USDT 1m

# Анализ конкретной комбинации (из БД)
python -m features_combinations.cli analyze BTC-USDT 1m --combination macd_rsi

# Анализ через файловый провайдер
python -m features_combinations.cli analyze BTC-USDT 1m \
    --provider file \
    --data-dir ./data/indicators \
    --format parquet
```

### Анализ производительности

```bash
# Анализ производительности комбинации (из БД)
python -m features_combinations.cli performance BTC-USDT 1m macd_rsi --periods 100

# Анализ производительности через файловый провайдер
python -m features_combinations.cli performance BTC-USDT 1m macd_rsi \
    --periods 100 \
    --provider file \
    --data-dir ./data/indicators
```

### Список доступных комбинаций

```bash
python -m features_combinations.cli list
```

## Структура результатов

### CombinationResult

```python
@dataclass
class CombinationResult:
    combination_name: str          # Название комбинации
    indicators: list[str]          # Список индикаторов
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
from features_combinations import CombinationCalculator

# Загрузка данных индикаторов
df = pd.read_csv("indicators_data.csv")

# Создание калькулятора
calculator = CombinationCalculator()

# Анализ комбинации MACD + RSI
result = calculator.calculate_combination(df, "macd_rsi")

if result:
    print(f"Сила сигнала: {result.signal_strength}")
    print(f"Рекомендация: {result.recommendation}")
    print(f"Корреляция: {result.correlation_matrix.loc['macd', 'rsi14']:.3f}")
```

### Использование с файловым провайдером

```python
from pathlib import Path
from features_combinations import CombinationCalculator
from features_combinations.providers import FileIndicatorProvider

# Инициализация провайдера
provider = FileIndicatorProvider(
    root=Path("./data/indicators"),
    file_format="parquet"
)

# Загрузка данных
df = provider.load("BTC-USDT", "1m", limit=500)

# Анализ комбинаций
calculator = CombinationCalculator()
results = calculator.calculate_all_combinations(df)
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
- (опционально) sqlalchemy и async драйвер БД — только для CLI-интеграции с БД
- (опционально) asyncio — для запуска CLI команд
- (опционально) pyarrow или fastparquet — для работы с Parquet файлами

## Логирование

Модуль использует стандартное логирование Python. Конфигурация логирования выполняется приложением-потребителем:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Примечания

- Все комбинации предопределены в файлах `pairs.py`, `trios.py`, `quartets.py` и централизованы в `registry.py`
- Для корректной работы требуется наличие соответствующих колонок индикаторов в DataFrame
- Минимальное количество данных для анализа: 10 строк после очистки `NaN`
- Результаты могут кэшироваться на уровне экземпляра калькулятора
- Провайдеры данных автоматически валидируют схему входных данных

## Список экспортируемых объектов

```python
from features_combinations import (
    # Реестры комбинаций
    PAIRS,
    TRIOS,
    QUARTETS,
    COMBINATIONS,
    # Основные классы
    CombinationCalculator,
    CombinationResult,
    SignalAnalyzer,
    RecommendationGenerator,
    PerformanceAnalyzer,
    # Функции
    analyze_combination_performance,
)

# Провайдеры данных
from features_combinations.providers import (
    IndicatorDataProvider,
    FileIndicatorProvider,
    validate_input_schema,
)
```
