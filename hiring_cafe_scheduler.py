"""
Hiring Cafe Website Scheduler Integration

Flow
-----
1. Task Scheduler runs this script
2. Script calls website API to check due schedules
3. If workflow is due → run pipeline
4. Update logs and next_run_at
"""

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_api_client():
    return BaseAPIClient()


def get_orchestrator_endpoint():
    return "orchestrator"


def _utc_now() -> datetime:
    """Return current time as UTC-aware datetime."""
    return datetime.now(timezone.utc)


def _to_utc_mysql(dt: datetime) -> str:
    """
    Convert a datetime to UTC in MySQL DATETIME format 'YYYY-MM-DD HH:MM:SS'.

    Handles both timezone-aware and naive datetimes:
    - Aware: Convert to UTC
    - Naive: Treat as local system time, convert to UTC

    Returns UTC timestamp in MySQL-compatible format (no 'Z' suffix).
    """
    if dt.tzinfo is None:
        # Naive datetime: treat as local system time
        # Use astimezone() with no args to attach local timezone, then convert to UTC
        dt = dt.astimezone(timezone.utc)
    else:
        # Already timezone-aware: convert to UTC
        dt = dt.astimezone(timezone.utc)

    # Return as naive UTC string for MySQL
    return dt.replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def get_next_run_from_cron(cron_expression: str, timezone_str: str = "America/Los_Angeles") -> str:
    """
    Calculate the next run time from a cron expression in the specified timezone.

    Returns UTC timestamp in MySQL DATETIME format 'YYYY-MM-DD HH:MM:SS'.

    Uses croniter/pytz if available for full cron support.
    Falls back to built-in parser for simple patterns like '0 9,16 * * *'.
    """
    # Get current time in target timezone
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(timezone_str)
    except ImportError:
        # Python < 3.9 fallback
        try:
            import pytz
            tz = pytz.timezone(timezone_str)
        except ImportError:
            logger.warning(f"No timezone library available. Treating times as local.")
            tz = None

    # Get timezone-aware current time
    if tz:
        now_local = datetime.now(tz)
    else:
        now_local = datetime.now().astimezone()  # Local timezone

    # ── Try croniter first (most accurate) ────────────────────────────────
    try:
        from croniter import croniter
        cron = croniter(cron_expression, now_local)
        next_run = cron.get_next(datetime)  # Returns timezone-aware datetime
        utc_str = _to_utc_mysql(next_run)
        logger.info(f"Next run (croniter): {next_run.isoformat()} -> UTC: {utc_str}")
        return utc_str
    except ImportError:
        logger.warning("croniter not installed. Using built-in cron parser. "
                       "Install: pip install croniter")
    except Exception as e:
        logger.warning(f"croniter failed ({e}). Falling back to built-in parser.")

    # ── Built-in fallback: parse hour field only ───────────────────────────
    try:
        parts = cron_expression.strip().split()
        if len(parts) >= 2:
            hour_field   = parts[1]
            minute_field = parts[0]

            hours  = sorted([int(h.strip()) for h in hour_field.split(",") if h.strip().isdigit()])
            minute = int(minute_field) if minute_field.isdigit() else 0

            # Build candidates in local timezone
            today = now_local.date()
            for h in hours:
                if tz:
                    candidate = datetime(today.year, today.month, today.day, h, minute, 0, tzinfo=tz)
                else:
                    candidate = datetime(today.year, today.month, today.day, h, minute, 0).astimezone()

                if candidate > now_local:
                    utc_str = _to_utc_mysql(candidate)
                    logger.info(f"Next run (built-in): {candidate.isoformat()} -> UTC: {utc_str}")
                    return utc_str

            # All today's slots passed → first slot tomorrow
            tomorrow = today + timedelta(days=1)
            if tz:
                next_run = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hours[0], minute, 0, tzinfo=tz)
            else:
                next_run = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hours[0], minute, 0).astimezone()

            utc_str = _to_utc_mysql(next_run)
            logger.info(f"Next run (built-in, tomorrow): {next_run.isoformat()} -> UTC: {utc_str}")
            return utc_str

    except Exception as e:
        logger.warning(f"Built-in cron parser failed ({e}). Using +1 day fallback.")

    # ── Last resort ────────────────────────────────────────────────────────
    fallback = now_local + timedelta(days=1)
    utc_str = _to_utc_mysql(fallback)
    logger.warning(f"Using fallback next_run_at: {utc_str}")
    return utc_str


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

    KEY FIX (datetime offset-naive/aware bug)
    ──────────────────────────────────────────
    The server DB stores next_run_at as a MySQL DATETIME (no timezone).
    The server-side Python treats stored values as UTC in comparisons.
    Previously we sent LOCAL time strings, so '16:00:00' PDT was stored
    and the server compared it as UTC '16:00:00' vs real UTC (~23:00),
    seeing it as always overdue → fires every 5 min → logs FAILED.
    FIX: send UTC values in MySQL DATETIME format 'YYYY-MM-DD HH:MM:SS'.
    """
    try:
        client = get_api_client()
        now_utc = _utc_now()

        if cron_expression:
            next_run_str = get_next_run_from_cron(cron_expression, timezone_str)
        else:
            next_run_str = _to_utc_mysql(now_utc + timedelta(days=1))
            logger.warning("No cron expression provided to unlock_schedule. Used +1 day fallback.")

        payload = {
            "next_run_at": next_run_str,
            "last_run_at": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "is_running":  0,
        }

        logger.info(f"Unlocking schedule {schedule_id} → next_run_at: {next_run_str}")

        response = client.put(
            f"{get_orchestrator_endpoint()}/schedules/{schedule_id}",
            json=payload,
        )
        if response.status_code == 200:
            logger.info(f"Schedule {schedule_id} unlocked successfully.")
            return True
        logger.error(f"unlock_schedule failed: {response.status_code} {response.text[:300]}")
        return False
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
            "started_at":  _utc_now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        response = client.post(f"{get_orchestrator_endpoint()}/logs", json=payload)
        if response.status_code in (200, 201):
            data = response.json()
            log_id = data.get("id")
            logger.info(f"Log created → id={log_id}, run_id={run_id}")
            return log_id
        logger.error(f"create_log failed: {response.status_code} {response.text[:300]}")
        return None
    except Exception as e:
        logger.error(f"Failed to create log: {e}")
        return None


def update_log(log_id, status, records_processed=0, error=None, execution_metadata=None):
    try:
        client = get_api_client()
        payload = {
            "status":            status,
            "finished_at":       _utc_now().strftime("%Y-%m-%d %H:%M:%S"),
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
        if response.status_code == 200:
            logger.info(f"Log {log_id} updated → status={status}, records_processed={records_processed}")
            return True
        logger.error(f"update_log failed: {response.status_code} {response.text[:300]}")
        return False
    except Exception as e:
        logger.error(f"Failed to update log: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Debug helper: dump schedule record so you can diagnose the "never due" bug
# ─────────────────────────────────────────────────────────────────────────────
def debug_schedule():
    """
    Print full details of the schedule record for WORKFLOW_ID from the
    orchestrator API. Run once to diagnose why it's never returned as due:

        python hiring_cafe_scheduler.py --debug-schedule
    """
    try:
        client = BaseAPIClient()

        # 1. All schedules (see every record)
        logger.info("── Fetching ALL schedules ──────────────────────────────")
        r = client.get("orchestrator/schedules")
        if r.status_code == 200:
            schedules = r.json()
            logger.info(f"Total schedules in DB: {len(schedules)}")
            for s in schedules:
                logger.info(
                    f"  id={s.get('id')}  workflow_id={s.get('automation_workflow_id')}  "
                    f"is_running={s.get('is_running')}  "
                    f"next_run_at={s.get('next_run_at')}  "
                    f"last_run_at={s.get('last_run_at')}  "
                    f"cron={s.get('cron_expression')}"
                )
        else:
            logger.error(f"GET /schedules failed: {r.status_code} {r.text}")

        # 2. Due schedules right now
        logger.info("── Fetching DUE schedules ──────────────────────────────")
        r2 = client.get("orchestrator/schedules/due")
        if r2.status_code == 200:
            due = r2.json()
            logger.info(f"Due schedules right now: {len(due)}")
            for s in due:
                logger.info(f"  {s}")
        else:
            logger.error(f"GET /schedules/due failed: {r2.status_code} {r2.text}")

    except Exception as e:
        logger.error(f"debug_schedule failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# main()
# ─────────────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"),
        exist_ok=True,
    )

    # ── CLI args ──────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(description="Hiring Cafe Scheduler")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run the pipeline even if no schedule is currently due.",
    )
    parser.add_argument(
        "--debug-schedule",
        action="store_true",
        help="Print orchestrator schedule details and exit (no pipeline run).",
    )
    args = parser.parse_args()

    # ── Debug mode: just dump schedule info and exit ──────────────────────────
    if args.debug_schedule:
        debug_schedule()
        return

    logger.info("Hiring Cafe Scheduler Heartbeat - Polling Orchestrator")

    # ── Try to fetch a due schedule from orchestrator ─────────────────────────
    schedule = None
    api_reachable = True
    try:
        schedule = get_schedule_from_website()
    except Exception as e:
        logger.warning(f"Failed to connect to orchestrator API: {e}")
        api_reachable = False

    # ── Decide whether to proceed ─────────────────────────────────────────────
    if not schedule:
        if not api_reachable:
            logger.warning("Orchestrator API unreachable.")
        else:
            logger.info("No schedule due.")

        if not args.force:
            # Normal exit — nothing to do
            return

        logger.info("--force provided. Proceeding with pipeline run.")

    else:
        logger.info(
            f"Schedule due → id={schedule.get('id')}, "
            f"cron='{schedule.get('cron_expression')}', "
            f"tz={schedule.get('timezone')}"
        )

    # ── Extract schedule metadata ─────────────────────────────────────────────
    schedule_id  = schedule.get("id")               if schedule else None
    workflow_id  = schedule.get("automation_workflow_id") if schedule else WORKFLOW_ID
    cron_expr    = schedule.get("cron_expression", "0 9,16 * * *") if schedule else "0 9,16 * * *"
    timezone_str = schedule.get("timezone", "America/Los_Angeles")  if schedule else "America/Los_Angeles"

    # Lock the schedule so concurrent runs can't start
    if schedule_id:
        if not lock_schedule(schedule_id):
            logger.warning("Could not lock schedule — proceeding anyway.")

    run_id = str(uuid.uuid4())
    log_id = create_log(workflow_id, schedule_id, run_id) if schedule_id else None

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        logger.info("Running Hiring Cafe Pipeline")
        
        # Determine run name for the email report
        run_name = "Manual Run"
        if schedule:
            # Check current hour in local timezone to identify which scheduled slot this is
            now_local = datetime.now().astimezone()
            now_hour = now_local.hour
            if 8 <= now_hour <= 11:
                run_name = "9 AM Run"
            elif 15 <= now_hour <= 18:
                run_name = "4 PM Run"
            else:
                run_name = "Scheduled Run"
        elif args.force:
            run_name = "Forced Run"

        # Pass the run name to the pipeline (Step 4 / Email Reporter will use it)
        results = run_pipeline(["--run-name", run_name])

        jobs_processed = results.get("jobs_saved", 0) if results else 0
        execution_metadata = None
        if results:
            execution_metadata = {
                "jobs_saved":  results.get("jobs_saved"),
                "jobs_found":  results.get("jobs_found"),
                "timestamp":   results.get("timestamp"),
                "workflow":    WORKFLOW_KEY,
                "forced_run":  not bool(schedule),
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
