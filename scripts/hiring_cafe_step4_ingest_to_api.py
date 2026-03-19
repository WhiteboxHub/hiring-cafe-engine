# import json
# import os
# import sys
# import time
# import re
# import requests
# from datetime import datetime
# from pathlib import Path

# # Add project root to sys.path
# ROOT = Path(__file__).resolve().parent.parent
# sys.path.append(str(ROOT))

# from core.logger import logger
# from core.auth_service import auth_service
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException, NoSuchElementException
# import undetected_chromedriver as uc

# def get_driver():
#     """Initialize undetected chromedriver."""
#     options = uc.ChromeOptions()
#     if os.getenv("HEADLESS", "false").lower() == "true":
#         options.add_argument("--headless")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     driver = uc.Chrome(options=options)
#     return driver

# def extract_workable_details(driver, url):
#     """Extract job details from a Workable application page."""
#     try:
#         driver.get(url)
#         wait = WebDriverWait(driver, 10)
#         wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        
#         details = {}
#         try:
#             details['title'] = driver.find_element(By.TAG_NAME, "h1").text.strip()
#         except:
#             details['title'] = None
#         try:
#             details['company_name'] = driver.find_element(By.CSS_SELECTOR, "[class*='styles--3CvIg'] span").text.strip()
#         except:
#             details['company_name'] = None
#         try:
#             details['location'] = driver.find_element(By.CSS_SELECTOR, "[class*='styles--11q6G'] span").text.strip()
#         except:
#             details['location'] = None
#         try:
#             meta_text = driver.find_element(By.CSS_SELECTOR, "[class*='styles--1HMvu']").text.lower()
#             if 'full time' in meta_text or 'full-time' in meta_text:
#                 details['position_type'] = 'full_time'
#             elif 'contract' in meta_text:
#                 details['position_type'] = 'contract'
#             elif 'intern' in meta_text:
#                 details['position_type'] = 'internship'
#             else:
#                 details['position_type'] = 'full_time'
#         except:
#             details['position_type'] = 'full_time'
#         try:
#             work_mode_text = driver.find_element(By.CSS_SELECTOR, "[class*='styles--QTMDv']").text.lower()
#             if 'remote' in work_mode_text:
#                 details['employment_mode'] = 'remote'
#             elif 'hybrid' in work_mode_text:
#                 details['employment_mode'] = 'hybrid'
#             else:
#                 details['employment_mode'] = 'onsite'
#         except:
#             details['employment_mode'] = 'onsite'
#         try:
#             details['description'] = driver.find_element(By.CSS_SELECTOR, "section[class*='styles--3vx-H']").text.strip()
#         except:
#             details['description'] = None
#         return details
#     except Exception as e:
#         logger.debug(f"Error extracting Workable details from {url}: {e}")
#         return None

# def _clean_company_name(raw: str) -> str:
#     """
#     Extract just the company name, stripping any description after a colon.
#     e.g. "HERE Technologies: Provides digital mapping..." -> "HERE Technologies"
#     e.g. "Google" -> "Google"
#     """
#     if not raw:
#         return raw
#     # Split on first colon and take only the part before it
#     name = raw.split(':')[0].strip()
#     # Also strip any trailing punctuation
#     name = name.rstrip('.,;-').strip()
#     return name or raw


# def _normalize_employment_mode(raw: str) -> str:
#     """Normalize employment mode to lowercase API values."""
#     if not raw:
#         return 'onsite'
#     r = raw.strip().lower()
#     if 'remote' in r:
#         return 'remote'
#     elif 'hybrid' in r:
#         return 'hybrid'
#     else:
#         return 'onsite'


# def _normalize_position_type(raw: str) -> str:
#     """Normalize position type to lowercase API values."""
#     if not raw:
#         return 'full_time'
#     r = raw.strip().lower()
#     if 'contract' in r:
#         return 'contract'
#     elif 'intern' in r:
#         return 'internship'
#     elif 'part' in r:
#         return 'part_time'
#     else:
#         return 'full_time'


# def parse_hiring_cafe_title(raw_title):
#     lines = [l.strip() for l in raw_title.split('\n') if l.strip()]
#     data = {
#         'title': None, 'location': None, 'employment_mode': 'onsite',
#         'position_type': 'full_time', 'company_name': None
#     }
#     if not lines: return data
#     # Skip the first line if it is a time-elapsed token (e.g. "15h", "2d", "1w", "3m")
#     # OR a UI button label that sometimes gets scraped into the card text (e.g. "Save").
#     _NON_TITLE_PREFIXES = {'save', 'bookmark', 'apply', 'saved', 'shortlist'}
#     start_idx = 1 if (
#         re.match(r'^\d+[hdmw]$', lines[0])
#         or lines[0].strip().lower() in _NON_TITLE_PREFIXES
#     ) else 0
#     if len(lines) > start_idx: data['title'] = lines[start_idx]
#     for line in lines[start_idx+1:]:
#         if ',' in line or any(c in line for c in ['India', 'USA', 'United States', 'Remote']):
#             if 'Remote' in line: data['employment_mode'] = 'remote'
#             if not data['location']: data['location'] = line
#         if 'Remote' in line.lower(): data['employment_mode'] = 'remote'
#         elif 'Hybrid' in line.lower(): data['employment_mode'] = 'hybrid'
#         if 'Full Time' in line or 'Full-time' in line: data['position_type'] = 'full_time'
#         elif 'Contract' in line: data['position_type'] = 'contract'
#         elif 'Intern' in line: data['position_type'] = 'internship'
#         if ':' in line and not data['company_name']:
#             # Only take the part before the colon as the company name
#             data['company_name'] = _clean_company_name(line)
#     return data

# def ingest_to_api(json_path):
#     """Process job data and send it to the backend API."""
#     if not os.path.exists(json_path):
#         logger.error(f"File not found: {json_path}")
#         return

#     # Get authentication token
#     token = auth_service.get_access_token()
#     if not token:
#         logger.error("Failed to obtain authentication token. Check .env AUTH settings.")
#         return

#     # Base URL for API calls
#     # Usually the login URL minus the '/login' part
#     api_base_url = auth_service.auth_url.replace('/login', '').replace('/api/login', '')
#     if '/api' not in api_base_url:
#         api_base_url += '/api'
    
#     positions_url = f"{api_base_url}/positions/bulk"

#     with open(json_path, 'r', encoding='utf-8') as f:
#         data = json.load(f)

#     driver = None
#     processed_count = 0
#     batch_data = []
    
#     try:
#         by_ats = data.get('by_ats', {})
#         for platform, jobs in by_ats.items():
#             logger.info(f"Processing {len(jobs)} jobs for platform: {platform}")
            
#             for job in jobs:
#                 job_id = job.get('job_id')
#                 ats_url = job.get('ats_url')
#                 raw_title = job.get('title', '')
                
#                 # Use enriched info if available, otherwise fallback to legacy parser
#                 job_tittle = job.get('job_tittle')
#                 comapany_name = job.get('comapany')
#                 enriched_location = job.get('location')
#                 enriched_type = job.get('type', '').lower()
                
#                 parsed_info = parse_hiring_cafe_title(raw_title)
                
#                 # Prioritize enriched fields, with cleaning applied
#                 if job_tittle:
#                     parsed_info['title'] = job_tittle
#                 if comapany_name:
#                     # Strip description after colon: "HERE Technologies: Provides..." -> "HERE Technologies"
#                     parsed_info['company_name'] = _clean_company_name(comapany_name)
#                 if enriched_location:
#                     parsed_info['location'] = enriched_location
#                 # Normalize to lowercase API values (Onsite->onsite, Remote->remote, Hybrid->hybrid)
#                 if enriched_type:
#                     parsed_info['employment_mode'] = _normalize_employment_mode(enriched_type)
                
#                 if ats_url and platform == 'workable':
#                     try:
#                         if not driver:
#                             driver = get_driver()
#                         details = extract_workable_details(driver, ats_url)
#                         if details:
#                             parsed_info.update({k: v for k, v in details.items() if v})
#                     except Exception as e:
#                         logger.warning(f"⚠️ Could not extract workable details for {job_id} due to browser error: {e}")
                
#                 # Construct job listing object for API
#                 # Lowercase all human-readable fields to match LinkedIn data format
#                 _title = (parsed_info.get('title') or job.get('title', 'Unknown Title'))[:255]
#                 _company = parsed_info.get('company_name') or "Unknown Company"
#                 _location = parsed_info.get('location')
#                 _city = job.get('city')
#                 _state = job.get('state')
#                 _country = job.get('country')
#                 job_listing = {
#                     "title": _title.lower() if _title else _title,
#                     "company_name": _company.lower() if _company else _company,
#                     "location": _location.lower() if _location else _location,
#                     "city": _city.lower() if _city else _city,
#                     "state": _state.lower() if _state else _state,
#                     "country": _country.lower() if _country else _country,
#                     "position_type": parsed_info.get('position_type', 'full_time'),
#                     "employment_mode": parsed_info.get('employment_mode', 'onsite'),
#                     "source": "hiring.cafe",
#                     "source_uid": job_id,
#                     "job_url": ats_url or job.get('hiring_cafe_url'),
#                     "description": job.get('company_description') or parsed_info.get('description'),
#                     "status": "open"
#                 }
#                 batch_data.append(job_listing)
                
#                 # Send in batches of 50
#                 if len(batch_data) >= 50:
#                     _send_batch(positions_url, token, batch_data)
#                     processed_count += len(batch_data)
#                     batch_data = []

#         # Final batch
#         if batch_data:
#             _send_batch(positions_url, token, batch_data)
#             processed_count += len(batch_data)

#     finally:
#         if driver:
#             driver.quit()
    
#     logger.info(f"Finished processing. Total jobs sent to API: {processed_count}")

# def _send_batch(url, token, batch):
#     """Helper to send a batch of positions to the API."""
#     headers = {
#         "Authorization": f"Bearer {token}",
#         "Content-Type": "application/json"
#     }
#     payload = {"positions": batch}
#     try:
#         response = requests.post(url, json=payload, headers=headers, timeout=30)
#         response.raise_for_status()
#         res_data = response.json()
#         logger.info(f"Batch success: {res_data.get('inserted', 0)} inserted, {res_data.get('skipped', 0)} duplicates")
#     except Exception as e:
#         logger.error(f"Failed to send batch to API: {e}")

# if __name__ == "__main__":
#     import argparse
#     parser = argparse.ArgumentParser(description="Ingest grouped job data into the website API.")
#     parser.add_argument("--input", help="Path to the by_ats JSON file", 
#                        default=str(ROOT / "hiring_cafe_by_ats.json"))
#     args = parser.parse_args()
    
#     ingest_to_api(args.input)



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
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc


# ---------------------------------------------------------------------------
# Junk-value detection — things that are NEVER a company name
# ---------------------------------------------------------------------------

_SALARY_RE = re.compile(
    r'\$\d+[kK]?[\-–]\$?\d+[kK]?'       # $100k-$200k
    r'|\$\d+[kK]?/\w+'                   # $100k/yr
    r'|\d+[kK]\s*/\s*(?:yr|mo|year|hr)',  # 100k/yr
    re.IGNORECASE,
)

_JUNK_PREFIXES_RE = re.compile(
    r'^(?:\$\d'                           # salary starting with $
    r'|NYSE:'                             # stock ticker
    r'|NASDAQ:'
    r'|Euronext'
    r'|\d+\+?\s*YOE'                      # "5+ YOE..."
    r'|:)',                               # bare description fragment
    re.IGNORECASE,
)

# "Full Time", "Full-time", "Contract", "Part Time", "Internship"
_JOB_TYPE_RE = re.compile(
    r'^(?:full[\s\-]time|contract|part[\s\-]time|internship|temporary)$',
    re.IGNORECASE,
)

# "Onsite", "Remote", "Hybrid"
_WORK_MODE_RE = re.compile(r'^(?:onsite|remote|hybrid)$', re.IGNORECASE)


def _is_junk_company(name: str) -> bool:
    """Return True if name is definitely not a real company name."""
    if not name or not name.strip():
        return True
    s = name.strip()
    if _SALARY_RE.search(s):
        return True
    if _JUNK_PREFIXES_RE.search(s):
        return True
    if _JOB_TYPE_RE.match(s):          # ← THIS catches "Full Time" as company
        return True
    if _WORK_MODE_RE.match(s):         # catches "Remote", "Onsite", "Hybrid"
        return True
    if _is_multi_city_line(s):
        return True
    return False


def _is_multi_city_line(text: str) -> bool:
    """'Dublin or Charlotte', 'Boston or Raleigh' etc. — not a company."""
    if not text:
        return False
    parts = re.split(r'\s+or\s+', text.strip(), flags=re.IGNORECASE)
    if len(parts) < 2:
        return False
    return all(':' not in p and len(p.split()) <= 5 for p in parts)


def _clean_company_name(raw: str) -> str:
    """Strip description fragment after first colon, trim punctuation."""
    if not raw:
        return ""
    s = raw.strip()
    if s.startswith(':'):
        return ""
    name = s.split(':')[0].strip().rstrip('.,;-').strip()
    return name


# ---------------------------------------------------------------------------
# ATS URL → company name extractor
# ---------------------------------------------------------------------------

def _extract_company_from_url(url: str) -> str | None:
    """
    Extract a human-readable company slug from known ATS URL patterns.
    Returns Title-cased name or None.
    """
    if not url:
        return None
    u = url.lower()

    # Workday: company.wd5.myworkdayjobs.com  or  company.myworkdayjobs.com
    m = re.search(r'https?://([a-z0-9-]+)\.(?:wd\d+\.)?myworkdayjobs\.com', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # Lever: jobs.lever.co/company  or  company.lever.co
    m = re.search(r'https?://(?:jobs\.lever\.co/([a-z0-9-]+)|([a-z0-9-]+)\.lever\.co)', u)
    if m:
        slug = (m.group(1) or m.group(2) or '').strip('/')
        if slug and slug != 'jobs':
            return slug.replace('-', ' ').title()

    # Greenhouse: boards.greenhouse.io/company  or  job-boards.greenhouse.io/company
    m = re.search(r'https?://(?:boards|job-boards)\.greenhouse\.io/([a-z0-9%_-]+)', u)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1).split('/')[0]).replace('-', ' ').replace('_', ' ').title()

    # Ashby: jobs.ashbyhq.com/company
    m = re.search(r'https?://jobs\.ashbyhq\.com/([a-z0-9%_\s-]+)', u)
    if m:
        from urllib.parse import unquote
        return unquote(m.group(1).split('/')[0]).replace('-', ' ').title()

    # SmartRecruiters: jobs.smartrecruiters.com/Company
    m = re.search(r'https?://jobs\.smartrecruiters\.com/([a-z0-9-]+)', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # iCIMS: careers-company.icims.com  or  company.icims.com
    m = re.search(r'https?://(?:careers-)?([a-z0-9-]+)\.icims\.com', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # Jobvite: jobs.jobvite.com/company
    m = re.search(r'https?://jobs\.jobvite\.com/([a-z0-9-]+)', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # Rippling: ats.rippling.com/company-slug
    m = re.search(r'https?://ats\.rippling\.com/([a-z0-9-]+)', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # Taleo: company.taleo.net  or  tas-company.taleo.net
    m = re.search(r'https?://(?:tas-)?([a-z0-9-]+)\.taleo\.net', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # BambooHR: company.bamboohr.com
    m = re.search(r'https?://([a-z0-9-]+)\.bamboohr\.com', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # Recruitee: company.recruitee.com
    m = re.search(r'https?://([a-z0-9-]+)\.recruitee\.com', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # Teamtailor: company.teamtailor.com
    m = re.search(r'https?://([a-z0-9-]+)\.teamtailor\.com', u)
    if m:
        return m.group(1).replace('-', ' ').title()

    # Paylocity / UltiPro / BrassRing / Oracle — no company slug in URL
    return None


# ---------------------------------------------------------------------------
# Main company resolver — priority chain
# ---------------------------------------------------------------------------

def _resolve_company_name(job: dict) -> str:
    """
    Priority chain:
      1. `comapany` field from JSON — only if it passes junk checks
      2. ATS URL slug extraction — most reliable for Workday/Lever/Greenhouse etc.
      3. First token of `company_description` before ':'
      4. "Unknown Company"
    """
    ats_url = job.get('ats_url') or ''

    # 1 — scraped company field
    raw = job.get('comapany') or ''
    cleaned = _clean_company_name(raw)
    if cleaned and not _is_junk_company(cleaned):
        return cleaned

    # 2 — extract from ATS URL
    url_company = _extract_company_from_url(ats_url)
    if url_company and not _is_junk_company(url_company):
        return url_company

    # 3 — description prefix
    desc = job.get('company_description') or ''
    if ':' in desc:
        before = desc.split(':')[0].strip()
        if before and len(before) > 1 and not _is_junk_company(before):
            return before

    return "Unknown Company"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_employment_mode(raw: str) -> str:
    if not raw:
        return 'onsite'
    r = raw.strip().lower()
    if 'remote' in r:
        return 'remote'
    if 'hybrid' in r:
        return 'hybrid'
    return 'onsite'


def _normalize_position_type(raw: str) -> str:
    if not raw:
        return 'full_time'
    r = raw.strip().lower()
    if 'contract' in r:
        return 'contract'
    if 'intern' in r:
        return 'internship'
    if 'part' in r:
        return 'part_time'
    return 'full_time'


# Tech-stack fragments that sometimes bleed into city/state/country fields
# when location parsing misidentifies a requirements line as a location.
_TECH_FRAGMENT_RE = re.compile(
    r'^(?:python|c\+\+|cuda|typescript|golang|java|kotlin|swift|terraform|'
    r'ansible|docker|kubernetes|genai|aws|gcp|azure|react|node|javascript|'
    r'pytorch|tensorflow|scikit|openai|langchain|github|ci/cd|linux)$',
    re.IGNORECASE,
)


def _sanitize_geo(value: str | None) -> str | None:
    """Return None if the value looks like a tech keyword rather than a place."""
    if not value:
        return None
    if _TECH_FRAGMENT_RE.match(value.strip()):
        return None
    # Also reject if it looks like a full sentence / requirements fragment
    if len(value) > 60:
        return None
    return value


# ---------------------------------------------------------------------------
# Workable detail extractor (browser)
# ---------------------------------------------------------------------------

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
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        details = {}
        try:
            details['title'] = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except Exception:
            details['title'] = None
        try:
            details['company_name'] = driver.find_element(
                By.CSS_SELECTOR, "[class*='styles--3CvIg'] span"
            ).text.strip()
        except Exception:
            details['company_name'] = None
        try:
            details['location'] = driver.find_element(
                By.CSS_SELECTOR, "[class*='styles--11q6G'] span"
            ).text.strip()
        except Exception:
            details['location'] = None
        try:
            meta = driver.find_element(By.CSS_SELECTOR, "[class*='styles--1HMvu']").text.lower()
            if 'full time' in meta or 'full-time' in meta:
                details['position_type'] = 'full_time'
            elif 'contract' in meta:
                details['position_type'] = 'contract'
            elif 'intern' in meta:
                details['position_type'] = 'internship'
            else:
                details['position_type'] = 'full_time'
        except Exception:
            details['position_type'] = 'full_time'
        try:
            wm = driver.find_element(By.CSS_SELECTOR, "[class*='styles--QTMDv']").text.lower()
            details['employment_mode'] = (
                'remote' if 'remote' in wm else 'hybrid' if 'hybrid' in wm else 'onsite'
            )
        except Exception:
            details['employment_mode'] = 'onsite'
        try:
            details['description'] = driver.find_element(
                By.CSS_SELECTOR, "section[class*='styles--3vx-H']"
            ).text.strip()
        except Exception:
            details['description'] = None
        return details
    except Exception as e:
        logger.debug(f"Error extracting Workable details from {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# API ingestion
# ---------------------------------------------------------------------------

def ingest_to_api(json_path):
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
                job_id   = job.get('job_id')
                ats_url  = job.get('ats_url')

                # ── Company: use robust resolver, never trust raw comapany blindly ──
                company_name = _resolve_company_name(job)

                # ── Title ─────────────────────────────────────────────────────
                title = (job.get('job_tittle') or job.get('title') or 'Unknown Title')[:255]

                # ── Location / geo ────────────────────────────────────────────
                location = job.get('location')
                city     = _sanitize_geo(job.get('city'))
                state    = _sanitize_geo(job.get('state'))
                country  = _sanitize_geo(job.get('country'))

                # ── Work mode & position type ──────────────────────────────────
                employment_mode = _normalize_employment_mode(job.get('type', ''))
                position_type   = _normalize_position_type(
                    job.get('position_type') or job.get('type') or ''
                )

                # ── Workable: enrich from live page ───────────────────────────
                if ats_url and platform == 'workable':
                    try:
                        if not driver:
                            driver = get_driver()
                        details = extract_workable_details(driver, ats_url)
                        if details:
                            if details.get('title'):
                                title = details['title'][:255]
                            if details.get('company_name') and not _is_junk_company(details['company_name']):
                                company_name = details['company_name']
                            if details.get('location'):
                                location = details['location']
                            if details.get('employment_mode'):
                                employment_mode = details['employment_mode']
                            if details.get('position_type'):
                                position_type = details['position_type']
                    except Exception as e:
                        logger.warning(f"⚠️ Workable details failed for {job_id}: {e}")

                job_listing = {
                    "title":           title.lower() if title else title,
                    "company_name":    company_name.lower() if company_name else company_name,
                    "location":        location.lower() if location else location,
                    "city":            city.lower() if city else city,
                    "state":           state.lower() if state else state,
                    "country":         country.lower() if country else country,
                    "position_type":   position_type,
                    "employment_mode": employment_mode,
                    "source":          "hiring.cafe",
                    "source_uid":      job_id,
                    "job_url":         ats_url or job.get('hiring_cafe_url'),
                    "description":     job.get('company_description'),
                    "status":          "open",
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

    logger.info(f"Finished. Total jobs sent to API: {processed_count}")


def _send_batch(url, token, batch):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        response = requests.post(url, json={"positions": batch}, headers=headers, timeout=30)
        response.raise_for_status()
        res = response.json()
        logger.info(
            f"Batch success: {res.get('inserted', 0)} inserted, "
            f"{res.get('skipped', 0)} duplicates"
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
