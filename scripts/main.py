import argparse
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from config.secrets_validator import validate_secrets
from engine.runner import EngineRunner
from core.logger import logger

def main():
    """Main entry point for the job application engine"""
    parser = argparse.ArgumentParser(description="Job Application Engine CLI")
    parser.add_argument("--dry-run", action="store_true", help="Run without submitting applications")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--site", type=str, help="Run only a specific site (e.g., 'LanceSoft')")
    
    args = parser.parse_args()
    
    # Override settings based on CLI arguments
    if args.dry_run:
        settings.DRY_RUN = True
        logger.info("🔍 Mode: DRY RUN (No applications will be submitted)")
        
    if args.headless:
        settings.HEADLESS = True
        logger.info("👻 Mode: HEADLESS Browser")

    try:
        # Validate configuration (optional - comment out if not needed)
        # validate_secrets()
        
        # Run the engine
        runner = EngineRunner()
        runner.run(site_filter=args.site)
        
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
