"""
Policy Service
Centralized outbound message authorization, consent ledger management,
and compliance guardrails (DND, Quiet Hours, 24-Hour Customer Window, Daily Limits).
"""

from datetime import datetime, timedelta
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session

import config
import models
from services.phone_service import normalize_phone, InvalidPhoneNumberError

logger = logging.getLogger("policy_service")

FIXED_DAILY_LIMIT = 200

# Transactional templates exempt from promotional quiet hours
TRANSACTIONAL_TEMPLATES = {
    "cart_recovery_reminder",
    "milestone_reward_offer",
    "order_confirmation",
    "shipping_update",
    "account_alert"
}


def is_quiet_hours(now_utc: Optional[datetime] = None) -> bool:
    """
    Checks if current time falls within TRAI / Consumer quiet hours:
    21:00 (9 PM) to 09:00 (9 AM) Indian Standard Time (IST = UTC + 5:30).
    """
    if now_utc is None:
        now_utc = datetime.utcnow()
    ist_time = now_utc + timedelta(hours=5, minutes=30)
    hour = ist_time.hour
    return hour >= 21 or hour < 9


def is_quiet_hours_enabled(db: Optional[Session] = None) -> bool:
    """
    Checks if Quiet Hours enforcement is turned on in SystemSettings.
    Can be toggled via Settings UI. Defaults to True if no setting record is found.
    """
    if db is None:
        return True
    try:
        setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "quiet_hours_enabled").first()
        if setting is not None:
            return str(setting.value).strip().lower() in ["true", "1", "yes", "on"]
    except Exception:
        pass
    return True


def record_consent(
    db: Session,
    phone: str,
    source: str = "store_checkout",
    proof_details: Optional[str] = None
) -> models.ConsentRecord:
    """
    Records or updates affirmative customer consent in the Consent Ledger.
    """
    clean_phone = normalize_phone(phone)
    active_record = (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.phone == clean_phone, models.ConsentRecord.status == "ACTIVE")
        .first()
    )
    if active_record:
        active_record.source = source or active_record.source
        active_record.proof_details = proof_details or active_record.proof_details
        active_record.consent_timestamp = datetime.utcnow()
        db.flush()
        return active_record

    record = models.ConsentRecord(
        phone=clean_phone,
        source=source,
        status="ACTIVE",
        proof_details=proof_details,
        consent_timestamp=datetime.utcnow()
    )
    db.add(record)
    db.flush()
    return record


def revoke_consent(
    db: Session,
    phone: str,
    reason: str = "OPT_OUT"
) -> None:
    """
    Revokes customer consent across the Consent Ledger and ensures an entry in opt_outs.
    """
    try:
        clean_phone = normalize_phone(phone)
    except InvalidPhoneNumberError:
        clean_phone = phone.strip()

    # Update active consent records to REVOKED
    active_records = (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.phone == clean_phone, models.ConsentRecord.status == "ACTIVE")
        .all()
    )
    now = datetime.utcnow()
    for rec in active_records:
        rec.status = "REVOKED"
        rec.revoked_at = now

    if not active_records:
        existing_revoked = db.query(models.ConsentRecord).filter(
            models.ConsentRecord.phone == clean_phone,
            models.ConsentRecord.status == "REVOKED"
        ).first()
        if not existing_revoked:
            db.add(models.ConsentRecord(
                phone=clean_phone,
                status="REVOKED",
                source=reason[:50] if reason else "OPT_OUT",
                proof_details=reason,
                revoked_at=now
            ))

    # Ensure phone is in opt_outs table
    opt_out = db.query(models.OptOut).filter(models.OptOut.phone == clean_phone).first()
    if not opt_out:
        db.add(models.OptOut(phone=clean_phone, reason=reason))

    db.flush()
    logger.info(f"🛑 [Consent Revoked] Phone {clean_phone} revoked: {reason}")


def has_active_consent(db: Session, phone: str) -> bool:
    """
    Returns True if recipient has active consent and is not opted out.
    """
    try:
        clean_phone = normalize_phone(phone)
    except InvalidPhoneNumberError:
        return False

    is_opted_out = db.query(models.OptOut).filter(models.OptOut.phone == clean_phone).first()
    if is_opted_out:
        return False

    has_active = (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.phone == clean_phone, models.ConsentRecord.status == "ACTIVE")
        .first()
    )
    return bool(has_active)


def get_next_quiet_hours_end_utc(now_utc: Optional[datetime] = None) -> datetime:
    """
    Returns the next datetime (in UTC) when quiet hours end (09:00:00 IST).
    Quiet hours: 21:00 to 09:00 IST.
    """
    if now_utc is None:
        now_utc = datetime.utcnow()
    # Convert now_utc to IST
    ist_time = now_utc + timedelta(hours=5, minutes=30)
    # Target 09:00:00 IST
    if ist_time.hour >= 21:
        # After 9 PM IST -> 9 AM IST tomorrow
        target_ist = (ist_time + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        # Before 9 AM IST -> 9 AM IST today
        target_ist = ist_time.replace(hour=9, minute=0, second=0, microsecond=0)
    # Convert back from IST to UTC (subtract 5h 30m)
    return target_ist - timedelta(hours=5, minutes=30)


def authorize_outbound_message(
    db: Session,
    recipient_phone: str,
    message_type: str = "template",  # "template", "free_text"
    purpose: str = "utility",        # "utility", "marketing", "authentication"
    template_name: Optional[str] = None,
    campaign_id: Optional[int] = None,
    sender_user: Optional[str] = "System",
    enforce_quiet_hours: bool = True
) -> Tuple[bool, str]:
    """
    Central Outbound Message Policy Bottleneck.
    Evaluates:
    1. Valid E.164 Phone format
    2. DND / Opt-Out List
    3. Consent Ledger status
    4. Meta 24-Hour Customer Service Window (for free-text chat replies)
    5. Daily Outbound Message Quota (fixed 200/day)
    6. Quiet Hours (21:00 - 09:00 IST) for promotional/campaign broadcasts
       (Transactional/Utility messages like cart recovery or order confirmation are exempt)

    Returns (is_authorized, reason)
    """
    # 1. Phone validation
    try:
        clean_phone = normalize_phone(recipient_phone)
    except InvalidPhoneNumberError as e:
        return False, f"Invalid recipient phone: {e}"

    # 2. Strict DND / Opt-Out Check
    is_opted_out = db.query(models.OptOut).filter(models.OptOut.phone == clean_phone).first()
    if is_opted_out:
        return False, "Customer opted out / on DND list"

    # 3. Consent check
    # Check if consent was explicitly revoked
    revoked_consent = (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.phone == clean_phone, models.ConsentRecord.status == "REVOKED")
        .order_by(models.ConsentRecord.id.desc())
        .first()
    )
    active_consent = (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.phone == clean_phone, models.ConsentRecord.status == "ACTIVE")
        .order_by(models.ConsentRecord.id.desc())
        .first()
    )
    if revoked_consent and (not active_consent or revoked_consent.id > active_consent.id):
        return False, "Customer consent revoked"

    # For promotional campaign broadcasts, active consent is MANDATORY (deny-by-default).
    # A contact record without explicit ACTIVE consent is NOT sufficient.
    if campaign_id is not None or purpose == "marketing":
        if not active_consent:
            return False, "No active marketing consent on file for campaign recipient — send denied"

    # 4. Meta 24-Hour Customer Service Window (for free_text / agent chat)
    if message_type == "free_text":
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        last_inbound_msg = (
            db.query(models.ChatMessage)
            .filter(
                models.ChatMessage.customer_phone == clean_phone,
                models.ChatMessage.sender_type == "CUSTOMER",
                models.ChatMessage.created_at >= twenty_four_hours_ago
            )
            .first()
        )
        if config.WHATSAPP_API_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID and not last_inbound_msg:
            return False, "Outside Meta's 24-hour customer service window"

    # 5. Fixed Daily Outbound Send Limit (Max 200/day hard budget ceiling)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    current_count = (
        db.query(models.MessageLog)
        .filter(
            models.MessageLog.created_at >= today_start,
            models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED", "READ"])
        )
        .count()
    )
    import whatsapp_service
    effective_limit = min(FIXED_DAILY_LIMIT, getattr(whatsapp_service, "DAILY_MESSAGE_SEND_LIMIT", FIXED_DAILY_LIMIT))
    if current_count >= effective_limit:
        return False, f"Daily budget ceiling reached ({current_count}/{effective_limit} messages sent today)."

    # 6. Quiet Hours Enforcement (21:00 - 09:00 IST)
    # Broadcast campaigns and promotional marketing templates are held during quiet hours.
    # Utility messages (cart recovery, order status, workflow journey triggers) are exempt.
    is_marketing = purpose == "marketing" or campaign_id is not None
    is_promotional = is_marketing or (template_name and template_name not in TRANSACTIONAL_TEMPLATES and purpose != "utility")
    if enforce_quiet_hours and is_quiet_hours_enabled(db) and is_promotional and is_quiet_hours():
        return False, "Promotional message blocked: Quiet hours in effect (21:00 - 09:00 IST)"

    return True, "Authorized"



def authorize_and_create_outbound(
    db: Session,
    recipient_phone: str,
    idempotency_key: str,
    message_kind: str = "template",
    purpose: str = "utility",
    template_name: Optional[str] = None,
    campaign_id: Optional[int] = None,
    workflow_session_id: Optional[int] = None,
    created_by_user_id: Optional[int] = None,
    service_actor: Optional[str] = "System",
    correlation_id: Optional[str] = None,
    enforce_quiet_hours: bool = True
) -> Tuple[bool, Optional[models.OutboundMessage], str]:
    """
    WP2: Atomic Policy Gate and Durable OutboundMessage Creator.
    1. Validates and normalizes phone.
    2. Enforces idempotency — checks if an OutboundMessage already exists for this key.
    3. Runs authorize_outbound_message.
    4. Persists an OutboundMessage record and an immutable AuditEvent row.
    5. Returns (is_authorized, outbound_message, reason).
    """
    from services.audit_service import record_audit_event, hash_phone
    from sqlalchemy.exc import IntegrityError

    try:
        clean_phone = normalize_phone(recipient_phone)
    except InvalidPhoneNumberError as e:
        return False, None, f"Invalid recipient phone: {e}"

    existing = db.query(models.OutboundMessage).filter(
        models.OutboundMessage.idempotency_key == idempotency_key
    ).first()
    if existing:
        is_ok = existing.policy_decision == "authorized" and existing.status in ("PENDING", "SENT")
        return is_ok, existing, "Duplicate idempotency_key"

    is_auth, reason = authorize_outbound_message(
        db=db,
        recipient_phone=clean_phone,
        message_type=message_kind,
        purpose=purpose,
        template_name=template_name,
        campaign_id=campaign_id,
        sender_user=service_actor,
        enforce_quiet_hours=enforce_quiet_hours
    )

    outbound = models.OutboundMessage(
        idempotency_key=idempotency_key,
        recipient_phone_e164=clean_phone,
        recipient_hash=hash_phone(clean_phone),
        message_kind=message_kind,
        purpose=purpose,
        template_name=template_name,
        campaign_id=campaign_id,
        workflow_session_id=workflow_session_id,
        created_by_user_id=created_by_user_id,
        service_actor=service_actor,
        policy_decision="authorized" if is_auth else "denied",
        policy_reason=reason,
        status="PENDING" if is_auth else "SKIPPED",
        correlation_id=correlation_id
    )
    db.add(outbound)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(models.OutboundMessage).filter(
            models.OutboundMessage.idempotency_key == idempotency_key
        ).first()
        is_ok = existing.policy_decision == "authorized" and existing.status in ("PENDING", "SENT") if existing else False
        return is_ok, existing, "Concurrent duplicate idempotency_key"

    try:
        record_audit_event(
            db=db,
            action="outbound_message_authorized" if is_auth else "outbound_message_denied",
            actor_user_id=created_by_user_id,
            target_type="outbound_message",
            target_id=str(outbound.id),
            correlation_id=correlation_id,
            metadata={
                "purpose": purpose,
                "message_kind": message_kind,
                "decision": "authorized" if is_auth else "denied",
                "reason": reason
            }
        )
    except Exception as audit_err:
        logger.warning(f"Could not record audit event for outbound message: {audit_err}")

    return is_auth, outbound, reason
