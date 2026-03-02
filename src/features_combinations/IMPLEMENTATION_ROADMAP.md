Вывод: слой `features_combinations` надо сделать чисто числовым: комбинации = набор нормализованных фичей по таймстемпу. Никаких `bullish/bearish`, никаких «оценок сигнала». Всё, что похоже на «сигнал», уезжает в слой `signals`. Ниже — переписанный план и каркас кода под это.

## 📊 Статус выполнения

- ✅ **Этап 0**: Контракт данных зафиксирован (миграция БД создана, README обновлён)
- ✅ **Этап 1**: Домейн и инфраструктура реализованы
- ✅ **Этап 2**: Сервис расчёта комбинаций (numeric) реализован
- ✅ **Этап 3**: CLI реализован, интеграция в Airflow DAG выполнена
- ⏳ **Этап 4**: Интеграция с signals (не выполнено)
- ⏳ **Этап 5**: Backtest и MTF (не выполнено)
- ✅ **Этап 6**: Логирование реализовано, debug-скрипт создан
- ✅ **Этап 7**: Тесты созданы (юнит и интеграционные)

---

## 1. Новый контракт данных: только цифры

### 1.1. Модель в БД

Вместо `direction / strength / score` делаем «контейнер числовых фичей»:

```text
table: combination_features  (можно оставить имя combination_results, но смысл такой)

symbol          TEXT
timeframe       TEXT
timestamp       TIMESTAMPTZ / BIGINT
combination_id  TEXT / SMALLINT  -- идентификатор набора правил/фичей

features        JSONB            -- { "trend_score": 0.83, "vol_z": -1.2, ... }
meta            JSONB            -- отладка, dbg-значения, флаги

created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

Индекс (как и раньше):

```sql
CREATE UNIQUE INDEX IF NOT EXISTS ux_combination_features
ON combination_features (symbol, timeframe, timestamp, combination_id);
```

Где:

* `features` — только численные значения (float / int), никаких строк «bullish/bearish».
* If нужно кодировать направление: делай `direction_num: -1 | 0 | 1` в `features`, а не enum/текст.

### 1.2. Домейн-модель

`src/features_combinations/domain/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class CombinationRow:
    symbol: str
    timeframe: str
    timestamp: datetime  # или int, если везде epoch_ms
    combination_id: str

    features: dict[str, float]         # только числа
    meta: dict[str, Any] | None = None
```

Ключевая идея: слой комбинаций = «группа производных фичей», без принятия решений.

---

## 2. Переписанный план этапов (0 → 7) в numeric-формате

### Этап 0. Зафиксировать контракт данных ✅

1. ✅ Миграция под `combination_features`:

   * ✅ создана новая таблица `combination_features`
   * ✅ добавлен UNIQUE INDEX `ux_combination_features`
   * ✅ добавлены дополнительные индексы (combo_id, timestamp, GIN для JSONB)
   * ✅ тип `timestamp` BIGINT (совпадает с `indicators`)

2. ✅ Описать контракт в README:

   * ✅ что такое `combination_id` (ссылка на registry),
   * ✅ формат `features` (только числовые ключи/значения),
   * ✅ что `meta` — не для прод-логики, а для дебага/исследований.

---

### Этап 1. Домейн и инфраструктура ✅

3. ✅ Домейн-модель: `CombinationRow` в `domain/models.py`

4. ✅ Репозиторий:

`src/features_combinations/infrastructure/repository.py`:

* ✅ `CombinationRepository` (Protocol) определён
* ✅ `PostgresCombinationRepository` реализован
* ✅ Методы: `upsert_batch`, `load_for_range`, `load_latest`

5. ✅ Привязка к UPSERT:

* ✅ используется `upsert_helper.py` для UPSERT операций
* ✅ сериализация `features` → JSONB через `json.dumps()`
* ✅ используется `get_db_session()` для коннектов

---

### Этап 2. Сервис расчёта комбинаций (numeric) ✅

#### 2.1. Порты provider / calculator ✅

✅ `IndicatorProvider` (Protocol) определён в `application/ports.py`
✅ `PostgresIndicatorProvider` реализован в `infrastructure/indicator_provider.py`

✅ `CombinationCalculator` (Protocol) определён в `application/ports.py`
✅ `NumericCombinationCalculator` реализован в `infrastructure/numeric_calculator.py`
✅ `NumericSignalAnalyzer` реализован в `infrastructure/numeric_analyzer.py`
✅ Все сигналы преобразуются в numeric features (direction_num, trend_score, etc.)

#### 2.2. CombinationService: чистый numeric ✅

✅ `src/features_combinations/application/service.py`:

* ✅ `CombinationService` реализован
* ✅ Методы: `compute_for_df`, `compute_and_save_for_range`, `compute_and_save_latest`
* ✅ Использует собственный логгер через `get_combinations_logger("service")`
* ✅ Логирование состояния DataFrame через `_log_df_debug`

    def _log_df_debug(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        stage: str,
    ) -> None:
        if df.empty:
            self.logger.warning(
                "Empty DF at stage=%s symbol=%s timeframe=%s",
                stage,
                symbol,
                timeframe,
            )
            return

        self.logger.debug(
            "DF at stage=%s symbol=%s timeframe=%s rows=%d cols=%d",
            stage,
            symbol,
            timeframe,
            len(df),
            len(df.columns),
        )
        self.logger.debug("Columns: %s", df.columns.tolist())
        self.logger.debug("Dtypes:\n%s", df.dtypes)

    # ===== публичные методы =====

    @performance_timer(get_features_logger("combinations"), "compute_for_df")
    def compute_for_df(
        self,
        symbol: str,
        timeframe: str,
        df_indicators: pd.DataFrame,
    ) -> list[CombinationRow]:
        if df_indicators.empty:
            self.logger.info(
                "No indicators for symbol=%s timeframe=%s – skip combinations",
                symbol,
                timeframe,
            )
            return []

        self._log_df_debug(df_indicators, symbol, timeframe, "compute_for_df:input")

        rows_iter: Iterable[CombinationRow] = self.calculator.calculate_for_df(
            symbol=symbol,
            timeframe=timeframe,
            df_indicators=df_indicators,
        )
        rows = list(rows_iter)

        self.logger.info(
            "Computed combination rows: symbol=%s timeframe=%s count=%d",
            symbol,
            timeframe,
            len(rows),
        )
        return rows

    @performance_timer(get_features_logger("combinations"), "compute_and_save_for_range")
    def compute_and_save_for_range(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None,
        end: datetime | None,
        limit: int | None = None,
    ) -> int:
        self.logger.info(
            "Start combinations symbol=%s timeframe=%s start=%s end=%s limit=%s",
            symbol,
            timeframe,
            start,
            end,
            limit,
        )

        df_indicators = self.provider.load_indicators(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )

        self._log_df_debug(df_indicators, symbol, timeframe, "compute_and_save:load_indicators")

        if df_indicators.empty:
            self.logger.warning(
                "No indicators loaded for symbol=%s timeframe=%s start=%s end=%s – skip",
                symbol,
                timeframe,
                start,
                end,
            )
            return 0

        rows = self.compute_for_df(symbol, timeframe, df_indicators)
        if not rows:
            self.logger.warning(
                "No combination rows produced for symbol=%s timeframe=%s",
                symbol,
                timeframe,
            )
            return 0

        saved = self.repository.upsert_batch(rows)
        self.logger.info(
            "Combination rows saved: symbol=%s timeframe=%s saved=%d",
            symbol,
            timeframe,
            saved,
        )
        return saved

    @performance_timer(get_features_logger("combinations"), "compute_and_save_latest")
    def compute_and_save_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> int:
        return self.compute_and_save_for_range(
            symbol=symbol,
            timeframe=timeframe,
            start=None,
            end=None,
            limit=limit,
        )
```

---

### Этап 3. CLI / Airflow

7. ✅ CLI реализован:

```bash
python -m src.features_combinations.cli compute \
    --symbol BTC-USDT-SWAP \
    --timeframes 1m 5m 15m \
    --start 2025-01-01 \
    --end 2025-01-31
```

✅ Внутри:

* ✅ собирается `CombinationService` с провайдером, калькулятором и репозиторием
* ✅ для каждого symbol×TF вызывается `compute_and_save_for_range`
* ✅ логируется количество строк

8. ✅ В DAG:

```text
calc_ohlcv → calc_indicators → calc_combinations → signals/backtest/...
```

✅ `calc_combinations` получает тот же `date_window`, что и `calc_indicators`.
✅ Задача `combinations_run` добавлена в DAG `features_calc` после `smoke_validate_features`.

---

### Этап 4. Интеграция с `signals` (без bullish/bearish) ⏳

9. ⏳ Модель сигнала перестаёт напрямую ссылаться на `direction/strength`. Вместо этого:

* ⏳ хранит числовые фичи/агрегаты, которые вытащены из `features`:

```python
class Signal(...):
    ...
    combo_features: dict[str, float] | None = None
    # или конкретные агрегаты:
    combo_trend_score: float | None = None
    combo_direction_num: float | None = None
```

10. ⏳ Логика генерации сигналов:

* ⏳ загружает `CombinationRow` через репозиторий,
* ⏳ из `features` вытаскивает нужные ключи: `direction_num`, `trend_score`, `vol_regime` и т.п.,
* ⏳ принимает решение уже на этом уровне, например:

```python
if row.features.get("direction_num", 0.0) > 0 and row.features.get("trend_score", 0.0) > 0.7:
    # считаем, что есть лонговый сетап
```

⏳ То есть «маркетинговая» семантика живёт в `signals`, а combinations остаются «сырыми агрегатами».

---

### Этап 5. Backtest и MTF как numeric-клиенты ⏳

11. ⏳ Backtest:

* ⏳ подгружает `combination_features`,
* ⏳ объединяет их с OHLCV/indicators по timestamp,
* ⏳ любые правила используют numeric-фичи:

```python
if combo["trend_score"] > 0.7 and combo["direction_num"] > 0:
    open_long()
```

12. ⏳ Аггрегация результатов по `combination_id`:

* ⏳ считаешь hit-rate, PnL, Sharpe и т.д. по тем правилам, где использовались фичи конкретной комбинации,
* ⏳ принимаешь решение, какие комбинации оставить в registry.

13. ⏳ MTF:

* ⏳ на старшем TF комбинации выдают numeric-контекст: `mtf_trend_num`, `mtf_vol_regime` и пр.,
* ⏳ младший TF просто читает эти числа и использует как фильтры или дополнительные признаки — никаких слов «trend up» и т.п.

---

### Этап 6. Логи и отладка

14. ✅ Логгер реализован:

* ✅ `logging_config.py` с `get_combinations_logger()` и `setup_combinations_logging()`
* ✅ Сообщения нейтральные: «rows saved», «features keys count», «NaN в features» и т.д.
* ✅ Все компоненты используют единый логгер

15. ✅ Debug-скрипт:

* ✅ выводит рядом `indicators` и `combination_features` для нескольких таймстемпов,
* ✅ печатает содержимое `features` как dict с сортировкой по ключам.
* ✅ Реализован в `cli/debug.py`, запуск: `python -m src.features_combinations.cli.debug --symbol BTC-USDT-SWAP --timeframe 1m`

---

### Этап 7. Тесты ✅

16. ✅ Юнит-тесты `CombinationService`:

* ✅ мокнутый `IndicatorProvider` (маленький df),
* ✅ мокнутый `CombinationCalculator` (возвращает 2–3 `CombinationRow` с features),
* ✅ мокнутый `CombinationRepository` — проверяешь, что ушли правильные data-классы.
* ✅ Реализованы в `tests/test_service.py`: `test_compute_for_df`, `test_compute_for_df_empty`, `test_compute_and_save_for_range`, `test_compute_and_save_latest`

17. ✅ Интеграционный тест:

* ✅ использует существующие данные в `indicators`,
* ✅ запускает `compute_and_save_for_range`,
* ✅ проверяет, что в `combination_features` появились строки с нужными `features` (и что все значения числовые).
* ✅ Реализованы в `tests/test_integration.py`: `test_compute_and_save_integration`, `test_features_numeric_only`

---

Если нужно, дальше можно отдельно пройтись по твоему текущему `CombinationCalculator` и показать, как перевести конкретные «bullish/bearish/neutral» правила в numeric-фичи (`direction_num`, `prob_long`, `prob_short`, `regime_id` и т.п.).
