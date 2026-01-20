# Scoring Engine

Модуль для вычисления итогового `score` на основе индикаторов и комбинаций. Объединяет расчёты в единый `score_raw ∈ [0;1]`, калибрует его и сохраняет результат в БД.

## 📁 Структура модуля

```
scoring_engine/
├── __init__.py          # Экспорты модуля
├── models.py            # Модели SQLAlchemy
├── compute.py           # Основная логика вычислений
├── cli.py              # CLI интерфейс
├── weights_extended.yaml        # Расширенная конфигурация весов (50+ индикаторов)
└── README.md           # Документация
```

## 🗄️ Таблица `score_results`

```sql
CREATE TABLE score_results (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    ts BIGINT NOT NULL,
    score_raw NUMERIC(5, 4),        -- Сырой score [0;1]
    score_calibrated NUMERIC(5, 4), -- Калиброванный score [0;1]
    p_win NUMERIC(5, 4),           -- Вероятность выигрыша
    edge_net NUMERIC(7, 4),        -- Чистое преимущество
    confidence NUMERIC(5, 4),      -- Уверенность [0;1]
    is_valid BOOLEAN DEFAULT TRUE, -- Валидность результата
    reasons TEXT[],                -- Причины отклонения
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## ⚙️ Конфигурация весов

Файл `weights_extended.yaml` содержит:

- **Веса индикаторов**: RSI, MACD, Bollinger Bands, ADX, OBV, CMF, VWAP, EMA21
- **Веса комбинаций**: bbands_kc_ttm, ichimoku_macd_rsi, macd_rsi_bbands
- **Параметры нормализации**: границы для приведения значений к [0;1]
- **Торговые параметры**: reward/risk ratio, комиссии

## 🧠 Алгоритм вычисления

### 1. Получение данных
- Извлекает последние значения из таблиц `indicators` и `combination_results`
- Проверяет наличие всех необходимых полей

### 2. Нормализация
- Приводит значения индикаторов к диапазону [0;1]
- Специальная обработка для относительных индикаторов (BB, KC, EMA, VWAP)

### 3. Вычисление score_raw
```
score_raw = Σ (вес_i × нормализованное_значение_i)
```

### 4. Калибровка
- Пока что `score_calibrated = score_raw`
- В будущем: линейная модель по историческим hitrate

### 5. Дополнительные метрики
- `p_win = score_calibrated`
- `confidence = abs(score_calibrated - 0.5) * 2`
- `edge_net = (p_win - 0.5) × RR - cost`

## 🚀 Использование

### CLI интерфейс

```bash
# Вычисление score для конкретной пары и времени
python -m src.scoring_engine.cli --symbol BTC-USDT --tf 1m

# С указанием timestamp
python -m src.scoring_engine.cli --symbol BTC-USDT --tf 1m --ts 1704067200

# Подробный вывод
python -m src.scoring_engine.cli --symbol BTC-USDT --tf 1m --verbose
```

### Python API

```python
from src.scoring_engine.compute import compute_score

# Вычисление score
result = await compute_score("BTC-USDT", "1m", 1704067200)

if result:
    print(f"Score Raw: {result.score_raw:.4f}")
    print(f"Score Calibrated: {result.score_calibrated:.4f}")
    print(f"P(Win): {result.p_win:.4f}")
    print(f"Edge Net: {result.edge_net:.4f}")
    print(f"Confidence: {result.confidence:.4f}")
    print(f"Valid: {result.is_valid}")
```

## 🗄️ Миграция БД

```bash
# Создание таблицы score_results
python src/db/migrate_create_score_results.py
```

## 📊 Пример результата

| symbol   | timeframe | ts                  | score_raw | score_calibrated | p_win | edge_net | confidence | is_valid |
|----------|-----------|---------------------|-----------|------------------|-------|----------|------------|----------|
| BTC-USDT | 1m        | 2025-01-01 12:00:00 | 0.72      | 0.68             | 0.68  | 0.14     | 0.44       | TRUE     |

## 🔧 Настройка

### Изменение весов

Отредактируйте `weights_extended.yaml`:

```yaml
indicators:
  rsi14: 0.15        # Увеличить вес RSI
  macd_histogram: 0.2 # Увеличить вес MACD
  # ...

combinations:
  ichimoku_macd_rsi: 0.25  # Увеличить вес комбинации
```

### Добавление новых индикаторов

1. Добавьте индикатор в `weights_extended.yaml`
2. Добавьте нормализацию в секцию `normalization`
3. Обновите метод `get_indicator_value()` в `compute.py`

## 🧪 Тестирование

### Юнит-тесты
- Корректность расчёта `score_raw` по шаблону весов
- Валидация нормализации значений
- Проверка граничных случаев

### Интеграционные тесты
- Запись в `score_results`
- Обработка отсутствующих данных
- Производительность запросов

### Property-based тесты
- `0 ≤ score_calibrated ≤ 1`
- `confidence ≥ 0`
- `is_valid` корректно устанавливается

## 🔮 TODO

- [ ] Fallback на медианные значения при отсутствии индикаторов
- [ ] Перенос нормализации и калибровки в отдельные конфиги
- [ ] Версионирование расчётов (v1, v2…)
- [ ] Калибровка по историческим данным
- [ ] A/B тестирование различных весов
- [ ] Мониторинг качества score
- [ ] Интеграция с OrderManager

## 📈 Метрики качества

- **Hitrate**: процент успешных сделок
- **Sharpe Ratio**: риск-скорректированная доходность
- **Max Drawdown**: максимальная просадка
- **Win/Loss Ratio**: соотношение выигрышей/проигрышей

## 🔗 Интеграция

Модуль готов к интеграции с:
- **OrderManager**: для принятия решений о входе в сделку
- **Backtest**: для тестирования стратегий
- **Monitoring**: для отслеживания качества score
