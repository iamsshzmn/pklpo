"""Log categories and verbosity levels.

This module defines the enums used for log filtering and organization.
"""

from __future__ import annotations

from enum import Enum


class LogCategory(Enum):
    """Log categories for filtering and organizing log output.

    Categories allow filtering logs by functional area:

    Features module:
    - GATE: Data freshness validation
    - CALC: Indicator calculation
    - MERGE: Result merging
    - INSERT: Database insert operations
    - SCHEMA: Schema validation
    - DIAG: Diagnostics (DEBUG only in production)
    - BATCH: Batch processing
    - PERF: Performance metrics

    Project-wide categories:
    - MTF: Multi-timeframe analysis
    - MARKET: Market meta/selection
    - RISK: Risk management
    - SIGNAL: Trading signals
    - CANDLE: OHLCV sync operations
    - DB: Database operations (migrations, queries)
    - API: External API calls
    - CLI: CLI commands
    """

    # Features module (existing)
    GATE = "gate"
    CALC = "calc"
    MERGE = "merge"
    INSERT = "insert"
    SCHEMA = "schema"
    DIAG = "diag"
    BATCH = "batch"
    PERF = "perf"

    # Project-wide categories (new)
    MTF = "mtf"
    MARKET = "market"
    RISK = "risk"
    SIGNAL = "signal"
    CANDLE = "candle"
    DB = "db"
    API = "api"
    CLI = "cli"


class Verbosity(Enum):
    """Verbosity levels controlling log output volume.

    Levels:
    - QUIET (0): Errors and warnings only
    - NORMAL (1): Summary messages + warnings (production default)
    - VERBOSE (2): Detailed progress information
    - DEBUG (3): Full diagnostics including per-item logs
    """

    QUIET = 0
    NORMAL = 1
    VERBOSE = 2
    DEBUG = 3
