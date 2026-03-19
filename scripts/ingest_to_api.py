import json
import os
import sys
import time
import re
import requests
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from core.logger import logger
from core.auth_service import auth_service
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc

def get_driver():
    """Initialize undetected chromedriver."""
    options = uc.ChromeOptions()
    if os.getenv("HEADLESS", "false").lower() == "true":
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = uc.Chrome(options=options)
    return driver

def extract_workable_details(driver, url):
    """Extract job details from a Workable application page."""
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        
        details = {}
        try:
            details['title'] = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except:
            details['title'] = None
        try:
            details['company_name'] = driver.find_element(By.CSS_SELECTOR, "[class*='styles--3CvIg'] span").text.strip()
        except:
            details['company_name'] = None
        try:
            details['location'] = driver.find_element(By.CSS_SELECTOR, "[class*='styles--11q6G'] span").text.strip()
        except:
            details['location'] = None
        try:
            meta_text = driver.find_element(By.CSS_SELECTOR, "[class*='styles--1HMvu']").text.lower()
            if 'full time' in meta_text or 'full-time' in meta_text:
                details['position_type'] = 'full_time'
            elif 'contract' in meta_text:
                details['position_type'] = 'contract'
            elif 'intern' in meta_text:
                details['position_type'] = 'internship'
            else:
                details['position_type'] = 'full_time'
        except:
            details['position_type'] = 'full_time'
        try:
            work_mode_text = driver.find_element(By.CSS_SELECTOR, "[class*='styles--QTMDv']").text.lower()
            if 'remote' in work_mode_text:
                details['employment_mode'] = 'remote'
            elif 'hybrid' in work_mode_text:
                details['employment_mode'] = 'hybrid'
            else:
                details['employment_mode'] = 'onsite'
        except:
            details['employment_mode'] = 'onsite'
        try:
            details['description'] = driver.find_element(By.CSS_SELECTOR, "section[class*='styles--3vx-H']").text.strip()
        except:
            details['description'] = None
        return details
    except Exception as e:
        logger.debug(f"Error extracting Workable details from {url}: {e}")
        return None


def _is_salary_line(text: str) -> bool:
    """Return True if text looks like a salary/compensation string."""
    if not text:
        return False
    return bool(re.search(
        r'\$\d+[kK]?[\-–]\$?\d+[kK]?'   # $100k-$200k or $100k–200k
        r'|\$\d+[kK]?/\w+'               # $100k/yr
        r'|\$\d+[kK]?\s*(?:per|a)\s+\w+' # $100k per year
        r'|\d+[kK]\s*/\s*(?:yr|mo|month|year|hr|hour)',  # 100k/yr
        text,
        re.IGNORECASE,
    ))


def _is_multi_city_line(text: str) -> bool:
    """
    Return True if text looks like 'City A or City B' — a multi-location
    string that Hiring Cafe uses when a job has multiple office options.
    These are NOT company names.
    """
    if not text:
        return False
    # Pattern: two or more words joined by ' or ' where each segment looks like
    # a place name (Title Case, no punctuation typical of company descriptions)
    parts = re.split(r'\s+or\s+', text.strip(), flags=re.IGNORECASE)
    if len(parts) < 2:
        return False
    # Each part should be short (city/state names are rarely > 4 words)
    # and not contain colons or sentence-like punctuation
    for p in parts:
        if ':' in p or len(p.split()) > 5:
            return False
    return True


def _extract_company_from_url(url: str) -> str | None:
    """
    Extract a human-readable company name from known ATS URL patterns.

    Covers: Workday, Lever, Greenhouse (boards + job-boards),
            Ashby, SmartRecruiters, iCIMS, Jobvite, Rippling,
            Taleo, Paylocity, UltiPro/UKG, BrassRing, BambooHR,
            Recruitee, Teamtailor, Oracle HCM.

    Returns the extracted name with hyphens replaced by spaces, or None.
    """
    if not url or not isinstance(url, str):
        return None

    url_lower = url.lower()

    # ── Workday ──────────────────────────────────────────────────────────────
    # company.wd5.myworkdayjobs.com  or  company.myworkdayjobs.com
    m = re.search(
        r'https?://(?:www\.)?([a-z0-9-]+)\.(?:wd\d+\.)?myworkdayjobs\.com',
        url_lower,
    )
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── Lever ─────────────────────────────────────────────────────────────────
    # jobs.lever.co/company-name  or  company.lever.co/...
    m = re.search(
        r'https?://(?:jobs\.lever\.co/([a-z0-9][a-z0-9-]*)'
        r'|([a-z0-9][a-z0-9-]*)\.lever\.co)',
        url_lower,
    )
    if m:
        slug = (m.group(1) or m.group(2) or '').strip('/')
        if slug and slug != 'jobs':
            return slug.replace('-', ' ').title()

    # ── Greenhouse (boards + job-boards) ─────────────────────────────────────
    m = re.search(
        r'https?://(?:boards|job-boards)\.greenhouse\.io/([a-z0-9%][a-z0-9%_-]*)',
        url_lower,
    )
    if m:
        slug = m.group(1).split('/')[0]
        # URL-decode percent-encoded slugs (e.g. %20 -> space)
        from urllib.parse import unquote
        slug = unquote(slug)
        return slug.replace('-', ' ').replace('_', ' ').title()

    # ── Ashby ─────────────────────────────────────────────────────────────────
    # jobs.ashbyhq.com/company-name  (slug may be URL-encoded)
    m = re.search(r'https?://jobs\.ashbyhq\.com/([a-z0-9%][a-z0-9%_\s-]*)', url_lower)
    if m:
        from urllib.parse import unquote
        slug = unquote(m.group(1).split('/')[0])
        return slug.replace('-', ' ').replace('%20', ' ').replace('_', ' ').title()

    # ── SmartRecruiters ───────────────────────────────────────────────────────
    # jobs.smartrecruiters.com/CompanyName/...
    m = re.search(r'https?://jobs\.smartrecruiters\.com/([a-z0-9][a-z0-9-]*)', url_lower)
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── iCIMS ─────────────────────────────────────────────────────────────────
    # careers-companyname.icims.com  or  company.icims.com
    m = re.search(r'https?://(?:careers-)?([a-z0-9][a-z0-9-]*)\.icims\.com', url_lower)
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── Jobvite ───────────────────────────────────────────────────────────────
    # jobs.jobvite.com/company/...
    m = re.search(r'https?://jobs\.jobvite\.com/([a-z0-9][a-z0-9-]*)', url_lower)
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── Rippling ──────────────────────────────────────────────────────────────
    # ats.rippling.com/company-slug/jobs/...
    m = re.search(r'https?://ats\.rippling\.com/([a-z0-9][a-z0-9-]*)', url_lower)
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── Taleo ─────────────────────────────────────────────────────────────────
    # company.taleo.net  or  tas-company.taleo.net
    m = re.search(r'https?://(?:tas-)?([a-z0-9][a-z0-9-]*)\.taleo\.net', url_lower)
    if m:
        slug = m.group(1)
        # Strip common prefixes like 'tas-', 'uhg', etc. — keep raw slug
        return slug.replace('-', ' ').title()

    # ── Paylocity ─────────────────────────────────────────────────────────────
    # recruiting.paylocity.com — no company in URL, skip
    # (company name must come from card text or fallback)

    # ── UltiPro / UKG ─────────────────────────────────────────────────────────
    # recruiting.ultipro.com/COMPANYCODE.../  — code not human-readable, skip

    # ── BrassRing ─────────────────────────────────────────────────────────────
    # sjobs.brassring.com — no slug, skip

    # ── BambooHR ──────────────────────────────────────────────────────────────
    # company.bamboohr.com
    m = re.search(r'https?://([a-z0-9][a-z0-9-]*)\.bamboohr\.com', url_lower)
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── Recruitee ─────────────────────────────────────────────────────────────
    # company.recruitee.com
    m = re.search(r'https?://([a-z0-9][a-z0-9-]*)\.recruitee\.com', url_lower)
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── Teamtailor ────────────────────────────────────────────────────────────
    # company.teamtailor.com
    m = re.search(r'https?://([a-z0-9][a-z0-9-]*)\.teamtailor\.com', url_lower)
    if m:
        return m.group(1).replace('-', ' ').title()

    # ── Oracle HCM ────────────────────────────────────────────────────────────
    # hcgn.fa.us2.oraclecloud.com — no company slug, skip

    # ── ADP ───────────────────────────────────────────────────────────────────
    # workforcenow.adp.com — no company slug in URL, skip

    return None


# Known junk values that should never appear as a company name.
# These are patterns produced by the Hiring Cafe card-text parser when it
# mistakes another field (salary, stock ticker, multi-city label, etc.) for
# the company name.
_JUNK_COMPANY_PATTERNS = [
    re.compile(r'^\$\d', re.IGNORECASE),          # salary: "$184k-$288k/yr"
    re.compile(r'\$\d+[kK]'),                      # any salary mention
    re.compile(r'^NYSE:', re.IGNORECASE),           # stock ticker line
    re.compile(r'^NASDAQ:', re.IGNORECASE),
    re.compile(r'^Euronext', re.IGNORECASE),
    re.compile(r'^\d+[kK]?\s*/\s*(yr|mo|month)', re.IGNORECASE),  # "100k/yr"
    re.compile(r'^\d+\+\s*YOE', re.IGNORECASE),   # "5+ YOE..."
    re.compile(r'^:'),                              # bare description fragment
]


def _is_junk_company(name: str) -> bool:
    """Return True if `name` looks like a mis-parsed non-company value."""
    if not name or not name.strip():
        return True
    s = name.strip()
    if _is_salary_line(s):
        return True
    if _is_multi_city_line(s):
        return True
    for pat in _JUNK_COMPANY_PATTERNS:
        if pat.search(s):
            return True
    return False


def _clean_company_name(raw: str) -> str:
    """
    Strip trailing description / punctuation from a company name.
    e.g. "HERE Technologies: Provides digital mapping..." -> "HERE Technologies"
    e.g. ": designs graphics pr..."                      -> ""  (empty → junk)
    """
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith(':'):
        return ""
    name = s.split(':')[0].strip().rstrip('.,;-').strip()
    return name


def _normalize_employment_mode(raw: str) -> str:
    """Normalize employment mode to lowercase API values."""
    if not raw:
        return 'onsite'
    r = raw.strip().lower()
    if 'remote' in r:
        return 'remote'
    elif 'hybrid' in r:
        return 'hybrid'
    return 'onsite'


def _normalize_position_type(raw: str) -> str:
    """Normalize position type to lowercase API values."""
    if not raw:
        return 'full_time'
    r = raw.strip().lower()
    if 'contract' in r:
        return 'contract'
    elif 'intern' in r:
        return 'internship'
    elif 'part' in r:
        return 'part_time'
    return 'full_time'


def _resolve_company_name(job: dict) -> str:
    """
    Best-effort company name resolution with a clear priority chain:

    1. JSON `comapany` field — if it passes junk checks after cleaning.
    2. ATS URL slug extraction  — reliable for most platforms.
    3. `company_description` prefix — first token before ':' when present.
    4. Fallback to "Unknown Company".

    This ensures that salary strings, multi-city labels, and description
    fragments scraped from Hiring Cafe card text never reach the database.
    """
    ats_url = job.get('ats_url') or ''

    # ── Priority 1: scraped company field (after cleaning) ────────────────────
    raw_company = job.get('comapany') or ''
    cleaned = _clean_company_name(raw_company)
    if cleaned and not _is_junk_company(cleaned):
        return cleaned

    # ── Priority 2: extract from ATS URL ─────────────────────────────────────
    url_company = _extract_company_from_url(ats_url)
    if url_company and not _is_junk_company(url_company):
        return url_company

    # ── Priority 3: first token of company_description ────────────────────────
    desc = job.get('company_description') or ''
    if desc and ':' in desc:
        before_colon = desc.split(':')[0].strip()
        if before_colon and len(before_colon) > 1 and not _is_junk_company(before_colon):
            return before_colon

    # ── Fallback ──────────────────────────────────────────────────────────────
    # Try parsing the raw `title` card text for a company-like line
    raw_title = job.get('title', '')
    parsed = parse_hiring_cafe_title(raw_title, ats_url=ats_url)
    if parsed.get('company_name') and not _is_junk_company(parsed['company_name']):
        return parsed['company_name']

    return "Unknown Company"


def parse_hiring_cafe_title(raw_title, ats_url=None):
    """
    Robust parsing of Hiring Cafe job title/card text.
    Identifies fields by content rather than line index.
    """
    lines = [l.strip() for l in raw_title.split('\n') if l.strip()]
    data = {
        'title': None, 'location': None, 'employment_mode': 'onsite',
        'position_type': 'full_time', 'company_name': None
    }
    if not lines:
        return data

    time_pattern = r'^\d+[hdmw]$|^\d+ months? ago$'
    _NON_TITLE_PREFIXES = {'save', 'bookmark', 'apply', 'saved', 'shortlist'}
    mode_keywords = {'onsite', 'remote', 'hybrid'}
    type_keywords = {'full time', 'contract', 'internship', 'part time'}
    location_signals = {
        'united states', 'usa', 'india', 'germany', 'france', 'spain',
        'italy', 'egypt', 'canada', 'uk', 'united kingdom', 'dublin',
        'charlotte', 'london', 'beavercreek', 'santa clara', 'mountain view',
        'san francisco', 'new york', 'sunnyvale', 'austin', 'seattle',
        'boston', 'raleigh', 'kansas city', 'indianapolis', 'dallas',
        'denver', 'chicago', 'atlanta',
    }

    filtered_lines = []
    for line in lines:
        ll = line.lower()
        if re.match(time_pattern, ll) or ll in _NON_TITLE_PREFIXES:
            continue
        if ll in mode_keywords:
            data['employment_mode'] = ll
        elif ll in type_keywords:
            data['position_type'] = _normalize_position_type(ll)
        else:
            filtered_lines.append(line)

    if not filtered_lines:
        return data

    # First remaining line is the job title
    data['title'] = filtered_lines[0]
    remaining = filtered_lines[1:]

    # Find location (line with comma or known location keyword)
    location_idx = -1
    for i, line in enumerate(remaining):
        ll = line.lower()
        if ',' in line or any(
            sig == ll or f' {sig}' in ll or f'{sig} ' in ll
            for sig in location_signals
        ):
            data['location'] = line
            location_idx = i
            if 'remote' in ll:
                data['employment_mode'] = 'remote'
            elif 'hybrid' in ll:
                data['employment_mode'] = 'hybrid'
            break

    # Find company — skip salary lines, multi-city lines, stock tickers, YOE lines
    description_keywords = {'provides', 'building', 'leading', 'global', 'designs', 'develops'}
    skip_patterns = ['NYSE:', 'NASDAQ:', 'YOE:', 'Euronext']

    for i, line in enumerate(remaining):
        if i == location_idx:
            continue
        if any(x in line for x in skip_patterns):
            continue
        if _is_salary_line(line):
            continue
        if _is_multi_city_line(line):
            continue

        if ':' in line:
            if line.strip().startswith(':'):
                continue
            name = _clean_company_name(line)
            if name and not _is_junk_company(name):
                data['company_name'] = name
                return data
            continue

        ll = line.lower()
        if any(x in ll for x in ['view all', 'job posting', 'see views', 'yoe']):
            continue
        if any(ll.startswith(kw) for kw in description_keywords):
            continue
        if len(line) < 2:
            continue

        if not _is_junk_company(line):
            data['company_name'] = line
            break

    # Fallback: extract from ATS URL
    if not data['company_name'] and ats_url:
        data['company_name'] = _extract_company_from_url(ats_url)

    return data


def ingest_to_api(json_path):
    """Process job data and send it to the backend API."""
    if not os.path.exists(json_path):
        logger.error(f"File not found: {json_path}")
        return

    token = auth_service.get_access_token()
    if not token:
        logger.error("Failed to obtain authentication token. Check .env AUTH settings.")
        return

    api_base_url = auth_service.auth_url.replace('/login', '').replace('/api/login', '')
    if '/api' not in api_base_url:
        api_base_url += '/api'

    positions_url = f"{api_base_url}/positions/bulk"

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    driver = None
    processed_count = 0
    batch_data = []

    try:
        by_ats = data.get('by_ats', {})
        for platform, jobs in by_ats.items():
            logger.info(f"Processing {len(jobs)} jobs for platform: {platform}")

            for job in jobs:
                job_id = job.get('job_id')
                ats_url = job.get('ats_url')
                raw_title = job.get('title', '')

                # Use enriched job_tittle if available, else fall back to card-text parse
                job_tittle = job.get('job_tittle')
                enriched_location = job.get('location')
                enriched_type = job.get('type', '').lower()

                parsed_info = parse_hiring_cafe_title(raw_title, ats_url=ats_url)

                if job_tittle:
                    parsed_info['title'] = job_tittle
                if enriched_location:
                    parsed_info['location'] = enriched_location
                if enriched_type:
                    parsed_info['employment_mode'] = _normalize_employment_mode(enriched_type)

                # ── Robust company resolution (replaces direct use of `comapany`) ──
                company_name = _resolve_company_name(job)

                if ats_url and platform == 'workable':
                    try:
                        if not driver:
                            driver = get_driver()
                        details = extract_workable_details(driver, ats_url)
                        if details:
                            parsed_info.update({k: v for k, v in details.items() if v})
                    except Exception as e:
                        logger.warning(f"⚠️ Could not extract workable details for {job_id}: {e}")

                _title = (parsed_info.get('title') or job.get('title', 'Unknown Title'))[:255]
                _location = parsed_info.get('location')
                _city = job.get('city')
                _state = job.get('state')
                _country = job.get('country')

                # Sanity-check city/state/country: if they look like tech stack
                # fragments (e.g. "Python", "C++") produced by bad location parsing,
                # clear them so we don't store garbage.
                _tech_fragment_pattern = re.compile(
                    r'^(?:python|c\+\+|cuda|typescript|golang|java|kotlin|swift|terraform|ansible|docker|kubernetes|genai|aws|gcp|azure|react|node)$',
                    re.IGNORECASE,
                )
                if _city and _tech_fragment_pattern.match(_city.strip()):
                    _city = None
                if _state and _tech_fragment_pattern.match(_state.strip()):
                    _state = None
                if _country and _tech_fragment_pattern.match(_country.strip()):
                    _country = None

                job_listing = {
                    "title": _title.lower() if _title else _title,
                    "company_name": company_name.lower() if company_name else company_name,
                    "location": _location.lower() if _location else _location,
                    "city": _city.lower() if _city else _city,
                    "state": _state.lower() if _state else _state,
                    "country": _country.lower() if _country else _country,
                    "position_type": parsed_info.get('position_type', 'full_time'),
                    "employment_mode": parsed_info.get('employment_mode', 'onsite'),
                    "source": "hiring.cafe",
                    "source_uid": job_id,
                    "job_url": ats_url or job.get('hiring_cafe_url'),
                    "description": job.get('company_description') or parsed_info.get('description'),
                    "status": "open",
                }
                batch_data.append(job_listing)

                if len(batch_data) >= 50:
                    _send_batch(positions_url, token, batch_data)
                    processed_count += len(batch_data)
                    batch_data = []

        if batch_data:
            _send_batch(positions_url, token, batch_data)
            processed_count += len(batch_data)

    finally:
        if driver:
            driver.quit()

    logger.info(f"Finished processing. Total jobs sent to API: {processed_count}")


def _send_batch(url, token, batch):
    """Helper to send a batch of positions to the API."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"positions": batch}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        res_data = response.json()
        logger.info(
            f"Batch success: {res_data.get('inserted', 0)} inserted, "
            f"{res_data.get('skipped', 0)} duplicates"
        )
    except Exception as e:
        logger.error(f"Failed to send batch to API: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest grouped job data into the website API.")
    parser.add_argument(
        "--input",
        help="Path to the by_ats JSON file",
        default=str(ROOT / "hiring_cafe_by_ats.json"),
    )
    args = parser.parse_args()
    ingest_to_api(args.input)
