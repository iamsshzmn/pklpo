# Модуль Features - Подробная документация

## Обзор

Модуль `features` представляет собой комплексную систему для расчета технических индикаторов с поддержкой онлайн/офлайн паритета, предотвращением look-ahead bias и интеграцией с Airflow. Система построена на слоистой архитектуре и обеспечивает высокую производительность и надежность расчетов.

## Архитектура

### Слоистая архитектура (Clean Architecture)

```
src/features/
├── core.py                     # Основной публичный API
├── calc.py                     # Модуль расчета с поддержкой потоковой обработки
├── specs.py                    # Спецификации всех доступных индикаторов
├── models.py                   # Модели данных и исключения
├── utils.py                    # Утилиты и вспомогательные функции
├── validation.py               # Валидация данных
├── config.py                   # Конфигурация системы
├── gate_validation.py          # Quality gates перед записью/возвратом
├── code_validations.py         # Доп. проверки качества/аномалий
├── group_calculation.py        # Групповой расчёт без look‑ahead
├── domain/                     # Бизнес-логика (Domain Layer)
│   ├── calculator.py          # Фасад для расчета индикаторов
│   ├── indicator_specs.py     # Спецификации индикаторов
│   └── protocols.py           # Абстракции и протоколы
├── infrastructure/            # Инфраструктура (Infrastructure Layer)
│   ├── database.py            # Работа с базой данных
│   ├── db_operations.py       # Операции с БД (чтение/служебные)
│   ├── indicator_registry.py  # Реестр индикаторов (фасад)
│   ├── insert_indicators.py   # Вставка индикаторов в БД (UPSERT, sanitize)
│   └── upsert_builder.py      # Построитель UPSERT, санитизация значений
├── application/               # Прикладной слой (Application Layer)
│   └── batch_processor.py     # Оркестрация процессов
├── indicator_groups/          # Группы индикаторов по типам
│   ├── ma.py                  # Скользящие средние
│   ├── oscillators.py         # Осцилляторы
│   ├── volatility.py         # Индикаторы волатильности
│   ├── volume.py             # Объемные индикаторы
│   ├── trend.py              # Трендовые индикаторы
│   ├── squeeze.py            # TTM Squeeze индикаторы
│   ├── candles.py            # Свечные паттерны
│   ├── overlap.py            # Перекрывающиеся индикаторы
│   ├── statistics.py         # Статистические индикаторы
│   └── performance.py        # Индикаторы производительности
├── schema/                    # Схемы данных
│   ├── indicators_schema_clean.yml
│   ├── indicators_schema_complete.yml
│   └── schema_manager.py
├── registry/                  # Legacy реестр (deprecated)
├── tests/                     # Тесты
└── README/                    # Документация
```

## Основные компоненты

### 1. Core Module (`core.py`)

**Назначение**: Основной публичный API для расчета индикаторов.

**Ключевые функции**:
- `compute_features()` - главная функция для расчета индикаторов
- `get_available_features()` - получение списка доступных индикаторов
- `get_feature_info()` - получение информации об индикаторе
- `validate_feature_compatibility()` - проверка совместимости данных

**Особенности**:
- Единый интерфейс для расчета без look-ahead bias
- Поддержка онлайн/офлайн паритета
- Встроенная валидация данных
- Поддержка волатильностной нормализации
- Детальное логирование процесса расчета
 - Встроенные Quality Gates: вызывается `validate_data_gate()` перед возвратом результата

### 2. Specifications (`specs.py`)

**Назначение**: Централизованное хранение спецификаций всех доступных индикаторов.

**Структура спецификации**:
```python
@dataclass
class FeatureSpec:
    name: str                    # Уникальное имя индикатора
    type: str                    # Тип (trend, oscillator, volatility, volume, ma, etc.)
    params: dict[str, Any]       # Параметры расчета
    requires: list[str]          # Требуемые колонки OHLCV
    description: str             # Описание индикатора
```

**Группы индикаторов**:
- **Trend**: ADX, Aroon, Ichimoku, Supertrend, PSAR, Vortex
- **Oscillators**: RSI, MACD, Stochastic, StochRSI, Ultimate Oscillator
- **Volatility**: ATR, Bollinger Bands, Keltner Channels, Donchian Channels
- **Volume**: OBV, CMF, VWAP, Volume Profile, MFI
- **Moving Averages**: SMA, EMA, WMA, HMA, KAMA, TEMA, DEMA
- **Candles**: Heikin-Ashi, Doji, Inside bars
- **Squeeze**: TTM Squeeze индикаторы
- **Statistics**: Rolling statistics (median, std, variance, skewness, kurtosis)
- **Performance**: Returns, volatility, Sharpe ratio, drawdown

### 3. Calculation Module (`calc.py`)

**Назначение**: Модуль расчета с поддержкой потоковой обработки больших объемов данных.

**Ключевые функции**:
- `process_chunks()` - обработка данных по частям с перекрытием
- `compute_and_dump_parquet()` - расчет и сохранение в parquet файлы
- `validate_parquet_file()` - валидация сохраненных файлов

**Особенности**:
- Потоковая обработка для больших датасетов
- Перекрытие между чанками для корректного расчета
- Управление памятью и сборка мусора
- Сохранение промежуточных результатов в parquet

### 4. Data Models (`models.py`)

**Назначение**: Определение структур данных и исключений.

**Основные классы**:
- `FeatureSpec` - спецификация индикатора
- `FeatureResult` - результат расчета
- `FeatureCalculationConfig` - конфигурация расчета
- `FeatureValidationResult` - результат валидации
- `FeatureError` - базовое исключение модуля

### 5. Utilities (`utils.py`)

**Назначение**: Вспомогательные функции для обработки данных.

**Ключевые функции**:
- `volatility_normalize_features()` - нормализация по волатильности
- `zscore_normalize_features()` - Z-score нормализация
- `minmax_normalize_features()` - Min-Max нормализация
- `fill_missing_values()` - заполнение пропущенных значений
- `detect_outliers()` - обнаружение выбросов
- `calculate_feature_statistics()` - статистики по индикаторам
- `ensure_no_lookahead()` - проверка отсутствия look-ahead bias

### 6. Validation (`validation.py`)

**Назначение**: Комплексная валидация данных на всех этапах обработки.

**Класс `DataValidator`**:
- `validate_ohlcv_data()` - валидация входных OHLCV данных
- `validate_calculated_features()` - валидация рассчитанных индикаторов
- `validate_database_data()` - валидация данных перед записью в БД

**Функции валидации**:
- `validate_data_quality()` - основная функция валидации
- `check_data_consistency()` - проверка консистентности данных

### 7. Configuration (`config.py`)

**Назначение**: Централизованная конфигурация системы.

**Конфигурационные классы**:
- `StreamingConfig` - конфигурация потоковой обработки
- `DatabaseConfig` - конфигурация работы с БД
- `FeatureConfig` - конфигурация расчета индикаторов

**Поддержка переменных окружения**:
- `FEATURES_CHUNKSIZE` - размер чанка
- `FEATURES_MAX_LOOKBACK` - максимальный lookback
- `FEATURES_VOLATILITY_NORMALIZE` - включение нормализации
- `FEATURES_VERBOSE` - детальное логирование

## Группы индикаторов

### Moving Averages (`indicator_groups/ma.py`)
- **SMA**: Simple Moving Average (20, 34, 50, 200)
- **EMA**: Exponential Moving Average (8, 12, 13, 21, 26, 34, 50, 55, 89, 144, 200, 233)
- **WMA**: Weighted Moving Average (20)
- **HMA**: Hull Moving Average (20)
- **KAMA**: Kaufman Adaptive Moving Average (20)
- **TEMA**: Triple Exponential Moving Average (20)
- **DEMA**: Double Exponential Moving Average (20)
- **Advanced MAs**: ALMA, FWMA, RMA, T3, TRIMA, VIDYA, ZLMA, SINWMA, SWMA, PWMA, HWMA, LINREG

### Oscillators (`indicator_groups/oscillators.py`)
- **RSI**: Relative Strength Index (14)
- **MACD**: Moving Average Convergence Divergence (12, 26, 9)
- **Stochastic**: %K и %D (14, 3)
- **StochRSI**: Stochastic RSI (14, 14, 3, 3)
- **CCI**: Commodity Channel Index (20)
- **Ultimate Oscillator**: (7, 14, 28)
- **Williams %R**: (14)
- **Additional**: AO, APO, BOP, KDJ, RSX, TSI, Fisher Transform, Slope

### Volatility (`indicator_groups/volatility.py`)
- **ATR**: Average True Range (14)
- **NATR**: Normalized ATR (14)
- **Bollinger Bands**: Upper, Middle, Lower (20, 2)
- **Keltner Channels**: Upper, Middle, Lower (20, 10, 2)
- **Donchian Channels**: Upper, Middle, Lower (20)
- **Parkinson Volatility**: (14)
- **Additional**: Aberration, Acceleration Bands, Mass Index, Price Distance, RVI, Ulcer Index

### Volume (`indicator_groups/volume.py`)
- **OBV**: On Balance Volume
- **AD**: Accumulation/Distribution Line
- **CMF**: Chaikin Money Flow (20)
- **MFI**: Money Flow Index (14)
- **VWAP**: Volume Weighted Average Price

## Quality Gates и политика записи

### Gate Validation (`gate_validation.py`)
- Проверки перед записью и возвратом результата:
  - `min_rows` (по умолчанию 20)
  - общий `min_fill_rate` (по умолчанию 0.50)
  - `max_nan_ratio` на группу (по умолчанию 0.10)
  - `max_outlier_ratio` (по умолчанию 0.05)
- Возвращает `(is_valid, report)` с подробной статистикой, ошибками и предупреждениями.
- Интегрировано в `core.compute_features()`.

Пример:
```python
from src.features.gate_validation import GateValidator, GateConfig

valid, report = GateValidator(GateConfig()).validate_before_write(df, feature_groups)
if not valid:
    # блокируем запись/использование
    ...
```

### Политика схемы БД и запись (`infrastructure/`)
- Схема фиксируется миграциями (Alembic). Динамическое создание/изменение колонок в рантайме отключено.
- `insert_indicators.py`: фильтрует колонки, отсутствующие в схеме, и санитизирует значения (`NaN/±inf → NULL`).
- `upsert_builder.py`: строит UPSERT‑запросы, обеспечивает идемпотентность по `(symbol, timeframe, timestamp)` и безопасную вставку числовых значений.
- `db_operations.ensure_columns_exist`: присутствует для совместимости/офлайн‑утилит, но не используется в основном пути записи.

## CLI и оркестрация

Запуск через общий CLI:
```bash
python -m src.cli.main features --symbols BTC-USDT-SWAP ETH-USDT-SWAP \
  --timeframes 1m 5m 1H 1D --limit 200 --normalize --backend pandas_ta
```

Airflow:
- DAG `ops/airflow/dags/features_calc.py` вызывает CLI, публикует smoke‑метрики и логи прогресса.
- **VWMA**: Volume Weighted Moving Average (20)
- **Volume Profile**: Point of Control, Value Area High/Low
- **Additional**: EFI, EOM, NVI, PVI, PVT

### Trend (`indicator_groups/trend.py`)
- **ADX**: Average Directional Index (14) + Positive/Negative DI
- **Aroon**: Up, Down, Oscillator (14)
- **Ichimoku**: Tenkan, Kijun, Senkou A/B, Chikou
- **Supertrend**: Value, Direction, Long/Short lines (10, 3.0)
- **PSAR**: Parabolic SAR + Direction, Long/Short lines
- **Additional**: AMAT, Choppiness Index, Decay, DPO, QStick, TTM Trend, Vortex

### Candles (`indicator_groups/candles.py`)
- **Heikin-Ashi**: Open, High, Low, Close
- **Patterns**: Doji, Inside bar

### Squeeze (`indicator_groups/squeeze.py`)
- **TTM Squeeze**: On-state, Histogram, Value

### Statistics (`indicator_groups/statistics.py`)
- **Rolling Statistics**: Median, MAD, Standard Deviation, Variance, Skewness, Kurtosis, Z-score (20)

### Performance (`indicator_groups/performance.py`)
- **Returns**: Log return, Percent return, Rolling returns (20)
- **Risk Metrics**: Drawdown, Volatility, Sharpe ratio, Maximum drawdown (20)

## Инфраструктура

### Database Operations (`infrastructure/`)

**`database.py`**:
- Управление подключениями к БД
- Выполнение SQL запросов
- Обработка ошибок подключения

**`db_operations.py`**:
- Операции вставки данных
- Batch операции
- Upsert операции

**`insert_indicators.py`**:
- Специализированная вставка индикаторов
- Валидация данных перед вставкой
- Обработка конфликтов

**`upsert_builder.py`**:
- Построение UPSERT запросов
- Оптимизация для больших объемов данных

### Indicator Registry (`infrastructure/indicator_registry.py`)
- Централизованный реестр всех доступных индикаторов
- Метаданные индикаторов
- Конфигурация параметров

## Применение

### Application Layer (`application/`)

**`batch_processor.py`**:
- Оркестрация процессов расчета
- Управление батчами данных
- Координация между компонентами

## Использование

### Базовое использование

```python
import pandas as pd
from src.features.core import compute_features

# Подготовка данных OHLCV
df_ohlcv = pd.DataFrame({
    'ts': [1640995200, 1640998800, 1641002400],
    'open': [100.0, 101.0, 102.0],
    'high': [102.0, 103.0, 104.0],
    'low': [99.0, 100.0, 101.0],
    'close': [101.0, 102.0, 103.0],
    'volume': [1000, 1100, 1200]
})

# Расчет конкретных индикаторов
df_features = compute_features(
    df_ohlcv,
    specs=["rsi_14", "atr_14", "ema_12", "macd"],
    volatility_normalize=True,
    normalize_window=20,
    normalize_method="rolling_std"
)

print(f"Рассчитано {len(df_features.columns)} колонок")
print(f"Ключевые индикаторы: {df_features[['rsi_14', 'atr_14', 'ema_12']].head()}")
```

### Расчет всех доступных индикаторов

```python
from src.features.core import get_available_features

# Получение всех доступных индикаторов
all_features = get_available_features()
print(f"Доступно {len(all_features)} индикаторов")

# Расчет всех индикаторов
df_all_features = compute_features(
    df_ohlcv,
    specs=all_features,
    volatility_normalize=True
)
```

### Потоковая обработка больших данных

```python
from src.features.calc import process_chunks, compute_and_dump_parquet
from src.features.config import create_streaming_config

# Конфигурация потоковой обработки
config = create_streaming_config(
    CHUNKSIZE=100000,
    MAX_LOOKBACK=200,
    OVERLAP_SIZE=200
)

# Обработка по чанкам
def data_reader():
    # Ваш генератор данных
    for chunk in your_data_source:
        yield chunk

# Потоковая обработка
for features_chunk in process_chunks(
    data_reader(),
    symbol="BTC-USDT",
    timeframe="1h",
    config=config
):
    # Обработка каждого чанка
    process_features_chunk(features_chunk)

# Или расчет и сохранение в файл
stats = compute_and_dump_parquet(
    df_ohlcv=df_ohlcv,
    symbol="BTC-USDT",
    timeframe="1h",
    output_path="features_BTC-USDT_1h.parquet",
    volatility_normalize=True
)
```

### Валидация данных

```python
from src.features.validation import DataValidator, validate_data_quality

# Создание валидатора
validator = DataValidator()

# Валидация входных данных
ohlcv_result = validator.validate_ohlcv_data(df_ohlcv)
print(f"OHLCV данные валидны: {ohlcv_result['valid']}")
if ohlcv_result['errors']:
    print(f"Ошибки: {ohlcv_result['errors']}")

# Валидация рассчитанных индикаторов
features_result = validator.validate_calculated_features(df_features)
print(f"Индикаторы валидны: {features_result['valid']}")

# Быстрая валидация
is_valid, result = validate_data_quality(df_ohlcv, data_type="ohlcv", strict=False)
```

### Конфигурация

```python
from src.features.config import create_streaming_config, create_feature_config

# Конфигурация потоковой обработки
streaming_config = create_streaming_config(
    CHUNKSIZE=200000,
    MAX_LOOKBACK=200,
    OVERLAP_SIZE=200,
    FORCE_GC_AFTER_CHUNK=True,
    LOG_MEMORY_USAGE=True
)

# Конфигурация расчета индикаторов
feature_config = create_feature_config(
    ENABLE_VOLATILITY_NORMALIZE=True,
    NORMALIZE_WINDOW=20,
    NORMALIZE_METHOD="rolling_std",
    MIN_FILL_RATE=0.5,
    VALIDATE_RESULTS=True
)
```

## CLI и Airflow интеграция

### CLI команды

```bash
# Расчет индикаторов через CLI
python -m src.cli.main features --timeframes 1m 5m 15m 1H 4H 1D --normalize

# Smoke тест
python scripts/run_features_smoke.py BTC-USDT-SWAP 1D --limit 200
```

### Airflow DAG

DAG `features_calc` включает:
- `features_run` - запуск расчета индикаторов
- `smoke_validate_features` - валидация и метрики

## Мониторинг и метрики

### Ключевые метрики
- `total_rows` - общее количество строк
- `rows_last_24h` - строки за последние 24 часа
- `nan_ratio_last_24h` - доля NaN значений по ключевым колонкам

### Ключевые индикаторы для мониторинга
- `rsi_14`, `macd`, `atr_14`, `obv`, `vwap`
- `supertrend`, `psar`, `aroon_up`, `stochrsi_k`

### Логирование
- Детальное логирование процесса расчета
- Мониторинг использования памяти
- Отслеживание производительности
- Валидация качества данных

## Добавление новых индикаторов

### 1. Добавление спецификации

В `specs.py`:
```python
NEW_INDICATOR = FeatureSpec(
    name="new_indicator",
    type="oscillator",
    params={"period": 14},
    requires=["close"],
    description="New Technical Indicator (14 periods)"
)

FEATURE_SPECS["new_indicator"] = NEW_INDICATOR
```

### 2. Реализация расчета

В соответствующем файле `indicator_groups/`:
```python
def calc_new_indicator(df: pd.DataFrame, available_names: set) -> dict:
    """Calculate new indicator."""
    result = {}

    if "new_indicator" in available_names:
        # Реализация расчета
        values = your_calculation_logic(df)
        result["new_indicator"] = values

    return result
```

### 3. Обновление реестра

В `infrastructure/indicator_registry.py`:
```python
AVAILABLE_INDICATORS.append("new_indicator")

INDICATOR_CONFIG["new_indicator"] = {
    "params": {"period": 14},
    "requires": ["close"],
    "description": "New Technical Indicator (14 periods)"
}
```

### 4. Тестирование

```python
# Создание тестов в tests/
def test_new_indicator():
    df = create_test_data()
    result = compute_features(df, specs=["new_indicator"])
    assert "new_indicator" in result.columns
    assert not result["new_indicator"].isna().all()
```

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest src/features/tests/

# Интеграционные тесты с БД
pytest src/features/tests/test_db_integration_smoke.py

# Property-тесты (критически важные)
pytest src/features/tests/test_property.py

# Тесты производительности
pytest src/features/tests/test_performance.py
```

### Типы тестов
- **Unit тесты**: Тестирование отдельных функций
- **Integration тесты**: Тестирование взаимодействия компонентов
- **Property тесты**: Проверка свойств системы (отсутствие look-ahead, консистентность)
- **Performance тесты**: Тестирование производительности
- **Smoke тесты**: Быстрая проверка работоспособности

## Производительность и оптимизация

### Оптимизации
- **Векторизованные операции**: Использование pandas/numpy для быстрых вычислений
- **Потоковая обработка**: Обработка данных по частям для больших датасетов
- **Управление памятью**: Принудительная сборка мусора и очистка промежуточных объектов
- **Кэширование**: Кэширование промежуточных результатов
- **Параллелизация**: Поддержка многопоточности для независимых операций

### Мониторинг производительности
- Логирование времени выполнения
- Мониторинг использования памяти
- Отслеживание качества данных
- Метрики заполненности индикаторов

## Безопасность и надежность

### Предотвращение look-ahead bias
- Строгая проверка временных меток
- Валидация порядка данных
- Тестирование на изменяющихся данных

### Обработка ошибок
- Graceful degradation при ошибках расчета
- Детальное логирование ошибок
- Валидация входных данных
- Проверка качества результатов

### Консистентность данных
- Валидация типов данных
- Проверка диапазонов значений
- Обнаружение выбросов
- Контроль качества заполненности

## Заключение

Модуль `features` представляет собой комплексную, хорошо структурированную систему для расчета технических индикаторов. Архитектура обеспечивает:

- **Масштабируемость**: Поддержка больших объемов данных
- **Надежность**: Комплексная валидация и обработка ошибок
- **Производительность**: Оптимизированные алгоритмы и управление ресурсами
- **Расширяемость**: Легкое добавление новых индикаторов
- **Мониторинг**: Детальное отслеживание процесса и качества данных

Система готова к использованию в продакшене и может быть легко интегрирована в существующие торговые системы.
