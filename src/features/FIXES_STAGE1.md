# ИСПРАВЛЕНИЯ: Этап 1 (Быстрые выигрыши)

**Дата:** 2025-01-XX
**Статус:** ✅ Завершено

---

## Выполненные исправления

### 1. ✅ Исправлены bare `except:` в `core.py`

**Файл:** `src/features/core.py`

- **Строка 177:** `except Exception: pass` → `except Exception as e: logger.debug(...)`
- **Строка 247:** `except Exception: pass` → `except Exception as e: logger.debug(...)`
- **Строка 976:** `except Exception: pass` → `except Exception as e: logger.debug(...)`
- **Строка 1002:** `except Exception: pass` → `except Exception as e: logger.debug(...)`

**Результат:** Все исключения теперь логируются с контекстом вместо проглатывания.

---

### 2. ✅ Улучшено логирование исключений

**Файл:** `src/features/core.py`

- **Строка 822:** Добавлен `exc_info=True` и `extra` контекст для лучшей диагностики
- Все `except Exception: pass` заменены на логирование с контекстом

**Результат:** Исключения логируются с полным traceback и контекстом.

---

### 3. ✅ Удалён закомментированный код

**Файл:** `src/features/core.py`

- **Строка 37:** Удалён закомментированный импорт `# from .utils import volatility_normalize_features`

**Результат:** Код очищен от мёртвого кода.

---

### 4. ✅ Добавлены type hints

**Файл:** `src/features/ta_safe.py`

- **`safe_ta_fallback()`:** Добавлен `-> pd.DataFrame`
- **`_normalize_to_df()`:** Добавлен тип для параметра `out: pd.DataFrame | pd.Series | None`
- **`_detect_available_functions()`:** Добавлен `-> set[str]` и явная типизация переменной `available`

**Результат:** Все функции имеют полные type hints.

---

### 5. ✅ Исправлены bare `except:` в `ta_safe.py`

**Файл:** `src/features/ta_safe.py`

- **Строка 330:** `except:` → `except Exception as e: logger.debug(...)`
- **Строка 332:** `except:` → `except Exception as e: logger.debug(...)`

**Результат:** Все исключения логируются.

---

### 6. ✅ Исправлен возврат `None` в `safe_ta_with_fallback()`

**Файл:** `src/features/ta_safe.py`

- **Строка 942:** `return None` → `return pd.DataFrame(index=df.index)`

**Результат:** Функция всегда возвращает `pd.DataFrame`, соответствует типу возврата.

---

### 7. ✅ Улучшена обработка исключений в `insert_indicators.py`

**Файл:** `src/features/infrastructure/insert_indicators.py`

- **Строка 437:** Добавлен `exc_info=True` и `extra` контекст для логирования

**Результат:** Исключения логируются с полным traceback и контекстом (row_index, symbol, timeframe).

---

### 8. ✅ Исправлены абсолютные импорты

**Файл:** `src/features/infrastructure/insert_indicators.py`

- **Строка 13:** `from src.features.schema.name_aliases` → `from ..schema.name_aliases`
- **Строка 14:** `from src.features.schema.schema_manager` → `from ..schema.schema_manager`

**Результат:** Используются относительные импорты для лучшей переносимости.

---

## Метрики

- ✅ **Bare `except:`:** 0 (было 6)
- ✅ **Функции без type hints:** 0 в критических местах (было 3)
- ✅ **Закомментированный код:** 0 (было 1)
- ✅ **Абсолютные импорты в основном коде:** 0 (было 2)

---

## Следующие шаги

Переход к **Этапу 2: Типизация и докстринги**:
1. Добавить type hints для всех публичных функций
2. Настроить mypy с базовыми проверками
3. Дополнить докстринги (Examples, Raises)

---

**Конец отчёта**
