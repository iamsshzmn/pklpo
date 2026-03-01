# Модуль управления настройками пользователей

Модуль `src/settings/` предоставляет полную систему управления пользовательскими настройками для расчёта позиций в торговой системе PKLPO.

## 🎯 Назначение

Система настроек позволяет:
- **Управлять параметрами риска** для каждого пользователя
- **Настраивать торговые параметры** (стопы, тейк-профиты, плечо)
- **Контролировать качество сигналов** через пороги консенсуса
- **Применять предустановленные профили** (консервативный, сбалансированный, агрессивный)
- **Валидировать настройки** перед использованием

## 📁 Структура модуля

```
src/settings/
├── __init__.py          # Инициализация модуля
├── defaults.py          # Настройки по умолчанию и пресеты
├── validator.py         # Валидация настроек
├── manager.py           # Менеджер настроек (CRUD операции)
├── cli.py              # Командная строка для управления
└── README.md           # Этот файл
```

## 🔧 Основные компоненты

### 1. DefaultSettings (`defaults.py`)
Настройки по умолчанию и предустановленные профили:

```python
from src.settings import DefaultSettings

# Получить настройки по умолчанию
settings = DefaultSettings.get_default_settings("user123")

# Применить пресет
preset_settings = DefaultSettings.get_preset_settings("conservative")

# Список доступных пресетов
presets = DefaultSettings.list_presets()  # ["conservative", "balanced", "aggressive"]
```

### 2. SettingsValidator (`validator.py`)
Валидация всех параметров настроек:

```python
from src.settings import SettingsValidator

# Валидация настроек
errors = SettingsValidator.validate_settings(settings)

# Специальная валидация для расчёта позиций
errors = SettingsValidator.validate_settings_for_position_calculation(settings)
```

### 3. UserSettingsManager (`manager.py`)
Основной менеджер для работы с настройками:

```python
from src.settings import UserSettingsManager

manager = UserSettingsManager()

# CRUD операции
await manager.create_user_settings("user123", settings)
await manager.get_user_settings("user123")
await manager.update_user_settings("user123", new_settings)
await manager.delete_user_settings("user123")

# Специальные операции
await manager.apply_preset("user123", "aggressive")
await manager.get_settings_for_position_calculation("user123")
```

### 4. SettingsCLI (`cli.py`)
Командная строка для управления настройками:

```bash
# Список пользователей
python src/settings/cli.py list

# Показать настройки
python src/settings/cli.py show user123

# Создать настройки с пресетом
python src/settings/cli.py create user123 --preset conservative

# Обновить настройки
python src/settings/cli.py update user123 --balance 15000 --risk 3

# Показать пресеты
python src/settings/cli.py presets

# Валидировать настройки
python src/settings/cli.py validate --file settings.json
```

## 📊 Параметры настроек

### Основные параметры риска:
- **balance_usdt** - баланс в USDT (1 - 1,000,000)
- **risk_per_trade_pct** - риск на сделку в % (0.1% - 10%)
- **leverage_target** - целевое плечо (1 - 100)

### Настройки торговли:
- **default_stop_method** - метод стопа ("percent", "atr_mult", "fixed")
- **default_stop_value** - значение стопа в % (0.1% - 100%)
- **default_tp_levels_pct** - уровни тейк-профита в % [список]
- **default_order_type_entry** - тип ордера входа ("market", "limit")
- **default_slippage_pct** - проскальзывание в % (0% - 100%)

### Настройки сигналов:
- **consensus_threshold** - порог консенсуса в % (0% - 100%)
- **timeframe_entry** - таймфрейм входа ("1m", "5m", "15m", "1H", "4H", "1D")
- **signal_age_max** - максимальный возраст сигнала в барах (1 - 1000)

## 🎯 Предустановленные профили

### Conservative (Консервативный)
- Баланс: 5,000 USDT
- Риск: 1% на сделку
- Плечо: 5x
- Стоп: 2%
- Консенсус: 8%

### Balanced (Сбалансированный)
- Баланс: 10,000 USDT
- Риск: 2% на сделку
- Плечо: 10x
- Стоп: 3%
- Консенсус: 5%

### Aggressive (Агрессивный)
- Баланс: 20,000 USDT
- Риск: 5% на сделку
- Плечо: 20x
- Стоп: 5%
- Консенсус: 3%

## 💻 Использование в коде

### Интеграция с расчётом позиций:

```python
from src.settings import UserSettingsManager

async def calculate_positions_with_user_settings(user_id: str):
    manager = UserSettingsManager()

    # Получаем настройки пользователя
    settings = await manager.get_settings_for_position_calculation(user_id)

    if settings is None:
        print(f"❌ Не удалось получить настройки для {user_id}")
        return

    # Используем настройки в расчёте позиций
    position_data = {
        "balance_usdt": settings["balance_usdt"],
        "risk_per_trade_pct": settings["risk_per_trade_pct"],
        "leverage_target": settings["leverage_target"],
        "consensus_threshold": settings["consensus_threshold"],
        # ... остальные параметры
    }

    # Расчёт позиции
    result = calculator.calculate_position(position_data)
```

### Создание пользователя с настройками:

```python
from src.settings import UserSettingsManager, DefaultSettings

async def setup_new_user(user_id: str, preset: str = "balanced"):
    manager = UserSettingsManager()

    # Создаём настройки с пресетом
    success = await manager.apply_preset(user_id, preset)

    if success:
        print(f"✅ Пользователь {user_id} создан с пресетом {preset}")
    else:
        print(f"❌ Ошибка при создании пользователя {user_id}")
```

## 🔍 Валидация

Система автоматически валидирует все настройки:

```python
from src.settings import SettingsValidator

# Проверка отдельных полей
is_valid, error = SettingsValidator.validate_balance_usdt(10000)
is_valid, error = SettingsValidator.validate_risk_per_trade_pct(0.02)

# Полная валидация
errors = SettingsValidator.validate_settings(settings)
if errors:
    for error in errors:
        print(f"❌ {error.field}: {error.message}")
```

## 📝 Примеры использования

### 1. Создание пользователя через CLI:

```bash
# Создать пользователя с консервативным профилем
python src/settings/cli.py create trader1 --preset conservative

# Создать пользователя с кастомными настройками
python src/settings/cli.py create trader2 --file my_settings.json
```

### 2. Обновление настроек:

```bash
# Изменить баланс и риск
python src/settings/cli.py update trader1 --balance 15000 --risk 2.5

# Применить агрессивный профиль
python src/settings/cli.py update trader1 --preset aggressive
```

### 3. Просмотр настроек:

```bash
# Показать всех пользователей
python src/settings/cli.py list

# Показать настройки конкретного пользователя
python src/settings/cli.py show trader1

# Показать в JSON формате
python src/settings/cli.py show trader1 --json
```

### 4. Валидация файла настроек:

```bash
# Создать файл settings.json
echo '{
  "balance_usdt": 10000,
  "risk_per_trade_pct": 0.02,
  "leverage_target": 10
}' > settings.json

# Валидировать
python src/settings/cli.py validate --file settings.json
```

## 🔧 Интеграция с основной системой

### Обновление main_with_options.py:

```python
from src.settings import UserSettingsManager

async def calculate_positions(symbol=None, user_id="default_user"):
    manager = UserSettingsManager()

    # Получаем настройки пользователя
    settings = await manager.get_settings_for_position_calculation(user_id)

    if settings is None:
        logger.error(f"Не удалось получить настройки для {user_id}")
        return

    # Используем настройки в расчёте
    position_data = {
        "balance_usdt": settings["balance_usdt"],
        "risk_per_trade_pct": settings["risk_per_trade_pct"],
        "leverage_target": settings["leverage_target"],
        "consensus_threshold": settings["consensus_threshold"],
        # ... остальные параметры
    }

    # Расчёт позиций с пользовательскими настройками
    # ...
```

## 🚀 Преимущества системы

1. **Гибкость** - каждый пользователь может иметь свои настройки
2. **Безопасность** - валидация всех параметров
3. **Удобство** - предустановленные профили и CLI
4. **Интеграция** - легко интегрируется с основной системой
5. **Масштабируемость** - поддержка множественных пользователей

## 📈 Планы развития

- [ ] Веб-интерфейс для управления настройками
- [ ] Группы пользователей с общими настройками
- [ ] Автоматическая оптимизация настроек
- [ ] Интеграция с внешними системами
- [ ] Аналитика эффективности настроек

---

Система настроек предоставляет мощный и гибкий инструмент для управления торговыми параметрами в PKLPO! 🎯
