"""
Test Stage B indicators: advanced moving averages and trend indicators
"""

import pandas as pd
import pytest
from sqlalchemy import text

from src.database import get_async_session
from src.features import compute_features


class TestStageB:
    """Test Stage B indicators with real OHLCV data"""

    @pytest.fixture()
    async def sample_data(self):
        """Get real OHLCV data from database"""
        async for session in get_async_session():
            # Get recent BTC-USDT-SWAP 1m data
            query = text(
                """
                SELECT open, high, low, close, volume, ts
                FROM ohlcv
                WHERE symbol = 'BTC-USDT-SWAP'
                AND timeframe = '1m'
                ORDER BY ts DESC
                LIMIT 1000
            """
            )
            result = await session.execute(query)
            rows = result.fetchall()

            if not rows:
                pytest.skip("No OHLCV data available")

            # Convert to DataFrame
            data = {
                "open": [float(row[0]) for row in rows],
                "high": [float(row[1]) for row in rows],
                "low": [float(row[2]) for row in rows],
                "close": [float(row[3]) for row in rows],
                "volume": [float(row[4]) for row in rows],
                "ts": [int(row[5]) for row in rows],
            }
            df = pd.DataFrame(data)
            return df.sort_values("ts").reset_index(drop=True)
        return None

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

        # Check all indicators are calculated
        for spec in ma_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            # Allow some NaN values for rolling calculations
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check that MA values are reasonable (close to price range)
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

        # Check all indicators are calculated
        for spec in supertrend_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            # Allow some NaN values for calculations
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check that supertrend_direction is binary (0 or 1)
        direction = result["supertrend_direction"].dropna()
        if len(direction) > 0:
            assert direction.isin([0, 1]).all(), "supertrend_direction should be 0 or 1"

        print(f"✅ Supertrend indicators: {len(supertrend_specs)} passed")

    def test_cksp_indicators(self, sample_data):
        """Test Chande Kroll Stop indicators: cksp_upper, cksp_lower"""
        cksp_specs = ["cksp_upper", "cksp_lower"]

        result = compute_features(
            sample_data, specs=cksp_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in cksp_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            # Allow some NaN values for calculations
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check that upper >= lower
        upper = result["cksp_upper"].dropna()
        lower = result["cksp_lower"].dropna()
        if len(upper) > 0 and len(lower) > 0:
            # Compare where both are not NaN
            mask = ~(result["cksp_upper"].isna() | result["cksp_lower"].isna())
            if mask.any():
                assert (
                    result.loc[mask, "cksp_upper"] >= result.loc[mask, "cksp_lower"]
                ).all(), "cksp_upper should be >= cksp_lower"

        print(f"✅ CKSP indicators: {len(cksp_specs)} passed")

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
            # CKSP
            "cksp_upper",
            "cksp_lower",
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
        sample_data = await test_instance.sample_data()

        print("Running Stage B tests...")
        test_instance.test_advanced_ma_indicators(sample_data)
        test_instance.test_supertrend_indicators(sample_data)
        test_instance.test_cksp_indicators(sample_data)
        test_instance.test_stage_b_all_together(sample_data)
        print("All Stage B tests passed!")

    asyncio.run(run_tests())
