# File Structure

Organized repository layout for the Hiring Cafe Job Extractor.

```
project-hiringcafe-job-extractor-automation-bot/
│
├── config/                          # Configuration files
│   ├── __init__.py
│   ├── data_loader.py              # Load hiring_cafe.json
│   ├── hiring_cafe.json            # Search params (keywords, date range)
│   ├── hiring_cafe_locators.json   # XPath selectors, ATS patterns
│   ├── secrets_validator.py        # Validate .env secrets
│   └── settings.py                 # Pydantic settings (env vars)
│
├── core/                            # Infrastructure (browser, auth, logging)
│   ├── auth_service.py             # API authentication
│   ├── browser.py                  # Browser lifecycle (start/stop/cleanup)
│   ├── captcha_handler.py          # CAPTCHA detection/handling
│   ├── email_reporter.py           # Email job reports
│   ├── human_behavior.py           # Mouse jitter, random pauses
│   ├── locator_loader.py           # Load locators.json
│   ├── logger.py                   # Centralized logging
│   ├── proxy_manager.py            # Proxy rotation
│   └── safe_actions.py             # Safe click/type with retries
│
├── strategies/                      # Scraping strategies
│   ├── base.py                     # BaseStrategy (abstract)
│   └── custom/
│       ├── __init__.py
│       ├── hiring_cafe.py          # Main strategy (1,400 LOC)
│       └── modules/
│           ├── ats_extractor.py    # ATS URL extraction (6-layer)
│           ├── parser.py           # Card text parsing
│           └── validators.py       # URL validation, ATS detection
│
├── scripts/                         # Pipeline steps
│   ├── __init__.py
│   ├── hiring_cafe_step1_extract_urls.py           # Step 1: Extract job IDs
│   ├── hiring_cafe_step2_extract_ats_urls.py       # Step 2: Extract ATS URLs (serial)
│   ├── hiring_cafe_step2_parallel.py               # Step 2: Parallel (2-3 workers)
│   ├── hiring_cafe_step3_combine_by_ats.py         # Step 3: Group by ATS platform
│   └── hiring_cafe_step4_ingest_to_api.py          # Step 4: Send to API
│
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── README.md                   # Test documentation
│   ├── run_all_tests.py            # Test runner
│   ├── test_parser.py              # Card parsing tests
│   ├── test_resume_logic.py        # Checkpoint/resume tests
│   ├── test_sanitization.py        # URL/company name cleaning tests
│   ├── test_status_tracking.py     # ATS status tracking tests
│   ├── test_timezone_fix.py        # Scheduler timezone tests
│   └── test_validators.py          # URL validation tests
│
├── docs/                            # Documentation
│   ├── architecture/
│   │   └── REFACTORING_SUMMARY.md  # Module refactoring history
│   ├── fixes/
│   │   ├── FIXES_IMPLEMENTED.md    # Recent fixes (status tracking, dry-run)
│   │   ├── FIXES_PLAN.md           # Planned fixes
│   │   └── TIMEZONE_FIX.md         # Scheduler timezone bug fix
│   ├── FILE_STRUCTURE.md           # This file
│   └── HIRING_CAFE_THREE_STEPS.md  # Pipeline overview
│
├── run_hiring_cafe_pipeline.py     # Main entry point (orchestrator)
├── hiring_cafe_scheduler.py        # Scheduled runs (cron integration)
│
├── CLAUDE.md                        # Repository operating manual (LLM instructions)
├── README.md                        # User-facing documentation
├── requirements.txt                 # Python dependencies
├── .env                             # Secrets (not committed)
├── .gitignore
│
├── start.sh                         # Linux/Mac launcher
├── start.ps1                        # Windows launcher
│
└── Output Files (generated)
    ├── hiring_cafe_jobs.json       # Step 1 → Step 2 output
    ├── hiring_cafe_by_ats.json     # Step 3 output
    ├── dry_run_payload.json        # Step 4 dry-run output
    └── logs/
        └── pipeline_runs.log       # Execution logs

```

---

## Directory Purposes

### `config/`
**Purpose**: All configuration and settings  
**Read by**: All modules  
**Contains**:
- Search parameters (keywords, date filters)
- XPath selectors for scraping
- Environment variable bindings (Pydantic)
- ATS platform detection patterns

**Never commit**: `.env` (secrets)

---

### `core/`
**Purpose**: Infrastructure and utilities  
**Used by**: Strategies, scripts  
**Stateless**: No domain logic, pure utilities  
**Contains**:
- Browser lifecycle management
- Authentication (API tokens)
- Logging (structured logs)
- Human behavior simulation (anti-detection)

**Key principle**: Reusable across different scraping targets

---

### `strategies/`
**Purpose**: Site-specific scraping logic  
**Extends**: `base.BaseStrategy`  
**Contains**:
- `hiring_cafe.py`: Main 1,400 LOC strategy
- `modules/`: Extracted functionality (parsers, validators, extractors)

**Design**: Strategy pattern - swap implementations without changing core

---

### `scripts/`
**Purpose**: Pipeline steps (CLI entry points)  
**Run**: Standalone via `python scripts/step*.py`  
**Thin wrappers**: Call strategy methods, handle I/O  
**Checkpointed**: Save after every job (resume-safe)

**Pipeline**:
1. `step1`: Extract job IDs from search pages
2. `step2`: Visit each job, extract ATS URL (6-layer fallback)
3. `step3`: Group jobs by ATS platform
4. `step4`: Ingest to API (with company name resolution)

---

### `tests/`
**Purpose**: Automated test suite  
**Run**: `python tests/run_all_tests.py`  
**Coverage**: Unit tests (no integration yet)  
**Status**: 6 suites, 26+ tests, 100% pass rate

**Tested**:
- Status tracking (7 failure types)
- Resume/retry logic
- URL validation & sanitization
- Timezone handling

---

### `docs/`
**Purpose**: Technical documentation  
**Audience**: Developers, future maintainers  
**Organized by**:
- `architecture/`: Design decisions, refactoring history
- `fixes/`: Bug fixes, improvements, migration guides

**Key files**:
- `FIXES_IMPLEMENTED.md`: Recent changes (status tracking, dry-run)
- `TIMEZONE_FIX.md`: Scheduler bug fix (naive datetime issue)

---

## Entry Points

### For Users
```bash
# Main pipeline (all 4 steps)
python run_hiring_cafe_pipeline.py

# Scheduled run (cron/Task Scheduler)
python hiring_cafe_scheduler.py
```

### For Developers
```bash
# Individual steps
python scripts/hiring_cafe_step1_extract_urls.py
python scripts/hiring_cafe_step2_extract_ats_urls.py
python scripts/hiring_cafe_step3_combine_by_ats.py
python scripts/hiring_cafe_step4_ingest_to_api.py --dry-run

# Tests
python tests/run_all_tests.py
```

---

## Output Files

### `hiring_cafe_jobs.json`
**Created by**: Step 1  
**Updated by**: Step 2  
**Format**:
```json
{
  "source": "hiring.cafe",
  "step": 2,
  "count": 150,
  "jobs": [
    {
      "job_id": "abc123",
      "title": "Engineer",
      "company": "Acme Corp",
      "ats_url": "https://apply.workable.com/x/",
      "ats_platform": "workable",
      "ats_extraction_status": "success",
      "ats_attempt_count": 1,
      "last_attempted_at": "2024-01-15T10:30:00"
    }
  ]
}
```

---

### `hiring_cafe_by_ats.json`
**Created by**: Step 3  
**Format**:
```json
{
  "source": "hiring.cafe",
  "platforms": ["workable", "greenhouse", "workday"],
  "by_ats": {
    "workable": [{...}, {...}],
    "greenhouse": [{...}]
  }
}
```

---

### `dry_run_payload.json`
**Created by**: Step 4 (--dry-run)  
**Format**: API payload (positions array)  
**Use**: Test before sending to production API

---

## Configuration Files

### `.env`
**Purpose**: Secrets (not committed)  
**Example**:
```env
AUTH_URL=https://api.example.com/login
AUTH_USERNAME=user
AUTH_PASSWORD=secret
CHROME_USER_DATA_DIR=./chrome_profile
HEADLESS=false
```

---

### `config/hiring_cafe.json`
**Purpose**: Search parameters  
**Example**:
```json
{
  "search_keywords": ["AI Engineer", "ML Engineer"],
  "date_fetched_past_n_days": 2
}
```

---

### `config/hiring_cafe_locators.json`
**Purpose**: XPath selectors, ATS patterns  
**Sections**:
- `selectors`: XPath for buttons, cards, etc.
- `ats_platform_patterns`: Regex for ATS detection
- `patterns`: Validation patterns (non-ATS domains, etc.)

---

## File Naming Conventions

### Scripts
`{site}_{step_name}.py`  
Examples: `hiring_cafe_step1_extract_urls.py`

### Tests
`test_{module_name}.py`  
Examples: `test_validators.py`, `test_resume_logic.py`

### Docs
`{TOPIC}_{TYPE}.md`  
Examples: `FIXES_IMPLEMENTED.md`, `TIMEZONE_FIX.md`

---

## Cleanup Targets

### Safe to delete
- `hiring_cafe_jobs.json` (regenerated by Step 1)
- `hiring_cafe_by_ats.json` (regenerated by Step 3)
- `dry_run_payload.json` (test output)
- `logs/` (regenerated)
- `__pycache__/` (Python cache)
- `chrome_profile/` (browser data, but may trigger re-detection)

### Never delete
- `config/` (configuration)
- `core/` (infrastructure)
- `strategies/` (scraping logic)
- `scripts/` (pipeline)
- `tests/` (test suite)
- `.env` (secrets - but gitignored)

---

## Adding New Files

### New scraping target
1. Create `strategies/custom/{site}.py` (extend BaseStrategy)
2. Create `scripts/{site}_step*.py` (pipeline steps)
3. Add config: `config/{site}.json`, `config/{site}_locators.json`
4. Update `run_{site}_pipeline.py`

### New test
1. Create `tests/test_{feature}.py`
2. Follow structure in existing tests
3. Run `python tests/run_all_tests.py` to verify

### New documentation
1. Add to `docs/architecture/` (design docs)
2. Add to `docs/fixes/` (bug fixes, improvements)
3. Update `README.md` if user-facing

---

## Migration from Old Structure

### Before
```
project/
├── test_timezone_fix.py        # Root level
├── test_status_tracking.py     # Root level
├── TIMEZONE_FIX.md             # Root level
├── FIXES_IMPLEMENTED.md        # Root level
└── FIXES_PLAN.md               # Root level
```

### After
```
project/
├── tests/
│   ├── test_timezone_fix.py
│   └── test_status_tracking.py
└── docs/
    └── fixes/
        ├── TIMEZONE_FIX.md
        ├── FIXES_IMPLEMENTED.md
        └── FIXES_PLAN.md
```

**Benefits**:
- ✅ Cleaner root directory
- ✅ Tests grouped together
- ✅ Documentation organized by category
- ✅ Easier to find related files

---

**Last updated**: 2024-01-15  
**Total files**: ~40 Python files, ~10 docs  
**Lines of code**: ~5,600 LOC
