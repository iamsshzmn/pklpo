"""Composition helpers for features save orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..infrastructure.persistence import create_indicator_repository
from .save_observer import create_feature_save_observer
from .save_validation import create_feature_save_validator

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ..domain.protocols import (
        FeatureSaveObserver,
        FeatureSaveValidator,
        IndicatorRepository,
    )


@dataclass(frozen=True)
class FeatureSaveDependencies:
    """Explicit save dependencies assembled at the composition root."""

    repository: IndicatorRepository
    validator: FeatureSaveValidator
    observer: FeatureSaveObserver


def create_feature_save_dependencies(
    session: AsyncSession,
) -> FeatureSaveDependencies:
    """Create the default dependency bundle for save use cases."""
    return FeatureSaveDependencies(
        repository=create_indicator_repository(session),
        validator=create_feature_save_validator(),
        observer=create_feature_save_observer(),
    )
