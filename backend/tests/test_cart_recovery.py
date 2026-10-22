import pytest
import uuid
import hashlib
import hmac
import json
from fastapi import status
import models

def make_hmac_headers(payload: dict) -> tuple[bytes, dict]:
    raw_body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(
        b"test-store-webhook-secret", raw_body, hashlib.sha256
    ).hexdigest()
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature}
    return raw_body, headers


def test_cart_event_webhook(client, db):
    unique_token = f"cart_test_{uuid.uuid4().hex[:8]}"
    payload = {
        "cart_token": unique_token,
        "customer_phone": "+919876543210",
        "cart_value": 450.0,
        "items": [{"item": "Silver Bracelet", "qty": 1}]
    }
    raw_body, headers = make_hmac_headers(payload)
    res = client.post("/api/webhooks/cart-event?delay_seconds=1800", content=raw_body, headers=headers)
    assert res.status_code == status.HTTP_202_ACCEPTED
    data = res.json()
    assert data["status"] == "received"

    # Verify cart event in DB is freshly created as PENDING
    cart = db.query(models.CartEvent).filter(models.CartEvent.cart_token == unique_token).first()
    assert cart is not None
    assert cart.status == "PENDING"


def test_store_webhook_requires_valid_signature(client, auth_headers):
    payload = {
        "cart_token": f"cart_signed_{uuid.uuid4().hex[:8]}",
        "customer_phone": "+919876543211",
        "cart_value": 450.0,
        "items": []
    }
    raw_body, headers = make_hmac_headers(payload)
    accepted = client.post(
        "/api/webhooks/cart-event",
        content=raw_body,
        headers=headers,
    )
    assert accepted.status_code == status.HTTP_202_ACCEPTED

    # Calling with no auth / bad auth must return 401
    rejected_no_auth = client.post("/api/webhooks/cart-event", json=payload)
    assert rejected_no_auth.status_code == status.HTTP_401_UNAUTHORIZED

    # Calling with invalid bearer token must return 401
    rejected_bad_bearer = client.post("/api/webhooks/cart-event", json=payload, headers={"Authorization": "Bearer invalid_token_123"})
    assert rejected_bad_bearer.status_code == status.HTTP_401_UNAUTHORIZED

    # Calling with valid logged-in Bearer JWT is now accepted
    accepted_bearer = client.post("/api/webhooks/cart-event", json=payload, headers=auth_headers)
    assert accepted_bearer.status_code == status.HTTP_202_ACCEPTED


def test_order_completion_cancels_recovery(client, db):
    unique_token = f"cart_test_{uuid.uuid4().hex[:8]}"
    cart_payload = {
        "cart_token": unique_token,
        "customer_phone": "+919876543210",
        "cart_value": 300.0,
        "items": []
    }
    raw_body, headers = make_hmac_headers(cart_payload)
    # Create fresh cart
    client.post("/api/webhooks/cart-event?delay_seconds=1800", content=raw_body, headers=headers)

    # Simulate customer purchasing via HMAC-signed request
    order_url = f"/api/webhooks/order-completed?cart_token={unique_token}&customer_phone=%2B919876543210"
    order_body = b""
    order_sig = "sha256=" + hmac.new(
        b"test-store-webhook-secret", order_body, hashlib.sha256
    ).hexdigest()
    res = client.post(order_url, content=order_body, headers={"X-Hub-Signature-256": order_sig})
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "success"

    # Verify marked as RECOVERED in DB
    cart = db.query(models.CartEvent).filter(models.CartEvent.cart_token == unique_token).first()
    assert cart.status == "RECOVERED"

