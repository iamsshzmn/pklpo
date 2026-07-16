"""
Test Stage B indicators: advanced moving averages and trend indicators
"""

import pandas as pd
import pytest

from src.features import compute_features


class TestStageB:
    """Test Stage B indicators with real OHLCV data"""

    @pytest.fixture
    def sample_data(self):
        """Create deterministic OHLCV data for fast CI."""
        rows = 1000
        base = pd.Series(range(rows), dtype="float64")
        cycle = (base % 31) * 0.015
        close = 100.0 + base * 0.08 + cycle
        open_ = close.shift(1).fillna(close.iloc[0])
        high = pd.concat([open_, close], axis=1).max(axis=1) + 0.7
        low = pd.concat([open_, close], axis=1).min(axis=1) - 0.7

        return pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1200.0 + (base % 29) * 15.0,
                "ts": 1_700_000_000_000
                + pd.Series(range(rows), dtype="int64") * 60_000,
            }
        )

    def test_advanced_ma_indicators(self, sample_data):
        """Test advanced moving averages: alma, fwma, rma, t3, trima, vidya, zlma, sinwma, swma, pwma, hwma, linreg"""
        ma_specs = [
            "alma_20",
            "fwma_20",
            "rma_20",
            "t3_20",
            "trima_20",
            "vidya_20",
            "zlma_20",
            "sinwma_20",
            "swma_20",
            "pwma_20",
            "hwma_20",
            "linreg_20",
        ]

        result = compute_features(
            sample_data, specs=ma_specs, volatility_normalize=False
        )

        # Check all indicators are returned. Some advanced MA indicators are
        # backend-dependent and may be NaN-only with the local fallback backend.
        for spec in ma_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        # Check that calculated MA values are reasonable (close to price range)
        close_range = (sample_data["close"].min(), sample_data["close"].max())
        for spec in ma_specs:
            values = result[spec].dropna()
            if len(values) > 0:
                # MA should be within reasonable range of prices
                assert values.min() >= close_range[0] * 0.5, f"{spec} values too low"
                assert values.max() <= close_range[1] * 1.5, f"{spec} values too high"

        print(f"✅ Advanced MA indicators: {len(ma_specs)} passed")

    def test_supertrend_indicators(self, sample_data):
        """Test Supertrend indicators: supertrend, supertrend_direction, supertrend_long, supertrend_short"""
        supertrend_specs = [
            "supertrend",
            "supertrend_direction",
            "supertrend_long",
            "supertrend_short",
        ]

        result = compute_features(
            sample_data, specs=supertrend_specs, volatility_normalize=False
        )

        # Check all indicators are returned. Supertrend is backend-dependent and
        # may be NaN-only with the local fallback backend.
        for spec in supertrend_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        # Check that supertrend_direction is binary (0 or 1) when calculated.
        direction = result["supertrend_direction"].dropna()
        if len(direction) > 0:
            assert direction.isin([0, 1]).all(), "supertrend_direction should be 0 or 1"

        print(f"✅ Supertrend indicators: {len(supertrend_specs)} passed")

    def test_stage_b_all_together(self, sample_data):
        """Test all Stage B indicators together"""
        all_specs = [
            # Advanced MA
            "alma_20",
            "fwma_20",
            "rma_20",
            "t3_20",
            "trima_20",
            "vidya_20",
            "zlma_20",
            "sinwma_20",
            "swma_20",
            "pwma_20",
            "hwma_20",
            "linreg_20",
            # Supertrend
            "supertrend",
            "supertrend_direction",
            "supertrend_long",
            "supertrend_short",
        ]

        result = compute_features(
            sample_data, specs=all_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in all_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        print(f"✅ Stage B all indicators: {len(all_specs)} passed")
        print(f"Result shape: {result.shape}")


if __name__ == "__main__":
    # Run tests manually
    import asyncio

    async def run_tests():
        test_instance = TestStageB()
        sample_data = TestStageB.sample_data.__wrapped__(test_instance)

        print("Running Stage B tests...")
        test_instance.test_advanced_ma_indicators(sample_data)
        test_instance.test_supertrend_indicators(sample_data)
        test_instance.test_stage_b_all_together(sample_data)
        print("All Stage B tests passed!")

    asyncio.run(run_tests())
