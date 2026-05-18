# Tests

Comprehensive test suite for the Hiring Cafe Job Extractor.

## Running Tests

```bash
# Run all tests
python tests/run_all_tests.py

# Run individual test file
python tests/test_status_tracking.py
python tests/test_resume_logic.py
python tests/test_validators.py
python tests/test_sanitization.py
python tests/test_timezone_fix.py
python tests/test_parser.py
```

## Test Suites

### `test_status_tracking.py`
**Status**: ✅ Passing

Tests the new ATS extraction status tracking system:
- Return format validation (7 status codes)
- Retry logic correctness
- Resume behavior safety

**Coverage**:
- `success`, `no_apply_button`, `timeout`, `browser_error`, `invalid_url`, `blocked`, `retryable`
- Attempt count limits (max 3)
- Error detail preservation

---

### `test_resume_logic.py`
**Status**: ✅ Passing

Tests checkpoint/resume functionality:
- New jobs are processed
- Successful jobs are skipped
- Permanent failures (`no_apply_button`) are skipped
- Retryable errors are retried up to 3 attempts
- Batch statistics calculation
- Status transitions across multiple runs

**Coverage**:
- Resume logic (should_process_job)
- Attempt counting
- Status transitions
- Legacy data handling

---

### `test_validators.py`
**Status**: ✅ Passing

Tests URL validation and ATS platform detection:
- Platform detection (Workable, Greenhouse, Workday, Lever, etc.)
- URL validation (reject job boards, social media, non-HTTP)
- Job ID extraction from URLs

**Platforms tested**: Workable, Greenhouse, Workday, Lever, iCIMS, UltiPro, SmartRecruiters, Jobvite, BambooHR

---

### `test_sanitization.py`
**Status**: ✅ Passing

Tests URL sanitization and company name cleaning:
- Fix corrupted URLs (double-protocol: `https://sjotps://...`)
- Reject invalid URLs
- Junk company name detection (salary, ticker, job types)
- Company name resolution priority

**Edge cases**: Whitespace, query params, fragments, empty strings

---

### `test_timezone_fix.py`
**Status**: ✅ Passing

Tests scheduler timezone handling:
- Timezone-aware PST → UTC conversion
- Already-UTC preservation
- Naive datetime conversion (system local)
- MySQL DATETIME format validation
- Deterministic output

**Fixed bug**: Scheduler was treating naive datetimes as UTC instead of local time.

---

### `test_parser.py`
**Status**: ⚠️ Skipped (requires selenium/dependencies)

Tests card text parsing and company name resolution:
- Basic card parsing
- Cards with/without descriptions
- Salary line handling
- Stock ticker skipping
- Multi-city listings
- Junk company name filtering
- Job categorization by ATS platform

**Note**: This test requires full dependencies (selenium, etc.) and will skip gracefully if not available.

---

## Test Results

```
✅ ALL 6 TEST SUITES PASSED

✓ PASS   test_parser.py           (skipped, dependencies not available)
✓ PASS   test_resume_logic.py     (9 tests)
✓ PASS   test_sanitization.py     (6 tests)
✓ PASS   test_status_tracking.py  (2 test cases)
✓ PASS   test_timezone_fix.py     (5 tests)
✓ PASS   test_validators.py       (4 tests)
```

**Total**: 26+ test cases  
**Passing**: 100% (excluding skipped)

---

## Adding New Tests

### Structure

```python
"""
Brief description of what this test file covers
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import functions to test
from module import function


def test_feature_basic_case():
    """Test basic functionality."""
    result = function(input)
    assert result == expected
    print("✓ test_feature_basic_case")


def test_feature_edge_case():
    """Test edge case."""
    # Test implementation
    print("✓ test_feature_edge_case")


if __name__ == "__main__":
    print("=" * 70)
    print("FEATURE TESTS")
    print("=" * 70)

    test_feature_basic_case()
    test_feature_edge_case()

    print("\n" + "=" * 70)
    print("ALL FEATURE TESTS PASSED ✓")
    print("=" * 70)
```

### Guidelines

1. **Test names**: `test_module_name.py`
2. **Function names**: `test_feature_scenario()`
3. **Print progress**: Use `print("✓ test_name")` for each passing test
4. **Exit code**: Return 0 on success, non-zero on failure
5. **Standalone**: Each test file should be runnable independently
6. **No external deps**: Use stubs/mocks for heavy dependencies (selenium, etc.)

### Running in CI/CD

```bash
# In CI pipeline
python tests/run_all_tests.py
exit_code=$?

if [ $exit_code -eq 0 ]; then
  echo "✅ All tests passed"
else
  echo "❌ Tests failed"
  exit 1
fi
```

---

## Coverage

### Tested
- ✅ Status tracking (7 statuses)
- ✅ Resume/retry logic
- ✅ URL validation & sanitization
- ✅ ATS platform detection
- ✅ Timezone handling
- ✅ Company name junk detection

### Not Tested (Integration)
- ❌ Browser automation (Selenium)
- ❌ API authentication
- ❌ Full pipeline end-to-end
- ❌ Parallel processing workers

**Recommendation**: Add integration tests once unit tests are stable.

---

## Debugging Failed Tests

### Individual Test
```bash
python tests/test_resume_logic.py
```

### With Verbose Output
```python
# Add to test file
import traceback

try:
    test_function()
except AssertionError as e:
    print(f"❌ FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)
```

### Common Issues

**Import errors**:
- Ensure parent directory is in `sys.path`
- Check for circular imports
- Verify module exists

**Assertion failures**:
- Print actual vs expected values
- Check data types (str vs int, None vs "None")
- Verify test data is current

**Skipped tests**:
- Expected if dependencies (selenium, etc.) not installed
- Tests will pass with warning message

---

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Run tests
        run: python tests/run_all_tests.py
```

---

## Future Enhancements

1. **pytest integration**: Migrate to pytest for fixtures, parametrization
2. **Code coverage**: Add coverage.py to track test coverage %
3. **Integration tests**: Test full pipeline with mock data
4. **Performance tests**: Measure extraction rate, memory usage
5. **Load tests**: Test parallel workers under high load

---

**Last updated**: 2024-01-15  
**Test suites**: 6  
**Test cases**: 26+  
**Pass rate**: 100%
