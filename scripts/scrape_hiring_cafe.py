#!/usr/bin/env python3
"""
Standalone script to scrape Hiring Cafe job listings.

Usage:
    python scripts/scrape_hiring_cafe.py [--output output.json] [--headless]
"""

import argparse
import json
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.browser import browser_service
from core.logger import logger
from strategies.custom.hiring_cafe import HiringCafeStrategy, categorize_jobs_by_ats
from config.settings import settings


def main():
    """Main entry point for Hiring Cafe scraper"""
    parser = argparse.ArgumentParser(
        description="Scrape job listings from Hiring Cafe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/scrape_hiring_cafe.py
  python scripts/scrape_hiring_cafe.py --output jobs.json
  python scripts/scrape_hiring_cafe.py --headless --output jobs.json
        """
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="hiring_cafe_output.json",
        help="Output JSON file (default: hiring_cafe_output.json)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (works for job collection and ATS URL extraction)"
    )
    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=100,
        help="Maximum number of scroll attempts (default: 100)"
    )
    parser.add_argument(
        "--ids-only",
        type=str,
        metavar="FILE",
        help="Also write job IDs only to FILE (one per line)"
    )
    parser.add_argument(
        "--no-enrich-ats",
        action="store_true",
        help="Skip opening job pages and capturing ATS links (default: enrich ATS)"
    )
    parser.add_argument(
        "--enrich-ats-limit",
        type=int,
        metavar="N",
        default=None,
        help="When using --enrich-ats, only enrich first N jobs (default: all)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: run for 10 jobs only (same as --job-limit 10 --enrich-ats-limit 10)"
    )
    parser.add_argument(
        "--job-limit",
        type=int,
        metavar="N",
        default=None,
        help="Max number of jobs to process (default: all)"
    )
    parser.add_argument(
        "--ats-batch-size",
        type=int,
        metavar="N",
        default=100,
        help="Enrich ATS URLs in batches of N, per keyword (default: 100)"
    )
    
    args = parser.parse_args()
    args.enrich_ats = not args.no_enrich_ats

    if args.test:
        args.job_limit = args.job_limit or 10
        args.enrich_ats_limit = args.enrich_ats_limit or 10
        logger.info("Test mode: 10 jobs only")

    # Override headless setting if specified
    if args.headless:
        settings.HEADLESS = True
        logger.info("Running in HEADLESS mode")
    
    driver = None
    try:
        # Start browser
        logger.info("Starting browser...")
        driver = browser_service.start_browser()
        logger.info("Browser started successfully")
        
        # Create strategy instance
        strategy = HiringCafeStrategy(driver)
        
        # Scrape and save (optionally enrich with ATS links)
        jobs = strategy.scrape_and_save(
            output_file=args.output,
            enrich_ats=args.enrich_ats,
            enrich_ats_limit=args.enrich_ats_limit,
            job_limit=args.job_limit,
            ats_batch_size=args.ats_batch_size,
        )
        
        # Job posting URLs by ATS (second file)
        if jobs:
            by_ats = categorize_jobs_by_ats(jobs)
            out_dir = os.path.dirname(args.output)
            by_ats_path = os.path.join(out_dir, "job_posting_urls_by_ats.json") if out_dir else "job_posting_urls_by_ats.json"
            payload = {
                "source": "hiring.cafe",
                "description": "Job posting URLs by ATS",
                "platforms": list(by_ats.keys()),
                "job_posting_urls_by_ats": by_ats,
            }
            with open(by_ats_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info("Saved job posting URLs by ATS: %s", by_ats_path)
            print(f"Job posting URLs by ATS: {by_ats_path}")

        # Print summary
        print("\n" + "=" * 60)
        print(f"Scraping completed!")
        print(f"Total jobs found: {len(jobs)}")
        print(f"Saved to: {args.output}")
        print("=" * 60)
        
        # Optionally save job IDs only
        if args.ids_only and jobs:
            ids = [j.get("job_id") or j.get("external_id") for j in jobs if j.get("job_id") or j.get("external_id")]
            with open(args.ids_only, "w", encoding="utf-8") as f:
                f.write("\n".join(ids))
            print(f" Job IDs written to: {args.ids_only} ({len(ids)} IDs)")
        
        # Print first few jobs as preview
        if jobs:
            print("\n Sample jobs (first 5):")
            for i, job in enumerate(jobs[:5], 1):
                ats = job.get("ats") or {"url": job.get("ats_url"), "platform": job.get("ats_platform")}
                print(f"\n{i}. {job.get('job_id', job.get('external_id', 'N/A'))} - {job.get('title', 'N/A')}")
                print(f"   job_posting_url: {job.get('url', 'N/A')}")
                print(f"   ats: {ats.get('platform', 'N/A')} -> {ats.get('url', '') or 'N/A'}")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n Interrupted by user")
        return 1
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Clean up browser
        if driver:
            logger.info("Closing browser...")
            browser_service.stop_browser()
            logger.info("Browser closed")


if __name__ == "__main__":
    sys.exit(main())

