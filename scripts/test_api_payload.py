import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

# Mock logger and other imports if needed, or just import what we need
from scripts.hiring_cafe_step4_ingest_to_api import parse_hiring_cafe_title

def dry_run_payload(json_path):
    if not os.path.exists(json_path):
        print(f"File not found: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    by_ats = data.get('by_ats', {})
    first_platform = list(by_ats.keys())[0]
    first_job = by_ats[first_platform][0]

    job_id = first_job.get('job_id')
    ats_url = first_job.get('ats_url')
    raw_title = first_job.get('title', '')
    
    # Use enriched info if available
    job_tittle = first_job.get('job_tittle')
    comapany_name = first_job.get('comapany')
    enriched_location = first_job.get('location')
    enriched_type = first_job.get('type', '').lower()
    
    parsed_info = parse_hiring_cafe_title(raw_title)
    
    # Prioritize enriched fields
    if job_tittle: parsed_info['title'] = job_tittle
    if comapany_name: parsed_info['company_name'] = comapany_name
    if enriched_location: parsed_info['location'] = enriched_location
    if enriched_type in ['onsite', 'remote', 'hybrid']:
        parsed_info['employment_mode'] = enriched_type
    
    # Construct job listing object for API
    job_listing = {
        "title": parsed_info.get('title') or first_job.get('title', 'Unknown Title')[:255],
        "company_name": parsed_info.get('company_name') or "Unknown Company",
        "location": parsed_info.get('location'),
        "city": first_job.get('city'),
        "state": first_job.get('state'),
        "country": first_job.get('country'),
        "position_type": parsed_info.get('position_type', 'full_time'),
        "employment_mode": parsed_info.get('employment_mode', 'onsite'),
        "source": "hiring.cafe",
        "source_uid": job_id,
        "job_url": ats_url or first_job.get('hiring_cafe_url'),
        "description": first_job.get('company_description') or parsed_info.get('description'),
        "status": "open"
    }

    print("\n--- DRY RUN API PAYLOAD (First Job) ---")
    print(json.dumps(job_listing, indent=2))
    print("---------------------------------------")

if __name__ == "__main__":
    dry_run_payload("hiring_cafe_by_ats.json")
