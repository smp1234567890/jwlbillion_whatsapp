import hashlib
import hmac
import json
import pytest
from fastapi import status
import config
import models

def test_customer_sync_unauthorized(client):
    res = client.post("/api/webhooks/customer-created", json={"phone": "+919876500001", "name": "Test"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

def test_customer_sync_api_key_header(client, db):
    phone = "+919876500002"
    db.query(models.Contact).filter(models.Contact.phone == phone).delete()
    db.commit()

    headers = {"X-API-Key": config.WEBHOOK_SECRET}
    payload = {
        "phone": "9876500002",
        "name": "Arjun Patel",
        "email": "arjun@example.com",
        "city": "Ahmedabad",
        "tags": "VIP, Namkeen",
        "total_orders": 3,
        "gstin": "24ABCDE1234F1Z5",
        "loyalty_tier": "Gold",
        "fav_item": "Diamond Ring"
    }

    res = client.post("/api/webhooks/customer-created", json=payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "success"
    assert data["action"] == "created"
    assert data["contact"]["phone"] == phone
    assert data["contact"]["name"] == "Arjun Patel"
    assert data["contact"]["city"] == "Ahmedabad"
    assert data["contact"]["total_orders"] == 3
    # Verify custom attributes persisted
    custom_attrs = data["contact"]["custom_attributes"]
    assert custom_attrs["gstin"] == "24ABCDE1234F1Z5"
    assert custom_attrs["loyalty_tier"] == "Gold"
    assert custom_attrs["fav_item"] == "Diamond Ring"

    # Verify in DB
    contact_db = db.query(models.Contact).filter(models.Contact.phone == phone).first()
    assert contact_db is not None
    assert contact_db.custom_attributes.get("loyalty_tier") == "Gold"

def test_customer_sync_upsert_merge(client, db):
    phone = "+919876500003"
    db.query(models.Contact).filter(models.Contact.phone == phone).delete()
    db.commit()

    headers = {"X-API-Key": config.WEBHOOK_SECRET}
    # Initial create
    res1 = client.post("/api/contacts/sync", json={
        "phone": phone,
        "first_name": "Priya",
        "last_name": "Shah",
        "city": "Surat",
        "tags": "Retail",
        "membership_id": "MEM100"
    }, headers=headers)
    assert res1.status_code == status.HTTP_200_OK
    assert res1.json()["action"] == "created"
    assert res1.json()["contact"]["name"] == "Priya Shah"
    assert res1.json()["contact"]["custom_attributes"]["membership_id"] == "MEM100"

    # Subsequent sync update
    res2 = client.post("/api/contacts/sync", json={
        "phone": phone,
        "email": "priya@example.com",
        "tags": "VIP",
        "total_orders": 5,
        "store_credit": 250
    }, headers=headers)
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["action"] == "updated"
    contact_data = res2.json()["contact"]
    assert contact_data["name"] == "Priya Shah"  # Preserved
    assert contact_data["email"] == "priya@example.com"
    assert contact_data["total_orders"] == 5
    assert "Retail" in contact_data["tags"] and "VIP" in contact_data["tags"]  # Tags merged
    # Custom attributes merged
    assert contact_data["custom_attributes"]["membership_id"] == "MEM100"
    assert contact_data["custom_attributes"]["store_credit"] == 250

def test_customer_sync_hmac_auth(client, db):
    phone = "+919876500004"
    db.query(models.Contact).filter(models.Contact.phone == phone).delete()
    db.commit()

    payload = {"phone": phone, "name": "HMAC User"}
    body_bytes = json.dumps(payload).encode()
    signature = hmac.new(config.WEBHOOK_SECRET.encode(), body_bytes, hashlib.sha256).hexdigest()

    res = client.post(
        "/api/webhooks/customer-created",
        data=body_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"}
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["contact"]["phone"] == phone

def test_customer_sync_query_param_auth(client, db):
    phone = "+919876500005"
    db.query(models.Contact).filter(models.Contact.phone == phone).delete()
    db.commit()

    res = client.post(
        f"/api/webhooks/customer-created?api_key={config.WEBHOOK_SECRET}",
        json={"phone": phone, "name": "Query Param User"}
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["contact"]["name"] == "Query Param User"

def test_customer_sync_missing_phone(client):
    headers = {"X-API-Key": config.WEBHOOK_SECRET}
    res = client.post("/api/webhooks/customer-created", json={"name": "No Phone"}, headers=headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
