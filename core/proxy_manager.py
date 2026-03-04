from config.settings import settings
from core.logger import logger

class ProxyManager:
    def __init__(self):
        self.proxy_url = settings.PROXY_URL
        if self.proxy_url:
            logger.info(f"ProxyManager initialized with proxy.")
        else:
            logger.info("ProxyManager initialized (No proxy configured).")

    def get_proxy_option(self):
        """Returns the Selenium argument for proxy if configured."""
        if self.proxy_url:
            # Note: undetected-chromedriver handles --proxy-server=protocol://host:port
            # Auth is trickier in standard chrome, often requires extension or middleware.
            # providing basic arg here.
            return f"--proxy-server={self.proxy_url}"
        return None

proxy_manager = ProxyManager()
