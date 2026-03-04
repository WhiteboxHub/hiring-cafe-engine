"""
Guards - Safety Mechanisms for Automation
Handles rate limiting, DRY_RUN mode, and application counters
"""

from config.settings import settings
from core.logger import logger

class Guards:
    """Safety mechanisms to prevent over-application and respect limits"""
    
    def __init__(self):
        self.application_count = 0
        self.max_applications = settings.MAX_APPLICATIONS_PER_RUN
        self.dry_run = settings.DRY_RUN
        
    def can_apply(self) -> bool:
        """Check if we can apply to another job"""
        # Treat 999999 or higher as unlimited
        if self.max_applications >= 999999:
            return True
        
        if self.application_count >= self.max_applications:
            logger.warning(f"Reached maximum applications limit: {self.max_applications}")
            return False
        return True
    
    def increment_counter(self):
        """Increment application counter"""
        self.application_count += 1
        max_display = "Unlimited" if self.max_applications >= 999999 else str(self.max_applications)
        logger.info(f"Applications submitted: {self.application_count}/{max_display}")
    
    def is_dry_run(self) -> bool:
        """Check if running in dry-run mode"""
        return self.dry_run
    
    def get_stats(self) -> dict:
        """Get current guard statistics"""
        return {
            'applications_submitted': self.application_count,
            'max_applications': self.max_applications,
            'remaining': self.max_applications - self.application_count,
            'dry_run_mode': self.dry_run
        }

# Singleton instance
guards = Guards()
