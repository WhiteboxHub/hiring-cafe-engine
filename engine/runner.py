"""
Engine Runner - Main Orchestration Logic
Coordinates the entire automation workflow
"""

import time
from data.db_connection import db
from models.config_models import JobSite, SiteSelector
from engine.factory import strategy_factory
from engine.guards import guards
from core.browser import browser_service
from core.logger import logger
from core.auth_service import auth_service

class EngineRunner:
    """Main orchestrator for the job application engine"""
    
    def __init__(self):
        self.browser = None
        
    def run(self, site_filter=None):
        """
        Main execution workflow:
        1. Initialize Browser
        2. Fetch Active Sites from Database
        3. For each site:
           a. Load Strategy via Factory
           b. Run find_jobs()
           c. Apply to jobs (respecting guards)
        4. Cleanup and report
        
        Args:
            site_filter (str, optional): Name of company to filter by (case-insensitive)
        """
        logger.info("=" * 60)
        logger.info("🚀 Starting Job Application Engine...")
        logger.info("=" * 60)
        
        try:
            # 1. Start Browser
            logger.info("Initializing browser...")
            self.browser = browser_service.start_browser()
            logger.info("✅ Browser started successfully")

            # 1.5 Optional: Authentication
            token = auth_service.get_access_token()
            if token:
                logger.info(f"🔑 Engine authorized with token: {token[:10]}...")
            
            # 2. Get Active Sites from Database
            session = db.get_session()
            try:
                # Base query
                query = session.query(JobSite).filter(JobSite.is_active == True)
                
                # Apply filter if provided
                if site_filter:
                    logger.info(f"🔎 Filtering for site: {site_filter}")
                    query = query.filter(JobSite.company_name.ilike(f"%{site_filter}%"))
                
                active_sites = query.all()
                
                if not active_sites:
                    if site_filter:
                        logger.warning(f"⚠️ No active job sites found matching '{site_filter}'")
                    else:
                        logger.warning("⚠️ No active job sites found in database.")
                    logger.info("Run: python scripts/init_db.py to seed Insight Global")
                    return
                
                logger.info(f"\n📋 Found {len(active_sites)} active job site(s):")
                for site in active_sites:
                    logger.info(f"   - {site.company_name} ({site.domain})")
                
                # 3. Process Each Site
                for site in active_sites:
                    if not guards.can_apply():
                        logger.warning("⛔ Application limit reached. Stopping.")
                        break
                    
                    self._process_site(session, site)
                
                # 4. Final Report
                stats = guards.get_stats()
                logger.info("\n" + "=" * 60)
                logger.info("✅ ENGINE RUN COMPLETE")
                logger.info("=" * 60)
                logger.info(f"Applications submitted: {stats['applications_submitted']}/{stats['max_applications']}")
                logger.info(f"Dry run mode: {stats['dry_run_mode']}")
                logger.info("=" * 60)
                
            finally:
                db.close_session(session)
                
        except Exception as e:
            logger.critical(f"❌ Engine crashed: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            if self.browser:
                # Respect KEEP_BROWSER_OPEN setting for debugging
                try:
                    from config.settings import settings
                    if getattr(settings, 'KEEP_BROWSER_OPEN', False):
                        logger.info("\nKEEP_BROWSER_OPEN is True - leaving browser open for inspection")
                    else:
                        logger.info("\nStopping browser...")
                        browser_service.stop_browser()
                        logger.info("✅ Browser closed")
                except Exception:
                    logger.info("\nStopping browser (settings check failed)...")
                    browser_service.stop_browser()
                    logger.info("✅ Browser closed")
    
    def _process_site(self, session, site: JobSite):
        """
        Process a single job site
        
        Args:
            session: Database session
            site: JobSite model instance
        """
        logger.info("\n" + "-" * 60)
        logger.info(f"🎯 Processing: {site.company_name}")
        logger.info("-" * 60)
        
        try:
            # Load selectors from database
            selectors = self._load_selectors(session, site)
            
            # Get strategy class path from platform
            strategy_path = site.platform.class_handler
            logger.info(f"Strategy: {strategy_path}")
            
            # Load strategy via factory
            try:
                # Debug: verify session is valid
                logger.info(f"📊 Database session type: {type(session)}")
                logger.info(f"📊 Passing session to strategy: {session is not None}")
                
                strategy = strategy_factory.get_strategy(
                    strategy_path,
                    self.browser,
                    site,
                    selectors,
                    session  # Pass database session
                )
            except Exception as e:
                logger.error(f"❌ Failed to load strategy for {site.company_name}: {e}")
                return
            
            # Login (if required)
            logger.info("Attempting login...")
            if not strategy.login():
                logger.error(f"❌ Login failed for {site.company_name}")
                return
            logger.info("✅ Login successful (or not required)")
            
            # Find jobs (or find and apply for LanceSoft)
            logger.info("🔍 Discovering jobs...")
            
            if site.company_name == "LanceSoft":
                # LanceSoft uses apply-immediately strategy
                logger.info(f"\n📤 Finding and applying to jobs...")
                applied_count = strategy.find_and_apply_jobs()
                logger.info(f"✅ Completed {site.company_name}: {applied_count} applications submitted")
                return  # Early return for LanceSoft
            
            # Traditional approach for other sites
            jobs = strategy.find_jobs()
            logger.info(f"✅ Found {len(jobs)} job(s)")
            
            # Apply to jobs
            if jobs:
                logger.info(f"\n📤 Starting application process...")
                applied_count = 0
                
                for job in jobs:
                    if not guards.can_apply():
                        logger.warning("⛔ Application limit reached")
                        break
                    
                    try:
                        logger.info(f"\nApplying to: {job.get('job_title', 'Unknown Title')}")
                        success = strategy.apply(job)
                        
                        if success:
                            guards.increment_counter()
                            applied_count += 1
                            logger.info(f"✅ Application #{applied_count} successful")
                        else:
                            logger.warning("⚠️ Application failed")
                            
                    except Exception as e:
                        logger.error(f"❌ Error applying to job: {e}")
                        continue
                
                logger.info(f"\n✅ Completed {site.company_name}: {applied_count} applications")
            else:
                logger.info("ℹ️ No jobs found to apply to")
                
        except Exception as e:
            logger.error(f"❌ Error processing {site.company_name}: {e}")
            import traceback
            traceback.print_exc()
    
    def _load_selectors(self, session, site: JobSite) -> dict:
        """
        Load selectors for a job site from database
        
        Args:
            session: Database session
            site: JobSite instance
            
        Returns:
            Dictionary with 'listing' and 'application' selectors
        """
        selectors = {}
        
        # Query selectors for this site
        site_selectors = session.query(SiteSelector).filter(
            SiteSelector.job_site_id == site.id
        ).all()
        
        for selector in site_selectors:
            selectors[selector.type] = selector.config_json
        
        logger.info(f"Loaded {len(selectors)} selector configuration(s)")
        return selectors
