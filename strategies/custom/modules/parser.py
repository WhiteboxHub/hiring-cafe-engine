"""
Card Text Parsing and Company Name Resolution

Handles:
- Parsing raw hiring.cafe card text into structured job fields
- Company name extraction and cleaning
- Job categorization by ATS platform
"""

import re
from core.logger import logger


def parse_hiring_cafe_card_text(text: str) -> dict:
    """
    Parse the raw text from a Hiring Cafe job card into granular fields.

    Hiring Cafe cards do NOT have a guaranteed fixed line order.
    A salary line, stock ticker, or multi-city label can appear anywhere
    and shift subsequent lines down — making fixed-index parsing unreliable.

    This version classifies each line by its *content*:
      • Time token  → skip (e.g., 15h, 2d)
      • Work mode   → "Onsite/Remote/Hybrid" (exact) → data["type"]
      • Job type    → "Full Time/Contract/…" (exact) → skip (not company!)
      • Salary      → $100k-$200k pattern → skip
      • Stock ticker/ YOE → skip
      • Location    → has comma OR known geo keyword → data["location"]
      • Title       → first surviving line → data["job_tittle"]
      • Company     → line with ":" whose left side passes junk checks
      • Description → colon-right-side or remaining lines
    """
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    data = {
        "job_tittle": None,
        "location": None,
        "city": None,
        "state": None,
        "country": None,
        "type": None,
        "company": None,
        "company_description": None,
    }
    if not lines:
        return data

    # ── classifiers ───────────────────────────────────────────────────────
    _time_re   = re.compile(r'^\d+[hdmw]$|^\d+ months? ago$', re.I)
    _salary_re = re.compile(
        r'\$\d+[kK]?[-–]\$?\d+[kK]?|\$\d+[kK]?/\w+|\d+[kK]/(?:yr|mo|year|hr)',
        re.I,
    )
    _mode_map  = {'onsite': 'Onsite', 'remote': 'Remote', 'hybrid': 'Hybrid'}
    _type_set  = {
        'full time', 'full-time', 'contract', 'internship',
        'part time', 'temporary', 'part-time',
    }
    _loc_signals = {
        'united states', 'usa', 'india', 'germany', 'france', 'spain',
        'italy', 'egypt', 'canada', 'uk', 'united kingdom', 'remote',
        'santa clara', 'mountain view', 'san francisco', 'new york',
        'sunnyvale', 'austin', 'seattle', 'charlotte', 'mclean', 'boston',
        'raleigh', 'dublin', 'kansas city', 'indianapolis', 'dallas',
        'denver', 'chicago', 'atlanta', 'milpitas', 'bellevue',
        'palo alto', 'chevy chase', 'linthicum heights', 'annapolis junction',
        'conshohocken', 'ridgefield park', 'schiller park', 'boerne',
        'newberg', 'fairborn', 'mountlake terrace',
    }
    _junk_starts = ('NYSE:', 'NASDAQ:', 'Euronext', 'YOE:')

    def _is_salary(s):
        return bool(_salary_re.search(s))

    def _is_location(s):
        sl = s.lower()
        return ',' in s or any(sig in sl for sig in _loc_signals)

    def _is_multi_city(s):
        parts = re.split(r'\s+or\s+', s.strip(), flags=re.I)
        return len(parts) >= 2 and all(':' not in p and len(p.split()) <= 5 for p in parts)

    def _is_junk(s):
        ll = s.strip().lower()
        return (
            bool(_time_re.match(s))
            or bool(_salary_re.search(s))
            or ll in _mode_map
            or ll in _type_set
            or any(s.startswith(p) for p in _junk_starts)
            or s.startswith(':')
        )

    # ── single-pass classification ────────────────────────────────────────
    title_set  = False
    desc_lines = []

    for line in lines:
        ll = line.strip().lower()

        if _time_re.match(line):
            continue                          # skip time token

        if ll in _mode_map:
            data['type'] = _mode_map[ll]      # work mode
            continue

        if ll in _type_set:
            continue                          # "Full Time" etc — NOT a company

        if _is_salary(line):
            continue                          # skip salary

        if any(line.startswith(p) for p in _junk_starts):
            continue                          # skip ticker / YOE

        if line.startswith(':'):
            if not data['company_description']:
                data['company_description'] = line.lstrip(':').strip()
            continue

        # Location
        if not data['location'] and _is_location(line) and not _is_multi_city(line):
            data['location'] = line
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                data['city'], data['state'], data['country'] = parts[0], parts[1], parts[2]
            elif len(parts) == 2:
                data['city'], data['country'] = parts[0], parts[1]
            else:
                data['city'] = parts[0]
            continue

        # Title — first surviving line
        if not title_set:
            data['job_tittle'] = line
            title_set = True
            continue

        # Company — line with ":" whose left side passes checks
        if ':' in line and not data['company']:
            name = line.split(':', 1)[0].strip().rstrip('.,;-')
            if name and not _is_salary(name) and not _is_multi_city(name):
                data['company'] = name
                right = line.split(':', 1)[1].strip()
                if right and not data['company_description']:
                    data['company_description'] = right
            continue

        # Candidate company (no colon) — first line that isn't junk
        if not data['company'] and not _is_junk(line) and not _is_multi_city(line):
            data['company'] = line
            continue

        # Everything else → description
        if line and not _is_junk(line):
            desc_lines.append(line)

    if not data['company_description'] and desc_lines:
        data['company_description'] = ' '.join(desc_lines)

    return data


def categorize_jobs_by_ats(jobs: list[dict]) -> dict[str, list[dict]]:
    """Group jobs by ATS platform."""
    by_platform = {}
    for j in jobs:
        ats_obj = j.get("ats")
        if isinstance(ats_obj, dict):
            platform = (ats_obj.get("platform") or "unknown").strip() or "unknown"
            ats_url = ats_obj.get("url")
        else:
            platform = (j.get("ats_platform") or "unknown").strip() or "unknown"
            ats_url = j.get("ats_url")
        job_posting_url = j.get("url") or j.get("job_posting_url") or j.get("hiring_cafe_url")
        entry = {
            **j,
            "job_posting_url": job_posting_url,
            "ats": {"url": ats_url, "platform": platform},
        }
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(entry)
    return by_platform
