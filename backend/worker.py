"""
Worker Process — WP8
Stand-alone process that owns the scheduler. Never import this in the API.
Acquires a PostgreSQL advisory lock before starting, ensuring only one worker
runs active jobs in a multi-replica deployment.

Run with:
    SCHEDULER_ENABLED=true python worker.py
"""
import logging
import os
import sys
import time

from services.logging_config import configure_secure_logging

configure_secure_logging()
logger = logging.getLogger("worker")


def main():
    if not os.getenv("SCHEDULER_ENABLED", "false").lower() == "true":
        logger.error(
            "SCHEDULER_ENABLED is not set to 'true'. "
            "Set SCHEDULER_ENABLED=true in the worker container's environment."
        )
        sys.exit(1)

    # Import here so that the scheduler module is not loaded in the API process
    from database import get_db
    from services.job_claim_service import (
        acquire_leader_lock,
        release_leader_lock,
        generate_worker_id,
    )
    from scheduler import start_scheduler

    worker_id = generate_worker_id()
    logger.info(f"Worker starting — ID: {worker_id}")

    # ── Leader Election via PostgreSQL Advisory Lock ──────────────────────────
    # Get a dedicated DB connection for the lifetime of this process
    db_gen = get_db()
    db = next(db_gen)

    is_leader = acquire_leader_lock(db)
    if not is_leader:
        logger.warning(
            "Another worker already holds the scheduler advisory lock. "
            "This process will exit. Render/K8s should run only ONE worker replica."
        )
        sys.exit(0)

    logger.info("Advisory lock acquired — this worker is the scheduler leader.")

    try:
        # Start the in-process APScheduler (background thread scheduler)
        sched = start_scheduler()
        logger.info("Scheduler started successfully. Worker is running.")

        # Keep the main thread alive; the scheduler runs in a daemon thread pool
        while True:
            time.sleep(30)
            logger.debug("Worker heartbeat — scheduler is active.")

    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker received shutdown signal.")
    except Exception as exc:
        logger.exception(f"Worker crashed: {exc}")
        sys.exit(2)
    finally:
        try:
            release_leader_lock(db)
        except Exception as e:
            logger.warning(f"Failed to release advisory lock on shutdown: {e}")
        logger.info("Worker exiting.")


if __name__ == "__main__":
    main()
