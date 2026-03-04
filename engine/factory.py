"""
Factory Pattern - Dynamic Strategy Loader
Dynamically imports and instantiates strategy classes based on database configuration
"""

import importlib
from core.logger import logger

class StrategyFactory:
    """Factory for dynamically loading strategy classes"""
    
    @staticmethod
    def get_strategy(class_path: str, driver, job_site, selectors, db_session=None):
        """
        Dynamically imports and instantiates a strategy class.
        
        Args:
            class_path: Python module path (e.g., 'strategies.custom.InsightGlobalStrategy')
            driver: Selenium WebDriver instance
            job_site: JobSite model instance from database
            selectors: Dictionary of selectors from database
            db_session: Database session for persistence (optional)
            
        Returns:
            Instantiated strategy object
            
        Raises:
            ValueError: If strategy class cannot be loaded
        """
        try:
            # Split module path and class name
            # Example: 'strategies.custom.InsightGlobalStrategy' -> module='strategies.custom', class='InsightGlobalStrategy'
            module_name, class_name = class_path.rsplit('.', 1)
            
            # Dynamically import the module
            module = importlib.import_module(module_name)
            
            # Get the class from the module
            strategy_class = getattr(module, class_name)
            
            # Instantiate and return
            logger.info(f"Loaded strategy: {class_name} from {module_name}")
            return strategy_class(driver, job_site, selectors, db_session)
            
        except (ImportError, AttributeError) as e:
            logger.critical(f"Failed to load strategy '{class_path}': {e}")
            raise ValueError(f"Could not load strategy {class_path}") from e

# Singleton instance
strategy_factory = StrategyFactory()
