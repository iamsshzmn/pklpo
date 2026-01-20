# Модуль позиций на SWAP инструментах

Модуль для расчёта позиций на SWAP инструментах согласно техническому заданию.

## 🎯 Основная функциональность

### Алгоритм расчёта позиций

1. **Загрузка метаданных** (tick/lot, MMR, fees, max L)
2. **Сбор OHLCV данных** (spot и swap)
3. **Расчёт индикаторов** (ATR14, RSI, EMA, consensus)
4. **Проверка сигналов** (consensus ≥ threshold, signal_age ≤ max)
5. **Определение стопа** (percent или atr_mult)
6. **Расчёт риска и размера позиции** (R = balance × risk_pct, Qty = R / (Stop% × P))
7. **Проверка ликвидации** (d_liq ≈ 1/L - MMR - fee)
8. **Корректировка плеча** при необходимости
9. **Формирование ордеров** (Entry, Stop-loss, Take-profit)

## 📁 Структура модуля

```
src/positions/
├── __init__.py          # Инициализация модуля
├── models.py            # Модели данных (SQLAlchemy)
├── validator.py         # Валидатор обязательных данных
├── calculator.py        # Основной калькулятор позиций
├── cli.py              # CLI для работы с позициями
└── README.md           # Документация
```

## 🗄️ Модели данных

### SwapMetadata
Метаданные SWAP инструмента:
- `symbol` - символ инструмента
- `margin_mode` - режим маржи (isolated/cross)
- `tick_size`, `lot_size` - размеры тика и лота
- `maker_fee`, `taker_fee` - комиссии
- `maintenance_margin_rate` - MMR
- `max_leverage` - максимальное плечо
- `funding_rate` - ставка финансирования

### UserSettings
Пользовательские настройки:
- `balance_usdt` - баланс в USDT
- `risk_per_trade_pct` - риск на сделку (%)
- `leverage_target` - целевое плечо
- `default_stop_pct` - стоп по умолчанию
- `default_tp_pct` - тейк-профит по умолчанию

### PositionCalculation
Результат расчёта позиции:
- `symbol` - символ
- `position_size` - размер позиции
- `position_value_usdt` - стоимость позиции
- `entry_price` - цена входа
- `stop_loss_price` - цена стопа
- `take_profit_prices` - цены тейк-профитов
- `risk_amount_usdt` - сумма риска
- `leverage_used` - использованное плечо
- `margin_required` - требуемая маржа
- `liquidation_distance_pct` - расстояние до ликвидации

### PositionOrder
Детали ордеров:
- `calculation_id` - ссылка на расчёт
- `order_type` - тип ордера (entry/stop/tp)
- `price` - цена ордера
- `size` - размер ордера
- `status` - статус ордера

## 🔧 Валидация данных

Система проверяет **5 блоков обязательных данных**:

### Блок 1: Биржевые метаданные
- `symbol` - символ с суффиксом -SWAP
- `margin_mode` - isolated/cross
- `tick_size`, `lot_size` - положительные числа
- `maker_fee`, `taker_fee` - комиссии
- `maintenance_margin_rate` - MMR
- `max_leverage` - целое число ≤ 1000

### Блок 2: Рыночные данные
- `spot_ohlcv`, `swap_ohlcv` - минимум 200 баров
- `P_last` - последняя цена (положительная)

### Блок 3: Параметры пользователя
- `balance_usdt` - баланс > 0
- `risk_per_trade_pct` - риск 0.1-10%
- `leverage_target` - плечо 1-100

### Блок 4: Условия сделки
- `direction` - long/short
- `stop_method` - percent/atr_mult
- `stop_value` - значение стопа
- `tp_levels_pct` - уровни тейк-профитов
- `order_type_entry` - тип ордера входа

### Блок 5: Контроль сигналов
- `consensus_threshold` - порог consensus
- `timeframe_entry` - таймфрейм
- `signal_age_max` - максимальный возраст сигнала

## 🚀 Использование

### Через основную систему

```bash
# Расчёт позиций для всех SWAP инструментов
python src/main_with_options.py --positions

# Расчёт позиций для конкретного символа
python src/main_with_options.py --positions --symbol BTC-USDT-SWAP

# Полный цикл с позициями
python src/main_with_options.py --all
```

### Через CLI позиций

```bash
# Список доступных SWAP инструментов
python src/positions/cli.py --list

# Расчёт позиции для конкретного символа
python src/positions/cli.py --calculate BTC-USDT-SWAP

# Расчёт с кастомными параметрами
python src/positions/cli.py --calculate BTC-USDT-SWAP --balance 50000 --risk 1.5 --leverage 20

# История расчётов
python src/positions/cli.py --history BTC-USDT-SWAP

# Тестирование параметров
python src/positions/cli.py --test BTC-USDT-SWAP
```

### Программное использование

```python
from src.positions.calculator import PositionCalculator

# Создаём калькулятор
calculator = PositionCalculator()

# Данные для расчёта
position_data = {
    # Блок 1: Биржевые метаданные
    "symbol": "BTC-USDT-SWAP",
    "margin_mode": "isolated",
    "tick_size": 0.1,
    "lot_size": 1,
    "maker_fee": 0.0001,
    "taker_fee": 0.0005,
    "maintenance_margin_rate": 0.005,
    "max_leverage": 100,
    "funding_rate": 0.0001,

    # Блок 2: Рыночные данные
    "spot_ohlcv": [...],  # 200+ баров
    "swap_ohlcv": [...],  # 200+ баров
    "P_last": 50000,

    # Блок 3: Параметры пользователя
    "balance_usdt": 10000,
    "risk_per_trade_pct": 0.02,  # 2%
    "leverage_target": 10,

    # Блок 4: Условия сделки
    "direction": "long",
    "stop_method": "percent",
    "stop_value": 0.03,  # 3%
    "tp_levels_pct": [0.03, 0.06],
    "order_type_entry": "market",
    "slippage_pct": 0.001,

    # Блок 5: Контроль сигналов
    "consensus_threshold": 1.0,
    "timeframe_entry": "1m",
    "signal_age_max": 60
}

# Рассчитываем позицию
result = calculator.calculate_position(position_data)

if result.is_valid:
    print(f"Размер позиции: {result.position_size}")
    print(f"Стоимость: {result.position_value_usdt} USDT")
    print(f"Риск: {result.risk_amount_usdt} USDT")
    print(f"Плечо: {result.leverage_used}")
else:
    print("Ошибки валидации:")
    for error in result.validation_errors:
        print(f"- {error}")
```

## 📊 Примеры результатов

### Успешный расчёт
```
📊 Результаты расчёта позиции для BTC-USDT-SWAP
============================================================
✅ Статус: Успешно
💰 Размер позиции: 12.698413
💵 Стоимость позиции: 1333.33 USDT
📈 Цена входа: 105.0000
🛑 Стоп-лосс: 101.8500
🎯 Тейк-профиты: ['108.1500', '111.3000']
⚠️ Риск: 20.00 USDT
📏 Расстояние стопа: 3.00%
⚡ Использованное плечо: 10
💳 Требуемая маржа: 2.00 USDT
🚨 Расстояние до ликвидации: 9.45%
============================================================
```

### Ошибка валидации
```
❌ Статус: Ошибка
🚫 Ошибки:
   - Consensus (0.5) ниже порога (1.0)
   - Недостаточно данных OHLCV: 150 баров (требуется 200+)
```

## 🔍 Тестирование

```bash
# Тест валидатора
python test_position_validator.py

# Тест калькулятора
python test_position_calculator.py
```

## 📝 Важные особенности

1. **Обязательная валидация** - без заполнения каждой ячейки расчёт НЕ выполняется
2. **Точные расчёты** - используется `Decimal` для финансовых вычислений
3. **Проверка ликвидации** - автоматическая корректировка плеча при необходимости
4. **Гибкая настройка** - поддержка различных методов стопа и тейк-профитов
5. **Интеграция с сигналами** - связь с существующей системой сигналов

## 🚨 Ограничения

- Требуется минимум 200 баров OHLCV данных
- Consensus должен быть ≥ threshold
- Возраст сигнала должен быть ≤ max_age
- Баланс должен быть достаточным для маржи
- Плечо не может превышать максимальное для инструмента
