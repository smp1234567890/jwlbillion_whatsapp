"""
Audit Service — WP2
Centralized, immutable audit event recorder. Callers must never provide raw PII;
use recipient_hash (SHA-256 salted with AUDIT_HASH_SALT) in metadata_json.
"""
import hashlib
import logging
from datetime import datetime
from typing import Optional

import config
from sqlalchemy.orm import Session
import models

logger = logging.getLogger("audit_service")

_SALT = getattr(config, "AUDIT_HASH_SALT", config.SECRET_KEY)


def hash_phone(phone: str) -> str:
    """Returns a salted SHA-256 hash of a phone number for audit-safe storage."""
    return hashlib.sha256((_SALT + phone).encode("utf-8")).hexdigest()[:16]


def record_audit_event(
    db: Session,
    action: str,
    actor_user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> models.AuditEvent:
    """
    Creates an immutable AuditEvent row.

    Rules:
    - Never place raw phone numbers or email addresses in metadata.
    - Use hash_phone() for recipient references.
    - After creation the row must NOT be updated (treat as append-only).
    """
    import json

    if metadata:
        # Refuse to write if raw E.164 phone is embedded in metadata values
        for v in metadata.values():
            if isinstance(v, str) and v.startswith("+") and v[1:].isdigit() and len(v) > 7:
                raise ValueError(
                    f"audit_service.record_audit_event: raw phone detected in metadata. "
                    f"Use hash_phone() instead. Offending value: {v[:4]}***"
                )

    event = models.AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        correlation_id=correlation_id,
        metadata_json=json.dumps(metadata) if metadata else None,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    db.flush()  # get ID without committing; caller owns the transaction
    logger.info(
        "AuditEvent recorded",
        extra={
            "audit_action": action,
            "actor_user_id": actor_user_id,
            "target_type": target_type,
            "correlation_id": correlation_id,
        },
    )
    return event
