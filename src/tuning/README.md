# Tuning Module

Модуль для оптимизации параметров торговых сигналов. Содержит инструменты для автоматической настройки порогов индикаторов и весов правил с использованием методов машинного обучения.

## Обзор

Модуль `tuning` предназначен для:
- Автоматической оптимизации порогов индикаторов (RSI, ADX, Stochastic и др.)
- Оптимизации весов правил сигналов
- Бэктестинга различных комбинаций параметров
- Поиска оптимальных настроек для максимизации прибыли и минимизации рисков

## Структура модуля

### 1. Grid Search Optimizer (`grid_search.py`)
**Класс:** `GridSearchOptimizer`

Метод полного перебора (grid search) для оптимизации порогов индикаторов:

#### Оптимизируемые параметры:
- **RSI**: `rsi_buy` (20-35), `rsi_sell` (65-80)
- **ADX**: `adx_threshold` (20-35)
- **Stochastic**: `stoch_k_buy` (10-25), `stoch_k_sell` (75-90)
- **Score thresholds**: `min_score_for_buy` (2-5), `min_score_for_sell` (-5 to -2)

#### Основные методы:
```python
async def optimize_parameters(
    symbols: List[str] = None,
    timeframe: str = '1m',
    days_back: int = 7,
    max_drawdown_limit: float = 20.0
) -> Dict
```

### 2. Weight Optimizer (`opt_weights.py`)
**Класс:** `WeightOptimizer`

Метод случайного поиска (random search) для оптимизации весов правил:

#### Оптимизируемые веса:
- **EMA21/SMA50**: (0.5, 2.0)
- **SMA50/SMA200**: (1.0, 3.0) - более важный
- **MACD**: (0.8, 2.0)
- **ADX14**: (0.8, 2.0)
- **Ichimoku**: (0.8, 2.0)
- **RSI14**: (0.5, 2.0)
- **Bollinger**: (0.5, 2.0)
- **Stochastic**: (0.5, 2.0)
- **Keltner**: (0.5, 2.0)
- **OBV/CMF**: (0.3, 1.5) - менее важный

#### Основные методы:
```python
async def optimize_weights(
    symbols: List[str] = None,
    timeframe: str = '1m',
    days_back: int = 7,
    iterations: int = 100,
    max_drawdown_limit: float = 20.0
) -> Dict
```

## Использование

### Grid Search оптимизация

```python
from src.tuning import GridSearchOptimizer

# Создаем оптимизатор
optimizer = GridSearchOptimizer(commission=0.0005)

# Запускаем оптимизацию
best_params = await optimizer.optimize_parameters(
    symbols=['BTC-USDT', 'ETH-USDT'],
    timeframe='1m',
    days_back=7,
    max_drawdown_limit=20.0
)

print(f"Лучшие параметры: {best_params}")
```

### Оптимизация весов

```python
from src.tuning import WeightOptimizer

# Создаем оптимизатор весов
weight_optimizer = WeightOptimizer(commission=0.0005)

# Запускаем оптимизацию
best_weights = await weight_optimizer.optimize_weights(
    symbols=['BTC-USDT', 'ETH-USDT'],
    timeframe='1m',
    days_back=7,
    iterations=100,
    max_drawdown_limit=20.0
)

print(f"Лучшие веса: {best_weights}")
```

## Метрики оценки

Оба оптимизатора используют следующие метрики для оценки качества:

### Основные метрики:
- **Sharpe Ratio**: отношение доходности к риску
- **Total Return**: общая доходность
- **Max Drawdown**: максимальная просадка
- **Win Rate**: процент прибыльных сделок
- **Profit Factor**: отношение прибыли к убыткам

### Ограничения:
- `max_drawdown_limit`: максимальная допустимая просадка (по умолчанию 20%)
- Фильтрация результатов по качеству сигналов

## Результаты

### Сохранение результатов:
- **JSON файлы**: детальные результаты всех тестов
- **CSV файлы**: сводные таблицы для анализа
- **Логи**: подробные логи процесса оптимизации

### Структура результатов:
```json
{
    "best_parameters": {...},
    "best_metrics": {
        "sharpe_ratio": 1.85,
        "total_return": 15.2,
        "max_drawdown": 8.5,
        "win_rate": 0.65
    },
    "all_results": [...],
    "optimization_time": "2024-01-15T10:30:00"
}
```

## Зависимости

- `asyncio`: асинхронное выполнение
- `pandas`: обработка данных
- `numpy`: численные вычисления
- `src.database`: работа с базой данных
- `src.signals`: расчет сигналов
- `src.backtest`: бэктестинг

## Интеграция

Модуль интегрирован с:
- **Signal Calculator**: пересчет сигналов с новыми параметрами
- **Signal Evaluator**: оценка качества сигналов
- **Database**: сохранение и загрузка конфигураций
- **Logging**: детальное логирование процесса

## Рекомендации по использованию

### Для Grid Search:
1. Начните с небольшого количества символов (5-10)
2. Используйте короткий период бэктестинга (3-7 дней)
3. Установите разумные ограничения по просадке (15-25%)

### Для Weight Optimization:
1. Используйте больше итераций (100-500) для лучших результатов
2. Тестируйте на различных рыночных условиях
3. Регулярно пересматривайте диапазоны весов

### Общие рекомендации:
- Запускайте оптимизацию в неактивные часы торгов
- Сохраняйте промежуточные результаты
- Анализируйте стабильность результатов на разных периодах
- Не переоптимизируйте - используйте out-of-sample тестирование

## Примеры запуска

### Через CLI:
```bash
# Grid search оптимизация
python -m src.tuning.grid_search

# Оптимизация весов
python -m src.tuning.opt_weights
```

### Программно:
```python
import asyncio
from src.tuning import GridSearchOptimizer, WeightOptimizer

async def main():
    # Grid search
    grid_optimizer = GridSearchOptimizer()
    grid_results = await grid_optimizer.optimize_parameters()

    # Weight optimization
    weight_optimizer = WeightOptimizer()
    weight_results = await weight_optimizer.optimize_weights()

if __name__ == "__main__":
    asyncio.run(main())
```
