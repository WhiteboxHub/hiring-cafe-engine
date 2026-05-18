"""
ATS URL Extraction with Multi-Layer Fallback

Handles:
- 6-layer ATS URL extraction strategy (DOM, page source, click, redirect, etc.)
- Apply button detection with fallback XPaths
- Page source regex scanning with Unicode escape handling
"""

import re
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from core.logger import logger
from core.locator_loader import LocatorLoader
from .validators import is_likely_ats_url, detect_ats_platform

locators = LocatorLoader()


def extract_ats_urls_from_page_source(driver) -> list[str]:
    """
    Scan raw page HTML/JS for known ATS URLs.
    Handles three encodings found in hiring.cafe (Next.js SPA):
      1. Plain URLs in HTML attributes and JS strings
      2. Unicode-escaped URLs in JSON (__NEXT_DATA__): \\u0026 -> &
      3. JSON-encoded URLs from __NEXT_DATA__ blobs
    Returns deduplicated list of valid candidate ATS URLs.
    """
    try:
        source = driver.page_source
        candidates = set()
        regex = locators.ats_url_regex
        if not regex:
            return []

        # Pass 1: direct regex scan
        for url in regex.findall(source):
            url_clean = url.strip().rstrip('"\'\\ ')
            if "hiring.cafe" not in url_clean.lower():
                candidates.add(url_clean)

        # Pass 2: decode Unicode escapes then rescan
        try:
            decoded = source.encode('utf-8').decode('unicode_escape', errors='replace')
            for url in regex.findall(decoded):
                url_clean = url.strip().rstrip('"\'\\ ')
                if "hiring.cafe" not in url_clean.lower():
                    candidates.add(url_clean)
        except Exception:
            pass

        # Pass 3: extract __NEXT_DATA__ JSON blob and parse URLs
        try:
            import json as _json
            next_data_match = re.search(
                r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                source, re.DOTALL | re.IGNORECASE
            )
            if next_data_match:
                blob = next_data_match.group(1).strip()
                def _find_urls(obj):
                    if isinstance(obj, str):
                        if obj.startswith('http') and is_likely_ats_url(obj):
                            candidates.add(obj)
                    elif isinstance(obj, dict):
                        for v in obj.values():
                            _find_urls(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            _find_urls(item)
                try:
                    data = _json.loads(blob)
                    _find_urls(data)
                except Exception:
                    for url in regex.findall(blob):
                        url_clean = url.strip().rstrip('"\'\\ ')
                        if "hiring.cafe" not in url_clean.lower():
                            candidates.add(url_clean)
        except Exception:
            pass

        results = list(candidates)
        if results:
            logger.debug(f"[PageSource] Found {len(results)} ATS URL(s)")
        return results
    except Exception as e:
        logger.debug(f"Page source ATS scan failed: {e}")
        return []


def try_get_ats_url_from_dom(driver) -> str | None:
    """
    Multi-step DOM search for ATS URL without clicking.
    Steps: button tag check → ancestor <a> → siblings → page-wide ATS <a> → page source regex.
    """
    def accept_url(href: str) -> bool:
        return (
            bool(href)
            and href.strip().startswith("http")
            and "hiring.cafe" not in href.lower()
            and is_likely_ats_url(href)
        )

    try:
        xpath = locators.get("xpaths", "apply_now_button")
        buttons = driver.find_elements(By.XPATH, xpath)

        if buttons:
            btn = buttons[0]

            # Step 1: Apply button itself is an <a>
            if btn.tag_name.lower() == "a":
                href = btn.get_attribute("href")
                if accept_url(href):
                    return href.strip()

            # Step 2: Ancestor <a>
            try:
                parent = btn
                for _ in range(10):
                    parent = parent.find_element(By.XPATH, "..")
                    if parent.tag_name.lower() == "a":
                        href = parent.get_attribute("href")
                        if accept_url(href):
                            return href.strip()
                    if parent.tag_name.lower() == "body":
                        break
            except Exception:
                pass

            # Step 3: Sibling <a> in same container
            try:
                container = btn.find_element(By.XPATH, "..")
                for a in container.find_elements(By.TAG_NAME, "a"):
                    href = a.get_attribute("href")
                    if accept_url(href):
                        return href.strip()
            except Exception:
                pass

            # Step 4: Walk up 8 levels, look for ATS links
            try:
                root = btn
                for _ in range(8):
                    root = root.find_element(By.XPATH, "..")
                    for a in root.find_elements(By.CSS_SELECTOR, 'a[href^="http"]'):
                        href = a.get_attribute("href")
                        if not accept_url(href):
                            continue
                        target = (a.get_attribute("target") or "").lower()
                        rel = (a.get_attribute("rel") or "").lower()
                        text = (a.text or "").lower()
                        if "apply" in text or target == "_blank" or "noopener" in rel:
                            return href.strip()
            except Exception:
                pass

        # Step 5: Page-wide — any <a> pointing to a known ATS platform
        try:
            for a in driver.find_elements(By.CSS_SELECTOR, 'a[href^="http"]'):
                href = a.get_attribute("href") or ""
                if accept_url(href) and detect_ats_platform(href):
                    return href.strip()
        except Exception:
            pass

        # Step 6: Regex scan of raw page source
        candidates = extract_ats_urls_from_page_source(driver)
        if candidates:
            return candidates[0]

        return None

    except Exception as e:
        logger.debug(f"DOM ATS URL extraction failed: {e}")
        return None


def find_apply_button(driver):
    """
    Find the Apply button using primary XPath first, then fallbacks.
    Scrolls the page to help lazy-loaded buttons appear.
    Returns the button element or None.
    """
    # Scroll down a bit
    try:
        driver.execute_script("window.scrollTo(0, 400);")
        time.sleep(0.5)
    except Exception:
        pass

    # Try primary XPath with 10s wait
    try:
        xpath = locators.get("xpaths", "apply_now_button")
        btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        return btn
    except (TimeoutException, NoSuchElementException):
        pass

    # Try each fallback XPath with 3s wait
    fallbacks = locators.get("xpaths", "apply_button_fallbacks", [])
    for xpath in fallbacks:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            logger.debug(f"Found Apply button via fallback XPath")
            return btn
        except (TimeoutException, NoSuchElementException):
            continue

    # Last resort: scroll to bottom and try primary again
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        xpath = locators.get("xpaths", "apply_now_button")
        btns = driver.find_elements(By.XPATH, xpath)
        if btns:
            return btns[0]
    except Exception:
        pass

    return None
