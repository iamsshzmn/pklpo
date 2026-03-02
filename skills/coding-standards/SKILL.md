---
name: coding-standards
description: Python coding standards for PKLPO: PEP 8, Black (line-length 88), Ruff, mypy, Google docstrings, function size limits, import order.
---

# Coding Standards (Python / PKLPO)

Standards as defined in `CLAUDE.md`. All new code must comply.

## Formatting

- **Black** with `line-length = 88`
- **Ruff** linter — run `ruff check src/` before every commit
- Never bypass with `# noqa` without a comment explaining why

```bash
black src/          # format
ruff check src/     # lint
ruff check src/ --fix   # auto-fix safe issues
```

## Type Hints

Type hints are **required** on all function signatures. `mypy` must pass.

```python
# ✅ GOOD
def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series: ...

async def fetch_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame: ...

# ❌ BAD — no type hints
def compute_rsi(df, period=14): ...
```

Use `TYPE_CHECKING` for imports only needed by type checkers:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from sqlalchemy.ext.asyncio import AsyncSession
```

Avoid `Any` — use `object` or proper generics when type is truly unknown.

## Function / Module Size Limits

| Constraint | Limit |
|---|---|
| Function max lines | **25** |
| Nesting max levels | **2** |
| Module max lines | **400** |

Long functions must be split into smaller helpers.

```python
# ✅ GOOD: small, focused functions
def _validate_period(period: int) -> None:
    if period < 2:
        raise ValueError(f"period must be >= 2, got {period}")

def _compute_gain_loss(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    delta = close.diff()
    return delta.clip(lower=0), (-delta.clip(upper=0))

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    _validate_period(period)
    gain, loss = _compute_gain_loss(close)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
```

## Import Order

stdlib → third-party → local. One blank line between groups.

```python
# ✅ GOOD
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pandas as pd
import numpy as np
from sqlalchemy import select

from src.models import Instrument
from src.features.core import compute_features
```

## Naming Conventions

| Entity | Convention | Example |
|---|---|---|
| Module, variable, function | `snake_case` | `calc_features`, `ohlcv_df` |
| Class | `PascalCase` | `FeatureService` |
| Constant | `UPPER_SNAKE` | `CHUNK_SIZE = 200_000` |
| Private helper | `_underscore` | `_validate_period` |

Booleans should read as questions:
```python
is_active: bool
has_sufficient_data: bool
can_upsert: bool
```

## Docstrings (Google Style)

Required on all public functions and classes:

```python
def compute_features(
    df: pd.DataFrame,
    specs: list[str],
    volatility_normalize: bool = False,
    normalize_window: int = 20,
) -> pd.DataFrame:
    """Compute technical indicator features for a given OHLCV DataFrame.

    Args:
        df: OHLCV data with columns [open, high, low, close, volume].
        specs: List of indicator spec names, e.g. ['rsi_14', 'ema_21'].
        volatility_normalize: If True, normalize outputs by rolling volatility.
        normalize_window: Window size for normalization.

    Returns:
        DataFrame with original columns plus computed indicator columns.

    Raises:
        ValueError: If df is missing required OHLCV columns.
    """
```

Do NOT add docstrings to private helpers or trivial one-liners.

## Error Handling

Catch specific exceptions. Always log with context. Re-raise with meaningful messages.

```python
# ✅ GOOD
try:
    result = await session.execute(stmt)
except OperationalError as exc:
    logger.error("DB connection failed for %s: %s", symbol, exc)
    raise RuntimeError(f"Failed to fetch OHLCV for {symbol}") from exc

# ❌ BAD
try:
    result = await session.execute(stmt)
except Exception:
    pass
```

Use early returns to reduce nesting (max 2 levels):

```python
# ✅ GOOD
async def process(symbol: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    if len(df) < MIN_ROWS:
        logger.warning("Insufficient data for %s (%d rows)", symbol, len(df))
        return 0
    return await _upsert(df)

# ❌ BAD — 3+ levels of nesting
async def process(symbol: str, df: pd.DataFrame) -> int:
    if not df.empty:
        if len(df) >= MIN_ROWS:
            return await _upsert(df)
```

## Constants over Magic Numbers

```python
# ✅ GOOD
CHUNK_SIZE = 200_000
MIN_CANDLES_FOR_RSI = 15
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10

# ❌ BAD
chunk = df.iloc[:200000]
if len(df) > 15:
    ...
```

## Immutability Preference

Prefer creating new objects over mutating:

```python
# ✅ GOOD
updated = {**config, "debug": True}

# For DataFrames — assign, don't mutate in-place
result = df.assign(rsi=rsi_series)

# ❌ BAD
config["debug"] = True
df["rsi"] = rsi_series  # in-place mutation of input
```

## Safety Conventions

Destructive DB/file operations must default to dry-run:
```python
# ✅ GOOD
async def delete_partitions(before: date, apply: bool = False) -> list[str]:
    partitions = await _find_old_partitions(before)
    if not apply:
        logger.info("DRY RUN: would delete %d partitions", len(partitions))
        return partitions
    # ... actual deletion
```

**Remember**: Code quality is enforced by CI. Black + Ruff + mypy must all pass before merging.
