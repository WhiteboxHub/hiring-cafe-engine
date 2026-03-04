#!/usr/bin/env python3
"""
Step 1: Extract Hiring Cafe job URLs only (no ATS enrichment).

Uses filters from config/hiring_cafe.json (keywords, date). Saves jobs to JSON
with job_id, title, hiring_cafe_url. Run step 2 to add ATS URLs, then step 3 to build by_ats.

Usage:
  python scripts/hiring_cafe_step1_extract_urls.py [--output FILE] [--date-filter PRESET] [--job-limit N]
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.browser import browser_service
from core.logger import logger
from strategies.custom.hiring_cafe import HiringCafeStrategy
from config.settings import settings


def main():
    parser = argparse.ArgumentParser(
        description="Step 1: Extract Hiring Cafe job URLs (no ATS extraction)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Date filter presets: today, 24h, 3d, 1w, 2w, all (default: from config/hiring_cafe.json)

Examples:
  python scripts/hiring_cafe_step1_extract_urls.py
  python scripts/hiring_cafe_step1_extract_urls.py --output my_jobs.json --date-filter today
  python scripts/hiring_cafe_step1_extract_urls.py --date-filter 24h --job-limit 50
        """,
    )
    parser.add_argument(
        "--output",
        type=str,
        default="hiring_cafe_jobs.json",
        help="Output JSON file (default: hiring_cafe_jobs.json)",
    )
    parser.add_argument(
        "--date-filter",
        type=str,
        default=None,
        choices=["today", "24h", "3d", "1w", "2w", "all"],
        help="Override date filter: today/24h, 3d, 1w, 2w, all (default: from config)",
    )
    parser.add_argument(
        "--job-limit",
        type=int,
        metavar="N",
        default=None,
        help="Max number of jobs to collect (default: all)",
    )
    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=100,
        help="Max scroll attempts per keyword (default: 100)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    args = parser.parse_args()

    if args.headless:
        settings.HEADLESS = True
        logger.info("👻 Running in HEADLESS mode")

    driver = None
    try:
        logger.info("🚀 Step 1: Extracting Hiring Cafe URLs (no ATS)...")
        driver = browser_service.start_browser()
        strategy = HiringCafeStrategy(driver, date_filter_override=args.date_filter)
        jobs = strategy.find_jobs()
        if args.job_limit and jobs:
            jobs = jobs[: args.job_limit]
            logger.info("📋 Limited to first %d jobs", len(jobs))

        if not jobs:
            logger.warning("⚠️ No jobs found")
            payload = {"source": "hiring.cafe", "step": 1, "updated": datetime.now().isoformat(), "count": 0, "jobs": []}
        else:
            payload = {
                "source": "hiring.cafe",
                "step": 1,
                "updated": datetime.now().isoformat(),
                "count": len(jobs),
                "jobs": [
                    {
                        "job_id": j.get("job_id"),
                        "title": j.get("title"),
                        "hiring_cafe_url": j.get("url") or f"https://hiring.cafe/viewjob/{j.get('job_id')}",
                        "ats_url": None,
                        "ats_platform": None,
                        "source_keywords": j.get("source_keywords"),
                        "scraped_at": j.get("scraped_at"),
                        # Enriched fields
                        "job_tittle": j.get("job_tittle"),
                        "location": j.get("location"),
                        "comapany": j.get("comapany"),
                        "type": j.get("type"),
                        "city": j.get("city"),
                        "state": j.get("state"),
                        "country": j.get("country"),
                        "company_description": j.get("company_description")
                    }
                    for j in jobs
                ],
            }

        out_dir = os.path.dirname(os.path.abspath(args.output))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 60)
        print(f"✅ Step 1 complete: {len(jobs)} jobs saved to {args.output}")
        print("   Run step 2 to extract ATS URLs, then step 3 to build by_ats file.")
        print("=" * 60)
        return 0

    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if driver:
            logger.info("🧹 Closing browser...")
            browser_service.stop_browser()


if __name__ == "__main__":
    sys.exit(main())
