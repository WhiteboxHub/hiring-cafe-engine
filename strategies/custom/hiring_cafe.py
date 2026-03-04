# from strategies.base import BaseStrategy
# from core.logger import logger
# from core.human_behavior import HumanBehavior
# from core.safe_actions import SafeActions
# import json
# import os
# import re
# import time
# from datetime import datetime
# from urllib.parse import quote
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException, NoSuchElementException
# from models.config_models import JobListing

# # Hiring Cafe job link: <a href="/viewjob/{job_id}">...</a>
# JOB_LINK_SELECTOR = 'a[href^="/viewjob/"]'

# # Apply now button on job page (opens ATS in new tab)
# APPLY_NOW_BUTTON_XPATH = """
# //button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]
# | //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply') and not(contains(@href, 'hiring.cafe'))]
# """

# # URL host/path patterns -> ATS platform name (lowercase)
# ATS_PLATFORM_PATTERNS = [
#     (r"lever\.co|jobs\.lever\.", "lever"),
#     (r"greenhouse\.io|boards\.greenhouse|jobs\.greenhouse", "greenhouse"),
#     (r"sapsf\.com|successfactors\.com", "successfactors"),  # SAP SuccessFactors (sapsf = same ATS)
#     (r"workday\.com", "workday"),
#     (r"adp\.com|workforcenow\.adp\.com", "adp"),
#     (r"ashhq\.by|ashhqby", "ashhqby"),
#     (r"smartrecruiters\.com", "smartrecruiters"),
#     (r"icims\.com", "icims"),
#     (r"jobvite\.com", "jobvite"),
#     (r"taleo\.net|taleocdn", "taleo"),
#     (r"myworkdayjobs\.com", "workday"),
#     (r"apply\.workable\.com|workable\.com", "workable"),
#     (r"bamboohr\.com", "bamboohr"),
#     (r"paycom\.com", "paycom"),
#     (r"paychex\.com|myapps\.paychex\.com", "paychex"),
#     (r"ultipro\.com", "ultipro"),
#     (r"linkedin\.com/jobs", "linkedin"),
#     (r"indeed\.com", "indeed"),
#     (r"ashbyhq\.com", "ashby"),
#     (r"recruitee\.com", "recruitee"),
#     (r"teamtailor\.com", "teamtailor"),
#     (r"personio\.com", "personio"),
#     (r"oraclecloud\.com", "oraclecloud"),
#     (r"applytojob\.com", "applytojob"),
#     (r"brassring\.com", "brassring"),
#     (r"rippling\.com", "rippling"),
# ]


# def _job_id_from_href(href: str) -> str | None:
#     """Extract job ID from href like '/viewjob/p16gu5rnyh9yhp7v'."""
#     if not href:
#         return None
#     match = re.search(r"/viewjob/([a-zA-Z0-9_-]+)", href)
#     return match.group(1) if match else None


# def _load_hiring_cafe_config() -> dict:
#     """Load Hiring Cafe config from config/hiring_cafe.json. Returns {} if missing."""
#     try:
#         config_path = os.path.join(
#             os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
#             "config",
#             "hiring_cafe.json",
#         )
#         if os.path.isfile(config_path):
#             with open(config_path, "r", encoding="utf-8") as f:
#                 return json.load(f)
#     except Exception as e:
#         logger.warning(f"Could not load hiring_cafe config: {e}")
#     return {}


# # Date filter: dateFetchedPastNDays in searchState (default 2 = 24 hours)
# DATE_FETCHED_PRESETS = {
#     "today": 2,
#     "24h": 2,   # 24 hours
#     "3d": 4,    # 3 days
#     "1w": 14,   # 1 week
#     "2w": 21,   # 2 weeks
#     "all": -1,  # All time
# }


# def _parse_date_fetched_past_n_days(value) -> int:
#     """Parse config value to dateFetchedPastNDays. Presets: 24h=2, 3d=4, 1w=14, 2w=21, all=-1. Default 2 (24h)."""
#     if value is None:
#         return 2
#     if isinstance(value, int):
#         return value
#     s = str(value).strip().lower()
#     if s in DATE_FETCHED_PRESETS:
#         return DATE_FETCHED_PRESETS[s]
#     try:
#         return int(value)
#     except (TypeError, ValueError):
#         return 2


# def _normalize_search_keyword(keyword: str) -> str:
#     """Use + for spaces in searchQuery (e.g. 'AI Engineer' -> 'AI+Engineer'). Hiring.cafe expects AI+Engineer (encoded as AI%2BEngineer in URL)."""
#     if not keyword:
#         return keyword
#     s = keyword.strip()
#     if " " in s and "+" not in s:
#         s = s.replace(" ", "+")
#     return s


# def _build_search_url(
#     keyword: str,
#     base_url: str = "https://hiring.cafe",
#     date_fetched_past_n_days: int = 2,
# ) -> str:
#     """Build hiring.cafe search URL. searchState = {"searchQuery": "AI+Engineer", "dateFetchedPastNDays": N}; + is encoded as %2B."""
#     search_query = _normalize_search_keyword(keyword)
#     search_state = json.dumps({
#         "searchQuery": search_query,
#         "dateFetchedPastNDays": date_fetched_past_n_days,
#     })
#     encoded = quote(search_state, safe="")
#     return f"{base_url}/?searchState={encoded}"


# def detect_ats_platform(url: str) -> str | None:
#     """
#     Detect ATS platform from URL (e.g. lever, greenhouse, successfactors, workday, ashhqby).
#     Returns platform name or None if unknown.
#     """
#     if not url:
#         return None
#     url_lower = url.lower()
#     for pattern, platform in ATS_PLATFORM_PATTERNS:
#         if re.search(pattern, url_lower):
#             return platform
#     return None


# # Domains that are NOT job application (ATS) URLs - reject these when resolving Apply link
# NON_ATS_URL_DOMAINS = (
#     "reddit.com",
#     "twitter.com",
#     "x.com",
#     "facebook.com",
#     "linkedin.com/share",
#     "linkedin.com/feed",
#     "t.co",
#     "wa.me",
#     "telegram.me",
#     "whatsapp.com",
# )


# def is_likely_ats_url(url: str) -> bool:
#     """
#     Return True only if url looks like a job/application URL. Rejects Reddit, social sharing, etc.
#     """
#     if not url or not url.strip().startswith("http"):
#         return False
#     url_lower = url.lower().strip()
#     if "hiring.cafe" in url_lower:
#         return False
#     for domain in NON_ATS_URL_DOMAINS:
#         if domain in url_lower:
#             return False
#     # Known ATS platform -> accept
#     if detect_ats_platform(url):
#         return True
#     # Heuristic: job/apply/careers paths often indicate ATS (reject generic external links)
#     if any(p in url_lower for p in ("/job", "/jobs", "/career", "/apply", "/opportunity", "jobdetail", "jobboard", "opening", "openings", "opportunity", "opportunities", "req", "requisition", "vacancy")):
#         return True
#     return False


# def categorize_jobs_by_ats(jobs: list[dict]) -> dict[str, list[dict]]:
#     """
#     Group jobs by ATS platform. Each group is a list of entries with
#     job_id, title, job_posting_url, ats: { url, platform }. Keys are platform names; "unknown" for null/missing.
#     """
#     by_platform = {}
#     for j in jobs:
#         ats_obj = j.get("ats")
#         if isinstance(ats_obj, dict):
#             platform = (ats_obj.get("platform") or "unknown").strip() or "unknown"
#             ats_url = ats_obj.get("url")
#         else:
#             platform = (j.get("ats_platform") or "unknown").strip() or "unknown"
#             ats_url = j.get("ats_url")
#         job_posting_url = j.get("url") or j.get("job_posting_url") or j.get("hiring_cafe_url")
#         entry = {
#             "job_id": j.get("job_id"),
#             "title": j.get("title"),
#             "job_posting_url": job_posting_url,
#             "ats": {"url": ats_url, "platform": platform},
#         }
#         if platform not in by_platform:
#             by_platform[platform] = []
#         by_platform[platform].append(entry)
#     return by_platform


# class HiringCafeStrategy(BaseStrategy):
#     """
#     Hiring Cafe scraper strategy.
    
#     Features:
#     - Infinite scroll to load all job positions
#     - Extracts job listings from the search results
#     - Can be run standalone for scraping only
#     """
    
#     def __init__(self, driver, job_site=None, selectors=None, db_session=None, date_filter_override=None):
#         config = _load_hiring_cafe_config()
#         # Keywords: prefer config/hiring_cafe.json (search_keywords list, then search_keyword), then env, then default
#         if config.get("search_keywords"):
#             keywords = [str(k).strip() for k in config["search_keywords"] if str(k).strip()]
#         elif config.get("search_keyword"):
#             keywords = [str(config["search_keyword"]).strip()]
#         else:
#             env_kw = os.environ.get("HIRING_CAFE_SEARCH_KEYWORD", "").strip()
#             keywords = [env_kw] if env_kw else ["AI"]
#         self._search_keywords = keywords if keywords else ["AI"]
#         self._date_fetched_past_n_days = (
#             _parse_date_fetched_past_n_days(date_filter_override)
#             if date_filter_override is not None
#             else _parse_date_fetched_past_n_days(
#                 config.get("date_fetched_past_n_days") or config.get("date_filter") or 2
#             )
#         )
#         base_url = "https://hiring.cafe"
#         search_url = _build_search_url(
#             self._search_keywords[0], base_url, self._date_fetched_past_n_days
#         )

#         # Allow initialization without job_site for standalone use
#         if job_site is None:
#             class MinimalJobSite:
#                 def __init__(self, url_template):
#                     self.company_name = "Hiring Cafe"
#                     self.search_url_template = url_template
#             job_site = MinimalJobSite(search_url)

#         super().__init__(driver, job_site, selectors or {})
#         self.db_session = db_session
#         self.human = HumanBehavior(driver)
#         self.base_url = base_url
#         self.search_url = search_url

#         logger.info(
#             "✅ HiringCafeStrategy initialized (keywords=%s, date_fetched_past_n_days=%s)",
#             self._search_keywords,
#             self._date_fetched_past_n_days,
#         )
    
#     def login(self):
#         """
#         Hiring Cafe doesn't require login for viewing jobs.
#         Returns True to indicate success.
#         """
#         logger.info("ℹ️ No login required for Hiring Cafe")
#         return True
    
#     def _scroll_to_bottom(self):
#         """Scroll to the bottom of the page"""
#         self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         time.sleep(1)  # Wait for content to load
    
#     def _get_viewjob_links(self):
#         """Find all visible 'Job Posting' links with href /viewjob/{id}."""
#         try:
#             links = self.driver.find_elements(By.CSS_SELECTOR, JOB_LINK_SELECTOR)
#             return [el for el in links if el.is_displayed()]
#         except Exception as e:
#             logger.warning(f"Error finding viewjob links: {e}")
#             return []

#     def _get_unique_job_ids(self) -> set[str]:
#         """Return set of unique job IDs currently visible on the page."""
#         ids = set()
#         for link in self._get_viewjob_links():
#             href = link.get_attribute("href") or ""
#             job_id = _job_id_from_href(href)
#             if job_id:
#                 ids.add(job_id)
#         return ids

#     def _get_current_job_count(self) -> int:
#         """
#         Count unique job listings via a[href^="/viewjob/"] links.
#         """
#         return len(self._get_unique_job_ids())
    
#     def _debug_page_structure(self):
#         """
#         Debug method to print page structure for troubleshooting.
#         Useful when selectors don't match the actual page structure.
#         """
#         logger.info("🔍 Analyzing page structure for debugging...")
#         try:
#             # Get page source length
#             page_source_length = len(self.driver.page_source)
#             logger.info(f"Page source length: {page_source_length} characters")
            
#             # Count common elements
#             element_counts = {}
#             test_selectors = [
#                 ("articles", "article"),
#                 ("divs", "div"),
#                 ("links", "a"),
#                 ("cards", "[class*='card']"),
#                 ("jobs", "[class*='job']"),
#                 ("listings", "[class*='listing']"),
#             ]
            
#             for name, selector in test_selectors:
#                 try:
#                     count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
#                     element_counts[name] = count
#                 except Exception:
#                     element_counts[name] = 0
            
#             logger.info(f"Element counts: {element_counts}")
            
#             # Try to find any links with job-related text
#             try:
#                 all_links = self.driver.find_elements(By.TAG_NAME, "a")
#                 job_related_links = [
#                     link for link in all_links 
#                     if link.is_displayed() and any(
#                         keyword in link.text.lower() or keyword in link.get_attribute("href", "").lower()
#                         for keyword in ["job", "position", "career", "apply", "hiring"]
#                     )
#                 ]
#                 logger.info(f"Found {len(job_related_links)} links with job-related keywords")
                
#                 if job_related_links:
#                     logger.info("Sample link texts:")
#                     for link in job_related_links[:5]:
#                         logger.info(f"  - {link.text[:50]} | {link.get_attribute('href')[:80]}")
#             except Exception as e:
#                 logger.debug(f"Error analyzing links: {e}")
                
#         except Exception as e:
#             logger.warning(f"Error in debug_page_structure: {e}")
    
#     def _scroll_until_end(self, max_scrolls=100, scroll_delay=2):
#         """
#         Scroll until no more jobs are loading.
        
#         Args:
#             max_scrolls: Maximum number of scroll attempts
#             scroll_delay: Delay between scrolls in seconds
            
#         Returns:
#             True if scrolling completed, False if max scrolls reached
#         """
#         logger.info("🔄 Starting infinite scroll to load all positions...")
        
#         previous_count = 0
#         no_change_count = 0
#         scroll_attempts = 0
        
#         while scroll_attempts < max_scrolls:
#             # Get current job count
#             current_count = self._get_current_job_count()
#             logger.info(f"📊 Current job count: {current_count} (scroll attempt {scroll_attempts + 1}/{max_scrolls})")
            
#             # If count hasn't changed after multiple scrolls, we're done
#             if current_count == previous_count:
#                 no_change_count += 1
#                 if no_change_count >= 3:  # No change for 3 consecutive scrolls
#                     logger.info(f"✅ No new jobs loaded after {no_change_count} scrolls. Reached end.")
#                     return True
#             else:
#                 no_change_count = 0  # Reset counter when new jobs appear
            
#             previous_count = current_count
            
#             # Scroll down
#             last_height = self.driver.execute_script("return document.body.scrollHeight")
#             self._scroll_to_bottom()
            
#             # Wait for new content to potentially load
#             time.sleep(scroll_delay)
            
#             # Check if page height changed (new content loaded)
#             new_height = self.driver.execute_script("return document.body.scrollHeight")
#             if new_height == last_height:
#                 # Try scrolling a bit more to trigger lazy loading
#                 self.driver.execute_script("window.scrollBy(0, 500);")
#                 time.sleep(1)
            
#             scroll_attempts += 1
            
#             # Human-like delay
#             self.human.random_delay(0.5, 1.5)
        
#         logger.warning(f"⚠️ Reached maximum scroll attempts ({max_scrolls}). Stopping.")
#         return False
    
#     def extract_all_job_ids(self) -> list[str]:
#         """
#         Extract all unique job IDs from the current page (a[href^="/viewjob/"]).
#         Call after scrolling to end to get the full list.
#         """
#         return sorted(self._get_unique_job_ids())

#     def _extract_job_listings(self):
#         """
#         Extract job listings using a[href^="/viewjob/"] links.
#         Each link gives job_id from href; url is base_url + href.
#         """
#         jobs = []
#         logger.info("🔍 Extracting job listings via viewjob links...")
        
#         try:
#             seen_ids = set()
#             for link in self._get_viewjob_links():
#                 try:
#                     href = link.get_attribute("href") or ""
#                     job_id = _job_id_from_href(href)
#                     if not job_id or job_id in seen_ids:
#                         continue
#                     seen_ids.add(job_id)
                    
#                     url = href if href.startswith("http") else (self.base_url + (href if href.startswith("/") else "/" + href))
                    
#                     # Optional: try to get title from parent container
#                     title = None
#                     try:
#                         parent = link.find_element(By.XPATH, "./ancestor::*[self::article or self::div][position()<=3]")
#                         raw = (parent.text or "").strip()
#                         if raw and "Job Posting" in raw:
#                             title = raw.replace("Job Posting", "").strip()[:200] or None
#                     except Exception:
#                         pass
#                     if not title:
#                         title = f"Job {job_id}"
                    
#                     job_data = {
#                         "job_id": job_id,
#                         "external_id": job_id,
#                         "title": title,
#                         "url": url,
#                         "company": None,
#                         "location": None,
#                         "scraped_at": datetime.now().isoformat(),
#                     }
#                     jobs.append(job_data)
#                 except Exception as e:
#                     logger.warning(f"Error extracting from link: {e}")
#                     continue
            
#             logger.info(f"✅ Extracted {len(jobs)} unique job listings (job IDs)")
#             return jobs
            
#         except Exception as e:
#             logger.error(f"❌ Error extracting job listings: {e}")
#             import traceback
#             traceback.print_exc()
#             return []

#     def _try_get_ats_url_from_dom(self) -> str | None:
#         """
#         Try to get ATS URL from the job page DOM without clicking (e.g. from a wrapper <a>
#         or nearby external link). Returns URL string or None.
#         """
#         try:
#             buttons = self.driver.find_elements(By.XPATH, APPLY_NOW_BUTTON_XPATH)
#             if not buttons:
#                 return None
#             btn = buttons[0]

#             def is_external(url: str) -> bool:
#                 if not url or not url.strip().startswith("http"):
#                     return False
#                 return "hiring.cafe" not in url.lower()

#             def accept_url(href: str) -> bool:
#                 return is_external(href) and is_likely_ats_url(href)

#             # 1) Ancestor <a href="..."> wrapping the button
#             try:
#                 parent = btn
#                 for _ in range(10):
#                     parent = parent.find_element(By.XPATH, "..")
#                     tag = parent.tag_name.lower()
#                     if tag == "a":
#                         href = parent.get_attribute("href")
#                         if accept_url(href):
#                             return href.strip()
#                         break
#                     if tag == "body":
#                         break
#             except Exception:
#                 pass

#             # 2) Sibling or following <a> with external href (e.g. next to button)
#             try:
#                 container = btn.find_element(By.XPATH, "..")
#                 for a in container.find_elements(By.TAG_NAME, "a"):
#                     href = a.get_attribute("href")
#                     if accept_url(href):
#                         return href.strip()
#             except Exception:
#                 pass

#             # 3) In the same section as the button: <a target="_blank"> or "apply" in text (must be ATS-like)
#             try:
#                 root = btn
#                 for _ in range(8):
#                     root = root.find_element(By.XPATH, "..")
#                     for a in root.find_elements(By.CSS_SELECTOR, 'a[href^="http"]'):
#                         href = a.get_attribute("href")
#                         if not accept_url(href):
#                             continue
#                         target = (a.get_attribute("target") or "").lower()
#                         rel = (a.get_attribute("rel") or "").lower()
#                         text = (a.text or "").lower()
#                         if "apply" in text or target == "_blank" or "noopener" in rel:
#                             return href.strip()
#             except Exception:
#                 pass

#             return None
#         except Exception as e:
#             logger.debug(f"DOM ATS URL extraction failed: {e}")
#             return None

#     def _get_ats_link_from_job_page(self, job_id: str) -> dict | None:
#         """
#         Open job page, get ATS URL from Apply button link if visible in DOM; otherwise
#         click Apply now and capture ATS URL from new tab. Rejects non-ATS URLs (e.g. Reddit).
#         Returns {"ats_url": str, "ats_platform": str} or None if failed.
#         """
#         job_url = f"{self.base_url}/viewjob/{job_id}"
#         try:
#             self.driver.get(job_url)
#             time.sleep(2)
#             self.human.random_delay(1, 2)

#             main_handle = self.driver.current_window_handle

#             # Try to get ATS URL from DOM first (wrapper <a> or nearby external link; already filtered to ATS-like)
#             ats_url_from_dom = self._try_get_ats_url_from_dom()
#             if ats_url_from_dom and is_likely_ats_url(ats_url_from_dom):
#                 platform = detect_ats_platform(ats_url_from_dom) or "unknown"
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: {ats_url_from_dom}")
#                 return {"ats_url": ats_url_from_dom, "ats_platform": platform}

#             # Find and click "Apply now" button to open ATS in new tab
#             try:
#                 btn = WebDriverWait(self.driver, 10).until(
#                     EC.element_to_be_clickable((By.XPATH, APPLY_NOW_BUTTON_XPATH))
#                 )
#                 self.actions.safe_click_element(btn)
#             except (TimeoutException, NoSuchElementException) as e:
#                 logger.warning(f"Apply now button not found on {job_id}: {e}")
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null")
#                 return None

#             time.sleep(2)
#             self.human.random_delay(1, 2)

#             handles = self.driver.window_handles
#             new_handles = [h for h in handles if h != main_handle]
#             if not new_handles:
#                 # Same-tab redirect
#                 current = self.driver.current_url
#                 if "hiring.cafe" not in current.lower() and is_likely_ats_url(current):
#                     platform = detect_ats_platform(current) or "unknown"
#                     logger.info(f"hiring_cafe_url: {job_url} -> ats_url: {current}")
#                     return {"ats_url": current, "ats_platform": platform}
#                 logger.warning(f"No new tab opened for job {job_id}")
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null")
#                 return None

#             self.driver.switch_to.window(new_handles[0])
#             ats_url = self.driver.current_url
#             self.driver.close()
#             self.driver.switch_to.window(main_handle)

#             if not is_likely_ats_url(ats_url):
#                 logger.debug(f"Rejected URL (not ATS-like): {ats_url}")
#                 logger.warning(f"Rejected non-ATS URL (e.g. Reddit) for {job_id}: {ats_url[:80]}...")
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null (rejected)")
#                 return None
#             ats_platform = detect_ats_platform(ats_url) or "unknown"
#             logger.info(f"hiring_cafe_url: {job_url} -> ats_url: {ats_url}")
#             return {"ats_url": ats_url, "ats_platform": ats_platform}
#         except Exception as e:
#             logger.warning(f"Error getting ATS link for job {job_id}: {e}")
#             logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null")
#             try:
#                 if len(self.driver.window_handles) > 1:
#                     self.driver.switch_to.window(self.driver.window_handles[0])
#             except Exception:
#                 pass
#             return None

#     def enrich_jobs_with_ats_links(
#         self, jobs: list[dict], limit: int | None = None
#     ) -> list[dict]:
#         """
#         For each job (with job_id or external_id), open job page, click Apply now,
#         capture ATS URL and platform from new tab. Adds ats_url and ats_platform to each job.
#         If limit is set, only process that many jobs.
#         """
#         out = []
#         to_process = jobs[:limit] if limit is not None else jobs
#         for i, job in enumerate(to_process):
#             jid = job.get("job_id") or job.get("external_id")
#             if not jid:
#                 out.append({**job, "ats_url": None, "ats_platform": None})
#                 continue
#             hiring_cafe_url = job.get("url") or job.get("hiring_cafe_url") or f"{self.base_url}/viewjob/{jid}"
#             logger.info(f"Enriching job {i+1}/{len(to_process)}: {jid}")
#             ats = self._get_ats_link_from_job_page(jid)
#             enriched = {**job, "ats_url": None, "ats_platform": None}
#             if ats:
#                 enriched["ats_url"] = ats["ats_url"]
#                 enriched["ats_platform"] = ats["ats_platform"]
#                 logger.info(f"  hiring_cafe_url: {hiring_cafe_url} -> ats_url: {ats['ats_url']}")
#             else:
#                 logger.info(f"  hiring_cafe_url: {hiring_cafe_url} -> ats_url: null")
#             out.append(enriched)
#             self.human.random_delay(1, 2)
#         if limit is not None and len(jobs) > limit:
#             for j in jobs[limit:]:
#                 out.append({**j, "ats_url": j.get("ats_url"), "ats_platform": j.get("ats_platform")})
#         return out

#     def enrich_jobs_with_ats_links_batched(
#         self,
#         jobs: list[dict],
#         batch_size: int = 100,
#         output_file: str | None = None,
#         limit: int | None = None,
#     ) -> list[dict]:
#         """
#         Enrich jobs in batches of batch_size (default 100), ordered per keyword.
#         After each batch, updates jobs in place and writes output_file if given.
#         """
#         ordered = self._jobs_ordered_per_keyword(jobs)
#         if limit is not None:
#             ordered = ordered[:limit]
#         total = len(ordered)
#         logger.info("🔗 Enriching %d jobs in batches of %d (per-keyword order)", total, batch_size)
#         for start in range(0, total, batch_size):
#             batch = ordered[start : start + batch_size]
#             batch_num = start // batch_size + 1
#             max_batch = (total + batch_size - 1) // batch_size
#             logger.info("📦 Batch %d/%d: jobs %d–%d", batch_num, max_batch, start + 1, start + len(batch))
#             try:
#                 for i, job in enumerate(batch):
#                     jid = job.get("job_id") or job.get("external_id")
#                     if not jid:
#                         continue
#                     hiring_cafe_url = job.get("url") or job.get("hiring_cafe_url") or f"{self.base_url}/viewjob/{jid}"
#                     ats = self._get_ats_link_from_job_page(jid)
#                     job["ats_url"] = ats["ats_url"] if ats else None
#                     job["ats_platform"] = ats["ats_platform"] if ats else None
#                     if ats:
#                         logger.info("  hiring_cafe_url: %s -> ats_url: %s", hiring_cafe_url, ats["ats_url"])
#                     else:
#                         logger.info("  hiring_cafe_url: %s -> ats_url: null", hiring_cafe_url)
#                     self.human.random_delay(1, 2)
#                 if output_file:
#                     self._write_jobs_payload(output_file, jobs)
#             except BaseException:
#                 logger.warning("⚠️ Batch %d interrupted; saving current state.", batch_num)
#                 if output_file:
#                     self._write_jobs_payload(output_file, jobs)
#                 raise
#         return jobs
    
#     def find_jobs_for_keyword(self, keyword: str) -> list[dict]:
#         """
#         Run search for one keyword: navigate, scroll to end, extract jobs.
#         Returns list of job dicts (job_id, title, url, ...).
#         """
#         search_url = _build_search_url(
#             keyword, self.base_url, self._date_fetched_past_n_days
#         )
#         try:
#             logger.info("🌐 Keyword %r -> %s", keyword, search_url)
#             self.driver.get(search_url)
#             time.sleep(3)
#             self.human.random_delay(2, 4)
#             if "hiring.cafe" not in self.driver.current_url.lower():
#                 logger.warning("⚠️ Unexpected URL: %s", self.driver.current_url)
#             initial_count = self._get_current_job_count()
#             if initial_count == 0:
#                 self._debug_page_structure()
#             self._scroll_until_end(max_scrolls=100, scroll_delay=2)
#             jobs = self._extract_job_listings()
#             logger.info("✅ Keyword %r: %d jobs", keyword, len(jobs))
#             return jobs
#         except Exception as e:
#             logger.error("❌ Error for keyword %r: %s", keyword, e)
#             import traceback
#             traceback.print_exc()
#             return []

#     def _merge_jobs_unique(self, keyword_job_lists: list[tuple[str, list[dict]]]) -> list[dict]:
#         """
#         Merge (keyword, jobs) pairs into one unique list by job_id.
#         Each job gets source_keywords: list of keywords that found it.
#         """
#         by_id = {}
#         for keyword, lst in keyword_job_lists:
#             for j in lst:
#                 jid = j.get("job_id") or j.get("external_id")
#                 if not jid:
#                     continue
#                 if jid not in by_id:
#                     by_id[jid] = {**j, "source_keywords": [keyword]}
#                 else:
#                     if keyword not in by_id[jid].get("source_keywords", []):
#                         by_id[jid].setdefault("source_keywords", []).append(keyword)
#         return list(by_id.values())

#     def _jobs_ordered_per_keyword(self, jobs: list[dict]) -> list[dict]:
#         """Order jobs so we process by keyword: all from first keyword, then second, etc. Each job once."""
#         order = []
#         seen_ids = set()
#         for keyword in self._search_keywords:
#             for j in jobs:
#                 jid = j.get("job_id") or j.get("external_id")
#                 if not jid or jid in seen_ids:
#                     continue
#                 if keyword in (j.get("source_keywords") or []):
#                     order.append(j)
#                     seen_ids.add(jid)
#         # Any job not in any keyword (shouldn't happen) append at end
#         for j in jobs:
#             jid = j.get("job_id") or j.get("external_id")
#             if jid and jid not in seen_ids:
#                 order.append(j)
#                 seen_ids.add(jid)
#         return order

#     def find_jobs(self) -> list[dict]:
#         """
#         Phase 1: Infinite scroll per keyword, collect all jobs into a unique set (by job_id).
#         Each job has source_keywords listing which keyword(s) found it.
#         Returns list of job dicts (deduplicated).
#         """
#         if len(self._search_keywords) == 1:
#             kw = self._search_keywords[0]
#             jobs = self.find_jobs_for_keyword(kw)
#             for j in jobs:
#                 j["source_keywords"] = [kw]
#             return jobs
#         keyword_job_lists = []
#         for keyword in self._search_keywords:
#             jobs = self.find_jobs_for_keyword(keyword)
#             keyword_job_lists.append((keyword, jobs))
#             self.human.random_delay(1, 2)
#         merged = self._merge_jobs_unique(keyword_job_lists)
#         logger.info("✅ Unique jobs across all keywords: %d", len(merged))
#         return merged
    
#     def apply(self, listing: JobListing):
#         """
#         Placeholder for apply functionality.
#         Hiring Cafe application process not implemented yet.
        
#         Args:
#             listing: JobListing object
            
#         Returns:
#             False (not implemented)
#         """
#         logger.warning("⚠️ Apply functionality not implemented for Hiring Cafe")
#         return False

#     def _write_jobs_payload(self, output_file: str, jobs: list) -> None:
#         """Write current jobs to JSON file (used for normal save and on unexpected exit)."""
#         if not jobs:
#             return
#         try:
#             payload = {
#                 "source": "hiring.cafe",
#                 "updated": datetime.now().isoformat(),
#                 "count": len(jobs),
#                 "jobs": [
#                     {
#                         "job_id": j.get("job_id"),
#                         "title": j.get("title"),
#                         "job_posting_url": j.get("url"),
#                         "ats": {
#                             "url": j.get("ats_url"),
#                             "platform": j.get("ats_platform"),
#                         },
#                         "source_keywords": j.get("source_keywords"),
#                         "scraped_at": j.get("scraped_at"),
#                     }
#                     for j in jobs
#                 ],
#             }
#             with open(output_file, "w", encoding="utf-8") as f:
#                 json.dump(payload, f, indent=2, ensure_ascii=False)
#             logger.info("💾 Saved %d jobs to %s", len(jobs), output_file)
#         except Exception as e:
#             logger.error("❌ Error saving to file: %s", e)
    
#     def scrape_and_save(
#         self,
#         output_file=None,
#         enrich_ats: bool = False,
#         enrich_ats_limit: int | None = None,
#         job_limit: int | None = None,
#         ats_batch_size: int = 100,
#     ):
#         """
#         Phase 1: Infinite scroll per keyword, collect unique jobs (set by job_id) with source_keywords.
#         Phase 2: Enrich in batches of ats_batch_size (default 100), ordered per keyword; write after each batch.
#         Phase 3: Combine and categorize by ATS at end (caller writes hiring_cafe_by_ats.json).
#         """
#         if output_file is None:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             output_file = f"hiring_cafe_jobs_{timestamp}.json"
        
#         logger.info("🚀 Phase 1: Infinite scroll per keyword, collect unique jobs...")
#         if job_limit is not None:
#             logger.info("🧪 Test mode: limiting to %d jobs", job_limit)
        
#         jobs = self.find_jobs()
        
#         if job_limit is not None and jobs:
#             jobs = jobs[:job_limit]
#             logger.info("📋 Using first %d jobs (test limit)", len(jobs))
        
#         self._write_jobs_payload(output_file, jobs)
        
#         if enrich_ats and jobs:
#             logger.info("🔗 Phase 2: Enrich in batches of %d (per-keyword order)...", ats_batch_size)
#             try:
#                 self.enrich_jobs_with_ats_links_batched(
#                     jobs,
#                     batch_size=ats_batch_size,
#                     output_file=output_file,
#                     limit=enrich_ats_limit,
#                 )
#                 self._write_jobs_payload(output_file, jobs)
#             except BaseException:
#                 logger.warning("⚠️ Enrichment interrupted; current state saved to JSON.")
#                 self._write_jobs_payload(output_file, jobs)
#                 raise
        
#         if not jobs:
#             logger.warning("⚠️ No jobs found to save")
#         return jobs


# from strategies.base import BaseStrategy
# from core.logger import logger
# from core.human_behavior import HumanBehavior
# from core.safe_actions import SafeActions
# import json
# import os
# import re
# import time
# from datetime import datetime
# from urllib.parse import quote
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.common.exceptions import TimeoutException, NoSuchElementException
# from models.config_models import JobListing

# # Hiring Cafe job link: <a href="/viewjob/{job_id}">...</a>
# JOB_LINK_SELECTOR = 'a[href^="/viewjob/"]'

# # Apply now button on job page (opens ATS in new tab)
# APPLY_NOW_BUTTON_XPATH = """
# //button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]
# | //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply') and not(contains(@href, 'hiring.cafe'))]
# """

# # URL host/path patterns -> ATS platform name (lowercase)
# ATS_PLATFORM_PATTERNS = [
#     (r"lever\.co|jobs\.lever\.", "lever"),
#     (r"greenhouse\.io|boards\.greenhouse|jobs\.greenhouse", "greenhouse"),
#     (r"sapsf\.com|successfactors\.com", "successfactors"),  # SAP SuccessFactors (sapsf = same ATS)
#     (r"workday\.com", "workday"),
#     (r"adp\.com|workforcenow\.adp\.com", "adp"),
#     (r"ashhq\.by|ashhqby", "ashhqby"),
#     (r"smartrecruiters\.com", "smartrecruiters"),
#     (r"icims\.com", "icims"),
#     (r"jobvite\.com", "jobvite"),
#     (r"taleo\.net|taleocdn", "taleo"),
#     (r"myworkdayjobs\.com", "workday"),
#     (r"apply\.workable\.com|workable\.com", "workable"),
#     (r"bamboohr\.com", "bamboohr"),
#     (r"paycom\.com", "paycom"),
#     (r"paychex\.com|myapps\.paychex\.com", "paychex"),
#     (r"ultipro\.com", "ultipro"),
#     (r"linkedin\.com/jobs", "linkedin"),
#     (r"indeed\.com", "indeed"),
#     (r"ashbyhq\.com", "ashby"),
#     (r"recruitee\.com", "recruitee"),
#     (r"teamtailor\.com", "teamtailor"),
#     (r"personio\.com", "personio"),
#     (r"oraclecloud\.com", "oraclecloud"),
#     (r"applytojob\.com", "applytojob"),
#     (r"brassring\.com", "brassring"),
#     (r"rippling\.com", "rippling"),
# ]


# def _job_id_from_href(href: str) -> str | None:
#     """Extract job ID from href like '/viewjob/p16gu5rnyh9yhp7v'."""
#     if not href:
#         return None
#     match = re.search(r"/viewjob/([a-zA-Z0-9_-]+)", href)
#     return match.group(1) if match else None


# def _load_hiring_cafe_config() -> dict:
#     """Load Hiring Cafe config from config/hiring_cafe.json. Returns {} if missing."""
#     try:
#         config_path = os.path.join(
#             os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
#             "config",
#             "hiring_cafe.json",
#         )
#         if os.path.isfile(config_path):
#             with open(config_path, "r", encoding="utf-8") as f:
#                 return json.load(f)
#     except Exception as e:
#         logger.warning(f"Could not load hiring_cafe config: {e}")
#     return {}


# # Date filter: dateFetchedPastNDays in searchState (default 2 = 24 hours)
# DATE_FETCHED_PRESETS = {
#     "today": 2,
#     "24h": 2,   # 24 hours
#     "3d": 4,    # 3 days
#     "1w": 14,   # 1 week
#     "2w": 21,   # 2 weeks
#     "all": -1,  # All time
# }


# def _parse_date_fetched_past_n_days(value) -> int:
#     """Parse config value to dateFetchedPastNDays. Presets: 24h=2, 3d=4, 1w=14, 2w=21, all=-1. Default 2 (24h)."""
#     if value is None:
#         return 2
#     if isinstance(value, int):
#         return value
#     s = str(value).strip().lower()
#     if s in DATE_FETCHED_PRESETS:
#         return DATE_FETCHED_PRESETS[s]
#     try:
#         return int(value)
#     except (TypeError, ValueError):
#         return 2


# def _normalize_search_keyword(keyword: str) -> str:
#     """Use + for spaces in searchQuery (e.g. 'AI Engineer' -> 'AI+Engineer'). Hiring.cafe expects AI+Engineer (encoded as AI%2BEngineer in URL)."""
#     if not keyword:
#         return keyword
#     s = keyword.strip()
#     if " " in s and "+" not in s:
#         s = s.replace(" ", "+")
#     return s


# def _build_search_url(
#     keyword: str,
#     base_url: str = "https://hiring.cafe",
#     date_fetched_past_n_days: int = 2,
# ) -> str:
#     """Build hiring.cafe search URL. searchState = {"searchQuery": "AI+Engineer", "dateFetchedPastNDays": N}; + is encoded as %2B."""
#     search_query = _normalize_search_keyword(keyword)
#     search_state = json.dumps({
#         "searchQuery": search_query,
#         "dateFetchedPastNDays": date_fetched_past_n_days,
#     })
#     encoded = quote(search_state, safe="")
#     return f"{base_url}/?searchState={encoded}"


# def detect_ats_platform(url: str) -> str | None:
#     """
#     Detect ATS platform from URL (e.g. lever, greenhouse, successfactors, workday, ashhqby).
#     Returns platform name or None if unknown.
#     """
#     if not url:
#         return None
#     url_lower = url.lower()
#     for pattern, platform in ATS_PLATFORM_PATTERNS:
#         if re.search(pattern, url_lower):
#             return platform
#     return None


# # Domains that are NOT job application (ATS) URLs - reject these when resolving Apply link
# NON_ATS_URL_DOMAINS = (
#     "reddit.com",
#     "twitter.com",
#     "x.com",
#     "facebook.com",
#     "linkedin.com/share",
#     "linkedin.com/feed",
#     "t.co",
#     "wa.me",
#     "telegram.me",
#     "whatsapp.com",
# )


# def is_likely_ats_url(url: str) -> bool:
#     """
#     Return True only if url looks like a job/application URL. Rejects Reddit, social sharing, etc.
#     """
#     if not url or not url.strip().startswith("http"):
#         return False
#     url_lower = url.lower().strip()
#     if "hiring.cafe" in url_lower:
#         return False
#     for domain in NON_ATS_URL_DOMAINS:
#         if domain in url_lower:
#             return False
#     # Known ATS platform -> accept
#     if detect_ats_platform(url):
#         return True
#     # Heuristic: job/apply/careers paths often indicate ATS (reject generic external links)
#     if any(p in url_lower for p in ("/job", "/jobs", "/career", "/apply", "/opportunity", "jobdetail", "jobboard", "opening", "openings", "opportunity", "opportunities", "req", "requisition", "vacancy")):
#         return True
#     return False


# def categorize_jobs_by_ats(jobs: list[dict]) -> dict[str, list[dict]]:
#     """
#     Group jobs by ATS platform. Each group is a list of entries with
#     job_id, title, job_posting_url, ats: { url, platform }. Keys are platform names; "unknown" for null/missing.
#     """
#     by_platform = {}
#     for j in jobs:
#         ats_obj = j.get("ats")
#         if isinstance(ats_obj, dict):
#             platform = (ats_obj.get("platform") or "unknown").strip() or "unknown"
#             ats_url = ats_obj.get("url")
#         else:
#             platform = (j.get("ats_platform") or "unknown").strip() or "unknown"
#             ats_url = j.get("ats_url")
#         job_posting_url = j.get("url") or j.get("job_posting_url") or j.get("hiring_cafe_url")
#         entry = {
#             "job_id": j.get("job_id"),
#             "title": j.get("title"),
#             "job_posting_url": job_posting_url,
#             "ats": {"url": ats_url, "platform": platform},
#         }
#         if platform not in by_platform:
#             by_platform[platform] = []
#         by_platform[platform].append(entry)
#     return by_platform


# class HiringCafeStrategy(BaseStrategy):
#     """
#     Hiring Cafe scraper strategy.
    
#     Features:
#     - Infinite scroll to load all job positions
#     - Extracts job listings from the search results
#     - Can be run standalone for scraping only
#     """
    
#     def __init__(self, driver, job_site=None, selectors=None, db_session=None, date_filter_override=None):
#         config = _load_hiring_cafe_config()
#         # Keywords: prefer config/hiring_cafe.json (search_keywords list, then search_keyword), then env, then default
#         if config.get("search_keywords"):
#             keywords = [str(k).strip() for k in config["search_keywords"] if str(k).strip()]
#         elif config.get("search_keyword"):
#             keywords = [str(config["search_keyword"]).strip()]
#         else:
#             env_kw = os.environ.get("HIRING_CAFE_SEARCH_KEYWORD", "").strip()
#             keywords = [env_kw] if env_kw else ["AI"]
#         self._search_keywords = keywords if keywords else ["AI"]
#         self._date_fetched_past_n_days = (
#             _parse_date_fetched_past_n_days(date_filter_override)
#             if date_filter_override is not None
#             else _parse_date_fetched_past_n_days(
#                 config.get("date_fetched_past_n_days") or config.get("date_filter") or 2
#             )
#         )
#         base_url = "https://hiring.cafe"
#         search_url = _build_search_url(
#             self._search_keywords[0], base_url, self._date_fetched_past_n_days
#         )

#         # Allow initialization without job_site for standalone use
#         if job_site is None:
#             class MinimalJobSite:
#                 def __init__(self, url_template):
#                     self.company_name = "Hiring Cafe"
#                     self.search_url_template = url_template
#             job_site = MinimalJobSite(search_url)

#         super().__init__(driver, job_site, selectors or {})
#         self.db_session = db_session
#         self.human = HumanBehavior(driver)
#         self.base_url = base_url
#         self.search_url = search_url

#         logger.info(
#             "✅ HiringCafeStrategy initialized (keywords=%s, date_fetched_past_n_days=%s)",
#             self._search_keywords,
#             self._date_fetched_past_n_days,
#         )
    
#     def login(self):
#         """
#         Hiring Cafe doesn't require login for viewing jobs.
#         Returns True to indicate success.
#         """
#         logger.info("ℹ️ No login required for Hiring Cafe")
#         return True
    
#     def _scroll_to_bottom(self):
#         """Scroll to the bottom of the page"""
#         self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         time.sleep(1)  # Wait for content to load
    
#     def _get_viewjob_links(self):
#         """Find all visible 'Job Posting' links with href /viewjob/{id}."""
#         try:
#             links = self.driver.find_elements(By.CSS_SELECTOR, JOB_LINK_SELECTOR)
#             return [el for el in links if el.is_displayed()]
#         except Exception as e:
#             logger.warning(f"Error finding viewjob links: {e}")
#             return []

#     def _get_unique_job_ids(self) -> set[str]:
#         """Return set of unique job IDs currently visible on the page."""
#         ids = set()
#         for link in self._get_viewjob_links():
#             href = link.get_attribute("href") or ""
#             job_id = _job_id_from_href(href)
#             if job_id:
#                 ids.add(job_id)
#         return ids

#     def _get_current_job_count(self) -> int:
#         """
#         Count unique job listings via a[href^="/viewjob/"] links.
#         """
#         return len(self._get_unique_job_ids())
    
#     def _debug_page_structure(self):
#         """
#         Debug method to print page structure for troubleshooting.
#         Useful when selectors don't match the actual page structure.
#         """
#         logger.info("🔍 Analyzing page structure for debugging...")
#         try:
#             # Get page source length
#             page_source_length = len(self.driver.page_source)
#             logger.info(f"Page source length: {page_source_length} characters")
            
#             # Count common elements
#             element_counts = {}
#             test_selectors = [
#                 ("articles", "article"),
#                 ("divs", "div"),
#                 ("links", "a"),
#                 ("cards", "[class*='card']"),
#                 ("jobs", "[class*='job']"),
#                 ("listings", "[class*='listing']"),
#             ]
            
#             for name, selector in test_selectors:
#                 try:
#                     count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
#                     element_counts[name] = count
#                 except Exception:
#                     element_counts[name] = 0
            
#             logger.info(f"Element counts: {element_counts}")
            
#             # Try to find any links with job-related text
#             try:
#                 all_links = self.driver.find_elements(By.TAG_NAME, "a")
#                 job_related_links = [
#                     link for link in all_links 
#                     if link.is_displayed() and any(
#                         keyword in link.text.lower() or keyword in link.get_attribute("href", "").lower()
#                         for keyword in ["job", "position", "career", "apply", "hiring"]
#                     )
#                 ]
#                 logger.info(f"Found {len(job_related_links)} links with job-related keywords")
                
#                 if job_related_links:
#                     logger.info("Sample link texts:")
#                     for link in job_related_links[:5]:
#                         logger.info(f"  - {link.text[:50]} | {link.get_attribute('href')[:80]}")
#             except Exception as e:
#                 logger.debug(f"Error analyzing links: {e}")
                
#         except Exception as e:
#             logger.warning(f"Error in debug_page_structure: {e}")
    
#     def _scroll_until_end(self, max_scrolls=100, scroll_delay=2):
#         """
#         Scroll until no more jobs are loading.
        
#         Args:
#             max_scrolls: Maximum number of scroll attempts
#             scroll_delay: Delay between scrolls in seconds
            
#         Returns:
#             True if scrolling completed, False if max scrolls reached
#         """
#         logger.info("🔄 Starting infinite scroll to load all positions...")
        
#         previous_count = 0
#         no_change_count = 0
#         scroll_attempts = 0
        
#         while scroll_attempts < max_scrolls:
#             # Get current job count
#             current_count = self._get_current_job_count()
#             logger.info(f"📊 Current job count: {current_count} (scroll attempt {scroll_attempts + 1}/{max_scrolls})")
            
#             # If count hasn't changed after multiple scrolls, we're done
#             if current_count == previous_count:
#                 no_change_count += 1
#                 if no_change_count >= 3:  # No change for 3 consecutive scrolls
#                     logger.info(f"✅ No new jobs loaded after {no_change_count} scrolls. Reached end.")
#                     return True
#             else:
#                 no_change_count = 0  # Reset counter when new jobs appear
            
#             previous_count = current_count
            
#             # Scroll down
#             last_height = self.driver.execute_script("return document.body.scrollHeight")
#             self._scroll_to_bottom()
            
#             # Wait for new content to potentially load
#             time.sleep(scroll_delay)
            
#             # Check if page height changed (new content loaded)
#             new_height = self.driver.execute_script("return document.body.scrollHeight")
#             if new_height == last_height:
#                 # Try scrolling a bit more to trigger lazy loading
#                 self.driver.execute_script("window.scrollBy(0, 500);")
#                 time.sleep(1)
            
#             scroll_attempts += 1
            
#             # Human-like delay
#             self.human.random_delay(0.5, 1.5)
        
#         logger.warning(f"⚠️ Reached maximum scroll attempts ({max_scrolls}). Stopping.")
#         return False
    
#     def extract_all_job_ids(self) -> list[str]:
#         """
#         Extract all unique job IDs from the current page (a[href^="/viewjob/"]).
#         Call after scrolling to end to get the full list.
#         """
#         return sorted(self._get_unique_job_ids())

#     def _extract_job_listings(self):
#         """
#         Extract job listings using a[href^="/viewjob/"] links.
#         Each link gives job_id from href; url is base_url + href.
#         """
#         jobs = []
#         logger.info("🔍 Extracting job listings via viewjob links...")
        
#         try:
#             seen_ids = set()
#             for link in self._get_viewjob_links():
#                 try:
#                     href = link.get_attribute("href") or ""
#                     job_id = _job_id_from_href(href)
#                     if not job_id or job_id in seen_ids:
#                         continue
#                     seen_ids.add(job_id)
                    
#                     url = href if href.startswith("http") else (self.base_url + (href if href.startswith("/") else "/" + href))
                    
#                     # Optional: try to get title from parent container
#                     title = None
#                     try:
#                         parent = link.find_element(By.XPATH, "./ancestor::*[self::article or self::div][position()<=3]")
#                         raw = (parent.text or "").strip()
#                         if raw and "Job Posting" in raw:
#                             title = raw.replace("Job Posting", "").strip()[:200] or None
#                     except Exception:
#                         pass
#                     if not title:
#                         title = f"Job {job_id}"
                    
#                     job_data = {
#                         "job_id": job_id,
#                         "external_id": job_id,
#                         "title": title,
#                         "url": url,
#                         "company": None,
#                         "location": None,
#                         "scraped_at": datetime.now().isoformat(),
#                     }
#                     jobs.append(job_data)
#                 except Exception as e:
#                     logger.warning(f"Error extracting from link: {e}")
#                     continue
            
#             logger.info(f"✅ Extracted {len(jobs)} unique job listings (job IDs)")
#             return jobs
            
#         except Exception as e:
#             logger.error(f"❌ Error extracting job listings: {e}")
#             import traceback
#             traceback.print_exc()
#             return []

#     def _try_get_ats_url_from_dom(self) -> str | None:
#         """
#         Try to get ATS URL from the job page DOM without clicking (e.g. from a wrapper <a>
#         or nearby external link). Returns URL string or None.
#         """
#         try:
#             buttons = self.driver.find_elements(By.XPATH, APPLY_NOW_BUTTON_XPATH)
#             if not buttons:
#                 return None
#             btn = buttons[0]

#             def is_external(url: str) -> bool:
#                 if not url or not url.strip().startswith("http"):
#                     return False
#                 return "hiring.cafe" not in url.lower()

#             def accept_url(href: str) -> bool:
#                 return is_external(href) and is_likely_ats_url(href)

#             # 1) Ancestor <a href="..."> wrapping the button
#             try:
#                 parent = btn
#                 for _ in range(10):
#                     parent = parent.find_element(By.XPATH, "..")
#                     tag = parent.tag_name.lower()
#                     if tag == "a":
#                         href = parent.get_attribute("href")
#                         if accept_url(href):
#                             return href.strip()
#                         break
#                     if tag == "body":
#                         break
#             except Exception:
#                 pass

#             # 2) Sibling or following <a> with external href (e.g. next to button)
#             try:
#                 container = btn.find_element(By.XPATH, "..")
#                 for a in container.find_elements(By.TAG_NAME, "a"):
#                     href = a.get_attribute("href")
#                     if accept_url(href):
#                         return href.strip()
#             except Exception:
#                 pass

#             # 3) In the same section as the button: <a target="_blank"> or "apply" in text (must be ATS-like)
#             try:
#                 root = btn
#                 for _ in range(8):
#                     root = root.find_element(By.XPATH, "..")
#                     for a in root.find_elements(By.CSS_SELECTOR, 'a[href^="http"]'):
#                         href = a.get_attribute("href")
#                         if not accept_url(href):
#                             continue
#                         target = (a.get_attribute("target") or "").lower()
#                         rel = (a.get_attribute("rel") or "").lower()
#                         text = (a.text or "").lower()
#                         if "apply" in text or target == "_blank" or "noopener" in rel:
#                             return href.strip()
#             except Exception:
#                 pass

#             return None
#         except Exception as e:
#             logger.debug(f"DOM ATS URL extraction failed: {e}")
#             return None

#     def _get_ats_link_from_job_page(self, job_id: str) -> dict | None:
#         """
#         Open job page, get ATS URL from Apply button link if visible in DOM; otherwise
#         click Apply now and capture ATS URL from new tab. Rejects non-ATS URLs (e.g. Reddit).
#         Returns {"ats_url": str, "ats_platform": str} or None if failed.
#         """
#         job_url = f"{self.base_url}/viewjob/{job_id}"
#         try:
#             self.driver.get(job_url)
#             time.sleep(2)
#             self.human.random_delay(1, 2)

#             main_handle = self.driver.current_window_handle

#             # Try to get ATS URL from DOM first (wrapper <a> or nearby external link; already filtered to ATS-like)
#             ats_url_from_dom = self._try_get_ats_url_from_dom()
#             if ats_url_from_dom and is_likely_ats_url(ats_url_from_dom):
#                 platform = detect_ats_platform(ats_url_from_dom) or "unknown"
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: {ats_url_from_dom}")
#                 return {"ats_url": ats_url_from_dom, "ats_platform": platform}

#             # Find and click "Apply now" button to open ATS in new tab
#             try:
#                 btn = WebDriverWait(self.driver, 10).until(
#                     EC.element_to_be_clickable((By.XPATH, APPLY_NOW_BUTTON_XPATH))
#                 )
#                 self.actions.safe_click_element(btn)
#             except (TimeoutException, NoSuchElementException) as e:
#                 logger.warning(f"Apply now button not found on {job_id}: {e}")
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null")
#                 return None

#             time.sleep(2)
#             self.human.random_delay(1, 2)

#             handles = self.driver.window_handles
#             new_handles = [h for h in handles if h != main_handle]
#             if not new_handles:
#                 # Same-tab redirect
#                 current = self.driver.current_url
#                 if "hiring.cafe" not in current.lower() and is_likely_ats_url(current):
#                     platform = detect_ats_platform(current) or "unknown"
#                     logger.info(f"hiring_cafe_url: {job_url} -> ats_url: {current}")
#                     return {"ats_url": current, "ats_platform": platform}
#                 logger.warning(f"No new tab opened for job {job_id}")
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null")
#                 return None

#             self.driver.switch_to.window(new_handles[0])
#             ats_url = self.driver.current_url
#             self.driver.close()
#             self.driver.switch_to.window(main_handle)

#             if not is_likely_ats_url(ats_url):
#                 logger.debug(f"Rejected URL (not ATS-like): {ats_url}")
#                 logger.warning(f"Rejected non-ATS URL (e.g. Reddit) for {job_id}: {ats_url[:80]}...")
#                 logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null (rejected)")
#                 return None
#             ats_platform = detect_ats_platform(ats_url) or "unknown"
#             logger.info(f"hiring_cafe_url: {job_url} -> ats_url: {ats_url}")
#             return {"ats_url": ats_url, "ats_platform": ats_platform}
#         except Exception as e:
#             logger.warning(f"Error getting ATS link for job {job_id}: {e}")
#             logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null")
#             try:
#                 if len(self.driver.window_handles) > 1:
#                     self.driver.switch_to.window(self.driver.window_handles[0])
#             except Exception:
#                 pass
#             return None

#     def enrich_jobs_with_ats_links(
#         self, jobs: list[dict], limit: int | None = None
#     ) -> list[dict]:
#         """
#         For each job (with job_id or external_id), open job page, click Apply now,
#         capture ATS URL and platform from new tab. Adds ats_url and ats_platform to each job.
#         If limit is set, only process that many jobs.
#         """
#         out = []
#         to_process = jobs[:limit] if limit is not None else jobs
#         for i, job in enumerate(to_process):
#             jid = job.get("job_id") or job.get("external_id")
#             if not jid:
#                 out.append({**job, "ats_url": None, "ats_platform": None})
#                 continue
#             hiring_cafe_url = job.get("url") or job.get("hiring_cafe_url") or f"{self.base_url}/viewjob/{jid}"
#             logger.info(f"Enriching job {i+1}/{len(to_process)}: {jid}")
#             ats = self._get_ats_link_from_job_page(jid)
#             enriched = {**job, "ats_url": None, "ats_platform": None}
#             if ats:
#                 enriched["ats_url"] = ats["ats_url"]
#                 enriched["ats_platform"] = ats["ats_platform"]
#                 logger.info(f"  hiring_cafe_url: {hiring_cafe_url} -> ats_url: {ats['ats_url']}")
#             else:
#                 logger.info(f"  hiring_cafe_url: {hiring_cafe_url} -> ats_url: null")
#             out.append(enriched)
#             self.human.random_delay(1, 2)
#         if limit is not None and len(jobs) > limit:
#             for j in jobs[limit:]:
#                 out.append({**j, "ats_url": j.get("ats_url"), "ats_platform": j.get("ats_platform")})
#         return out

#     def enrich_jobs_with_ats_links_batched(
#         self,
#         jobs: list[dict],
#         batch_size: int = 100,
#         output_file: str | None = None,
#         limit: int | None = None,
#     ) -> list[dict]:
#         """
#         Enrich jobs in batches of batch_size (default 100), ordered per keyword.
#         After each batch, updates jobs in place and writes output_file if given.
#         """
#         ordered = self._jobs_ordered_per_keyword(jobs)
#         if limit is not None:
#             ordered = ordered[:limit]
#         total = len(ordered)
#         logger.info("🔗 Enriching %d jobs in batches of %d (per-keyword order)", total, batch_size)
#         for start in range(0, total, batch_size):
#             batch = ordered[start : start + batch_size]
#             batch_num = start // batch_size + 1
#             max_batch = (total + batch_size - 1) // batch_size
#             logger.info("📦 Batch %d/%d: jobs %d–%d", batch_num, max_batch, start + 1, start + len(batch))
#             try:
#                 for i, job in enumerate(batch):
#                     jid = job.get("job_id") or job.get("external_id")
#                     if not jid:
#                         continue
#                     hiring_cafe_url = job.get("url") or job.get("hiring_cafe_url") or f"{self.base_url}/viewjob/{jid}"
#                     ats = self._get_ats_link_from_job_page(jid)
#                     job["ats_url"] = ats["ats_url"] if ats else None
#                     job["ats_platform"] = ats["ats_platform"] if ats else None
#                     if ats:
#                         logger.info("  hiring_cafe_url: %s -> ats_url: %s", hiring_cafe_url, ats["ats_url"])
#                     else:
#                         logger.info("  hiring_cafe_url: %s -> ats_url: null", hiring_cafe_url)
#                     self.human.random_delay(1, 2)
#                 if output_file:
#                     self._write_jobs_payload(output_file, jobs)
#             except BaseException:
#                 logger.warning("⚠️ Batch %d interrupted; saving current state.", batch_num)
#                 if output_file:
#                     self._write_jobs_payload(output_file, jobs)
#                 raise
#         return jobs
    
#     def find_jobs_for_keyword(self, keyword: str) -> list[dict]:
#         """
#         Run search for one keyword: navigate, scroll to end, extract jobs.
#         Returns list of job dicts (job_id, title, url, ...).
#         """
#         search_url = _build_search_url(
#             keyword, self.base_url, self._date_fetched_past_n_days
#         )
#         try:
#             logger.info("🌐 Keyword %r -> %s", keyword, search_url)
#             self.driver.get(search_url)
#             time.sleep(3)
#             self.human.random_delay(2, 4)
#             if "hiring.cafe" not in self.driver.current_url.lower():
#                 logger.warning("⚠️ Unexpected URL: %s", self.driver.current_url)
#             initial_count = self._get_current_job_count()
#             if initial_count == 0:
#                 self._debug_page_structure()
#             self._scroll_until_end(max_scrolls=100, scroll_delay=2)
#             jobs = self._extract_job_listings()
#             logger.info("✅ Keyword %r: %d jobs", keyword, len(jobs))
#             return jobs
#         except Exception as e:
#             logger.error("❌ Error for keyword %r: %s", keyword, e)
#             import traceback
#             traceback.print_exc()
#             return []

#     def _merge_jobs_unique(self, keyword_job_lists: list[tuple[str, list[dict]]]) -> list[dict]:
#         """
#         Merge (keyword, jobs) pairs into one unique list by job_id.
#         Each job gets source_keywords: list of keywords that found it.
#         """
#         by_id = {}
#         for keyword, lst in keyword_job_lists:
#             for j in lst:
#                 jid = j.get("job_id") or j.get("external_id")
#                 if not jid:
#                     continue
#                 if jid not in by_id:
#                     by_id[jid] = {**j, "source_keywords": [keyword]}
#                 else:
#                     if keyword not in by_id[jid].get("source_keywords", []):
#                         by_id[jid].setdefault("source_keywords", []).append(keyword)
#         return list(by_id.values())

#     def _jobs_ordered_per_keyword(self, jobs: list[dict]) -> list[dict]:
#         """Order jobs so we process by keyword: all from first keyword, then second, etc. Each job once."""
#         order = []
#         seen_ids = set()
#         for keyword in self._search_keywords:
#             for j in jobs:
#                 jid = j.get("job_id") or j.get("external_id")
#                 if not jid or jid in seen_ids:
#                     continue
#                 if keyword in (j.get("source_keywords") or []):
#                     order.append(j)
#                     seen_ids.add(jid)
#         # Any job not in any keyword (shouldn't happen) append at end
#         for j in jobs:
#             jid = j.get("job_id") or j.get("external_id")
#             if jid and jid not in seen_ids:
#                 order.append(j)
#                 seen_ids.add(jid)
#         return order

#     def find_jobs(self) -> list[dict]:
#         """
#         Phase 1: Infinite scroll per keyword, collect all jobs into a unique set (by job_id).
#         Each job has source_keywords listing which keyword(s) found it.
#         Returns list of job dicts (deduplicated).
#         """
#         if len(self._search_keywords) == 1:
#             kw = self._search_keywords[0]
#             jobs = self.find_jobs_for_keyword(kw)
#             for j in jobs:
#                 j["source_keywords"] = [kw]
#             return jobs
#         keyword_job_lists = []
#         for keyword in self._search_keywords:
#             jobs = self.find_jobs_for_keyword(keyword)
#             keyword_job_lists.append((keyword, jobs))
#             self.human.random_delay(1, 2)
#         merged = self._merge_jobs_unique(keyword_job_lists)
#         logger.info("✅ Unique jobs across all keywords: %d", len(merged))
#         return merged
    
#     def apply(self, listing: JobListing):
#         """
#         Placeholder for apply functionality.
#         Hiring Cafe application process not implemented yet.
        
#         Args:
#             listing: JobListing object
            
#         Returns:
#             False (not implemented)
#         """
#         logger.warning("⚠️ Apply functionality not implemented for Hiring Cafe")
#         return False

#     def _write_jobs_payload(self, output_file: str, jobs: list) -> None:
#         """Write current jobs to JSON file (used for normal save and on unexpected exit)."""
#         if not jobs:
#             return
#         try:
#             payload = {
#                 "source": "hiring.cafe",
#                 "updated": datetime.now().isoformat(),
#                 "count": len(jobs),
#                 "jobs": [
#                     {
#                         "job_id": j.get("job_id"),
#                         "title": j.get("title"),
#                         "job_posting_url": j.get("url"),
#                         "ats": {
#                             "url": j.get("ats_url"),
#                             "platform": j.get("ats_platform"),
#                         },
#                         "source_keywords": j.get("source_keywords"),
#                         "scraped_at": j.get("scraped_at"),
#                     }
#                     for j in jobs
#                 ],
#             }
#             with open(output_file, "w", encoding="utf-8") as f:
#                 json.dump(payload, f, indent=2, ensure_ascii=False)
#             logger.info("💾 Saved %d jobs to %s", len(jobs), output_file)
#         except Exception as e:
#             logger.error("❌ Error saving to file: %s", e)
    
#     def scrape_and_save(
#         self,
#         output_file=None,
#         enrich_ats: bool = False,
#         enrich_ats_limit: int | None = None,
#         job_limit: int | None = None,
#         ats_batch_size: int = 100,
#     ):
#         """
#         Phase 1: Infinite scroll per keyword, collect unique jobs (set by job_id) with source_keywords.
#         Phase 2: Enrich in batches of ats_batch_size (default 100), ordered per keyword; write after each batch.
#         Phase 3: Combine and categorize by ATS at end (caller writes hiring_cafe_by_ats.json).
#         """
#         if output_file is None:
#             timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#             output_file = f"hiring_cafe_jobs_{timestamp}.json"
        
#         logger.info("🚀 Phase 1: Infinite scroll per keyword, collect unique jobs...")
#         if job_limit is not None:
#             logger.info("🧪 Test mode: limiting to %d jobs", job_limit)
        
#         jobs = self.find_jobs()
        
#         if job_limit is not None and jobs:
#             jobs = jobs[:job_limit]
#             logger.info("📋 Using first %d jobs (test limit)", len(jobs))
        
#         self._write_jobs_payload(output_file, jobs)
        
#         if enrich_ats and jobs:
#             logger.info("🔗 Phase 2: Enrich in batches of %d (per-keyword order)...", ats_batch_size)
#             try:
#                 self.enrich_jobs_with_ats_links_batched(
#                     jobs,
#                     batch_size=ats_batch_size,
#                     output_file=output_file,
#                     limit=enrich_ats_limit,
#                 )
#                 self._write_jobs_payload(output_file, jobs)
#             except BaseException:
#                 logger.warning("⚠️ Enrichment interrupted; current state saved to JSON.")
#                 self._write_jobs_payload(output_file, jobs)
#                 raise
        
#         if not jobs:
#             logger.warning("⚠️ No jobs found to save")
#         return jobs


from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from models.config_models import JobListing

# Hiring Cafe job link: <a href="/viewjob/{job_id}">...</a>
JOB_LINK_SELECTOR = 'a[href^="/viewjob/"]'

# Apply now button on job page (opens ATS in new tab)
# Primary XPath — matches any button/link containing "apply" (case-insensitive)
APPLY_NOW_BUTTON_XPATH = """
//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]
| //a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply') and not(contains(@href, 'hiring.cafe'))]
"""

# Fallback selectors tried in order when primary XPath finds nothing or times out
APPLY_BUTTON_FALLBACK_XPATHS = [
    # Buttons/links with "apply" in aria-label or data attributes
    "//button[@aria-label and contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'apply')]",
    "//*[@data-testid and contains(translate(@data-testid,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'apply')]",
    # "View job" / "View posting" links (some companies use this wording)
    "//a[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'view job')]",
    "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'view job')]",
    # External links with target=_blank that point outside hiring.cafe
    "//a[@target='_blank' and not(contains(@href,'hiring.cafe')) and starts-with(@href,'http')]",
]

# URL host/path patterns -> ATS platform name (lowercase)
ATS_PLATFORM_PATTERNS = [
    (r"lever\.co|jobs\.lever\.", "lever"),
    (r"greenhouse\.io|boards\.greenhouse|jobs\.greenhouse|job-boards\.greenhouse", "greenhouse"),
    (r"sapsf\.com|successfactors\.com", "successfactors"),
    (r"workday\.com|myworkdayjobs\.com|wd\d+\.myworkdayjobs\.com", "workday"),
    (r"adp\.com|workforcenow\.adp\.com", "adp"),
    (r"ashhq\.by|ashhqby", "ashhqby"),
    (r"smartrecruiters\.com", "smartrecruiters"),
    (r"icims\.com", "icims"),
    (r"jobvite\.com", "jobvite"),
    (r"taleo\.net|taleocdn", "taleo"),
    (r"apply\.workable\.com|workable\.com", "workable"),
    (r"bamboohr\.com", "bamboohr"),
    (r"paycom\.com", "paycom"),
    (r"paychex\.com|myapps\.paychex\.com", "paychex"),
    (r"ultipro\.com", "ultipro"),
    (r"linkedin\.com/jobs", "linkedin"),
    (r"indeed\.com", "indeed"),
    (r"ashbyhq\.com", "ashby"),
    (r"recruitee\.com", "recruitee"),
    (r"teamtailor\.com", "teamtailor"),
    (r"personio\.com", "personio"),
    (r"oraclecloud\.com", "oraclecloud"),
    (r"applytojob\.com", "applytojob"),
    (r"brassring\.com", "brassring"),
    (r"rippling\.com", "rippling"),
    (r"paylocity\.com", "paylocity"),
    (r"breezy\.hr", "breezy"),
    (r"jazz\.co", "jazz"),
    (r"pinpointrecruitment\.com", "pinpoint"),
    (r"dover\.com", "dover"),
    (r"phenompeople\.com", "phenom"),
    (r"careers\.google\.com/jobs|careers\.google\.com/intl", "google"),  # only actual job listings
    (r"jobs\.apple\.com", "apple"),
    (r"microsoft\.com/.*careers", "microsoft"),
    (r"workdayjobs\.com", "workday"),
]

# Fingerprints of hiring.cafe's empty React shell (blocked/rate-limited state).
# Observed from logs: these exact page source sizes = no jobs loaded.
BLOCKED_PAGE_SIZES = {63178, 63180, 63183, 63184, 63170, 56140}
BLOCKED_DIV_COUNT = {65, 77}   # div counts seen on empty pages
BLOCKED_LINK_COUNT = 7         # link count seen on every empty page

# Regex to find ATS URLs directly in page source HTML
ATS_URL_REGEX = re.compile(
    r'https?://(?:'
    # Lever
    r'[a-z0-9-]+\.lever\.co'
    r'|jobs\.lever\.co'
    # Greenhouse
    r'|boards\.greenhouse\.io'
    r'|[a-z0-9-]+\.greenhouse\.io'
    r'|jobs\.greenhouse\.io'
    r'|job-boards\.greenhouse\.io'
    # Workday — matches wd1/wd2/.../wd103/wd5 subdomains AND myworkdayjobs.com
    r'|[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com'
    r'|[a-z0-9-]+\.myworkdayjobs\.com'
    r'|[a-z0-9-]+\.workday\.com'
    # SAP SuccessFactors
    r'|[a-z0-9-]+\.successfactors\.com'
    r'|[a-z0-9-]+\.sapsf\.com'
    # Ashby
    r'|[a-z0-9-]+\.ashbyhq\.com'
    r'|jobs\.ashbyhq\.com'
    # SmartRecruiters
    r'|[a-z0-9-]+\.smartrecruiters\.com'
    r'|jobs\.smartrecruiters\.com'
    # iCIMS
    r'|[a-z0-9-]+\.icims\.com'
    # Jobvite
    r'|[a-z0-9-]+\.jobvite\.com'
    # Taleo — matches axp.taleo.net, sjobs.taleo.net etc.
    r'|[a-z0-9-]+\.taleo\.net'
    # Workable
    r'|apply\.workable\.com'
    r'|[a-z0-9-]+\.workable\.com'
    # BambooHR
    r'|[a-z0-9-]+\.bamboohr\.com'
    # Recruitee
    r'|[a-z0-9-]+\.recruitee\.com'
    # Teamtailor
    r'|[a-z0-9-]+\.teamtailor\.com'
    # Personio
    r'|[a-z0-9-]+\.personio\.com'
    # Rippling
    r'|[a-z0-9-]+\.rippling\.com'
    # Paylocity
    r'|[a-z0-9-]+\.paylocity\.com'
    # Breezy
    r'|[a-z0-9-]+\.breezy\.hr'
    # Jazz HR
    r'|[a-z0-9-]+\.jazz\.co'
    r'|app\.jazz\.co'
    # ApplyToJob — matches pairsoft.applytojob.com etc.
    r'|[a-z0-9-]+\.applytojob\.com'
    # BrassRing — matches sjobs.brassring.com etc.
    r'|[a-z0-9-]+\.brassring\.com'
    # Oracle HCM / Taleo Cloud
    r'|[a-z0-9-]+\.oraclecloud\.com'
    r'|[a-z0-9-]+\.fa\.ocs\.oraclecloud\.com'
    # Phenom People (phenompeople.com/jobs/ paths only — not CDN/PDF)
    r'|[a-z0-9-]+\.phenompeople\.com/(?:careers|jobs)'
    # Dover
    r'|[a-z0-9-]+\.dover\.com'
    # Pinpoint
    r'|[a-z0-9-]+\.pinpointrecruitment\.com'
    # Greenhouse job-boards subdomain
    r'|job-boards\.[a-z0-9-]+\.io'
    r')[/\w\-\.\?\=\&\%\#\@\+]*',
    re.IGNORECASE
)


def _job_id_from_href(href: str) -> str | None:
    """Extract job ID from href like '/viewjob/p16gu5rnyh9yhp7v'."""
    if not href:
        return None
    match = re.search(r"/viewjob/([a-zA-Z0-9_-]+)", href)
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


DATE_FETCHED_PRESETS = {
    "today": 2,
    "24h": 2,
    "3d": 4,
    "1w": 14,
    "2w": 21,
    "all": -1,
}


def _parse_date_fetched_past_n_days(value) -> int:
    if value is None:
        return 2
    if isinstance(value, int):
        return value
    s = str(value).strip().lower()
    if s in DATE_FETCHED_PRESETS:
        return DATE_FETCHED_PRESETS[s]
    try:
        return int(value)
    except (TypeError, ValueError):
        return 2


def _normalize_search_keyword(keyword: str) -> str:
    if not keyword:
        return keyword
    s = keyword.strip()
    if " " in s and "+" not in s:
        s = s.replace(" ", "+")
    return s


def _build_search_url(
    keyword: str,
    base_url: str = "https://hiring.cafe",
    date_fetched_past_n_days: int = 2,
) -> str:
    search_query = _normalize_search_keyword(keyword)
    search_state = json.dumps({
        "searchQuery": search_query,
        "dateFetchedPastNDays": date_fetched_past_n_days,
    })
    encoded = quote(search_state, safe="")
    return f"{base_url}/?searchState={encoded}"


def detect_ats_platform(url: str) -> str | None:
    if not url:
        return None
    url_lower = url.lower()
    for pattern, platform in ATS_PLATFORM_PATTERNS:
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
    for domain in NON_ATS_URL_DOMAINS:
        if domain in url_lower:
            return False

    # Reject file downloads (PDFs, docs, images, etc.)
    path_part = url_lower.split("?")[0].split("#")[0]
    if any(path_part.endswith(ext) for ext in NON_JOB_EXTENSIONS):
        return False

    # Reject policy/non-job pages by path segment
    for segment in NON_JOB_PATH_SEGMENTS:
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
    job_path_keywords = (
        "/job/", "/jobs/", "/job-detail", "/jobdetail", "/jobboard",
        "/apply/", "/apply?", "/careers/job", "/career/job",
        "/opening/", "/openings/", "/opportunity/", "/opportunities/",
        "/req/", "/requisition/", "/vacancy/", "/vacancies/",
        "/position/", "/positions/", "/listing/", "/listings/",
        "jobid=", "jobId=", "job_id=", "referenceid=", "reqid=",
    )
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

        logger.info(
            "✅ HiringCafeStrategy initialized (keywords=%s, date_fetched_past_n_days=%s)",
            self._search_keywords,
            self._date_fetched_past_n_days,
        )

    def login(self):
        logger.info("ℹ️ No login required for Hiring Cafe")
        return True

    def _scroll_to_bottom(self):
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

    def _get_viewjob_links(self):
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, JOB_LINK_SELECTOR)
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
        Standard format observed:
        Line 0: Time elapsed (e.g., "15h" or "2d")
        Line 1: Job Title
        Line 2: Location (City, State, Country)
        Line 3: Type (Onsite/Remote/Hybrid)
        Line 4: Job Type (Full Time/Contract)
        Line 5: Company Name
        Line 6+: Optional Stock info (NYSE: ACN) and Description snippet
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        data = {
            "job_tittle": None,
            "location": None,
            "city": None,
            "state": None,
            "country": None,
            "type": None,
            "comapany": None,
            "company_description": None
        }
        
        if not lines:
            return data
            
        # Line 0 is usually time elapsed, skip if it matches pattern like "15h" or "2d"
        start_idx = 0
        if re.match(r'^\d+[hdmw]$', lines[0]):
            start_idx = 1
            
        if len(lines) > start_idx:
            data["job_tittle"] = lines[start_idx]
            
        if len(lines) > start_idx + 1:
            loc_str = lines[start_idx + 1]
            data["location"] = loc_str
            # Parse Location: "Hyderabad, Telangana, India"
            parts = [p.strip() for p in loc_str.split(',')]
            if len(parts) >= 3:
                data["city"] = parts[0]
                data["state"] = parts[1]
                data["country"] = parts[2]
            elif len(parts) == 2:
                data["city"] = parts[0]
                data["country"] = parts[1]
            elif len(parts) == 1:
                data["city"] = parts[0]

        if len(lines) > start_idx + 2:
            data["type"] = lines[start_idx + 2]
            
        # Skip "Full Time" / "Contract" line (usually start_idx + 3)
        
        if len(lines) > start_idx + 4:
            data["comapany"] = lines[start_idx + 4]
            
        # Description snippet usually starts after company or stock info
        # It often starts with a colon ": Provides..."
        desc_lines = []
        for line in lines[start_idx + 5:]:
            if line.startswith(':'):
                desc_lines.append(line.lstrip(':').strip())
            elif not any(x in line for x in ['NYSE:', 'NASDAQ:', 'YOE']):
                desc_lines.append(line)
        
        if desc_lines:
            data["company_description"] = " ".join(desc_lines)
            
        return data

    def _scroll_until_end(self, max_scrolls=100, scroll_delay=2):
        logger.info("🔄 Starting infinite scroll to load all positions...")
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
                time.sleep(scroll_delay)
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
                        "company": enriched_data.get("comapany"),
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
            for url in ATS_URL_REGEX.findall(source):
                url_clean = url.strip().rstrip('"\'\\ ')
                if "hiring.cafe" not in url_clean.lower():
                    candidates.add(url_clean)

            # ── Pass 2: decode Unicode escapes then rescan ───────────────────
            # hiring.cafe embeds job data in __NEXT_DATA__ JSON where & -> \u0026
            try:
                decoded = source.encode('utf-8').decode('unicode_escape', errors='replace')
                for url in ATS_URL_REGEX.findall(decoded):
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
                        for url in ATS_URL_REGEX.findall(blob):
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
            buttons = self.driver.find_elements(By.XPATH, APPLY_NOW_BUTTON_XPATH)

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
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, APPLY_NOW_BUTTON_XPATH))
            )
            return btn
        except (TimeoutException, NoSuchElementException):
            pass

        # Try each fallback XPath with 3s wait
        for xpath in APPLY_BUTTON_FALLBACK_XPATHS:
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
            btns = self.driver.find_elements(By.XPATH, APPLY_NOW_BUTTON_XPATH)
            if btns:
                return btns[0]
        except Exception:
            pass

        return None

    def _get_ats_link_from_job_page(self, job_id: str) -> dict | None:
        """
        6-layer ATS URL extraction with fallback button detection:

        Layer 1+2: DOM check + page source regex (no clicking needed)
        Layer 3:   _find_apply_button (primary XPath + fallbacks + scroll) → click → new tab
        Layer 4:   Same-tab redirect detection
        Layer 5:   Page source regex after click
        """
        job_url = f"{self.base_url}/viewjob/{job_id}"

        # Job IDs that persistently fail — log page source snippet for diagnosis
        DEBUG_JOB_IDS = {
            'qeu7b8sxz39rdc0o', 'e88lancdghmr59nh', 'vxpe1y6evnixao8c',
            'glv6wzud1snhi2dn', 'sdxd2sbaemobnnbt', 'nerymx0rtqhhblij',
            '7cxd1czqf3s2y6db', 'wflpb81im2umy3fb', 'l90pefs1018lxx96',
            'p5txnh2fbsp8x210', 'efrj795x4r59nqlr', 'cyrnkn2jq72mkemz', '72w0xhixj1jxi37s',
        }
        try:
            self.driver.get(job_url)
            time.sleep(3)
            self.human.random_delay(1, 2)

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
                return {"ats_url": ats_url, "ats_platform": platform}

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
                        # IMPORTANT: Some ATS sites (Workday, etc.) open a tab
                        # then immediately close it after setting a cookie/redirect.
                        # We must handle the case where the tab is already gone.
                        try:
                            self.driver.switch_to.window(new_handles[0])
                            time.sleep(2)
                            # Check if this tab is still alive
                            try:
                                ats_url = self.driver.current_url
                            except Exception:
                                # Tab closed itself — switch back to main
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
                            # Try to recover back to main window
                            try:
                                handles = self.driver.window_handles
                                if handles:
                                    self.driver.switch_to.window(handles[0])
                            except Exception:
                                pass

                        if ats_url and is_likely_ats_url(ats_url):
                            platform = detect_ats_platform(ats_url) or "unknown"
                            logger.info(f"[NewTab] hiring_cafe_url: {job_url} -> ats_url: {ats_url}")
                            return {"ats_url": ats_url, "ats_platform": platform}
                        elif ats_url:
                            logger.debug(f"Rejected new-tab URL: {ats_url}")
                    else:
                        # ── Layer 4: Same-tab redirect ────────────────────────
                        time.sleep(1)
                        current = self.driver.current_url
                        if "hiring.cafe" not in current.lower() and is_likely_ats_url(current):
                            platform = detect_ats_platform(current) or "unknown"
                            logger.info(f"[SameTab] hiring_cafe_url: {job_url} -> ats_url: {current}")
                            return {"ats_url": current, "ats_platform": platform}

                        # ── Layer 5: Page source after click ──────────────────
                        time.sleep(2)
                        candidates = self._extract_ats_urls_from_page_source()
                        if candidates:
                            ats_url = candidates[0]
                            platform = detect_ats_platform(ats_url) or "unknown"
                            logger.info(f"[PostClick/Regex] hiring_cafe_url: {job_url} -> ats_url: {ats_url}")
                            return {"ats_url": ats_url, "ats_platform": platform}
            else:
                logger.warning(f"Apply button not found for {job_id} (all XPaths failed)")

            logger.info(f"[Failed] hiring_cafe_url: {job_url} -> ats_url: null")
            return None

        except Exception as e:
            logger.warning(f"Error getting ATS link for {job_id}: {e}")
            logger.info(f"hiring_cafe_url: {job_url} -> ats_url: null")
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception:
                pass
            return None

    # ─────────────────────────────────────────────────────────────────────────────
    # REST OF STRATEGY (unchanged)
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
        already_done = sum(1 for j in to_process if "ats_url" in j)
        remaining    = len(to_process) - already_done
        if already_done:
            logger.info(
                "⏭️  Resuming: %d/%d jobs already processed, skipping them...",
                already_done, len(to_process),
            )
        logger.info("🔗 Step 2: Extracting ATS URLs for %d jobs...", remaining)

        for i, job in enumerate(to_process):
            jid = job.get("job_id") or job.get("external_id")
            if not jid:
                job.setdefault("ats_url", None)
                job.setdefault("ats_platform", None)
                continue

            # ── SKIP if this job was already attempted (key exists) ──────────
            if "ats_url" in job:
                continue

            hiring_cafe_url = (
                job.get("url")
                or job.get("hiring_cafe_url")
                or f"{self.base_url}/viewjob/{jid}"
            )
            logger.info(f"Enriching job {i+1}/{len(to_process)}: {jid}")

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
                    # Save checkpoint and stop — can resume later
                    if output_file:
                        try:
                            self._write_jobs_payload(output_file, jobs)
                        except Exception:
                            pass
                    break

            ats = self._get_ats_link_from_job_page(jid)

            # Mutate job dict IN-PLACE — reflected immediately in `jobs`
            if ats:
                job["ats_url"]      = ats["ats_url"]
                job["ats_platform"] = ats["ats_platform"]
                logger.info(f"  hiring_cafe_url: {hiring_cafe_url} -> ats_url: {ats['ats_url']}")
                consecutive_failures = 0
            else:
                job["ats_url"]      = None   # mark as attempted so resume skips it
                job["ats_platform"] = None
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
                    time.sleep(5)
                    self.human.random_delay(3, 6)
                except Exception:
                    pass
                time.sleep(40)
                consecutive_failures = 0
            else:
                self.human.random_delay(2, 4)

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
                    hiring_cafe_url = job.get("url") or job.get("hiring_cafe_url") or f"{self.base_url}/viewjob/{jid}"
                    ats = self._get_ats_link_from_job_page(jid)
                    job["ats_url"] = ats["ats_url"] if ats else None
                    job["ats_platform"] = ats["ats_platform"] if ats else None

                    if ats:
                        logger.info("  hiring_cafe_url: %s -> ats_url: %s", hiring_cafe_url, ats["ats_url"])
                        consecutive_failures = 0
                    else:
                        logger.info("  hiring_cafe_url: %s -> ats_url: null", hiring_cafe_url)
                        consecutive_failures += 1

                    # Rate-limit protection (same logic as enrich_jobs_with_ats_links)
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
                        self.human.random_delay(2, 4)

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
        Detect if hiring.cafe returned its empty React shell (blocked / rate-limited).
        Uses page source size + element counts as fingerprints from observed logs.
        """
        try:
            src_len = len(self.driver.page_source)
            if src_len in BLOCKED_PAGE_SIZES:
                logger.debug(f"Blocked page fingerprint: source length {src_len}")
                return True
            # Also check element counts as secondary signal
            try:
                div_count = len(self.driver.find_elements(By.CSS_SELECTOR, "div"))
                link_count = len(self.driver.find_elements(By.CSS_SELECTOR, "a"))
                if div_count in BLOCKED_DIV_COUNT and link_count == BLOCKED_LINK_COUNT:
                    logger.debug(f"Blocked page fingerprint: divs={div_count}, links={link_count}")
                    return True
            except Exception:
                pass
        except Exception:
            pass
        return False

    def _wait_for_jobs_to_load(self, timeout: int = 15) -> bool:
        """
        Wait until we are on hiring.cafe AND job links appear in the DOM.

        IMPORTANT: Chrome shortcuts on the Google new tab page can contain
        hiring.cafe /viewjob/ URLs, causing a false positive if we only check
        for the link selector without verifying the current URL first.
        """
        # Step 1: Verify current URL is actually on hiring.cafe
        current_url = self.driver.current_url
        if "hiring.cafe" not in current_url.lower():
            logger.warning(
                "⚠️  Browser is NOT on hiring.cafe (current: %s). "
                "Navigation may have failed.", current_url
            )
            return False

        # Step 2: Wait for /viewjob/ links to appear in DOM
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, JOB_LINK_SELECTOR))
            )
            logger.info("✅ Job content detected on page")
            return True
        except TimeoutException:
            logger.debug("Timed out waiting for job links to appear")
            return False

    def find_jobs_for_keyword(self, keyword: str, max_retries: int = 3) -> list[dict]:
        """
        Navigate to search URL, wait for React hydration, scroll to end, extract jobs.
        Includes:
        - Blocked-page detection with retry + cooldown
        - Homepage reset between retries to clear bot-detection state
        - WebDriverWait for actual job content (not just a fixed sleep)
        """
        search_url = _build_search_url(keyword, self.base_url, self._date_fetched_past_n_days)

        for attempt in range(1, max_retries + 1):
            try:
                logger.info("🌐 Keyword %r (attempt %d/%d) -> %s", keyword, attempt, max_retries, search_url)

                # Reset session: go to homepage first, then navigate to search
                # This mimics a real user browsing pattern and avoids rate-limit on direct URL jumps
                if attempt > 1:
                    logger.info("🏠 Resetting via homepage before retry...")
                    self.driver.get(self.base_url)
                    time.sleep(3)
                    self.human.random_delay(2, 4)

                self.driver.get(search_url)

                # Wait for React SPA to hydrate (up to 15s)
                # First do a short fixed wait for initial JS execution
                time.sleep(4)
                self.human.random_delay(1, 3)

                # ── Verify we actually landed on hiring.cafe ──────────────────
                # On first run, Chrome may open on a Google new tab. Chrome shortcuts
                # on the new tab can contain /viewjob/ links causing false positives.
                # If we're not on hiring.cafe, retry the navigation once.
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
                        cooldown = 15 + (attempt * 10)  # 25s, 35s progressive backoff
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

                # Scroll to load all jobs
                self._scroll_until_end(max_scrolls=100, scroll_delay=2)
                jobs = self._extract_job_listings()
                logger.info("✅ Keyword %r: %d jobs", keyword, len(jobs))
                return jobs

            except Exception as e:
                logger.error("❌ Error for keyword %r (attempt %d): %s", keyword, attempt, e)
                import traceback
                traceback.print_exc()
                # If Chrome session is dead (browser closed), stop retrying immediately
                if not self._is_session_alive():
                    logger.error("❌ Chrome session is dead — browser was closed. Stopping.")
                    return []
                if attempt < max_retries:
                    time.sleep(10)

        return []

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
            return jobs
        keyword_job_lists = []
        for i, keyword in enumerate(self._search_keywords):
            jobs = self.find_jobs_for_keyword(keyword)
            keyword_job_lists.append((keyword, jobs))
            # Longer human-like delay between keywords to avoid rate limiting.
            # hiring.cafe blocks rapid successive searches (seen in logs: 0 jobs after first keyword).
            if i < len(self._search_keywords) - 1:
                delay = 12 + (i * 3)  # 12s, 15s, 18s, 21s — progressive to look more human
                logger.info("⏳ Waiting %ds before next keyword search...", delay)
                time.sleep(delay)
                self.human.random_delay(2, 5)
        merged = self._merge_jobs_unique(keyword_job_lists)
        logger.info("✅ Unique jobs across all keywords: %d", len(merged))
        return merged

    def apply(self, listing: JobListing):
        logger.warning("⚠️ Apply functionality not implemented for Hiring Cafe")
        return False

    def _write_jobs_payload(self, output_file: str, jobs: list) -> None:
        """
        Save jobs to file in the FLAT format used by Step 2 and Step 3.
        Uses hiring_cafe_url + ats_url + ats_platform (NOT nested ats: {}).
        This is critical — Step 2 checkpoint saves and Step 3 reads this format.
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
                        "hiring_cafe_url": j.get("hiring_cafe_url") or j.get("url") or f"https://hiring.cafe/viewjob/{j.get('job_id')}",
                        "ats_url": j.get("ats_url"),
                        "ats_platform": j.get("ats_platform"),
                        "source_keywords": j.get("source_keywords"),
                        "scraped_at": j.get("scraped_at"),
                        # Enriched fields
                        "job_tittle": j.get("job_tittle"),
                        "location": j.get("location"),
                        "comapany": j.get("comapany"),
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
            # Atomic rename — avoids corrupt file if crash happens mid-write
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
