# CLAUDE.md

Repository operating manual for AI-assisted development.

---

## Repository Purpose

Job scraping pipeline: hiring.cafe → ATS enrichment → API ingestion.

**Architecture**: 4-stage checkpoint pipeline with bot-detection evasion.
**Core constraint**: Must evade Cloudflare. All design decisions serve this.

---

## Philosophy

### Core Principles

- **Simplicity**: Flat over nested, explicit over clever
- **Observable**: Log transitions, not execution
- **Resumable**: Ctrl+C safe, checkpoint after mutations
- **Idempotent**: Same input = same output
- **Deterministic**: Configurable randomness
- **Schema-first**: Pydantic configs, explicit dicts
- **Surgical**: Change only what breaks

### Values

- Working > perfect
- Logs > comments  
- Config > hardcoded
- Explicit > comprehensions
- Early returns > nested ifs
- Functions > classes
- Retry logic > hope

### Avoid

- Classes for single functions
- Inheritance (use composition)
- Global mutable state
- Async (Selenium is sync)
- Premature optimization
- Magic/metaprogramming

---

## Token & Context Efficiency

**5,600 LOC repository**. Loading everything wastes tokens.

### Before Changes

1. **Search first**: `grep` before `Read`
2. **Load selectively**: Only files you'll modify + imports
3. **Reuse patterns**: Check existing code
4. **No speculation**: Don't "improve" unrelated code

### File Priority

**Read for context**:
- `CLAUDE.md` - this file
- `config/settings.py` - all config
- `README.md` - user docs

**Read on demand**:
- `core/browser.py` - browser setup
- `core/auth_service.py` - API auth
- `strategies/custom/modules/*.py` - specific logic
- `scripts/hiring_cafe_step*.py` - pipeline steps

**Never load**: `logs/`, `.git/`, `venv/`, `__pycache__/`, `chrome_profile/`

### Modification Rules

**DO**:
- Targeted edits (`old_string`/`new_string`)
- Preserve indentation
- Match existing style
- Reuse helpers
- Keep names unless fixing typos

**DON'T**:
- Rewrite functions unnecessarily
- Add explanatory comments (use logs)
- Rename for "clarity"
- Refactor "while you're there"
- Add type hints to untyped files

### Efficient Prompts

**Good**: "Add retry to step4 (3 attempts, exp backoff)"  
**Bad**: "Review and improve codebase"

**Your responses**: 1 sentence → change → 1 sentence. No essays.

---

## Architecture

### Pipeline

```
Step 1: Extract URLs     → hiring_cafe_jobs.json
  Scroll, extract IDs, save

Step 2: Extract ATS URLs → hiring_cafe_jobs.json (enriched)
  Visit pages, 6-layer URL extraction, save per job (resume-safe)

Step 3: Group by ATS     → hiring_cafe_by_ats.json
  Categorize by platform (no browser, pure transform)

Step 4: Ingest to API    → Backend
  Resolve names, sanitize, batch send
```

### Data Flow

```python
# Step 1 → Step 2
{"job_id": "x", "title": "...", "ats_url": None, "ats_platform": None}

# Step 2 → Step 3
{"job_id": "x", "ats_url": "https://...", "ats_platform": "workday"}

# Step 3 → Step 4
{"by_ats": {"workday": [...], "greenhouse": [...]}}

# Step 4 → API
{"positions": [{"title": "engineer", "company_name": "acme", ...}]}
```

### Modules

```
core/               Infrastructure (browser, auth, logging)
strategies/         Scraping logic
  custom/
    hiring_cafe.py      Main (1,400 LOC)
    modules/
      validators.py     URL validation, ATS detection
      parser.py         Card text parsing
      ats_extractor.py  ATS URL extraction
config/             Settings, locators
scripts/            Pipeline steps
```

**Rules**:
- `core/` is stateless
- `strategies/` is site-specific
- `config/` is data only
- `scripts/` are thin wrappers

---

## Python Standards

### Typing

**Use**: Function signatures, Pydantic models, known dicts  
**Skip**: Internal helpers, callbacks, `Any`

```python
# Good
def extract(job_id: str) -> str | None: pass
def categorize(jobs: list[dict]) -> dict[str, list[dict]]: pass

# Skip
def _is_junk(line): pass  # Internal, obvious
```

### Logging

**Log state, not code**:
```python
# Good
logger.info(f"Step 2: {len(jobs)} jobs")
logger.warning(f"3 failures — cooldown 20s")

# Bad
logger.info("Entering function")
logger.debug("Calling driver.get()")
```

**Levels**: INFO (progress), WARNING (retries), ERROR (failures), DEBUG (diagnosis)

**No emojis in production** (breaks log parsing)

### Error Handling

**Fail fast at boundaries**:
```python
if not job.get("job_id"):
    raise ValueError("Missing job_id")
```

**Catch specific exceptions**:
```python
try:
    driver.get(url)
except TimeoutException:
    logger.warning("Timeout — retrying")
except WebDriverException:
    logger.error("WebDriver died")
    raise
```

**Retry with backoff**:
```python
for attempt in range(max_retries):
    try:
        return api_call()
    except RequestException:
        if attempt == max_retries - 1:
            raise
        time.sleep(2 ** attempt)
```

### Config

**Pydantic settings**:
```python
class Settings(BaseSettings):
    HEADLESS: bool = False
    AUTH_URL: str | None = None
    model_config = SettingsConfigDict(env_file=".env")
```

**Rules**:
- All env vars through Pydantic
- Defaults for non-secrets
- Secrets = None (forces user)
- Never commit `.env`

### Data Structures

**Dicts for scraped data** (flexible, JSON)  
**Pydantic for APIs** (validation)  
**Dataclasses for state** (optional)

### Files

**Atomic writes**:
```python
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f)
os.replace(tmp, path)  # Atomic
```

**Always encoding**:
```python
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
```

### APIs

**Timeouts**:
```python
response = requests.post(url, json=payload, timeout=30)
```

**Batching**:
```python
batch = []
for item in items:
    batch.append(item)
    if len(batch) >= 10:
        send(batch)
        batch = []
if batch: send(batch)
```

### Browser

**Explicit waits**:
```python
element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "a.job"))
)
```

**Handle stale**:
```python
for attempt in range(3):
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, sel)
        hrefs = [el.get_attribute("href") for el in elements]
        break
    except StaleElementReferenceException:
        if attempt == 2: raise
        time.sleep(1)
```

**Cleanup**:
```python
driver = None
try:
    driver = start_browser()
    # ... scraping
finally:
    if driver:
        try: driver.quit()
        except: pass
```

---

## Code Review

### Must Fix

**Correctness**:
- [ ] Handle None/empty inputs
- [ ] Atomic file writes
- [ ] JSON keys match pipeline
- [ ] No hardcoded secrets
- [ ] Catch at right level
- [ ] No infinite loops

**Reliability**:
- [ ] Checkpoints save after mutations
- [ ] Resume skips processed
- [ ] API timeouts
- [ ] Browser cleanup in finally
- [ ] Clear stale data

**Security**:
- [ ] No secrets in code
- [ ] No command injection
- [ ] Validate inputs

**Observability**:
- [ ] Log progress
- [ ] Errors include context
- [ ] No silent failures

### Should Fix

**Performance**:
- [ ] Batch API calls
- [ ] Reuse driver
- [ ] Cache expensive ops
- [ ] Avoid O(n²)

**Maintainability**:
- [ ] Functions < 100 LOC
- [ ] Modules < 500 LOC
- [ ] Named constants
- [ ] Regex comments

**Consistency**:
- [ ] Match conventions
- [ ] Use existing helpers
- [ ] Consistent log levels

### Optional

- Parallel processing (if needed)
- Async (if multiple I/O)
- Caching (if bottleneck)

---

## LLM Coding Rules

### File Modification

**Before editing**:
1. Read file
2. Find exact text
3. Preserve indentation
4. Match style

**Surgical edits**:
```python
# Good
Edit(path="x.py", old_string='    "comapany": None,', 
     new_string='    "company": None,')

# Bad: rewrite
Edit(path="x.py", old_string="def parse(...):\n  # 50 lines",
     new_string="def parse(...):\n  # 50 new lines")
```

**Batch related**:
```python
# Good: all in one message
Edit(file1, "comapany", "company")
Edit(file2, "comapany", "company")
Edit(file3, "comapany", "company")
```

### New Modules

**Create when**:
- 200+ LOC of related functions
- New domain concept
- Optional integration

**Don't when**:
- 1-2 helpers (add to existing)
- "Organizing" working code
- Single-function modules

**Checklist**:
- [ ] Name describes domain
- [ ] Functions are cohesive
- [ ] < 500 LOC
- [ ] Has docstring

### Refactoring

**When**:
- Bug requires restructuring
- 3+ duplications
- Function > 150 LOC multi-purpose
- Feature doesn't fit

**Not when**:
- "Could be cleaner"
- "I'd write it differently"
- "Best practices"
- Fixing unrelated bug

**Safe**:
1. Test first
2. Small change
3. Verify
4. Commit
5. Repeat

### Migration-Safe

**Add field**:
```python
job = {"job_id": id, "new_field": None}  # Default
```

**Rename field**:
```python
# Support both
val = job.get("new") or job.get("old")
```

**Remove field**:
```python
# Ignore unknown
out = {k: v for k, v in job.items() if k != "old"}
```

### Backward Compat

**Never break**:
- JSON schemas (jobs.json, by_ats.json)
- Public function signatures
- Config format
- CLI args

**Safe to change**:
- Internal helpers
- Log messages
- Defaults
- Private functions (`_prefix`)

### Anti-Hallucination

**Don't invent**:
- Non-existent APIs
- Undefined config fields
- Unimplemented functions
- Missing error types

**Verify first**:
```bash
grep -r "def function_name" .
grep -r "from module import" .
```

**Ask if unsure**: "Should I create X or does it exist?"

---

## Common Patterns

### Checkpoint Files

**jobs.json**:
```json
{
  "source": "hiring.cafe",
  "step": 2,
  "count": 150,
  "jobs": [{
    "job_id": "x",
    "ats_url": "https://...",
    "ats_platform": "workday",
    "job_tittle": "Engineer",
    "company": "Acme"
  }]
}
```

**by_ats.json**:
```json
{
  "source": "hiring.cafe",
  "platforms": ["workday", "greenhouse"],
  "by_ats": {
    "workday": [{"job_id": "x", "ats_url": "..."}]
  }
}
```

### Browser Session

**Pre-flight**:
```python
# Kill stale
taskkill /F /IM chrome.exe
# Remove locks
unlink("SingletonLock")
# Nuke profile (reset fingerprint)
rmtree("Default/")
```

**Lifecycle**:
```python
driver = None
try:
    driver = browser_service.start_browser()
    # scrape
finally:
    if driver:
        try: driver.quit()
        except: pass
```

### Random Delays

**New value each call**:
```python
def random_pause(lo, hi):
    sec = random.uniform(lo, hi)
    logger.info(f"Pause: {sec:.1f}s")
    time.sleep(sec)

random_pause(2, 8)  # 5.3s
random_pause(2, 8)  # 3.1s
```

**Configurable ranges**:
```python
# settings.py
PAUSE_MIN: float = 10.0
PAUSE_MAX: float = 50.0

# usage
random_pause(settings.PAUSE_MIN, settings.PAUSE_MAX)
```

### Retry Patterns

**Exponential backoff**:
```python
for attempt in range(max_retries):
    try:
        return api_call()
    except RequestException:
        if attempt == max_retries - 1:
            raise
        time.sleep(2 ** attempt)  # 1s, 2s, 4s
```

**Consecutive failures**:
```python
failures = 0
for job in jobs:
    if not process(job):
        failures += 1
        if failures == 3:
            time.sleep(20)  # Cooldown
        elif failures >= 5:
            driver.get(homepage)  # Reset
            time.sleep(40)
            failures = 0
    else:
        failures = 0
```

### ATS Extraction (6-Layer)

```python
def get_ats(job_id):
    url = try_dom()          # 1: Check href
    if url: return url
    url = try_page_source()  # 2: Regex scan
    if url: return url
    
    btn = find_apply_button()
    if not btn: return None
    btn.click()
    
    if new_tab():
        url = get_tab_url()  # 3: New tab
        close_tab()
        return url
    
    if redirected():         # 4: Same-tab
        return current_url()
    
    url = try_page_source()  # 5: After click
    if url: return url
    
    return None              # 6: Accept failure
```

### Company Resolution

**Priority**:
1. Parsed field (if not junk)
2. URL slug (`company.workday.com` → "Company")
3. Description prefix
4. "Unknown Company"

```python
def resolve_company(job):
    company = job.get("company")
    if company and not is_junk(company):
        return company
    
    url_company = extract_from_url(job.get("ats_url"))
    if url_company:
        return url_company
    
    desc = job.get("company_description", "")
    if ":" in desc:
        prefix = desc.split(":")[0].strip()
        if prefix and not is_junk(prefix):
            return prefix
    
    return "Unknown Company"
```

### Junk Detection

```python
SALARY_RE = re.compile(r'\$\d+[kK]?[-–]\$?\d+[kK]?')
JUNK_PREFIXES = ("NYSE:", "NASDAQ:", "YOE:")
JOB_TYPES = {"full time", "contract", "internship"}
WORK_MODES = {"onsite", "remote", "hybrid"}

def is_junk(name):
    if not name: return True
    if SALARY_RE.search(name): return True
    if any(name.startswith(p) for p in JUNK_PREFIXES): return True
    if name.lower() in JOB_TYPES: return True
    if name.lower() in WORK_MODES: return True
    return False
```

---

## Anti-Patterns

### Never

```python
# Silent fail
try: x = risky()
except: pass

# Unbounded loop
while True:
    if api_call(): break
    time.sleep(1)

# Mutable default
def fn(jobs=[]): ...

# String concat in loop
s = ""
for x in xs: s += x  # O(n²)

# Nested try
try:
    try: a()
    except: b()
    c()
except: pass

# Global mutable
COUNTER = 0
def fn(): global COUNTER; COUNTER += 1

# Monkey patch
requests.get = custom_get

# Wildcard import
from module import *
```

### Avoid

```python
# Single-function class
class Processor:
    def process(self, x): return transform(x)

# Deep inheritance
class Base(ABC): pass
class Mid(Base): pass
class Concrete(Mid): pass  # 3 levels

# Meta-programming
def make_fn(name):
    def fn(x): return magic(x)
    return fn

# Premature abstraction
def extract_transform_load(extractor, transformer, loader): ...
```

---

## Quick Reference

### File Locations

```
Entry:
  run_hiring_cafe_pipeline.py
  hiring_cafe_scheduler.py

Steps:
  scripts/hiring_cafe_step{1,2,3,4}_*.py

Core:
  core/browser.py
  core/auth_service.py
  core/logger.py

Strategy:
  strategies/custom/hiring_cafe.py
  strategies/custom/modules/{validators,parser,ats_extractor}.py

Config:
  config/settings.py
  config/hiring_cafe.json
  config/hiring_cafe_locators.json
  .env

Output:
  hiring_cafe_jobs.json
  hiring_cafe_by_ats.json
  logs/pipeline_runs.log
```

### CLI

```bash
# Full
python run_hiring_cafe_pipeline.py

# Resume
python run_hiring_cafe_pipeline.py --skip-step1

# Test
python run_hiring_cafe_pipeline.py --limit 20

# Steps
python scripts/hiring_cafe_step1_extract_urls.py
python scripts/hiring_cafe_step2_extract_ats_urls.py
python scripts/hiring_cafe_step3_combine_by_ats.py
python scripts/hiring_cafe_step4_ingest_to_api.py
```

### Config

```bash
# .env
CHROME_USER_DATA_DIR=./chrome_profile
HEADLESS=false
AUTH_URL=https://api.example.com/login
AUTH_USERNAME=user
AUTH_PASSWORD=secret

# hiring_cafe.json
{"search_keywords": ["AI Engineer"], "date_fetched_past_n_days": 2}
```

### Debug

**No jobs scraped**:
- Check "Blocked page detected" in logs
- Try headless=false
- Verify chrome_profile/ wiped

**No ATS URLs**:
- Check "Apply button not found"
- Verify selectors in locators.json
- Test manual in browser

**API fails**:
- Verify AUTH_* in .env
- Check API server running
- Inspect first failed job (logged)

**Chrome crashes**:
- Kill chrome.exe
- Delete chrome_profile/Default/
- Check Chrome/chromedriver versions

---

## Contributing

**Before submitting**:
1. Read this CLAUDE.md
2. Run affected steps end-to-end
3. Check logs
4. No new dependencies unless required
5. Minimal focused changes

**Review focus**: Correctness > performance > style

**When in doubt**: Simple > elegant, explicit > implicit, working > perfect

---

**Version**: 2024-01-15 | **LOC**: ~4,350 | **Python**: 3.10+ | **Deps**: selenium, undetected-chromedriver, pydantic, requests
