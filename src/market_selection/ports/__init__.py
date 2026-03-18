"""Ports for market selection application services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any, TypeVar

    import pandas as pd

    from src.market_selection.domain.quality_gate import QualityResult
    from src.market_selection.domain.regime import GlobalRegime
    from src.market_selection.domain.scoring import TFScore
    from src.market_selection.domain.universe import UniverseEntry, UniverseVersion

    T = TypeVar("T")


@runtime_checkable
class MarketSelectionDBPort(Protocol):
    """Read-side port for market selection data access."""

    async def resolve_ts_eval(self) -> int | None: ...

    async def validate_short_features(self) -> tuple[bool, list[str]]: ...

    async def fetch_quality_data(self, timeframe: str, ts_eval: int) -> pd.DataFrame: ...

    async def fetch_pair_metrics_data(self, timeframe: str, ts_eval: int) -> pd.DataFrame: ...

    async def fetch_basket_volume_data(
        self,
        timeframe: str,
        ts_eval: int,
        window_days: int = 30,
    ) -> pd.DataFrame: ...

    async def fetch_regime_metrics(
        self,
        timeframe: str,
        ts_eval: int,
        basket_symbols: list[str],
    ) -> pd.DataFrame: ...

    async def fetch_atr_percentile(
        self,
        timeframe: str,
        ts_eval: int,
        percentile: int = 80,
    ) -> float: ...

    async def fetch_previous_universe(self) -> set[str]: ...

    async def fetch_score_history(
        self,
        symbols: list[str],
        days: int = 30,
    ) -> dict[str, list[float]]: ...

    async def get_last_published_version(self) -> int | None: ...

    async def get_last_valid_regime(self) -> dict[str, Any] | None: ...

    async def check_regime_tf_lag(self, timeframe: str, ts_eval: int) -> int: ...


@runtime_checkable
class PersistencePort(Protocol):
    """Write-side port for persisting market selection results."""

    async def upsert_scores_tf(
        self,
        ts_eval: int,
        timeframe: str,
        scores: list[TFScore],
        quality_results: dict[str, QualityResult],
        metrics_raw: dict[str, dict],
        regime: GlobalRegime,
        config_hash: str,
        window_days: int,
    ) -> int: ...

    async def insert_regime_history(
        self,
        ts_eval: int,
        regime: GlobalRegime,
        config_hash: str,
    ) -> None: ...

    async def insert_universe_version(self, version: UniverseVersion) -> None: ...

    async def insert_universe_entries(
        self,
        ts_version: int,
        entries: list[UniverseEntry],
        config_hash: str,
    ) -> int: ...

    async def update_version_status(
        self,
        ts_version: int,
        status: str,
        notes: str | None = None,
    ) -> None: ...

    async def copy_previous_universe_with_metrics(
        self,
        new_ts_version: int,
        source_ts_version: int,
        config_hash: str,
    ) -> dict[str, int]: ...

    async def acquire_write_lock_for_ts_version(
        self,
        ts_version: int,
        lock_timeout_ms: int = 10_000,
    ) -> float: ...


@runtime_checkable
class MonitoringPort(Protocol):
    """Application-facing monitoring port."""

    def record_error(self, error_type: str, message: str) -> None: ...

    def record_pipeline_metrics(
        self,
        *,
        ts_version: int,
        ts_eval: int,
        success: bool,
        status: str,
        universe_size: int,
        execution_time_seconds: float,
        global_regime: str | None = None,
        regime_strength: float = 0.0,
        regime_stale: bool = False,
        eligible_counts: dict[str, int] | None = None,
        total_symbols: int = 0,
        error_message: str | None = None,
        reason_flags: list[str] | None = None,
    ) -> None: ...
