# #!/usr/bin/env python3
# """
# hiring.cafe — Full Pipeline Runner
# ===================================
# Runs all 3 steps in sequence with a single command:

#   Step 1 → Scrape fresh job URLs from hiring.cafe
#   Step 2 → Extract ATS URLs from each job page  (checkpoint/resume safe)
#   Step 3 → Combine jobs into by_ats grouping

# USAGE
# ─────
#   # Run full pipeline (add this to your scheduler)
#   python run_hiring_cafe_pipeline.py

#   # Resume interrupted Step 2 without re-scraping
#   python run_hiring_cafe_pipeline.py --skip-step1

#   # Test mode: only process first N jobs in step 2
#   python run_hiring_cafe_pipeline.py --limit 20

# SCHEDULING EXAMPLES
# ───────────────────
#   Windows Task Scheduler:
#     Program : python
#     Args    : C:\\path\\to\\project\\run_hiring_cafe_pipeline.py
#     Start in: C:\\path\\to\\project

#   Linux/Mac cron (runs every day at 6am):
#     0 6 * * * cd /path/to/project && python run_hiring_cafe_pipeline.py >> logs/pipeline.log 2>&1
# """

# import argparse
# import json
# import os
# import subprocess
# import sys
# import time
# from datetime import datetime
# from pathlib import Path

# # ── Paths ─────────────────────────────────────────────────────────────────────
# ROOT        = Path(__file__).resolve().parent
# SCRIPTS_DIR = ROOT / "scripts"
# LOGS_DIR    = ROOT / "logs"
# JOBS_FILE   = ROOT / "hiring_cafe_jobs.json"
# BY_ATS_FILE = ROOT / "hiring_cafe_by_ats.json"

# STEP1 = SCRIPTS_DIR / "hiring_cafe_step1_extract_urls.py"
# STEP2 = SCRIPTS_DIR / "hiring_cafe_step2_extract_ats_urls.py"
# STEP3 = SCRIPTS_DIR / "hiring_cafe_step3_combine_by_ats.py"



# # ── Helpers ───────────────────────────────────────────────────────────────────
# def _banner(msg: str, char: str = "=") -> None:
#     print(f"\n{char * 60}")
#     print(f"  {msg}")
#     print(f"{char * 60}")


# def _now() -> str:
#     return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# def _run_step(label: str, script: Path, extra_args: list = []) -> bool:
#     """Run a step script as subprocess. Returns True on success."""
#     cmd = [sys.executable, str(script)] + extra_args
#     print(f"\n▶  {label}")
#     print(f"   Command : {' '.join(str(a) for a in cmd)}")
#     print(f"   Started : {_now()}")
#     print()
#     start = time.time()
#     result = subprocess.run(cmd, cwd=str(ROOT))
#     elapsed = time.time() - start
#     m, s = int(elapsed // 60), int(elapsed % 60)
#     duration = f"{m}m {s}s" if m else f"{s}s"
#     if result.returncode == 0:
#         print(f"\n   ✅ {label} finished in {duration}")
#         return True
#     else:
#         print(f"\n   ❌ {label} FAILED (exit {result.returncode}) after {duration}")
#         return False


# def _load_jobs(path: Path) -> tuple[dict, list]:
#     """Load jobs JSON → (meta, jobs_list)."""
#     with open(path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     if isinstance(data, list):
#         return {}, data
#     jobs = data.get("jobs", [])
#     meta = {k: v for k, v in data.items() if k != "jobs"}
#     return meta, jobs


# def _save_jobs(path: Path, meta: dict, jobs: list) -> None:
#     """Atomically save jobs to file."""
#     tmp = str(path) + ".tmp"
#     payload = {**meta, "step": 1, "updated": datetime.now().isoformat(),
#                 "count": len(jobs), "jobs": jobs}
#     with open(tmp, "w", encoding="utf-8") as f:
#         json.dump(payload, f, indent=2, ensure_ascii=False)
#     os.replace(tmp, path)


# def _clear_ats_fields(jobs_path: Path) -> int:
#     """
#     After a fresh Step 1 scrape, remove stale ats_url / ats_platform fields
#     so Step 2 knows to process all jobs fresh instead of skipping them.
#     Returns number of jobs cleared.
#     """
#     if not jobs_path.exists():
#         return 0
#     try:
#         meta, jobs = _load_jobs(jobs_path)
#         cleared = 0
#         for j in jobs:
#             if "ats_url" in j or "ats_platform" in j:
#                 j.pop("ats_url", None)
#                 j.pop("ats_platform", None)
#                 cleared += 1
#         _save_jobs(jobs_path, meta, jobs)
#         return cleared
#     except Exception as e:
#         print(f"   ⚠️  Could not clear ATS fields: {e}")
#         return 0


# def _load_job_count(path: Path) -> int:
#     try:
#         _, jobs = _load_jobs(path)
#         return len(jobs)
#     except Exception:
#         return 0


# def _write_run_log(log_path: Path, summary: dict) -> None:
#     LOGS_DIR.mkdir(exist_ok=True)
#     with open(log_path, "a", encoding="utf-8") as f:
#         f.write(json.dumps(summary) + "\n")


#!/usr/bin/env python3
"""
hiring.cafe — Full Pipeline Runner
===================================
Runs all 3 steps in sequence with a single command:

  Step 1 → Scrape fresh job URLs from hiring.cafe
  Step 2 → Extract ATS URLs from each job page  (checkpoint/resume safe)
  Step 3 → Combine jobs into by_ats grouping

USAGE
─────
  python run_hiring_cafe_pipeline.py              # full run
  python run_hiring_cafe_pipeline.py --skip-step1 # resume Step 2 after interrupt
  python run_hiring_cafe_pipeline.py --limit 20   # test with 20 jobs
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "scripts"
LOGS_DIR    = ROOT / "logs"
JOBS_FILE   = ROOT / "hiring_cafe_jobs.json"
BY_ATS_FILE = ROOT / "hiring_cafe_by_ats.json"

STEP1 = SCRIPTS_DIR / "hiring_cafe_step1_extract_urls.py"
STEP2 = SCRIPTS_DIR / "hiring_cafe_step2_extract_ats_urls.py"
STEP3 = SCRIPTS_DIR / "hiring_cafe_step3_combine_by_ats.py"
STEP4 = SCRIPTS_DIR / "hiring_cafe_step4_ingest_to_api.py"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _banner(msg: str, char: str = "=") -> None:
    print(f"\n{char * 60}")
    print(f"  {msg}")
    print(f"{char * 60}")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _kill_chrome() -> None:
    """
    Kill any lingering Chrome/Chromedriver processes.
    Critical on Windows — stale Chrome processes lock the profile folder,
    causing 'Browser window not found' and InvalidSessionIdException errors.
    """
    if sys.platform == "win32":
        for proc_name in ("chrome.exe", "chromedriver.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
    else:
        # Linux/Mac
        for proc_name in ("chrome", "chromedriver", "google-chrome"):
            try:
                subprocess.run(
                    ["pkill", "-f", proc_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass


def _kill_chrome_profile_locks(root: Path) -> None:
    """
    Remove Chrome profile lock files that prevent a new session from starting.
    These are left behind when Chrome crashes or is force-killed.
    """
    chrome_profile = root / "chrome_profile"
    lock_files = [
        chrome_profile / "SingletonLock",
        chrome_profile / "SingletonCookie",
        chrome_profile / "SingletonSocket",
        chrome_profile / "Default" / "LOCK",
        chrome_profile / "Default" / "lockfile",
    ]
    removed = []
    for lock in lock_files:
        if lock.exists():
            try:
                lock.unlink()
                removed.append(lock.name)
            except Exception as e:
                print(f"   ⚠️  Could not remove lock file {lock.name}: {e}")
    if removed:
        print(f"   🔓 Removed Chrome lock files: {', '.join(removed)}")


def _run_step(label: str, script: Path, extra_args: list = []) -> bool:
    """
    Run a step script as a subprocess.
    On Ctrl+C: kills the child process AND Chrome, then exits cleanly.
    """
    cmd = [sys.executable, str(script)] + extra_args
    print(f"\n▶  {label}")
    print(f"   Command : {' '.join(str(a) for a in cmd)}")
    print(f"   Started : {_now()}")
    print()

    start = time.time()
    proc = None
    try:
        proc = subprocess.Popen(cmd, cwd=str(ROOT))
        proc.wait()
        elapsed = time.time() - start
        m, s = int(elapsed // 60), int(elapsed % 60)
        duration = f"{m}m {s}s" if m else f"{s}s"
        if proc.returncode == 0:
            print(f"\n   ✅ {label} finished in {duration}")
            return True
        else:
            print(f"\n   ❌ {label} FAILED (exit {proc.returncode}) after {duration}")
            return False
    except KeyboardInterrupt:
        print(f"\n🛑 Ctrl+C — stopping {label}...")
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        print("   🧹 Killing Chrome processes...")
        _kill_chrome()
        print("   ✅ Done. Progress was saved.")
        print("   ℹ️  Re-run with --skip-step1 to resume Step 2.")
        sys.exit(1)


def _load_jobs(path: Path) -> tuple[dict, list]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {}, data
    jobs = data.get("jobs", [])
    meta = {k: v for k, v in data.items() if k != "jobs"}
    return meta, jobs


def _save_jobs(path: Path, meta: dict, jobs: list) -> None:
    tmp = str(path) + ".tmp"
    payload = {**meta, "step": 1, "updated": datetime.now().isoformat(),
                "count": len(jobs), "jobs": jobs}
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _clear_ats_fields(jobs_path: Path) -> int:
    """Strip stale ats_url/ats_platform so Step 2 processes all fresh jobs."""
    if not jobs_path.exists():
        return 0
    try:
        meta, jobs = _load_jobs(jobs_path)
        cleared = sum(1 for j in jobs if "ats_url" in j or "ats_platform" in j)
        for j in jobs:
            j.pop("ats_url", None)
            j.pop("ats_platform", None)
        _save_jobs(jobs_path, meta, jobs)
        return cleared
    except Exception as e:
        print(f"   ⚠️  Could not clear ATS fields: {e}")
        return 0


def _load_job_count(path: Path) -> int:
    try:
        _, jobs = _load_jobs(path)
        return len(jobs)
    except Exception:
        return 0


def _write_run_log(log_path: Path, summary: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full hiring.cafe pipeline (Steps 1 → 2 → 3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--skip-step1", action="store_true",
                        help="Skip scraping. Resume Step 2 from where it left off.")
    parser.add_argument("--skip-step2", action="store_true",
                        help="Skip ATS extraction.")
    parser.add_argument("--skip-step3", action="store_true",
                        help="Skip combining. Only run Step 4 (API Ingestion).")
    parser.add_argument("--limit", type=int, metavar="N", default=None,
                        help="Only enrich first N jobs in Step 2 (for testing).")
    args = parser.parse_args()

    run_start = time.time()
    run_id    = datetime.now().strftime("%Y%m%d_%H%M%S")

    _banner(f"🚀 hiring.cafe Pipeline  —  {_now()}")
    print(f"   Run ID  : {run_id}")
    print(f"   Root    : {ROOT}")

    # ── PRE-FLIGHT: Kill stale Chrome + remove profile locks ─────────────────
    # This prevents "Browser window not found" and InvalidSessionIdException
    # errors caused by leftover Chrome processes from previous runs.
    print(f"\n   🧹 Pre-flight: killing stale Chrome processes...")
    _kill_chrome()
    time.sleep(1)  # Give OS time to release file handles
    _kill_chrome_profile_locks(ROOT)
    print(f"   ✅ Pre-flight complete")

    results = {}

    # ── STEP 1 ────────────────────────────────────────────────────────────────
    if args.skip_step1:
        count = _load_job_count(JOBS_FILE) if JOBS_FILE.exists() else 0
        print(f"\n⏭️  Step 1 skipped — reusing {JOBS_FILE.name} ({count} jobs)")
        results["step1"] = "skipped"
    else:
        if not STEP1.exists():
            print(f"❌ Step 1 script not found: {STEP1}", file=sys.stderr)
            return 1
        _banner("STEP 1 — Scraping job URLs from hiring.cafe", "-")
        ok = _run_step("Step 1: Scrape jobs", STEP1)
        results["step1"] = "ok" if ok else "failed"
        if not ok:
            _banner("❌ Pipeline stopped — Step 1 failed")
            return 1

        print(f"\n   🧹 Clearing stale ATS fields from previous run...")
        cleared = _clear_ats_fields(JOBS_FILE)
        count = _load_job_count(JOBS_FILE)
        print(f"   📋 Jobs scraped: {count}  |  ATS fields cleared: {cleared}")

        if count == 0:
            print(f"\n   ⚠️  Step 1 found 0 jobs — hiring.cafe may be blocking requests.")
            print(f"   ℹ️  Wait 30 minutes and try again, or check your internet connection.")
            _banner("❌ Pipeline stopped — 0 jobs scraped")
            return 1

    # ── STEP 2 ────────────────────────────────────────────────────────────────
    if args.skip_step2:
        print(f"\n⏭️  Step 2 skipped — reusing existing ATS URLs")
        results["step2"] = "skipped"
    else:
        if not STEP2.exists():
            print(f"❌ Step 2 script not found: {STEP2}", file=sys.stderr)
            return 1

        # Kill Chrome again between steps — fresh session for Step 2
        print(f"\n   🧹 Resetting Chrome before Step 2...")
        _kill_chrome()
        time.sleep(2)
        _kill_chrome_profile_locks(ROOT)

        _banner("STEP 2 — Extracting ATS URLs (saves after every job)", "-")
        step2_args = ["--input", str(JOBS_FILE), "--output", str(JOBS_FILE)]
        if args.limit:
            step2_args += ["--limit", str(args.limit)]

        ok = _run_step("Step 2: Extract ATS URLs", STEP2, step2_args)
        results["step2"] = "ok" if ok else "failed"

        if not ok:
            print("\n   ⚠️  Step 2 interrupted — progress already saved.")
            print("   ℹ️  Re-run with --skip-step1 to resume from where it stopped.")

    # ── STEP 3 ────────────────────────────────────────────────────────────────
    if args.skip_step3:
        print(f"\n⏭️  Step 3 skipped — using {BY_ATS_FILE.name}")
        results["step3"] = "skipped"
    else:
        if not STEP3.exists():
            print(f"❌ Step 3 script not found: {STEP3}", file=sys.stderr)
            return 1
        _banner("STEP 3 — Combining jobs by ATS platform", "-")
        step3_args = ["--input", str(JOBS_FILE), "--output", str(BY_ATS_FILE)]
        ok = _run_step("Step 3: Combine by ATS", STEP3, step3_args)
        results["step3"] = "ok" if ok else "failed"

    # ── STEP 4 ────────────────────────────────────────────────────────────────
    if STEP4.exists():
        _banner("STEP 4 — Extracting ATS details & Ingesting to Website API", "-")
        step4_args = ["--input", str(BY_ATS_FILE)]
        ok = _run_step("Step 4: Ingest to API", STEP4, step4_args)
        results["step4"] = "ok" if ok else "failed"

    # ── Final Summary ─────────────────────────────────────────────────────────
    total_elapsed = time.time() - run_start
    m, s = int(total_elapsed // 60), int(total_elapsed % 60)

    jobs_count, jobs_with_ats, platform_list = 0, 0, []
    try:
        _, all_jobs = _load_jobs(JOBS_FILE)
        jobs_count    = len(all_jobs)
        jobs_with_ats = sum(1 for j in all_jobs if j.get("ats_url"))
    except Exception:
        pass
    try:
        with open(BY_ATS_FILE) as f:
            by_ats = json.load(f)
        platform_list = by_ats.get("platforms", [])
        if isinstance(platform_list, dict):
            platform_list = list(platform_list.keys())
    except Exception:
        pass

    _banner(f"🏁 Pipeline Complete  —  {_now()}")
    print(f"   Total time      : {m}m {s}s")
    print(f"   Step 1          : {results.get('step1', 'not run')}")
    print(f"   Step 2          : {results.get('step2', 'not run')}")
    print(f"   Step 3          : {results.get('step3', 'not run')}")
    print(f"   Step 4          : {results.get('step4', 'not run')}")
    print(f"   Jobs total      : {jobs_count}")
    print(f"   Jobs with ATS   : {jobs_with_ats}  ({int(jobs_with_ats/jobs_count*100) if jobs_count else 0}%)")
    if platform_list:
        real_platforms = [p for p in sorted(platform_list) if p != "unknown"]
        print(f"   ATS platforms   : {', '.join(real_platforms) if real_platforms else 'none yet'}")
    print()

    LOGS_DIR.mkdir(exist_ok=True)
    _write_run_log(LOGS_DIR / "pipeline_runs.log", {
        "run_id": run_id, "timestamp": _now(),
        "duration_sec": round(total_elapsed), "results": results,
        "jobs_total": jobs_count, "jobs_with_ats": jobs_with_ats,
        "platforms": platform_list,
    })
    print(f"   📝 Run log → logs/pipeline_runs.log")
    print("=" * 60)

    if results.get("step1") == "failed" or results.get("step3") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
