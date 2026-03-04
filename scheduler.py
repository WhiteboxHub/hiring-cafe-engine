import schedule
import time
import os
import subprocess
import sys
from datetime import datetime
from dotenv import load_dotenv
import logging

# Load environment variables (like SCHEDULER_TIME) FIRST
# so they're available for the subprocess env below
load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(logs_dir, "scheduler.log"), mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("scheduler")


def _build_subprocess_env() -> dict:
    """
    Build the environment dict to pass to the pipeline subprocess.

    TWO CRITICAL FIXES here:
    1. PYTHONIOENCODING=utf-8  — Without this, Python's stdout inside the
       subprocess defaults to Windows cp1252 encoding, which cannot encode
       emoji characters (like the rocket 🚀) used in pipeline banners.
       This was the direct cause of the UnicodeEncodeError crash.

    2. DISPLAY / no capture_output — The pipeline needs a real stdout/stderr
       attached (not pipes) so that Chrome/undetected-chromedriver launches
       correctly. capture_output=True hijacks the pipes and makes Chrome think
       it is running in a headless/sandboxed environment, causing it to open
       a blank page (the empty React shell) instead of loading hiring.cafe.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"          # Python 3.7+ UTF-8 mode — belt-and-suspenders
    return env


def run_extraction():
    """Run the main hiring_cafe pipeline script as a subprocess."""
    logger.info("=" * 50)
    logger.info("Starting scheduled extraction pipeline...")
    logger.info("=" * 50)

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run_hiring_cafe_pipeline.py')
    cwd = os.path.dirname(os.path.abspath(__file__))

    if not os.path.isfile(script_path):
        logger.error(f"Pipeline script not found: {script_path}")
        return

    # ── KEY FIX: do NOT use capture_output=True ───────────────────────────────
    # The original scheduler used:
    #   subprocess.run(..., capture_output=True, text=True)
    #
    # capture_output=True redirects stdout/stderr to internal pipes.
    # This has two nasty side-effects:
    #
    # A) Chrome (via undetected-chromedriver) detects the missing terminal and
    #    behaves as if it is in a restricted/sandboxed environment. It opens a
    #    blank page instead of loading hiring.cafe, so Step 1 finds 0 jobs.
    #
    # B) The pipeline's print() calls with emoji hit Windows cp1252 encoding
    #    (because there is no real terminal to force UTF-8), causing:
    #    UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f680'
    #
    # Fix: Use Popen so the child process inherits the scheduler's own
    # stdout/stderr (a real console or log file), and pass PYTHONIOENCODING
    # in the environment to guarantee UTF-8 everywhere.
    # ─────────────────────────────────────────────────────────────────────────

    try:
        start_time = time.time()
        logger.info(f"Launching pipeline: {sys.executable} {script_path}")

        proc = subprocess.Popen(
            [sys.executable, script_path],
            cwd=cwd,
            env=_build_subprocess_env(),
            # stdout/stderr intentionally NOT redirected — child inherits parent's
            # console/terminal so Chrome behaves normally and emoji print correctly.
            stdout=None,
            stderr=None,
        )

        proc.wait()  # Block until pipeline finishes

        elapsed = time.time() - start_time
        m, s = int(elapsed // 60), int(elapsed % 60)

        if proc.returncode == 0:
            logger.info(f"Pipeline completed successfully in {m}m {s}s.")
        else:
            logger.error(f"Pipeline FAILED with exit code {proc.returncode} after {m}m {s}s.")

    except Exception as e:
        logger.exception(f"Failed to run extraction process: {e}")


def start_scheduler():
    # Set the schedule time from .env (default 09:00)
    schedule_time = os.getenv("SCHEDULER_TIME", "09:00")

    logger.info("=" * 50)
    logger.info("Job Engine Scheduler started")
    logger.info(f"Pipeline will run daily at: {schedule_time}")
    logger.info("Note: if started AFTER the scheduled time, first run is tomorrow.")
    logger.info("Keep this window open. Press Ctrl+C to stop.")
    logger.info("=" * 50)

    schedule.every().day.at(schedule_time).do(run_extraction)

    # ── Optional: run immediately on start so you can verify it works ─────────
    # Uncomment the next line to trigger a run right now when the scheduler starts:
    # run_extraction()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == '__main__':
    try:
        start_scheduler()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
    except Exception as e:
        logger.exception(f"Scheduler crashed: {e}")