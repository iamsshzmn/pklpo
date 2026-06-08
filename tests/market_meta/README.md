# Тесты для модуля market_meta

## Структура тестов

Все тесты обновлены для работы с новой архитектурой модуля (domain/application/infrastructure/cli).

### Файлы тестов

- `test_market_meta.py` - Комплексные тесты основной функциональности
- `test_extended_features.py` - Тесты расширенных функций
- `test_config.py` - Тесты конфигурации
- `test_logging.py` - Тесты логирования
- `test_metrics.py` - Тесты метрик
- `test_exceptions.py` - Тесты исключений
- `test_retry.py` - Тесты retry механизмов
- `test_integration.py` - Интеграционные тесты

## Запуск тестов

### Все тесты модуля

```bash
pytest tests/market_meta/ -v
```

### Конкретный тест

```bash
pytest tests/market_meta/test_market_meta.py -v
pytest tests/market_meta/test_config.py -v
```

### С покрытием

```bash
pytest tests/market_meta/ --cov=src.market_meta --cov-report=html
```

## Импорты

Все тесты используют правильные импорты согласно новой структуре:

- **Domain layer**: `from src.market_meta.domain.* import ...`
- **Application layer**: `from src.market_meta.application.* import ...`
- **Infrastructure layer**: `from src.market_meta.infrastructure.* import ...`
- **CLI**: `from src.market_meta.cli import ...`
- **Публичный API**: `from src.market_meta import ...` (работает как раньше)

## Зависимости

Убедитесь, что установлены все зависимости:

```bash
pip install -r requirements.txt
```

Основные зависимости для тестов:
- pytest
- aiohttp (для infrastructure клиентов)
- sqlalchemy (для database тестов)
