"""
Run all memory optimization tests.

This script runs all the tests we created for the memory optimization features.
"""

import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))


def run_test_script(script_name: str, description: str) -> bool:
    """Run a test script and return success status."""
    print(f"\n🧪 Running {description}...")
    print("-" * 50)

    try:
        start_time = time.time()

        result = subprocess.run(
            [sys.executable, script_name], capture_output=True, text=True, timeout=300
        )  # 5 minute timeout

        end_time = time.time()
        duration = end_time - start_time

        if result.returncode == 0:
            print(f"✅ {description} passed in {duration:.2f} seconds")
            if result.stdout:
                print("Output:")
                print(result.stdout)
            return True
        print(f"❌ {description} failed in {duration:.2f} seconds")
        if result.stderr:
            print("Error:")
            print(result.stderr)
        return False

    except subprocess.TimeoutExpired:
        print(f"❌ {description} timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {e}")
        return False


def run_all_tests():
    """Run all memory optimization tests."""
    print("🚀 Starting comprehensive memory optimization test suite...")
    print("=" * 60)

    # List of tests to run
    tests = [
        ("src/features/quick_test.py", "Quick Memory Test"),
        ("src/features/test_memory_optimization.py", "Full Memory Optimization Test"),
        ("src/features/test_cli.py", "CLI Test"),
    ]

    results = {}

    for script_name, description in tests:
        success = run_test_script(script_name, description)
        results[description] = success

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print("=" * 60)

    total_tests = len(tests)
    passed_tests = sum(1 for success in results.values() if success)
    failed_tests = total_tests - passed_tests

    for description, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {description}: {status}")

    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Memory optimization is working correctly.")
        return True
    print(f"\n⚠️  {failed_tests} test(s) failed. Please check the output above.")
    return False


def run_quick_tests_only():
    """Run only the quick tests."""
    print("🚀 Running quick tests only...")
    print("=" * 40)

    # Run quick test
    success = run_test_script("src/features/quick_test.py", "Quick Memory Test")

    if success:
        print("\n🎉 Quick test passed!")
        return True
    print("\n❌ Quick test failed!")
    return False


def run_cli_tests_only():
    """Run only the CLI tests."""
    print("🚀 Running CLI tests only...")
    print("=" * 40)

    # Run CLI test
    success = run_test_script("src/features/test_cli.py", "CLI Test")

    if success:
        print("\n🎉 CLI test passed!")
        return True
    print("\n❌ CLI test failed!")
    return False


def main():
    """Main function to run tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Run memory optimization tests")
    parser.add_argument("--quick", action="store_true", help="Run only quick tests")
    parser.add_argument("--cli", action="store_true", help="Run only CLI tests")
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")

    args = parser.parse_args()

    if args.quick:
        success = run_quick_tests_only()
    elif args.cli:
        success = run_cli_tests_only()
    else:
        success = run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
