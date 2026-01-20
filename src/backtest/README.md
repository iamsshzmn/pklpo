# Backtest Module

Модуль для бэктестинга и оценки качества торговых сигналов. Предоставляет инструменты для анализа эффективности торговых стратегий с использованием исторических данных.

## Обзор

Модуль `backtest` предназначен для:
- Оценки качества торговых сигналов на исторических данных
- Расчета ключевых метрик производительности (PnL, Sharpe Ratio, Max Drawdown)
- Анализа эффективности торговых стратегий
- Генерации отчетов о результатах бэктестинга

## Структура модуля

### Основные компоненты:

#### 1. Метрики (`metrics.py`)
Набор функций для расчета ключевых метрик производительности:

##### `calc_pnl(signals, prices, commission)`
Рассчитывает прибыль/убыток на основе сигналов и цен:

**Параметры:**
- `signals`: список сигналов [{'ts': timestamp, 'signal': -1/0/1, 'reason': str}]
- `prices`: список цен [{'ts': timestamp, 'open': float, 'high': float, 'low': float, 'close': float}]
- `commission`: комиссия за сделку (по умолчанию 0.05%)

**Возвращает:**
- `Tuple[List[float], float]`: (список PnL, общий PnL)

**Логика торговли:**
- Сигнал 1: открытие длинной позиции
- Сигнал -1: открытие короткой позиции
- Сигнал 0: удержание текущей позиции

##### `calc_sharpe_ratio(pnl_list, risk_free_rate)`
Рассчитывает коэффициент Шарпа:

**Параметры:**
- `pnl_list`: список значений PnL
- `risk_free_rate`: безрисковая ставка (по умолчанию 2% годовых)

**Формула:**
```
Sharpe = (Mean Return - Risk Free Rate) / Standard Deviation
```

##### `calc_max_drawdown(pnl_list)`
Рассчитывает максимальную просадку:

**Параметры:**
- `pnl_list`: список значений PnL

**Возвращает:**
- Максимальную просадку в процентах

##### `calc_win_rate(pnl_list)`
Рассчитывает процент прибыльных сделок:

**Параметры:**
- `pnl_list`: список значений PnL

**Возвращает:**
- Процент прибыльных сделок

##### `calc_metrics(signals, prices, commission)`
Рассчитывает все метрики качества сигналов:

**Возвращает:**
```python
{
    'total_pnl': float,           # Общий PnL
    'total_pnl_percent': float,   # Общий PnL в процентах
    'sharpe_ratio': float,        # Коэффициент Шарпа
    'max_drawdown': float,        # Максимальная просадка
    'win_rate': float,            # Процент прибыльных сделок
    'total_trades': int,          # Общее количество сделок
    'avg_trade_pnl': float        # Средний PnL за сделку
}
```

#### 2. Оценщик сигналов (`evaluate.py`)

##### `SignalEvaluator`
Основной класс для оценки качества торговых сигналов:

**Инициализация:**
```python
evaluator = SignalEvaluator(commission=0.0005)
```

**Основные методы:**

###### `evaluate_symbol(symbol, timeframe, days_back)`
Оценивает качество сигналов для конкретного символа:

**Параметры:**
- `symbol`: торговый символ (например, "BTC-USDT")
- `timeframe`: таймфрейм (по умолчанию '1m')
- `days_back`: количество дней назад для анализа (по умолчанию 7)

**Возвращает:**
- Словарь с результатами оценки

###### `evaluate_all_symbols(timeframe, days_back)`
Оценивает качество сигналов для всех символов:

**Параметры:**
- `timeframe`: таймфрейм (по умолчанию '1m')
- `days_back`: количество дней назад для анализа (по умолчанию 7)

**Возвращает:**
- Список результатов для всех символов

## Использование

### Базовое использование:

```python
import asyncio
from src.backtest import SignalEvaluator

async def evaluate_strategy():
    # Создаем оценщик
    evaluator = SignalEvaluator(commission=0.0005)

    # Оцениваем конкретный символ
    result = await evaluator.evaluate_symbol("BTC-USDT", timeframe='1m', days_back=7)

    if result:
        print(f"PnL: {result['total_pnl_percent']:.2f}%")
        print(f"Sharpe: {result['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {result['max_drawdown']:.2f}%")
        print(f"Win Rate: {result['win_rate']:.1f}%")

# Запуск
asyncio.run(evaluate_strategy())
```

### Оценка всех символов:

```python
async def evaluate_all():
    evaluator = SignalEvaluator()

    # Оцениваем все символы
    results = await evaluator.evaluate_all_symbols(days_back=7)

    # Анализируем результаты
    for result in results:
        print(f"{result['symbol']}: PnL={result['total_pnl_percent']:.2f}%, "
              f"Sharpe={result['sharpe_ratio']:.2f}")

asyncio.run(evaluate_all())
```

### Использование отдельных метрик:

```python
from src.backtest.metrics import calc_pnl, calc_sharpe_ratio, calc_max_drawdown

# Пример данных
signals = [
    {'ts': 1640995200000, 'signal': 1, 'reason': 'buy'},
    {'ts': 1640995260000, 'signal': -1, 'reason': 'sell'}
]

prices = [
    {'ts': 1640995200000, 'open': 50000, 'high': 50100, 'low': 49900, 'close': 50050},
    {'ts': 1640995260000, 'open': 50050, 'high': 50200, 'low': 50000, 'close': 50150}
]

# Рассчитываем метрики
pnl_list, total_pnl = calc_pnl(signals, prices, commission=0.0005)
sharpe = calc_sharpe_ratio(pnl_list)
max_dd = calc_max_drawdown(pnl_list)

print(f"Total PnL: {total_pnl:.4f}")
print(f"Sharpe Ratio: {sharpe:.2f}")
print(f"Max Drawdown: {max_dd:.2f}%")
```

## Запуск через CLI

### Оценка всех символов:
```bash
python src/backtest/evaluate.py
```

### Программный запуск:
```python
if __name__ == "__main__":
    asyncio.run(main())
```

## Конфигурация

### Параметры комиссии:
- **По умолчанию**: 0.05% (0.0005)
- **Настраивается**: при создании SignalEvaluator

### Периоды анализа:
- **По умолчанию**: 7 дней назад
- **Настраивается**: параметр days_back

### Таймфреймы:
- **По умолчанию**: 1m
- **Поддерживаемые**: 1m, 5m, 15m, 1H, 4H, 1Dutc

## Структура данных

### Сигналы:
```python
{
    'ts': int,           # timestamp в миллисекундах
    'signal': int,       # -1 (sell), 0 (hold), 1 (buy)
    'reason': str,       # причина сигнала
    'created_at': datetime  # время создания
}
```

### Цены OHLCV:
```python
{
    'ts': int,           # timestamp в миллисекундах
    'open': float,       # цена открытия
    'high': float,       # максимальная цена
    'low': float,        # минимальная цена
    'close': float,      # цена закрытия
    'volume': float      # объем
}
```

### Результаты оценки:
```python
{
    'symbol': str,                    # торговый символ
    'timeframe': str,                 # таймфрейм
    'period_days': int,               # период анализа
    'signals_count': int,             # количество сигналов
    'prices_count': int,              # количество цен
    'commission': float,              # комиссия
    'total_pnl': float,               # общий PnL
    'total_pnl_percent': float,       # общий PnL в процентах
    'sharpe_ratio': float,            # коэффициент Шарпа
    'max_drawdown': float,            # максимальная просадка
    'win_rate': float,                # процент прибыльных сделок
    'total_trades': int,              # общее количество сделок
    'avg_trade_pnl': float            # средний PnL за сделку
}
```

## Интеграция с системой

### Зависимости:
- **Database**: получение сигналов и цен из базы данных
- **Signals**: анализ торговых сигналов
- **Candles**: исторические OHLCV данные

### Связь с другими модулями:
- **Tuning**: оптимизация параметров на основе результатов бэктестинга
- **Visual**: визуализация результатов бэктестинга
- **Alerts**: уведомления о результатах оценки

## Рекомендации по использованию

### Выбор периода анализа:
- **Краткосрочный**: 1-7 дней для быстрой оценки
- **Среднесрочный**: 30-90 дней для стабильной оценки
- **Долгосрочный**: 180-365 дней для долгосрочной стратегии

### Интерпретация метрик:
- **Sharpe Ratio > 1**: хорошая стратегия
- **Sharpe Ratio > 2**: отличная стратегия
- **Max Drawdown < 10%**: низкий риск
- **Win Rate > 50%**: положительное математическое ожидание

### Оптимизация:
- Тестируйте различные периоды
- Анализируйте влияние комиссий
- Сравнивайте разные таймфреймы

## Примеры использования

### Сравнение стратегий:

```python
async def compare_strategies():
    evaluator = SignalEvaluator()

    # Тестируем разные периоды
    periods = [1, 7, 30, 90]

    for days in periods:
        print(f"\n📊 Анализ за {days} дней:")
        results = await evaluator.evaluate_all_symbols(days_back=days)

        if results:
            avg_pnl = sum(r['total_pnl_percent'] for r in results) / len(results)
            avg_sharpe = sum(r['sharpe_ratio'] for r in results) / len(results)

            print(f"   Средний PnL: {avg_pnl:.2f}%")
            print(f"   Средний Sharpe: {avg_sharpe:.2f}")

asyncio.run(compare_strategies())
```

### Анализ лучших символов:

```python
async def find_best_symbols():
    evaluator = SignalEvaluator()
    results = await evaluator.evaluate_all_symbols(days_back=30)

    if results:
        # Сортируем по Sharpe Ratio
        best_sharpe = sorted(results, key=lambda x: x['sharpe_ratio'], reverse=True)[:10]

        print("🏆 Топ-10 символов по Sharpe Ratio:")
        for i, result in enumerate(best_sharpe, 1):
            print(f"{i:2d}. {result['symbol']}: "
                  f"Sharpe={result['sharpe_ratio']:.2f}, "
                  f"PnL={result['total_pnl_percent']:.2f}%")

asyncio.run(find_best_symbols())
```

### Сохранение результатов:

```python
async def save_results():
    evaluator = SignalEvaluator()
    results = await evaluator.evaluate_all_symbols(days_back=7)

    if results:
        import json
        from datetime import datetime

        filename = f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        print(f"💾 Результаты сохранены в {filename}")

asyncio.run(save_results())
```

## Мониторинг и логирование

### Логирование:
- Информационные сообщения о процессе оценки
- Ошибки при получении данных
- Результаты расчета метрик

### Метрики:
- Время выполнения оценки
- Количество обработанных символов
- Статистика по результатам

### Алерты:
- Ошибки подключения к базе данных
- Отсутствие данных для анализа
- Аномальные результаты метрик
