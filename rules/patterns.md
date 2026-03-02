# Common Patterns

## Repository Pattern (SQLAlchemy async)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Instrument

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
```

## Service Layer Pattern

```python
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
        result = compute_features(df, specs=["rsi_14", "ema_21"])
        return await self._indicators.upsert(result, symbol, timeframe)
```

## UPSERT Pattern (Composite Key)

```python
from sqlalchemy import text

async def upsert_indicators(session: AsyncSession, records: list[dict]) -> None:
    await session.execute(
        text("""
            INSERT INTO indicators_p (symbol, timeframe, timestamp, rsi_14)
            VALUES (:symbol, :timeframe, :timestamp, :rsi_14)
            ON CONFLICT (symbol, timeframe, timestamp) DO UPDATE SET
                rsi_14 = EXCLUDED.rsi_14
        """),
        records,
    )
```

## Async Context Manager

```python
from contextlib import asynccontextmanager

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

## DTO / Dataclass Models

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class OHLCVRow:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
```

## Group-Based Calculation Pipeline

```python
INDICATOR_GROUPS = [
    ("candles",     candles.SPECS),
    ("ma",          ma.SPECS),
    ("oscillators", oscillators.SPECS),
    ("volatility",  volatility.SPECS),
    ("trend",       trend.SPECS),
]

def compute_all_groups(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for _name, specs in INDICATOR_GROUPS:
        result = compute_features(result, specs=specs)
    return result
```

## Skeleton Projects

When implementing new functionality:
1. Search for battle-tested patterns in `src/features/` and `src/candles/`
2. Follow existing Clean Architecture layers:
   - `domain/` — models, protocols
   - `application/` — business logic
   - `infrastructure/` — DB, external APIs
3. Wire via `container.py` dependency injection
4. Add tests in `tests/` or `src/features/tests/`
