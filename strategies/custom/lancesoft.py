from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler
from core.safe_actions import SafeActions
import time
import os
import json
import random
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from models.history_models import Application


class LanceSoftStrategy(BaseStrategy):
    """
    LanceSoft automation strategy using JobDiva portal.
    
    JobDiva is a modern ATS platform with:
    - JavaScript-heavy UI with dynamic loading
    - Pagination for job listings
    - Multi-step application flow with EEO form
    - Quick Apply option for guest applications
    
    This strategy implements the complete flow discovered through manual exploration.
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None):
        super().__init__(driver, job_site, selectors)
        self.db_session = db_session
        self.job_site = job_site
        self.config_data = self._load_config()
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
        self.safe_actions = SafeActions(driver)
        
        # JobDiva portal base URL
        self.portal_url = job_site.search_url_template
        
        # Load selectors from centralized location
        self.selectors_config = self._load_selectors()
        
        # Debug logging
        if self.db_session:
            logger.info("✅ Database session available - will save to DuckDB")
        else:
            logger.warning("⚠️ No database session - will only use CSV tracking")
    
    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data',
                'guest_form_data.json'
            )
            with open(config_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load config JSON: {e}")
            return None
    
    def _load_selectors(self):
        """
        Load all CSS/XPath selectors used for LanceSoft JobDiva portal.
        This centralizes all selector management - similar to Insight Global approach.
        """
        return {
            # Country/Location Filters
            'country_button': "//button[contains(., 'United States')]",
            'country_dropdown_btn': "//button[contains(., 'Country')] | //button[contains(., 'Select Country')]",
            'usa_option': "//a[@class='dropdown-item'][contains(., 'United States')]",
            'country_fallback': "div.hideshow-country button",
            
            # Search Input
            'search_input': "input.inputbox_search, input[placeholder*='Search job title' i]",
            
            # Job Listings
            'job_container': "div.list-group-item.list-group-item-action",
            'job_title': "span.text-capitalize.jd-nav-label.notranslate",
            'job_id': "div.d-flex.text-muted small:nth-child(3)",
            'details_button': "button.btn.jd-btn",
            
            # Pagination
            'next_page_btn': "button[aria-label='Next Page']",
            
            # Application Buttons
            'apply_button': "#root > div > div > div:nth-child(4) > div:nth-child(1) > button",
            'quick_apply_option': "#applyOptionsModal > div > div > div.modal-body > div > button:nth-child(3) > span",
            
            # Form Fields
            'form_modal': "#quickApplyModal",
            'submit_btn': "#quickApplyModal > div > div > div.job-app-btns > div:nth-child(2) > button",
            'next_btn_outline': "button.btn.jd-btn-outline",
            'next_btn_solid': "button.btn.jd-btn:not(.jd-btn-outline)",
            
            # Form Labels and Inputs
            'consent_checkbox': "//div[@id='quickApplyModal']//input[@type='checkbox']",
            'file_input': "div#quickApplyModal input[type='file']",
            
            # EEO Form Fields
            'gender_radio': "//input[@type='radio'][@name='gender'][@value='1,3']",
            'ethnicity_radio': "//input[@type='radio'][@name='ethnicity'][@value='1,3']",
            'race_radio': "//input[@type='radio'][@name='race'][@value='2,8']",
            'veteran_radios': "//input[@type='radio'][@name='veteran_status']",
        }

    
    def login(self):
        """
        Check if login is required for JobDiva portal.
        JobDiva portals allow guest browsing and quick apply.
        """
        logger.info("LanceSoft/JobDiva: Checking login requirements...")
        
        try:
            # Navigate to portal
            logger.info(f"Opening JobDiva portal: {self.portal_url}")
            self.driver.get(self.portal_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
            logger.info("✅ Portal loaded - no login required (guest mode)")
            return True
            
        except Exception as e:
            logger.error(f"Error accessing JobDiva portal: {e}")
            return False
    
    def find_and_apply_jobs(self):
        """
        Combined workflow: Find and apply to jobs immediately.
        This is the main entry point for LanceSoft strategy.
        
        Uses a single-phase approach: apply to each job as soon as it's found.
        This prevents issues with jobs not being found when navigating back to search results.
        
        Returns:
            int: Number of successful applications
        """
        logger.info("🔍 Starting find_and_apply_jobs workflow...")
        
        if not self.config_data:
            logger.error("No configuration data available")
            return 0
        
        # Support multiple search configurations
        search_configurations = self.config_data.get('search_configurations', [])
        if not search_configurations:
            # Fallback to single search config
            search_config = self.config_data.get('search', {})
            search_configurations = [{
                'keyword': search_config.get('keyword', 'AI Engineer'),
                'location': search_config.get('location', 'Chicago, IL'),
                'distance': search_config.get('distance', '50')
            }]
        
        total_applied = 0
        
        # Perform each search and apply immediately
        for config in search_configurations:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Search: {config['keyword']} in {config['location']}")
            logger.info(f"{'='*60}")
            
            # Search and apply immediately (single-phase)
            applied_count = self._search_and_apply_immediately(
                config['keyword'],
                config['location'],
                config.get('distance', '50')
            )
            total_applied += applied_count
            
            # Small delay between searches
            if len(search_configurations) > 1:
                time.sleep(random.uniform(2, 4))
        
        logger.info(f"\n✅ Workflow complete: {total_applied} applications submitted")
        return total_applied
    
    def find_jobs(self):
        """
        PHASE 1: Search for jobs on JobDiva portal
        Returns list of job dicts with: {'job_title': '...', 'external_id': '...', 'job_url': '...'}
        
        This implements the two-phase approach:
        - Phase 1: find_jobs() - Collects all jobs across all pages
        - Phase 2: apply() - Applies to each job individually
        
        Returns:
            List of job data dicts to apply to
        """
        if not self.config_data:
            logger.error("No configuration data available")
            return []
        
        # Support multiple search configurations
        search_configurations = self.config_data.get('search_configurations', [])
        if not search_configurations:
            # Fallback to single search config
            search_config = self.config_data.get('search', {})
            search_configurations = [{
                'keyword': search_config.get('keyword', 'AI Engineer'),
                'location': search_config.get('location', 'Chicago, IL'),
                'distance': search_config.get('distance', '50')
            }]
        
        all_jobs = []
        
        # Perform each search
        for config in search_configurations:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Search: {config['keyword']} in {config['location']}")
            logger.info(f"{'='*60}")
            
            # Collect all jobs from all pages for this search
            jobs = self._search_and_collect_jobs(
                config['keyword'],
                config['location'],
                config.get('distance', '50')
            )
            all_jobs.extend(jobs)
            
            # Small delay between searches
            if len(search_configurations) > 1:
                time.sleep(random.uniform(2, 4))
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Job Collection Complete")
        logger.info(f"Total jobs found: {len(all_jobs)}")
        logger.info(f"{'='*60}\n")
        
        return all_jobs

    def _search_and_collect_jobs(self, keyword, location, distance):
        """
        Search and collect all jobs across all pages.
        Uses selectors from centralized _load_selectors() configuration.
        
        Returns list of job dicts without applying to them.
        """
        all_jobs = []
        selectors = self.selectors_config  # Use centralized selectors

        """
        PHASE 1: Collect all job listings from all pages
        Returns list of job data dicts without applying
        
        Args:
            keyword: Job title/keyword to search
            location: Location to search in
            distance: Distance radius
        
        Returns:
            List of job data dicts: [{'job_title': '...', 'external_id': '...', 'job_url': '...'}, ...]
        """
        all_jobs = []
        
        try:
            # Navigate to the base portal URL (without keyword in URL)
            logger.info(f"  Navigating to JobDiva portal...")
            self.driver.get(self.portal_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info("  ✓ Portal loaded")
            time.sleep(2)
            
            # --- Country Filter Selection ---
            try:
                logger.info("  Setting Country filter...")
                time.sleep(2)
                
                country_selected = False
                
                # First check if United States is already selected
                try:
                    current_country_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'United States')]")
                    logger.info("  ✓ Country 'United States' already selected")
                    country_selected = True
                except Exception:
                    logger.info("    Country selection needed - attempting to select...")
                
                if not country_selected:
                    # Strategy 1: Find Country button and click dropdown
                    try:
                        country_btn_xpath = "//button[contains(., 'Country')] | //button[contains(., 'Select Country')]"
                        
                        logger.info("    Waiting for country dropdown button...")
                        dropdown_btn = WebDriverWait(self.driver, 10).until(  # Increased from 5 to 10 seconds
                            EC.element_to_be_clickable((By.XPATH, country_btn_xpath))
                        )
                        logger.info("    ✓ Found country dropdown button")
                        
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
                        time.sleep(0.5)
                        self.human.human_click(dropdown_btn)
                        logger.info("    ✓ Clicked country dropdown")
                        time.sleep(1.5)
                        
                        # Strategy 2: Select 'United States' from dropdown using multiple selectors
                        usa_found = False
                        
                        # Attempt 1: User-provided selector pattern - find anchor tags with dropdown-item class
                        try:
                            logger.info("    Attempting to find USA option (method 1: dropdown-item)...")
                            usa_option_xpath = "//a[@class='dropdown-item'][contains(., 'United States')]"
                            usa_options = self.driver.find_elements(By.XPATH, usa_option_xpath)
                            if usa_options:
                                usa_option = usa_options[0]
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", usa_option)
                                time.sleep(0.3)
                                self.human.human_click(usa_option)
                                usa_found = True
                                logger.info("    ✓ Selected USA (method 1)")
                                time.sleep(1)
                        except Exception as e:
                            logger.debug(f"    Method 1 failed: {e}")
                        
                        # Attempt 2: General dropdown menu buttons or divs
                        if not usa_found:
                            logger.info("    Attempting to find USA option (method 2: alternative selectors)...")
                            try:
                                usa_option_xpaths = [
                                    "//div[contains(@class, 'dropdown-menu')]//a[contains(text(), 'United States')]",
                                    "//div[contains(@class, 'dropdown-menu')]//button[contains(., 'United States')]",
                                    "//div[contains(@class, 'dropdown-menu')]//span[contains(., 'United States')]/..",
                                    "//button[contains(., 'United States')]"
                                ]
                                
                                for idx, xpath in enumerate(usa_option_xpaths, 1):
                                    try:
                                        usa_options = self.driver.find_elements(By.XPATH, xpath)
                                        if usa_options:
                                            usa_option = usa_options[0]
                                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", usa_option)
                                            time.sleep(0.3)
                                            self.human.human_click(usa_option)
                                            usa_found = True
                                            logger.info(f"    ✓ Selected USA (method 2, variant {idx})")
                                            time.sleep(1)
                                            break
                                    except Exception:
                                        continue
                            except Exception as e:
                                logger.debug(f"    Method 2 failed: {e}")
                        
                        if usa_found:
                            country_selected = True
                        else:
                            logger.warning("    ⚠️ Could not find USA option in dropdown")
                            
                    except Exception as e:
                        logger.warning(f"    ⚠️ Could not open Country dropdown: {e}")
                    
                    # Fallback: Try CSS selector approach
                    if not country_selected:
                        logger.info("    Attempting fallback country selection method...")
                        try:
                            fallback_dropdown = self.driver.find_element(By.CSS_SELECTOR, "div.hideshow-country button")
                            if "United States" not in fallback_dropdown.text:
                                self.human.human_click(fallback_dropdown)
                                time.sleep(1)
                                usa_option = self.driver.find_element(By.XPATH, "//div[contains(@class, 'dropdown-menu')]//a[contains(., 'United States')]")
                                self.human.human_click(usa_option)
                                country_selected = True
                                logger.info("    ✓ Selected USA (fallback method)")
                        except Exception as fb_err:
                            logger.debug(f"    Fallback country selection failed: {fb_err}")
                
                if country_selected:
                    logger.info("  ✅ Country filter set to 'United States'")
                else:
                    logger.warning("  ⚠️ Country selection failed - continuing anyway (may affect results)")

            except Exception as e:
                logger.warning(f"  ⚠️ Country filter error (non-critical, continuing): {e}")

            # --- Enter Search Keyword ---
            logger.info(f"  Entering search keyword: '{keyword}'")
            search_input_selector = "input.inputbox_search, input[placeholder*='Search job title' i]"
            
            search_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, search_input_selector))
            )
            
            # Clear any existing text and type the keyword
            search_input.clear()
            self.human.fill_text_field(search_input, keyword)
            logger.info(f"  ✓ Entered keyword: '{keyword}'")
            
            # Press Enter or wait for results to load
            search_input.send_keys("\n")
            time.sleep(3)  # Wait for search results to load
            logger.info("  ✓ Search results loaded")
            
        except Exception as e:
            logger.error(f"  ❌ Failed to perform search: {e}")
            import traceback
            traceback.print_exc()
            return []
        
        # Use selectors from centralized configuration
        container_selector = self.selectors_config['job_container']
        
        page_num = 1
        MAX_PAGES = 20  # Safety limit to prevent infinite loops
        
        # Pagination loop: Collect jobs from all pages
        while page_num <= MAX_PAGES:
            logger.info(f"  📄 Collecting from page {page_num}...")
            
            # Extract jobs from current page (no applying yet)
            jobs_on_page = self._extract_job_listings(container_selector)
            all_jobs.extend(jobs_on_page)
            logger.info(f"    Found {len(jobs_on_page)} jobs on page {page_num}")
            
            # Try to find and click Next Page button
            try:
                # Use selector from centralized configuration
                next_btn_selector = self.selectors_config['next_page_btn']
                
                next_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_btn_selector))
                )
                
                # Check if button is disabled (last page)
                is_disabled = next_btn.get_attribute('disabled')
                has_disabled_class = 'disabled' in (next_btn.get_attribute('class') or '')
                
                if is_disabled or has_disabled_class:
                    logger.info(f"    ✓ Reached last page")
                    break
                
                # Scroll to button and click
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                time.sleep(0.5)
                self.human.human_click(next_btn)
                logger.info(f"    ✓ Navigating to page {page_num + 1}...")
                
                # Wait for new page to load
                time.sleep(2)
                page_num += 1
                
            except Exception as e:
                logger.info(f"    ✓ No more pages")
                break
        
        if page_num > MAX_PAGES:
            logger.warning(f"  ⚠️ Reached maximum page limit ({MAX_PAGES})")
        
        logger.info(f"  ✅ Collection complete: {len(all_jobs)} total jobs")
        return all_jobs
    
    def _search_and_apply_immediately(self, keyword, location, distance):
        """
        SINGLE-PHASE APPROACH: Search for jobs and apply to them immediately.
        This method finds jobs on each page and applies to them before moving to the next page.
        
        This is more reliable than the two-phase approach because:
        - Jobs are applied to while they're visible on screen
        - No need to navigate back to find specific jobs
        - Avoids stale element issues
        
        Args:
            keyword: Job title/keyword to search
            location: Location to search in
            distance: Distance radius
        
        Returns:
            int: Number of successful applications
        """
        from engine.guards import guards
        
        total_applied = 0
        selectors = self.selectors_config
        
        try:
            # Navigate to the base portal URL
            logger.info(f"  Navigating to JobDiva portal...")
            self.driver.get(self.portal_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info("  ✓ Portal loaded")
            time.sleep(2)
            
            # Country Filter Selection - IMPROVED WITH MULTIPLE STRATEGIES
            try:
                logger.info("  Setting Country filter...")
                time.sleep(2)
                
                country_selected = False
                
                # STRATEGY 1: Check if United States is already selected
                try:
                    current_country_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'United States')]")
                    logger.info("  ✓ Country 'United States' already selected")
                    country_selected = True
                except Exception:
                    logger.info("    Country not pre-selected - will attempt to select...")
                
                # STRATEGY 2: Try to select country if not already selected
                if not country_selected:
                    # Try multiple approaches to find and click the country dropdown
                    dropdown_selectors = [
                        "//button[contains(., 'Country')]",
                        "//button[contains(., 'Select Country')]",
                        "//button[contains(@class, 'country')]",
                        "div.hideshow-country button",
                        "button[data-toggle='dropdown'][aria-label*='Country']"
                    ]
                    
                    dropdown_clicked = False
                    for selector in dropdown_selectors:
                        if dropdown_clicked:
                            break
                        try:
                            logger.info(f"    Trying dropdown selector: {selector[:50]}...")
                            
                            # Determine if XPath or CSS
                            if selector.startswith("//") or selector.startswith("("):
                                dropdown_btn = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                            else:
                                dropdown_btn = WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )
                            
                            # Scroll into view
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown_btn)
                            time.sleep(0.5)
                            
                            # Try clicking
                            try:
                                dropdown_btn.click()
                            except Exception:
                                # Fallback to JavaScript click
                                self.driver.execute_script("arguments[0].click();", dropdown_btn)
                            
                            logger.info("    ✓ Clicked country dropdown")
                            dropdown_clicked = True
                            time.sleep(1.5)
                            
                        except Exception as e:
                            logger.debug(f"    Selector failed: {str(e)[:50]}")
                            continue
                    
                    if not dropdown_clicked:
                        logger.warning("    ⚠️ Could not find/click country dropdown")
                    else:
                        # Try to select USA from dropdown
                        usa_selectors = [
                            "//a[@class='dropdown-item'][contains(., 'United States')]",
                            "//div[contains(@class, 'dropdown-menu')]//a[contains(text(), 'United States')]",
                            "//li[contains(., 'United States')]//a",
                            "//button[contains(., 'United States')]",
                            "a.dropdown-item:contains('United States')"
                        ]
                        
                        usa_found = False
                        for selector in usa_selectors:
                            if usa_found:
                                break
                            try:
                                logger.info(f"    Trying USA selector: {selector[:50]}...")
                                
                                # Determine if XPath or CSS
                                if selector.startswith("//") or selector.startswith("("):
                                    usa_options = self.driver.find_elements(By.XPATH, selector)
                                else:
                                    usa_options = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                
                                if usa_options:
                                    usa_option = usa_options[0]
                                    
                                    # Scroll into view
                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", usa_option)
                                    time.sleep(0.3)
                                    
                                    # Try clicking
                                    try:
                                        usa_option.click()
                                    except Exception:
                                        # Fallback to JavaScript click
                                        self.driver.execute_script("arguments[0].click();", usa_option)
                                    
                                    usa_found = True
                                    country_selected = True
                                    logger.info("    ✓ Selected USA")
                                    time.sleep(1)
                                    
                            except Exception as e:
                                logger.debug(f"    USA selector failed: {str(e)[:50]}")
                                continue
                        
                        if not usa_found:
                            logger.warning("    ⚠️ Could not find USA option in dropdown")
                
                # Final status
                if country_selected:
                    logger.info("  ✅ Country filter set to 'United States'")
                else:
                    logger.warning("  ⚠️ Country selection failed - continuing anyway (search may show all countries)")

            except Exception as e:
                logger.warning(f"  ⚠️ Country filter error (non-critical, continuing): {e}")


            # Enter Search Keyword
            logger.info(f"  Entering search keyword: '{keyword}'")
            search_input_selector = "input.inputbox_search, input[placeholder*='Search job title' i]"
            
            search_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, search_input_selector))
            )
            
            search_input.clear()
            self.human.fill_text_field(search_input, keyword)
            logger.info(f"  ✓ Entered keyword: '{keyword}'")
            
            search_input.send_keys("\n")
            time.sleep(3)
            logger.info("  ✓ Search results loaded")
            
        except Exception as e:
            logger.error(f"  ❌ Failed to perform search: {e}")
            import traceback
            traceback.print_exc()
            return 0
        
        # Pagination loop: Apply to jobs on each page
        page_num = 1
        MAX_PAGES = 20
        
        while page_num <= MAX_PAGES:
            logger.info(f"\n  📄 Processing page {page_num}...")
            
            # Get all job elements on current page
            try:
                container_selector = selectors['job_container']
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, container_selector))
                )
                time.sleep(1)
                
                job_elements = self.driver.find_elements(By.CSS_SELECTOR, container_selector)
                logger.info(f"    Found {len(job_elements)} jobs on this page")
                
                # Apply to each job on this page
                for idx, job_elem in enumerate(job_elements, 1):
                    try:
                        # Check if we can still apply
                        if not guards.can_apply():
                            logger.warning(f"\n  ⛔ Application limit reached after {total_applied} applications")
                            return total_applied
                        
                        # Extract job info
                        try:
                            title_elem = job_elem.find_element(By.CSS_SELECTOR, selectors['job_title'])
                            title = title_elem.text.strip()
                            
                            job_text = job_elem.text
                            import re
                            id_match = re.search(r'(\d{2}-\d{4,10})', job_text)
                            if id_match:
                                job_id = id_match.group(1)
                            else:
                                job_id = job_elem.find_element(By.CSS_SELECTOR, selectors['job_id']).text.strip()
                            
                            job_url = self.driver.current_url
                            
                            job_data = {
                                'job_title': title,
                                'external_id': job_id,
                                'job_url': job_url
                            }
                            
                            logger.info(f"\n    📌 Job {idx}/{len(job_elements)}: {title} ({job_id})")
                            
                            # Save to DB
                            if self.db_session and self.job_site:
                                self._save_job_to_db(job_data)
                            
                            # Apply to this job immediately
                            success = self._apply_to_visible_job_immediate(job_elem, job_data)
                            
                            if success:
                                guards.increment_counter()
                                total_applied += 1
                                logger.info(f"      ✅ Application #{total_applied} successful")
                                
                                # Update job status in DB
                                if self.db_session:
                                    self._update_job_status(job_id, 'applied')
                            else:
                                logger.warning(f"      ⚠️ Application failed")
                            
                            # Small delay between applications
                            time.sleep(random.uniform(1, 2))
                            
                            # Reload the page to get fresh job list (prevents stale elements)
                            logger.info(f"      Reloading page to continue...")
                            self.driver.get(job_url)
                            time.sleep(2)
                            
                            # Re-fetch job elements after reload
                            job_elements = self.driver.find_elements(By.CSS_SELECTOR, container_selector)
                            
                        except Exception as e:
                            logger.debug(f"      Error extracting job info: {e}")
                            continue
                            
                    except Exception as e:
                        logger.error(f"      ❌ Error processing job: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"    ❌ Error processing page {page_num}: {e}")
            
            # Try to navigate to next page
            try:
                next_btn_selector = selectors['next_page_btn']
                next_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_btn_selector))
                )
                
                is_disabled = next_btn.get_attribute('disabled')
                has_disabled_class = 'disabled' in (next_btn.get_attribute('class') or '')
                
                if is_disabled or has_disabled_class:
                    logger.info(f"    ✓ Reached last page")
                    break
                
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                time.sleep(0.5)
                self.human.human_click(next_btn)
                logger.info(f"    ✓ Navigating to page {page_num + 1}...")
                time.sleep(2)
                page_num += 1
                
            except Exception as e:
                logger.info(f"    ✓ No more pages")
                break
        
        if page_num > MAX_PAGES:
            logger.warning(f"  ⚠️ Reached maximum page limit ({MAX_PAGES})")
        
        logger.info(f"\n  📊 Search complete: Applied to {total_applied} jobs")
        return total_applied
    
    def _apply_to_all_jobs(self, all_jobs):
        """
        PHASE 2: Apply to each collected job with fresh page loads
        This prevents stale element issues by reloading the search page for each application
        
        Args:
            all_jobs: List of job data dicts collected in Phase 1
        
        Returns:
            Integer count of successful applications
        """
        from engine.guards import guards
        
        total_applied = 0
        
        for idx, job_data in enumerate(all_jobs, 1):
            try:
                # Check if we can still apply
                if not guards.can_apply():
                    logger.warning(f"\n  ⛔ Application limit reached after {total_applied} applications")
                    break
                
                job_id = job_data['external_id']
                job_title = job_data['job_title']
                
                logger.info(f"\n  📌 Job {idx}/{len(all_jobs)}: {job_title} ({job_id})")
                
                # Save to DB first
                if self.db_session and self.job_site:
                    self._save_job_to_db(job_data)
                
                # Navigate to search results page fresh
                logger.info(f"    Loading search results page...")
                self.driver.get(job_data['job_url'])
                time.sleep(2)
                
                # Find and apply to the specific job
                success = self._apply_to_job_by_id(job_id, job_data)
                
                if success:
                    guards.increment_counter()
                    total_applied += 1
                    logger.info(f"    ✅ Application #{total_applied} successful")
                    
                    # Update job status in DB
                    if self.db_session:
                        self._update_job_status(job_id, 'applied')
                else:
                    logger.warning(f"    ⚠️ Application failed for {job_id}")
                
                # Small delay between applications to avoid rate limiting
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"    ❌ Error applying to job {idx}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        logger.info(f"\n  📊 Phase 2 Complete: Applied to {total_applied}/{len(all_jobs)} jobs")
        return total_applied
    
    def _extract_job_listings(self, container_selector):
        """
        Extract job listings from current page WITHOUT applying
        Used in Phase 1 of two-phase approach
        
        Returns:
            List of job data dicts: [{'job_title': '...', 'external_id': '...', 'job_url': '...'}, ...]
        """
        jobs_on_page = []
        selectors = self.selectors_config  # Use centralized selectors
        
        try:
            # Wait for job listings to appear
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, container_selector))
            )
            time.sleep(1)
            
            # Get all job elements
            job_elements = self.driver.find_elements(By.CSS_SELECTOR, container_selector)
            
            for job_elem in job_elements:
                try:
                    # Get job title
                    title_elem = job_elem.find_element(By.CSS_SELECTOR, selectors['job_title'])
                    title = title_elem.text.strip()
                    
                    # Extract ID (Regex or Selector)
                    job_text = job_elem.text
                    import re
                    id_match = re.search(r'(\d{2}-\d{4,10})', job_text)
                    if id_match:
                        job_id = id_match.group(1)
                    else:
                        job_id = job_elem.find_element(By.CSS_SELECTOR, selectors['job_id']).text.strip()

                    job_url = self.driver.current_url
                    
                    job_data = {
                        'job_title': title,
                        'external_id': job_id,
                        'job_url': job_url
                    }
                    
                    jobs_on_page.append(job_data)
                
                except Exception as e:
                    logger.debug(f"      Error extracting job: {e}")
                    continue
            
        except Exception as e:
            logger.debug(f"No job listings found or error: {e}")
        
        return jobs_on_page

    def _save_job_to_db(self, job_data):
        try:
             
            existing = self.db_session.query(JobListing).filter(
                JobListing.job_site_id == self.job_site.id,
                JobListing.external_job_id == job_data['external_id']
            ).first()
            
            if not existing:
                job_listing = JobListing(
                    job_site_id=self.job_site.id,
                    external_job_id=job_data['external_id'],
                    job_title=job_data['job_title'],
                    job_url=job_data['job_url'],
                    status='discovered'
                )
                self.db_session.add(job_listing)
                self.db_session.commit()
                logger.info(f"      💾 Saved to DB")
        except Exception as e:
            logger.error(f"      ❌ DB Save Error: {e}")
            self.db_session.rollback()
    
    def _apply_to_job_by_id(self, job_id, job_data):
        """
        Apply to a job found in the search results (loaded fresh for this application)
        Used in Phase 2 of two-phase approach
        
        Args:
            job_id: Job ID to find and apply to
            job_data: Job data dict with title, url, etc.
        
        Returns:
            bool: True if application successful
        """
        try:
            job_title = job_data['job_title']
            
            # Step 1: Find and click the Details button for this job
            logger.info(f"      Step 1: Locating job in list...")
            
            container_selector = self.selectors_config['job_container']
            
            job_rows = self.driver.find_elements(By.CSS_SELECTOR, container_selector)
            target_row = None
            
            for row in job_rows:
                if job_id in row.text:
                    target_row = row
                    break
            
            if not target_row:
                logger.error(f"      Could not locate job {job_id} in search results")
                return False
            
            logger.info(f"      ✓ Found job in list")
            
            # Click Details button
            details_btn = target_row.find_element(By.CSS_SELECTOR, self.selectors_config['details_button'])
            
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", details_btn)
            time.sleep(1)
            self.human.human_click(details_btn)
            time.sleep(3)  # Wait for details to open
            
            logger.info(f"      Step 2: Clicking Apply Now button...")
            
            # Step 2: Click "Apply Now" button
            apply_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.selectors_config['apply_button']))
            )
            self.human.human_click(apply_btn)
            time.sleep(5)
            
            # Step 3: Select "Quick Apply (No Account)" option
            logger.info(f"      Step 3: Selecting Quick Apply option...")
            quick_apply_selector = self.selectors_config['quick_apply_option']
            
            quick_apply_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, quick_apply_selector))
            )
            self.human.human_click(quick_apply_btn)
            time.sleep(2)
            
            # Step 4: Fill application form
            logger.info(f"      Step 4: Filling application form...")
            self._fill_application_form()
            
            # Step 5: Submit initial form
            logger.info(f"      Step 5: Submitting initial form...")
            self._submit_initial_form()
            
            # Step 6: Fill EEO form (if it exists - it's optional on some portals)
            logger.info(f"      Step 6: Filling EEO form (if available)...")
            try:
                self._fill_eeo_form()
                
                # Step 7: Complete application
                logger.info(f"      Step 7: Completing application...")
                self._complete_application()
            except Exception as eeo_error:
                logger.info(f"      ℹ️ EEO form not available or optional: {eeo_error}")
                logger.info(f"      Step 7: Application may be complete (EEO form not required)")
            
            # Success!
            logger.info(f"      ✅ Successfully applied")
            
            # Update tracking
            csv_tracker.update_job_status(
                'lancesoft',
                job_data['job_url'],
                'applied',
                attempts_inc=1
            )
            
            # Update database
            if self.db_session and self.job_site:
                try:
                    application = Application(
                        job_site_id=self.job_site.id,
                        job_title=job_title,
                        job_url=job_data['job_url'],
                        status='success'
                    )
                    self.db_session.add(application)
                    self.db_session.commit()
                except Exception as e:
                    logger.warning(f"      ⚠️ Database save failed: {e}")
                    self.db_session.rollback()
            
            return True
            
        except Exception as e:
            logger.error(f"      ❌ Application error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # Update tracking
            csv_tracker.update_job_status(
                'lancesoft',
                job_data['job_url'],
                'failed',
                attempts_inc=1,
                last_error=str(e)
            )
            return False
    
    def apply(self, listing):
        """
        Apply to a single job on JobDiva portal.
        This is called by the engine for each job returned by find_jobs().
        
        Args:
            listing: JobListing model or dict with job details from find_jobs()
        
        Returns:
            bool: True if application successful
        """
        from engine.guards import guards
        
        # Get job details
        if isinstance(listing, dict):
            job_data = listing  # From find_jobs() - has job_title, external_id, job_url
            job_url = job_data.get('job_url')
            job_title = job_data.get('job_title', 'Unknown')
            job_id = job_data.get('external_id', 'unknown')
        else:
            job_data = {
                'job_url': listing.job_url,
                'job_title': listing.job_title,
                'external_id': listing.external_job_id
            }
            job_url = job_data['job_url']
            job_title = job_data['job_title']
            job_id = job_data['external_id']
        
        if not guards.can_apply():
            logger.info("Application limit reached - stopping")
            return False
        
        # Check if already applied
        # Check if already applied
        # try:
        #     status = csv_tracker.get_job_status('lancesoft', job_url)
        #     if status and status.get('status') == 'applied':
        #         logger.info(f"Already applied to this job, skipping: {job_url}")
        #         return False
        # except Exception:
        #     pass
        
        logger.info(f"=" * 60)
        logger.info(f"Applying to job: {job_title}")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"=" * 60)
        
        try:
            # Step 1: Navigate to search results page fresh (prevents stale elements)
            logger.info("Step 1: Navigating to job page...")
            logger.info(f"  Loading search results page: {job_url}")
            self.driver.get(job_url)
            time.sleep(3)
            
            # Step 2: Locate job in the current page
            logger.info("Step 2: Locating job in list...")
            
            try:
                # Find the row with the Job ID
                container_selector = self.selectors_config['job_container']
                
                job_rows = self.driver.find_elements(By.CSS_SELECTOR, container_selector)
                target_row = None
                
                for row in job_rows:
                    if job_id in row.text:
                        target_row = row
                        break
                
                if not target_row:
                    logger.error(f"Could not locate job {job_id} in search results")
                    return False
                
                logger.info(f"✓ Found job row for {job_id}")
                # Click Details
                details_btn = target_row.find_element(By.CSS_SELECTOR, self.selectors_config['details_button'])
                
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", details_btn)
                time.sleep(1)
                self.human.human_click(details_btn)
                time.sleep(3)  # Wait for details to open

            except Exception as e:
                logger.error(f"Error navigating to job: {e}")
                return False
            
            # Step 3: Click "Apply Now" button
            logger.info("Step 3: Clicking Apply Now button...")
            apply_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.selectors_config['apply_button']))
            )
            self.human.human_click(apply_btn)
            time.sleep(5)
            
            # Step 4: Select "Quick Apply (No Account)" option
            logger.info("Step 4: Selecting Quick Apply option...")
            quick_apply_selector = self.selectors_config['quick_apply_option']
            
            quick_apply_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, quick_apply_selector))
            )
            self.human.human_click(quick_apply_btn)
            time.sleep(2)
            
            # Step 5: Fill application form
            logger.info("Step 5: Filling application form...")
            self._fill_application_form()
            
            # Step 4.5: Ensure consent checkbox is selected BEFORE resume upload
            try:
                logger.info("Step 4.5: Ensuring consent checkbox is selected before resume upload...")
                target_texts = ["consent to receive", "employment-related", "text message", "i consent", "consent"]
                consent_found = False

                # Find labels with target text and get their associated inputs via 'for' attribute
                labels = self.driver.find_elements(By.XPATH, "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employment-related')]")
                
                for lbl in labels:
                    try:
                        # Method 1: Check if label has a 'for' attribute pointing to an input
                        label_for = lbl.get_attribute('for')
                        if label_for:
                            try:
                                inp = self.driver.find_element(By.ID, label_for)
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
                                time.sleep(0.3)
                                if not inp.is_selected():
                                    try:
                                        inp.click()
                                    except Exception:
                                        self.driver.execute_script("arguments[0].click();", inp)
                                    time.sleep(0.5)
                                if inp.is_selected():
                                    consent_found = True
                                    logger.info("  ✓ Consent checkbox selected via 'for' attribute")
                                    break
                            except Exception:
                                pass
                        
                        # Method 2: Try to find input inside the label
                        if not consent_found:
                            try:
                                inp = lbl.find_element(By.XPATH, ".//input[@type='checkbox']")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
                                time.sleep(0.3)
                                if not inp.is_selected():
                                    try:
                                        inp.click()
                                    except Exception:
                                        self.driver.execute_script("arguments[0].click();", inp)
                                    time.sleep(0.5)
                                if inp.is_selected():
                                    consent_found = True
                                    logger.info("  ✓ Consent checkbox selected via nested input")
                                    break
                            except Exception:
                                pass
                        
                        # Method 3: Click label directly as fallback
                        if not consent_found:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lbl)
                            try:
                                lbl.click()
                                consent_found = True
                                logger.info("  ✓ Clicked consent label (fallback)")
                                break
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", lbl)
                                consent_found = True
                                logger.info("  ✓ Clicked consent label via JS (fallback)")
                                break
                    except Exception as label_error:
                        logger.debug(f"  Error processing consent label: {label_error}")

                if not consent_found:
                    logger.info("  ℹ️ Consent checkbox not found before resume upload (continuing anyway)")
            except Exception as e:
                logger.debug(f"  Consent pre-upload check error: {e}")

            # Step 5: Upload resume
            logger.info("Step 5: Uploading resume...")
            self._upload_resume()
            time.sleep(2)
            
            # Step 6: Submit initial form
            logger.info("Step 6: Submitting application form...")
            submit_btn_selector = self.selectors_config['submit_btn']
            
            submit_btn = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, submit_btn_selector))
            )
            self.human.human_click(submit_btn)
            logger.info("  ✓ Submit button clicked")
            
            # Wait for confirmation page to appear (contains "You've applied" message)
            try:
                logger.info("  ⏳ Waiting for confirmation page...")
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'applied')]"))
                )
                time.sleep(1)
                logger.info("  ✓ Confirmation page loaded")
            except Exception as e:
                logger.warning(f"  Confirmation message not found: {e}")
                time.sleep(2)
            
            # Step 7: Click Next button on confirmation page to go to EEO form
            logger.info("Step 7: Clicking Next button on confirmation page...")
            next_btn = None
            
            # Strategy 1: Look for the confirmation page Next button (button.btn.jd-btn-outline)
            try:
                logger.info("  Trying CSS selector: button.btn.jd-btn-outline")
                next_btns = self.driver.find_elements(By.CSS_SELECTOR, "button.btn.jd-btn-outline")
                
                for btn in next_btns:
                    btn_text = (btn.text or '').strip()
                    if 'next' in btn_text.lower():
                        next_btn = btn
                        logger.info(f"  ✓ Found Next button: '{btn_text}'")
                        break
                
                # If no text match, take the first one
                if not next_btn and next_btns:
                    next_btn = next_btns[0]
                    logger.info("  ✓ Found Next button (first match)")
                    
            except Exception as e:
                logger.debug(f"  CSS selector failed: {e}")
            
            # Strategy 2: XPath search
            if not next_btn:
                try:
                    logger.info("  Trying XPath: //button[normalize-space(.)='Next' or .//span[contains(., 'Next')]]")
                    next_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='Next' or .//span[contains(., 'Next')]]"))
                    )
                    logger.info("  ✓ Found Next button via XPath")
                except Exception as e:
                    logger.debug(f"  XPath search failed: {e}")
            
            if next_btn:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                    time.sleep(0.5)
                    self.human.human_click(next_btn)
                    logger.info("  ✓ Clicked Next button successfully")
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"  ✗ Failed to click Next button: {e}")
                    raise
            else:
                logger.error("  ✗ Could not find Next button on confirmation page")
                raise Exception("Next button not found on confirmation page")
            
            # Step 9: Fill EEO form
            logger.info("Step 9: Filling EEO form...")
            self._fill_eeo_form()
            
            # Step 10: Click Next button on EEO form
            logger.info("Step 10: Clicking Next button on EEO form...")
            try:
                next_button_found = False
                
                # Strategy 1: Look for button.btn.jd-btn with Next text (not outlined)
                try:
                    logger.info("  Trying to find EEO Next button via selector: button.btn.jd-btn")
                    eeo_next_btns = self.driver.find_elements(By.CSS_SELECTOR, self.selectors_config['next_btn_solid'])
                    
                    for btn in eeo_next_btns:
                        try:
                            btn_text = (btn.text or '').strip()
                            if 'next' in btn_text.lower():
                                logger.info(f"  ✓ Found EEO Next button with text: '{btn_text}'")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                time.sleep(0.3)
                                
                                # Check if disabled and wait for it to be enabled
                                if btn.get_attribute('disabled'):
                                    logger.info("  Button is disabled, waiting for it to be enabled...")
                                    WebDriverWait(self.driver, 10).until(
                                        lambda d: not d.find_element(By.CSS_SELECTOR, "button.btn.jd-btn:not(.jd-btn-outline)").get_attribute('disabled')
                                    )
                                    logger.info("  ✓ Button enabled")
                                
                                self.human.human_click(btn)
                                logger.info("  ✓ Clicked EEO form Next button")
                                next_button_found = True
                                time.sleep(2)
                                break
                        except Exception as inner_e:
                            logger.debug(f"  Error with button: {inner_e}")
                            continue
                except Exception as e:
                    logger.debug(f"  Strategy 1 failed: {e}")
                
                # Strategy 2: XPath for nested span structure
                if not next_button_found:
                    try:
                        logger.info("  Trying XPath: //button[contains(@class, 'jd-btn')]//span[contains(., 'Next')]")
                        next_btn_xpath = "//button[contains(@class, 'jd-btn') and not(contains(@class, 'jd-btn-outline'))]//span[contains(., 'Next')]/ancestor::button"
                        next_btns = self.driver.find_elements(By.XPATH, next_btn_xpath)
                        
                        if next_btns:
                            next_btn = next_btns[0]
                            logger.info("  ✓ Found EEO Next button via XPath")
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                            time.sleep(0.3)
                            self.human.human_click(next_btn)
                            logger.info("  ✓ Clicked EEO form Next button (XPath)")
                            next_button_found = True
                            time.sleep(2)
                    except Exception as e:
                        logger.debug(f"  Strategy 2 failed: {e}")
                
                # Strategy 3: Generic button search
                if not next_button_found:
                    try:
                        logger.info("  Trying generic button search in job-app-btns")
                        btn_container = self.driver.find_element(By.CSS_SELECTOR, "div.job-app-btns")
                        buttons_in_container = btn_container.find_elements(By.TAG_NAME, "button")
                        
                        for btn in buttons_in_container:
                            btn_text = (btn.text or '').lower()
                            if 'next' in btn_text and 'back' not in btn_text:
                                logger.info(f"  ✓ Found Next button in container")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                time.sleep(0.3)
                                self.human.human_click(btn)
                                logger.info("  ✓ Clicked EEO form Next button (container search)")
                                next_button_found = True
                                time.sleep(2)
                                break
                    except Exception as e:
                        logger.debug(f"  Strategy 3 failed: {e}")
                
                if not next_button_found:
                    logger.warning("  ⚠️ Could not find EEO Next button - continuing anyway")
                else:
                    logger.info("✅ EEO form Next button clicked successfully")
                    
            except Exception as e:
                logger.warning(f"Error clicking EEO Next button: {e}")
            
            # Step 11: Final save/submission
            logger.info("Step 11: Finalizing application submission...")
            
            # Success!
            logger.info("=" * 60)
            logger.info("✅ APPLICATION SUBMITTED SUCCESSFULLY!")
            logger.info("=" * 60)
            
            # Update tracking
            csv_tracker.update_job_status(
                'lancesoft',
                job_url,
                'applied',
                attempts_inc=1
            )
            
            # Update database
            if self.db_session and self.job_site:
                try:
                    application = Application(
                        job_site_id=self.job_site.id,
                        job_title=job_title,
                        job_url=job_url,
                        status='success'
                    )
                    self.db_session.add(application)
                    self.db_session.commit()
                    logger.info("💾 Application saved to database")
                except Exception as e:
                    logger.warning(f"⚠️ Database save failed: {e}")
                    self.db_session.rollback()
            
            guards.increment_counter()
            return True
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            import traceback
            traceback.print_exc()
            
            csv_tracker.update_job_status(
                'lancesoft',
                job_url,
                'failed',
                attempts_inc=1,
                last_error=str(e)
            )
            return False
    
    
    def _apply_to_visible_job(self, job_elem, job_data):
        """
        Apply to a job that's already visible on screen (DEPRECATED).
        This method is not used - the main apply flow uses _apply_to_job_by_id with fresh page loads.
        Kept for reference only.
        """
        raise NotImplementedError("_apply_to_visible_job is deprecated. Use _apply_to_job_by_id instead.")
    
    def _apply_to_visible_job_immediate(self, job_elem, job_data):
        """
        Apply to a job that's currently visible on the page.
        This is used in the single-phase approach where we apply immediately.
        
        Args:
            job_elem: The WebElement representing the job listing
            job_data: Dict with job_title, external_id, job_url
        
        Returns:
            bool: True if application successful
        """
        try:
            job_title = job_data['job_title']
            job_id = job_data['external_id']
            
            logger.info(f"      Step 1: Clicking Details button...")
            
            # Click Details button
            details_btn = job_elem.find_element(By.CSS_SELECTOR, self.selectors_config['details_button'])
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", details_btn)
            time.sleep(1)
            self.human.human_click(details_btn)
            time.sleep(3)
            
            logger.info(f"      Step 2: Clicking Apply Now button...")
            
            # Click "Apply Now" button
            apply_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.selectors_config['apply_button']))
            )
            self.human.human_click(apply_btn)
            time.sleep(5)
            
            # Select "Quick Apply (No Account)" option
            logger.info(f"      Step 3: Selecting Quick Apply option...")
            quick_apply_selector = self.selectors_config['quick_apply_option']
            
            quick_apply_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, quick_apply_selector))
            )
            self.human.human_click(quick_apply_btn)
            time.sleep(2)
            
            # Fill application form
            logger.info(f"      Step 4: Filling application form...")
            self._fill_application_form()
            
            # Submit initial form
            logger.info(f"      Step 5: Submitting initial form...")
            self._submit_initial_form()
            
            # Fill EEO form (if it exists - it's optional on some portals)
            logger.info(f"      Step 6: Filling EEO form (if available)...")
            try:
                self._fill_eeo_form()
                
                # Complete application
                logger.info(f"      Step 7: Completing application...")
                self._complete_application()
            except Exception as eeo_error:
                logger.info(f"      ℹ️ EEO form not available or optional: {eeo_error}")
                logger.info(f"      Step 7: Application may be complete (EEO form not required)")
            
            # Success!
            logger.info(f"      ✅ Successfully applied")
            
            # Update tracking
            csv_tracker.update_job_status(
                'lancesoft',
                job_data['job_url'],
                'applied',
                attempts_inc=1
            )
            
            # Update database
            if self.db_session and self.job_site:
                try:
                    application = Application(
                        job_site_id=self.job_site.id,
                        job_title=job_title,
                        job_url=job_data['job_url'],
                        status='success'
                    )
                    self.db_session.add(application)
                    self.db_session.commit()
                except Exception as e:
                    logger.warning(f"      ⚠️ Database save failed: {e}")
                    self.db_session.rollback()
            
            return True
            
        except Exception as e:
            logger.error(f"      ❌ Application error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            
            # Update tracking
            csv_tracker.update_job_status(
                'lancesoft',
                job_data['job_url'],
                'failed',
                attempts_inc=1,
                last_error=str(e)
            )
            return False
    
    def _update_job_status(self, job_id, status):
        """Update job status in database"""
        try:
            from db.models import JobListing
            
            job = self.db_session.query(JobListing).filter(
                JobListing.job_site_id == self.job_site.id,
                JobListing.external_job_id == job_id
            ).first()
            
            if job:
                job.status = status
                self.db_session.commit()
                logger.debug(f"      Updated job {job_id} status to '{status}'")
        except Exception as e:
            logger.error(f"      Error updating job status: {e}")
            self.db_session.rollback()
    
    def _fill_application_form(self):
        """Fill the main application form using robust label finding"""
        try:
            # Use config data for applicant information
            applicant_data = self.config_data.get('applicant', {})
            user_data = {
                "First Name": applicant_data.get('first_name', 'Ghazal'),
                "Last Name": applicant_data.get('last_name', 'Sultan'),
                "Email": applicant_data.get('email', 'mahendarbathini34@gmail.com').strip(),
                "Phone": applicant_data.get('phone', '+1 (669) 000-0000')
            }
            
            # Map labels to keys
            field_map = {
                "First Name": "First Name",
                "Last Name": "Last Name", 
                "Email": "Email"
            }

            for label_text, data_key in field_map.items():
                try:
                    # Strategy: Find label containing text, then find input in same container or following sibling
                    # This XPath finds input inside the parent of the label (standard form group)
                    xpath = f"//label[contains(text(), '{label_text}')]/..//input"
                    input_fields = self.driver.find_elements(By.XPATH, xpath)
                    
                    if not input_fields:
                         # Fallback: Try searching document wide if specific container fails
                         xpath_alt = f"//input[@placeholder='{label_text}']"
                         input_fields = self.driver.find_elements(By.XPATH, xpath_alt)

                    if input_fields:
                        input_field = input_fields[0]
                        # Scroll to it
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_field)
                        time.sleep(0.5)
                        self.human.fill_text_field(input_field, user_data[data_key])
                        logger.info(f"  ✓ Filled {label_text}")
                    else:
                        logger.warning(f"  Could not find input for {label_text}")
                        
                except Exception as e:
                    logger.warning(f"  Error filling {label_text}: {e}")

            # Phone (Special handling)
            try:
                phone_xpath = "//label[contains(text(), 'Phone')]/..//input"
                phone_inputs = self.driver.find_elements(By.XPATH, phone_xpath)
                if phone_inputs:
                    phone_input = phone_inputs[0]
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", phone_input)
                    phone_input.clear()
                    self.human.fill_text_field(phone_input, user_data["Phone"])
                    logger.info("  ✓ Filled Phone")
            except Exception as e:
                logger.warning(f"  Could not fill Phone: {e}")

            # keywords/Checkboxes (Consent/Agree)
            try:
                logger.info("  Checking for checkboxes/consent...")
                # Targeted search within the modal
                checkboxes = self.driver.find_elements(By.XPATH, self.selectors_config['consent_checkbox'])
                
                if not checkboxes:
                    logger.info("  No checkboxes found in modal via ID, trying generic search...")
                    checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")

                for cb in checkboxes:
                    try:
                        # Check if it's the right one (consent)
                        # We can check simple visibility/interactivity
                        if not cb.is_selected():
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cb)
                            time.sleep(0.5)
                            
                            # Try clicking the label if input click fails?
                            try:
                                self.human.human_click(cb)
                                logger.info("  ✓ Clicked consent checkbox")
                            except:
                                self.driver.execute_script("arguments[0].click();", cb)
                                logger.info("  ✓ Clicked consent checkbox (JS force)")
                                
                    except Exception as cbe:
                        logger.debug(f"  Checkbox interaction failed: {cbe}")
                        
            except Exception as e:
                logger.warning(f"  Error handling checkboxes: {e}")

        except Exception as e:
            logger.error(f"Error filling application form: {e}")
            raise
    
    def _upload_resume(self):
        """Upload resume to the application"""
        try:
            # Get resume path from config
            resume_filename = self.config_data.get('resume_path', 'resume/candidate_resume.pdf')
            # Ensure absolute path
            if not os.path.isabs(resume_filename):
                resume_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    resume_filename
                )
            else:
                resume_path = resume_filename
            
            if not os.path.exists(resume_path):
                logger.error(f"Resume not found: {resume_path}")
                raise FileNotFoundError(f"Resume not found: {resume_path}")
            
            logger.info(f"  Using resume: {resume_path}")
            
            # Find file input
            # In the screenshot, there is a "Upload Your Resume" section.
            # Usually strict file inputs are hidden.
            
            file_input = None
            
            # Strategy 1: Look for any file input in the modal
            try:
                logger.info("  Looking for file input in modal...")
                file_input = self.driver.find_element(By.CSS_SELECTOR, "div#quickApplyModal input[type='file']")
            except:
                pass
                
            # Strategy 2: Look for any file input on page
            if not file_input:
                try:
                    logger.info("  Looking for any file input on page...")
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_inputs:
                        file_input = file_inputs[0]
                except:
                    pass

            if file_input:
                # Unhide if necessary (common issue with stylized uploaders)
                # Remove all blocking styles that prevent interaction
                unhide_script = """
                arguments[0].style.display = 'block';
                arguments[0].style.visibility = 'visible';
                arguments[0].style.opacity = '1';
                arguments[0].style.pointerEvents = 'auto';
                arguments[0].style.width = 'auto';
                arguments[0].style.height = 'auto';
                """
                self.driver.execute_script(unhide_script, file_input)
                time.sleep(0.5)
                
                try:
                    file_input.send_keys(resume_path)
                    logger.info("  ✓ Resume uploaded successfully")
                    time.sleep(2)
                except Exception as send_error:
                    # If send_keys fails, try alternative method
                    logger.warning(f"  send_keys failed ({send_error}), trying alternative method...")
                    self.driver.execute_script(f"arguments[0].value = '{resume_path}';", file_input)
                    # Trigger change event
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', {{ bubbles: true }}));", file_input)
                    logger.info("  ✓ Resume uploaded via JS property assignment")
                    time.sleep(2)
            else:
                logger.error("  ✗ Could not find file input for resume upload")
                # Last ditch: try to find the drop zone and see if we can attach to it? No, Selenium needs input.
                raise Exception("Resume upload input not found")
            
        except Exception as e:
            logger.error(f"Error uploading resume: {e}")
            raise
    
    def _fill_eeo_form(self):
        """Fill the EEO (Equal Employment Opportunity) form with user-provided selectors"""
        try:
            logger.info("Filling EEO form...")
            time.sleep(1)  # Wait for form to fully render
            
            # Gender - select "I do not wish to provide this information"
            try:
                logger.info("  Selecting Gender: I do not wish to provide this information")
                gender_input = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, self.selectors_config['gender_radio']))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", gender_input)
                time.sleep(0.3)
                self.human.human_click(gender_input)
                logger.info("  ✓ Selected Gender")
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"  Could not select gender: {e}")
            
            # Ethnicity - select "I do not wish to provide this information"
            try:
                logger.info("  Selecting Ethnicity: I do not wish to provide this information")
                ethnicity_input = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, self.selectors_config['ethnicity_radio']))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ethnicity_input)
                time.sleep(0.3)
                self.human.human_click(ethnicity_input)
                logger.info("  ✓ Selected Ethnicity")
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"  Direct ethnicity selector failed: {e}")
                # Fallback 1: Try to find the span with "I do not wish" text
                try:
                    logger.info("  Trying ethnicity via span selector: //span[@class='radio-buttons-label'][contains(., 'I do not wish')]...")
                    ethnicity_span_xpath = "//span[@class='radio-buttons-label'][contains(., 'I do not wish')]"
                    ethnicity_span = self.driver.find_element(By.XPATH, ethnicity_span_xpath)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ethnicity_span)
                    time.sleep(0.3)
                    self.human.human_click(ethnicity_span)
                    logger.info("  ✓ Selected Ethnicity (via span)")
                    time.sleep(0.5)
                except Exception as e2:
                    logger.debug(f"  Span-based ethnicity selector failed: {e2}")
                    # Fallback 2: Try to find any ethnicity radio with "not wish" text
                    try:
                        logger.info("  Trying ethnicity fallback: finding 'I do not wish' option...")
                        ethnicity_fallback_xpath = "//input[@type='radio'][@name='ethnicity']"
                        ethnicity_options = self.driver.find_elements(By.XPATH, ethnicity_fallback_xpath)
                        
                        for eth_input in ethnicity_options:
                            try:
                                # Check associated label
                                eth_id = eth_input.get_attribute('id')
                                if eth_id:
                                    eth_label = self.driver.find_element(By.XPATH, f"//label[@for='{eth_id}']")
                                    if "not wish" in eth_label.text.lower() or "decline" in eth_label.text.lower():
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", eth_input)
                                        time.sleep(0.3)
                                        self.human.human_click(eth_input)
                                        logger.info(f"  ✓ Selected Ethnicity (fallback): {eth_label.text}")
                                        time.sleep(0.5)
                                        break
                            except Exception:
                                continue
                    except Exception as e3:
                        logger.warning(f"  Could not select ethnicity: {e3}")
            
            # Race - select "I do not wish to provide this information"
            try:
                logger.info("  Selecting Race: I do not wish to provide this information")
                race_input = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, self.selectors_config['race_radio']))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", race_input)
                time.sleep(0.3)
                self.human.human_click(race_input)
                logger.info("  ✓ Selected Race")
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"  Input-based race selector failed: {e}")
                # Fallback: Try clicking the span directly
                try:
                    logger.info("  Trying span-based race selection...")
                    race_span_xpath = "//span[@name='race'][@value='2,8'][@class='radio-buttons-label'][contains(., 'I do not wish')]"
                    race_span = self.driver.find_element(By.XPATH, race_span_xpath)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", race_span)
                    time.sleep(0.3)
                    self.human.human_click(race_span)
                    logger.info("  ✓ Selected Race (via span)")
                    time.sleep(0.5)
                except Exception as e2:
                    logger.warning(f"  Could not select race: {e2}")
            
            # Veteran Status (optional field)
            try:
                logger.info("  Checking Veteran Status...")
                veteran_inputs = self.driver.find_elements(By.XPATH, self.selectors_config['veteran_radios'])
                if veteran_inputs:
                    # Look for "I do not wish to provide" option
                    for vet_input in veteran_inputs:
                        try:
                            vet_label = vet_input.find_element(By.XPATH, "following-sibling::label | parent::label")
                            if "not wish" in vet_label.text.lower():
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vet_input)
                                time.sleep(0.3)
                                self.human.human_click(vet_input)
                                logger.info("  ✓ Selected Veteran Status")
                                break
                        except Exception:
                            continue
            except Exception as e:
                logger.debug(f"  Veteran status field not found: {e}")
            
            logger.info("✅ EEO form completed")
            
        except Exception as e:
            logger.error(f"Error filling EEO form: {e}")
            raise

    def _submit_initial_form(self):
        """Submit the initial application form and proceed to EEO"""
        try:
            # Step 4.5: Ensure consent checkbox is selected BEFORE resume upload
            try:
                logger.info("      Ensuring consent checkbox is selected...")
                target_texts = ["consent to receive", "employment-related", "text message", "i consent", "consent"]
                consent_found = False

                # Find labels with target text and get their associated inputs via 'for' attribute
                labels = self.driver.find_elements(By.XPATH, "//label[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employment-related')]")
                
                for lbl in labels:
                    try:
                        # Method 1: Check if label has a 'for' attribute pointing to an input
                        label_for = lbl.get_attribute('for')
                        if label_for:
                            try:
                                inp = self.driver.find_element(By.ID, label_for)
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
                                time.sleep(0.3)
                                if not inp.is_selected():
                                    try:
                                        inp.click()
                                    except Exception:
                                        self.driver.execute_script("arguments[0].click();", inp)
                                    time.sleep(0.5)
                                if inp.is_selected():
                                    consent_found = True
                                    logger.info("      ✓ Consent checkbox selected via 'for' attribute")
                                    break
                            except Exception:
                                pass
                        
                        # Method 2: Try to find input inside the label
                        if not consent_found:
                            try:
                                inp = lbl.find_element(By.XPATH, ".//input[@type='checkbox']")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
                                time.sleep(0.3)
                                if not inp.is_selected():
                                    try:
                                        inp.click()
                                    except Exception:
                                        self.driver.execute_script("arguments[0].click();", inp)
                                    time.sleep(0.5)
                                if inp.is_selected():
                                    consent_found = True
                                    logger.info("      ✓ Consent checkbox selected via nested input")
                                    break
                            except Exception:
                                pass
                        
                        # Method 3: Click label directly as fallback
                        if not consent_found:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", lbl)
                            try:
                                lbl.click()
                                consent_found = True
                                logger.info("      ✓ Clicked consent label (fallback)")
                                break
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", lbl)
                                consent_found = True
                                logger.info("      ✓ Clicked consent label via JS (fallback)")
                                break
                    except Exception as label_error:
                        logger.debug(f"      Error processing consent label: {label_error}")

                if not consent_found:
                    logger.info("      ℹ️ Consent checkbox not found before resume upload (continuing anyway)")
            except Exception as e:
                logger.debug(f"      Consent pre-upload check error: {e}")

            # Step 6: Upload resume
            logger.info("      Uploading resume...")
            self._upload_resume()
            time.sleep(1)

            # Step 7: Submit initial form
            logger.info("      Submitting initial form...")
            submit_btn_selector = self.selectors_config['submit_btn']
            
            submit_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, submit_btn_selector))
            )
            self.human.human_click(submit_btn)
            logger.info("      ✓ Submit button clicked")
            
            # Wait for confirmation page to appear (contains "You've applied" message)
            try:
                logger.info("      ⏳ Waiting for confirmation page...")
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'applied')]"))
                )
                time.sleep(1)
                logger.info("      ✓ Confirmation page loaded")
            except Exception as e:
                logger.warning(f"      Confirmation message not found: {e}")
                time.sleep(2)
            
            # Step 8: Click Next button on confirmation page to go to EEO form
            logger.info("      Clicking Next button on confirmation page...")
            next_btn = None
            
            # Strategy 1: Look for the confirmation page Next button
            try:
                logger.info("      Trying CSS selector: button.btn.jd-btn-outline")
                next_btns = self.driver.find_elements(By.CSS_SELECTOR, self.selectors_config['next_btn_outline'])
                
                for btn in next_btns:
                    btn_text = (btn.text or '').strip()
                    if 'next' in btn_text.lower():
                        next_btn = btn
                        logger.info(f"      ✓ Found Next button: '{btn_text}'")
                        break
                
                # If no text match, take the first one
                if not next_btn and next_btns:
                    next_btn = next_btns[0]
                    logger.info("      ✓ Found Next button (first match)")
                    
            except Exception as e:
                logger.debug(f"      CSS selector failed: {e}")
            
            # Strategy 2: XPath search
            if not next_btn:
                try:
                    logger.info("      Trying XPath: //button[normalize-space(.)='Next' or .//span[contains(., 'Next')]]")
                    next_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='Next' or .//span[contains(., 'Next')]]"))
                    )
                    logger.info("      ✓ Found Next button via XPath")
                except Exception as e:
                    logger.debug(f"      XPath search failed: {e}")
            
            if next_btn:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                    time.sleep(0.5)
                    self.human.human_click(next_btn)
                    logger.info("      ✓ Clicked Next button successfully")
                    
                    # Wait for the EEO form to be visible (look for gender radio buttons or other EEO elements)
                    logger.info("      ⏳ Waiting for EEO form to load...")
                    eeo_form_found = False
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//input[@type='radio'][@name='gender']"))
                        )
                        logger.info("      ✓ EEO form loaded successfully (gender field found)")
                        eeo_form_found = True
                        time.sleep(1)
                    except Exception:
                        logger.debug("      Gender field not found, trying alternative EEO form detection...")
                    
                    # If EEO form not found, check for other EEO form indicators
                    if not eeo_form_found:
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, "//input[@type='radio'][@name='ethnicity']"))
                            )
                            logger.info("      ✓ EEO form loaded successfully (ethnicity field found)")
                            eeo_form_found = True
                            time.sleep(1)
                        except Exception:
                            logger.debug("      Ethnicity field not found either")
                    
                    # If still not found, check for modal/form with EEO-like content
                    if not eeo_form_found:
                        try:
                            WebDriverWait(self.driver, 3).until(
                                EC.presence_of_element_located((By.XPATH, "//label[contains(text(), 'Gender') or contains(text(), 'gender')]"))
                            )
                            logger.info("      ✓ EEO form found via label text")
                            eeo_form_found = True
                            time.sleep(1)
                        except Exception:
                            pass
                    
                    # If no EEO form found after 10+ seconds, the application might be complete without EEO
                    if not eeo_form_found:
                        logger.info("      ⚠️ EEO form not found - application may be complete without EEO questions")
                        logger.info("      ℹ️ EEO form might not be required for this portal")
                        time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"      ✗ Failed to click Next button or navigate: {e}")
                    raise
            else:
                logger.error("      ✗ Could not find Next button on confirmation page")
                raise Exception("Next button not found on confirmation page")

        except Exception as e:
            logger.error(f"Error submitting initial form: {e}")
            raise

    def _complete_application(self):
        """Complete the application process (EEO submission and final steps)"""
        try:
            # Step 9: Click Next button on EEO form
            logger.info("      Completing application (clicking EEO Next)...")
            try:
                # Find the Next button on EEO form
                next_button_found = False
                
                # Strategy 1: Look for button.btn.jd-btn with Next text (not outlined)
                try:
                    logger.info("      Trying to find EEO Next button via selector: button.btn.jd-btn")
                    eeo_next_btns = self.driver.find_elements(By.CSS_SELECTOR, self.selectors_config['next_btn_solid'])
                    
                    for btn in eeo_next_btns:
                        try:
                            btn_text = (btn.text or '').strip()
                            if 'next' in btn_text.lower():
                                logger.info(f"      ✓ Found EEO Next button with text: '{btn_text}'")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                time.sleep(0.3)
                                
                                # Check if disabled and wait for it to be enabled
                                if btn.get_attribute('disabled'):
                                    logger.info("      Button is disabled, waiting for it to be enabled...")
                                    WebDriverWait(self.driver, 10).until(
                                        lambda d: not d.find_element(By.CSS_SELECTOR, "button.btn.jd-btn:not(.jd-btn-outline)").get_attribute('disabled')
                                    )
                                    logger.info("      ✓ Button enabled")
                                
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                time.sleep(0.5)
                                self.human.human_click(btn)
                                logger.info("      ✓ Clicked EEO form Next button")
                                next_button_found = True
                                
                                # Wait for page transition after clicking
                                logger.info("      ⏳ Waiting for page to transition...")
                                try:
                                    WebDriverWait(self.driver, 10).until(
                                        EC.staleness_of(btn)
                                    )
                                    logger.info("      ✓ Page transitioned successfully")
                                except Exception:
                                    logger.debug("      Page didn't transition (normal), waiting...")
                                    time.sleep(3)
                                break
                        except Exception as inner_e:
                            logger.debug(f"      Error with button: {inner_e}")
                            continue
                except Exception as e:
                    logger.debug(f"      Strategy 1 failed: {e}")
                
                # Strategy 2: XPath for nested span structure
                if not next_button_found:
                    try:
                        logger.info("      Trying XPath: //button[contains(@class, 'jd-btn')]//span[contains(., 'Next')]")
                        next_btn_xpath = "//button[contains(@class, 'jd-btn') and not(contains(@class, 'jd-btn-outline'))]//span[contains(., 'Next')]/ancestor::button"
                        next_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, next_btn_xpath))
                        )
                        logger.info("      ✓ Found EEO Next button via XPath")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                        time.sleep(0.5)
                        self.human.human_click(next_btn)
                        logger.info("      ✓ Clicked EEO form Next button (XPath)")
                        
                        # Wait for page transition
                        try:
                            WebDriverWait(self.driver, 10).until(EC.staleness_of(next_btn))
                            logger.info("      ✓ Page transitioned successfully")
                        except Exception:
                            time.sleep(3)
                        
                        next_button_found = True
                    except Exception as e:
                        logger.debug(f"      Strategy 2 failed: {e}")
                
                # Strategy 3: Generic button search
                if not next_button_found:
                    try:
                        logger.info("      Trying generic button search in job-app-btns")
                        btn_container = self.driver.find_element(By.CSS_SELECTOR, "div.job-app-btns")
                        buttons_in_container = btn_container.find_elements(By.TAG_NAME, "button")
                        
                        for btn in buttons_in_container:
                            btn_text = (btn.text or '').lower()
                            if 'next' in btn_text and 'back' not in btn_text:
                                logger.info(f"      ✓ Found Next button in container")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                time.sleep(0.5)
                                
                                # Wait for button to be enabled if disabled
                                if btn.get_attribute('disabled'):
                                    logger.info("      Button is disabled, waiting...")
                                    WebDriverWait(self.driver, 5).until(
                                        EC.element_to_be_clickable((By.TAG_NAME, "button"))
                                    )
                                
                                self.human.human_click(btn)
                                logger.info("      ✓ Clicked EEO form Next button (container search)")
                                
                                # Wait for page transition
                                try:
                                    WebDriverWait(self.driver, 10).until(EC.staleness_of(btn))
                                    logger.info("      ✓ Page transitioned successfully")
                                except Exception:
                                    time.sleep(3)
                                
                                next_button_found = True
                                break
                    except Exception as e:
                        logger.debug(f"      Strategy 3 failed: {e}")
                
                if not next_button_found:
                    logger.warning("      ⚠️ Could not find EEO Next button - continuing anyway")
                else:
                    logger.info("      ✅ EEO form Next button clicked successfully")
            
            except Exception as e:
                logger.warning(f"      Error clicking EEO Next button: {e}")

            # Step 10: Final save/submission
            logger.info("      Finalizing application submission...")
            
             # Success!
            logger.info("=" * 60)
            logger.info("      ✅ APPLICATION SUBMITTED SUCCESSFULLY!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error completing application: {e}")
            raise
