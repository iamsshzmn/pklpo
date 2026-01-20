"""
Calculation module for features - separates calculation from saving.

This module implements the strategy of calculating indicators and saving to parquet files
to avoid XCom limitations and improve reliability.
"""

import gc
from collections.abc import Generator, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .config import StreamingConfig, create_streaming_config
from .core import compute_features
from .logging_config import get_features_logger
from .strategy import get_max_lookback_for_strategies
from .utils.memlog import force_cleanup, memory_monitor

logger = get_features_logger("features.calc")


def process_chunks(
    reader: Iterator[pd.DataFrame],
    symbol: str,
    timeframe: str,
    available_indicators: set | None = None,
    config: StreamingConfig | None = None,
    **kwargs,
) -> Generator[pd.DataFrame, None, None]:
    """
    Process data in chunks with overlap for streaming calculation.

    Args:
        reader: Iterator yielding DataFrames
        symbol: Trading symbol
        timeframe: Timeframe
        available_indicators: Set of indicators to calculate
        config: Streaming configuration
        **kwargs: Additional parameters

    Yields:
        DataFrame with calculated features for each chunk
    """
    if config is None:
        config = create_streaming_config()

    # Determine max lookback
    if available_indicators:
        max_lookback = get_max_lookback_for_strategies(list(available_indicators))
    else:
        max_lookback = config.MAX_LOOKBACK

    overlap_size = max(max_lookback, config.OVERLAP_SIZE)

    logger.info(
        f"Processing chunks with overlap={overlap_size}, max_lookback={max_lookback}"
    )

    # Keep track of overlap data
    overlap_data = None
    chunk_count = 0

    with memory_monitor("process_chunks") as mem_log:
        for chunk_df in reader:
            chunk_count += 1

            if config.LOG_MEMORY_USAGE:
                mem_log.log_dataframe_memory(chunk_df, f"Chunk {chunk_count}")

            # Add overlap from previous chunk
            if overlap_data is not None:
                # Combine overlap with new chunk
                # Валидация: проверяем что overlap_data и chunk_df не пустые
                if (
                    overlap_data is not None
                    and not overlap_data.empty
                    and not chunk_df.empty
                ):
                    combined_df = pd.concat([overlap_data, chunk_df], ignore_index=True)
                elif overlap_data is not None and not overlap_data.empty:
                    combined_df = overlap_data
                else:
                    combined_df = chunk_df
                logger.debug(
                    f"Combined chunk {chunk_count}: {len(overlap_data)} overlap + {len(chunk_df)} new = {len(combined_df)} total"
                )
            else:
                combined_df = chunk_df
                logger.debug(f"First chunk {chunk_count}: {len(combined_df)} rows")

            # Calculate features on combined data
            try:
                with memory_monitor(f"calculate_chunk_{chunk_count}") as chunk_mem:
                    features_df = compute_features(
                        combined_df,
                        available=available_indicators,
                        volatility_normalize=config.ENABLE_VOLATILITY_NORMALIZE,
                        **kwargs,
                    )

                    if config.LOG_MEMORY_USAGE:
                        chunk_mem.log_dataframe_memory(
                            features_df, f"Features chunk {chunk_count}"
                        )

                    # Remove overlap from the beginning (except for first chunk)
                    if overlap_data is not None:
                        # Keep only the new data (after overlap)
                        clean_features_df = features_df.iloc[overlap_size:].copy()
                        logger.debug(
                            f"Removed overlap: {len(features_df)} -> {len(clean_features_df)} rows"
                        )
                    else:
                        clean_features_df = features_df
                        logger.debug(
                            f"First chunk, no overlap removal: {len(clean_features_df)} rows"
                        )

                    # Store overlap for next chunk
                    if len(features_df) > overlap_size:
                        overlap_data = features_df.iloc[-overlap_size:].copy()
                        logger.debug(f"Stored overlap: {len(overlap_data)} rows")
                    else:
                        overlap_data = features_df.copy()
                        logger.debug(
                            f"Stored full chunk as overlap: {len(overlap_data)} rows"
                        )

                    # Clean up intermediate objects
                    if config.CLEAR_INTERMEDIATE_OBJECTS:
                        force_cleanup(combined_df, features_df)

                    if config.FORCE_GC_AFTER_CHUNK:
                        gc.collect()

                    yield clean_features_df

            except Exception as e:
                logger.error(f"Error processing chunk {chunk_count}: {e}")
                raise

            # Clean up chunk data
            if config.CLEAR_INTERMEDIATE_OBJECTS:
                force_cleanup(chunk_df)

        logger.info(f"Processed {chunk_count} chunks with streaming calculation")


def compute_and_dump_parquet(
    df_ohlcv: pd.DataFrame,
    symbol: str,
    timeframe: str,
    output_path: str,
    available_indicators: set | None = None,
    volatility_normalize: bool = False,
    **kwargs,
) -> dict[str, Any]:
    """
    Calculate indicators and save to parquet file.

    Args:
        df_ohlcv: OHLCV DataFrame
        symbol: Trading symbol
        timeframe: Timeframe
        output_path: Path to save parquet file
        available_indicators: Set of indicators to calculate
        volatility_normalize: Whether to apply volatility normalization
        **kwargs: Additional parameters

    Returns:
        Dictionary with calculation results and metadata
    """
    logger.info(f"Starting calculation for {symbol} {timeframe}")

    try:
        # Validate input data
        if df_ohlcv is None or len(df_ohlcv) < 20:
            raise ValueError(
                f"Insufficient data for {symbol} {timeframe}: {len(df_ohlcv) if df_ohlcv is not None else 0} rows"
            )

        # Check for required columns
        required_cols = ["open", "high", "low", "close", "volume"]
        missing_cols = [col for col in required_cols if col not in df_ohlcv.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Calculate indicators
        logger.info(f"Calculating indicators for {symbol} {timeframe}")
        result_df = compute_features(
            df_ohlcv,
            available=available_indicators,
            volatility_normalize=volatility_normalize,
            **kwargs,
        )

        # Validate calculation results
        if result_df is None or len(result_df) == 0:
            raise ValueError("Calculation resulted in empty DataFrame")

        # Check for critical features
        critical_features = ["hlc3", "ema_8", "sma_20"]
        missing_critical = [f for f in critical_features if f not in result_df.columns]
        if missing_critical:
            logger.warning(f"Missing critical features: {missing_critical}")

        # Add metadata
        result_df.attrs.update(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "calculated_at": datetime.utcnow().isoformat(),
                "source_rows": len(df_ohlcv),
                "result_rows": len(result_df),
            }
        )

        # Ensure output directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to parquet
        logger.info(f"Saving results to {output_path}")
        result_df.to_parquet(output_path, index=False, compression="snappy")

        # Calculate statistics
        feature_cols = [
            col
            for col in result_df.columns
            if col not in ["open", "high", "low", "close", "volume", "ts"]
        ]

        stats = {
            "symbol": symbol,
            "timeframe": timeframe,
            "source_rows": len(df_ohlcv),
            "result_rows": len(result_df),
            "feature_count": len(feature_cols),
            "output_path": str(output_path),
            "file_size_mb": output_path.stat().st_size / (1024 * 1024),
            "calculated_at": datetime.utcnow().isoformat(),
        }

        # Calculate fill rates for key features
        key_features = ["hlc3", "ema_8", "sma_20", "rsi_14", "atr_14", "macd", "obv"]
        available_key_features = [f for f in key_features if f in result_df.columns]

        fill_rates = {}
        for feature in available_key_features:
            non_null_count = result_df[feature].notna().sum()
            fill_rate = (
                (non_null_count / len(result_df) * 100) if len(result_df) > 0 else 0
            )
            fill_rates[feature] = fill_rate

        stats["fill_rates"] = fill_rates

        logger.info(
            f"Successfully calculated and saved {symbol} {timeframe}",
            result_rows=stats["result_rows"],
            feature_count=stats["feature_count"],
            file_size_mb=stats["file_size_mb"],
        )

        return stats

    except Exception as e:
        logger.error(f"Calculation failed for {symbol} {timeframe}: {e}")
        raise


def validate_parquet_file(file_path: str) -> dict[str, Any]:
    """
    Validate a parquet file with calculated indicators.

    Args:
        file_path: Path to parquet file

    Returns:
        Validation results
    """
    try:
        df = pd.read_parquet(file_path)

        validation = {
            "file_exists": True,
            "rows": len(df),
            "columns": list(df.columns),
            "has_metadata": hasattr(df, "attrs") and len(df.attrs) > 0,
            "metadata": df.attrs if hasattr(df, "attrs") else {},
            "file_size_mb": Path(file_path).stat().st_size / (1024 * 1024),
        }

        # Check for required columns
        required_cols = ["ts"]
        missing_required = [col for col in required_cols if col not in df.columns]
        validation["missing_required_columns"] = missing_required

        # Check for feature columns
        feature_cols = [
            col
            for col in df.columns
            if col not in ["open", "high", "low", "close", "volume", "ts"]
        ]
        validation["feature_columns"] = feature_cols
        validation["feature_count"] = len(feature_cols)

        # Check data quality
        if len(df) > 0:
            validation["has_data"] = True
            validation["null_rates"] = {}
            for col in feature_cols[:10]:  # Check first 10 features
                null_count = df[col].isna().sum()
                null_rate = (null_count / len(df) * 100) if len(df) > 0 else 100
                validation["null_rates"][col] = null_rate
        else:
            validation["has_data"] = False

        return validation

    except Exception as e:
        return {"file_exists": False, "error": str(e), "validation_failed": True}


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.append(str(Path(__file__).parent.parent.parent))

    parser = argparse.ArgumentParser(
        description="Calculate indicators and save to parquet"
    )
    parser.add_argument("input_csv", help="Input CSV file with OHLCV data")
    parser.add_argument("output_parquet", help="Output parquet file path")
    parser.add_argument("--symbol", required=True, help="Trading symbol")
    parser.add_argument("--timeframe", required=True, help="Timeframe")
    parser.add_argument(
        "--volatility-normalize",
        action="store_true",
        help="Apply volatility normalization",
    )

    args = parser.parse_args()

    try:
        # Load OHLCV data
        df_ohlcv = pd.read_csv(args.input_csv)

        # Calculate and save
        result = compute_and_dump_parquet(
            df_ohlcv=df_ohlcv,
            symbol=args.symbol,
            timeframe=args.timeframe,
            output_path=args.output_parquet,
            volatility_normalize=args.volatility_normalize,
        )

        print(
            f"✅ Successfully calculated indicators for {args.symbol} {args.timeframe}"
        )
        print(
            f"📊 Result: {result['result_rows']} rows, {result['feature_count']} features"
        )
        print(f"💾 Saved to: {result['output_path']}")
        print(f"📁 File size: {result['file_size_mb']:.2f} MB")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
