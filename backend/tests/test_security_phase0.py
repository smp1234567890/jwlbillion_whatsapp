import pytest
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from fastapi import status
import models
import config
import auth


def make_hmac_headers(payload: dict) -> tuple[bytes, dict]:
    raw_body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(
        b"test-store-webhook-secret", raw_body, hashlib.sha256
    ).hexdigest()
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature}
    return raw_body, headers


def test_webhook_hmac_only_enforcement(client, auth_headers):
    """
    H-01 / P0: Public store webhooks must strictly accept only HMAC-SHA256 signatures.
    Bearer JWTs, X-API-Key, and missing signatures must be rejected with 404 (stealth mode).
    """
    payload = {
        "cart_token": "cart_sec_phase0",
        "customer_phone": "+919876543299",
        "cart_value": 500.0,
        "items": []
    }

    # 1. Missing signature -> 401
    res_no_sig = client.post("/api/webhooks/cart-event", json=payload)
    assert res_no_sig.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Invalid Bearer Token -> 401
    res_bad_bearer = client.post("/api/webhooks/cart-event", json=payload, headers={"Authorization": "Bearer invalid_token"})
    assert res_bad_bearer.status_code == status.HTTP_401_UNAUTHORIZED

    # 3. Valid Bearer JWT -> 202 Accepted
    res_bearer = client.post("/api/webhooks/cart-event", json=payload, headers=auth_headers)
    assert res_bearer.status_code == status.HTTP_202_ACCEPTED

    # 4. Valid HMAC -> 202 Accepted
    raw_body, headers = make_hmac_headers(payload)
    res_hmac = client.post("/api/webhooks/cart-event", content=raw_body, headers=headers)
    assert res_hmac.status_code == status.HTTP_202_ACCEPTED


def test_external_data_sources_api_key_redacted_and_role_scoped(client, auth_headers, db):
    """
    H-02 / P0: GET /api/external-data-sources must not return plaintext api_key.
    Only has_api_key (boolean) is returned. Non-admin/manager accounts are rejected.
    """
    # Create test source
    src = models.ExternalDataSource(
        name="Store Customer Lookup API",
        endpoint_url="https://api.jwl-billion.com/customers",
        auth_method="api_key",
        api_key="super_secret_crm_token_9999",
        header_name="X-Store-Token",
        lookup_param="phone",
        is_active=True
    )
    db.add(src)
    db.commit()

    # List sources as admin
    res = client.get("/api/external-data-sources", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert isinstance(data, list)
    target = next((item for item in data if item["id"] == src.id), None)
    assert target is not None
    assert "api_key" not in target  # Sensitive API key completely omitted
    assert target["has_api_key"] is True

    # Test that normal agent cannot access external data sources
    agent_user = db.query(models.User).filter(models.User.username == "support_agent_test").first()
    if not agent_user:
        agent_user = models.User(
            username="support_agent_test",
            email="support_agent@example.com",
            hashed_password=auth.get_password_hash("AgentPass123!"),
            role="agent",
            is_active=True
        )
        db.add(agent_user)
        db.commit()

    agent_token = auth.create_access_token(data={"sub": "support_agent_test", "role": "agent"})
    res_agent = client.get("/api/external-data-sources", headers={"Authorization": f"Bearer {agent_token}"})
    assert res_agent.status_code == status.HTTP_403_FORBIDDEN



def test_ssrf_mitigation_blocks_internal_and_insecure_urls(client, auth_headers):
    """
    H-03 / P0: External data sources must require HTTPS and strictly reject
    loopback (127.0.0.1), link-local, cloud metadata (169.254.169.254), and private IPs.
    """
    # 1. Reject plain HTTP
    res_http = client.post("/api/external-data-sources", json={
        "name": "Insecure HTTP",
        "endpoint_url": "http://api.example.com/customers"
    }, headers=auth_headers)
    assert res_http.status_code == status.HTTP_400_BAD_REQUEST
    assert "HTTPS" in res_http.json()["detail"]

    # 2. Reject Loopback IP
    res_loopback = client.post("/api/external-data-sources", json={
        "name": "Loopback Attack",
        "endpoint_url": "https://127.0.0.1/api/v1"
    }, headers=auth_headers)
    assert res_loopback.status_code == status.HTTP_400_BAD_REQUEST

    # 3. Reject Cloud Metadata IP
    res_meta = client.post("/api/external-data-sources", json={
        "name": "Cloud Metadata Exfil",
        "endpoint_url": "https://169.254.169.254/latest/meta-data"
    }, headers=auth_headers)
    assert res_meta.status_code == status.HTTP_400_BAD_REQUEST

    # 4. Reject Private Subnet IP
    res_private = client.post("/api/external-data-sources", json={
        "name": "Private Lan Probe",
        "endpoint_url": "https://192.168.1.100/internal"
    }, headers=auth_headers)
    assert res_private.status_code == status.HTTP_400_BAD_REQUEST


def test_chat_blocks_opted_out_recipients(client, auth_headers, db):
    """
    H-04 / P0: Manual chat send must reject messaging recipients who are on the DND/Opt-Out list.
    """
    opt_phone = "+919988776655"
    db.query(models.OptOut).filter(models.OptOut.phone == opt_phone).delete()
    db.add(models.OptOut(phone=opt_phone, reason="USER_REQUEST"))
    db.commit()

    # Attempt to send chat message
    res = client.post("/api/chat/send", json={
        "customer_phone": opt_phone,
        "text": "Hello, we have fresh fafda ready for you!"
    }, headers=auth_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "opted out" in res.json()["detail"].lower()


def test_chat_service_window_enforcement_in_production(client, auth_headers, db, monkeypatch):
    """
    H-04 / P0: When live WhatsApp credentials are configured, free-text chat replies
    are restricted to Meta's 24-hour customer service window.
    """
    test_phone = "+919777788889"
    # Ensure recipient is not on DND
    db.query(models.OptOut).filter(models.OptOut.phone == test_phone).delete()
    # Ensure no recent inbound messages from this customer
    db.query(models.ChatMessage).filter(models.ChatMessage.customer_phone == test_phone).delete()
    db.commit()

    # Simulate production environment with live WhatsApp credentials
    monkeypatch.setattr(config, "WHATSAPP_API_TOKEN", "EAAtest_live_token")
    monkeypatch.setattr(config, "WHATSAPP_PHONE_NUMBER_ID", "123456789012345")

    # Send message without any prior customer message -> must be rejected
    res = client.post("/api/chat/send", json={
        "customer_phone": test_phone,
        "text": "Checking in on your snack preferences"
    }, headers=auth_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "24-hour" in res.json()["detail"].lower()

    # Now simulate customer sending an inbound message 1 hour ago
    inbound_msg = models.ChatMessage(
        customer_phone=test_phone,
        sender_type="CUSTOMER",
        message_type="text",
        text="What are your store hours today?",
        created_at=datetime.utcnow() - timedelta(hours=1),
        is_read=True
    )
    db.add(inbound_msg)
    db.commit()

    # Message within 24h should now pass the window validation
    # (Mock send_whatsapp_free_text so we don't make real external Meta HTTP calls)
    monkeypatch.setattr("routers.chat.send_whatsapp_free_text", lambda phone, text: {"status": "success", "message_id": "wamid.123"})
    res_within_window = client.post("/api/chat/send", json={
        "customer_phone": test_phone,
        "text": "We are open from 8 AM to 9 PM daily!"
    }, headers=auth_headers)
    assert res_within_window.status_code == status.HTTP_200_OK
    assert res_within_window.json()["sender_type"] == "AGENT"
