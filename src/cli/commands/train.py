"""
CLI command train: train MetaLabeler (metalabeling pipeline, AFML Ch.10).

Usage:
    python -m src.cli.main train --symbols BTC-USDT-SWAP --model rf --cv purged-kfold --feature-selection mda
    python -m src.cli.main train --symbols BTC-USDT-SWAP \\
        --feature-selection mutual_info --n-features 30 --no-calibrate
    python -m src.cli.main train --symbols BTC-USDT-SWAP --dry-run

Features are built from the OHLCV price series (log-returns, rolling vol/SMA/vol ratios).
To use pre-computed features from the features pipeline, set --features-source db
(support will be added in a future version).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.core.run_context import RunContext
from src.ml.labeling.sample_weights import get_uniqueness_weights
from src.ml.labeling.triple_barrier import triple_barrier_labels
from src.ml.metalabeling.pipeline import MetaLabeler
from src.ml.models import BarrierConfig

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def register(subparsers) -> None:  # type: ignore[no-untyped-def]
    """Register the train command in the CLI."""
    p = subparsers.add_parser(
        "train",
        help="Train MetaLabeler (metalabeling pipeline, AFML Ch.10)",
    )
    p.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Symbols to train on (e.g.: BTC-USDT-SWAP ETH-USDT-SWAP)",
    )
    p.add_argument(
        "--timeframe",
        default="1m",
        help="Source data timeframe (default: 1m)",
    )
    p.add_argument(
        "--model",
        choices=["rf", "xgboost"],
        default="rf",
        help="Backend classifier: rf (RandomForest) or xgboost (default: rf)",
    )
    p.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Number of trees/iterations in the model (default: 100)",
    )
    p.add_argument(
        "--cv",
        choices=["purged-kfold"],
        default="purged-kfold",
        help="Cross-validation strategy (default: purged-kfold)",
    )
    p.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of folds for PurgedKFold (default: 5)",
    )
    p.add_argument(
        "--feature-selection",
        choices=["mda", "mutual_info", "pca_variance"],
        default="mda",
        help="Feature selection method (default: mda)",
    )
    p.add_argument(
        "--n-features",
        type=int,
        default=50,
        help="Maximum number of features to select (default: 50)",
    )
    p.add_argument(
        "--pt",
        dest="profit_take",
        type=float,
        default=0.02,
        help="Profit take threshold as fraction of price (default: 0.02 = 2%%)",
    )
    p.add_argument(
        "--sl",
        dest="stop_loss",
        type=float,
        default=0.01,
        help="Stop loss threshold as fraction of price (default: 0.01 = 1%%)",
    )
    p.add_argument(
        "--max-h",
        dest="max_horizon",
        type=int,
        default=48,
        help="Maximum horizon in bars until vertical barrier (default: 48)",
    )
    p.add_argument(
        "--decay",
        type=float,
        default=1.0,
        help="Time-decay factor for sample weights (default: 1.0 = no decay)",
    )
    p.add_argument(
        "--no-calibrate",
        action="store_true",
        help="Disable probability calibration (enabled by default)",
    )
    p.add_argument(
        "--output-dir",
        default="./artifacts",
        help="Directory for saving artifacts (default: ./artifacts)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Row limit from DB (default: all data)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show parameters without running training",
    )
    p.set_defaults(_handler=handle)


async def handle(args) -> None:  # type: ignore[no-untyped-def]
    """Handler for the train command."""
    if args.dry_run:
        _show_plan(args)
        return

    ctx = RunContext.create(
        params={
            "model": args.model,
            "n_estimators": args.n_estimators,
            "cv": args.cv,
            "n_splits": args.n_splits,
            "feature_selection": args.feature_selection,
            "n_features": args.n_features,
            "profit_take": args.profit_take,
            "stop_loss": args.stop_loss,
            "max_horizon": args.max_horizon,
            "decay": args.decay,
            "calibrate": not args.no_calibrate,
            "timeframe": args.timeframe,
        }
    )
    logger.info("RunContext: run_id=%s", ctx.run_id)

    barrier_config = BarrierConfig(
        profit_take=args.profit_take,
        stop_loss=args.stop_loss,
        max_horizon=args.max_horizon,
    )

    output_dir = Path(args.output_dir) / ctx.run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    for symbol in args.symbols:
        df = await _load_ohlcv(symbol, args.timeframe, args.limit)
        if df is None or len(df) == 0:
            logger.warning("No data for %s %s", symbol, args.timeframe)
            continue

        logger.info("%s: loaded %d bars", symbol, len(df))

        X = _build_price_features(df)
        labels_df = triple_barrier_labels(df, barrier_config)

        # Align on common indices
        common_idx = X.index.intersection(labels_df.index)
        X = X.loc[common_idx]
        y = labels_df.loc[common_idx, "label"].astype(int)
        t1 = labels_df.loc[common_idx, "t1"]

        weights = get_uniqueness_weights(
            t1=t1,
            close=df["close"],
            decay_factor=args.decay,
        )
        weights = weights.reindex(common_idx).fillna(1.0)

        logger.info(
            "%s: %d samples | features=%d | label_dist=%s",
            symbol,
            len(X),
            X.shape[1],
            dict(y.value_counts().sort_index()),
        )

        feature_selector = _make_feature_selector(
            method=args.feature_selection,
            n_features=args.n_features,
            n_splits=args.n_splits,
            t1=t1,
        )
        base_model = _make_base_model(args.model, args.n_estimators)

        labeler = MetaLabeler(
            base_model=base_model,
            calibrate=not args.no_calibrate,
            feature_selector=feature_selector,
        )
        labeler.fit(X, y, sample_weight=weights)

        safe_symbol = symbol.replace("/", "_").replace("-", "_")
        artifact_path = output_dir / f"metalabeler_{safe_symbol}.joblib"
        labeler.save(artifact_path, ctx)

        n_selected = labeler.n_features_in or 0
        logger.info(
            "%s: model trained | features_selected=%d/%d | artifact=%s",
            symbol,
            n_selected,
            X.shape[1],
            artifact_path,
        )

    logger.info(
        "train completed: %d symbols (run_id=%s) | artifacts -> %s",
        len(args.symbols),
        ctx.run_id[:8],
        output_dir,
    )


async def _load_ohlcv(
    symbol: str, timeframe: str, limit: int | None
) -> pd.DataFrame | None:
    """Load OHLCV data from the database."""
    from src.utils.session_utils import get_db_session

    try:
        async with get_db_session() as session:
            limit_clause = f"LIMIT {limit}" if limit else ""
            query = text(f"""
                SELECT timestamp, open, high, low, close, volume
                FROM swap_ohlcv_p
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY timestamp ASC
                {limit_clause}
            """)
            result = await session.execute(
                query, {"symbol": symbol, "timeframe": timeframe}
            )
            rows = result.fetchall()

        if not rows:
            return None

        df = pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df.index = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.index.name = "timestamp"
        df = df.drop(columns=["timestamp"])
        return df.astype(float)

    except Exception as e:
        logger.error("Error loading data for %s %s: %s", symbol, timeframe, e)
        return None


def _build_price_features(
    df: pd.DataFrame,
    windows: tuple[int, ...] = (5, 10, 20, 50),
) -> pd.DataFrame:
    """
    Basic price features from OHLCV.

    Builds log-returns, rolling volatility, SMA ratios, and volume ratios.
    Used when pre-computed features from the features pipeline are unavailable.
    """
    close = df["close"]
    volume = df["volume"]
    log_ret = np.log(close / close.shift(1))

    features: dict[str, pd.Series] = {
        "log_ret_1": log_ret,
        "hl_ratio": (df["high"] - df["low"]) / close,
        "co_ratio": (close - df["open"]) / df["open"],
    }

    for w in windows:
        features[f"log_ret_{w}"] = log_ret.rolling(w).sum()
        features[f"vol_{w}"] = log_ret.rolling(w).std()
        features[f"sma_ratio_{w}"] = close / close.rolling(w).mean() - 1
        features[f"vol_ratio_{w}"] = volume / volume.rolling(w).mean()

    return pd.DataFrame(features, index=df.index).dropna()


def _make_feature_selector(
    method: str,
    n_features: int,
    n_splits: int,
    t1: pd.Series,
) -> Callable[[pd.DataFrame, pd.Series], list[str]]:
    """Create a feature selection function for MetaLabeler."""
    from src.ml.feature_selection.reduction import select_features
    from src.ml.validation.purged_kfold import PurgedKFold

    cv = PurgedKFold(n_splits=n_splits)

    def selector(X: pd.DataFrame, y: pd.Series) -> list[str]:
        return select_features(
            X,
            y,
            method=method,  # type: ignore[arg-type]
            n_features=n_features,
            cv=cv,
            groups=t1.reindex(X.index),
        )

    return selector


def _make_base_model(model_type: str, n_estimators: int) -> Any:
    """Create a base classifier by type."""
    if model_type == "rf":
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=n_estimators, random_state=0, n_jobs=-1
        )

    if model_type == "xgboost":
        try:
            from xgboost import XGBClassifier

            return XGBClassifier(
                n_estimators=n_estimators,
                random_state=0,
                n_jobs=-1,
                eval_metric="logloss",
            )
        except ImportError:
            logger.warning(
                "xgboost is not installed, falling back to RandomForest. "
                "To install: pip install xgboost"
            )
            from sklearn.ensemble import RandomForestClassifier

            return RandomForestClassifier(
                n_estimators=n_estimators, random_state=0, n_jobs=-1
            )

    raise ValueError(f"Unknown model type: {model_type!r}")


def _show_plan(args) -> None:  # type: ignore[no-untyped-def]
    """Show plan without executing (dry-run)."""
    logger.info("train dry-run:")
    logger.info("  Symbols:           %s", args.symbols)
    logger.info("  Timeframe:         %s", args.timeframe)
    logger.info("  Model:             %s (n_estimators=%d)", args.model, args.n_estimators)
    logger.info("  CV:                %s (n_splits=%d)", args.cv, args.n_splits)
    logger.info(
        "  Feature selection: %s (n_features=%d)",
        args.feature_selection,
        args.n_features,
    )
    logger.info(
        "  Profit take:       %.3f (%.1f%%)", args.profit_take, args.profit_take * 100
    )
    logger.info(
        "  Stop loss:         %.3f (%.1f%%)", args.stop_loss, args.stop_loss * 100
    )
    logger.info("  Max horizon:       %d bars", args.max_horizon)
    logger.info("  Time decay:        %.2f", args.decay)
    logger.info("  Calibrate:         %s", "no" if args.no_calibrate else "yes")
    logger.info("  Output dir:        %s", args.output_dir)
    logger.info("  Row limit:         %s", args.limit or "all data")
