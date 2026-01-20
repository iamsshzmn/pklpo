# MTF Интеграция с существующими системами

## Обзор

MTF (Multi-Timeframe) интеграция предоставляет дополнительную точку зрения на рынок, дополняя существующие расчёты без их замены. Это позволяет получить более точные результаты, имея несколько источников анализа.

## Архитектура интеграции

### 1. MTF Integrator (`src/mtf/integrator.py`)
- **MTFIntegrator** - основной класс для работы с MTF данными
- **MTFSignalData** - структура данных MTF сигнала
- Методы для получения и анализа MTF сигналов

### 2. MTF-улучшенный Position Calculator (`src/positions/calculator_mtf.py`)
- **MTFEnhancedPositionCalculator** - расширяет базовый калькулятор
- Корректирует размер позиции на основе MTF уверенности
- Адаптирует стоп-лосс на основе MTF context_score
- Улучшает take-profit на основе MTF вероятностей разворота

### 3. MTF-улучшенный Scoring Engine (`src/scoring_engine/compute_mtf.py`)
- **MTFEnhancedScoringEngine** - расширяет базовый scoring engine
- Корректирует score_calibrated на основе MTF consensus
- Улучшает p_win на основе MTF уверенности
- Адаптирует edge_net на основе MTF context_score

### 4. MTF-улучшенный Trade Recommender (`src/trade_recommender/recommend_mtf.py`)
- **MTFEnhancedTradeRecommender** - расширяет базовый recommender
- Корректирует направление на основе сильных MTF сигналов
- Улучшает размер позиции на основе MTF уверенности
- Адаптирует стоп и take-profit на основе MTF данных

## Использование

### 1. CLI для MTF интеграции

```bash
# Расчёт позиций с MTF интеграцией
python src/mtf_integration_cli.py positions --symbol BTC-USDT --mtf-weight 0.3

# Расчёт scores с MTF интеграцией
python src/mtf_integration_cli.py scoring --symbol BTC-USDT --mtf-weight 0.25

# Генерация рекомендаций с MTF интеграцией
python src/mtf_integration_cli.py recommendations --limit 100 --mtf-weight 0.3

# Валидация MTF выравнивания
python src/mtf_integration_cli.py validate --symbol BTC-USDT
```

### 2. Интеграция в основной pipeline

```bash
# Запуск всех этапов с MTF интеграцией
python src/main_with_options.py --all --mtf-integration --mtf-weight 0.3

# Только MTF интеграция
python src/main_with_options.py --mtf-integration --mtf-weight 0.3

# MTF интеграция для конкретного символа
python src/main_with_options.py --mtf-integration --symbol BTC-USDT --mtf-weight 0.3
```

### 3. Программное использование

```python
from src.mtf.integrator import mtf_integrator
from src.positions.calculator_mtf import MTFEnhancedPositionCalculator
from src.scoring_engine.compute_mtf import mtf_scoring_engine
from src.trade_recommender.recommend_mtf import mtf_trade_recommender

# Получение MTF сигнала
mtf_data = await mtf_integrator.get_latest_mtf_signal("BTC-USDT")

# Расчёт позиции с MTF
calculator = MTFEnhancedPositionCalculator()
result = await calculator.calculate_position_with_mtf(position_data, use_mtf=True, mtf_weight=0.3)

# Расчёт score с MTF
score_result = await mtf_scoring_engine.compute_score_with_mtf("BTC-USDT", "1m", timestamp, use_mtf=True)

# Рекомендация с MTF
recommendation = await mtf_trade_recommender.recommend_for_score_with_mtf(score_id, use_mtf=True)
```

## Алгоритмы корректировки

### 1. Корректировка размера позиции
```python
# Увеличиваем размер при высокой MTF уверенности
confidence_multiplier = 1.0 + (mtf_confidence - 0.5) * mtf_weight
enhanced_size = base_size * confidence_multiplier
```

### 2. Корректировка стоп-лосса
```python
# При сильном тренде увеличиваем расстояние стопа
context_multiplier = 1.0 + abs(mtf_data.context_score) * mtf_weight * 0.5
new_stop_distance = base_stop_distance * context_multiplier
```

### 3. Корректировка take-profit
```python
# Увеличиваем take-profit при высокой вероятности разворота
if mtf_data.consensus == 1:  # LONG
    tp_multiplier = 1.0 + mtf_data.p_reversal_up * mtf_weight
else:  # SHORT
    tp_multiplier = 1.0 + mtf_data.p_reversal_down * mtf_weight
```

### 4. Корректировка score
```python
# Увеличиваем score при совпадении направления
if mtf_data.consensus == 1:  # MTF LONG
    mtf_boost = mtf_confidence * mtf_weight
    enhanced_score = min(1.0, base_score + mtf_boost)
elif mtf_data.consensus == -1:  # MTF SHORT
    mtf_boost = mtf_confidence * mtf_weight
    enhanced_score = max(0.0, base_score - mtf_boost)
```

## Валидация MTF выравнивания

### 1. Проверка соответствия направления
```python
# Позиции
is_aligned = (
    (direction == "LONG" and mtf_direction == "LONG") or
    (direction == "SHORT" and mtf_direction == "SHORT")
)

# Scores
is_aligned = (
    (score_direction == "LONG" and mtf_direction == "LONG") or
    (score_direction == "SHORT" and mtf_direction == "SHORT") or
    (score_direction == "FLAT" and mtf_direction == "FLAT")
)
```

### 2. Проверка уверенности
```python
# Минимальная уверенность MTF сигнала
is_confident = mtf_confidence >= min_confidence  # по умолчанию 0.4
```

## Метрики и статистика

### 1. MTF улучшение позиций
- Процент позиций, улучшенных MTF данными
- Статистика по размерам позиций до/после корректировки

### 2. MTF выравнивание scores
- Процент scores, выровненных с MTF сигналами
- Статистика по направлениям и уверенности

### 3. MTF выравнивание рекомендаций
- Процент рекомендаций, выровненных с MTF сигналами
- Статистика по направлениям и параметрам

## Настройка весов

### Рекомендуемые значения mtf_weight:

- **0.1-0.2**: Консервативная интеграция (минимальное влияние)
- **0.3-0.4**: Умеренная интеграция (баланс)
- **0.5-0.6**: Агрессивная интеграция (сильное влияние)
- **0.7+**: Очень агрессивная интеграция (максимальное влияние)

### Примеры использования:

```bash
# Консервативная интеграция
python src/main_with_options.py --mtf-integration --mtf-weight 0.2

# Умеренная интеграция (по умолчанию)
python src/main_with_options.py --mtf-integration --mtf-weight 0.3

# Агрессивная интеграция
python src/main_with_options.py --mtf-integration --mtf-weight 0.5
```

## Логирование

MTF интеграция создаёт подробные логи:

- `mtf_integration.log` - основной лог MTF интеграции
- `app.log` - лог основного приложения с MTF интеграцией

### Примеры логов:

```
🧭 MTF анализ для BTC-USDT:
  Направление: LONG
  Уверенность: 0.750
  Сила: STRONG
  Context Score: 0.450
  Bias: long

MTF корректировка размера позиции: 1.075
MTF корректировка стопа: 1.225
MTF корректировка take-profit: 1.180

🧭 BTC-USDT: MTF выравнивание подтверждено
```

## Преимущества интеграции

1. **Дополнительная точка зрения**: MTF данные предоставляют контекст на разных таймфреймах
2. **Повышение точности**: Корректировки на основе MTF сигналов улучшают качество решений
3. **Гибкость**: Настраиваемые веса позволяют контролировать влияние MTF
4. **Обратная совместимость**: Существующие системы продолжают работать без изменений
5. **Валидация**: Встроенные проверки выравнивания обеспечивают качество интеграции

## Ограничения

1. **Зависимость от MTF данных**: Интеграция требует наличия актуальных MTF сигналов
2. **Настройка весов**: Неправильные веса могут ухудшить результаты
3. **Производительность**: Дополнительные запросы к БД могут замедлить обработку
4. **Сложность**: Увеличение сложности системы требует дополнительного тестирования
