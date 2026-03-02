---
name: eval-harness
description: Evaluation framework for PKLPO sessions using pytest: capability evals as fixtures, regression evals via --lf, performance evals with pytest-benchmark, pass@k via parametrize.
category: testing
model: sonnet
tools: [Read, Grep, Glob, Edit, Bash]
---

# Eval Harness Skill (Python / pytest)

A formal evaluation framework implementing eval-driven development (EDD) for PKLPO.

## Philosophy

Eval-Driven Development treats evals as the "unit tests of AI development":
- Define expected behavior **before** implementation
- Run evals continuously during development
- Track regressions with each change
- Use pass@k metrics for reliability measurement

## Eval Types

### Capability Evals
Test if a new feature works correctly. Implement as pytest fixtures or test functions:

```python
# tests/evals/test_capability_rsi.py
import pytest
import pandas as pd

@pytest.mark.smoke
def test_capability_rsi_returns_bounded_values(sample_ohlcv):
    """Capability eval: RSI must stay in [0, 100]."""
    from src.features.specs.oscillators import rsi_spec
    result = rsi_spec(sample_ohlcv, period=14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all(), "RSI out of [0, 100] bounds"

@pytest.mark.smoke
def test_capability_compute_features_returns_all_specs(sample_ohlcv):
    """Capability eval: compute_features must return all requested specs."""
    from src.features.core import compute_features
    specs = ["rsi_14", "ema_21", "macd"]
    result = compute_features(sample_ohlcv, specs=specs)
    for spec in specs:
        assert spec in result.columns, f"Missing column: {spec}"
```

### Regression Evals
Ensure changes don't break existing behavior. Use `pytest --lf` (last-failed) for fast regression check:

```bash
# Run only previously failing tests
pytest --lf -v

# Run and stop on first regression
pytest --lf -x
```

Mark baselines explicitly:

```python
# tests/evals/test_regression_indicators.py
import pytest

@pytest.mark.parametrize("symbol,timeframe", [
    ("BTC-USDT-SWAP", "1m"),
    ("ETH-USDT-SWAP", "5m"),
])
@pytest.mark.integration
async def test_regression_indicator_count(symbol, timeframe, db_session):
    """Regression eval: row count must not decrease after refactor."""
    from src.features.infrastructure.database import IndicatorRepository
    repo = IndicatorRepository(db_session)
    count = await repo.count(symbol=symbol, timeframe=timeframe)
    # Baseline established 2025-01-01 — must not regress
    assert count >= 10_000, f"Regression: {symbol} {timeframe} has only {count} rows"
```

## Grader Types

### 1. Code-Based Grader (deterministic)

```python
@pytest.mark.smoke
def test_grader_no_lookahead_bias(sample_ohlcv):
    """Grader: indicator at bar T must not use data from bar T+1."""
    from src.features.core import compute_features
    df = sample_ohlcv.copy()
    result_full = compute_features(df, specs=["rsi_14"])

    # Compute on truncated data (drop last bar)
    result_short = compute_features(df.iloc[:-1], specs=["rsi_14"])

    # Value at second-to-last bar must be identical
    assert result_full["rsi_14"].iloc[-2] == pytest.approx(
        result_short["rsi_14"].iloc[-1], rel=1e-6
    ), "Look-ahead bias detected!"
```

### 2. Performance Grader (pytest-benchmark)

```python
# tests/evals/test_performance.py
def test_benchmark_compute_features(benchmark, large_ohlcv):
    """Performance eval: compute_features for 200K rows must finish in < 10s."""
    from src.features.core import compute_features
    result = benchmark(compute_features, large_ohlcv, specs=["rsi_14", "ema_21", "macd"])
    assert not result.empty
```

Run benchmarks:
```bash
pytest tests/evals/test_performance.py --benchmark-only
pytest tests/evals/test_performance.py --benchmark-compare   # compare vs baseline
```

### 3. Human Review Grader

Flag for manual review in code comments:
```python
# [HUMAN REVIEW REQUIRED]
# Change: UPSERT conflict resolution strategy updated
# Reason: May affect historical data integrity
# Risk Level: HIGH
```

## pass@k Metrics

Implement via `pytest.mark.parametrize` with multiple random seeds:

```python
@pytest.mark.parametrize("seed", [42, 123, 999])  # k=3
def test_passk_rsi_stability(seed):
    """pass@3: RSI result must be stable across different data seeds."""
    import numpy as np
    rng = np.random.default_rng(seed)
    close = pd.Series(100 + rng.normal(0, 1, 200).cumsum())
    df = pd.DataFrame({"close": close, "open": close, "high": close, "low": close, "volume": 1000.0})

    from src.features.specs.oscillators import rsi_spec
    result = rsi_spec(df, period=14)
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()
```

Pass@k threshold: **all 3 seeds must pass** for critical paths.

## Eval Workflow

### 1. Define (Before Coding)

```markdown
## EVAL DEFINITION: feature-xyz

### Capability Evals
- [ ] compute_features returns expected columns
- [ ] values are within valid bounds
- [ ] no look-ahead bias

### Regression Evals
- [ ] existing indicators unchanged
- [ ] UPSERT idempotency preserved
- [ ] DB row counts stable

### Performance Evals
- [ ] 200K rows processed in < 10s

### Success Metrics
- pass@3 > 90% for capability evals
- pass^3 = 100% for regression evals
```

### 2. Implement
Write code to pass the defined evals.

### 3. Evaluate

```bash
# Capability + regression
pytest tests/evals/ -v --tb=short

# With coverage
pytest tests/evals/ --cov=src --cov-report=term-missing

# Performance only
pytest tests/evals/test_performance.py --benchmark-only
```

### 4. Report

```
EVAL REPORT: feature-xyz
========================

Capability Evals:
  rsi_bounded_values:     PASS (pass@1)
  all_specs_returned:     PASS (pass@1)
  no_lookahead_bias:      PASS (pass@1)
  Overall:                3/3 passed

Regression Evals:
  indicator_count_BTC:    PASS
  indicator_count_ETH:    PASS
  upsert_idempotency:     PASS
  Overall:                3/3 passed

Performance Evals:
  compute_features_200k:  PASS (8.3s < 10s target)

Metrics:
  pass@1: 100% (3/3)
  pass@3: 100% (all seeds)

Status: READY FOR REVIEW
```

## Eval Storage

```
.claude/
  evals/
    feature-xyz.md          # eval definition
    baselines.json          # regression baselines (row counts, etc.)
tests/
  evals/
    test_capability_*.py
    test_regression_*.py
    test_performance.py
```

## Integration with CI

```bash
# In pre-PR verification
pytest -m "smoke" -x -q              # fast smoke evals first
pytest -m "not slow and not performance" --cov=src  # full suite
pytest tests/evals/test_performance.py --benchmark-only  # performance gate
```

## Best Practices

1. **Define evals BEFORE coding** — forces clear thinking about success criteria
2. **Run `pytest --lf` after refactoring** — catch regressions fast
3. **Track benchmark history** — use `--benchmark-compare` to detect slowdowns
4. **Use `pass@3` for flaky areas** — parametrize with multiple seeds
5. **Human review for DB schema changes** — never fully automate critical migrations
6. **Keep evals fast** — slow evals don't get run; mark with `@pytest.mark.slow`
7. **Version evals with code** — eval files are first-class artifacts in git

**Remember**: Evals are the contract between intent and implementation. Define them first, implement to pass them.
