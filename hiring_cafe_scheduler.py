"""
Hiring Cafe Website Scheduler Integration

Flow
-----
1. Task Scheduler runs this script
2. Script calls website API to check due schedules
3. If workflow is due → run pipeline
4. Update logs and next_run_at
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Signal to all child processes that this run was launched by the scheduler.
# BrowserService reads SCHEDULER_LAUNCHED to apply anti-detection Chrome flags
# that make the browser fingerprint match an interactive session.
# Must be set BEFORE importing or calling anything that touches the browser.
os.environ["SCHEDULER_LAUNCHED"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_hiring_cafe_pipeline import run_pipeline
from core.logger import logger
from core.auth_service import BaseAPIClient

WORKFLOW_KEY = "hiring_cafe_job_extractor"
WORKFLOW_ID = 9


def get_api_client():
    return BaseAPIClient()


def get_orchestrator_endpoint():
    return "orchestrator"


def get_next_run_from_cron(cron_expression: str, timezone_str: str = "America/Los_Angeles") -> str:
    """
    Calculate the next run time from a cron expression.

    Uses the 'croniter' library if available (pip install croniter).
    Falls back to a simple parser for the common '0 9,16 * * *' pattern
    so the code works even without croniter installed.

    Returns a string in 'YYYY-MM-DD HH:MM:SS' format.
    """
    now = datetime.now()

    # ── Try croniter first (most accurate) ────────────────────────────────
    try:
        from croniter import croniter
        cron = croniter(cron_expression, now)
        next_run = cron.get_next(datetime)
        logger.info(f"Next run calculated via croniter: {next_run}")
        return next_run.strftime("%Y-%m-%d %H:%M:%S")
    except ImportError:
        logger.warning("croniter not installed. Using built-in cron parser. "
                       "Run:  venv\\Scripts\\pip install croniter  for full cron support.")
    except Exception as e:
        logger.warning(f"croniter failed ({e}). Falling back to built-in parser.")

    # ── Built-in fallback: parse hour field only ───────────────────────────
    # Handles patterns like '0 9,16 * * *' or '0 9 * * *'
    try:
        parts = cron_expression.strip().split()
        if len(parts) >= 2:
            hour_field   = parts[1]
            minute_field = parts[0]

            hours  = sorted([int(h.strip()) for h in hour_field.split(",") if h.strip().isdigit()])
            minute = int(minute_field) if minute_field.isdigit() else 0

            today = now.date()
            for h in hours:
                candidate = datetime(today.year, today.month, today.day, h, minute, 0)
                if candidate > now:
                    logger.info(f"Next run calculated via built-in parser: {candidate}")
                    return candidate.strftime("%Y-%m-%d %H:%M:%S")

            # All today's slots passed → first slot tomorrow
            tomorrow = today + timedelta(days=1)
            next_run = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hours[0], minute, 0)
            logger.info(f"Next run calculated via built-in parser (tomorrow): {next_run}")
            return next_run.strftime("%Y-%m-%d %H:%M:%S")

    except Exception as e:
        logger.warning(f"Built-in cron parser failed ({e}). Using +1 day fallback.")

    # ── Last resort ────────────────────────────────────────────────────────
    fallback = now + timedelta(days=1)
    logger.warning(f"Using fallback next_run_at: {fallback}")
    return fallback.strftime("%Y-%m-%d %H:%M:%S")


def get_schedule_from_website():
    try:
        client = get_api_client()
        response = client.get(f"{get_orchestrator_endpoint()}/schedules/due")
        if response.status_code == 200:
            schedules = response.json()
            for s in schedules:
                if s.get("automation_workflow_id") == WORKFLOW_ID:
                    return s
        return None
    except Exception as e:
        logger.error(f"Failed to fetch schedule: {e}")
        return None


def lock_schedule(schedule_id):
    try:
        client = get_api_client()
        response = client.post(
            f"{get_orchestrator_endpoint()}/schedules/{schedule_id}/lock", json={}
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to lock schedule: {e}")
        return False


def unlock_schedule(schedule_id, cron_expression: str = None, timezone_str: str = "America/Los_Angeles"):
    """
    Unlock the schedule and set next_run_at correctly from the cron expression.

    THE BUG THIS FIXES
    ──────────────────
    The old code did:  next_run = now + timedelta(days=interval)
    With interval=1 that always jumped exactly 24 hours ahead.
    Result: after the 9AM run completed, next_run_at was set to tomorrow 9AM,
    and the 4PM slot on the same day was permanently skipped.

    The new code reads the cron expression ('0 9,16 * * *') and finds the
    next actual future slot — so after the 9AM run it sets next_run_at to
    4PM the same day, and after the 4PM run it sets it to tomorrow 9AM.
    """
    try:
        client = get_api_client()
        now = datetime.now()

        if cron_expression:
            next_run_str = get_next_run_from_cron(cron_expression, timezone_str)
        else:
            next_run_str = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
            logger.warning("No cron expression provided to unlock_schedule. Used +1 day fallback.")

        payload = {
            "next_run_at": next_run_str,
            "last_run_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "is_running":  0,
        }

        logger.info(f"Unlocking schedule {schedule_id} → next_run_at: {next_run_str}")

        response = client.put(
            f"{get_orchestrator_endpoint()}/schedules/{schedule_id}",
            json=payload,
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to unlock schedule: {e}")
        return False


def create_log(workflow_id, schedule_id, run_id):
    try:
        client = get_api_client()
        payload = {
            "workflow_id": workflow_id,
            "schedule_id": schedule_id,
            "run_id":      run_id,
            "status":      "running",
            "started_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        response = client.post(f"{get_orchestrator_endpoint()}/logs", json=payload)
        if response.status_code == 200:
            return response.json().get("id")
        return None
    except Exception as e:
        logger.error(f"Failed to create log: {e}")
        return None


def update_log(log_id, status, records_processed=0, error=None, execution_metadata=None):
    try:
        client = get_api_client()
        payload = {
            "status":            status,
            "finished_at":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "records_processed": records_processed,
        }
        if error:
            payload["error_summary"] = str(error)
        if execution_metadata:
            payload["execution_metadata"] = execution_metadata
        response = client.put(
            f"{get_orchestrator_endpoint()}/logs/{log_id}",
            json=payload,
        )
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to update log: {e}")
        return False


def main():
    logger.info("Hiring Cafe Scheduler Starting")

    schedule = None
    api_reachable = True
    try:
        schedule = get_schedule_from_website()
    except Exception as e:
        logger.warning(f"Failed to connect to orchestrator API: {e}. Running pipeline in standalone mode.")
        api_reachable = False

    if not api_reachable or not schedule:
        if api_reachable:
            logger.info("No schedule due. Exiting.")
            return

        logger.warning("Running pipeline in standalone mode due to API unreachability.")
        try:
            logger.info("Running Hiring Cafe Pipeline (standalone)")
            results = run_pipeline()
            logger.info(f"Standalone pipeline finished. Results: {results}")
        except Exception as e:
            logger.error(f"Standalone pipeline failed: {e}")
        finally:
            logger.info("Scheduler Finished (standalone mode)")
        return

# ── Extract schedule metadata if API returned one ──────────────────────
    schedule_id  = schedule.get("id")  if schedule else None
    workflow_id  = schedule.get("automation_workflow_id") if schedule else WORKFLOW_ID
    cron_expr    = schedule.get("cron_expression", "0 9,16 * * *") if schedule else "0 9,16 * * *"
    timezone_str = schedule.get("timezone", "America/Los_Angeles") if schedule else "America/Los_Angeles"

    if not schedule:
        logger.warning("No schedule due or API unreachable — running pipeline anyway.")
    else:
        logger.info(f"Schedule due → id={schedule_id}, cron='{cron_expr}', tz={timezone_str}")
        if not lock_schedule(schedule_id):
            logger.warning("Could not lock schedule — running pipeline anyway.")

    run_id = str(uuid.uuid4())
    log_id = create_log(workflow_id, schedule_id, run_id) if schedule_id else None

    try:
        logger.info("Running Hiring Cafe Pipeline")
        results = run_pipeline()

        jobs_processed = results.get("jobs_saved", 0) if results else 0
        execution_metadata = None
        if results:
            execution_metadata = {
                "jobs_saved": results.get("jobs_saved"),
                "jobs_found": results.get("jobs_found"),
                "timestamp":  results.get("timestamp"),
                "workflow":   WORKFLOW_KEY,
            }

        if log_id:
            update_log(
                log_id,
                status="success",
                records_processed=jobs_processed,
                execution_metadata=execution_metadata,
            )

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if log_id:
            update_log(log_id, "failed", error=e)

    finally:
        if schedule_id:
            unlock_schedule(schedule_id, cron_expression=cron_expr, timezone_str=timezone_str)
        logger.info("Scheduler Finished")

if __name__ == "__main__":
    main()
