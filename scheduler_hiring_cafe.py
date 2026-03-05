"""
Hiring Cafe Website Scheduler Integration

This script connects the hiring-cafe-engine pipeline to the website
automation orchestrator.

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

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_hiring_cafe_pipeline import run_pipeline
from core.logger import logger
from core.auth_service import BaseAPIClient


# Workflow configuration
WORKFLOW_KEY = "hiring_cafe_job_extractor"
WORKFLOW_ID = 9


def get_api_client():
    """Create API client."""
    return BaseAPIClient()


def get_orchestrator_endpoint():
    return "orchestrator"


def get_schedule_from_website():
    """
    Fetch due schedules from the website.
    """
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
    """
    Lock the schedule to prevent multiple runs.
    """
    try:
        client = get_api_client()

        response = client.post(
            f"{get_orchestrator_endpoint()}/schedules/{schedule_id}/lock", json={}
        )

        return response.status_code == 200

    except Exception as e:
        logger.error(f"Failed to lock schedule: {e}")
        return False


def unlock_schedule(schedule_id, frequency="daily", interval=1):
    """
    Update next_run_at after job completion.
    """
    try:
        client = get_api_client()

        now = datetime.now()

        if frequency == "daily":
            next_run = now + timedelta(days=interval)
        elif frequency == "weekly":
            next_run = now + timedelta(weeks=interval)
        else:
            next_run = now + timedelta(days=interval)

        payload = {
            "next_run_at": next_run.strftime("%Y-%m-%d %H:%M:%S"),
            "last_run_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "is_running": 0,
        }

        response = client.put(
            f"{get_orchestrator_endpoint()}/schedules/{schedule_id}",
            json=payload,
        )

        return response.status_code == 200

    except Exception as e:
        logger.error(f"Failed to unlock schedule: {e}")
        return False


def create_log(workflow_id, schedule_id, run_id):
    """
    Create execution log.
    """
    try:
        client = get_api_client()

        payload = {
            "workflow_id": workflow_id,
            "schedule_id": schedule_id,
            "run_id": run_id,
            "status": "running",
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        response = client.post(f"{get_orchestrator_endpoint()}/logs", json=payload)

        if response.status_code == 200:
            return response.json().get("id")

        return None

    except Exception as e:
        logger.error(f"Failed to create log: {e}")
        return None


def update_log(log_id, status, records_processed=0, error=None, execution_metadata=None):
    """
    Update execution log.
    """
    try:
        client = get_api_client()

        payload = {
            "status": status,
            "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
    """
    Main scheduler entry.
    """

    logger.info("Hiring Cafe Scheduler Starting")

    schedule = get_schedule_from_website()

    if not schedule:
        logger.info("No schedule due. Exiting.")
        return

    schedule_id = schedule.get("id")
    workflow_id = schedule.get("automation_workflow_id")

    frequency = schedule.get("frequency", "daily")
    interval = schedule.get("interval_value", 1)

    if not lock_schedule(schedule_id):
        logger.error("Could not lock schedule")
        return

    run_id = str(uuid.uuid4())

    log_id = create_log(workflow_id, schedule_id, run_id)

    try:

        logger.info("Running Hiring Cafe Pipeline")

        results = run_pipeline()

        jobs_processed = results.get("jobs_saved", 0) if results else 0

        execution_metadata = None
        if results:
            execution_metadata = {
                "jobs_saved": results.get("jobs_saved"),
                "jobs_found": results.get("jobs_found"),
                "timestamp": results.get("timestamp"),
                "workflow": WORKFLOW_KEY
            }

        if log_id:
            update_log(
                log_id,
                status="success",
                records_processed=jobs_processed,
                execution_metadata=execution_metadata
            )

    except Exception as e:

        logger.error(f"Pipeline failed: {e}")

        if log_id:
            update_log(log_id, "failed", error=e)

    finally:

        unlock_schedule(schedule_id, frequency, interval)

        logger.info("Scheduler Finished")


if __name__ == "__main__":
    main()
