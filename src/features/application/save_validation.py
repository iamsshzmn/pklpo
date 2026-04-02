"""Pre-save validation for features persistence orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd


class DefaultFeatureSaveValidator:
    """Lightweight validation for feature frames before persistence."""

    _CRITICAL_FEATURES = ("hlc3", "ema_8", "sma_20")
    _BASE_COLUMNS = {"open", "high", "low", "close", "volume", "ts"}

    def validate_save_dataframe(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        if len(df) == 0:
            errors.append("DataFrame is empty")

        required_cols = ["ts"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")

        if "ts" in df.columns and df["ts"].isna().any():
            warnings.append("Timestamp column contains NaN values")

        feature_cols = [col for col in df.columns if col not in self._BASE_COLUMNS]
        if not feature_cols:
            warnings.append("No feature columns found")

        missing_critical = [
            feature
            for feature in self._CRITICAL_FEATURES
            if feature not in feature_cols
        ]
        if missing_critical:
            warnings.append(f"Missing critical features: {missing_critical}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "feature_count": len(feature_cols),
            "row_count": len(df),
            "symbol": symbol,
            "timeframe": timeframe,
        }


def create_feature_save_validator() -> DefaultFeatureSaveValidator:
    """Factory to keep application save orchestration injectable."""
    return DefaultFeatureSaveValidator()
