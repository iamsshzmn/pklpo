---
name: backend-patterns
description: Python backend patterns for this project: SQLAlchemy 2.0 async, repository pattern, UPSERT, chunked processing, dependency injection via container.py.
---

# Backend Development Patterns (Python / SQLAlchemy async)

Patterns for the PKLPO Python backend: asyncpg, SQLAlchemy 2.0, PostgreSQL, OKX data pipeline.

## Database: SQLAlchemy 2.0 Async

### Session Setup

```python
# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/db",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

### Async Context Manager

```python
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

@asynccontextmanager
async def get_session():
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

## Repository Pattern

```python
# src/candles/repository.py
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Instrument, OHLCV

class InstrumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_symbol(self, symbol: str) -> Instrument | None:
        result = await self._session.execute(
            select(Instrument).where(Instrument.symbol == symbol)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Instrument]:
        result = await self._session.execute(
            select(Instrument).where(Instrument.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def upsert(self, data: dict) -> None:
        await self._session.execute(
            text("""
                INSERT INTO instruments (symbol, base, quote, is_active)
                VALUES (:symbol, :base, :quote, :is_active)
                ON CONFLICT (symbol) DO UPDATE SET
                    is_active = EXCLUDED.is_active
            """),
            data,
        )
```

## UPSERT Pattern (Composite Key)

All DB writes use `(symbol, timeframe, timestamp)` composite key for idempotency:

```python
# src/features/infrastructure/db_operations.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd

async def upsert_indicators(
    session: AsyncSession,
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
) -> int:
    """UPSERT indicator rows. Returns number of rows affected."""
    records = df.to_dict("records")

    stmt = text("""
        INSERT INTO indicators_p (symbol, timeframe, timestamp, rsi_14, ema_21)
        VALUES (:symbol, :timeframe, :timestamp, :rsi_14, :ema_21)
        ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE SET
            rsi_14 = EXCLUDED.rsi_14,
            ema_21 = EXCLUDED.ema_21
    """)

    await session.execute(stmt, records)
    return len(records)
```

## Chunked Processing (200K rows default)

Large datasets are split into overlapping chunks to fit in memory:

```python
# src/features/core/pipeline.py
from collections.abc import Iterator
import pandas as pd

CHUNK_SIZE = 200_000
OVERLAP = 500  # extra rows for indicator warmup

def iter_chunks(df: pd.DataFrame, chunk_size: int = CHUNK_SIZE) -> Iterator[pd.DataFrame]:
    """Yield overlapping chunks for streaming calculation."""
    n = len(df)
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        # include overlap from previous chunk for indicator warmup
        overlap_start = max(0, start - OVERLAP)
        chunk = df.iloc[overlap_start:end]
        yield chunk, start, end
        start = end


async def process_large_dataset(
    df: pd.DataFrame,
    session: AsyncSession,
    symbol: str,
    timeframe: str,
) -> int:
    total = 0
    for chunk, start, end in iter_chunks(df):
        result = compute_features(chunk, specs=["rsi_14", "ema_21"])
        # trim overlap before saving
        result_trimmed = result.iloc[max(0, start - (start // CHUNK_SIZE * CHUNK_SIZE)):]
        total += await upsert_indicators(session, result_trimmed, symbol, timeframe)
    return total
```

## Dependency Injection (container.py)

```python
# src/features/container.py
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import async_session_maker
from src.features.infrastructure.database import IndicatorRepository
from src.features.application.calc import FeatureCalculator

@dataclass
class Container:
    session: AsyncSession
    indicator_repo: IndicatorRepository
    calculator: FeatureCalculator

    @classmethod
    async def create(cls) -> "Container":
        session = async_session_maker()
        return cls(
            session=session,
            indicator_repo=IndicatorRepository(session),
            calculator=FeatureCalculator(),
        )

    async def __aenter__(self) -> "Container":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.session.close()
```

Usage:
```python
async with await Container.create() as c:
    df = await c.indicator_repo.fetch_ohlcv("BTC-USDT-SWAP", "1m")
    result = c.calculator.compute(df)
    await c.indicator_repo.upsert(result)
```

## Service Layer Pattern

```python
# src/features/application/calc.py
from src.features.core import compute_features
from src.features.infrastructure.database import OHLCVRepository, IndicatorRepository
import pandas as pd

class FeatureService:
    def __init__(
        self,
        ohlcv_repo: OHLCVRepository,
        indicator_repo: IndicatorRepository,
    ) -> None:
        self._ohlcv = ohlcv_repo
        self._indicators = indicator_repo

    async def run(self, symbol: str, timeframe: str) -> int:
        df = await self._ohlcv.fetch(symbol, timeframe)
        if df.empty:
            return 0
        result = compute_features(df, specs=["rsi_14", "ema_21", "macd"])
        return await self._indicators.upsert(result, symbol, timeframe)
```

## Connection Pooling Configuration

```python
engine = create_async_engine(
    dsn,
    pool_size=5,           # persistent connections
    max_overflow=10,       # extra connections under load
    pool_timeout=30,       # seconds to wait for a connection
    pool_recycle=1800,     # recycle connections after 30 min
    pool_pre_ping=True,    # validate connection before use
)
```

## Error Handling

```python
from sqlalchemy.exc import IntegrityError, OperationalError
import logging

logger = logging.getLogger(__name__)

async def safe_upsert(session: AsyncSession, records: list[dict]) -> int:
    try:
        await upsert_indicators(session, records)
        await session.commit()
        return len(records)
    except IntegrityError as e:
        await session.rollback()
        logger.error("Integrity error during upsert: %s", e)
        raise
    except OperationalError as e:
        await session.rollback()
        logger.error("DB connection error: %s", e)
        raise
```

## Retry with Exponential Backoff

```python
# src/features/infrastructure/retry.py
import asyncio
import logging
from collections.abc import Callable, Awaitable
from typing import TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)

async def with_retry(
    fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    for attempt in range(max_retries):
        try:
            return await fn()
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("Attempt %d failed (%s), retrying in %.1fs", attempt + 1, exc, delay)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")
```

## Group-Based Calculation Pipeline

Indicators are calculated in dependency order across 10 groups:

```python
# src/features/core/group_calculation.py
from src.features.specs import (
    candles, ma, oscillators, overlap,
    performance, statistics, trend, volatility, volume,
)

INDICATOR_GROUPS = [
    ("candles",     candles.SPECS),
    ("ma",          ma.SPECS),
    ("overlap",     overlap.SPECS),
    ("oscillators", oscillators.SPECS),
    ("volatility",  volatility.SPECS),
    ("trend",       trend.SPECS),
    ("volume",      volume.SPECS),
    ("statistics",  statistics.SPECS),
    ("performance", performance.SPECS),
]

def compute_all_groups(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for group_name, specs in INDICATOR_GROUPS:
        result = compute_features(result, specs=specs)
    return result
```

## Security Reminders

- Never commit `POSTGRES_PASSWORD` or other secrets — use env vars
- Validate symbol/timeframe inputs at CLI boundary before DB calls
- Use parameterized queries (SQLAlchemy does this automatically)
- Sanitize error messages — don't expose DB credentials in logs

**Remember**: async + SQLAlchemy 2.0 is the project standard. Never use sync sessions or raw psycopg2 in application code.
