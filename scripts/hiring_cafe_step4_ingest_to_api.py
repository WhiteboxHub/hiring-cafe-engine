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

# def parse_hiring_cafe_title(raw_title):
#     lines = [l.strip() for l in raw_title.split('\n') if l.strip()]
#     data = {
#         'title': None, 'location': None, 'employment_mode': 'onsite',
#         'position_type': 'full_time', 'company_name': None
#     }
#     if not lines: return data
#     start_idx = 1 if re.match(r'^\d+[hd]$', lines[0]) else 0
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
#             data['company_name'] = line.split(':')[0].strip()
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
                
#                 # Prioritize enriched fields
#                 if job_tittle: parsed_info['title'] = job_tittle
#                 if comapany_name: parsed_info['company_name'] = comapany_name
#                 if enriched_location: parsed_info['location'] = enriched_location
#                 if enriched_type in ['onsite', 'remote', 'hybrid']:
#                     parsed_info['employment_mode'] = enriched_type
                
#                 if ats_url and platform == 'workable':
#                     try:
#                         if not driver:
#                             driver = get_driver()
#                         details = extract_workable_details(driver, ats_url)
#                         if details:
#                             parsed_info.update({k: v for k, v in details.items() if v})
#                     except Exception as e:
#                         logger.warning(f"Could not extract workable details for {job_id} due to browser error: {e}")
                
#                 # Construct job listing object for API
#                 job_listing = {
#                     "title": parsed_info.get('title') or job.get('title', 'Unknown Title')[:255],
#                     "company_name": parsed_info.get('company_name') or "Unknown Company",
#                     "location": parsed_info.get('location'),
#                     "city": job.get('city'),
#                     "state": job.get('state'),
#                     "country": job.get('country'),
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
#         logger.info(f"🚀 Batch success: {res_data.get('inserted', 0)} inserted, {res_data.get('skipped', 0)} duplicates")
#     except Exception as e:
#         logger.error(f"Failed to send batch to API: {e}")

# if __name__ == "__main__":
#     import argparse
#     parser = argparse.ArgumentParser(description="Ingest grouped job data into the website API.")
#     parser.add_argument("--input", help="Path to the by_ats JSON file", 
#                        default=str(ROOT.parent / "hiring_cafe_by_ats.json"))
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

def _clean_company_name(raw: str) -> str:
    """
    Extract just the company name, stripping any description after a colon.
    e.g. "HERE Technologies: Provides digital mapping..." -> "HERE Technologies"
    e.g. "Google" -> "Google"
    """
    if not raw:
        return raw
    # Split on first colon and take only the part before it
    name = raw.split(':')[0].strip()
    # Also strip any trailing punctuation
    name = name.rstrip('.,;-').strip()
    return name or raw


def _normalize_employment_mode(raw: str) -> str:
    """Normalize employment mode to lowercase API values."""
    if not raw:
        return 'onsite'
    r = raw.strip().lower()
    if 'remote' in r:
        return 'remote'
    elif 'hybrid' in r:
        return 'hybrid'
    else:
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
    else:
        return 'full_time'


def parse_hiring_cafe_title(raw_title):
    lines = [l.strip() for l in raw_title.split('\n') if l.strip()]
    data = {
        'title': None, 'location': None, 'employment_mode': 'onsite',
        'position_type': 'full_time', 'company_name': None
    }
    if not lines: return data
    start_idx = 1 if re.match(r'^\d+[hd]$', lines[0]) else 0
    if len(lines) > start_idx: data['title'] = lines[start_idx]
    for line in lines[start_idx+1:]:
        if ',' in line or any(c in line for c in ['India', 'USA', 'United States', 'Remote']):
            if 'Remote' in line: data['employment_mode'] = 'remote'
            if not data['location']: data['location'] = line
        if 'Remote' in line.lower(): data['employment_mode'] = 'remote'
        elif 'Hybrid' in line.lower(): data['employment_mode'] = 'hybrid'
        if 'Full Time' in line or 'Full-time' in line: data['position_type'] = 'full_time'
        elif 'Contract' in line: data['position_type'] = 'contract'
        elif 'Intern' in line: data['position_type'] = 'internship'
        if ':' in line and not data['company_name']:
            # Only take the part before the colon as the company name
            data['company_name'] = _clean_company_name(line)
    return data

def ingest_to_api(json_path):
    """Process job data and send it to the backend API."""
    if not os.path.exists(json_path):
        logger.error(f"File not found: {json_path}")
        return

    # Get authentication token
    token = auth_service.get_access_token()
    if not token:
        logger.error("Failed to obtain authentication token. Check .env AUTH settings.")
        return

    # Base URL for API calls
    # Usually the login URL minus the '/login' part
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
                
                # Use enriched info if available, otherwise fallback to legacy parser
                job_tittle = job.get('job_tittle')
                comapany_name = job.get('comapany')
                enriched_location = job.get('location')
                enriched_type = job.get('type', '').lower()
                
                parsed_info = parse_hiring_cafe_title(raw_title)
                
                # Prioritize enriched fields, with cleaning applied
                if job_tittle:
                    parsed_info['title'] = job_tittle
                if comapany_name:
                    # Strip description after colon: "HERE Technologies: Provides..." -> "HERE Technologies"
                    parsed_info['company_name'] = _clean_company_name(comapany_name)
                if enriched_location:
                    parsed_info['location'] = enriched_location
                # Normalize to lowercase API values (Onsite->onsite, Remote->remote, Hybrid->hybrid)
                if enriched_type:
                    parsed_info['employment_mode'] = _normalize_employment_mode(enriched_type)
                
                if ats_url and platform == 'workable':
                    try:
                        if not driver:
                            driver = get_driver()
                        details = extract_workable_details(driver, ats_url)
                        if details:
                            parsed_info.update({k: v for k, v in details.items() if v})
                    except Exception as e:
                        logger.warning(f"⚠️ Could not extract workable details for {job_id} due to browser error: {e}")
                
                # Construct job listing object for API
                job_listing = {
                    "title": parsed_info.get('title') or job.get('title', 'Unknown Title')[:255],
                    "company_name": parsed_info.get('company_name') or "Unknown Company",
                    "location": parsed_info.get('location'),
                    "city": job.get('city'),
                    "state": job.get('state'),
                    "country": job.get('country'),
                    "position_type": parsed_info.get('position_type', 'full_time'),
                    "employment_mode": parsed_info.get('employment_mode', 'onsite'),
                    "source": "hiring.cafe",
                    "source_uid": job_id,
                    "job_url": ats_url or job.get('hiring_cafe_url'),
                    "description": job.get('company_description') or parsed_info.get('description'),
                    "status": "open"
                }
                batch_data.append(job_listing)
                
                # Send in batches of 50
                if len(batch_data) >= 50:
                    _send_batch(positions_url, token, batch_data)
                    processed_count += len(batch_data)
                    batch_data = []

        # Final batch
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
        "Content-Type": "application/json"
    }
    payload = {"positions": batch}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        res_data = response.json()
        logger.info(f"Batch success: {res_data.get('inserted', 0)} inserted, {res_data.get('skipped', 0)} duplicates")
    except Exception as e:
        logger.error(f"Failed to send batch to API: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest grouped job data into the website API.")
    parser.add_argument("--input", help="Path to the by_ats JSON file", 
                       default=str(ROOT / "hiring_cafe_by_ats.json"))
    args = parser.parse_args()
    
    ingest_to_api(args.input)
