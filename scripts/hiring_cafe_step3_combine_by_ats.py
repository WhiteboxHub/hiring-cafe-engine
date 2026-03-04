#!/usr/bin/env python3
"""
Step 3: Combine enriched jobs (from Step 2) into a single JSON grouped by ATS platform.

Reads JSON with jobs (job_id, title, hiring_cafe_url, ats_url, ats_platform) and writes
by_ats file with platforms as keys and flat entries: job_id, title, hiring_cafe_url, ats_url.
No browser required; run after step 2.

Usage:
  python scripts/hiring_cafe_step3_combine_by_ats.py [--input FILE] [--output FILE]
"""

import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.custom.hiring_cafe import categorize_jobs_by_ats


def main():
    parser = argparse.ArgumentParser(
        description="Step 3: Combine jobs into by_ats file (no browser)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/hiring_cafe_step3_combine_by_ats.py --input hiring_cafe_jobs.json
  python scripts/hiring_cafe_step3_combine_by_ats.py --input enriched.json --output hiring_cafe_by_ats.json
        """,
    )
    parser.add_argument(
        "--input",
        type=str,
        default="hiring_cafe_jobs.json",
        help="Input JSON from Step 2 (with ats_url, ats_platform) (default: hiring_cafe_jobs.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="hiring_cafe_by_ats.json",
        help="Output by_ats JSON (default: hiring_cafe_by_ats.json)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs") if isinstance(data, dict) else data
    if not jobs:
        print("No jobs in input.", file=sys.stderr)
        by_ats = {}
    else:
        # Normalize for categorize: ats_url/ats_platform or ats.url/ats.platform
        for j in jobs:
            if "ats_url" not in j and isinstance(j.get("ats"), dict):
                j["ats_url"] = j["ats"].get("url")
                j["ats_platform"] = j["ats"].get("platform")
            if "hiring_cafe_url" not in j:
                j["hiring_cafe_url"] = j.get("url") or j.get("job_posting_url") or (
                    f"https://hiring.cafe/viewjob/{j.get('job_id')}" if j.get("job_id") else None
                )
        by_ats = categorize_jobs_by_ats(jobs)

    # Output format: by_ats with flat entries (job_id, title, hiring_cafe_url, ats_url)
    by_ats_flat = {}
    for platform, entries in by_ats.items():
        by_ats_flat[platform] = [
            {
                "job_id": e.get("job_id"),
                "title": e.get("title"),
                "hiring_cafe_url": e.get("job_posting_url") or e.get("hiring_cafe_url"),
                "ats_url": e.get("ats", {}).get("url") if isinstance(e.get("ats"), dict) else e.get("ats_url"),
                # Preserve enriched fields
                "job_tittle": e.get("job_tittle"),
                "comapany": e.get("comapany"),
                "location": e.get("location"),
                "city": e.get("city"),
                "state": e.get("state"),
                "country": e.get("country"),
                "type": e.get("type"),
                "company_description": e.get("company_description")
            }
            for e in entries
        ]

    payload = {
        "source": "hiring.cafe",
        "categorized_by": "ats_platform",
        "platforms": sorted(by_ats_flat.keys()),
        "by_ats": by_ats_flat,
    }

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"✅ Step 3 complete: by_ats written to {args.output}")
    print(f"   Platforms: {', '.join(sorted(by_ats_flat.keys()))}")
    for platform in sorted(by_ats_flat.keys()):
        print(f"   {platform}: {len(by_ats_flat[platform])} jobs")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
