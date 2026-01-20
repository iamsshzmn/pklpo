# Features Module - Индекс документации

## 📚 Полная документация

### Основные документы
- **[README.md](README.md)** - Полная документация модуля
- **[QUICKSTART.md](QUICKSTART.md)** - Быстрый старт для новых пользователей
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Описание слоистой архитектуры
- **[CHECKLIST.md](CHECKLIST.md)** - Чек-лист готовности к продакшену
- **[CHANGELOG.md](CHANGELOG.md)** - История изменений и версионирование

### Руководства
- **[MIGRATION.md](MIGRATION.md)** - Руководство по миграции с legacy кода
- **[TESTING.md](TESTING.md)** - Руководство по тестированию

### Примеры и код
- **[examples.py](examples.py)** - Практические примеры использования
- **[CLI](cli.py)** - Командная строка и примеры команд
- **[Тесты](tests/)** - Примеры использования в тестах

## 🎯 Быстрая навигация

### Для новых пользователей
1. **[QUICKSTART.md](QUICKSTART.md)** - Начните здесь
2. **[examples.py](examples.py)** - Изучите примеры
3. **[README.md](README.md)** - Подробная документация

### Для разработчиков
1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Понимание архитектуры
2. **[TESTING.md](TESTING.md)** - Запуск и написание тестов
3. **[CHECKLIST.md](CHECKLIST.md)** - Проверка готовности
4. **[CHANGELOG.md](CHANGELOG.md)** - История изменений

### Для миграции
1. **[MIGRATION.md](MIGRATION.md)** - Пошаговая миграция
2. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Новая архитектура
3. **[examples.py](examples.py)** - Сравнение старого и нового API
4. **[README.md](README.md)** - Новый API и функции

## 📋 Краткий обзор

### Что это?
Модуль для расчёта технических индикаторов с онлайн/офлайн паритетом, соответствующий требованиям Фазы 2 проекта.

### Ключевые возможности
- ✅ Единый расчёт признаков без look-ahead bias
- ✅ Слоистая архитектура (Domain/Infrastructure/Application)
- ✅ Property-тесты на отсутствие утечек
- ✅ Онлайн/офлайн паритет (расхождение < 1e-10)
- ✅ Волатильностная нормировка
- ✅ Полное покрытие тестами
- ✅ CLI интерфейс
- ✅ Интеграция с БД
- ✅ Готовность к интеграции с MTF

### Быстрый пример
```python
from src.features.core import compute_features

features = compute_features(
    ohlcv_data,
    specs=["rsi_14", "atr_14", "ema_12"],
    volatility_normalize=True
)
```

## 🔍 Поиск информации

### По функциям
- **Расчёт индикаторов**: [README.md#compute_features](README.md#🔧-api-reference)
- **Архитектура**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Валидация данных**: [README.md#validation](README.md#validation)
- **CLI команды**: [README.md#cli](README.md#🖥️-cli)
- **Тестирование**: [TESTING.md](TESTING.md)

### По индикаторам
- **Список всех индикаторов**: [README.md#доступные-индикаторы](README.md#📊-доступные-индикаторы)
- **По типам**: [README.md#feature-groups](README.md#get_features_by_type)
- **Примеры использования**: [examples.py](examples.py)

### По проблемам
- **Миграция с legacy**: [MIGRATION.md](MIGRATION.md)
- **Архитектурные вопросы**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Ошибки и отладка**: [TESTING.md#отладка-тестов](TESTING.md#🔍-отладка-тестов)
- **Производительность**: [README.md#производительность](README.md#📈-производительность)

## 📊 Статус готовности

### Фаза 2 - Выполнено ✅
- [x] Единый расчёт признаков без look-ahead
- [x] Слоистая архитектура (Domain/Infrastructure/Application)
- [x] База для ctx/trg/consensus
- [x] Property-тест "сдвиг на 1 бар"
- [x] Единый интерфейс с вола-нормировкой
- [x] Онлайн/офлайн паритет (расхождение < ε)
- [x] Интеграция с БД

### Готовность к продакшену ✅
- [x] Все требования выполнены
- [x] Покрытие тестами > 90%
- [x] Документация полная
- [x] Производительность соответствует требованиям
- [x] Безопасность обеспечена

## 🚀 Быстрый старт

### Установка
```bash
# Модуль уже включен в проект
# Никакой дополнительной установки не требуется
```

### Первый запуск
```bash
# Запуск примеров
python src/features/examples.py

# Запуск тестов
pytest src/features/tests/

# CLI интерфейс
python -m src.features.cli --help
```

### Базовое использование
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

## 📞 Поддержка

### Документация
- Все документы доступны в папке `src/features/`
- Архитектура описана в `reports/ARCHITECTURE.md`
- Примеры кода в `examples.py`
- Тесты как источник примеров в `tests/`

### Контакты
- Команда разработки MTF
- Технический лид проекта
- Документация проекта в `task project.md`

### Сообщение об ошибках
- Создать issue в репозитории
- Приложить минимальный пример
- Указать версию и окружение

---

**Модуль готов к использованию! 🎉**

Начните с [QUICKSTART.md](QUICKSTART.md) для быстрого старта, изучите [ARCHITECTURE.md](ARCHITECTURE.md) для понимания архитектуры или прочитайте [README.md](README.md) для полной документации.
