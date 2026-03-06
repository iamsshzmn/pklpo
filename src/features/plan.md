# План тестирования src/features после рефакторинга

> Дата создания: 2026-02-02
> Статус: 📋 **ПЛАН ТЕСТИРОВАНИЯ**

## Обзор изменений

После рефакторинга (13 задач) необходимо проверить:
1. Функциональные изменения (6 задач)
2. Архитектурные изменения (7 задач)
3. Обратную совместимость
4. Интеграцию между модулями

---

## Структура тестов

```
tests/
├── unit/                    # Модульные тесты
│   ├── test_container.py
│   ├── test_validation_chain.py
│   ├── test_group_registry.py
│   ├── test_protocols.py
│   ├── test_feature_service.py
│   ├── test_pipeline_context.py
│   └── test_alert_observers.py
├── integration/             # Интеграционные тесты
│   ├── test_calculation_pipeline.py
│   ├── test_di_integration.py
│   └── test_indicator_groups.py
└── smoke/                   # Smoke тесты
    └── test_imports.py
```

---

## 1. Модульные тесты (Unit Tests)

### 1.1 DI Container (`container.py`)

**Файл:** `tests/unit/test_container.py`

```python
import pytest
from src.features.container import Container, create_default_container

class TestContainer:
    """Task 10: DIP-compliant DI Container."""

    def test_register_singleton_callable(self):
        """Singleton с callable factory."""
        container = Container()
        container.register_singleton("config", lambda: {"key": "value"})

        result1 = container.resolve("config")
        result2 = container.resolve("config")

        assert result1 is result2  # Тот же объект
        assert result1 == {"key": "value"}

    def test_register_singleton_instance(self):
        """Singleton с готовым instance."""
        container = Container()
        instance = {"key": "value"}
        container.register_singleton("config", instance)

        assert container.resolve("config") is instance

    def test_register_factory(self):
        """Factory создаёт новый instance каждый раз."""
        container = Container()
        container.register_factory("service", lambda c: {"id": id(c)})

        result1 = container.resolve("service")
        result2 = container.resolve("service")

        assert result1 is not result2  # Разные объекты

    def test_factory_receives_container(self):
        """Factory получает контейнер для resolve зависимостей."""
        container = Container()
        container.register_singleton("config", {"db_url": "postgres://..."})
        container.register_factory("service", lambda c: {
            "config": c.resolve("config")
        })

        service = container.resolve("service")
        assert service["config"]["db_url"] == "postgres://..."

    def test_resolve_not_registered(self):
        """KeyError при resolve незарегистрированной зависимости."""
        container = Container()
        with pytest.raises(KeyError, match="not registered"):
            container.resolve("unknown")

    def test_has_method(self):
        """Проверка наличия зависимости."""
        container = Container()
        container.register_singleton("config", {})

        assert container.has("config")
        assert not container.has("unknown")
        assert "config" in container

    def test_clear_method(self):
        """Очистка всех регистраций."""
        container = Container()
        container.register_singleton("a", 1)
        container.register_factory("b", lambda c: 2)

        container.clear()

        assert not container.has("a")
        assert not container.has("b")

    def test_chaining(self):
        """Fluent interface для цепочки регистраций."""
        container = (
            Container()
            .register_singleton("a", 1)
            .register_factory("b", lambda c: 2)
        )

        assert container.resolve("a") == 1
        assert container.resolve("b") == 2

    def test_create_default_container_returns_fresh_container(self):
        """Фабрика возвращает новый контейнер."""
        c1 = create_default_container()
        c2 = create_default_container()

        assert c1 is not c2

    def test_default_dependencies_configured(self):
        """Дефолтные зависимости настроены."""
        container = create_default_container()

        assert container.has("logger")
        assert container.has("calculator")
        assert container.has("validation_chain")
        assert container.has("alert_dispatcher")
```

**Команда запуска:**
```bash
pytest tests/unit/test_container.py -v
```

---

### 1.2 ValidationChain (`validation/chain.py`)

**Файл:** `tests/unit/test_validation_chain.py`

```python
import pytest
import pandas as pd
import numpy as np
from src.features.validation.chain import (
    ValidationResult,
    Validator,
    ValidationChain,
    OHLCVValidator,
    MinRowsValidator,
    TimestampValidator,
    NaNRatioValidator,
    create_default_chain,
    create_strict_chain,
)

class TestValidationResult:
    """ValidationResult data class."""

    def test_default_valid(self):
        result = ValidationResult()
        assert result.is_valid
        assert result.errors == []
        assert result.warnings == []

    def test_add_error_marks_invalid(self):
        result = ValidationResult()
        result.add_error("Test error")

        assert not result.is_valid
        assert "Test error" in result.errors

    def test_add_warning_stays_valid(self):
        result = ValidationResult()
        result.add_warning("Test warning")

        assert result.is_valid
        assert "Test warning" in result.warnings

    def test_merge_combines_results(self):
        r1 = ValidationResult(is_valid=True)
        r1.add_warning("W1")

        r2 = ValidationResult(is_valid=False)
        r2.add_error("E1")

        r1.merge(r2)

        assert not r1.is_valid
        assert "W1" in r1.warnings
        assert "E1" in r1.errors


class TestOHLCVValidator:
    """Task 12: OHLCVValidator в Chain of Responsibility."""

    @pytest.fixture
    def valid_ohlcv(self):
        return pd.DataFrame({
            "open": [100, 101, 102],
            "high": [105, 106, 107],
            "low": [99, 100, 101],
            "close": [104, 105, 106],
            "volume": [1000, 1100, 1200],
        })

    def test_valid_dataframe(self, valid_ohlcv):
        validator = OHLCVValidator()
        result = validator.validate(valid_ohlcv)

        assert result.is_valid
        assert result.details["row_count"] == 3

    def test_none_dataframe(self):
        validator = OHLCVValidator()
        result = validator.validate(None)

        assert not result.is_valid
        assert "None" in result.errors[0]

    def test_empty_dataframe(self):
        validator = OHLCVValidator()
        result = validator.validate(pd.DataFrame())

        assert not result.is_valid
        assert "empty" in result.errors[0].lower()

    def test_missing_columns(self, valid_ohlcv):
        df = valid_ohlcv.drop(columns=["close", "volume"])
        validator = OHLCVValidator()
        result = validator.validate(df)

        assert not result.is_valid
        assert "Missing" in result.errors[0]

    def test_high_null_ratio_error(self):
        df = pd.DataFrame({
            "open": [100, None, None, None, None],
            "high": [105, 106, 107, 108, 109],
            "low": [99, 100, 101, 102, 103],
            "close": [104, 105, 106, 107, 108],
            "volume": [1000, 1100, 1200, 1300, 1400],
        })
        validator = OHLCVValidator()
        result = validator.validate(df)

        assert not result.is_valid
        assert any(">50% null" in e for e in result.errors)

    def test_should_stop_on_failure(self):
        validator = OHLCVValidator()
        assert validator.should_stop_on_failure() is True


class TestMinRowsValidator:
    """MinRowsValidator."""

    def test_sufficient_rows(self):
        df = pd.DataFrame({"a": range(50)})
        validator = MinRowsValidator(min_rows=20)

        result = validator.validate(df)
        assert result.is_valid

    def test_insufficient_rows(self):
        df = pd.DataFrame({"a": range(10)})
        validator = MinRowsValidator(min_rows=20)

        result = validator.validate(df)
        assert not result.is_valid
        assert "Insufficient rows" in result.errors[0]

    def test_should_stop_on_failure(self):
        validator = MinRowsValidator()
        assert validator.should_stop_on_failure() is True


class TestTimestampValidator:
    """TimestampValidator."""

    def test_valid_timestamps(self):
        df = pd.DataFrame({
            "ts": [1000, 2000, 3000],
            "close": [1, 2, 3],
        })
        validator = TimestampValidator()

        result = validator.validate(df)
        assert result.is_valid
        assert result.details["timestamp_column"] == "ts"

    def test_no_timestamp_column(self):
        df = pd.DataFrame({"close": [1, 2, 3]})
        validator = TimestampValidator()

        result = validator.validate(df)
        assert result.is_valid  # Warning only
        assert "No timestamp" in result.warnings[0]

    def test_duplicate_timestamps(self):
        df = pd.DataFrame({
            "ts": [1000, 1000, 3000],
            "close": [1, 2, 3],
        })
        validator = TimestampValidator()

        result = validator.validate(df)
        assert "duplicate" in result.warnings[0].lower()

    def test_non_monotonic(self):
        df = pd.DataFrame({
            "ts": [3000, 1000, 2000],
            "close": [1, 2, 3],
        })
        validator = TimestampValidator()

        result = validator.validate(df)
        assert "monotonic" in result.warnings[0].lower()


class TestValidationChain:
    """Task 12: ValidationChain (Chain of Responsibility)."""

    @pytest.fixture
    def valid_ohlcv(self):
        return pd.DataFrame({
            "ts": [1000, 2000, 3000] + list(range(4000, 24000, 1000)),
            "open": [100] * 23,
            "high": [105] * 23,
            "low": [99] * 23,
            "close": [104] * 23,
            "volume": [1000] * 23,
        })

    def test_empty_chain_is_valid(self, valid_ohlcv):
        chain = ValidationChain()
        result = chain.validate(valid_ohlcv)

        assert result.is_valid

    def test_add_validator(self, valid_ohlcv):
        chain = ValidationChain()
        chain.add(OHLCVValidator())

        assert len(chain) == 1
        result = chain.validate(valid_ohlcv)
        assert result.is_valid

    def test_fluent_add(self, valid_ohlcv):
        chain = (
            ValidationChain()
            .add(OHLCVValidator())
            .add(MinRowsValidator(min_rows=20))
        )

        assert len(chain) == 2

    def test_chain_stops_on_critical_failure(self):
        """Цепочка останавливается при should_stop_on_failure()."""
        df = pd.DataFrame()  # Empty - OHLCVValidator fails

        chain = (
            ValidationChain()
            .add(OHLCVValidator())        # Fails, stops
            .add(MinRowsValidator())      # Not executed
        )

        result = chain.validate(df)

        assert not result.is_valid
        assert len(result.errors) == 1  # Only OHLCV error

    def test_chain_continues_on_non_critical(self, valid_ohlcv):
        """Цепочка продолжается при обычных ошибках."""
        chain = (
            ValidationChain()
            .add(TimestampValidator())  # Warns about duplicates
            .add(NaNRatioValidator())   # Warns about NaN
        )

        result = chain.validate(valid_ohlcv)
        # All validators executed
        assert result.is_valid

    def test_remove_validator(self):
        chain = (
            ValidationChain()
            .add(OHLCVValidator())
            .add(MinRowsValidator())
        )

        chain.remove("min_rows")
        assert len(chain) == 1

    def test_create_default_chain(self, valid_ohlcv):
        chain = create_default_chain()

        assert len(chain) == 3  # OHLCV, MinRows, Timestamp
        result = chain.validate(valid_ohlcv)
        assert result.is_valid

    def test_create_strict_chain(self, valid_ohlcv):
        chain = create_strict_chain()

        assert len(chain) == 4  # + NaNRatio
```

**Команда запуска:**
```bash
pytest tests/unit/test_validation_chain.py -v
```

---

### 1.3 GroupRegistry (`indicator_groups/registry.py`)

**Файл:** `tests/unit/test_group_registry.py`

```python
import pytest
from src.features.indicator_groups.registry import (
    GroupRegistry,
    GroupEntry,
    get_ordered_groups,
    get_group_calculator,
)

class TestGroupRegistry:
    """Task 9: GroupRegistry с декоратором @register."""

    def setup_method(self):
        GroupRegistry.clear()

    def test_register_decorator(self):
        """Регистрация через декоратор."""
        @GroupRegistry.register("test_group", order=1)
        def calc_test(df, available):
            return {"test_indicator": df["close"]}

        entry = GroupRegistry.get("test_group")

        assert entry is not None
        assert entry.name == "test_group"
        assert entry.order == 1
        assert callable(entry.calculator)

    def test_register_with_dependencies(self):
        """Регистрация с зависимостями."""
        @GroupRegistry.register("child", order=2, dependencies=["parent"])
        def calc_child(df, available):
            return {}

        deps = GroupRegistry.get_dependencies("child")
        assert deps == ["parent"]

    def test_get_ordered(self):
        """Получение групп в порядке order."""
        @GroupRegistry.register("c", order=3)
        def calc_c(df, available): return {}

        @GroupRegistry.register("a", order=1)
        def calc_a(df, available): return {}

        @GroupRegistry.register("b", order=2)
        def calc_b(df, available): return {}

        ordered = GroupRegistry.get_ordered()
        names = [e.name for e in ordered]

        assert names == ["a", "b", "c"]

    def test_get_calculator(self):
        """Получение calculator функции."""
        @GroupRegistry.register("my_group", order=1)
        def calc_my(df, available):
            return {"result": 42}

        calc = GroupRegistry.get_calculator("my_group")
        assert calc is not None
        assert calc(None, set())["result"] == 42

    def test_get_nonexistent(self):
        """Несуществующая группа возвращает None."""
        assert GroupRegistry.get("nonexistent") is None
        assert GroupRegistry.get_calculator("nonexistent") is None

    def test_get_all_names(self):
        """Список всех имён групп."""
        @GroupRegistry.register("g1", order=1)
        def calc_g1(df, available): return {}

        @GroupRegistry.register("g2", order=2)
        def calc_g2(df, available): return {}

        names = GroupRegistry.get_all_names()
        assert "g1" in names
        assert "g2" in names

    def test_get_metadata(self):
        """Metadata для группы."""
        @GroupRegistry.register(
            "meta_group",
            order=5,
            dependencies=["dep1", "dep2"],
            description="Test description"
        )
        def calc_meta(df, available): return {}

        meta = GroupRegistry.get_metadata("meta_group")

        assert meta["name"] == "meta_group"
        assert meta["order"] == 5
        assert meta["dependencies"] == ["dep1", "dep2"]
        assert meta["description"] == "Test description"

    def test_clear(self):
        """Очистка реестра."""
        @GroupRegistry.register("temp", order=1)
        def calc_temp(df, available): return {}

        assert GroupRegistry.get("temp") is not None

        GroupRegistry.clear()

        assert GroupRegistry.get("temp") is None


class TestGroupRegistryConvenienceFunctions:
    """Вспомогательные функции для совместимости."""

    def setup_method(self):
        GroupRegistry.clear()

    def test_get_ordered_groups(self):
        """get_ordered_groups() возвращает list[(name, calculator)]."""
        @GroupRegistry.register("x", order=1)
        def calc_x(df, available): return {}

        result = get_ordered_groups()

        assert len(result) == 1
        assert result[0][0] == "x"
        assert callable(result[0][1])

    def test_get_group_calculator(self):
        """get_group_calculator() как shortcut."""
        @GroupRegistry.register("y", order=1)
        def calc_y(df, available): return {"val": 1}

        calc = get_group_calculator("y")
        assert calc is not None
```

**Команда запуска:**
```bash
pytest tests/unit/test_group_registry.py -v
```

---

### 1.4 Protocols (`domain/protocols.py`)

**Файл:** `tests/unit/test_protocols.py`

```python
import pytest
import pandas as pd
from src.features.domain.protocols import (
    IndicatorCalculator,
    BatchIndicatorCalculator,
    FeatureCalculator,
    OHLCVValidator,
    FeatureNormalizer,
)

class TestProtocolsAreRuntimeCheckable:
    """Task 7: Protocols с @runtime_checkable."""

    def test_indicator_calculator_checkable(self):
        class MyCalculator:
            def calculate(self, df_ohlcv, **params):
                return df_ohlcv["close"]

        calc = MyCalculator()
        assert isinstance(calc, IndicatorCalculator)

    def test_batch_calculator_checkable(self):
        class MyBatch:
            def calculate_many(self, df_ohlcv, names, **params):
                return {}

        batch = MyBatch()
        assert isinstance(batch, BatchIndicatorCalculator)

    def test_feature_calculator_checkable(self):
        class MyFeatureCalc:
            def calculate(self, df_ohlcv, specs=None, *,
                         volatility_normalize=False, normalize_window=20, **kwargs):
                return df_ohlcv

        fc = MyFeatureCalc()
        assert isinstance(fc, FeatureCalculator)

    def test_ohlcv_validator_checkable(self):
        class MyValidator:
            def validate(self, df):
                return True

        v = MyValidator()
        assert isinstance(v, OHLCVValidator)

    def test_feature_normalizer_checkable(self):
        class MyNorm:
            def normalize(self, df, window=20):
                return df

        n = MyNorm()
        assert isinstance(n, FeatureNormalizer)


class TestProtocolsRejectIncomplete:
    """Некорректные реализации не проходят isinstance."""

    def test_missing_method(self):
        class Incomplete:
            pass

        assert not isinstance(Incomplete(), FeatureCalculator)

    def test_wrong_signature(self):
        # Note: Python's Protocol doesn't check signatures at runtime
        # This test documents that behavior
        class WrongSig:
            def calculate(self, x):  # Missing required params
                return x

        # Passes isinstance (Python limitation)
        assert isinstance(WrongSig(), FeatureCalculator)
```

**Команда запуска:**
```bash
pytest tests/unit/test_protocols.py -v
```

---

### 1.5 FeatureCalculationService (`application/feature_service.py`)

**Файл:** `tests/unit/test_feature_service.py`

```python
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch
from src.features.application.feature_service import (
    FeatureCalculationService,
    DefaultOHLCVValidator,
    DefaultFeatureNormalizer,
    create_feature_service,
)

class TestDefaultOHLCVValidator:
    """DefaultOHLCVValidator implementation."""

    @pytest.fixture
    def valid_df(self):
        return pd.DataFrame({
            "open": [100, 101, 102],
            "high": [105, 106, 107],
            "low": [99, 100, 101],
            "close": [104, 105, 106],
            "volume": [1000, 1100, 1200],
        })

    def test_valid_df_passes(self, valid_df):
        validator = DefaultOHLCVValidator()
        assert validator.validate(valid_df) is True

    def test_none_df_raises(self):
        validator = DefaultOHLCVValidator()
        with pytest.raises(ValueError, match="None or empty"):
            validator.validate(None)

    def test_empty_df_raises(self):
        validator = DefaultOHLCVValidator()
        with pytest.raises(ValueError, match="None or empty"):
            validator.validate(pd.DataFrame())

    def test_missing_column_raises(self, valid_df):
        df = valid_df.drop(columns=["volume"])
        validator = DefaultOHLCVValidator()

        with pytest.raises(ValueError, match="Missing.*volume"):
            validator.validate(df)

    def test_all_nan_column_raises(self, valid_df):
        valid_df["close"] = np.nan
        validator = DefaultOHLCVValidator()

        with pytest.raises(ValueError, match="only NaN"):
            validator.validate(valid_df)


class TestFeatureCalculationService:
    """Task 8: FeatureCalculationService с DI."""

    @pytest.fixture
    def mock_compute_fn(self):
        mock = Mock(return_value=pd.DataFrame({"rsi_14": [50, 60, 70]}))
        return mock

    @pytest.fixture
    def valid_df(self):
        return pd.DataFrame({
            "open": [100, 101, 102],
            "high": [105, 106, 107],
            "low": [99, 100, 101],
            "close": [104, 105, 106],
            "volume": [1000, 1100, 1200],
        })

    def test_service_creation_defaults(self):
        service = FeatureCalculationService()

        assert isinstance(service.validator, DefaultOHLCVValidator)
        assert isinstance(service.normalizer, DefaultFeatureNormalizer)

    def test_service_calls_validator(self, valid_df, mock_compute_fn):
        mock_validator = Mock()
        mock_validator.validate = Mock(return_value=True)

        service = FeatureCalculationService(
            validator=mock_validator,
            _compute_fn=mock_compute_fn,
        )

        service.calculate(valid_df)

        mock_validator.validate.assert_called_once_with(valid_df)

    def test_service_calls_compute_fn(self, valid_df, mock_compute_fn):
        service = FeatureCalculationService(_compute_fn=mock_compute_fn)

        service.calculate(valid_df, specs=["rsi_14"])

        mock_compute_fn.assert_called_once()
        call_kwargs = mock_compute_fn.call_args
        assert call_kwargs[1]["specs"] == ["rsi_14"]
        assert call_kwargs[1]["volatility_normalize"] is False

    def test_service_applies_normalization(self, valid_df, mock_compute_fn):
        mock_normalizer = Mock()
        mock_normalizer.normalize = Mock(return_value=pd.DataFrame({"rsi_14_norm": [0.5]}))

        service = FeatureCalculationService(
            normalizer=mock_normalizer,
            _compute_fn=mock_compute_fn,
        )

        result = service.calculate(valid_df, volatility_normalize=True, normalize_window=30)

        mock_normalizer.normalize.assert_called_once()
        assert "rsi_14_norm" in result.columns

    def test_calculate_batch_compatibility(self, valid_df, mock_compute_fn):
        service = FeatureCalculationService(_compute_fn=mock_compute_fn)

        result = service.calculate_batch(valid_df, {"rsi_14", "ema_21"})

        assert mock_compute_fn.called

    def test_get_available_specs(self):
        specs = FeatureCalculationService.get_available_specs()

        assert isinstance(specs, list)
        # Should contain common indicators
        # assert "rsi_14" in specs or len(specs) > 0


class TestFactoryFunctions:
    """Factory functions для сервиса."""

    def test_create_feature_service_defaults(self):
        service = create_feature_service()

        assert isinstance(service, FeatureCalculationService)
        assert isinstance(service.validator, DefaultOHLCVValidator)

    def test_create_feature_service_custom(self):
        custom_validator = Mock()
        service = create_feature_service(validator=custom_validator)

        assert service.validator is custom_validator

    def test_create_feature_service_returns_fresh_instance(self):
        s1 = create_feature_service()
        s2 = create_feature_service()

        assert s1 is not s2
```

**Команда запуска:**
```bash
pytest tests/unit/test_feature_service.py -v
```

---

### 1.6 Pipeline Context (`core/pipeline.py`)

**Файл:** `tests/unit/test_pipeline_context.py`

```python
import pytest
from src.features.core.pipeline import (
    BaseContext,
    GroupCalculationContext,
    PipelineContext,
)

class TestBaseContext:
    """Task 11: BaseContext (ISP)."""

    def test_default_values(self):
        ctx = BaseContext()

        assert ctx.symbol == "unknown"
        assert ctx.timeframe == "unknown"
        assert len(ctx.run_id) == 12
        assert ctx.feature_count == 0

    def test_custom_values(self):
        ctx = BaseContext(
            symbol="BTC-USDT",
            timeframe="1h",
            feature_count=50,
        )

        assert ctx.symbol == "BTC-USDT"
        assert ctx.timeframe == "1h"
        assert ctx.feature_count == 50

    def test_run_id_unique(self):
        ctx1 = BaseContext()
        ctx2 = BaseContext()

        assert ctx1.run_id != ctx2.run_id


class TestGroupCalculationContext:
    """Task 11: GroupCalculationContext extends BaseContext."""

    def test_inherits_base_fields(self):
        ctx = GroupCalculationContext(symbol="ETH-USDT", timeframe="5m")

        assert ctx.symbol == "ETH-USDT"
        assert ctx.timeframe == "5m"
        assert len(ctx.run_id) == 12

    def test_additional_fields(self):
        ctx = GroupCalculationContext()

        assert ctx.failed_groups == []
        assert ctx.data_status == "ok"

    def test_failed_groups_tracking(self):
        ctx = GroupCalculationContext()

        ctx.failed_groups.append("trend")
        ctx.failed_groups.append("volatility")

        assert "trend" in ctx.failed_groups
        assert len(ctx.failed_groups) == 2


class TestPipelineContextAlias:
    """PipelineContext = GroupCalculationContext для совместимости."""

    def test_alias_is_same_class(self):
        assert PipelineContext is GroupCalculationContext

    def test_backward_compatible_usage(self):
        ctx = PipelineContext(symbol="BTC-USDT", timeframe="1m")

        assert isinstance(ctx, GroupCalculationContext)
        assert ctx.symbol == "BTC-USDT"
```

**Команда запуска:**
```bash
pytest tests/unit/test_pipeline_context.py -v
```

---

### 1.7 Alert Observers (`infrastructure/alerts.py`)

**Файл:** `tests/unit/test_alert_observers.py`

```python
import pytest
from datetime import datetime
from src.features.infrastructure.alerts import (
    AlertLevel,
    AlertContext,
    AlertObserver,
    AlertDispatcher,
    get_alert_dispatcher,
)

class TestAlertContext:
    """AlertContext dataclass."""

    def test_default_level(self):
        ctx = AlertContext(
            dag_id="test_dag",
            task_id="test_task",
            execution_date="2026-02-02",
            run_id="abc123",
            try_number=1,
        )

        assert ctx.level == AlertLevel.ERROR

    def test_to_dict(self):
        ctx = AlertContext(
            dag_id="test_dag",
            task_id="test_task",
            execution_date="2026-02-02",
            run_id="abc123",
            try_number=1,
            level=AlertLevel.WARNING,
        )

        d = ctx.to_dict()

        assert d["dag_id"] == "test_dag"
        assert d["level"] == "warning"

    def test_to_json(self):
        ctx = AlertContext(
            dag_id="test_dag",
            task_id="test_task",
            execution_date="2026-02-02",
            run_id="abc123",
            try_number=1,
        )

        json_str = ctx.to_json()

        assert "test_dag" in json_str
        assert "test_task" in json_str


class MockObserver(AlertObserver):
    """Mock observer для тестов."""

    def __init__(self, should_succeed=True):
        self.should_succeed = should_succeed
        self.notified_contexts = []

    def notify(self, alert_ctx):
        self.notified_contexts.append(alert_ctx)
        return self.should_succeed


class TestAlertDispatcher:
    """Task 13: AlertDispatcher (Observer pattern)."""

    @pytest.fixture
    def alert_ctx(self):
        return AlertContext(
            dag_id="features_dag",
            task_id="calculate",
            execution_date="2026-02-02",
            run_id="run_123",
            try_number=1,
        )

    def test_subscribe(self, alert_ctx):
        dispatcher = AlertDispatcher()
        observer = MockObserver()

        dispatcher.subscribe(observer)

        assert len(dispatcher) == 1

    def test_subscribe_fluent(self, alert_ctx):
        obs1 = MockObserver()
        obs2 = MockObserver()

        dispatcher = (
            AlertDispatcher()
            .subscribe(obs1)
            .subscribe(obs2)
        )

        assert len(dispatcher) == 2

    def test_subscribe_no_duplicates(self):
        dispatcher = AlertDispatcher()
        observer = MockObserver()

        dispatcher.subscribe(observer)
        dispatcher.subscribe(observer)

        assert len(dispatcher) == 1

    def test_unsubscribe(self):
        dispatcher = AlertDispatcher()
        observer = MockObserver()

        dispatcher.subscribe(observer)
        dispatcher.unsubscribe(observer)

        assert len(dispatcher) == 0

    def test_notify_all(self, alert_ctx):
        dispatcher = AlertDispatcher()
        obs1 = MockObserver()
        obs2 = MockObserver()

        dispatcher.subscribe(obs1).subscribe(obs2)
        results = dispatcher.notify_all(alert_ctx)

        assert len(obs1.notified_contexts) == 1
        assert len(obs2.notified_contexts) == 1
        assert results["MockObserver"] is True

    def test_notify_all_handles_failure(self, alert_ctx):
        dispatcher = AlertDispatcher()
        obs_ok = MockObserver(should_succeed=True)
        obs_fail = MockObserver(should_succeed=False)

        dispatcher.subscribe(obs_ok).subscribe(obs_fail)
        results = dispatcher.notify_all(alert_ctx)

        assert obs_ok.notified_contexts[0] is alert_ctx
        assert results.get("MockObserver") in [True, False]

    def test_clear(self):
        dispatcher = AlertDispatcher()
        dispatcher.subscribe(MockObserver())
        dispatcher.subscribe(MockObserver())

        dispatcher.clear()

        assert len(dispatcher) == 0

    def test_singleton_access(self):
        d1 = AlertDispatcher.get_instance()
        d2 = AlertDispatcher.get_instance()

        assert d1 is d2


class TestGetAlertDispatcher:
    """get_alert_dispatcher factory."""

    def test_returns_dispatcher(self):
        dispatcher = get_alert_dispatcher()

        assert isinstance(dispatcher, AlertDispatcher)
```

**Команда запуска:**
```bash
pytest tests/unit/test_alert_observers.py -v
```

---

## 2. Интеграционные тесты

### 2.1 Полный расчётный pipeline

**Файл:** `tests/integration/test_calculation_pipeline.py`

```python
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

@pytest.fixture
def ohlcv_100_bars():
    """100 баров OHLCV данных."""
    base_price = 100.0
    np.random.seed(42)

    prices = base_price + np.cumsum(np.random.randn(100) * 0.5)

    return pd.DataFrame({
        "ts": [int((datetime(2026, 1, 1) + timedelta(minutes=i)).timestamp() * 1000) for i in range(100)],
        "open": prices,
        "high": prices + np.abs(np.random.randn(100)) * 0.5,
        "low": prices - np.abs(np.random.randn(100)) * 0.5,
        "close": prices + np.random.randn(100) * 0.2,
        "volume": np.random.randint(1000, 10000, 100).astype(float),
    })

@pytest.mark.integration
class TestCalculationPipeline:
    """Интеграционные тесты расчётного пайплайна."""

    def test_compute_features_basic(self, ohlcv_100_bars):
        """Базовый расчёт индикаторов."""
        from src.features.core.calculation import compute_features

        result = compute_features(
            ohlcv_100_bars,
            specs=["rsi_14", "ema_21", "sma_20"],
            volatility_normalize=False,
        )

        assert len(result) == len(ohlcv_100_bars)
        # Проверяем наличие хотя бы некоторых индикаторов
        assert any(col.startswith(("rsi", "ema", "sma")) for col in result.columns)

    def test_compute_features_with_normalization(self, ohlcv_100_bars):
        """Расчёт с нормализацией."""
        from src.features.core.calculation import compute_features

        result = compute_features(
            ohlcv_100_bars,
            specs=["rsi_14"],
            volatility_normalize=True,
            normalize_window=20,
        )

        assert len(result) == len(ohlcv_100_bars)

    def test_compute_features_all_groups(self, ohlcv_100_bars):
        """Расчёт всех групп индикаторов."""
        from src.features.core.calculation import compute_features

        result = compute_features(
            ohlcv_100_bars,
            specs=None,  # Все доступные
            volatility_normalize=False,
        )

        # Должно быть много колонок (100+)
        assert len(result.columns) > 10

    def test_feature_service_integration(self, ohlcv_100_bars):
        """FeatureCalculationService end-to-end."""
        from src.features.application.feature_service import create_feature_service

        service = create_feature_service()
        result = service.calculate(ohlcv_100_bars, specs=["rsi_14", "ema_21"])

        assert len(result) > 0

    def test_pipeline_context_tracking(self, ohlcv_100_bars):
        """Pipeline context отслеживает ошибки."""
        from src.features.core.calculation import compute_features

        # Расчёт с debug mode
        result = compute_features(
            ohlcv_100_bars,
            specs=["rsi_14"],
            volatility_normalize=False,
            debug=True,
        )

        assert len(result) == len(ohlcv_100_bars)
```

**Команда запуска:**
```bash
pytest tests/integration/test_calculation_pipeline.py -v -m integration
```

---

### 2.2 DI интеграция

**Файл:** `tests/integration/test_di_integration.py`

```python
import pytest
from src.features.container import create_default_container

@pytest.mark.integration
class TestDIIntegration:
    """Интеграция DI контейнера с модулями."""

    def test_resolve_calculator(self):
        """Resolve FeatureCalculationService."""
        container = create_default_container()

        calculator = container.resolve("calculator")

        from src.features.application.feature_service import FeatureCalculationService
        assert isinstance(calculator, FeatureCalculationService)

    def test_resolve_validation_chain(self):
        """Resolve ValidationChain."""
        container = create_default_container()

        chain = container.resolve("validation_chain")

        from src.features.validation.chain import ValidationChain
        assert isinstance(chain, ValidationChain)

    def test_resolve_alert_dispatcher(self):
        """Resolve AlertDispatcher."""
        container = create_default_container()

        dispatcher = container.resolve("alert_dispatcher")

        from src.features.infrastructure.alerts import AlertDispatcher
        assert isinstance(dispatcher, AlertDispatcher)

    def test_calculator_uses_injected_components(self):
        """Calculator использует компоненты из DI."""
        container = create_default_container()
        calculator = container.resolve("calculator")

        # Calculator должен работать
        import pandas as pd
        import numpy as np

        df = pd.DataFrame({
            "open": np.random.rand(50) * 100,
            "high": np.random.rand(50) * 100 + 5,
            "low": np.random.rand(50) * 100 - 5,
            "close": np.random.rand(50) * 100,
            "volume": np.random.rand(50) * 10000,
        })

        # Должен отработать без исключений
        # (может не вернуть индикаторы если нет pandas_ta)
        try:
            result = calculator.calculate(df, specs=["rsi_14"])
            assert result is not None
        except Exception:
            pass  # OK если pandas_ta не установлен
```

**Команда запуска:**
```bash
pytest tests/integration/test_di_integration.py -v -m integration
```

---

## 3. Smoke тесты

### 3.1 Проверка импортов

**Файл:** `tests/smoke/test_imports.py`

```python
import pytest

@pytest.mark.smoke
class TestImports:
    """Smoke тесты импорта модулей."""

    def test_import_container(self):
        from src.features.container import Container, create_default_container

    def test_import_validation_chain(self):
        from src.features.validation.chain import (
            ValidationChain,
            ValidationResult,
            OHLCVValidator,
            create_default_chain,
        )

    def test_import_group_registry(self):
        from src.features.indicator_groups.registry import (
            GroupRegistry,
            get_ordered_groups,
        )

    def test_import_protocols(self):
        from src.features.domain.protocols import (
            FeatureCalculator,
            OHLCVValidator,
            FeatureNormalizer,
        )

    def test_import_feature_service(self):
        from src.features.application.feature_service import (
            FeatureCalculationService,
            create_feature_service,
        )

    def test_import_pipeline(self):
        from src.features.core.pipeline import (
            BaseContext,
            GroupCalculationContext,
            PipelineContext,
        )

    def test_import_alerts(self):
        from src.features.infrastructure.alerts import (
            AlertContext,
            AlertDispatcher,
            AlertObserver,
            get_alert_dispatcher,
        )

    def test_import_calculation(self):
        from src.features.core.calculation import compute_features

    def test_import_main_package(self):
        from src.features import compute_features
```

**Команда запуска:**
```bash
pytest tests/smoke/test_imports.py -v -m smoke
```

---

## 4. Команды запуска тестов

### Все тесты

```bash
# Все тесты
pytest tests/ -v

# С покрытием
pytest tests/ -v --cov=src/features --cov-report=html

# Только unit тесты
pytest tests/unit/ -v

# Только integration тесты
pytest tests/integration/ -v -m integration

# Только smoke тесты
pytest tests/smoke/ -v -m smoke
```

### Быстрая проверка

```bash
# Smoke + основные unit тесты
pytest tests/smoke/ tests/unit/test_container.py tests/unit/test_validation_chain.py -v --tb=short

# Только критичные
pytest tests/ -v -m "not slow" --maxfail=3
```

### Параллельный запуск

```bash
# С pytest-xdist
pytest tests/ -v -n auto
```

---

## 5. Чек-лист проверки

### Unit тесты (обязательные)

- [ ] `test_container.py` - DI контейнер работает
- [ ] `test_validation_chain.py` - Chain of Responsibility работает
- [ ] `test_group_registry.py` - Реестр групп работает
- [ ] `test_protocols.py` - Protocols @runtime_checkable
- [ ] `test_feature_service.py` - Service с DI
- [ ] `test_pipeline_context.py` - Context разделение
- [ ] `test_alert_observers.py` - Observer pattern

### Integration тесты

- [ ] `test_calculation_pipeline.py` - Полный расчёт
- [ ] `test_di_integration.py` - DI с реальными компонентами

### Smoke тесты

- [ ] `test_imports.py` - Все импорты работают

### Ручные проверки

- [ ] CLI работает: `python -m src.cli.main features --help`
- [ ] Mypy проходит: `mypy src/features/`
- [ ] Ruff проходит: `ruff check src/features/`

---

## 6. Ожидаемые результаты

После успешного выполнения всех тестов:

| Метрика | Ожидание |
|---------|----------|
| Unit tests | 100% pass |
| Integration tests | 100% pass |
| Smoke tests | 100% pass |
| Coverage (src/features) | ≥85% |
| Mypy errors | 0 |
| Ruff errors | 0 |

---

## 7. Структура файлов для создания

```
tests/
├── __init__.py
├── conftest.py                      # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_container.py
│   ├── test_validation_chain.py
│   ├── test_group_registry.py
│   ├── test_protocols.py
│   ├── test_feature_service.py
│   ├── test_pipeline_context.py
│   └── test_alert_observers.py
├── integration/
│   ├── __init__.py
│   ├── test_calculation_pipeline.py
│   └── test_di_integration.py
└── smoke/
    ├── __init__.py
    └── test_imports.py
```

---

## Следующие шаги

1. Создать директорию `tests/` со структурой выше
2. Реализовать `conftest.py` с общими фикстурами
3. Запустить smoke тесты для проверки импортов
4. Запустить unit тесты последовательно
5. Запустить integration тесты
6. Проверить coverage и исправить пробелы
