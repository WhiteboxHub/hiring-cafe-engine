
import json
import os
import sys
import time
import re
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from core.logger import logger
from core.auth_service import auth_service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc


# ── URL sanitizer ─────────────────────────────────────────────────────────────

def _sanitize_url(url: str | None) -> str | None:
    """
    Fix corrupted URLs like 'https://sjotps://sjobs.brassring.com/...'
    and reject anything that doesn't look like a real HTTP URL.
    """
    if not url:
        return None
    url = url.strip()

    # Fix double-protocol corruption: https://sjotps://real.domain -> https://real.domain
    url = re.sub(r'^https?://[a-zA-Z]{2,10}://', 'https://', url)

    # Must start with http
    if not url.startswith('http'):
        return None

    # Must have a dot in the netloc (real domain)
    try:
        parsed = urlparse(url)
        if '.' not in parsed.netloc or not parsed.netloc:
            return None
    except Exception:
        return None

    return url


# ── Junk detection (unchanged from your original) ────────────────────────────

_SALARY_RE = re.compile(
    r'\$\d+[kK]?[\-–]\$?\d+[kK]?'
    r'|\$\d+[kK]?/\w+'
    r'|\d+[kK]\s*/\s*(?:yr|mo|year|hr)',
    re.IGNORECASE,
)
_JUNK_PREFIXES_RE = re.compile(
    r'^(?:\$\d|NYSE:|NASDAQ:|Euronext|\d+\+?\s*YOE|:)',
    re.IGNORECASE,
)
_JOB_TYPE_RE = re.compile(
    r'^(?:full[\s\-]time|contract|part[\s\-]time|internship|temporary)$',
    re.IGNORECASE,
)
_WORK_MODE_RE = re.compile(r'^(?:onsite|remote|hybrid)$', re.IGNORECASE)


def _is_junk_company(name: str) -> bool:
    if not name or not name.strip():
        return True
    s = name.strip()
    if _SALARY_RE.search(s): return True
    if _JUNK_PREFIXES_RE.search(s): return True
    if _JOB_TYPE_RE.match(s): return True
    if _WORK_MODE_RE.match(s): return True
    if _is_multi_city_line(s): return True
    return False


def _is_multi_city_line(text: str) -> bool:
    if not text:
        return False
    parts = re.split(r'\s+or\s+', text.strip(), flags=re.IGNORECASE)
    if len(parts) < 2:
        return False
    return all(':' not in p and len(p.split()) <= 5 for p in parts)


def _clean_company_name(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith(':'):
        return ""
    name = s.split(':')[0].strip().rstrip('.,;-').strip()
    return name


def _extract_company_from_url(url: str) -> str | None:
    if not url:
        return None
    u = url.lower()
    patterns = [
        (r'https?://([a-z0-9-]+)\.(?:wd\d+\.)?myworkdayjobs\.com', 1),
        (r'https?://(?:boards|job-boards)\.greenhouse\.io/([a-z0-9%_-]+)', 1),
        (r'https?://jobs\.ashbyhq\.com/([a-z0-9%_\s-]+)', 1),
        (r'https?://jobs\.smartrecruiters\.com/([a-z0-9-]+)', 1),
        (r'https?://(?:careers-)?([a-z0-9-]+)\.icims\.com', 1),
        (r'https?://jobs\.jobvite\.com/([a-z0-9-]+)', 1),
        (r'https?://ats\.rippling\.com/([a-z0-9-]+)', 1),
        (r'https?://(?:tas-)?([a-z0-9-]+)\.taleo\.net', 1),
        (r'https?://([a-z0-9-]+)\.bamboohr\.com', 1),
        (r'https?://([a-z0-9-]+)\.recruitee\.com', 1),
        (r'https?://([a-z0-9-]+)\.teamtailor\.com', 1),
    ]
    for pattern, group in patterns:
        m = re.search(pattern, u)
        if m:
            from urllib.parse import unquote
            slug = unquote(m.group(group).split('/')[0])
            return slug.replace('-', ' ').replace('_', ' ').title()
    return None


def _resolve_company_name(job: dict) -> str:
    ats_url = job.get('ats_url') or ''
    raw = job.get('company') or ''
    cleaned = _clean_company_name(raw)
    if cleaned and not _is_junk_company(cleaned):
        return cleaned
    url_company = _extract_company_from_url(ats_url)
    if url_company and not _is_junk_company(url_company):
        return url_company
    desc = job.get('company_description') or ''
    if ':' in desc:
        before = desc.split(':')[0].strip()
        if before and len(before) > 1 and not _is_junk_company(before):
            return before
    return "Unknown Company"


def _normalize_employment_mode(raw: str) -> str:
    if not raw:
        return 'onsite'
    r = raw.strip().lower()
    if 'remote' in r: return 'remote'
    if 'hybrid' in r: return 'hybrid'
    return 'onsite'


def _normalize_position_type(raw: str) -> str:
    if not raw:
        return 'full_time'
    r = raw.strip().lower()
    if 'contract' in r: return 'contract'
    if 'intern' in r: return 'internship'
    if 'part' in r: return 'part_time'
    return 'full_time'


_TECH_FRAGMENT_RE = re.compile(
    r'^(?:python|c\+\+|cuda|typescript|golang|java|kotlin|swift|terraform|'
    r'ansible|docker|kubernetes|genai|aws|gcp|azure|react|node|javascript|'
    r'pytorch|tensorflow|scikit|openai|langchain|github|ci/cd|linux)$',
    re.IGNORECASE,
)


def _sanitize_geo(value: str | None) -> str | None:
    if not value:
        return None
    if _TECH_FRAGMENT_RE.match(value.strip()):
        return None
    if len(value) > 60:
        return None
    return value


# ── Workable browser extraction (unchanged) ───────────────────────────────────

def get_driver():
    options = uc.ChromeOptions()
    if os.getenv("HEADLESS", "false").lower() == "true":
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    return uc.Chrome(options=options)


def extract_workable_details(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        details = {}
        try: details['title'] = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except: details['title'] = None
        try: details['company_name'] = driver.find_element(By.CSS_SELECTOR, "[class*='styles--3CvIg'] span").text.strip()
        except: details['company_name'] = None
        try: details['location'] = driver.find_element(By.CSS_SELECTOR, "[class*='styles--11q6G'] span").text.strip()
        except: details['location'] = None
        try:
            meta = driver.find_element(By.CSS_SELECTOR, "[class*='styles--1HMvu']").text.lower()
            details['position_type'] = 'contract' if 'contract' in meta else 'internship' if 'intern' in meta else 'full_time'
        except: details['position_type'] = 'full_time'
        try:
            wm = driver.find_element(By.CSS_SELECTOR, "[class*='styles--QTMDv']").text.lower()
            details['employment_mode'] = 'remote' if 'remote' in wm else 'hybrid' if 'hybrid' in wm else 'onsite'
        except: details['employment_mode'] = 'onsite'
        try: details['description'] = driver.find_element(By.CSS_SELECTOR, "section[class*='styles--3vx-H']").text.strip()
        except: details['description'] = None
        return details
    except Exception as e:
        logger.debug(f"Error extracting Workable details from {url}: {e}")
        return None


# ── Job listing builder ───────────────────────────────────────────────────────

def _build_job_listing(job: dict, platform: str, driver=None) -> dict | None:
    """
    Build and validate a job listing dict ready for the API.
    Returns None if the job should be skipped (e.g. no ats_url or no valid URL).

    RULE: Only inject jobs that have a valid ats_url.
    Jobs with ats_url = null are skipped — they have no confirmed external
    application link and should not be sent to the API.
    """
    job_id  = job.get('job_id')

    # ── Require a non-null ats_url — skip anything without one ───────────────
    raw_ats_url = job.get('ats_url')
    if not raw_ats_url:
        logger.info(f"Skipping job {job_id}: ats_url is null — no external ATS link found")
        return None

    ats_url = _sanitize_url(raw_ats_url)
    if not ats_url:
        logger.warning(f"Skipping job {job_id}: ats_url '{raw_ats_url}' failed URL sanitization")
        return None

    hiring_cafe_url = _sanitize_url(job.get('hiring_cafe_url'))
    job_url = ats_url  # Always use ats_url — hiring_cafe_url is never the apply target

    company_name    = _resolve_company_name(job)
    title           = (job.get('job_tittle') or job.get('title') or 'Unknown Title')[:255]
    location        = job.get('location')
    city            = _sanitize_geo(job.get('city'))
    state           = _sanitize_geo(job.get('state'))
    country         = _sanitize_geo(job.get('country'))
    employment_mode = _normalize_employment_mode(job.get('type', ''))
    position_type   = _normalize_position_type(job.get('position_type') or job.get('type') or '')
    description     = (job.get('company_description') or '')[:2000] or None  # truncate long text

    # Workable: enrich from live page
    if ats_url and platform == 'workable' and driver:
        try:
            details = extract_workable_details(driver, ats_url)
            if details:
                if details.get('title'):        title           = details['title'][:255]
                if details.get('company_name') and not _is_junk_company(details['company_name']):
                                                company_name    = details['company_name']
                if details.get('location'):     location        = details['location']
                if details.get('employment_mode'): employment_mode = details['employment_mode']
                if details.get('position_type'):   position_type   = details['position_type']
                if details.get('description'):  description     = details['description'][:2000]
        except Exception as e:
            logger.warning(f"Workable details failed for {job_id}: {e}")

    def _lower(v):
        return v.lower() if v else v

    return {
        "title":           _lower(title),
        "company_name":    _lower(company_name),
        "location":        _lower(location),
        "city":            _lower(city),
        "state":           _lower(state),
        "country":         _lower(country),
        "position_type":   position_type,
        "employment_mode": employment_mode,
        "source":          "hiring.cafe",
        "source_uid":      job_id,
        "job_url":         job_url,
        "description":     description,
        "status":          "open",
    }


# ── API ingestion ─────────────────────────────────────────────────────────────

def ingest_to_api(json_path, dry_run=False):
    if not os.path.exists(json_path):
        logger.error(f"File not found: {json_path}")
        return

    if not dry_run:
        token = auth_service.get_access_token()
        if not token:
            logger.error("Failed to obtain authentication token.")
            return

        api_base_url = auth_service.auth_url.replace('/login', '').replace('/api/login', '')
        if '/api' not in api_base_url:
            api_base_url += '/api'
        positions_url = f"{api_base_url}/positions/bulk"
    else:
        token = None
        positions_url = None

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    driver        = None
    total_sent    = 0
    total_failed  = 0
    batch_data    = []
    all_listings  = []  # For dry-run output

    try:
        by_ats = data.get('by_ats', {})
        for platform, jobs in by_ats.items():
            logger.info(f"Processing {len(jobs)} jobs for platform: {platform}")

            # Start Workable browser lazily (skip in dry-run)
            if platform == 'workable' and not driver and not dry_run:
                try:
                    driver = get_driver()
                except Exception as e:
                    logger.warning(f"Could not start browser for Workable: {e}")

            for job in jobs:
                listing = _build_job_listing(job, platform, driver)
                if listing is None:
                    total_failed += 1
                    continue
                batch_data.append(listing)
                all_listings.append(listing)

                # Send in smaller batches of 10 so one bad job doesn't kill all 34
                if len(batch_data) >= 10:
                    if dry_run:
                        logger.info(f"[DRY RUN] Would send batch of {len(batch_data)} jobs")
                        total_sent += len(batch_data)
                        batch_data = []
                    else:
                        ok = _send_batch(positions_url, token, batch_data)
                        total_sent  += len(batch_data) if ok else 0
                        total_failed += 0 if ok else len(batch_data)
                        batch_data = []

        # Final batch
        if batch_data:
            if dry_run:
                logger.info(f"[DRY RUN] Would send final batch of {len(batch_data)} jobs")
                total_sent += len(batch_data)
            else:
                ok = _send_batch(positions_url, token, batch_data)
                total_sent  += len(batch_data) if ok else 0
                total_failed += 0 if ok else len(batch_data)

        # Save dry-run payload
        if dry_run:
            dry_run_path = ROOT / "dry_run_payload.json"
            with open(dry_run_path, 'w', encoding='utf-8') as f:
                json.dump({"positions": all_listings}, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Dry-run payload saved to: {dry_run_path}")

    finally:
        if driver:
            try: driver.quit()
            except: pass

    if dry_run:
        logger.info(f"✅ DRY RUN COMPLETE - Would send {total_sent} jobs, {total_failed} failed validation")
    else:
        logger.info(f"Finished. Jobs sent successfully: {total_sent} | Failed: {total_failed}")


def _send_batch(url: str, token: str, batch: list) -> bool:
    """Send a batch to the API. Returns True on success, False on failure."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    try:
        response = requests.post(
            url,
            json={"positions": batch},
            headers=headers,
            timeout=30,
        )

        # ── Always log the raw response so we can diagnose failures ──────
        logger.info(f"API status: {response.status_code}")
        if not response.ok:
            logger.error(f"API error body: {response.text[:1000]}")
            logger.error(f"First job in failed batch: {json.dumps(batch[0], indent=2)}")
            return False

        res = response.json()
        logger.info(
            f"Batch success: {res.get('inserted', 0)} inserted, "
            f"{res.get('skipped', 0)} duplicates"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to send batch to API: {e}")
        if batch:
            logger.error(f"First job in failed batch: {json.dumps(batch[0], indent=2)}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Step 4: Ingest jobs to API"
    )
    parser.add_argument(
        "--input",
        default=str(ROOT / "hiring_cafe_by_ats.json"),
        help="Input file from Step 3"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process and validate data but skip API POST. Saves payload to dry_run_payload.json"
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No data will be sent to API")

    ingest_to_api(args.input, dry_run=args.dry_run)