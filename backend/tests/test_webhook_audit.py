import pytest
import uuid
import hashlib
import hmac
import json
from fastapi import status
import models
import config

def make_hmac_headers(payload: dict, secret: str = "test-store-webhook-secret") -> tuple[bytes, dict]:
    raw_body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(
        secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature}
    return raw_body, headers


def test_webhook_audit_missing_signature_returns_401(client, db):
    payload = {
        "cart_token": f"audit_no_sig_{uuid.uuid4().hex[:8]}",
        "customer_phone": "9876543210",
        "cart_value": 350.0
    }
    correlation_id = f"corr-{uuid.uuid4().hex[:8]}"
    res = client.post(
        "/api/webhooks/cart-event",
        json=payload,
        headers={"X-Correlation-ID": correlation_id}
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Verify WebhookEvent audit record
    failed_event = db.query(models.WebhookEvent).filter(
        models.WebhookEvent.correlation_id == correlation_id
    ).first()
    assert failed_event is not None
    assert failed_event.source == "store"
    assert failed_event.hmac_validated is False
    assert failed_event.event_type == "store_auth_failure"


def test_webhook_audit_bad_signature_returns_401(client, db):
    payload = {
        "cart_token": f"audit_bad_sig_{uuid.uuid4().hex[:8]}",
        "customer_phone": "9876543210",
        "cart_value": 350.0
    }
    correlation_id = f"corr-{uuid.uuid4().hex[:8]}"
    raw_body, headers = make_hmac_headers(payload, secret="wrong-secret-12345")
    headers["X-Correlation-ID"] = correlation_id
    
    res = client.post(
        "/api/webhooks/cart-event",
        content=raw_body,
        headers=headers
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    failed_event = db.query(models.WebhookEvent).filter(
        models.WebhookEvent.correlation_id == correlation_id
    ).first()
    assert failed_event is not None
    assert failed_event.hmac_validated is False


def test_webhook_audit_valid_signature_creates_verified_event(client, db):
    import random
    token = f"audit_ok_{uuid.uuid4().hex[:8]}"
    suffix = random.randint(1000000, 9999999)
    test_phone = f"+91988{suffix}"
    payload = {
        "cart_token": token,
        "customer_phone": test_phone,
        "cart_value": 500.0,
        "items": []
    }
    correlation_id = f"corr-ok-{uuid.uuid4().hex[:8]}"
    raw_body, headers = make_hmac_headers(payload)
    headers["X-Correlation-ID"] = correlation_id

    res = client.post(
        "/api/webhooks/cart-event",
        content=raw_body,
        headers=headers
    )
    assert res.status_code == status.HTTP_202_ACCEPTED
    assert res.json()["status"] == "received"

    event = db.query(models.WebhookEvent).filter(
        models.WebhookEvent.external_event_id == token
    ).first()
    assert event is not None
    assert event.source == "store"
    assert event.hmac_validated is True
    assert event.correlation_id == correlation_id

    # Duplicate submission returns duplicate status
    res_dup = client.post(
        "/api/webhooks/cart-event",
        content=raw_body,
        headers=headers
    )
    assert res_dup.status_code == status.HTTP_202_ACCEPTED
    assert res_dup.json()["status"] == "duplicate"


def test_meta_webhook_invalid_signature_audited(client, db, monkeypatch):
    monkeypatch.setattr(config, "META_APP_SECRET", "test-meta-app-secret")
    correlation_id = f"corr-meta-{uuid.uuid4().hex[:8]}"
    
    res = client.post(
        "/api/webhooks/whatsapp",
        json={"entry": []},
        headers={
            "X-Hub-Signature-256": "sha256=invalidhash",
            "X-Correlation-ID": correlation_id
        }
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    event = db.query(models.WebhookEvent).filter(
        models.WebhookEvent.correlation_id == correlation_id
    ).first()
    assert event is not None
    assert event.source == "meta"
    assert event.hmac_validated is False
