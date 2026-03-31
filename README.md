# hiring-cafe-engine

> Automated job scraping, ATS enrichment, and API ingestion pipeline for [hiring.cafe](https://hiring.cafe) — runs daily on a schedule with built-in bot-detection evasion.

---

## Overview

`hiring-cafe-engine` is a 4-step Python pipeline that:

1. **Scrapes** job listings from hiring.cafe by keyword and date filter
2. **Enriches** each listing with its direct ATS (Applicant Tracking System) apply URL
3. **Groups** enriched jobs by ATS platform
4. **Ingests** clean, normalized job data into your backend API

The pipeline is triggered daily by **Windows Task Scheduler** and integrates with an orchestrator API for schedule locking, run logging, and next-run management.

---

## Project Structure

```
hiring-cafe-engine/
│
├── hiring_cafe_scheduler.py             # Scheduler entry point (orchestrator-aware)
├── hiring_cafe_scheduler_launcher.bat   # Windows Task Scheduler BAT launcher
├── run_hiring_cafe_pipeline.py          # Full pipeline runner (Steps 1 → 4)
│
├── scripts/
│   ├── hiring_cafe_step1_extract_urls.py       # Scrape job URLs from hiring.cafe
│   ├── hiring_cafe_step2_extract_ats_urls.py   # Extract ATS apply URLs (checkpoint-safe)
│   ├── hiring_cafe_step3_combine_by_ats.py     # Group jobs by ATS platform
│   ├── hiring_cafe_step4_ingest_to_api.py      # Normalize & send to backend API
│   ├── categorize_hiring_cafe_by_ats.py        # Utility: categorize by ATS
│   ├── scrape_hiring_cafe.py                   # Standalone scraper
│   ├── init_db.py                              # Initialize DuckDB database
│   ├── check_db.py                             # Inspect database content
│   ├── query_db.py                             # Run SQL queries on DB
│   ├── main.py                                 # Engine entry point
│   └── test_api_payload.py                     # Preview API payload (dry run)
│
├── core/
│   ├── browser.py          # Chrome automation (undetected-chromedriver + anti-detection)
│   ├── auth_service.py     # JWT authentication & BaseAPIClient
│   ├── human_behavior.py   # Human-like delay simulation
│   ├── safe_actions.py     # Resilient Selenium action wrappers
│   ├── captcha_handler.py  # CAPTCHA detection utilities
│   ├── proxy_manager.py    # Optional proxy support
│   └── logger.py           # Logging configuration
│
├── strategies/
│   └── custom/
│       └── hiring_cafe.py  # HiringCafeStrategy: scroll, scrape, enrich
│
├── config/
│   ├── settings.py         # Pydantic settings (reads from .env)
│   ├── hiring_cafe.json    # Search keywords & date filter
│   ├── data_loader.py      # JSON config loader
│   └── secrets_validator.py
│
├── data/
│   └── job_engine.duckdb   # Local DuckDB database
│
├── docs/
│   └── HIRING_CAFE_THREE_STEPS.md   # Step-by-step usage guide
│
├── logs/                   # Runtime logs (auto-created)
├── chrome_profile/         # Persistent Chrome user profile
├── hiring_cafe_jobs.json   # Step 1 & 2 output (runtime)
├── hiring_cafe_by_ats.json # Step 3 output / Step 4 input (runtime)
├── requirements.txt
└── .env                    # Environment config (not committed)
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/hiring-cafe-engine.git
cd hiring-cafe-engine
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```dotenv
# ── Browser ───────────────────────────────────────────────
CHROME_USER_DATA_DIR=./chrome_profile
HEADLESS=false

# ── Database ─────────────────────────────────────────────
DUCKDB_PATH=data/job_engine.duckdb

# ── Proxy (optional) ─────────────────────────────────────
PROXY_URL=

# ── Backend API ───────────────────────────────────────────
AUTH_URL=https://your-api.com/api/login
AUTH_USERNAME=your_email@example.com
AUTH_PASSWORD=your_password

# ── Optional overrides ────────────────────────────────────
# API_BASE_URL=https://your-api.com/api
# API_TOKEN=your_static_bearer_token
```

### 5. Initialize the database

```bash
python scripts/init_db.py
```

---

## Configuration

Edit `config/hiring_cafe.json` to control what jobs are scraped:

```json
{
    "search_keywords": ["AI+Engineer", "ML+Engineer", "LLM+Engineer"],
    "date_fetched_past_n_days": 2
}
```

| `date_fetched_past_n_days` | Filters jobs posted in the last… |
|---|---|
| `2` | 24 hours |
| `4` | 3 days |
| `14` | 1 week |
| `21` | 2 weeks |
| `-1` | All time |

---

## Running the Pipeline

### Full pipeline (Steps 1 → 4)

```bash
python run_hiring_cafe_pipeline.py
```

### Resume after interruption (skip Step 1)

```bash
python run_hiring_cafe_pipeline.py --skip-step1
```

### Test with a limited number of jobs

```bash
python run_hiring_cafe_pipeline.py --limit 20
```

### Run individual steps

```bash
# Step 1 — Scrape job URLs
python scripts/hiring_cafe_step1_extract_urls.py

# Step 2 — Extract ATS URLs (checkpoint/resume safe)
python scripts/hiring_cafe_step2_extract_ats_urls.py

# Step 3 — Group by ATS platform
python scripts/hiring_cafe_step3_combine_by_ats.py

# Step 4 — Ingest to backend API
python scripts/hiring_cafe_step4_ingest_to_api.py --input hiring_cafe_by_ats.json
```

---

## Pipeline Steps

| Step | Script | Description |
|------|--------|-------------|
| **1** | `hiring_cafe_step1_extract_urls.py` | Opens hiring.cafe, searches by keyword, scrolls to load all results, saves job IDs and URLs |
| **2** | `hiring_cafe_step2_extract_ats_urls.py` | Visits each job page and extracts the direct ATS apply URL. Saves after **every job** — safe to interrupt and resume |
| **3** | `hiring_cafe_step3_combine_by_ats.py` | Groups jobs into `hiring_cafe_by_ats.json` by platform. No browser required |
| **4** | `hiring_cafe_step4_ingest_to_api.py` | Resolves company names, sanitizes geo fields, sends to backend in **batches of 50** |

### Automatic pre-flight (before every run)

Before Step 1 launches, the pipeline automatically:
- Kills any stale `chrome.exe` / `chromedriver.exe` processes
- Removes Chrome profile lock files (`SingletonLock`, `Default/LOCK`, etc.)
- Clears Chrome cache directories — resets the Cloudflare bot fingerprint each run

---

## Scheduling

The engine is designed to run unattended via **Windows Task Scheduler**.

### How it works

```
Windows Task Scheduler
  └─► hiring_cafe_scheduler_launcher.bat   (sets env vars, captures logs)
        └─► hiring_cafe_scheduler.py
              ├─► GET  /orchestrator/schedules/due   (check if workflow #9 is due)
              ├─► POST /orchestrator/schedules/{id}/lock   (prevent double-runs)
              ├─► run_pipeline()
              ├─► PUT  /orchestrator/schedules/{id}   (set next_run_at via cron)
              └─► PUT  /orchestrator/logs/{id}        (record result)
              
              ↓ Fallback (if API unreachable)
              └─► run_pipeline() in standalone mode
```

> **Standalone mode:** If the orchestrator API cannot be reached, the pipeline still runs — no data is lost.

### Register in Task Scheduler

| Setting | Value |
|---|---|
| **Program** | `C:\Users\remot\Desktop\job_engine\hiring-cafe-engine\hiring_cafe_scheduler_launcher.bat` |
| **Start in** | `C:\Users\remot\Desktop\job_engine\hiring-cafe-engine` |
| **Trigger** | Daily at your preferred time |
| **General** | ✅ Run whether user is logged on or not |
| **Conditions** | ❌ Uncheck "Start only if on AC power" |
| **Settings** | ✅ Run task as soon as possible after a scheduled start is missed |

> **Why the BAT launcher?**  
> It sets `SCHEDULER_LAUNCHED=1`, which tells `browser.py` to apply additional Chrome anti-detection flags required when running under Task Scheduler (no interactive TTY).

### Log files

| File | Contents |
|------|---------|
| `logs/scheduler_bat_rolling.log` | Latest BAT launcher run output |
| `logs/scheduler_bat.log` | Full rolling BAT log history |
| `logs/pipeline_runs.log` | Structured JSON record of every pipeline run |

---

## Supported ATS Platforms

Workday · Greenhouse · Lever · Ashby · SmartRecruiters · iCIMS · Jobvite · Rippling · Taleo · BambooHR · Recruitee · Teamtailor · Workable · Oracle · SAP SuccessFactors · Paylocity · Breezy · JazzHR · BrassRing · ADP · and more

---

## Database Utilities

```bash
# Inspect database tables and row counts
python scripts/check_db.py

# Run custom SQL queries
python scripts/query_db.py
```

---

## Troubleshooting

**0 jobs scraped / blank page on Step 1**
- hiring.cafe may be rate-limiting your IP or session
- Wait 30–60 minutes and retry; the pre-flight cache clear helps reset fingerprinting
- Try running with `--headless` removed so Chrome appears as an interactive browser

**Step 2 was interrupted mid-run**
```bash
python run_hiring_cafe_pipeline.py --skip-step1
```
Step 2 saves progress after every single job — it resumes exactly where it stopped with no data loss.

**Step 4 authentication failed**
- Verify `AUTH_URL`, `AUTH_USERNAME`, `AUTH_PASSWORD` in `.env`
- Confirm your backend server is running and the login endpoint is reachable

**Chrome version mismatch error**
- `browser.py` auto-detects your installed Chrome version from the Windows registry
- If detection fails, the fallback version is `146` — update the fallback in `core/browser.py` if needed

**Unicode / emoji errors on Windows**
- Set `PYTHONUTF8=1` before running, or use the BAT launcher which sets this automatically

---

## License

MIT