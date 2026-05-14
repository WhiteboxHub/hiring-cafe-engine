import json
import os
import re
from core.logger import logger

class LocatorLoader:
    """Loads and provides access to Hiring Cafe locators and patterns."""
    
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "hiring_cafe_locators.json"
            )
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.error(f"Locator config not found at {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading locator config: {e}")
            return {}

    def get(self, category, key, default=None):
        return self.data.get(category, {}).get(key, default)

    @property
    def ats_url_regex(self):
        pattern = self.get("patterns", "ats_url_regex")
        if pattern:
            return re.compile(pattern, re.IGNORECASE)
        return None

    @property
    def ats_platform_patterns(self):
        patterns = self.get("patterns", "ats_platforms", [])
        return [(p[0], p[1]) for p in patterns]

    @property
    def date_fetched_presets(self):
        return self.get("presets", "date_fetched_past_n_days", {})
