"""Infrastructure wiring for market selection pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..application.pipeline import MarketSelectionPipeline
from ..config import MarketSelectionConfig
from .database import MarketSelectionDB
from .monitoring import MarketSelectionMonitoring
from .persistence import MarketSelectionPersistence

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def build_market_selection_pipeline(
    session: AsyncSession,
    config: MarketSelectionConfig,
) -> MarketSelectionPipeline:
    """Compose a pipeline with infrastructure implementations."""
    return MarketSelectionPipeline(
        session=session,
        config=config,
        db=MarketSelectionDB(session, config),
        persistence=MarketSelectionPersistence(session),
        monitoring=MarketSelectionMonitoring(),
    )
