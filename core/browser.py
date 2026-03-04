import os
import time
try:
    import fcntl
    _HAS_FCNTL = True
except Exception:
    _HAS_FCNTL = False
uc = None
from config.settings import settings
from core.logger import logger
from core.proxy_manager import proxy_manager

class BrowserService:
    def __init__(self):
        self.driver = None
        self.lock_file = None
        
    def _acquire_lock(self):
        """Ensures only one instance touches the profile. On Windows (no fcntl) locking is skipped."""
        profile_path = settings.chrome_profile_path
        os.makedirs(profile_path, exist_ok=True)
        lock_path = os.path.join(profile_path, "profile.lock")

        self.lock_file = None
        if not _HAS_FCNTL:
            logger.info("fcntl not available on this platform; skipping profile locking.")
            return

        self.lock_file = open(lock_path, 'w')
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Acquired lock on profile: {profile_path}")
        except IOError:
            logger.critical(f"Could not acquire lock on {lock_path}. Is another instance running?")
            raise RuntimeError("Browser profile is locked by another process.")

    def _release_lock(self):
        if not _HAS_FCNTL:
            return
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
            self.lock_file.close()
            logger.info("Released profile lock.")

    def start_browser(self):
        self._acquire_lock()
        # Try to import undetected_chromedriver here; if unavailable, we'll fall back to selenium webdriver
        try:
            import undetected_chromedriver as uc_local
            global uc
            uc = uc_local
        except ModuleNotFoundError as e:
            # If undetected_chromedriver can't be imported (e.g., distutils missing), log and continue to fallback
            logger.warning(f"undetected_chromedriver import failed: {e}. Falling back to selenium webdriver.")
            uc = None

        if uc:
            options = uc.ChromeOptions()
        else:
            from selenium.webdriver import ChromeOptions
            options = ChromeOptions()
        options.add_argument(f"--user-data-dir={settings.chrome_profile_path}")
        
        proxy_arg = proxy_manager.get_proxy_option()
        if proxy_arg:
            options.add_argument(proxy_arg)
            
        if settings.HEADLESS:
            options.add_argument("--headless=new")
            
        # Defense evasion
        options.add_argument("--no-first-run")
        options.add_argument("--no-service-autorun")
        options.add_argument("--password-store=basic")
        
        # If undetected_chromedriver is available, prefer it
        if uc:
            try:
                # Force ChromeDriver to match your Chrome version (144)
                self.driver = uc.Chrome(
                    options=options, 
                    use_subprocess=True,
                    version_main=144  # Match your Chrome version
                )
                logger.info("Browser started successfully (undetected-chromedriver).")
            except Exception as e:
                logger.warning(f"uc.Chrome failed to start: {e}. Attempting fallback using webdriver-manager.")

        # Fallback: use webdriver-manager to install a matching chromedriver and start selenium Chrome
        if not self.driver:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service as ChromeService
                from webdriver_manager.chrome import ChromeDriverManager

                service = ChromeService(ChromeDriverManager().install())
                # options is already selenium ChromeOptions when uc was None
                self.driver = webdriver.Chrome(service=service, options=options)
                logger.info("Browser started successfully (webdriver-manager fallback).")
            except Exception as e2:
                logger.error(f"Failed to start browser with fallback: {e2}")
                self._release_lock()
                raise

        if self.driver and not settings.HEADLESS:
            try:
                self.driver.maximize_window()
            except Exception as e:
                logger.warning(f"Could not maximize window: {e}")

        return self.driver

    def stop_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
        
        self._release_lock()

browser_service = BrowserService()
