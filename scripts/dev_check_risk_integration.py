import asyncio
import os
from decimal import Decimal

try:
    from dotenv import load_dotenv

    load_dotenv(".env")
except Exception:
    pass

from src.risk.database.client import RiskDatabaseClient
from src.risk.guards.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    GuardType,
)
from src.risk.sizing.calculator import PositionSizeCalculator
from src.risk.sizing.models import PositionSizeRequest, SizingContext, SizingStrategy


async def main() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        host = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST") or "localhost"
        port = os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT") or "5432"
        user = os.getenv("POSTGRES_USER") or os.getenv("DB_USER") or "postgres"
        password = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD") or ""
        db = os.getenv("POSTGRES_DB") or os.getenv("DB_NAME") or "postgres"
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"

    client = RiskDatabaseClient(db_url)
    await client.initialize()

    # CircuitBreaker with low thresholds to trigger OPEN fast
    cb_cfg = CircuitBreakerConfig(
        guard_type=GuardType.CIRCUIT_BREAKER,
        name="test-cb",
        failure_threshold=1,
        recovery_threshold=1,
        timeout_sec=1,
        half_open_max_calls=1,
    )
    cb = CircuitBreaker(config=cb_cfg, db_client=client)

    def failing():
        raise RuntimeError("boom")

    try:
        cb.call(failing)
    except Exception:
        pass

    opened_raised = False
    try:
        cb.call(lambda: None)
    except Exception:
        opened_raised = True

    calc = PositionSizeCalculator(db_client=client)
    req = PositionSizeRequest(
        symbol="BTCUSDT",
        entry_price=Decimal("30000"),
        stop_price=Decimal("29500"),
        balance=Decimal("10000"),
        risk_per_trade=Decimal("0.01"),
        lot_size=Decimal("0.001"),
    )
    ctx = SizingContext(symbol="BTCUSDT")
    strat = SizingStrategy(
        name="test",
        risk_method="percentage",
        position_sizing_method="equal_weight",
        rebalancing_frequency="daily",
        parameters={"fixed_risk": Decimal("0.01")},
    )
    _ = calc.calculate_position_size(req, ctx, strat)

    await asyncio.sleep(0.3)
    await client.close()
    print("cb_opened_exception:", opened_raised)


if __name__ == "__main__":
    asyncio.run(main())
