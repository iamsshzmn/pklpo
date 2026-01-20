# Настройка проверки типов (mypy)

## Установка

mypy уже указан в зависимостях проекта. Установите его:

```bash
pip install mypy
```

Или установите все dev-зависимости:

```bash
pip install -e '.[dev]'
```

## Конфигурация

Конфигурация mypy находится в `pyproject.toml` в секции `[tool.mypy]`.

**Текущая конфигурация (Этап 2):**
- `strict = false` — базовые проверки (не строгий режим)
- `warn_unused_ignores = true` — предупреждения о неиспользуемых `# type: ignore`
- `disallow_any_generics = true` — запрет `Any` в generic типах
- `no_implicit_optional = true` — явное указание `Optional`
- `warn_return_any = true` — предупреждения о возврате `Any`
- `warn_unreachable = true` — предупреждения о недостижимом коде

## Использование

### Проверка всего модуля features:

```bash
mypy src/features --config-file pyproject.toml
```

### Проверка конкретного файла:

```bash
mypy src/features/core.py --config-file pyproject.toml
```

### Использование скрипта:

```bash
python scripts/check_types.py
```

Или для конкретного файла:

```bash
python scripts/check_types.py src/features/core.py
```

## План миграции к strict режиму

**Этап 2 (текущий):** Базовые проверки
- ✅ `strict = false`
- ✅ Проверка основных типов
- ✅ Предупреждения о проблемных местах

**Этап 3 (будущий):** Строгий режим
- `strict = true`
- `disallow_untyped_defs = true`
- `disallow_incomplete_defs = true`
- `check_untyped_defs = true`
- `disallow_untyped_decorators = true`

## Игнорирование модулей

В `pyproject.toml` настроены overrides для внешних библиотек:

```toml
[[tool.mypy.overrides]]
module = [
    "pandas.*",
    "numpy.*",
    "pytest.*",
    "ta.*",
    "asyncpg.*",
    "pydantic.*",
    "yaml.*",
    "airflow.*",
]
ignore_missing_imports = true
```

## Типичные ошибки и решения

### 1. `Missing type annotation`

**Проблема:** Функция без аннотаций типов

**Решение:** Добавить type hints:
```python
def my_function(x: int, y: str) -> bool:
    ...
```

### 2. `Incompatible types in assignment`

**Проблема:** Несовместимые типы при присваивании

**Решение:** Использовать правильные типы или явное приведение:
```python
value: int = int(string_value)
```

### 3. `Argument of type "X" cannot be assigned to parameter "Y"`

**Проблема:** Неправильный тип аргумента

**Решение:** Проверить сигнатуру функции и исправить тип

### 4. `Function is missing a return type annotation`

**Проблема:** Функция не имеет аннотации возвращаемого типа

**Решение:** Добавить `-> ReturnType`:
```python
def my_function() -> int:
    return 42
```

## Интеграция с CI/CD

Добавьте проверку типов в CI:

```yaml
- name: Type check
  run: |
    pip install mypy
    mypy src/features --config-file pyproject.toml
```

## Следующие шаги

1. ✅ Настроена базовая конфигурация mypy
2. ⏳ Запустить проверку и исправить критические ошибки
3. ⏳ Постепенно увеличивать строгость проверок
4. ⏳ Перейти к `strict = true` после исправления всех ошибок
