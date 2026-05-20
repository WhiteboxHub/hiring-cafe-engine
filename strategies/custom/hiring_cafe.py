from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
from config.settings import settings
import json
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from core.locator_loader import LocatorLoader

# Initialize locator loader
locators = LocatorLoader()

def _job_id_from_href(href: str) -> str | None:
    """Extract job ID from href like '/job/p16gu5rnyh9yhp7v'."""
    if not href:
        return None
    # Support both new /job/ format and legacy /viewjob/ format
    match = re.search(r"/(?:job|viewjob)/([a-zA-Z0-9_-]+)", href)
    return match.group(1) if match else None


def _load_hiring_cafe_config() -> dict:
    """Load Hiring Cafe config from config/hiring_cafe.json. Returns {} if missing."""
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "hiring_cafe.json",
        )
        if os.path.isfile(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load hiring_cafe config: {e}")
    return {}


def _parse_date_fetched_past_n_days(value) -> int:
    presets = locators.date_fetched_presets
    if value is None:
        return 2
    if isinstance(value, int):
        return value
    s = str(value).strip().lower()
    if s in presets:
        return presets[s]
    try:
        return int(value)
    except (TypeError, ValueError):
        return 2


def _normalize_search_keyword(keyword: str) -> str:
    """
    Normalize a search keyword for Hiring Cafe's jobTitleQuery param.

    Hiring Cafe's state-based URL handles spaces naturally via encoding.
    Literal '+' symbols in the keyword can lead to double-encoding or
    displaying literally in the search filters, so we preserve spaces.
    """
    if not keyword:
        return keyword
    return keyword.strip()


def _build_search_url(
    keyword: str,
    base_url: str = "https://hiring.cafe",
    date_fetched_past_n_days: int = 2,
) -> str:
    # Use jobTitleQuery (not searchQuery) so the keyword is applied to
    # the "Job Title Terms" filter — exactly what the UI does when you
    # type a boolean query like "AI AND ENGINEER" and click Apply.
    job_title_query = _normalize_search_keyword(keyword)
    search_state = json.dumps({
        "jobTitleQuery": job_title_query,
        "dateFetchedPastNDays": date_fetched_past_n_days,
    })
    encoded = quote(search_state, safe="")
    return f"{base_url}/?searchState={encoded}"


def detect_ats_platform(url: str) -> str | None:
    if not url:
        return None
    url_lower = url.lower()
    for pattern, platform in locators.ats_platform_patterns:
        if re.search(pattern, url_lower):
            return platform
    return None


NON_ATS_URL_DOMAINS = (
    "reddit.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "linkedin.com/share",
    "linkedin.com/feed",
    "t.co",
    "wa.me",
    "telegram.me",
    "whatsapp.com",
)

# URL path segments that indicate a generic/policy page — NOT a specific job posting
NON_JOB_PATH_SEGMENTS = (
    "/eeo",
    "/eeo/",
    "equal-employment",
    "equal_employment",
    "/diversity",
    "/inclusion",
    "/accessibility",
    "/privacy",
    "/terms",
    "/legal",
    "/cookie",
    "/sitemap",
    "/about",
    "/contact",
    "/press",
    "/news",
    "/blog",
    "/faq",
    "/help",
    "/support",
    "/login",
    "/register",
    "/sign-in",
    "/sign-up",
    "/subscribe",
)

# File extensions that are never job application URLs
NON_JOB_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".gif", ".zip")


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

    # Reject generic homepage-level URLs (too shallow: scheme + domain + at most 1 segment ending in /)
    # e.g. https://careers.blackrock.com/ or https://kla.com/careers
    from urllib.parse import urlparse
    parsed = urlparse(url_stripped)
    path = parsed.path.rstrip("/")
    path_depth = len([p for p in path.split("/") if p])  # number of non-empty path segments
    if path_depth == 0:
        return False  # pure domain, no path
    if path_depth == 1:
        # Only accept single-segment paths if it's a known ATS platform
        # e.g. https://apply.workable.com/j/ABC123 has depth 2 → fine
        # But https://careers.blackrock.com/ has depth 0 → rejected above
        # https://kla.com/careers has depth 1 → only accept if known ATS
        if not detect_ats_platform(url_stripped):
            return False

    # ── POSITIVE SIGNALS ──────────────────────────────────────────────────────

    # Known ATS platform → strong positive signal
    if detect_ats_platform(url_stripped):
        return True

    # URL path contains job-specific keywords (deeper than homepage)
    job_path_keywords = locators.get("patterns", "job_path_keywords", [])
    if any(kw in url_lower for kw in job_path_keywords):
        return True

    return False


def categorize_jobs_by_ats(jobs: list[dict]) -> dict[str, list[dict]]:
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


class HiringCafeStrategy(BaseStrategy):
    """
    Hiring Cafe scraper strategy.
    Multi-layer ATS URL extraction with 5 fallback methods.
    """

    def __init__(self, driver, job_site=None, selectors=None, db_session=None, date_filter_override=None):
        config = _load_hiring_cafe_config()
        if config.get("search_keywords"):
            keywords = [str(k).strip() for k in config["search_keywords"] if str(k).strip()]
        elif config.get("search_keyword"):
            keywords = [str(config["search_keyword"]).strip()]
        else:
            env_kw = os.environ.get("HIRING_CAFE_SEARCH_KEYWORD", "").strip()
            keywords = [env_kw] if env_kw else ["AI"]
        self._search_keywords = keywords if keywords else ["AI"]
        self._date_fetched_past_n_days = (
            _parse_date_fetched_past_n_days(date_filter_override)
            if date_filter_override is not None
            else _parse_date_fetched_past_n_days(
                config.get("date_fetched_past_n_days") or config.get("date_filter") or 2
            )
        )
        base_url = "https://hiring.cafe"
        search_url = _build_search_url(
            self._search_keywords[0], base_url, self._date_fetched_past_n_days
        )

        if job_site is None:
            class MinimalJobSite:
                def __init__(self, url_template):
                    self.company_name = "Hiring Cafe"
                    self.search_url_template = url_template
            job_site = MinimalJobSite(search_url)

        super().__init__(driver, job_site, selectors or {})
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.base_url = base_url
        self.search_url = search_url
        self._random_pause_lo = float(settings.HIRING_CAFE_RANDOM_PAUSE_MIN_SEC)
        self._random_pause_hi = float(settings.HIRING_CAFE_RANDOM_PAUSE_MAX_SEC)
        self._scroll_step_lo = float(settings.HIRING_CAFE_SCROLL_STEP_MIN_SEC)
        self._scroll_step_hi = float(settings.HIRING_CAFE_SCROLL_STEP_MAX_SEC)
        self._step2_pause_lo = float(settings.HIRING_CAFE_STEP2_PAUSE_MIN_SEC)
        self._step2_pause_hi = float(settings.HIRING_CAFE_STEP2_PAUSE_MAX_SEC)
        self._step2_page_lo = float(settings.HIRING_CAFE_STEP2_PAGE_SETTLE_MIN_SEC)
        self._step2_page_hi = float(settings.HIRING_CAFE_STEP2_PAGE_SETTLE_MAX_SEC)
        self._step2_shuffle_pending = bool(settings.HIRING_CAFE_STEP2_SHUFFLE_PENDING)
        self._step2_break_every_n = int(settings.HIRING_CAFE_STEP2_BREAK_EVERY_N)
        self._step2_long_break_lo = float(settings.HIRING_CAFE_STEP2_LONG_BREAK_MIN_SEC)
        self._step2_long_break_hi = float(settings.HIRING_CAFE_STEP2_LONG_BREAK_MAX_SEC)
        self._step2_mouse_jitter = bool(settings.HIRING_CAFE_STEP2_MOUSE_JITTER)

        logger.info(
            "✅ HiringCafeStrategy initialized (keywords=%s, date_fetched_past_n_days=%s, "
            "human_pause=%.1f–%.1fs, scroll_step=%.1f–%.1fs, step2_between=%.1f–%.1fs, "
            "step2_page_settle=%.1f–%.1fs, shuffle_pending=%s, break_every_n=%d)",
            self._search_keywords,
            self._date_fetched_past_n_days,
            self._random_pause_lo,
            self._random_pause_hi,
            self._scroll_step_lo,
            self._scroll_step_hi,
            self._step2_pause_lo,
            self._step2_pause_hi,
            self._step2_page_lo,
            self._step2_page_hi,
            self._step2_shuffle_pending,
            self._step2_break_every_n,
        )

    def login(self):
        logger.info("ℹ️ No login required for Hiring Cafe")
        return True

    def _random_human_pause(
        self,
        label: str | None = None,
        lo: float | None = None,
        hi: float | None = None,
    ) -> float:
        """
        Sleep a random duration (new draw each call). Default range = Step 1 settings;
        pass lo/hi for Step 2 between-job pauses or other overrides.
        """
        lo = self._random_pause_lo if lo is None else float(lo)
        hi = self._random_pause_hi if hi is None else float(hi)
        if hi < lo:
            lo, hi = hi, lo
        sec = random.uniform(lo, hi)
        if label:
            logger.info("⏳ Human pause (%s): %.1fs (range %.1f–%.1fs)", label, sec, lo, hi)
        else:
            logger.info("⏳ Human pause: %.1fs (range %.1f–%.1fs)", sec, lo, hi)
        time.sleep(sec)
        return sec

    def _random_scroll_step_pause(self) -> float:
        """Random wait between infinite-scroll steps (new value each scroll)."""
        lo, hi = self._scroll_step_lo, self._scroll_step_hi
        if hi < lo:
            lo, hi = hi, lo
        sec = random.uniform(lo, hi)
        time.sleep(sec)
        return sec

    def _scroll_to_bottom(self):
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

    def _get_viewjob_links(self):
        try:
            selector = locators.get("selectors", "job_link")
            links = self.driver.find_elements(By.CSS_SELECTOR, selector)
            return [el for el in links if el.is_displayed()]
        except Exception as e:
            logger.warning(f"Error finding viewjob links: {e}")
            return []

    def _get_unique_job_ids(self) -> set[str]:
        ids = set()
        for link in self._get_viewjob_links():
            href = link.get_attribute("href") or ""
            job_id = _job_id_from_href(href)
            if job_id:
                ids.add(job_id)
        return ids

    def _get_current_job_count(self) -> int:
        return len(self._get_unique_job_ids())

    def _debug_page_structure(self):
        logger.info("🔍 Analyzing page structure for debugging...")
        try:
            page_source_length = len(self.driver.page_source)
            logger.info(f"Page source length: {page_source_length} characters")
            element_counts = {}
            test_selectors = [
                ("articles", "article"),
                ("divs", "div"),
                ("links", "a"),
                ("cards", "[class*='card']"),
                ("jobs", "[class*='job']"),
                ("listings", "[class*='listing']"),
            ]
            for name, selector in test_selectors:
                try:
                    count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
                    element_counts[name] = count
                except Exception:
                    element_counts[name] = 0
            logger.info(f"Element counts: {element_counts}")
        except Exception as e:
            logger.warning(f"Error in debug_page_structure: {e}")

    def _is_session_alive(self) -> bool:
        """Check if the Chrome session is still alive."""
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def _parse_hiring_cafe_card_text(self, text: str) -> dict:
        """
        Parse the raw text from a Hiring Cafe job card into granular fields.

        Hiring Cafe cards do NOT have a guaranteed fixed line order.
        A salary line, stock ticker, or multi-city label can appear anywhere
        and shift subsequent lines down — making fixed-index parsing unreliable.

        This version classifies each line by its *content*:
          • Time token  → r^\d+[hdmw]$  → skip
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
            r'\$\d+[kK]?[-\u2013]\$?\d+[kK]?|\$\d+[kK]?/\w+|\d+[kK]/(?:yr|mo|year|hr)',
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

    def _scroll_until_end(self, max_scrolls=100):
        logger.info(
            "🔄 Starting infinite scroll (random step %.1f–%.1fs each)...",
            self._scroll_step_lo,
            self._scroll_step_hi,
        )
        previous_count = 0
        no_change_count = 0
        scroll_attempts = 0
        while scroll_attempts < max_scrolls:
            # Check session is still alive before each scroll
            if not self._is_session_alive():
                logger.warning("⚠️ Chrome session died during scroll — stopping early.")
                return False

            current_count = self._get_current_job_count()
            logger.info(f"📊 Current job count: {current_count} (scroll attempt {scroll_attempts + 1}/{max_scrolls})")
            if current_count == previous_count:
                no_change_count += 1
                if no_change_count >= 3:
                    logger.info(f"✅ No new jobs loaded after {no_change_count} scrolls. Reached end.")
                    return True
            else:
                no_change_count = 0
            previous_count = current_count
            try:
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                self._scroll_to_bottom()
                self._random_scroll_step_pause()
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    self.driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(1)
            except Exception as e:
                logger.warning(f"⚠️ Scroll error (attempt {scroll_attempts+1}): {e}")
                if not self._is_session_alive():
                    logger.error("❌ Chrome session lost — browser was closed.")
                    return False
                break
            scroll_attempts += 1
            self.human.random_delay(0.5, 1.5)
        logger.warning(f"⚠️ Reached maximum scroll attempts ({max_scrolls}). Stopping.")
        return False

    def extract_all_job_ids(self) -> list[str]:
        return sorted(self._get_unique_job_ids())

    def _extract_job_listings(self):
        jobs = []
        logger.info("🔍 Extracting job listings via viewjob links...")
        try:
            seen_ids = set()
            for link in self._get_viewjob_links():
                try:
                    href = link.get_attribute("href") or ""
                    job_id = _job_id_from_href(href)
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    url = href if href.startswith("http") else (self.base_url + (href if href.startswith("/") else "/" + href))
                    title = None
                    enriched_data = {}
                    try:
                        parent = link.find_element(By.XPATH, "./ancestor::*[self::article or self::div][position()<=3]")
                        raw = (parent.text or "").strip()
                        if raw and "Job Posting" in raw:
                            title = raw.replace("Job Posting", "").strip()[:200] or None

                        if raw:
                            enriched_data = self._parse_hiring_cafe_card_text(raw)
                    except Exception:
                        pass
                    if not title:
                        title = enriched_data.get("job_tittle") or f"Job {job_id}"

                    job_data = {
                        "job_id": job_id,
                        "external_id": job_id,
                        "title": title,
                        "url": url,
                        "company": enriched_data.get("company"),
                        "location": enriched_data.get("location"),
                        "scraped_at": datetime.now().isoformat(),
                        **enriched_data
                    }
                    jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"Error extracting from link: {e}")
                    continue
            logger.info(f"✅ Extracted {len(jobs)} unique job listings (job IDs)")
            return jobs
        except Exception as e:
            logger.error(f"❌ Error extracting job listings: {e}")
            import traceback
            traceback.print_exc()
            return []

    # ─────────────────────────────────────────────────────────────────────────────
    # ATS URL EXTRACTION — IMPROVED WITH 5-LAYER FALLBACK
    # ─────────────────────────────────────────────────────────────────────────────

    def _extract_ats_urls_from_page_source(self) -> list[str]:
        """
        Scan raw page HTML/JS for known ATS URLs.
        Handles three encodings found in hiring.cafe (Next.js SPA):
          1. Plain URLs in HTML attributes and JS strings
          2. Unicode-escaped URLs in JSON (__NEXT_DATA__): \\u0026 -> &, \\u003e -> >
          3. JSON-encoded URLs extracted from __NEXT_DATA__ / window.__INITIAL_STATE__ blobs
        Returns deduplicated list of valid candidate ATS URLs.
        """
        try:
            source = self.driver.page_source

            # ── Pass 1: direct regex scan on raw source ─────────────────────
            candidates = set()
            regex = locators.ats_url_regex
            if not regex:
                return []
                
            for url in regex.findall(source):
                url_clean = url.strip().rstrip('"\'\\ ')
                if "hiring.cafe" not in url_clean.lower():
                    candidates.add(url_clean)

            # ── Pass 2: decode Unicode escapes then rescan ───────────────────
            # hiring.cafe embeds job data in __NEXT_DATA__ JSON where & -> \u0026
            try:
                decoded = source.encode('utf-8').decode('unicode_escape', errors='replace')
                for url in regex.findall(decoded):
                    url_clean = url.strip().rstrip('"\'\\ ')
                    if "hiring.cafe" not in url_clean.lower():
                        candidates.add(url_clean)
            except Exception:
                pass

            # ── Pass 3: extract __NEXT_DATA__ JSON blob and parse URLs ───────
            try:
                import json as _json
                next_data_match = re.search(
                    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                    source, re.DOTALL | re.IGNORECASE
                )
                if next_data_match:
                    blob = next_data_match.group(1).strip()
                    # Recursively find all string values that look like URLs
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
                        # Fallback: regex on the blob text
                        for url in regex.findall(blob):
                            url_clean = url.strip().rstrip('"\'\\ ')
                            if "hiring.cafe" not in url_clean.lower():
                                candidates.add(url_clean)
            except Exception:
                pass

            results = list(candidates)
            if results:
                logger.debug(f"[PageSource] Found {len(results)} ATS URL(s): {results[:3]}")
            return results
        except Exception as e:
            logger.debug(f"Page source ATS scan failed: {e}")
            return []

    def _try_get_ats_url_from_dom(self) -> str | None:
        """
        IMPROVED: Multi-step DOM search for ATS URL without clicking.
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
            buttons = self.driver.find_elements(By.XPATH, xpath)

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
                        tag = parent.tag_name.lower()
                        if tag == "a":
                            href = parent.get_attribute("href")
                            if accept_url(href):
                                return href.strip()
                            break
                        if tag == "body":
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
                for a in self.driver.find_elements(By.CSS_SELECTOR, 'a[href^="http"]'):
                    href = a.get_attribute("href") or ""
                    if accept_url(href) and detect_ats_platform(href):
                        return href.strip()
            except Exception:
                pass

            # Step 6: Regex scan of raw page source
            candidates = self._extract_ats_urls_from_page_source()
            if candidates:
                return candidates[0]

            return None

        except Exception as e:
            logger.debug(f"DOM ATS URL extraction failed: {e}")
            return None

    def _find_apply_button(self):
        """
        Find the Apply button using primary XPath first, then fallbacks.
        Scrolls the page to help lazy-loaded buttons appear.
        Returns the button element or None.
        """
        # Scroll down a bit — hiring.cafe lazy-loads the Apply button
        try:
            self.driver.execute_script("window.scrollTo(0, 400);")
            time.sleep(0.5)
        except Exception:
            pass

        # Try primary XPath with 10s wait
        try:
            xpath = locators.get("xpaths", "apply_now_button")
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            return btn
        except (TimeoutException, NoSuchElementException):
            pass

        # Try each fallback XPath with 3s wait
        fallbacks = locators.get("xpaths", "apply_button_fallbacks", [])
        for xpath in fallbacks:
            try:
                btn = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                logger.debug(f"Found Apply button via fallback XPath: {xpath[:60]}")
                return btn
            except (TimeoutException, NoSuchElementException):
                continue

        # Last resort: scroll to bottom and try primary again
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            xpath = locators.get("xpaths", "apply_now_button")
            btns = self.driver.find_elements(By.XPATH, xpath)
            if btns:
                return btns[0]
        except Exception:
            pass

        return None

    def _get_ats_link_from_job_page(self, job_id: str) -> dict | None:
        """
        6-layer ATS URL extraction with fallback button detection.

        Returns dict with status tracking:
        {
            "ats_url": str | None,
            "ats_platform": str | None,
            "status": "success" | "no_apply_button" | "blocked" | "timeout" | "browser_error" | "invalid_url",
            "error_detail": str  # human-readable error description
        }

        Status values:
        - success: ATS URL extracted and validated
        - no_apply_button: No apply button found (permanent failure)
        - blocked: Page blocked / Cloudflare challenge detected
        - timeout: Page load timeout
        - browser_error: WebDriver crash or connection lost
        - invalid_url: URL extracted but failed validation
        - retryable: Temporary error, safe to retry

        Layer 1+2: DOM check + page source regex (no clicking needed)
        Layer 3:   _find_apply_button (primary XPath + fallbacks + scroll) → click → new tab
        Layer 4:   Same-tab redirect detection
        Layer 5:   Page source regex after click
        """
        job_url = f"{self.base_url}/job/{job_id}"

        # Job IDs that persistently fail — log page source snippet for diagnosis
        DEBUG_JOB_IDS = {
            'qeu7b8sxz39rdc0o', 'e88lancdghmr59nh', 'vxpe1y6evnixao8c',
            'glv6wzud1snhi2dn', 'sdxd2sbaemobnnbt', 'nerymx0rtqhhblij',
            '7cxd1czqf3s2y6db', 'wflpb81im2umy3fb', 'l90pefs1018lxx96',
            'p5txnh2fbsp8x210', 'efrj795x4r59nqlr', 'cyrnkn2jq72mkemz', '72w0xhixj1jxi37s',
        }
        try:
            self.driver.get(job_url)
            p_lo, p_hi = self._step2_page_lo, self._step2_page_hi
            if p_hi < p_lo:
                p_lo, p_hi = p_hi, p_lo
            time.sleep(random.uniform(p_lo, p_hi))
            if self._step2_mouse_jitter:
                try:
                    self.human.move_mouse_randomly()
                except Exception:
                    pass

            main_handle = self.driver.current_window_handle

            # Debug logging for persistently failing jobs — helps diagnose what's in the page
            if job_id in DEBUG_JOB_IDS:
                try:
                    src = self.driver.page_source
                    all_urls = re.findall(r'https?://[^\s\'"<>\\]{10,120}', src)
                    external_urls = [u for u in all_urls if 'hiring.cafe' not in u.lower()][:15]
                    logger.info(f"[DEBUG {job_id}] Page source length: {len(src)}")
                    logger.info(f"[DEBUG {job_id}] External URLs in source: {external_urls}")
                    apply_variants = re.findall(r'["\'][^"\']{0,20}[Aa]pply[^"\']{0,20}["\']', src)[:5]
                    logger.info(f"[DEBUG {job_id}] Apply text variants: {apply_variants}")
                except Exception as de:
                    logger.debug(f"Debug logging failed: {de}")

            # ── Layer 1 + 2: DOM + page source (no clicks) ────────────────────
            ats_url = self._try_get_ats_url_from_dom()
            if ats_url and is_likely_ats_url(ats_url):
                platform = detect_ats_platform(ats_url) or "unknown"
                logger.info(f"[DOM/Regex] hiring_cafe_url: {job_url} -> ats_url: {ats_url}")
                return {
                    "ats_url": ats_url,
                    "ats_platform": platform,
                    "status": "success",
                    "error_detail": None
                }

            # ── Layer 3: Find Apply button (primary + fallbacks) and click ─────
            btn = self._find_apply_button()

            if btn:
                # Scroll button into view before clicking
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.5)
                except Exception:
                    pass

                # Click: normal first, then JS fallback
                clicked = False
                try:
                    self.actions.safe_click_element(btn)
                    clicked = True
                except Exception:
                    try:
                        self.driver.execute_script("arguments[0].click();", btn)
                        clicked = True
                    except Exception as e:
                        logger.warning(f"All click methods failed for {job_id}: {e}")

                if clicked:
                    # Wait for new tab with retry loop (up to 5s)
                    new_handles = []
                    for _ in range(5):
                        time.sleep(1)
                        handles = self.driver.window_handles
                        new_handles = [h for h in handles if h != main_handle]
                        if new_handles:
                            break

                    if new_handles:
                        # ── Layer 3a: New tab ─────────────────────────────────
                        try:
                            self.driver.switch_to.window(new_handles[0])
                            time.sleep(2)
                            try:
                                ats_url = self.driver.current_url
                            except Exception:
                                logger.debug("New tab closed itself before we could read URL")
                                try:
                                    self.driver.switch_to.window(main_handle)
                                except Exception:
                                    pass
                                ats_url = None

                            # Close the new tab if still open
                            if new_handles[0] in self.driver.window_handles:
                                try:
                                    self.driver.close()
                                except Exception:
                                    pass

                            # Always return to main window
                            try:
                                self.driver.switch_to.window(main_handle)
                            except Exception:
                                pass

                        except Exception as tab_err:
                            logger.debug(f"New tab handling error: {tab_err}")
                            ats_url = None
                            try:
                                handles = self.driver.window_handles
                                if handles:
                                    self.driver.switch_to.window(handles[0])
                            except Exception:
                                pass

                        if ats_url and is_likely_ats_url(ats_url):
                            platform = detect_ats_platform(ats_url) or "unknown"
                            logger.info(f"[NewTab] hiring_cafe_url: {job_url} -> ats_url: {ats_url}")
                            return {
                                "ats_url": ats_url,
                                "ats_platform": platform,
                                "status": "success",
                                "error_detail": None
                            }
                        elif ats_url:
                            logger.debug(f"Rejected new-tab URL: {ats_url}")
                            return {
                                "ats_url": None,
                                "ats_platform": None,
                                "status": "invalid_url",
                                "error_detail": f"Extracted URL failed validation: {ats_url}"
                            }
                    else:
                        # ── Layer 4: Same-tab redirect ────────────────────────
                        time.sleep(1)
                        current = self.driver.current_url
                        if "hiring.cafe" not in current.lower() and is_likely_ats_url(current):
                            platform = detect_ats_platform(current) or "unknown"
                            logger.info(f"[SameTab] hiring_cafe_url: {job_url} -> ats_url: {current}")
                            return {
                                "ats_url": current,
                                "ats_platform": platform,
                                "status": "success",
                                "error_detail": None
                            }

                        # ── Layer 5: Page source after click ──────────────────
                        time.sleep(2)
                        candidates = self._extract_ats_urls_from_page_source()
                        if candidates:
                            ats_url = candidates[0]
                            platform = detect_ats_platform(ats_url) or "unknown"
                            logger.info(f"[PostClick/Regex] hiring_cafe_url: {job_url} -> ats_url: {ats_url}")
                            return {
                                "ats_url": ats_url,
                                "ats_platform": platform,
                                "status": "success",
                                "error_detail": None
                            }
            else:
                logger.warning(f"Apply button not found for {job_id} (all XPaths failed)")
                return {
                    "ats_url": None,
                    "ats_platform": None,
                    "status": "no_apply_button",
                    "error_detail": "Apply button not found after trying all XPath selectors"
                }

            logger.info(f"[Failed] hiring_cafe_url: {job_url} -> ats_url: null")
            return {
                "ats_url": None,
                "ats_platform": None,
                "status": "retryable",
                "error_detail": "Click succeeded but no ATS URL found in any layer"
            }

        except TimeoutException as e:
            logger.warning(f"Timeout loading page for {job_id}: {e}")
            return {
                "ats_url": None,
                "ats_platform": None,
                "status": "timeout",
                "error_detail": f"Page load timeout: {str(e)[:200]}"
            }
        except WebDriverException as e:
            logger.error(f"Browser error for {job_id}: {e}")
            return {
                "ats_url": None,
                "ats_platform": None,
                "status": "browser_error",
                "error_detail": f"WebDriver error: {str(e)[:200]}"
            }
        except Exception as e:
            logger.error(f"Unexpected error getting ATS link for {job_id}: {e}", exc_info=True)
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception:
                pass
            return {
                "ats_url": None,
                "ats_platform": None,
                "status": "retryable",
                "error_detail": f"Unexpected error: {type(e).__name__}: {str(e)[:200]}"
            }

    # ─────────────────────────────────────────────────────────────────────────────
    # REST OF STRATEGY
    # ─────────────────────────────────────────────────────────────────────────────

    def enrich_jobs_with_ats_links(
        self,
        jobs: list[dict],
        limit: int | None = None,
        output_file: str | None = None,
    ) -> list[dict]:
        """
        Enrich jobs with ATS URLs.

        CHECKPOINT / RESUME SUPPORT
        ───────────────────────────
        • Jobs are mutated IN-PLACE so progress is never lost in memory.
        • After every single job the file is written to `output_file`.
        • On restart, jobs whose `ats_url` key already EXISTS are skipped
          automatically (both successful hits AND confirmed nulls).
        • Just re-run the same command after any crash or Ctrl-C to resume.
        """
        to_process = jobs[:limit] if limit is not None else jobs
        consecutive_failures = 0

        # ── Count resume state ───────────────────────────────────────────────
        # Skip jobs with permanent failures or successes, retry retryable ones
        PERMANENT_STATUSES = {"success", "no_apply_button"}  # Don't retry these

        def should_process(job):
            """Check if job needs processing or retry."""
            # Never attempted
            if "ats_extraction_status" not in job:
                return True

            status = job.get("ats_extraction_status")

            # Success or permanent failure - skip
            if status in PERMANENT_STATUSES:
                return False

            # Retryable failures - check attempt count
            attempt_count = job.get("ats_attempt_count", 0)
            if attempt_count >= 3:  # Max 3 attempts
                logger.debug(f"Skipping {job.get('job_id')}: max attempts reached ({attempt_count})")
                return False

            return True

        pending = [j for j in to_process if should_process(j)]
        already_done = len(to_process) - len(pending)

        if already_done:
            logger.info(
                "⏭️  Resuming: %d/%d jobs already processed/max-attempts, skipping them...",
                already_done, len(to_process),
            )
        logger.info("🔗 Step 2: Extracting ATS URLs for %d jobs (includes retries)...", len(pending))
        if self._step2_shuffle_pending and len(pending) > 1:
            random.shuffle(pending)
            logger.info("🔀 Shuffled %d pending jobs (HIRING_CAFE_STEP2_SHUFFLE_PENDING=1)", len(pending))

        for step_idx, job in enumerate(pending, start=1):
            jid = job.get("job_id") or job.get("external_id")
            if not jid:
                job.setdefault("ats_url", None)
                job.setdefault("ats_platform", None)
                continue

            hiring_cafe_url = (
                job.get("url")
                or job.get("hiring_cafe_url")
                or f"{self.base_url}/job/{jid}"
            )
            logger.info(f"Enriching job {step_idx}/{len(pending)}: {jid}")

            # ── Check Chrome is still alive before each job ───────────────
            if not self._is_session_alive():
                logger.warning("⚠️  Chrome session died — attempting restart...")
                try:
                    from core.browser import browser_service
                    browser_service.stop_browser()
                except Exception:
                    pass
                time.sleep(3)
                try:
                    from core.browser import browser_service
                    self.driver = browser_service.start_browser()
                    logger.info("✅ Browser restarted successfully")
                    consecutive_failures = 0
                except Exception as restart_err:
                    logger.critical("❌ Could not restart browser: %s", restart_err)
                    if output_file:
                        try:
                            self._write_jobs_payload(output_file, jobs)
                        except Exception:
                            pass
                    break

            ats = self._get_ats_link_from_job_page(jid)

            # Mutate job dict IN-PLACE — reflected immediately in `jobs`
            if ats:
                job["ats_url"]      = ats.get("ats_url")
                job["ats_platform"] = ats.get("ats_platform")
                job["ats_extraction_status"] = ats.get("status", "unknown")
                job["ats_error_detail"] = ats.get("error_detail")
                job["ats_attempt_count"] = job.get("ats_attempt_count", 0) + 1
                job["last_attempted_at"] = datetime.now().isoformat()

                if ats.get("status") == "success":
                    logger.info(f"  hiring_cafe_url: {hiring_cafe_url} -> ats_url: {ats['ats_url']}")
                    consecutive_failures = 0
                else:
                    logger.warning(f"  hiring_cafe_url: {hiring_cafe_url} -> status: {ats.get('status')} ({ats.get('error_detail')})")
                    consecutive_failures += 1
            else:
                # Legacy: old function returned None instead of dict
                job["ats_url"]      = None
                job["ats_platform"] = None
                job["ats_extraction_status"] = "retryable"
                job["ats_error_detail"] = "Extraction returned None (legacy path)"
                job["ats_attempt_count"] = job.get("ats_attempt_count", 0) + 1
                job["last_attempted_at"] = datetime.now().isoformat()
                logger.info(f"  hiring_cafe_url: {hiring_cafe_url} -> ats_url: null")
                consecutive_failures += 1

            # ── CHECKPOINT: save after every single job ──────────────────────
            if output_file:
                try:
                    self._write_jobs_payload(output_file, jobs)
                    logger.debug("💾 Checkpoint saved → %s", output_file)
                except Exception as save_err:
                    logger.warning("⚠️  Checkpoint save failed: %s", save_err)

            # ── Rate-limit protection ────────────────────────────────────────
            if consecutive_failures == 3:
                logger.warning("⚠️ 3 consecutive failures — cooling down 20s...")
                time.sleep(20)
                self.human.random_delay(3, 6)
            elif consecutive_failures >= 5:
                logger.warning(
                    "⚠️ %d consecutive failures — 40s cooldown + homepage reset...",
                    consecutive_failures,
                )
                try:
                    self.driver.get(self.base_url)
                    time.sleep(8)
                    self.human.random_delay(4, 10)
                except Exception:
                    pass
                time.sleep(40)
                consecutive_failures = 0
            elif (
                self._step2_break_every_n > 0
                and step_idx % self._step2_break_every_n == 0
            ):
                self._random_human_pause(
                    "step2 micro-break",
                    self._step2_long_break_lo,
                    self._step2_long_break_hi,
                )
            else:
                self._random_human_pause(
                    "between ATS jobs",
                    self._step2_pause_lo,
                    self._step2_pause_hi,
                )

        # Ensure jobs outside the limit window still have the key
        if limit is not None:
            for j in jobs[limit:]:
                j.setdefault("ats_url", None)
                j.setdefault("ats_platform", None)

        return jobs

    def enrich_jobs_with_ats_links_batched(
        self,
        jobs: list[dict],
        batch_size: int = 100,
        output_file: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        ordered = self._jobs_ordered_per_keyword(jobs)
        if limit is not None:
            ordered = ordered[:limit]
        total = len(ordered)
        logger.info("🔗 Enriching %d jobs in batches of %d (per-keyword order)", total, batch_size)
        consecutive_failures = 0

        for start in range(0, total, batch_size):
            batch = ordered[start: start + batch_size]
            batch_num = start // batch_size + 1
            max_batch = (total + batch_size - 1) // batch_size
            logger.info("📦 Batch %d/%d: jobs %d–%d", batch_num, max_batch, start + 1, start + len(batch))
            try:
                for i, job in enumerate(batch):
                    jid = job.get("job_id") or job.get("external_id")
                    if not jid:
                        continue
                    hiring_cafe_url = job.get("url") or job.get("hiring_cafe_url") or f"{self.base_url}/job/{jid}"
                    ats = self._get_ats_link_from_job_page(jid)
                    job["ats_url"] = ats["ats_url"] if ats else None
                    job["ats_platform"] = ats["ats_platform"] if ats else None

                    if ats:
                        logger.info("  hiring_cafe_url: %s -> ats_url: %s", hiring_cafe_url, ats["ats_url"])
                        consecutive_failures = 0
                    else:
                        logger.info("  hiring_cafe_url: %s -> ats_url: null", hiring_cafe_url)
                        consecutive_failures += 1

                    if consecutive_failures == 3:
                        logger.warning("⚠️ 3 consecutive failures — cooling down 20s...")
                        time.sleep(20)
                        self.human.random_delay(3, 6)
                    elif consecutive_failures >= 5:
                        logger.warning("⚠️ %d consecutive failures — 40s cooldown + homepage reset...", consecutive_failures)
                        try:
                            self.driver.get(self.base_url)
                            time.sleep(5)
                            self.human.random_delay(3, 6)
                        except Exception:
                            pass
                        time.sleep(40)
                        consecutive_failures = 0
                    else:
                        self._random_human_pause(
                            "between ATS jobs",
                            self._step2_pause_lo,
                            self._step2_pause_hi,
                        )

                if output_file:
                    self._write_jobs_payload(output_file, jobs)
            except BaseException:
                logger.warning("⚠️ Batch %d interrupted; saving current state.", batch_num)
                if output_file:
                    self._write_jobs_payload(output_file, jobs)
                raise
        return jobs

    def _is_page_blocked(self) -> bool:
        """
        Detect if hiring.cafe returned a Cloudflare challenge or empty React shell.

        Detection layers:
          1. Cloudflare Turnstile challenge strings in page source (primary — catches new CF challenges)
          2. Page title contains 'just a moment' or 'security check'
          3. Known blocked page source sizes (legacy)
          4. Known blocked div/link count fingerprints (legacy)
        """
        try:
            src = self.driver.page_source
            src_lower = src.lower()
            src_len = len(src)

            # ── Layer 1: Cloudflare Turnstile / challenge strings ────────────────
            cf_signals = [
                "verify you are human",
                "cf-turnstile",
                "challenges.cloudflare.com",
                "performing security verification",
                "ray id:",
                "cloudflare ray id",
                "enable javascript and cookies",
                "one more step",
                "checking your browser",
            ]
            for signal in cf_signals:
                if signal in src_lower:
                    logger.warning(
                        "⚠️ Cloudflare challenge detected: page contains '%s' (source len=%d)",
                        signal, src_len,
                    )
                    return True

            # ── Layer 2: Page title check ────────────────────────────────────────
            try:
                title = self.driver.title.lower()
                if any(t in title for t in ["just a moment", "security check", "attention required", "cloudflare"]):
                    logger.warning("⚠️ Cloudflare challenge detected via page title: '%s'", self.driver.title)
                    return True
            except Exception:
                pass

            # ── Layer 3: Known blocked page source sizes (legacy) ────────────────
            blocked_sizes = locators.get("blocked_thresholds", "page_sizes", [])
            if src_len in blocked_sizes:
                logger.warning("⚠️ Blocked page detected: source length %d matches known blocked fingerprint", src_len)
                return True

            if src_len < 70000:
                logger.debug("Detected suspicious small page source: %d chars", src_len)

            # ── Layer 4: Known blocked div/link count fingerprints (legacy) ──────
            try:
                div_count = len(self.driver.find_elements(By.CSS_SELECTOR, "div"))
                link_count = len(self.driver.find_elements(By.CSS_SELECTOR, "a"))
                blocked_divs = locators.get("blocked_thresholds", "div_counts", [])
                blocked_links = locators.get("blocked_thresholds", "link_count")
                if div_count in blocked_divs and link_count == blocked_links:
                    logger.warning(
                        "⚠️ Blocked page detected: divs=%d, links=%d matches blocked fingerprint",
                        div_count, link_count,
                    )
                    return True
            except Exception:
                pass

        except Exception as e:
            logger.debug("Error checking for blocked page: %s", e)
        return False

    def _wait_for_jobs_to_load(self, timeout: int = 15) -> bool:
        """
        Wait until we are on hiring.cafe AND job links appear in the DOM.
        Tries both relative (href^=/viewjob/) and absolute (href*=/viewjob/) selectors.
        """
        current_url = self.driver.current_url
        if "hiring.cafe" not in current_url.lower():
            logger.warning(
                "⚠️  Browser is NOT on hiring.cafe (current: %s). "
                "Navigation may have failed.", current_url
            )
            return False

        # Try primary selector from config (contains /viewjob/)
        selector = locators.get("selectors", "job_link")
        fallback_selectors = [
            selector,
            'a[href*="/job/"]',                           # new format (primary)
            'a[href*="/viewjob/"]',                       # legacy format fallback
            'a[href^="https://hiring.cafe/job/"]',        # fully-qualified new
            'a[href^="https://hiring.cafe/viewjob/"]',    # fully-qualified legacy
        ]
        for sel in fallback_selectors:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                logger.info("✅ Job content detected on page (selector: %s)", sel)
                return True
            except TimeoutException:
                logger.debug("Selector did not find jobs within %ds: %s", timeout, sel)
                timeout = 5  # reduce timeout for subsequent fallback attempts

        # Debug: log what links ARE on the page to diagnose selector drift
        try:
            all_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href]")
            sample_hrefs = [el.get_attribute("href") for el in all_links[:10]]
            logger.warning("🔍 No job links found. Sample <a href> on page: %s", sample_hrefs)
            src_len = len(self.driver.page_source)
            logger.warning("🔍 Page source length: %d chars", src_len)
        except Exception as dbg_err:
            logger.debug("Debug link scan failed: %s", dbg_err)

        return False

    def find_jobs_for_keyword(self, keyword: str, max_retries: int = 5) -> list[dict]:
        """
        Navigate to search URL, wait for React hydration, scroll to end, extract jobs.

        CHANGES vs original:
        - max_retries increased from 3 → 5
        - PRE-WARM step: visits homepage before first search to build a real session
        - Initial wait increased from 4s → 10s + random_delay(4, 7)
        - Homepage reset wait increased from 3s → 8s + random_delay(4, 8)
        - Cooldown formula changed to 20 + (attempt * 15) for longer backoffs
        """
        search_url = _build_search_url(keyword, self.base_url, self._date_fetched_past_n_days)

        # ── PRE-WARM: Visit homepage first so Chrome builds a real session ──────
        # Cold Chrome jumping straight to a search URL is a bot fingerprint.
        # Visiting homepage first mimics real user behaviour and reduces blocking.
        try:
            logger.info("🏠 Pre-warming session via homepage...")
            self.driver.get(self.base_url)
            time.sleep(2)
            self._random_human_pause("homepage read")
            # Scroll a little to simulate reading
            self.driver.execute_script("window.scrollTo(0, 300);")
            self.human.random_delay(1, 2)
            logger.info("✅ Pre-warm complete")
        except Exception as e:
            logger.warning(f"Pre-warm failed (non-fatal): {e}")

        for attempt in range(1, max_retries + 1):
            try:
                logger.info("🌐 Keyword %r (attempt %d/%d) -> %s", keyword, attempt, max_retries, search_url)

                # Reset session: go to homepage first, then navigate to search
                # This mimics a real user browsing pattern and avoids rate-limit on direct URL jumps
                if attempt > 1:
                    logger.info("🏠 Resetting via homepage before retry...")
                    self.driver.get(self.base_url)
                    time.sleep(2)
                    self._random_human_pause("retry homepage")

                self.driver.get(search_url)

                time.sleep(2)
                self._random_human_pause("search results load")

                # Verify we actually landed on hiring.cafe
                actual_url = self.driver.current_url
                if "hiring.cafe" not in actual_url.lower():
                    logger.warning(
                        "⚠️  Navigation landed on wrong page: %s — retrying...", actual_url
                    )
                    time.sleep(2)
                    self.driver.get(search_url)
                    time.sleep(5)
                    actual_url = self.driver.current_url
                    if "hiring.cafe" not in actual_url.lower():
                        logger.error(
                            "❌ Still not on hiring.cafe after retry (at: %s)", actual_url
                        )
                        if attempt < max_retries:
                            time.sleep(5)
                            continue
                        return []
                    logger.info("✅ Navigation succeeded on retry → %s", actual_url)

                # Check for blocked/empty page
                if self._is_page_blocked():
                    logger.warning(
                        "⚠️ Blocked/empty page detected for keyword %r (attempt %d). "
                        "Waiting before retry...", keyword, attempt
                    )
                    if attempt < max_retries:
                        # FIX: longer cooldowns — 35s, 50s, 65s, 80s
                        cooldown = 20 + (attempt * 15)
                        logger.info("⏳ Cooldown %ds before retry...", cooldown)
                        time.sleep(cooldown)
                        continue
                    else:
                        logger.error("❌ All %d attempts blocked for keyword %r", max_retries, keyword)
                        return []

                # Wait for job links to actually appear in DOM
                jobs_loaded = self._wait_for_jobs_to_load(timeout=15)
                if not jobs_loaded:
                    logger.warning("⚠️ No job links appeared within timeout for %r", keyword)
                    if attempt < max_retries:
                        time.sleep(10)
                        continue
                    return []

                # Scroll to load all jobs (random delay between scroll steps is inside _scroll_until_end)
                self._scroll_until_end(max_scrolls=100)
                jobs = self._extract_job_listings()
                logger.info("✅ Keyword %r: %d jobs", keyword, len(jobs))
                return jobs

            except Exception as e:
                logger.error("❌ Error for keyword %r (attempt %d): %s", keyword, attempt, e)
                import traceback
                traceback.print_exc()
                if not self._is_session_alive():
                    logger.error("❌ Chrome session is dead — browser was closed. Stopping.")
                    return []
                if attempt < max_retries:
                    time.sleep(10)

        return []

    @staticmethod
    def _matches_keyword_filter(job: dict, keyword: str) -> bool:
        """
        Client-side boolean title filter with word-boundary matching.
        """
        title_text = (job.get("job_tittle") or job.get("title") or "").lower()
        if not title_text:
            return True  # can't filter — let it through

        def _word_present(term: str, text: str) -> bool:
            t = re.escape(term.lower())
            pattern = r'(?<![a-z0-9])' + t + r'(?![a-z0-9])'
            return bool(re.search(pattern, text, re.IGNORECASE))

        kw_upper = keyword.upper()
        not_terms: list[str] = []
        and_part = keyword
        if " NOT " in kw_upper:
            not_idx = kw_upper.index(" NOT ")
            not_clause = keyword[not_idx + 5:].strip()
            and_part   = keyword[:not_idx].strip()
            not_terms = [
                t.strip()
                for t in re.split(r'\b(?:AND|\+)\b', not_clause, flags=re.IGNORECASE)
                if t.strip()
            ]

        and_terms = [
            t.strip()
            for t in re.split(r'\b(?:AND|\+)\b', and_part, flags=re.IGNORECASE)
            if t.strip()
        ]

        for term in and_terms:
            if not _word_present(term, title_text):
                return False

        for term in not_terms:
            if _word_present(term, title_text):
                return False

        return True

    def _merge_jobs_unique(self, keyword_job_lists: list[tuple[str, list[dict]]]) -> list[dict]:
        by_id = {}
        for keyword, lst in keyword_job_lists:
            for j in lst:
                jid = j.get("job_id") or j.get("external_id")
                if not jid:
                    continue
                if jid not in by_id:
                    by_id[jid] = {**j, "source_keywords": [keyword]}
                else:
                    if keyword not in by_id[jid].get("source_keywords", []):
                        by_id[jid].setdefault("source_keywords", []).append(keyword)
        return list(by_id.values())

    def _jobs_ordered_per_keyword(self, jobs: list[dict]) -> list[dict]:
        order = []
        seen_ids = set()
        for keyword in self._search_keywords:
            for j in jobs:
                jid = j.get("job_id") or j.get("external_id")
                if not jid or jid in seen_ids:
                    continue
                if keyword in (j.get("source_keywords") or []):
                    order.append(j)
                    seen_ids.add(jid)
        for j in jobs:
            jid = j.get("job_id") or j.get("external_id")
            if jid and jid not in seen_ids:
                order.append(j)
                seen_ids.add(jid)
        return order

    def find_jobs(self) -> list[dict]:
        if len(self._search_keywords) == 1:
            kw = self._search_keywords[0]
            jobs = self.find_jobs_for_keyword(kw)
            for j in jobs:
                j["source_keywords"] = [kw]
            before = len(jobs)
            jobs = [j for j in jobs if self._matches_keyword_filter(j, kw)]
            dropped = before - len(jobs)
            if dropped:
                logger.info("🔍 Title filter dropped %d irrelevant jobs for keyword %r", dropped, kw)
            return jobs

        keyword_job_lists = []
        for i, keyword in enumerate(self._search_keywords):
            jobs = self.find_jobs_for_keyword(keyword)
            before = len(jobs)
            jobs = [j for j in jobs if self._matches_keyword_filter(j, keyword)]
            dropped = before - len(jobs)
            if dropped:
                logger.info(
                    "🔍 Title filter dropped %d irrelevant jobs for keyword %r (%d kept)",
                    dropped, keyword, len(jobs)
                )
            keyword_job_lists.append((keyword, jobs))
            if i < len(self._search_keywords) - 1:
                self._random_human_pause("next keyword")
        merged = self._merge_jobs_unique(keyword_job_lists)
        logger.info("✅ Unique jobs across all keywords: %d", len(merged))
        return merged

    def apply(self, listing: dict):
        logger.warning("⚠️ Apply functionality not implemented for Hiring Cafe")
        return False

    def _write_jobs_payload(self, output_file: str, jobs: list) -> None:
        """
        Save jobs to file in the FLAT format used by Step 2 and Step 3.
        """
        if not jobs:
            return
        try:
            tmp = output_file + ".tmp"
            payload = {
                "source": "hiring.cafe",
                "step": 2,
                "updated": datetime.now().isoformat(),
                "count": len(jobs),
                "jobs": [
                    {
                        "job_id": j.get("job_id"),
                        "title": j.get("title"),
                        "hiring_cafe_url": j.get("hiring_cafe_url") or j.get("url") or f"https://hiring.cafe/job/{j.get('job_id')}",
                        "ats_url": j.get("ats_url"),
                        "ats_platform": j.get("ats_platform"),
                        "source_keywords": j.get("source_keywords"),
                        "scraped_at": j.get("scraped_at"),
                        "job_tittle": j.get("job_tittle"),
                        "location": j.get("location"),
                        "company": j.get("company"),
                        "type": j.get("type"),
                        "city": j.get("city"),
                        "state": j.get("state"),
                        "country": j.get("country"),
                        "company_description": j.get("company_description")
                    }
                    for j in jobs
                ],
            }
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            import os as _os
            _os.replace(tmp, output_file)
            logger.info("💾 Saved %d jobs to %s", len(jobs), output_file)
        except Exception as e:
            logger.error("❌ Error saving to file: %s", e)

    def scrape_and_save(
        self,
        output_file=None,
        enrich_ats: bool = False,
        enrich_ats_limit: int | None = None,
        job_limit: int | None = None,
        ats_batch_size: int = 100,
    ):
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"hiring_cafe_jobs_{timestamp}.json"

        logger.info("🚀 Phase 1: Infinite scroll per keyword, collect unique jobs...")
        if job_limit is not None:
            logger.info("🧪 Test mode: limiting to %d jobs", job_limit)

        jobs = self.find_jobs()

        if job_limit is not None and jobs:
            jobs = jobs[:job_limit]
            logger.info("📋 Using first %d jobs (test limit)", len(jobs))

        self._write_jobs_payload(output_file, jobs)

        if enrich_ats and jobs:
            logger.info("🔗 Phase 2: Enrich in batches of %d (per-keyword order)...", ats_batch_size)
            try:
                self.enrich_jobs_with_ats_links_batched(
                    jobs,
                    batch_size=ats_batch_size,
                    output_file=output_file,
                    limit=enrich_ats_limit,
                )
                self._write_jobs_payload(output_file, jobs)
            except BaseException:
                logger.warning("⚠️ Enrichment interrupted; current state saved to JSON.")
                self._write_jobs_payload(output_file, jobs)
                raise

        if not jobs:
            logger.warning("⚠️ No jobs found to save")
        return jobs
