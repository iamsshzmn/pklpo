# Application Layer

## 🎭 Обзор

Application Layer оркестрирует процессы и координирует работу других слоев. Этот слой содержит workflow логику, управляет транзакциями и обрабатывает ошибки.

## 📁 Структура

```
application/
├── batch_processor.py    # Обработка батчей данных
└── README.md            # Эта документация
```

## 🔄 Компоненты

### `batch_processor.py`

Модуль для оркестрации batch обработки данных, включая расчет индикаторов и сохранение в базу данных.

#### Основные функции:

```python
from src.features.application.batch_processor import (
    process_single_pair,
    process_dataframe
)

# Обработка одной пары symbol-timeframe
success, count, time, errors = await process_single_pair(
    session, symbol, timeframe, available_indicators
)

# Обработка DataFrame
features = await process_dataframe(
    df_ohlcv, available_indicators, volatility_normalize=False
)
```

#### Функции:

##### `process_single_pair(session, symbol, timeframe, available)`
Обрабатывает одну пару symbol-timeframe: получает данные, рассчитывает индикаторы, сохраняет в БД.

**Параметры:**
- `session`: SQLAlchemy сессия
- `symbol`: Символ (например, "BTC-USDT-SWAP")
- `timeframe`: Таймфрейм (например, "1D")
- `available`: Множество доступных индикаторов

**Возвращает:**
- `tuple[bool, int, float, list[str]]`: (успех, количество_строк, время_расчета, ошибки)

**Workflow:**
1. Получение последнего timestamp из indicators
2. Извлечение новых OHLCV данных
3. Проверка достаточности данных (минимум 20 строк)
4. Расчет индикаторов через Domain Layer
5. Обеспечение существования колонок в БД
6. Сохранение индикаторов с retry/backoff
7. Возврат результата

**Особенности:**
- Retry механизм для транзиентных ошибок БД
- Exponential backoff (0.2s → 0.4s → 0.8s → 1.6s → 2.0s)
- Максимум 5 попыток
- Детальное логирование ошибок

##### `process_dataframe(df_ohlcv, available, volatility_normalize=False)`
Обрабатывает один DataFrame OHLCV и возвращает рассчитанные индикаторы.

**Параметры:**
- `df_ohlcv`: DataFrame с OHLCV данными
- `available`: Множество доступных индикаторов
- `volatility_normalize`: Нормализация волатильности

**Возвращает:**
- `pd.DataFrame`: DataFrame с рассчитанными индикаторами

**Особенности:**
- Тонкая обертка над Domain Layer
- Сохраняет текущее поведение
- Не изменяет входные данные

## 🎯 Принципы

### 1. Оркестрация процессов
- Координирует работу слоев
- Управляет жизненным циклом
- Обрабатывает workflow

### 2. Управление транзакциями
- Обеспечивает атомарность операций
- Обрабатывает rollback
- Управляет сессиями БД

### 3. Обработка ошибок
- Retry механизмы
- Graceful degradation
- Детальное логирование

### 4. Производительность
- Batch обработка
- Параллелизация
- Оптимизация запросов

## 🔄 Взаимодействие с другими слоями

### С Domain Layer:
```python
# Application использует Domain для расчета
from src.features.domain.calculator import calculate_batch

# В batch_processor.py
features = calculate_batch(df, available=available_indicators)
```

### С Infrastructure Layer:
```python
# Application использует Infrastructure для работы с БД
from src.features.infrastructure.database import (
    fetch_latest_ts,
    fetch_ohlcv_df,
    ensure_columns_exist,
    insert_indicators
)

# В batch_processor.py
latest_ts = await fetch_latest_ts(session, symbol, timeframe)
df = await fetch_ohlcv_df(session, symbol, timeframe, since_ts=latest_ts)
await ensure_columns_exist(session, "indicators", indicator_columns)
await insert_indicators(session, features_df, symbol, timeframe)
```

### С Core API:
```python
# Application может использовать Core API напрямую
from src.features.core import compute_features

# Альтернативный способ расчета
features = compute_features(df, available=available_indicators)
```

## 📝 Примеры использования

### Обработка одной пары:

```python
import asyncio
from src.database import get_async_session
from src.features.application.batch_processor import process_single_pair
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

async def process_btc_1d():
    async for session in get_async_session():
        success, count, time, errors = await process_single_pair(
            session,
            "BTC-USDT-SWAP",
            "1D",
            set(AVAILABLE_INDICATORS)
        )

        if success:
            print(f"✅ Обработано {count} строк за {time:.2f}s")
        else:
            print(f"❌ Ошибки: {errors}")

        break

# Запуск
asyncio.run(process_btc_1d())
```

### Batch обработка множества пар:

```python
import asyncio
from src.database import get_async_session
from src.features.application.batch_processor import process_single_pair
from src.features.infrastructure.database import get_symbol_timeframes_to_update
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

async def process_all_pairs():
    async for session in get_async_session():
        # Получить все пары для обновления
        pairs = await get_symbol_timeframes_to_update(session)

        print(f"Найдено {len(pairs)} пар для обработки")

        results = []
        for symbol, timeframe in pairs:
            try:
                success, count, time, errors = await process_single_pair(
                    session, symbol, timeframe, set(AVAILABLE_INDICATORS)
                )

                results.append({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'success': success,
                    'count': count,
                    'time': time,
                    'errors': errors
                })

                if success:
                    print(f"✅ {symbol} {timeframe}: {count} строк за {time:.2f}s")
                else:
                    print(f"❌ {symbol} {timeframe}: {errors}")

            except Exception as e:
                print(f"💥 {symbol} {timeframe}: {e}")
                results.append({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'success': False,
                    'count': 0,
                    'time': 0,
                    'errors': [str(e)]
                })

        # Статистика
        successful = sum(1 for r in results if r['success'])
        total_rows = sum(r['count'] for r in results)
        total_time = sum(r['time'] for r in results)

        print(f"\n📊 Статистика:")
        print(f"Успешно обработано: {successful}/{len(results)} пар")
        print(f"Всего строк: {total_rows}")
        print(f"Общее время: {total_time:.2f}s")

        break

# Запуск batch обработки
asyncio.run(process_all_pairs())
```

### Обработка DataFrame:

```python
import pandas as pd
import asyncio
from src.features.application.batch_processor import process_dataframe

async def process_custom_dataframe():
    # Подготовка данных
    df = pd.DataFrame({
        'ts': [1640995200, 1640998800, 1641002400],
        'open': [100.0, 101.0, 102.0],
        'high': [102.0, 103.0, 104.0],
        'low': [99.0, 100.0, 101.0],
        'close': [101.0, 102.0, 103.0],
        'volume': [1000, 1100, 1200]
    })

    # Обработка
    features = await process_dataframe(
        df,
        available={"rsi_14", "atr_14", "ema_12"},
        volatility_normalize=True
    )

    print(f"Рассчитано {len(features.columns)} индикаторов")
    print(features.head())

# Запуск
asyncio.run(process_custom_dataframe())
```

### Параллельная обработка:

```python
import asyncio
from src.database import get_async_session
from src.features.application.batch_processor import process_single_pair
from src.features.infrastructure.database import get_symbol_timeframes_to_update
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

async def process_pair(session, symbol, timeframe):
    """Обработка одной пары"""
    return await process_single_pair(
        session, symbol, timeframe, set(AVAILABLE_INDICATORS)
    )

async def process_parallel():
    async for session in get_async_session():
        # Получить все пары
        pairs = await get_symbol_timeframes_to_update(session)

        # Ограничить количество для демонстрации
        pairs = pairs[:5]

        print(f"Параллельная обработка {len(pairs)} пар")

        # Создать задачи
        tasks = [
            process_pair(session, symbol, timeframe)
            for symbol, timeframe in pairs
        ]

        # Запустить параллельно
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обработать результаты
        for i, result in enumerate(results):
            symbol, timeframe = pairs[i]

            if isinstance(result, Exception):
                print(f"💥 {symbol} {timeframe}: {result}")
            else:
                success, count, time, errors = result
                if success:
                    print(f"✅ {symbol} {timeframe}: {count} строк за {time:.2f}s")
                else:
                    print(f"❌ {symbol} {timeframe}: {errors}")

        break

# Запуск параллельной обработки
asyncio.run(process_parallel())
```

## 🧪 Тестирование

### Unit тесты:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.features.application.batch_processor import process_single_pair

@pytest.mark.asyncio
async def test_process_single_pair_success():
    # Создание моков
    mock_session = AsyncMock()

    # Мок для fetch_latest_ts
    mock_session.execute.return_value.scalar_one_or_none.return_value = 1640995200000

    # Мок для fetch_ohlcv_df
    import pandas as pd
    mock_df = pd.DataFrame({
        'ts': [1640995200, 1640998800],
        'open': [100.0, 101.0],
        'high': [102.0, 103.0],
        'low': [99.0, 100.0],
        'close': [101.0, 102.0],
        'volume': [1000, 1100]
    })

    # Мок для calculate_batch
    with patch('src.features.application.batch_processor.calculate_batch') as mock_calc:
        mock_calc.return_value = mock_df

        # Тест
        success, count, time, errors = await process_single_pair(
            mock_session, "BTC-USDT-SWAP", "1D", {"rsi_14"}
        )

        assert success is True
        assert count == 2
        assert time > 0
        assert errors == []

@pytest.mark.asyncio
async def test_process_single_pair_insufficient_data():
    # Создание моков
    mock_session = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    # Мок для fetch_ohlcv_df - недостаточно данных
    import pandas as pd
    mock_df = pd.DataFrame({
        'ts': [1640995200],
        'open': [100.0],
        'high': [102.0],
        'low': [99.0],
        'close': [101.0],
        'volume': [1000]
    })

    # Тест
    success, count, time, errors = await process_single_pair(
        mock_session, "BTC-USDT-SWAP", "1D", {"rsi_14"}
    )

    assert success is False
    assert count == 0
    assert "Недостаточно данных" in errors
```

### Интеграционные тесты:

```python
import pytest
from src.database import get_async_session
from src.features.application.batch_processor import process_single_pair
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

@pytest.mark.asyncio
async def test_process_single_pair_integration():
    async for session in get_async_session():
        # Тест с реальными данными
        success, count, time, errors = await process_single_pair(
            session,
            "BTC-USDT-SWAP",
            "1D",
            {"rsi_14", "atr_14"}
        )

        if success:
            assert count > 0
            assert time > 0
            assert errors == []
        else:
            # Проверить, что ошибки логируются
            assert len(errors) > 0

        break
```

## 🔧 Расширение

### Добавление нового workflow:

```python
# application/custom_workflow.py
from src.features.application.batch_processor import process_single_pair

async def process_with_validation(session, symbol, timeframe, available):
    """Обработка с дополнительной валидацией"""

    # Предварительная валидация
    from src.features.validators import validate_ohlcv_data

    # Получить данные для валидации
    from src.features.infrastructure.database import fetch_ohlcv_df
    df = await fetch_ohlcv_df(session, symbol, timeframe, limit=10)

    if df is not None:
        try:
            validate_ohlcv_data(df)
        except Exception as e:
            return False, 0, 0, [f"Валидация не пройдена: {e}"]

    # Стандартная обработка
    return await process_single_pair(session, symbol, timeframe, available)
```

### Добавление метрик:

```python
# application/metrics.py
import time
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class ProcessingMetrics:
    symbol: str
    timeframe: str
    success: bool
    rows_processed: int
    processing_time: float
    errors: List[str]
    timestamp: float

class MetricsCollector:
    def __init__(self):
        self.metrics: List[ProcessingMetrics] = []

    def record(self, symbol: str, timeframe: str, success: bool,
               rows: int, time: float, errors: List[str]):
        metric = ProcessingMetrics(
            symbol=symbol,
            timeframe=timeframe,
            success=success,
            rows_processed=rows,
            processing_time=time,
            errors=errors,
            timestamp=time.time()
        )
        self.metrics.append(metric)

    def get_summary(self) -> Dict:
        if not self.metrics:
            return {}

        successful = sum(1 for m in self.metrics if m.success)
        total_rows = sum(m.rows_processed for m in self.metrics)
        total_time = sum(m.processing_time for m in self.metrics)

        return {
            'total_pairs': len(self.metrics),
            'successful_pairs': successful,
            'success_rate': successful / len(self.metrics),
            'total_rows': total_rows,
            'total_time': total_time,
            'avg_time_per_pair': total_time / len(self.metrics)
        }

# Использование в batch_processor.py
metrics_collector = MetricsCollector()

async def process_single_pair_with_metrics(session, symbol, timeframe, available):
    start_time = time.time()

    success, count, time_taken, errors = await process_single_pair(
        session, symbol, timeframe, available
    )

    # Записать метрики
    metrics_collector.record(symbol, timeframe, success, count, time_taken, errors)

    return success, count, time_taken, errors
```

## 📚 Дополнительные ресурсы

- [ARCHITECTURE.md](../reports/ARCHITECTURE.md) - Общая архитектура
- [README.md](../README.md) - Общая документация
- [Domain Layer](../domain/README.md) - Доменный слой
- [Infrastructure Layer](../infrastructure/README.md) - Инфраструктурный слой

---

**Application Layer обеспечивает надежную оркестрацию процессов и эффективную обработку данных с retry механизмами и детальным логированием.**
