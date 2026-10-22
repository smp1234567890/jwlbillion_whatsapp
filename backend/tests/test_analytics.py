import pytest
from datetime import datetime, timedelta
import models
from fastapi import status


def test_analytics_overview_unauthorized(client):
    res = client.get("/api/analytics/overview")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_analytics_overview_empty(client, auth_headers, db):
    # Ensure empty DB returns safe zeroed metrics
    res = client.get("/api/analytics/overview?time_range=30d", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["time_range"] == "30d"
    assert data["funnel"]["total_sent"] >= 0
    assert data["rates"]["delivery_rate"] >= 0.0
    assert data["meta_health"]["quality_rating"] in ("HIGH", "MEDIUM", "LOW")
    assert isinstance(data["template_performance"], list)
    assert isinstance(data["daily_trends"], list)


def test_analytics_overview_calculations(client, auth_headers, db):
    now = datetime.utcnow()

    # Create message logs
    log1 = models.MessageLog(
        recipient_phone="+919999000001",
        template_name="cart_reminder_discount_v1",
        status="READ",
        created_at=now - timedelta(hours=2)
    )
    log2 = models.MessageLog(
        recipient_phone="+919999000002",
        template_name="cart_reminder_discount_v1",
        status="DELIVERED",
        created_at=now - timedelta(hours=3)
    )
    log3 = models.MessageLog(
        recipient_phone="+919999000003",
        template_name="festival_offer_v1",
        status="FAILED",
        created_at=now - timedelta(hours=4)
    )
    db.add_all([log1, log2, log3])

    # Inbound replies & button clicks
    chat1 = models.ChatMessage(
        customer_phone="+919999000001",
        sender_type="CUSTOMER",
        text="Clicked: [YES - Send 10% Discount Code]",
        message_type="button",
        created_at=now - timedelta(hours=1)
    )
    db.add(chat1)

    # Cart recovery
    cart1 = models.CartEvent(
        cart_token="token_analytics_123",
        customer_phone="+919999000001",
        cart_value=850.0,
        status="RECOVERED",
        created_at=now - timedelta(hours=5)
    )
    db.add(cart1)
    db.commit()

    # Fetch 7d analytics
    res = client.get("/api/analytics/overview?time_range=7d", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["time_range"] == "7d"
    assert data["funnel"]["total_sent"] >= 2
    assert data["funnel"]["total_delivered"] >= 2
    assert data["funnel"]["total_read"] >= 1
    assert data["funnel"]["total_failed"] >= 1
    assert data["funnel"]["total_replied"] >= 1
    assert data["funnel"]["total_clicks"] >= 1
    assert data["funnel"]["recovered_carts"] >= 1
    assert data["funnel"]["revenue_recovered"] >= 850.0

    # Rates
    assert data["rates"]["delivery_rate"] > 0
    assert data["rates"]["read_rate"] > 0
    assert data["rates"]["click_rate"] > 0

    # Check template breakdown has cart_reminder_discount_v1
    tmpl_names = [t["template_name"] for t in data["template_performance"]]
    assert "cart_reminder_discount_v1" in tmpl_names


def test_analytics_customer_reply_counted_as_read(client, auth_headers, db):
    now = datetime.utcnow()
    phone = "+919876543299"

    # Outbound log is only DELIVERED
    log = models.MessageLog(
        recipient_phone=phone,
        template_name="reengagement_test_reply",
        status="DELIVERED",
        created_at=now - timedelta(minutes=5)
    )
    db.add(log)

    # Customer replies back
    reply = models.ChatMessage(
        customer_phone=phone,
        sender_type="CUSTOMER",
        text="Yes I want this offer!",
        created_at=now - timedelta(minutes=2)
    )
    db.add(reply)
    db.commit()

    res = client.get("/api/analytics/overview?time_range=today", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    # The customer reply should be reflected in read count & read rate
    assert data["funnel"]["total_read"] >= 1
    assert data["funnel"]["total_replied"] >= 1
    assert data["rates"]["read_rate"] > 0
