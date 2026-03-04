from abc import ABC, abstractmethod
from core.safe_actions import SafeActions
from core.logger import logger
from models.config_models import JobListing

class BaseStrategy(ABC):
    def __init__(self, driver, job_site, selectors):
        self.driver = driver
        self.job_site = job_site
        self.selectors = selectors # JSON config from DB
        self.actions = SafeActions(driver)
        
    @abstractmethod
    def login(self):
        """
        Handles authentication if required.
        """
        pass

    @abstractmethod
    def find_jobs(self):
        """
        Navigates to the search URL and scrapes job listings.
        Returns a list of dictionaries with job details (external_id, title, url).
        """
        pass

    @abstractmethod
    def apply(self, listing: JobListing):
        """
        Navigates to listing.job_url and attempts to apply.
        Returns True if successful, False otherwise.
        """
        pass

    def validate_content(self, required_selectors):
        """
        Checks if critical elements exist on the page.
        """
        for selector in required_selectors:
            if not self.actions.check_exists(selector):
                logger.error(f"Validation failed: Essential element '{selector}' missing.")
                return False
        return True
