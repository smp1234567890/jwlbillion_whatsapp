import pytest
from datetime import datetime, timedelta
import models
import config
from services.policy_service import (
    record_consent,
    revoke_consent,
    has_active_consent,
    is_quiet_hours,
    authorize_outbound_message,
    FIXED_DAILY_LIMIT
)
from whatsapp_service import send_whatsapp_template, send_whatsapp_free_text


def test_consent_record_lifecycle(db):
    import random
    suffix = random.randint(1000000, 9999999)
    test_phone = f"987{suffix}"
    norm_phone = f"+91987{suffix}"

    # 1. Record consent
    rec = record_consent(db, test_phone, source="store_checkout", proof_details="cart:123")
    db.commit()
    assert rec.phone == norm_phone
    assert rec.status == "ACTIVE"
    assert has_active_consent(db, test_phone) is True

    # 2. Revoke consent
    revoke_consent(db, test_phone, reason="USER_UNSUBSCRIBE")
    db.commit()
    assert has_active_consent(db, test_phone) is False

    # Check OptOut was created
    opt_out = db.query(models.OptOut).filter(models.OptOut.phone == norm_phone).first()
    assert opt_out is not None


def test_authorize_outbound_dnd_and_revoked_consent(db):
    test_phone = "+919876500001"
    
    # Pre-add to DND
    db.add(models.OptOut(phone=test_phone, reason="TEST_DND"))
    db.commit()

    is_auth, reason = authorize_outbound_message(db, test_phone, message_type="template")
    assert is_auth is False
    assert "DND" in reason or "opted out" in reason


def test_authorize_outbound_invalid_phone(db):
    is_auth, reason = authorize_outbound_message(db, "not-a-phone-123", message_type="template")
    assert is_auth is False
    assert "Invalid recipient phone" in reason


def test_authorize_outbound_24h_window(db, monkeypatch):
    test_phone = "+919876500002"
    # Ensure live creds are mocked
    monkeypatch.setattr(config, "WHATSAPP_API_TOKEN", "live_token")
    monkeypatch.setattr(config, "WHATSAPP_PHONE_NUMBER_ID", "123456789")

    # Clean previous messages
    db.query(models.ChatMessage).filter(models.ChatMessage.customer_phone == test_phone).delete()
    db.commit()

    # Free text without customer inbound message -> blocked
    is_auth, reason = authorize_outbound_message(db, test_phone, message_type="free_text")
    assert is_auth is False
    assert "24-hour" in reason

    # Simulate inbound customer message 2 hours ago
    db.add(models.ChatMessage(
        customer_phone=test_phone,
        sender_type="CUSTOMER",
        message_type="text",
        text="Hello!",
        created_at=datetime.utcnow() - timedelta(hours=2)
    ))
    db.commit()

    is_auth2, reason2 = authorize_outbound_message(db, test_phone, message_type="free_text")
    assert is_auth2 is True
    assert reason2 == "Authorized"


def test_authorize_outbound_daily_quota_limit(db):
    test_phone = "+919876500003"
    # Seed 200 messages today
    today_now = datetime.utcnow()
    logs = [
        models.MessageLog(
            recipient_phone=f"+9198765{i:05d}",
            template_name="sample",
            status="SENT",
            created_at=today_now
        )
        for i in range(200)
    ]
    db.add_all(logs)
    db.commit()

    try:
        is_auth, reason = authorize_outbound_message(db, test_phone, message_type="template")
        assert is_auth is False
        assert "Daily budget ceiling reached" in reason or "Daily outbound send limit" in reason
    finally:
        # Clean up seeded logs so other tests have a clean budget
        db.query(models.MessageLog).filter(models.MessageLog.template_name == "sample").delete()
        db.commit()


def test_authorize_outbound_quiet_hours_promotional_vs_transactional(db, monkeypatch):
    test_phone = "+919876500004"
    # Record active consent
    record_consent(db, test_phone, source="store_checkout")
    db.commit()

    # Mock quiet hours to return True (e.g. 23:00 IST / 17:30 UTC)
    quiet_utc = datetime(2026, 9, 20, 17, 30, 0)
    assert is_quiet_hours(quiet_utc) is True

    monkeypatch.setattr("services.policy_service.is_quiet_hours", lambda now_utc=None: True)

    # Promotional campaign message during quiet hours -> blocked
    is_auth_promo, reason_promo = authorize_outbound_message(
        db, test_phone, message_type="template", campaign_id=1, enforce_quiet_hours=True
    )
    assert is_auth_promo is False
    assert "Quiet hours" in reason_promo

    # Transactional cart recovery template during quiet hours -> authorized
    is_auth_trans, reason_trans = authorize_outbound_message(
        db, test_phone, message_type="template", template_name="cart_recovery_reminder", enforce_quiet_hours=True
    )
    assert is_auth_trans is True
    assert reason_trans == "Authorized"


def test_whatsapp_service_bottleneck_enforcement(db):
    test_phone = "+919876500005"
    # Add to DND
    db.add(models.OptOut(phone=test_phone, reason="DND_BOTTLENECK"))
    db.commit()

    # Attempt template send via whatsapp_service
    res = send_whatsapp_template(
        recipient_phone=test_phone,
        template_name="cart_recovery_reminder"
    )
    assert res["status"] == "blocked"
    assert "DND" in res["reason"] or "opted out" in res["reason"]

    # Verify failed message was recorded in MessageLog
    failed_log = db.query(models.MessageLog).filter(
        models.MessageLog.recipient_phone == test_phone
    ).first()
    assert failed_log is not None
    assert failed_log.status == "FAILED"
