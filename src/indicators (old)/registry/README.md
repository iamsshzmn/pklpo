# Indicator Registry

Централизованная система регистрации и конфигурации технических индикаторов. Модуль `registry` обеспечивает единообразное управление всеми доступными индикаторами, их параметрами и зависимостями.

## Обзор

Модуль `registry` предназначен для:
- Централизованного хранения списков доступных индикаторов
- Конфигурации параметров каждого индикатора
- Определения зависимостей между индикаторами и данными OHLCV
- Обеспечения единообразного интерфейса для работы с индикаторами

## Структура модуля

### Основные компоненты:

#### 1. Moving Averages (`ma.py`)
**Список индикаторов:** `MA_INDICATORS`
**Конфигурация:** `MA_CONFIG`

**Доступные индикаторы:**
- **EMA**: ema12, ema21, ema26, ema50, ema200
- **SMA**: sma34, sma50, sma200
- **EMA Ribbon**: ema_8, ema_13, ema_21, ema_34, ema_55, ema_89, ema_144, ema_233

#### 2. Oscillators (`oscillators.py`)
**Список индикаторов:** `OSC_INDICATORS`
**Конфигурация:** `OSC_CONFIG`

**Доступные индикаторы:**
- **RSI**: rsi14 (Relative Strength Index)
- **Stochastic**: stoch_k, stoch_d (Stochastic Oscillator)
- **MACD**: macd, macd_signal, macd_histogram
- **ADX**: adx14, adx_pos_di, adx_neg_di (Average Directional Index)

#### 3. Volatility (`volatility.py`)
**Список индикаторов:** `VOL_INDICATORS`
**Конфигурация:** `VOL_CONFIG`

**Доступные индикаторы:**
- **Bollinger Bands**: bb_upper, bb_middle, bb_lower
- **Keltner Channels**: kc_upper, kc_middle, kc_lower
- **ATR**: atr14 (Average True Range)

#### 4. Volume (`volume.py`)
**Список индикаторов:** `VOLU_INDICATORS`
**Конфигурация:** `VOLU_CONFIG`

**Доступные индикаторы:**
- **OBV**: obv (On-Balance Volume)
- **CMF**: cmf (Chaikin Money Flow)
- **VWAP**: vwap (Volume Weighted Average Price)
- **Volume Profile**: vp_value_area_high, vp_value_area_low, vp_point_of_control
- **Volume SMA**: volume_sma20

#### 5. Trend (`trend.py`)
**Список индикаторов:** `TREND_INDICATORS`
**Конфигурация:** `TREND_CONFIG`

**Доступные индикаторы:**
- **Ichimoku**: ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b, ichimoku_chikou
- **ADX**: adx14, adx_pos_di, adx_neg_di

#### 6. Squeeze (`squeeze.py`)
**Список индикаторов:** `SQUEEZE_INDICATORS`
**Конфигурация:** `SQUEEZE_CONFIG`

**Доступные индикаторы:**
- **TTM Squeeze**: ttm_squeeze_on, ttm_squeeze_hist, ttm_squeeze_value

## Структура конфигурации

### Общий формат конфигурации индикатора:

```python
'indicator_name': {
    'period': 14,                    # Основной период (опционально)
    'fast_period': 12,               # Быстрый период (для MACD)
    'slow_period': 26,               # Медленный период (для MACD)
    'signal_period': 9,              # Период сигнала (для MACD)
    'k_period': 14,                  # Период %K (для Stochastic)
    'd_period': 3,                   # Период %D (для Stochastic)
    'std_dev': 2,                    # Стандартное отклонение (для Bollinger)
    'length': 20,                    # Длина (для Keltner)
    'mult': 2,                       # Множитель (для Keltner)
    'description': 'Описание индикатора',
    'requires': ['close', 'high', 'low', 'volume']  # Требуемые данные
}
```

### Примеры конфигураций:

#### RSI:
```python
'rsi14': {
    'period': 14,
    'description': 'Relative Strength Index (14 periods)',
    'requires': ['close']
}
```

#### MACD:
```python
'macd': {
    'fast_period': 12,
    'slow_period': 26,
    'signal_period': 9,
    'description': 'MACD (12, 26, 9)',
    'requires': ['close']
}
```

#### Bollinger Bands:
```python
'bb_upper': {
    'period': 20,
    'std_dev': 2,
    'description': 'Bollinger Bands Upper (20, 2)',
    'requires': ['close']
}
```

## Использование

### Импорт всех индикаторов:

```python
from src.indicators.registry import AVAILABLE_INDICATORS, INDICATOR_CONFIG

# Получить список всех доступных индикаторов
print(f"Всего индикаторов: {len(AVAILABLE_INDICATORS)}")

# Получить конфигурацию конкретного индикатора
rsi_config = INDICATOR_CONFIG['rsi14']
print(f"RSI конфигурация: {rsi_config}")
```

### Импорт по категориям:

```python
from src.indicators.registry.ma import MA_INDICATORS, MA_CONFIG
from src.indicators.registry.oscillators import OSC_INDICATORS, OSC_CONFIG

# Работа с moving averages
print(f"Moving Averages: {MA_INDICATORS}")

# Работа с oscillators
print(f"Oscillators: {OSC_INDICATORS}")
```

### Проверка зависимостей:

```python
def check_indicator_requirements(indicator_name, available_data):
    """Проверяет, достаточно ли данных для расчета индикатора"""
    if indicator_name not in INDICATOR_CONFIG:
        return False

    required_data = INDICATOR_CONFIG[indicator_name]['requires']
    return all(data in available_data for data in required_data)

# Пример использования
available_data = ['close', 'high', 'low']
can_calculate_rsi = check_indicator_requirements('rsi14', available_data)
can_calculate_stoch = check_indicator_requirements('stoch_k', available_data)
```

## Интеграция с системой

### Связь с indicator_groups:

```python
# В indicator_groups используется registry для определения доступных индикаторов
from src.indicators.registry import AVAILABLE_INDICATORS

def calc_indicators(df, required_indicators):
    """Расчет индикаторов на основе registry"""
    available = set(required_indicators) & set(AVAILABLE_INDICATORS)
    # ... логика расчета
```

### Связь с signal calculator:

```python
# Signal calculator использует registry для валидации индикаторов
def validate_signal_indicators(indicators):
    """Проверяет, что все индикаторы доступны в registry"""
    return all(ind in AVAILABLE_INDICATORS for ind in indicators)
```

## Добавление новых индикаторов

### 1. Создание конфигурации:

```python
# В соответствующем файле категории (например, oscillators.py)
NEW_INDICATOR = 'new_oscillator'

OSC_INDICATORS.append(NEW_INDICATOR)

OSC_CONFIG[NEW_INDICATOR] = {
    'period': 14,
    'description': 'New Oscillator (14 periods)',
    'requires': ['close', 'volume']
}
```

### 2. Обновление __init__.py:

```python
# В __init__.py автоматически подхватываются новые индикаторы
# Никаких изменений не требуется
```

### 3. Реализация расчета:

```python
# В соответствующем файле indicator_groups добавить логику расчета
def calc_new_oscillator(df):
    # Логика расчета нового индикатора
    pass
```

## Валидация и проверки

### Проверка целостности registry:

```python
def validate_registry():
    """Проверяет целостность registry"""
    issues = []

    # Проверяем, что все индикаторы в списках имеют конфигурации
    for category in [MA_INDICATORS, OSC_INDICATORS, VOL_INDICATORS,
                    VOLU_INDICATORS, TREND_INDICATORS, SQUEEZE_INDICATORS]:
        for indicator in category:
            if indicator not in INDICATOR_CONFIG:
                issues.append(f"Missing config for {indicator}")

    return issues
```

### Проверка зависимостей:

```python
def validate_dependencies():
    """Проверяет корректность зависимостей"""
    valid_data = ['open', 'high', 'low', 'close', 'volume']
    issues = []

    for indicator, config in INDICATOR_CONFIG.items():
        for required in config['requires']:
            if required not in valid_data:
                issues.append(f"Invalid dependency {required} for {indicator}")

    return issues
```

## Рекомендации по использованию

### Организация индикаторов:
- Группируйте индикаторы по функциональности
- Используйте понятные имена индикаторов
- Документируйте параметры и зависимости

### Конфигурация:
- Указывайте все необходимые параметры
- Используйте стандартные периоды где возможно
- Описывайте назначение каждого индикатора

### Расширение:
- Следуйте существующей структуре при добавлении новых индикаторов
- Обновляйте документацию при изменениях
- Тестируйте новые индикаторы перед добавлением в registry

## Примеры использования

### Получение информации об индикаторе:

```python
def get_indicator_info(indicator_name):
    """Получает полную информацию об индикаторе"""
    if indicator_name not in INDICATOR_CONFIG:
        return None

    config = INDICATOR_CONFIG[indicator_name]
    return {
        'name': indicator_name,
        'description': config['description'],
        'parameters': {k: v for k, v in config.items()
                      if k not in ['description', 'requires']},
        'requires': config['requires']
    }

# Пример
rsi_info = get_indicator_info('rsi14')
print(f"RSI Info: {rsi_info}")
```

### Фильтрация индикаторов по требованиям:

```python
def get_indicators_by_requirements(available_data):
    """Возвращает индикаторы, которые можно рассчитать с доступными данными"""
    available_indicators = []

    for indicator, config in INDICATOR_CONFIG.items():
        if all(req in available_data for req in config['requires']):
            available_indicators.append(indicator)

    return available_indicators

# Пример
basic_data = ['close']
volume_data = ['close', 'volume']
full_data = ['open', 'high', 'low', 'close', 'volume']

basic_indicators = get_indicators_by_requirements(basic_data)
volume_indicators = get_indicators_by_requirements(volume_data)
full_indicators = get_indicators_by_requirements(full_data)
```
