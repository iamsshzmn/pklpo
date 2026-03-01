# Настройка проверок кода для PKLPO

## Быстрая установка

```powershell
# 1. Установить pre-commit (только для базовых проверок)
pip install pre-commit

# 2. Установить hooks в репозиторий
pre-commit install
```

## Workflow проверок

### Автоматические проверки (pre-commit hooks)

При каждом коммите автоматически проверяются только **базовые вещи**:

- ✅ Trailing whitespace - удаление лишних пробелов
- ✅ End-of-file fixer - добавление финальной пустой строки
- ✅ YAML/JSON/TOML валидация - проверка синтаксиса конфигов
- ✅ Large files check - блокировка файлов >200KB
- ✅ Merge conflicts - обнаружение конфликтов
- ✅ Private keys detection - поиск приватных ключей

### Ручные проверки (перед коммитом)

Все серьёзные проверки запускаются **вручную** через скрипт:

```powershell
# Запустить все проверки
.\scripts\check_before_commit.ps1

# С опциями
.\scripts\check_before_commit.ps1 -AllFiles      # Проверить все файлы
.\scripts\check_before_commit.ps1 -SkipTests      # Пропустить тесты
.\scripts\check_before_commit.ps1 -SkipFormat     # Пропустить форматирование
```

**Что проверяется:**

1. ✅ **Ruff lint** - проверка кода, автоисправление
2. ✅ **Ruff format** - форматирование кода
3. ✅ **Black** - дополнительное форматирование (для совместимости)
4. ✅ **Bandit** - проверка безопасности
5. ✅ **Быстрые unit-тесты** - pytest (без slow/integration)
6. ✅ **Базовые проверки** - pre-commit hooks

## Коммит с проверками

### Вариант 1: Скрипт (рекомендуется)

```powershell
# Запустить проверки и закоммитить
.\scripts\commit_with_checks.ps1 "feat: новый функционал"

# С опциями
.\scripts\commit_with_checks.ps1 "fix: баг" -AllFiles
.\scripts\commit_with_checks.ps1 "docs: обновление" -SkipTests
.\scripts\commit_with_checks.ps1 "WIP" -SkipChecks  # Пропустить все проверки
```

### Вариант 2: Вручную

```powershell
# 1. Запустить проверки
.\scripts\check_before_commit.ps1

# 2. Если всё ОК - закоммитить
git add .
git commit -m "feat: новый функционал"
```

### Вариант 3: Обычный git commit

```powershell
git add .
git commit -m "feat: новый функционал"
```

Запустятся только базовые pre-commit hooks (whitespace, EOF, конфликты).

## Отдельные команды

Если нужно запустить только одну проверку:

```powershell
# Ruff lint
ruff check --fix src/

# Ruff format
ruff format src/

# Black
black src/ --line-length 88

# Bandit
bandit -r src/ -c pyproject.toml -ll

# Тесты
pytest src/ -m "not slow and not integration" -v

# Базовые проверки
pre-commit run --all-files
```

## Пропуск проверок (только в крайних случаях!)

```powershell
# Пропустить все проверки
git commit -m "WIP: временный коммит" --no-verify

# Или через скрипт
.\scripts\commit_with_checks.ps1 "WIP" -SkipChecks
```

## Устранение проблем

### Ruff находит ошибки

```powershell
# Автоисправление
ruff check --fix src/

# Показать все ошибки
ruff check src/
```

### Black находит изменения

```powershell
# Применить форматирование
black src/ --line-length 88
```

### Тесты падают

```powershell
# Запустить конкретный тест
pytest src/features/tests/test_core.py -v

# Запустить с отладкой
pytest src/features/tests/test_core.py -v --pdb
```

### YAML ошибки

```powershell
# Проверить конкретный файл
python -c "import yaml; yaml.safe_load(open('config/mtf_phase3.yaml', encoding='utf-8'))"
```

## Обновление pre-commit hooks

```powershell
# Обновить все hooks до последних версий
pre-commit autoupdate
```

## Рекомендуемый workflow

1. **Перед коммитом:**
   ```powershell
   .\scripts\check_before_commit.ps1
   ```

2. **Если всё ОК:**
   ```powershell
   .\scripts\commit_with_checks.ps1 "feat: описание"
   ```

3. **Или вручную:**
   ```powershell
   git add .
   git commit -m "feat: описание"
   ```

## Что НЕ проверяется автоматически

- **Mypy** (type checking) - запускать вручную: `mypy src/`
- **Pydocstyle** - запускать вручную: `pydocstyle src/`
- **Полные тесты** (integration, slow) - только в CI/CD
