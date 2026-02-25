"""
Test CLI functionality for memory optimization features.

This script tests the CLI commands we implemented.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))


def create_test_data_file(n_rows: int = 1000) -> str:
    """Create a test CSV file with OHLCV data."""
    print(f"Creating test data file with {n_rows} rows...")

    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n_rows, freq="1H")
    base_price = 100.0
    returns = np.random.normal(0, 0.02, n_rows)
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame(
        {
            "ts": dates.astype("int64") // 10**9,
            "open": prices * (1 + np.random.normal(0, 0.001, n_rows)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.01, n_rows))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.01, n_rows))),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, n_rows),
        }
    )

    # Ensure high >= max(open, close) and low <= min(open, close)
    df["high"] = np.maximum(df["high"], np.maximum(df["open"], df["close"]))
    df["low"] = np.minimum(df["low"], np.minimum(df["open"], df["close"]))

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp_file:
        df.to_csv(tmp_file.name, index=False)
        return tmp_file.name


def test_cli_help():
    """Test CLI help commands."""
    print("\n🧪 Testing CLI help commands...")

    try:
        # Test main help
        result = subprocess.run(
            [sys.executable, "-m", "src.features", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("    ✅ Main help command works")
        else:
            print(f"    ❌ Main help command failed: {result.stderr}")
            return False

        # Test calculate help
        result = subprocess.run(
            [sys.executable, "-m", "src.features", "calculate", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("    ✅ Calculate help command works")
        else:
            print(f"    ❌ Calculate help command failed: {result.stderr}")
            return False

        # Test save help
        result = subprocess.run(
            [sys.executable, "-m", "src.features", "save", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("    ✅ Save help command works")
        else:
            print(f"    ❌ Save help command failed: {result.stderr}")
            return False

        # Test validate help
        result = subprocess.run(
            [sys.executable, "-m", "src.features", "validate", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("    ✅ Validate help command works")
        else:
            print(f"    ❌ Validate help command failed: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print("    ❌ CLI commands timed out")
        return False
    except Exception as e:
        print(f"    ❌ CLI test failed: {e}")
        return False


def test_cli_calculate():
    """Test CLI calculate command."""
    print("\n🧪 Testing CLI calculate command...")

    # Create test data file
    test_file = create_test_data_file(500)

    try:
        # Test calculate command
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.features",
                "calculate",
                "--input",
                test_file,
                "--symbol",
                "TEST",
                "--timeframe",
                "1H",
                "--output",
                "test_output.parquet",
                "--indicators",
                "hlc3,ema_8,sma_20,rsi_14",
                "--chunk-size",
                "100",
                "--max-lookback",
                "50",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print("    ✅ Calculate command works")
            print(f"    Output: {result.stdout}")
        else:
            print(f"    ❌ Calculate command failed: {result.stderr}")
            return False

        # Check if output file was created
        if Path("test_output.parquet").exists():
            print("    ✅ Output file created")
            # Clean up
            Path("test_output.parquet").unlink()
        else:
            print("    ❌ Output file not created")
            return False

        return True

    except subprocess.TimeoutExpired:
        print("    ❌ Calculate command timed out")
        return False
    except Exception as e:
        print(f"    ❌ Calculate test failed: {e}")
        return False
    finally:
        # Clean up test file
        if Path(test_file).exists():
            Path(test_file).unlink()


def test_cli_validate():
    """Test CLI validate command."""
    print("\n🧪 Testing CLI validate command...")

    # Create test data file
    test_file = create_test_data_file(200)

    try:
        # Test validate command
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.features",
                "validate",
                "--input",
                test_file,
                "--data-type",
                "ohlcv",
                "--strict",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print("    ✅ Validate command works")
            print(f"    Output: {result.stdout}")
        else:
            print(f"    ❌ Validate command failed: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print("    ❌ Validate command timed out")
        return False
    except Exception as e:
        print(f"    ❌ Validate test failed: {e}")
        return False
    finally:
        # Clean up test file
        if Path(test_file).exists():
            Path(test_file).unlink()


def test_cli_test_parquet():
    """Test CLI test-parquet command."""
    print("\n🧪 Testing CLI test-parquet command...")

    # Create test data file
    test_file = create_test_data_file(300)

    try:
        # Test test-parquet command
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.features",
                "test-parquet",
                "--input",
                test_file,
                "--symbol",
                "TEST",
                "--timeframe",
                "1H",
                "--indicators",
                "hlc3,ema_8,sma_20",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print("    ✅ Test-parquet command works")
            print(f"    Output: {result.stdout}")
        else:
            print(f"    ❌ Test-parquet command failed: {result.stderr}")
            return False

        return True

    except subprocess.TimeoutExpired:
        print("    ❌ Test-parquet command timed out")
        return False
    except Exception as e:
        print(f"    ❌ Test-parquet test failed: {e}")
        return False
    finally:
        # Clean up test file
        if Path(test_file).exists():
            Path(test_file).unlink()


def test_cli_pipeline():
    """Test CLI pipeline command."""
    print("\n🧪 Testing CLI pipeline command...")

    # Create test data file
    test_file = create_test_data_file(400)

    try:
        # Test pipeline command
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.features",
                "pipeline",
                "--input",
                test_file,
                "--symbol",
                "TEST",
                "--timeframe",
                "1H",
                "--output",
                "test_pipeline_output.parquet",
                "--indicators",
                "hlc3,ema_8,sma_20,rsi_14",
                "--chunk-size",
                "100",
                "--max-lookback",
                "50",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            print("    ✅ Pipeline command works")
            print(f"    Output: {result.stdout}")
        else:
            print(f"    ❌ Pipeline command failed: {result.stderr}")
            return False

        # Check if output file was created
        if Path("test_pipeline_output.parquet").exists():
            print("    ✅ Pipeline output file created")
            # Clean up
            Path("test_pipeline_output.parquet").unlink()
        else:
            print("    ❌ Pipeline output file not created")
            return False

        return True

    except subprocess.TimeoutExpired:
        print("    ❌ Pipeline command timed out")
        return False
    except Exception as e:
        print(f"    ❌ Pipeline test failed: {e}")
        return False
    finally:
        # Clean up test file
        if Path(test_file).exists():
            Path(test_file).unlink()


def run_cli_tests():
    """Run all CLI tests."""
    print("🚀 Starting CLI tests...")
    print("=" * 50)

    try:
        # Test 1: Help commands
        help_success = test_cli_help()

        # Test 2: Calculate command
        calculate_success = test_cli_calculate()

        # Test 3: Validate command
        validate_success = test_cli_validate()

        # Test 4: Test-parquet command
        test_parquet_success = test_cli_test_parquet()

        # Test 5: Pipeline command
        pipeline_success = test_cli_pipeline()

        print("\n" + "=" * 50)
        print("📊 CLI Test Results:")
        print(f"  Help commands: {'✅ Passed' if help_success else '❌ Failed'}")
        print(
            f"  Calculate command: {'✅ Passed' if calculate_success else '❌ Failed'}"
        )
        print(f"  Validate command: {'✅ Passed' if validate_success else '❌ Failed'}")
        print(
            f"  Test-parquet command: {'✅ Passed' if test_parquet_success else '❌ Failed'}"
        )
        print(f"  Pipeline command: {'✅ Passed' if pipeline_success else '❌ Failed'}")

        all_success = all(
            [
                help_success,
                calculate_success,
                validate_success,
                test_parquet_success,
                pipeline_success,
            ]
        )

        if all_success:
            print("\n🎉 All CLI tests passed!")
            return True
        print("\n❌ Some CLI tests failed!")
        return False

    except Exception as e:
        print(f"\n❌ CLI test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_cli_tests()
    sys.exit(0 if success else 1)
