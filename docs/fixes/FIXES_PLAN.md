# Fixes Implementation Plan

## 1. ATS Extraction Status Tracking (CRITICAL)

**Problem**: Failed jobs marked with `ats_url: null` are skipped forever on resume.

**Solution**: Add granular status tracking:

```python
{
  "ats_extraction_status": "success | failed | blocked | no_apply_button | timeout | browser_error",
  "ats_attempt_count": 2,
  "last_attempted_at": "2024-01-15T10:30:00",
  "ats_url": null,
  "ats_error_type": "apply_button_not_found"  # detailed error for reporting
}
```

**Status Categories**:
- `success` - ATS URL extracted
- `no_apply_button` - No apply button found (all XPaths failed)
- `blocked` - Page blocked / Cloudflare challenge
- `timeout` - Page load timeout
- `browser_error` - WebDriver crash / connection lost
- `invalid_url` - Extracted URL failed validation
- `redirect_failed` - Click succeeded but no redirect
- `retryable` - Temporary error, retry later

**Retry Logic**:
- Skip `success` and `no_apply_button` (permanent)
- Retry `retryable`, `blocked`, `timeout` up to 3 attempts
- Add `--retry-failed` flag to reprocess failures

**Files to modify**:
1. `strategies/custom/hiring_cafe.py` - `_get_ats_link_from_job_page()` return status
2. `scripts/hiring_cafe_step2_extract_ats_urls.py` - check status instead of ats_url
3. `scripts/hiring_cafe_step2_parallel.py` - same status check

---

## 2. Dry-Run Mode (HIGH PRIORITY)

**Add to Step 4**:

```bash
python scripts/hiring_cafe_step4_ingest_to_api.py --dry-run
```

**Behavior**:
- Load and sanitize data (full pipeline)
- Print summary stats
- Save payload to `dry_run_payload.json`
- Skip API POST
- Exit 0

**Files to modify**:
1. `scripts/hiring_cafe_step4_ingest_to_api.py` - add `--dry-run` arg

---

## 3. Fix Blind Exception Catching (HIGH PRIORITY)

**Pattern to fix**:

```python
# BAD
try:
    risky_operation()
except Exception as e:
    logger.warning(f"Error: {e}")
    pass  # ← loses context

# GOOD
try:
    risky_operation()
except SpecificError as e:
    logger.warning(f"Expected failure in risky_operation: {e}", exc_info=True)
    # handle or re-raise
except Exception as e:
    logger.error(f"Unexpected error in risky_operation: {e}", exc_info=True)
    raise  # don't swallow unexpected errors
```

**Search locations**:
```bash
grep -n "except Exception" *.py strategies/**/*.py scripts/*.py core/*.py
```

**Files likely affected** (from grep):
- `strategies/custom/hiring_cafe.py` (~10 instances)
- `scripts/hiring_cafe_step4_ingest_to_api.py` (~5 instances)
- `core/browser.py` (~3 instances)

---

## 4. Extract Magic Numbers to Config (MEDIUM)

**Create new constants file** or add to `config/settings.py`:

```python
# Timing
DEFAULT_PAGE_LOAD_WAIT = 2.0
APPLY_BUTTON_WAIT = 5.0
NEW_TAB_WAIT_MAX = 5.0

# Limits
MAX_SCROLL_ATTEMPTS = 100
API_BATCH_SIZE = 50
MAX_ATS_RETRY_ATTEMPTS = 3

# Delays (seconds)
MIN_STEP2_PAUSE = 10.0
MAX_STEP2_PAUSE = 50.0
```

**Files to modify**:
- `strategies/custom/hiring_cafe.py`
- All `scripts/hiring_cafe_step*.py`

---

## 5. Fix Inconsistent Naming (MEDIUM)

**Standard names**:
- `job_title` (not job_tittle)
- `company_name` (not company/comapany)
- `job_posting_url` (primary), `hiring_cafe_url` (source-specific)

**Migration strategy**:
- Support both old/new keys during read
- Write only new keys
- Document in schema

**Files to modify**:
- `strategies/custom/modules/parser.py`
- `strategies/custom/hiring_cafe.py`
- All scripts

---

## 6. Make Paths Configurable (MEDIUM)

**Add to settings.py**:

```python
JOBS_FILE: str = "hiring_cafe_jobs.json"
BY_ATS_FILE: str = "hiring_cafe_by_ats.json"
OUTPUT_DIR: Path = Path(".")
```

**Files to modify**:
- All `scripts/hiring_cafe_step*.py` - use settings instead of hardcoded paths

---

## 7. DuckDB Storage (LOW PRIORITY - Future Enhancement)

**Benefits**:
- Deduplication by job_id
- Queryable run history
- Audit logs
- Metrics aggregation

**Schema**:

```sql
CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY,
  title TEXT,
  company_name TEXT,
  ats_url TEXT,
  ats_platform TEXT,
  ats_extraction_status TEXT,
  ats_attempt_count INTEGER DEFAULT 0,
  last_attempted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE extraction_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT REFERENCES jobs(job_id),
  attempt_number INTEGER,
  status TEXT,
  error_type TEXT,
  error_message TEXT,
  attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE api_ingestion_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT,
  job_id TEXT REFERENCES jobs(job_id),
  status TEXT,  -- success | failed | skipped
  response_code INTEGER,
  error_message TEXT,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Migration path**:
- Keep JSON for v1 compatibility
- Add optional `--use-duckdb` flag
- Gradually migrate

---

## Implementation Order

1. **ATS Status Tracking** - Prevents data loss on resume
2. **Dry-Run Mode** - Safe testing before API changes
3. **Fix Exception Handling** - Improves debugging
4. **Extract Magic Numbers** - Makes tuning easier
5. **Fix Naming** - Cleanup (low risk)
6. **Configurable Paths** - Nice to have
7. **DuckDB** - Future enhancement

---

## Testing Checklist

- [ ] Step 2 resume works with new status field
- [ ] Failed jobs with `retryable` status are retried
- [ ] `--dry-run` creates payload without POSTing
- [ ] Exception handling preserves stack traces
- [ ] All magic numbers moved to config
- [ ] Old JSON files still work (backward compat)
