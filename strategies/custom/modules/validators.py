"""
URL Validation and Junk Detection

Handles:
- ATS platform detection from URLs
- URL validation (reject non-job URLs, social media, file downloads, etc.)
- Job path keyword detection
"""

import re
from core.locator_loader import LocatorLoader

locators = LocatorLoader()


def detect_ats_platform(url: str) -> str | None:
    """Detect ATS platform from URL using regex patterns."""
    if not url:
        return None
    url_lower = url.lower()
    for pattern, platform in locators.ats_platform_patterns:
        if re.search(pattern, url_lower):
            return platform
    return None


def is_likely_ats_url(url: str) -> bool:
    """
    Strict check: return True only for URLs that look like a specific job posting.
    Rejects: social media, PDF/doc files, generic career homepages, EEO/policy pages,
    and any URL too shallow to be a real job (homepage-level paths).
    """
    if not url or not url.strip().startswith("http"):
        return False

    url_stripped = url.strip()
    url_lower = url_stripped.lower()

    # Reject hiring.cafe internal links
    if "hiring.cafe" in url_lower:
        return False

    # Reject social / sharing domains
    for domain in locators.get("patterns", "non_ats_domains", []):
        if domain in url_lower:
            return False

    # Reject file downloads (PDFs, docs, images, etc.)
    path_part = url_lower.split("?")[0].split("#")[0]
    if any(path_part.endswith(ext) for ext in locators.get("patterns", "non_job_extensions", [])):
        return False

    # Reject policy/non-job pages by path segment
    for segment in locators.get("patterns", "non_job_path_segments", []):
        if segment in url_lower:
            return False

    # Reject generic homepage-level URLs
    from urllib.parse import urlparse
    parsed = urlparse(url_stripped)
    path = parsed.path.rstrip("/")
    path_depth = len([p for p in path.split("/") if p])
    if path_depth == 0:
        return False
    if path_depth == 1:
        if not detect_ats_platform(url_stripped):
            return False

    # ── POSITIVE SIGNALS ──────────────────────────────────────────────────────
    if detect_ats_platform(url_stripped):
        return True

    job_path_keywords = locators.get("patterns", "job_path_keywords", [])
    if any(kw in url_lower for kw in job_path_keywords):
        return True

    return False


def _job_id_from_href(href: str) -> str | None:
    """Extract job ID from href like '/viewjob/p16gu5rnyh9yhp7v'."""
    if not href:
        return None
    match = re.search(r"/viewjob/([a-zA-Z0-9_-]+)", href)
    return match.group(1) if match else None
