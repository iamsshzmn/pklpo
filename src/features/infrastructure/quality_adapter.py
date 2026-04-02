from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

from src.candles.application.quality_pipeline import run_quality_pipeline
from src.candles.infrastructure.sqlalchemy_pool_adapter import SQLAlchemyPoolAdapter


class SQLAlchemyQualityPipelineRunner:
    """Bridge the features validation flow to the candles quality pipeline."""

    async def __call__(
        self,
        engine: AsyncEngine,
        *,
        send_alerts: bool = True,
        alert_cooldown_minutes: int = 30,
    ) -> tuple[Any, dict[str, int]]:
        pool_adapter = SQLAlchemyPoolAdapter(engine)
        return await run_quality_pipeline(
            pool_adapter,
            send_alerts=send_alerts,
            alert_cooldown_minutes=alert_cooldown_minutes,
        )


def create_quality_pipeline_runner() -> SQLAlchemyQualityPipelineRunner:
    return SQLAlchemyQualityPipelineRunner()
