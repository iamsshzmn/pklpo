"""
Group Calculation Orchestrator (SRP: coordination only).

This module coordinates the calculation, persistence, and metrics
recording for indicator groups. It follows the Single Responsibility
Principle by focusing solely on orchestration logic.

Part of Phase 1.2 refactoring: Split GroupCalculator into SRP components.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.logging import (
    LogAggregator,
    LogCategory,
    Verbosity,
    get_category_logger,
    should_log,
)

from ..domain.models import FeatureError
from ..validation.code_validator import CodeValidator, ValidationConfig
from .group_calculator import GroupFeatureCalculator
from .group_metrics import GroupMetricsRecorder
from .group_persister import GroupPersister
from .pipeline import (
    PipelineContext,
    run_post_calculation,
    run_pre_calculation,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    import pandas as pd

    from src.config.settings import FeaturesSettings

__all__ = [
    "GroupCalculationConfig",
    "GroupCalculationOrchestrator",
    "compute_features_grouped",
]


def _default_group_order() -> list[str]:
    """Derive default group order from the registry snapshot."""
    from ..indicator_groups.registry import build_registry_snapshot

    return [entry.name for entry in build_registry_snapshot().get_ordered()]


@dataclass
class GroupCalculationConfig:
    """
    Configuration for group-based calculation.

    This class holds all configuration options for the orchestrator.
    It can be loaded from settings via the from_settings() factory method.

    OCP Compliance: Configuration can be changed without modifying code
    by updating the centralized FeaturesSettings.
    """

    # Deprecated compatibility field: runtime execution order is resolved from
    # registry metadata, not from a hardcoded config list.
    calculation_order: list[str] = field(default_factory=_default_group_order)

    # Batch persistence settings
    batch_size: int = 5000
    max_retries: int = 3
    retry_delay_base: float = 1.0

    # Quality gates
    min_rows: int = 20
    min_fill_rate: float = 0.5
    max_nan_ratio: float = 0.1

    # Feature validation periods (for warm-up validation)
    feature_periods: dict[str, int] = field(
        default_factory=lambda: {
            "sma_20": 20,
            "sma_50": 50,
            "sma_200": 200,
            "ema_8": 8,
            "ema_21": 21,
            "ema_50": 50,
            "atr_14": 14,
            "atr_21": 21,
        }
    )

    @classmethod
    def from_settings(
        cls, settings: FeaturesSettings | None = None
    ) -> GroupCalculationConfig:
        """
        Create configuration from FeaturesSettings.

        If settings is None, attempts to load from centralized config.

        Args:
            settings: Features settings (optional, loads from get_settings() if None)

        Returns:
            Configured GroupCalculationConfig instance
        """
        if settings is None:
            try:
                from src.config import get_settings

                settings = get_settings().features
            except ImportError:
                import logging

                logging.getLogger(__name__).warning(
                    "src.config not available, using default GroupCalculationConfig"
                )
                return cls()

        # Get default values for fallback
        defaults = cls()

        return cls(
            calculation_order=defaults.calculation_order,
            batch_size=getattr(settings, "batch_size", defaults.batch_size),
            max_retries=getattr(settings, "max_retries", defaults.max_retries),
            min_rows=getattr(settings, "min_rows", defaults.min_rows),
            min_fill_rate=getattr(settings, "min_fill_rate", defaults.min_fill_rate),
            feature_periods=getattr(settings, "feature_periods", None)
            or defaults.feature_periods,
        )


class GroupCalculationOrchestrator:
    """
    Orchestrator for group-based feature calculation.

    This class coordinates:
    - GroupFeatureCalculator for calculation
    - GroupPersister for persistence
    - GroupMetricsRecorder for metrics
    - CodeValidator for additional validations

    It follows the Single Responsibility Principle by focusing
    solely on orchestration, delegating actual work to components.
    """

    def __init__(
        self,
        config: GroupCalculationConfig | None = None,
        calculator: GroupFeatureCalculator | None = None,
        persister: GroupPersister | None = None,
        metrics_recorder: GroupMetricsRecorder | None = None,
        code_validator: CodeValidator | None = None,
        calc_timer: Callable | None = None,
    ):
        """
        Initialize the orchestrator with optional component injection.

        Args:
            config: Configuration for calculation
            calculator: Feature calculator (created if None)
            persister: Data persister (created if None)
            metrics_recorder: Metrics recorder (created if None)
            code_validator: Code validator (created if None)
            calc_timer: Context manager factory for timing calculations.
                Injected from application layer to avoid core→observability coupling.
        """
        self.config = config or GroupCalculationConfig()
        self._logger = get_category_logger(LogCategory.CALC)
        self._calc_timer = calc_timer or contextlib.nullcontext

        # Dependency injection for components (DIP compliance)
        self._calculator = calculator or GroupFeatureCalculator()
        self._persister = persister or GroupPersister()
        self._metrics = metrics_recorder or GroupMetricsRecorder()
        self._validator = code_validator or CodeValidator(ValidationConfig())

    def calculate_all_groups(
        self,
        df_ohlcv: pd.DataFrame,
        persist: bool = True,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Calculate all groups with optional persistence.

        Args:
            df_ohlcv: DataFrame with OHLCV data
            persist: Whether to persist results to database
            **kwargs: Additional parameters (symbol, timeframe, etc.)

        Returns:
            DataFrame with all calculated features
        """
        ordered_groups = self._calculator.get_ordered_groups()
        symbol = str(kwargs.get("symbol", "unknown"))
        timeframe = str(kwargs.get("timeframe", "unknown"))

        ctx = PipelineContext(
            symbol=symbol,
            timeframe=timeframe,
            feature_count=len(ordered_groups),
        )

        with (
            LogAggregator(LogCategory.CALC, "group_calculation") as agg,
            self._calc_timer(symbol, timeframe),
        ):
            try:
                result_df = run_pre_calculation(df_ohlcv, ctx, validate_specs=False)
                run_kwargs = dict(kwargs)
                available = set(run_kwargs.pop("available", set()))

                result_df = self._run_groups(
                    result_df,
                    ordered_groups,
                    available,
                    persist,
                    ctx,
                    agg,
                    **run_kwargs,
                )
                return self._finalize(result_df, ctx, agg)

            except Exception as e:
                self._logger.error(f"Group-based calculation failed: {e}")
                raise FeatureError(f"Group-based calculation failed: {e}") from e

    def _run_groups(
        self,
        result_df: pd.DataFrame,
        ordered_groups: list,
        available: set,
        persist: bool,
        ctx: PipelineContext,
        agg: LogAggregator,
        **kwargs,
    ) -> pd.DataFrame:
        """Calculate each group, persist, and record metrics."""
        for group_entry in ordered_groups:
            group_name = group_entry.name
            try:
                group_result = self._calculator.calculate_group(
                    result_df, group_name, available, **kwargs
                )
                for indicator_name, series in group_result.items():
                    result_df[indicator_name] = series

                if persist:
                    success = self._persister.persist_batch(
                        result_df, group_name, **kwargs
                    )
                    if not success:
                        agg.add_warning(f"Failed to persist {group_name}")

                fill_rate = self._metrics.record_group_metrics(
                    result_df, group_name, group_result
                )
                agg.add("groups", group_name, value=fill_rate)

            except Exception as e:
                agg.add_error(f"Failed to process {group_name}: {e}")
                ctx.failed_groups.append(group_name)
                ctx.data_status = "inc"

        return result_df

    def _finalize(
        self,
        result_df: pd.DataFrame,
        ctx: PipelineContext,
        agg: LogAggregator,
    ) -> pd.DataFrame:
        """Run validations, post-processing, and set summary info."""
        self._run_code_validations(result_df, ctx)
        result_df = run_post_calculation(result_df, ctx)

        agg.set_extra("bars", len(result_df))
        agg.set_extra("status", ctx.data_status)
        if ctx.failed_groups:
            agg.set_extra("failed", len(ctx.failed_groups))

        return result_df

    def _run_code_validations(
        self,
        result_df: pd.DataFrame,
        ctx: PipelineContext,
    ) -> None:
        """
        Run additional code validations (non-blocking).

        Args:
            result_df: DataFrame with calculated features
            ctx: Pipeline context
        """
        code_valid, code_result = self._validator.validate_all(
            result_df, self.config.feature_periods
        )

        if not code_valid and should_log(LogCategory.DIAG, Verbosity.VERBOSE):
            self._logger.warning(f"Code validations failed: {code_result['errors']}")

        if code_result.get("warnings") and should_log(
            LogCategory.DIAG, Verbosity.VERBOSE
        ):
            self._logger.warning(f"Code validation warnings: {code_result['warnings']}")


def compute_features_grouped(
    df_ohlcv: pd.DataFrame,
    config: GroupCalculationConfig | None = None,
    **kwargs,
) -> pd.DataFrame:
    """
    Calculate features using group-based architecture.

    This is the main entry point for group-based calculation.
    It follows the plan requirements:
    - Calculate by groups in sequence
    - Persist each group immediately
    - Better error isolation and debugging

    Args:
        df_ohlcv: DataFrame with OHLCV data
        config: Configuration for group calculation
        **kwargs: Additional parameters

    Returns:
        DataFrame with all calculated features
    """
    # Wire observability from application layer (DIP)
    try:
        from ..observability.metrics import record_fill_rate
        from ..observability.prometheus import get_metrics as get_prom_metrics

        calc_timer = get_prom_metrics().calc_timer
        fill_rate_recorder = record_fill_rate
    except ImportError:
        calc_timer = None
        fill_rate_recorder = None

    metrics_recorder = GroupMetricsRecorder(fill_rate_recorder=fill_rate_recorder)
    orchestrator = GroupCalculationOrchestrator(
        config,
        metrics_recorder=metrics_recorder,
        calc_timer=calc_timer,
    )
    return orchestrator.calculate_all_groups(df_ohlcv, **kwargs)
