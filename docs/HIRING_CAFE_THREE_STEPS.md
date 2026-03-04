# Hiring Cafe: Three-Step Workflow

You can run each step **individually**.

## Step 1: Extract Hiring Cafe URLs

Scrapes hiring.cafe by keyword and date filter; saves job list **without** ATS URLs.

```bash
# Use config/hiring_cafe.json for keywords and date (default)
python scripts/hiring_cafe_step1_extract_urls.py

# Override date filter: today, 24h, 3d, 1w, 2w, all
python scripts/hiring_cafe_step1_extract_urls.py --output hiring_cafe_jobs.json --date-filter today

# Limit number of jobs
python scripts/hiring_cafe_step1_extract_urls.py --date-filter 24h --job-limit 100 --headless
```

**Output:** `hiring_cafe_jobs.json` (or `--output`) with `jobs[]`: `job_id`, `title`, `hiring_cafe_url`, `ats_url: null`.

---

## Step 2: Extract ATS URLs

Reads the JSON from Step 1, opens each job page, resolves the Apply link, and saves `ats_url` and `ats_platform`.

```bash
# Enrich all jobs from default input (hiring_cafe_jobs.json)
python scripts/hiring_cafe_step2_extract_ats_urls.py

# Custom input/output, limit to first 50
python scripts/hiring_cafe_step2_extract_ats_urls.py --input hiring_cafe_jobs.json --output enriched.json --limit 50 --headless
```

**Output:** Same structure with `ats_url` and `ats_platform` filled (or overwrites `--input` if `--output` omitted).

---

## Step 3: Combine into By-ATS File

Takes the enriched JSON and builds one file grouped by ATS platform. **No browser.**

```bash
# Default: read hiring_cafe_jobs.json, write hiring_cafe_by_ats.json
python scripts/hiring_cafe_step3_combine_by_ats.py

# Custom paths
python scripts/hiring_cafe_step3_combine_by_ats.py --input enriched.json --output hiring_cafe_by_ats.json
```

**Output:** `hiring_cafe_by_ats.json` with `by_ats`: `{ "workday": [...], "greenhouse": [...], ... }` and each entry: `job_id`, `title`, `hiring_cafe_url`, `ats_url`.

---

## Config

- **Keywords / date:** `config/hiring_cafe.json`  
  - `search_keywords`: list of search terms (e.g. `["AI+Engineer", "ML+Engineer"]`)  
  - `date_fetched_past_n_days`: `2` = 24h, `4` = 3d, `14` = 1w, `21` = 2w, `-1` = all  
- Step 1 can override date with `--date-filter today|24h|3d|1w|2w|all`.
