"""
Test Stage A indicators: overlap, statistics, performance, squeeze, stochrsi
"""

import pandas as pd
import pytest
from sqlalchemy import text

from src.database import get_async_session
from src.features import compute_features


class TestStageA:
    """Test Stage A indicators with real OHLCV data"""

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

    def test_overlap_indicators(self, sample_data):
        """Test overlap indicators: hl2, hlc3, ohlc4, wcp, midpoint, midprice"""
        overlap_specs = ["hl2", "hlc3", "ohlc4", "wcp", "midpoint", "midprice"]

        result = compute_features(
            sample_data, specs=overlap_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in overlap_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check specific calculations
        assert (
            abs(
                result["hl2"].iloc[-1]
                - (result["high"].iloc[-1] + result["low"].iloc[-1]) / 2
            )
            < 1e-10
        )
        assert (
            abs(
                result["hlc3"].iloc[-1]
                - (
                    result["high"].iloc[-1]
                    + result["low"].iloc[-1]
                    + result["close"].iloc[-1]
                )
                / 3
            )
            < 1e-10
        )
        assert (
            abs(
                result["ohlc4"].iloc[-1]
                - (
                    result["open"].iloc[-1]
                    + result["high"].iloc[-1]
                    + result["low"].iloc[-1]
                    + result["close"].iloc[-1]
                )
                / 4
            )
            < 1e-10
        )

        # midpoint should equal hl2
        assert abs(result["midpoint"].iloc[-1] - result["hl2"].iloc[-1]) < 1e-10
        assert abs(result["midprice"].iloc[-1] - result["hl2"].iloc[-1]) < 1e-10

        print(f"✅ Overlap indicators: {len(overlap_specs)} passed")

    def test_statistics_indicators(self, sample_data):
        """Test statistics indicators: median, mad, stdev, variance, skew, kurtosis, zscore"""
        stats_specs = [
            "median_20",
            "mad_20",
            "stdev_20",
            "variance_20",
            "skew_20",
            "kurtosis_20",
            "zscore_20",
        ]

        result = compute_features(
            sample_data, specs=stats_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in stats_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            # Allow some NaN values for rolling calculations
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check that variance = stdev^2
        variance = result["variance_20"].dropna()
        stdev = result["stdev_20"].dropna()
        if len(variance) > 0 and len(stdev) > 0:
            assert abs(variance.iloc[-1] - stdev.iloc[-1] ** 2) < 1e-6

        print(f"✅ Statistics indicators: {len(stats_specs)} passed")

    def test_performance_indicators(self, sample_data):
        """Test performance indicators: log_return, percent_return, trend_return, drawdown"""
        perf_specs = ["log_return", "percent_return", "trend_return_20", "drawdown"]

        result = compute_features(
            sample_data, specs=perf_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in perf_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            # Allow some NaN values for calculations
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check that drawdown is negative or zero
        drawdown = result["drawdown"].dropna()
        if len(drawdown) > 0:
            assert (drawdown <= 0).all(), "Drawdown should be <= 0"

        print(f"✅ Performance indicators: {len(perf_specs)} passed")

    def test_squeeze_indicators(self, sample_data):
        """Test squeeze indicators: ttm_squeeze_on, ttm_squeeze_value, ttm_squeeze_hist"""
        squeeze_specs = ["ttm_squeeze_on", "ttm_squeeze_value", "ttm_squeeze_hist"]

        result = compute_features(
            sample_data, specs=squeeze_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in squeeze_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            # Allow some NaN values for calculations
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check that squeeze_on is binary (0 or 1)
        squeeze_on = result["ttm_squeeze_on"].dropna()
        if len(squeeze_on) > 0:
            assert squeeze_on.isin([0, 1]).all(), "squeeze_on should be 0 or 1"

        print(f"✅ Squeeze indicators: {len(squeeze_specs)} passed")

    def test_stochrsi_indicators(self, sample_data):
        """Test StochRSI indicators: stochrsi_k, stochrsi_d"""
        stochrsi_specs = ["stochrsi_k", "stochrsi_d"]

        result = compute_features(
            sample_data, specs=stochrsi_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in stochrsi_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"
            # Allow some NaN values for calculations
            assert not result[spec].isna().all(), f"All NaN values for {spec}"

        # Check that StochRSI values are in range [0, 1]
        for spec in stochrsi_specs:
            values = result[spec].dropna()
            if len(values) > 0:
                assert (values >= 0).all() and (
                    values <= 1
                ).all(), f"{spec} should be in range [0, 1]"

        print(f"✅ StochRSI indicators: {len(stochrsi_specs)} passed")

    def test_stage_a_all_together(self, sample_data):
        """Test all Stage A indicators together"""
        all_specs = [
            # Overlap
            "hl2",
            "hlc3",
            "ohlc4",
            "wcp",
            "midpoint",
            "midprice",
            # Statistics
            "median_20",
            "mad_20",
            "stdev_20",
            "variance_20",
            "skew_20",
            "kurtosis_20",
            "zscore_20",
            # Performance
            "log_return",
            "percent_return",
            "trend_return_20",
            "drawdown",
            # Squeeze
            "ttm_squeeze_on",
            "ttm_squeeze_value",
            "ttm_squeeze_hist",
            # StochRSI
            "stochrsi_k",
            "stochrsi_d",
        ]

        result = compute_features(
            sample_data, specs=all_specs, volatility_normalize=False
        )

        # Check all indicators are calculated
        for spec in all_specs:
            assert spec in result.columns, f"Missing indicator: {spec}"

        print(f"✅ Stage A all indicators: {len(all_specs)} passed")
        print(f"Result shape: {result.shape}")
        print(f"Columns: {list(result.columns)}")


if __name__ == "__main__":
    # Run tests manually
    import asyncio

    async def run_tests():
        test_instance = TestStageA()
        sample_data = await test_instance.sample_data()

        print("Running Stage A tests...")
        test_instance.test_overlap_indicators(sample_data)
        test_instance.test_statistics_indicators(sample_data)
        test_instance.test_performance_indicators(sample_data)
        test_instance.test_squeeze_indicators(sample_data)
        test_instance.test_stochrsi_indicators(sample_data)
        test_instance.test_stage_a_all_together(sample_data)
        print("All Stage A tests passed!")

    asyncio.run(run_tests())
