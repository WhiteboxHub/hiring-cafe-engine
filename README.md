# Hiring Cafe Engine 🚀

An automated job scraping and ingestion pipeline that extracts job listings from [hiring.cafe](https://hiring.cafe), enriches them with ATS (Applicant Tracking System) URLs, and ingests clean data into your backend API — running daily on a schedule.

---

## 📁 Project Structure

```
hiring-cafe-engine/
├── config/
│   ├── settings.py                  # App settings loaded from .env
│   ├── data_loader.py               # JSON config loader
│   ├── secrets_validator.py         # Credential validation
│   └── hiring_cafe.json             # Search keywords and date filter
├── core/
│   ├── auth_service.py              # API authentication (token management)
│   ├── browser.py                   # Chrome browser service (undetected-chromedriver)
│   ├── captcha_handler.py           # CAPTCHA handling utilities
│   ├── human_behavior.py            # Human-like browser behavior simulation
│   ├── logger.py                    # Logging setup
│   ├── proxy_manager.py             # Proxy configuration
│   └── safe_actions.py              # Safe Selenium click/type actions
├── data/
│   ├── db_connection.py             # DuckDB connection manager
│   └── guest_form_data.json         # Applicant form data
├── db/
│   └── schema.sql                   # Database schema (run once to initialize)
├── engine/
│   ├── factory.py                   # Strategy factory (dynamic loader)
│   ├── guards.py                    # Safety limits (rate limiting, dry run)
│   └── runner.py                    # Main engine orchestrator
├── models/
│   ├── config_models.py             # SQLAlchemy ORM models (config tables)
│   ├── history_models.py            # SQLAlchemy ORM models (history tables)
│   └── __init__.py
├── scripts/
│   ├── hiring_cafe_step1_extract_urls.py       # Step 1: Scrape job URLs
│   ├── hiring_cafe_step2_extract_ats_urls.py   # Step 2: Extract ATS URLs
│   ├── hiring_cafe_step3_combine_by_ats.py     # Step 3: Group jobs by ATS
│   ├── hiring_cafe_step4_ingest_to_api.py      # Step 4: Ingest to backend API
│   ├── categorize_hiring_cafe_by_ats.py        # Utility: categorize by ATS
│   ├── scrape_hiring_cafe.py                   # Standalone scraper
│   ├── init_db.py                              # Initialize database
│   ├── check_db.py                             # Inspect database content
│   ├── query_db.py                             # Run SQL queries on DB
│   ├── main.py                                 # Engine entry point
│   └── test_api_payload.py                     # Dry run API payload preview
├── strategies/
│   └── custom/
│       └── hiring_cafe.py           # Hiring Cafe scraping strategy
├── run_hiring_cafe_pipeline.py      # Full pipeline runner (Steps 1→2→3→4)
├── scheduler.py                     # Daily scheduler
├── requirements.txt                 # Python dependencies
├── .env                             # Environment variables (not in git)
└── .gitignore
```

---

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/your-username/hiring-cafe-engine.git
cd hiring-cafe-engine
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create `.env` file
```dotenv
# Database
DUCKDB_PATH=data/job_engine.duckdb

# Browser
CHROME_USER_DATA_DIR=./chrome_profile
HEADLESS=false

# Proxy (optional)
PROXY_URL=

# Safety
MAX_APPLICATIONS_PER_RUN=10
SUBMISSION_COOLDOWN_SECONDS=30
DRY_RUN=false

# Scheduler time (24h format)
SCHEDULER_TIME=09:00

# Backend API authentication
AUTH_URL=https://your-api.com/api/login
AUTH_USERNAME=your_email@example.com
AUTH_PASSWORD=your_password
```

### 5. Initialize the database
```bash
python scripts/init_db.py
```

---

## 🔍 Search Configuration

Edit `config/hiring_cafe.json` to set keywords and date filter:

```json
{
    "search_keywords": ["AI+Engineer", "ML+Engineer", "LLM+Engineer"],
    "date_fetched_past_n_days": 2
}
```

| Value | Meaning |
|-------|---------|
| `2`   | Last 24 hours |
| `4`   | Last 3 days |
| `14`  | Last 1 week |
| `21`  | Last 2 weeks |
| `-1`  | All time |

---

## 🚀 Running the Pipeline

### Full pipeline (all 4 steps)
```bash
python run_hiring_cafe_pipeline.py
```

### Skip step 1 (resume after interruption)
```bash
python run_hiring_cafe_pipeline.py --skip-step1
```

### Test with limited jobs
```bash
python run_hiring_cafe_pipeline.py --limit 20
```

### Run individual steps
```bash
# Step 1: Scrape job URLs
python scripts/hiring_cafe_step1_extract_urls.py

# Step 2: Extract ATS URLs (resumes from checkpoint if interrupted)
python scripts/hiring_cafe_step2_extract_ats_urls.py

# Step 3: Combine by ATS platform
python scripts/hiring_cafe_step3_combine_by_ats.py

# Step 4: Ingest to backend API
python scripts/hiring_cafe_step4_ingest_to_api.py --input hiring_cafe_by_ats.json
```

---

## 📋 Pipeline Steps Explained

| Step | Script | Description |
|------|--------|-------------|
| 1 | `hiring_cafe_step1_extract_urls.py` | Opens hiring.cafe, searches by keyword, scrolls to load all jobs, saves job IDs and URLs |
| 2 | `hiring_cafe_step2_extract_ats_urls.py` | Opens each job page, extracts the ATS apply URL (Workday, Greenhouse, etc.). Saves after every job — safe to interrupt and resume |
| 3 | `hiring_cafe_step3_combine_by_ats.py` | Groups jobs by ATS platform into `hiring_cafe_by_ats.json`. No browser needed |
| 4 | `hiring_cafe_step4_ingest_to_api.py` | Cleans and normalizes data, sends to backend API in batches of 50 |

---

## ⏰ Scheduler

### Start the daily scheduler
```bash
python scheduler.py
```

Set the run time in `.env`:
```
SCHEDULER_TIME=09:00
```

The scheduler runs the full pipeline automatically every day at the set time. Keep the terminal window open, or use Windows Task Scheduler for fully automated background runs.

### Windows Task Scheduler Setup
1. Open Task Scheduler → **Create Task**
2. **General tab**: Check "Run whether user is logged on or not" + "Run with highest privileges"
3. **Triggers tab**: Daily at your preferred time
4. **Actions tab**:
   - Program: `C:\path\to\venv\Scripts\python.exe`
   - Arguments: `run_hiring_cafe_pipeline.py`
   - Start in: `C:\path\to\hiring-cafe-engine`
5. **Conditions tab**: Uncheck "Start only if on AC power"
6. **Settings tab**: Check "Run task as soon as possible after a scheduled start is missed"

---

## 🗄️ Database

The project uses **DuckDB** (`data/job_engine.duckdb`).

### Inspect database
```bash
python scripts/check_db.py
```

### Run SQL queries
```bash
python scripts/query_db.py
```

### Common queries
```sql
-- All job listings
SELECT * FROM job_listings LIMIT 10;

-- Application history
SELECT * FROM applications ORDER BY applied_at DESC LIMIT 10;

-- Status breakdown
SELECT status, COUNT(*) FROM job_listings GROUP BY status;
```

---

## 📦 Output Files

| File | Description |
|------|-------------|
| `hiring_cafe_jobs.json` | Raw scraped jobs with ATS URLs (Step 1 & 2 output) |
| `hiring_cafe_by_ats.json` | Jobs grouped by ATS platform (Step 3 output) |
| `logs/pipeline_runs.log` | Pipeline run history |
| `logs/scheduler.log` | Scheduler activity log |

---

## 🔧 Supported ATS Platforms

Workday · Greenhouse · Lever · SmartRecruiters · iCIMS · Taleo · Ashby · Workable · BambooHR · Oracle Cloud · SAP SuccessFactors · Jobvite · Recruitee · Teamtailor · Personio · Rippling · Paylocity · Breezy · Jazz HR · BrassRing · ADP · and more

---

## 🛠️ Troubleshooting

**Browser opens blank page / 0 jobs scraped**
- hiring.cafe may be rate limiting your IP
- Wait 30-60 minutes and retry
- This only happens when running the pipeline multiple times in a short period

**UnicodeEncodeError on Windows**
- Make sure you are using the fixed `scheduler.py` which sets `PYTHONIOENCODING=utf-8`

**Step 4 authentication failed**
- Check `AUTH_URL`, `AUTH_USERNAME`, `AUTH_PASSWORD` in your `.env`
- Make sure your backend server is running

**Resume interrupted Step 2**
```bash
python run_hiring_cafe_pipeline.py --skip-step1
```
Step 2 saves progress after every single job — it will pick up exactly where it left off.

---

## 📄 License

MIT