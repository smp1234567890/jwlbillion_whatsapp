import pytest
from datetime import datetime, timedelta, timezone
from fastapi import status
import models

def test_unauthenticated_api_call_returns_401(client):
    """
    Test that webhook calls without valid signature return 401 (Unauthorized)
    per WP1 security specification.
    """
    res = client.post("/api/webhooks/cart-event", json={"cart_token": "abc", "customer_phone": "123"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    res_invalid_auth = client.post(
        "/api/webhooks/cart-event",
        json={"cart_token": "abc", "customer_phone": "123"},
        headers={"Authorization": "Bearer invalid-or-garbage-token"}
    )
    assert res_invalid_auth.status_code == status.HTTP_401_UNAUTHORIZED

    res_order = client.post("/api/webhooks/order-completed", json={"cart_token": "abc"})
    assert res_order.status_code == status.HTTP_401_UNAUTHORIZED


def test_logs_download_csv_and_json(client, auth_headers, db):
    """
    Test downloading message logs in CSV and JSON formats.
    """
    # Seed a log entry
    log_entry = models.MessageLog(
        recipient_phone="+919999988888",
        template_name="test_template",
        meta_message_id="wamid.HBgLMTIzNDU2",
        status="DELIVERED",
        sender_user="admin",
        created_at=datetime.now(timezone.utc)
    )
    db.add(log_entry)
    db.commit()

    # Test JSON download with admin step-up auth
    res_json = client.get("/api/message-logs/download?format=json&password=SecretPassword123!&reason=ComplianceAudit", headers=auth_headers)
    assert res_json.status_code == status.HTTP_200_OK
    assert res_json.headers["content-type"] == "application/json"
    json_data = res_json.json()
    assert isinstance(json_data, list)
    assert any(item.get("recipient_phone") == "+919999988888" and item.get("sender_user") == "admin" for item in json_data)

    # Test CSV download with admin step-up auth
    res_csv = client.get("/api/message-logs/download?format=csv&password=SecretPassword123!&reason=ComplianceAudit", headers=auth_headers)
    assert res_csv.status_code == status.HTTP_200_OK
    assert "text/csv" in res_csv.headers["content-type"]
    assert "+919999988888" in res_csv.text
    assert "admin" in res_csv.text



def test_logs_retention_deletion(client, auth_headers, db):
    """
    Test deleting logs older than specified days (e.g., 90, 120, 175) or deleting all.
    """
    now = datetime.now(timezone.utc)

    # Seed an old log (100 days old) and a fresh log (2 days old)
    old_log = models.MessageLog(
        recipient_phone="+911111111111",
        template_name="old_promo",
        meta_message_id="wamid.old1",
        status="SENT",
        sender_user="testuser",
        created_at=now - timedelta(days=100)
    )
    fresh_log = models.MessageLog(
        recipient_phone="+912222222222",
        template_name="new_promo",
        meta_message_id="wamid.fresh1",
        status="SENT",
        sender_user="testuser",
        created_at=now - timedelta(days=2)
    )
    db.add_all([old_log, fresh_log])
    db.commit()

    # Delete logs older than 90 days
    res_del_90 = client.delete("/api/message-logs?older_than_days=90", headers=auth_headers)
    assert res_del_90.status_code == status.HTTP_200_OK
    del_data = res_del_90.json()
    assert del_data["deleted_count"] >= 1

    # Verify old log is gone but fresh log remains
    assert db.query(models.MessageLog).filter(models.MessageLog.recipient_phone == "+911111111111").first() is None
    assert db.query(models.MessageLog).filter(models.MessageLog.recipient_phone == "+912222222222").first() is not None

    # Delete all remaining logs
    res_del_all = client.delete("/api/message-logs", headers=auth_headers)
    assert res_del_all.status_code == status.HTTP_200_OK
    assert db.query(models.MessageLog).filter(models.MessageLog.recipient_phone == "+912222222222").first() is None
