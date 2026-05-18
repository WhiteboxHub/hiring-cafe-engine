#!/usr/bin/env python3
"""
Run all tests for Hiring Cafe Job Extractor

Usage:
    python tests/run_all_tests.py
"""
import sys
import subprocess
from pathlib import Path

# Add parent to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run_test_file(test_file):
    """Run a single test file and return (pass, fail)."""
    print(f"\n{'=' * 70}")
    print(f"Running: {test_file.name}")
    print('=' * 70)

    try:
        result = subprocess.run(
            [sys.executable, str(test_file)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode == 0:
            return True, None
        else:
            return False, f"Exit code {result.returncode}"

    except subprocess.TimeoutExpired:
        return False, "Timeout (30s)"
    except Exception as e:
        return False, str(e)


def main():
    tests_dir = Path(__file__).parent

    # Find all test files
    test_files = sorted(tests_dir.glob("test_*.py"))

    if not test_files:
        print("❌ No test files found!")
        return 1

    print("=" * 70)
    print(f"RUNNING {len(test_files)} TEST SUITES")
    print("=" * 70)

    results = {}
    for test_file in test_files:
        passed, error = run_test_file(test_file)
        results[test_file.name] = (passed, error)

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for p, _ in results.values() if p)
    failed_count = len(results) - passed_count

    for test_name, (passed, error) in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} {test_name}")
        if error:
            print(f"         Error: {error}")

    print("\n" + "=" * 70)
    if failed_count == 0:
        print(f"✅ ALL {passed_count} TEST SUITES PASSED")
        print("=" * 70)
        return 0
    else:
        print(f"❌ {failed_count}/{len(results)} TEST SUITES FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
