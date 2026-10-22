import pytest
from fastapi import status
import models
import whatsapp_service

def test_create_and_trigger_campaign(client, auth_headers, db):
    payload = {
        "title": "Navratri Special Jewelry Fest",
        "template_name": "festive_promo_offer",
        "language": "gu",
        "target_filter": "ALL",
        "password": "SecretPassword123!"
    }
    res = client.post("/api/campaigns", json=payload, headers=auth_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["title"] == "Navratri Special Jewelry Fest"
    assert data["status"] in ["COMPLETED", "SCHEDULED", "IN_PROGRESS"]

def test_daily_budget_guardrail_cutoff(db):
    normal_phone = "+919877766655"
    db.query(models.OptOut).filter(models.OptOut.phone == normal_phone).delete()
    db.commit()

    # Get current count
    under_limit, current_count = whatsapp_service.check_daily_limit(db)
    original_limit = whatsapp_service.DAILY_MESSAGE_SEND_LIMIT

    # Set limit to current count
    whatsapp_service.DAILY_MESSAGE_SEND_LIMIT = current_count

    # Must be blocked by budget guardrail
    res = whatsapp_service.send_whatsapp_template(
        recipient_phone=normal_phone,
        template_name="festive_promo_offer",
        language="en"
    )
    assert res["status"] == "blocked"
    assert "Daily budget ceiling reached" in res["reason"]

    # Restore limit
    whatsapp_service.DAILY_MESSAGE_SEND_LIMIT = original_limit
