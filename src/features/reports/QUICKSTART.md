# Features Module - Быстрый старт

## 🚀 Минимальный пример

### Новый API (рекомендуется)
```python
import pandas as pd
from src.features.core import compute_features

# Подготовка данных
ohlcv_data = pd.DataFrame({
    'ts': [1640995200, 1640998800, 1641002400],
    'open': [100.0, 101.0, 102.0],
    'high': [102.0, 103.0, 104.0],
    'low': [99.0, 100.0, 101.0],
    'close': [101.0, 102.0, 103.0],
    'volume': [1000, 1100, 1200]
})

# Расчёт индикаторов
features = compute_features(
    ohlcv_data,
    specs=["rsi_14", "atr_14", "ema_12"],
    volatility_normalize=True
)

print(features.head())
```

### Legacy API (deprecated)
```python
# DEPRECATED: используйте compute_features() вместо calc_indicators()
import pandas as pd
from src.features.indicator_utils import calc_indicators

# Подготовка данных
ohlcv_data = pd.DataFrame({
    'ts': [1640995200, 1640998800, 1641002400],
    'open': [100.0, 101.0, 102.0],
    'high': [102.0, 103.0, 104.0],
    'low': [99.0, 100.0, 101.0],
    'close': [101.0, 102.0, 103.0],
    'volume': [1000, 1100, 1200]
})

# Расчёт индикаторов (вызовет предупреждение)
features = calc_indicators(ohlcv_data, {"rsi_14", "atr_14", "ema_12"})
print(features.head())
```

## 📋 Требования к данным

### Обязательные колонки
- `open` - цена открытия
- `high` - максимальная цена
- `low` - минимальная цена  
- `close` - цена закрытия
- `volume` - объём торгов

### Опциональные колонки
- `ts` - временная метка (рекомендуется для валидации)

### Требования к данным
- Все цены должны быть положительными
- `high >= low` для каждого бара
- `close` должен быть в диапазоне `[low, high]`
- Временные метки должны быть монотонно возрастающими

## 🔧 Основные функции

### Расчёт индикаторов
```python
# Базовый расчёт
features = compute_features(ohlcv_data, specs=["rsi_14", "atr_14"])

# Все доступные индикаторы
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS
features = compute_features(ohlcv_data, available=set(AVAILABLE_INDICATORS))

# С волатильностной нормировкой
features = compute_features(
    ohlcv_data,
    specs=["rsi_14", "atr_14"],
    volatility_normalize=True,
    normalize_window=20
)
```

### Валидация данных
```python
from src.features import validate_ohlcv_data, validate_feature_compatibility

# Проверка OHLCV данных
validate_ohlcv_data(ohlcv_data)

# Проверка совместимости с индикаторами
compat = validate_feature_compatibility(ohlcv_data, ["rsi_14", "obv"])
if not compat.is_valid:
    print(f"Ошибки: {compat.errors}")
```

### Получение информации об индикаторах
```python
from src.features.core import get_available_features
from src.features.domain.indicator_specs import get_features_by_type
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

# Все доступные индикаторы
all_features = get_available_features()

# Индикаторы по типу
trend_features = get_features_by_type("trend")
oscillator_features = get_features_by_type("oscillator")
volatility_features = get_features_by_type("volatility")
volume_features = get_features_by_type("volume")
ma_features = get_features_by_type("ma")

# Прямой доступ к реестру
print(f"Всего индикаторов: {len(AVAILABLE_INDICATORS)}")
```

## 🖥️ CLI интерфейс

### Установка
```bash
# Запуск через модуль
python -m src.features.cli --help
```

### Расчёт индикаторов
```bash
# Базовый расчёт
python -m src.features.cli compute \
  --input data/ohlcv.csv \
  --specs rsi_14,atr_14,ema_12 \
  --output data/features.csv

# С нормировкой
python -m src.features.cli compute \
  --input data/ohlcv.csv \
  --specs rsi_14,atr_14,ema_12 \
  --normalize \
  --normalize-window 20 \
  --output data/features_norm.csv

# Все индикаторы
python -m src.features.cli compute \
  --input data/ohlcv.csv \
  --output data/features_all.csv
```

### Валидация
```bash
# Проверка данных
python -m src.features.cli validate \
  --input data/ohlcv.csv \
  --specs rsi_14,atr_14,ema_12
```

## 🧪 Тестирование

### Запуск тестов
```bash
# Все тесты
pytest src/features/tests/

# Только unit-тесты
pytest src/features/tests/test_core.py

# Property-тесты (критически важные)
pytest src/features/tests/test_property.py

# Интеграционные тесты
pytest src/features/tests/test_integration.py
```

### Бенчмарк производительности
```bash
python src/features/benchmark_performance.py
```

## 📊 Доступные индикаторы

### Популярные индикаторы
- `rsi_14` - Relative Strength Index (14 периодов)
- `atr_14` - Average True Range (14 периодов)
- `ema_12` - Exponential Moving Average (12 периодов)
- `macd` - MACD Line (12, 26, 9)
- `obv` - On Balance Volume
- `vwap` - Volume Weighted Average Price

### Полный список
```python
from src.features.core import get_available_features
from src.features.infrastructure.indicator_registry import AVAILABLE_INDICATORS

# Через core API
all_features = get_available_features()
print(f"Всего доступно индикаторов: {len(all_features)}")

# Прямой доступ к реестру
print(f"Индикаторы в реестре: {len(AVAILABLE_INDICATORS)}")
```

## 🔒 Безопасность

### Обработка ошибок
```python
from src.features.core import compute_features
from src.features.models import FeatureError

try:
    features = compute_features(ohlcv_data, specs=["rsi_14"])
except FeatureError as e:
    print(f"Ошибка расчёта: {e}")
    # Обработка ошибки
```

### Валидация входных данных
```python
from src.features.validators import validate_ohlcv_data

try:
    validate_ohlcv_data(ohlcv_data)
    print("✅ Данные валидны")
except Exception as e:
    print(f"❌ Ошибка валидации: {e}")
```

## 📈 Производительность

### Типичные результаты
- 1 индикатор, 1000 баров: < 0.5s
- 5 индикаторов, 1000 баров: < 1.0s
- 10 индикаторов, 1000 баров: < 2.0s
- С нормировкой: +50% времени

### Оптимизация
- Используйте только нужные индикаторы
- Отключайте нормировку, если не нужна
- Обрабатывайте данные батчами для больших датасетов

## 🔄 Интеграция с MTF

### Использование в MTF контексте
```python
from src.features.core import compute_features

# Расчёт признаков для разных таймфреймов
features_1m = compute_features(ohlcv_1m, specs=["rsi_14", "atr_14"])
features_15m = compute_features(ohlcv_15m, specs=["rsi_14", "atr_14"])
features_1h = compute_features(ohlcv_1h, specs=["rsi_14", "atr_14"])
```

## 📝 Примеры

### Запуск примеров
```bash
python src/features/examples.py
```

### Или по частям
```python
# Базовое использование
from src.features.core import compute_features

# Волатильностная нормировка
features_norm = compute_features(ohlcv_data, specs=["rsi_14"], volatility_normalize=True)

# Валидация данных
from src.features.validators import validate_ohlcv_data
validate_ohlcv_data(ohlcv_data)

# Интеграция с БД
from src.features.infrastructure.database import fetch_ohlcv_df, insert_indicators
```

## 🆘 Поддержка

### Документация
- [README.md](README.md) - полная документация
- [CHECKLIST.md](CHECKLIST.md) - чек-лист готовности
- [examples.py](examples.py) - примеры использования

### Логирование
```python
import logging

# Настройка уровня логирования
logging.getLogger("src.features").setLevel(logging.DEBUG)
```

### Отладка
```python
# Проверка совместимости
from src.features.validators import validate_feature_compatibility
compat = validate_feature_compatibility(ohlcv_data, ["rsi_14"])
if not compat.is_valid:
    print(f"Ошибки: {compat.errors}")
    print(f"Предупреждения: {compat.warnings}")
```

## ✅ Готовность к использованию

Модуль `features/` полностью готов к использованию и соответствует всем требованиям Фазы 2 проекта:

- ✅ Единый расчёт признаков без look-ahead bias
- ✅ Property-тесты на отсутствие утечек
- ✅ Онлайн/офлайн паритет (расхождение < 1e-10)
- ✅ Волатильностная нормировка
- ✅ Полное покрытие тестами
- ✅ CLI интерфейс
- ✅ Примеры использования

**Модуль готов к интеграции с context/triggers/consensus модулями!**
