---
name: tdd-workflow
description: Use this skill when writing new features, fixing bugs, or refactoring code. Enforces test-driven development with pytest, 85%+ coverage, unit/integration markers, and async support.
---

# Test-Driven Development Workflow (Python / pytest)

This skill ensures all code follows TDD principles with comprehensive test coverage using the project's pytest stack.

## When to Activate

- Writing new features or functionality
- Fixing bugs or issues
- Refactoring existing code
- Adding new indicator groups or services

## Core Principles

### 1. Tests BEFORE Code
Write tests first, then implement the minimum code to make them pass.

### 2. Coverage Requirements (from CLAUDE.md)
- Minimum **85% total** coverage
- **90%** on changed lines
- All edge cases and error paths covered

### 3. Test Markers

```python
import pytest

@pytest.mark.unit
def test_something(): ...

@pytest.mark.integration
def test_db_something(): ...

@pytest.mark.slow
def test_heavy_computation(): ...

@pytest.mark.smoke
def test_critical_path(): ...
```

Run selectively:
```bash
pytest -m "not slow"       # skip slow tests during development
pytest -m integration      # only integration tests
pytest -m "unit or smoke"  # fast feedback loop
```

## TDD Workflow Steps

### Step 1: Write the failing test

```python
# tests/test_rsi_service.py
import pytest
from src.features.specs.oscillators import rsi_spec

def test_rsi_returns_series_with_correct_length(sample_ohlcv):
    result = rsi_spec(sample_ohlcv, period=14)
    assert len(result) == len(sample_ohlcv)

def test_rsi_values_within_bounds(sample_ohlcv):
    result = rsi_spec(sample_ohlcv, period=14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()

def test_rsi_raises_on_insufficient_data():
    import pandas as pd
    tiny = pd.DataFrame({"close": [1.0, 2.0]})
    with pytest.raises(ValueError, match="insufficient"):
        rsi_spec(tiny, period=14)
```

### Step 2: Run — tests should fail
```bash
pytest tests/test_rsi_service.py -v
# FAILED — not implemented yet
```

### Step 3: Implement the minimum code to pass
```python
# src/features/specs/oscillators.py
import pandas as pd

def rsi_spec(df: pd.DataFrame, period: int = 14) -> pd.Series:
    if len(df) < period + 1:
        raise ValueError(f"insufficient data: need {period+1} rows, got {len(df)}")
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))
```

### Step 4: Run tests — should pass
```bash
pytest tests/test_rsi_service.py -v
# PASSED
```

### Step 5: Refactor while keeping tests green
Improve naming, extract helpers, clean up. Run tests after each change.

### Step 6: Verify coverage
```bash
pytest --cov=src --cov-report=term-missing
# Ensure 85%+ total, 90%+ on changed lines
```

## Fixtures and conftest.py

Shared fixtures go in `conftest.py`:

```python
# tests/conftest.py
import pytest
import pandas as pd
import numpy as np

@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """200 bars of synthetic OHLCV data."""
    n = 200
    rng = np.random.default_rng(42)
    close = 100 + rng.normal(0, 1, n).cumsum()
    return pd.DataFrame({
        "open":   close * 0.999,
        "high":   close * 1.002,
        "low":    close * 0.998,
        "close":  close,
        "volume": rng.integers(1000, 5000, n).astype(float),
    })

@pytest.fixture
def db_session():
    """Async DB session for integration tests (uses test DB)."""
    # configure via POSTGRES_DB=test_pklpo env var
    from src.database import async_session_maker
    return async_session_maker()
```

## Parametrize Pattern

```python
@pytest.mark.parametrize("period,expected_nulls", [
    (14, 14),
    (20, 20),
    (5,  5),
])
def test_rsi_null_prefix_length(sample_ohlcv, period, expected_nulls):
    result = rsi_spec(sample_ohlcv, period=period)
    assert result.isna().sum() == expected_nulls
```

## Async Tests (pytest-asyncio)

```python
import pytest
import pytest_asyncio

@pytest.mark.asyncio
async def test_fetch_instruments(db_session):
    from src.features.infrastructure.database import fetch_instruments
    instruments = await fetch_instruments(db_session)
    assert isinstance(instruments, list)
    assert len(instruments) > 0
```

## Mocking with pytest-mock / unittest.mock

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_save_indicators_calls_upsert(sample_ohlcv):
    with patch("src.features.infrastructure.db_operations.upsert_indicators") as mock_upsert:
        mock_upsert.return_value = AsyncMock(return_value=None)()
        from src.features.application.save import save_features
        await save_features(sample_ohlcv, symbol="BTC-USDT-SWAP", timeframe="1m")
        mock_upsert.assert_called_once()
```

## Test File Organization

```
tests/
├── conftest.py                    # shared fixtures
├── test_phase1_blocks.py          # smoke / integration
├── candles/
│   ├── test_sync_candles.py
│   └── test_repository.py
src/features/tests/
├── test_core.py                   # unit tests for compute_features
├── test_pipeline.py
└── test_group_calculation.py
```

## Coverage Configuration (pyproject.toml)

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow",
    "integration: marks integration tests",
    "unit: marks unit tests",
    "smoke: marks smoke tests",
    "asyncio: marks async tests",
]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
fail_under = 85
show_missing = true
```

## Common Mistakes to Avoid

### ❌ WRONG: Testing implementation details
```python
# Don't assert on private attributes
assert service._cache == {}
```

### ✅ CORRECT: Test observable behavior
```python
assert service.get("key") is None
```

### ❌ WRONG: Tests depend on each other
```python
def test_a():
    shared_state.append(1)   # mutates shared state

def test_b():
    assert len(shared_state) == 1  # depends on test_a running first
```

### ✅ CORRECT: Each test is independent
```python
def test_a(fresh_state):
    fresh_state.append(1)
    assert len(fresh_state) == 1

def test_b(fresh_state):
    assert len(fresh_state) == 0
```

## CI Pipeline

```bash
# Run before every PR
black src/ --check           # format check
ruff check src/              # lint
mypy src/                    # types
pytest -m "not slow" --cov=src --cov-report=term-missing
```

## Success Metrics

- 85%+ total coverage, 90%+ on changed lines
- All tests pass (`pytest` exits 0)
- No skipped or xfail tests without explanation
- Unit tests complete in < 30s
- Integration tests complete in < 2 min

**Remember**: Tests are not optional. They are the safety net that enables confident refactoring and reliable indicator calculations.
