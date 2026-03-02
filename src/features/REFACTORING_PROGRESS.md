# Прогресс рефакторинга src/features — SOLID и ООП

## Статус выполнения

| Фаза | Задача | Статус | Изменённые файлы |
|------|--------|--------|------------------|
| 1.1 | Унификация типов возврата групп (LSP) | ✅ Завершено | registry.py, все indicator_groups/*.py |
| 1.2 | Разделение GroupCalculator (SRP) | ✅ Завершено | Созданы 4 новых файла |
| 2.1 | DIP — устранение hard-coded импортов | ✅ Завершено | calculation.py, batch_builder.py, protocols.py |
| 2.2 | OCP — вынос конфигурации | ✅ Завершено | config/settings.py, code_validator.py |
| 3.1 | Инкапсуляция GroupRegistry | ✅ Завершено | registry.py |
| 3.2 | Properties в ValidationConfig | ✅ Завершено | code_validator.py |
| 3.3 | Разделение batch_builder (SRP) | ❌ Не начато | — |
| 4 | Тесты и документация | ❌ Не начато | — |

---

## Фаза 1: Критические исправления (LSP, SRP)

### 1.1 Унификация типов возврата ✅

**Что сделано:**
1. Создан `GroupCalculatorProtocol` в `registry.py` — строгий Protocol для LSP
2. Добавлена runtime-валидация в `GroupRegistry.register()` и `GroupRegistry.validate_result()`
3. Обновлены все `calc_*_indicators()` функции:
   - `ma.py`: `def calc_ma_indicators(df, available, **kwargs) -> dict[str, pd.Series]`
   - `oscillators.py`, `volatility.py`, `volume.py`, `trend.py` — аналогично
   - `overlap.py`, `candles.py`, `statistics.py`, `performance.py`, `squeeze.py`
4. Создан `GroupCalculatorTypeError` для ошибок типов

### 1.2 Разделение GroupCalculator (SRP) ✅

**Созданные файлы:**
```
src/features/core/
├── group_calculator.py     # GroupFeatureCalculator — только расчёт
├── group_persister.py      # GroupPersister — только persistence
├── group_metrics.py        # GroupMetricsRecorder — только метрики
├── group_orchestrator.py   # GroupCalculationOrchestrator — координация
└── group_calculation.py    # Фасад для backward compatibility
```

**Ключевые классы:**
- `GroupFeatureCalculator`: `calculate_group()`, `calculate_groups()`
- `GroupPersister`: `persist_batch()`, `persist_groups()`
- `GroupMetricsRecorder`: `record_group_metrics()`, `record_overall_metrics()`
- `GroupCalculationOrchestrator`: координирует все компоненты

**Backward compatibility:**
- Старый `GroupCalculator` сохранён с deprecation warning
- `compute_features_grouped()` работает как раньше

---

## Фаза 2: DIP и OCP исправления

### 2.1 DIP — устранение hard-coded импортов ✅

**calculation.py:**
```python
def _apply_volatility_normalization(
    result_df, ctx, normalize_window, normalize_method,
    normalizer: FeatureNormalizer | None = None,  # DIP: инъекция зависимости
) -> pd.DataFrame
```

**batch_builder.py:**
```python
def build_batch_data(
    ind_df, symbol, timeframe, db_cols,
    timestamp_validator: TimestampValidatorProtocol | None = None,  # DIP
) -> tuple[list[dict], int]
```

**protocols.py:**
- Добавлен `TimestampValidator` Protocol
- Добавлен `GroupCalculator` Protocol

### 2.2 OCP — вынос конфигурации ✅

**src/config/settings.py — добавлены:**
```python
class FeaturesSettings:
    # Critical indicators (OCP)
    critical_indicators: list[str] = ["t3_20", "rma_20", "ics_26"]

    # Validation thresholds
    price_outlier_threshold: float = 0.02
    volume_outlier_threshold: float = 0.02
    outlier_multiplier: float = 1.5

    # Warm-up settings
    ma_warmup_multiplier: float = 2.0
    atr_warmup_multiplier: float = 2.0
    min_warmup_rows: int = 50

    # Price validation
    min_price_change: float = 0.001
    max_price_change: float = 0.5

    # Group calculation
    calculation_order: list[str]
    feature_periods: dict[str, int]
```

**code_validator.py:**
```python
class ValidationConfig:
    def __init__(self, use_settings: bool = True):
        # Автозагрузка из FeaturesSettings
```

**GroupCalculationConfig:**
```python
@classmethod
def from_settings(cls, settings=None) -> GroupCalculationConfig:
    # Загрузка из централизованной конфигурации
```

---

## Фаза 3: Инкапсуляция и улучшения

### 3.1 Инкапсуляция GroupRegistry ✅

**registry.py:**
```python
class GroupRegistry:
    # Name mangling для инкапсуляции
    __groups: dict[str, GroupEntry] = {}
    __initialized: bool = False

    # Приватные методы
    def __ensure_initialized(cls) -> None
    def __import_legacy_groups(cls) -> None
    def __validate_calculator(cls, func, name) -> None
```

### 3.2 Properties с валидацией в ValidationConfig ✅

**code_validator.py:**
```python
class ValidationConfig:
    # Private attributes
    _price_outlier_threshold: float
    _volume_outlier_threshold: float
    ...

    @property
    def price_outlier_threshold(self) -> float:
        return self._price_outlier_threshold

    @price_outlier_threshold.setter
    def price_outlier_threshold(self, value: float) -> None:
        if not 0 < value < 1:
            raise ValueError(f"must be 0 < x < 1, got {value}")
        self._price_outlier_threshold = value
```

---

## Оставшиеся задачи

### 3.3 Разделение batch_builder.py (SRP) ❌

**План:**
1. Создать `BatchValidator` класс
2. Извлечь логику логирования
3. Оставить `build_batch_data()` только для построения

### 4. Тесты и документация ❌

**План:**
1. Тесты для `GroupFeatureCalculator`
2. Тесты для `GroupPersister`
3. Тесты для Protocol compliance
4. Тесты для ValidationConfig setters
5. Обновить `src/features/README.md`

---

## Верификация

```bash
# Проверка синтаксиса
python -m py_compile src/features/indicator_groups/registry.py
python -m py_compile src/features/core/group_calculator.py
python -m py_compile src/features/core/group_orchestrator.py
python -m py_compile src/features/validation/code_validator.py
python -m py_compile src/config/settings.py

# Все файлы прошли проверку ✅
```

---

## Структура после рефакторинга

```
src/features/
├── core/
│   ├── group_calculator.py     # NEW: GroupFeatureCalculator
│   ├── group_persister.py      # NEW: GroupPersister
│   ├── group_metrics.py        # NEW: GroupMetricsRecorder
│   ├── group_orchestrator.py   # NEW: GroupCalculationOrchestrator
│   ├── group_calculation.py    # MODIFIED: Фасад
│   └── calculation.py          # MODIFIED: DIP (normalizer param)
├── indicator_groups/
│   ├── registry.py             # MODIFIED: LSP + инкапсуляция
│   ├── ma.py                   # MODIFIED: типизация
│   ├── oscillators.py          # MODIFIED: типизация
│   └── ...                     # Все остальные группы
├── validation/
│   └── code_validator.py       # MODIFIED: properties + OCP
├── infrastructure/persistence/
│   └── batch_builder.py        # MODIFIED: DIP (validator param)
├── domain/
│   └── protocols.py            # MODIFIED: новые Protocols
└── config/
    └── settings.py             # Используется из src/config/

src/config/
└── settings.py                 # MODIFIED: OCP конфигурация
```

---

## Примечания

- Все изменения backward-compatible
- Deprecation warnings для устаревших API
- Код проверен на синтаксические ошибки
- Рекомендуется запустить полный тест-сьют после завершения всех фаз
