"""
Job Claim Service — WP8
PostgreSQL advisory lock (leader election) and row-level lease claiming
for the scheduler worker process.  Only runs in the worker, never in the API.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger("job_claim_service")

# A stable advisory lock ID for scheduler leadership (must be unique per application)
SCHEDULER_ADVISORY_LOCK_ID = 88991234


def acquire_leader_lock(db: Session, lock_id: int = SCHEDULER_ADVISORY_LOCK_ID) -> bool:
    """
    Attempts to acquire a PostgreSQL session-level advisory lock.
    Returns True if this process is now the leader, False if another holds the lock.
    Falls back gracefully on SQLite (dev mode) — always returns True.
    """
    try:
        result = db.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": lock_id}
        )
        acquired: bool = result.scalar()
        if not acquired:
            logger.debug("Advisory lock not acquired — another worker is the leader.")
        return acquired
    except Exception as e:
        # SQLite or other non-PG driver — grant leadership unconditionally in dev
        if "pg_try_advisory_lock" in str(e) or "no such function" in str(e).lower():
            logger.debug("Advisory lock unavailable (non-PG); assuming leader for dev mode.")
            return True
        logger.error(f"Unexpected error acquiring advisory lock: {e}")
        return False


def release_leader_lock(db: Session, lock_id: int = SCHEDULER_ADVISORY_LOCK_ID) -> None:
    """Releases the session-level advisory lock. Call in the finally block."""
    try:
        db.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": lock_id}
        )
    except Exception as e:
        logger.warning(f"Failed to release advisory lock: {e}")


def claim_workflow_session(
    db: Session,
    session_id: int,
    worker_id: str,
    lease_seconds: int = 120,
) -> bool:
    """
    Atomically claims a workflow session using an UPDATE with a WHERE guard.
    Returns True if this worker now owns the lease, False if another beat us.
    """
    now = datetime.utcnow()
    claimed_until = now + timedelta(seconds=lease_seconds)
    try:
        result = db.execute(
            text("""
                UPDATE workflow_sessions
                SET claimed_by    = :worker_id,
                    claimed_until = :claimed_until,
                    attempt_count = COALESCE(attempt_count, 0) + 1
                WHERE id = :session_id
                  AND (claimed_until IS NULL OR claimed_until < :now)
            """),
            {
                "worker_id": worker_id,
                "claimed_until": claimed_until,
                "now": now,
                "session_id": session_id,
            },
        )
        db.commit()
        return result.rowcount == 1
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to claim workflow session {session_id}: {e}")
        return False


def release_workflow_session(db: Session, session_id: int) -> None:
    """
    Releases the row-level lease on a workflow session once processing completes or yields.
    """
    try:
        db.execute(
            text("""
                UPDATE workflow_sessions
                SET claimed_by    = NULL,
                    claimed_until = NULL
                WHERE id = :session_id
            """),
            {"session_id": session_id}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to release workflow session {session_id}: {e}")



def claim_campaign(
    db: Session,
    campaign_id: int,
    worker_id: str,
    lease_seconds: int = 600,
) -> bool:
    """
    Atomically claims a campaign row.  Returns True if claim succeeded.
    """
    now = datetime.utcnow()
    claimed_until = now + timedelta(seconds=lease_seconds)
    try:
        result = db.execute(
            text("""
                UPDATE campaigns
                SET claimed_by    = :worker_id,
                    claimed_until = :claimed_until,
                    attempt_count = COALESCE(attempt_count, 0) + 1
                WHERE id = :campaign_id
                  AND (claimed_until IS NULL OR claimed_until < :now)
            """),
            {
                "worker_id": worker_id,
                "claimed_until": claimed_until,
                "now": now,
                "campaign_id": campaign_id,
            },
        )
        db.commit()
        return result.rowcount == 1
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to claim campaign {campaign_id}: {e}")
        return False


def generate_worker_id() -> str:
    """Generates a unique worker identifier for lease attribution."""
    import socket
    hostname = socket.gethostname()
    return f"{hostname}-{uuid.uuid4().hex[:8]}"
