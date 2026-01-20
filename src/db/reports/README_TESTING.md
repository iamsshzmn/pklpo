# Тестирование миграций базы данных

## 🚀 Способы запуска тестов

### 1. Простой запуск (рекомендуется)
```bash
python run_migration_tests.py
```

### 2. Прямой запуск модуля
```bash
python src/db/migration_testing.py
```

### 3. С дополнительными опциями
```bash
# Подробный вывод
python src/db/migration_testing.py --verbose

# CI/CD режим (возвращает код ошибки при неудачных тестах)
python src/db/migration_testing.py --ci

# С указанием файла отчета
python src/db/migration_testing.py --report my_report.json
```

### 4. Через Python
```python
import asyncio
from src.db.migration_testing import run_migration_test_suite

# Запуск всех тестов
test_suite = asyncio.run(run_migration_test_suite())

# Получение результатов
summary = test_suite.get_summary()
print(f"Успешных тестов: {summary['passed_tests']}/{summary['total_tests']}")
```

## 📋 Что тестируется

### 1. **Schema Integrity Test**
- Проверка существования критичных таблиц (`ohlcv_p`, `indicators_p`, `instruments`, `schema_migrations`)
- Проверка наличия индексов

### 2. **Idempotency Test**
- Тест идемпотентности (повторный запуск без изменений)
- Проверка, что количество миграций не изменяется

### 3. **Large Table Performance Test**
- Smoke-test на больших таблицах
- Проверка производительности запросов
- Анализ размера таблиц и количества записей

### 4. **Constraints Validation Test**
- Проверка PRIMARY KEY ограничений
- Проверка CHECK ограничений
- Проверка UNIQUE ограничений

### 5. **Monitoring Functions Test**
- Тест функций создания бэкапов
- Проверка VIEW мониторинга
- Тест функций готовности к миграции

## 📊 Результаты тестирования

### Отчет в консоли
```
🧪 Запуск тестов миграций...
==================================================
🔍 Запускаем тест: test_schema_integrity
✅ PASS Schema Integrity Test (45ms): All critical tables exist; Found 12 indexes
🔍 Запускаем тест: test_idempotency
✅ PASS Idempotency Test (23ms): Migration count unchanged: 15
...

==================================================
📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:
   Всего тестов: 5
   ✅ Успешных: 5
   ❌ Неудачных: 0
   📈 Процент успеха: 100.0%
   ⏱️  Общее время: 234ms

✅ Все тесты прошли успешно!
```

### JSON отчет
Результаты сохраняются в файл `migration_test_report.json`:
```json
{
  "total_tests": 5,
  "passed_tests": 5,
  "failed_tests": 0,
  "success_rate": 100.0,
  "total_duration_ms": 234,
  "test_suite_duration_ms": 245,
  "results": [
    {
      "test_name": "Schema Integrity Test",
      "success": true,
      "duration_ms": 45,
      "details": "All critical tables exist; Found 12 indexes",
      "timestamp": "2024-01-15T10:30:45.123456"
    }
  ]
}
```

## 🔧 Настройка

### Переменные окружения
Убедитесь, что настроены переменные для подключения к БД:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/dbname"
```

### Логирование
Логи тестирования сохраняются в `migration_tests.log`

## 🚨 Устранение проблем

### Ошибка подключения к БД
```bash
# Проверьте переменные окружения
echo $DATABASE_URL

# Или настройте в коде
export DATABASE_URL="your_connection_string"
```

### Ошибка импорта модулей
```bash
# Убедитесь, что находитесь в корневой директории проекта
cd /path/to/your/project

# Или добавьте путь к PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/your/project"
```

### Тесты не проходят
1. Проверьте, что все миграции применены
2. Убедитесь, что БД доступна
3. Проверьте права доступа к БД
4. Посмотрите детали в JSON отчете

## 📈 CI/CD интеграция

### GitHub Actions
```yaml
- name: Run Migration Tests
  run: |
    python src/db/migration_testing.py --ci
```

### GitLab CI
```yaml
test_migrations:
  script:
    - python src/db/migration_testing.py --ci
```

### Jenkins
```bash
python src/db/migration_testing.py --ci
if [ $? -ne 0 ]; then
    echo "Migration tests failed!"
    exit 1
fi
```

## 🎯 Рекомендации

1. **Запускайте тесты после каждой миграции**
2. **Используйте `--ci` флаг в автоматизированных процессах**
3. **Проверяйте JSON отчеты для детального анализа**
4. **Мониторьте время выполнения тестов**
5. **Добавляйте новые тесты при изменении схемы БД**
