#!/usr/bin/env python3
"""
Build job posting URLs by ATS from hiring_cafe_output.json.

Usage:
  python scripts/categorize_hiring_cafe_by_ats.py [input.json] [output.json]

Defaults: input = hiring_cafe_output.json, output = job_posting_urls_by_ats.json
"""

import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.custom.hiring_cafe import categorize_jobs_by_ats


def main():
    parser = argparse.ArgumentParser(description="Categorize Hiring Cafe jobs by ATS platform")
    parser.add_argument("input", nargs="?", default="hiring_cafe_output.json", help="Input JSON (default: hiring_cafe_output.json)")
    parser.add_argument("output", nargs="?", default="job_posting_urls_by_ats.json", help="Output JSON (default: job_posting_urls_by_ats.json)")
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 1

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs") if isinstance(data, dict) else data
    if not jobs:
        print("No jobs in input.", file=sys.stderr)
        by_ats = {}
    else:
        by_ats = categorize_jobs_by_ats(jobs)

    payload = {
        "source": "hiring.cafe",
        "description": "Job posting URLs by ATS",
        "platforms": list(by_ats.keys()),
        "job_posting_urls_by_ats": by_ats,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"Wrote {output_path} with {len(by_ats)} platforms: {sorted(by_ats.keys())}")
    for platform, entries in sorted(by_ats.items()):
        print(f"  {platform}: {len(entries)} jobs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
