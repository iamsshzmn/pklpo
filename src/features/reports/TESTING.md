# Features Module - Руководство по тестированию

## 🧪 Обзор тестов

Модуль `features/` включает полный набор тестов для обеспечения качества и корректности работы:

### Типы тестов
- **Unit-тесты**: тестирование отдельных функций
- **Property-тесты**: проверка критических свойств (look-ahead, монотонность)
- **Интеграционные тесты**: тестирование взаимодействия компонентов
- **Тесты производительности**: бенчмарки и нагрузочное тестирование
- **Тесты граничных случаев**: обработка ошибок и исключений

## 🚀 Быстрый запуск

### Все тесты
```bash
# Запуск всех тестов
pytest src/features/tests/

# С подробным выводом
pytest src/features/tests/ -v

# С покрытием кода
pytest src/features/tests/ --cov=src.features --cov-report=html
```

### Отдельные тесты
```bash
# Unit-тесты
pytest src/features/tests/test_core.py

# Property-тесты (критически важные)
pytest src/features/tests/test_property.py

# Интеграционные тесты
pytest src/features/tests/test_integration.py

# Тесты производительности
pytest src/features/tests/test_performance.py

# Тесты нормировки
pytest src/features/tests/test_volatility_normalization.py

# Тесты граничных случаев
pytest src/features/tests/test_edge_cases.py

# Тесты маппинга имён
pytest src/features/tests/test_name_mapping.py
```

## 📊 Property-тесты

### Критически важные свойства

#### 1. Отсутствие look-ahead bias
```bash
pytest src/features/tests/test_property.py::TestNoLookaheadProperty::test_no_lookahead_shift_property
```

**Что проверяется:**
- Сдвиг данных на 1 бар не изменяет исторические значения
- Добавление новых данных не влияет на прошлые расчёты
- Отсутствие утечки будущей информации

#### 2. Онлайн/офлайн паритет
```bash
pytest src/features/tests/test_integration.py::TestIntegration::test_online_offline_parity
```

**Что проверяется:**
- Идентичность результатов онлайн и офлайн расчётов
- Расхождение < ε (1e-10)
- Симуляция реальных условий использования

#### 3. Детерминированность
```bash
pytest src/features/tests/test_property.py::TestDeterministicProperty::test_deterministic_results
```

**Что проверяется:**
- Одинаковые входные данные дают одинаковые результаты
- Воспроизводимость расчётов
- Отсутствие случайности в алгоритмах

#### 4. Масштабируемость
```bash
pytest src/features/tests/test_property.py::TestPerformanceProperty::test_performance_scaling
```

**Что проверяется:**
- Производительность растёт линейно с размером данных
- Отсутствие экспоненциального роста времени
- Эффективность алгоритмов

## 🔧 Настройка тестового окружения

### Установка зависимостей
```bash
# Основные зависимости для тестирования
pip install pytest pytest-cov pytest-benchmark

# Дополнительные зависимости
pip install pandas numpy ta
```

### Переменные окружения
```bash
# Уровень логирования для тестов
export PYTHONPATH=src
export LOG_LEVEL=DEBUG
```

### Конфигурация pytest
Создайте файл `pytest.ini` в корне проекта:
```ini
[tool:pytest]
testpaths = src/features/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    property: marks tests as property tests
    integration: marks tests as integration tests
    performance: marks tests as performance tests
```

## 📈 Тесты производительности

### Бенчмарки
```bash
# Запуск бенчмарков производительности
python src/features/benchmark_performance.py

# Тесты производительности через pytest
pytest src/features/tests/test_performance.py
```

### Метрики производительности
- **Время расчёта**: < 1.0s для 1000 баров × 5 индикаторов
- **Память**: < 100MB для 200 баров × 10 индикаторов
- **Масштабируемость**: линейный рост с размером данных

### Профилирование
```bash
# Профилирование с cProfile
python -m cProfile -o profile.stats src/features/benchmark_performance.py

# Анализ профиля
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"
```

## 🔍 Отладка тестов

### Подробный вывод
```bash
# Максимально подробный вывод
pytest src/features/tests/ -v -s --tb=long

# Вывод только неудачных тестов
pytest src/features/tests/ -x --tb=short
```

### Отладка конкретного теста
```bash
# Запуск одного теста с отладкой
pytest src/features/tests/test_core.py::TestCoreFunctions::test_compute_features_basic -v -s

# Запуск с pdb
pytest src/features/tests/test_core.py::TestCoreFunctions::test_compute_features_basic --pdb
```

### Логирование
```bash
# Включение логов во время тестов
pytest src/features/tests/ --log-cli-level=DEBUG

# Сохранение логов в файл
pytest src/features/tests/ --log-file=test.log --log-file-level=DEBUG
```

## 📊 Покрытие кода

### Генерация отчёта о покрытии
```bash
# HTML отчёт
pytest src/features/tests/ --cov=src.features --cov-report=html

# Консольный отчёт
pytest src/features/tests/ --cov=src.features --cov-report=term-missing

# XML отчёт для CI
pytest src/features/tests/ --cov=src.features --cov-report=xml
```

### Целевое покрытие
- **Общее покрытие**: > 90%
- **Критические компоненты**: > 95%
- **Property-тесты**: 100% покрытие критических свойств

### Анализ покрытия
```bash
# Просмотр HTML отчёта
open htmlcov/index.html

# Анализ непокрытых строк
pytest src/features/tests/ --cov=src.features --cov-report=term-missing | grep "Missing"
```

## 🚨 Обработка ошибок

### Типичные проблемы

#### 1. Импорт ошибки
```bash
# Добавьте src в PYTHONPATH
export PYTHONPATH=src:$PYTHONPATH

# Или запускайте из корня проекта
cd /path/to/project
pytest src/features/tests/
```

#### 2. Отсутствующие зависимости
```bash
# Установите все зависимости
pip install -r requirements.txt

# Или установите тестовые зависимости
pip install pytest pandas numpy ta
```

#### 3. Проблемы с памятью
```bash
# Запуск с ограничением памяти
pytest src/features/tests/ --maxfail=1 -x

# Пропуск медленных тестов
pytest src/features/tests/ -m "not slow"
```

## 🔄 Непрерывная интеграция

### GitHub Actions
```yaml
name: Features Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: |
        pip install pytest pytest-cov pandas numpy ta
    - name: Run tests
      run: |
        pytest src/features/tests/ --cov=src.features --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v1
```

### Локальная CI
```bash
#!/bin/bash
# run_tests.sh

set -e

echo "🧪 Запуск тестов features модуля..."

# Установка зависимостей
pip install pytest pytest-cov pandas numpy ta

# Запуск тестов
pytest src/features/tests/ -v --cov=src.features --cov-report=term-missing

# Проверка покрытия
coverage_failed=$(pytest src/features/tests/ --cov=src.features --cov-report=term | grep "TOTAL" | awk '{print $4}' | sed 's/%//')
if (( $(echo "$coverage_failed < 90" | bc -l) )); then
    echo "❌ Покрытие кода ниже 90%: ${coverage_failed}%"
    exit 1
fi

echo "✅ Все тесты прошли успешно!"
```

## 📝 Написание новых тестов

### Структура теста
```python
import pytest
import pandas as pd
from src.features import compute_features

class TestNewFeature:
    """Тесты для новой функциональности."""

    @pytest.fixture
    def sample_data(self):
        """Фикстура с тестовыми данными."""
        return pd.DataFrame({
            'ts': [1, 2, 3],
            'open': [100, 101, 102],
            'high': [102, 103, 104],
            'low': [99, 100, 101],
            'close': [101, 102, 103],
            'volume': [1000, 1100, 1200]
        })

    def test_new_functionality(self, sample_data):
        """Тест новой функциональности."""
        # Arrange
        expected_result = ...

        # Act
        result = compute_features(sample_data, specs=["rsi_14"])

        # Assert
        assert result is not None
        assert len(result) == len(sample_data)
        # Дополнительные проверки...
```

### Property-тест
```python
def test_property_example(self, sample_data):
    """Property-тест для критического свойства."""
    # Проверяем свойство: результат должен быть детерминированным
    result1 = compute_features(sample_data, specs=["rsi_14"])
    result2 = compute_features(sample_data, specs=["rsi_14"])

    # Результаты должны быть идентичными
    pd.testing.assert_frame_equal(result1, result2)
```

## ✅ Чек-лист тестирования

### Перед коммитом
- [ ] Все тесты проходят: `pytest src/features/tests/`
- [ ] Покрытие кода > 90%: `pytest --cov=src.features`
- [ ] Property-тесты проходят: `pytest test_property.py`
- [ ] Интеграционные тесты проходят: `pytest test_integration.py`
- [ ] Нет медленных тестов: `pytest -m "not slow"`

### Перед релизом
- [ ] Полный набор тестов
- [ ] Бенчмарки производительности
- [ ] Тесты граничных случаев
- [ ] Документация тестов
- [ ] CI/CD настроен

## 📞 Поддержка тестирования

### Полезные команды
```bash
# Быстрая проверка
pytest src/features/tests/ -x --tb=short

# Подробная диагностика
pytest src/features/tests/ -v -s --tb=long

# Только критические тесты
pytest src/features/tests/test_property.py src/features/tests/test_integration.py

# Пропуск медленных тестов
pytest src/features/tests/ -m "not slow"
```

### Контакты
- Обратитесь к команде разработки
- Проверьте документацию тестов
- Изучите примеры в `examples.py`
