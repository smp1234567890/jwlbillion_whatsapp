import pytest
import hmac
import hashlib
import json
from fastapi import status
import config
import models


def post_meta_webhook(client, payload):
    raw_body = json.dumps(payload).encode("utf-8")
    secret = config.META_APP_SECRET.encode("utf-8") if config.META_APP_SECRET else b"test-meta-app-secret"
    sig = "sha256=" + hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return client.post(
        "/api/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig
        }
    )


def test_meta_webhook_hmac_enforcement(client, monkeypatch):
    monkeypatch.setattr(config, "META_APP_SECRET", "super_secret_meta_key")
    payload = {"entry": []}
    raw_body = json.dumps(payload).encode("utf-8")

    # Missing signature
    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_body,
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Invalid signature
    res_bad = client.post(
        "/api/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=invalid_hash"
        }
    )
    assert res_bad.status_code == status.HTTP_401_UNAUTHORIZED

    # Valid signature
    valid_sig = "sha256=" + hmac.new(b"super_secret_meta_key", raw_body, hashlib.sha256).hexdigest()
    res_good = client.post(
        "/api/webhooks/whatsapp",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": valid_sig
        }
    )
    assert res_good.status_code == status.HTTP_200_OK


def test_meta_message_replay_prevention(client, db):
    meta_id = "wamid.REPLAY_TEST_12345"
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": meta_id,
                                    "from": "919876543210",
                                    "type": "text",
                                    "text": {"body": "Hello JWL, do you deliver to Vadodara?"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    # First dispatch
    res1 = post_meta_webhook(client, payload)
    assert res1.status_code == status.HTTP_200_OK
    assert res1.json().get("status") in ["message_processed", "ok"]

    # Verify chat message recorded
    chat_msgs = db.query(models.ChatMessage).filter(models.ChatMessage.meta_message_id == meta_id).all()
    assert len(chat_msgs) == 1
    assert chat_msgs[0].text == "Hello JWL, do you deliver to Vadodara?"
    assert chat_msgs[0].customer_phone == "+919876543210"

    # Verify inbound webhook event recorded
    inbound_event = db.query(models.InboundWebhookEvent).filter(
        models.InboundWebhookEvent.provider == "meta",
        models.InboundWebhookEvent.provider_event_id == meta_id
    ).first()
    assert inbound_event is not None

    # Second dispatch (REPLAY)
    res2 = post_meta_webhook(client, payload)
    assert res2.status_code == status.HTTP_200_OK

    # Verify NO duplicate chat message was created
    chat_msgs_after = db.query(models.ChatMessage).filter(models.ChatMessage.meta_message_id == meta_id).all()
    assert len(chat_msgs_after) == 1


def test_meta_opt_out_replay_does_not_duplicate_consent_revocation(client, db):
    meta_id = "wamid.STOP_REPLAY_999"
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": meta_id,
                                    "from": "919876543211",
                                    "type": "text",
                                    "text": {"body": "STOP"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    res1 = post_meta_webhook(client, payload)
    assert res1.status_code == status.HTTP_200_OK

    # Count consent audit records
    records_1 = db.query(models.ConsentRecord).filter(
        models.ConsentRecord.phone == "+919876543211"
    ).all()
    assert len(records_1) == 1
    assert records_1[0].status == "REVOKED"

    opt_outs_1 = db.query(models.OptOut).filter(
        models.OptOut.phone == "+919876543211"
    ).all()
    assert len(opt_outs_1) == 1

    # Replay
    res2 = post_meta_webhook(client, payload)
    assert res2.status_code == status.HTTP_200_OK

    # Still exactly 1 record
    records_2 = db.query(models.ConsentRecord).filter(
        models.ConsentRecord.phone == "+919876543211"
    ).all()
    assert len(records_2) == 1

    opt_outs_2 = db.query(models.OptOut).filter(
        models.OptOut.phone == "+919876543211"
    ).all()
    assert len(opt_outs_2) == 1


def test_meta_batch_processing_multiple_entries_and_changes(client, db):
    # Setup outbound message log to verify status update
    outbound_wamid = "wamid.OUTBOUND_BATCH_001"
    msg_log = models.MessageLog(
        recipient_phone="+919876543212",
        template_name="cart_recovery_reminder",
        status="SENT",
        meta_message_id=outbound_wamid
    )
    db.add(msg_log)
    db.commit()

    inbound_wamid_1 = "wamid.INBOUND_BATCH_001"
    inbound_wamid_2 = "wamid.INBOUND_BATCH_002"

    batch_payload = {
        "entry": [
            {
                "id": "entry_1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "statuses": [
                                {
                                    "id": outbound_wamid,
                                    "status": "delivered",
                                    "timestamp": "1726830000",
                                    "recipient_id": "919876543212"
                                }
                            ]
                        }
                    },
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "id": inbound_wamid_1,
                                    "from": "919876543213",
                                    "type": "text",
                                    "text": {"body": "First batch customer enquiry"}
                                }
                            ]
                        }
                    }
                ]
            },
            {
                "id": "entry_2",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messages": [
                                {
                                    "id": inbound_wamid_2,
                                    "from": "919876543214",
                                    "type": "text",
                                    "text": {"body": "Second entry customer enquiry"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }

    res = post_meta_webhook(client, batch_payload)
    assert res.status_code == status.HTTP_200_OK

    # 1. Verify outbound message status was updated to DELIVERED
    db.refresh(msg_log)
    assert msg_log.status == "DELIVERED"

    # 2. Verify inbound message 1 was processed
    chat1 = db.query(models.ChatMessage).filter(models.ChatMessage.meta_message_id == inbound_wamid_1).first()
    assert chat1 is not None
    assert chat1.text == "First batch customer enquiry"
    assert chat1.customer_phone == "+919876543213"

    # 3. Verify inbound message 2 was processed
    chat2 = db.query(models.ChatMessage).filter(models.ChatMessage.meta_message_id == inbound_wamid_2).first()
    assert chat2 is not None
    assert chat2.text == "Second entry customer enquiry"
    assert chat2.customer_phone == "+919876543214"


def test_read_receipt_preserves_waiting_delay_timer(client, db):
    from datetime import datetime, timedelta
    phone = "+919876543299"
    test_wamid = "wamid.TEST_DELAY_PRESERVE"
    future_time = datetime.utcnow() + timedelta(minutes=5)

    sess = models.WorkflowSession(
        flow_id=1,
        customer_phone=phone,
        status="WAITING_DELAY",
        current_node_id="delay_node_1",
        next_evaluation_at=future_time,
        state_data={"last_meta_message_id": test_wamid, "message_read": False}
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)

    # Post Meta status READ webhook
    read_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": test_wamid,
                                    "status": "read",
                                    "recipient_id": "919876543299",
                                    "timestamp": str(int(datetime.utcnow().timestamp()))
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    res = post_meta_webhook(client, read_payload)
    assert res.status_code == status.HTTP_200_OK

    db.refresh(sess)
    # 1. message_read is updated to True
    assert sess.state_data.get("message_read") is True
    # 2. WAITING_DELAY timer was preserved and NOT truncated to utcnow()
    assert sess.status == "WAITING_DELAY"
    assert sess.next_evaluation_at > datetime.utcnow() + timedelta(minutes=4)


def test_inbound_customer_reply_marks_message_read(client, db):
    from datetime import datetime, timedelta
    phone = "+919876543288"
    outbound_wamid = f"wamid.OUTBOUND_{int(datetime.utcnow().timestamp())}"

    # Setup outbound message log
    msg_log = models.MessageLog(
        recipient_phone=phone,
        template_name="cart_alert",
        status="DELIVERED",
        meta_message_id=outbound_wamid,
        created_at=datetime.utcnow()
    )
    db.add(msg_log)

    sess = models.WorkflowSession(
        flow_id=1,
        customer_phone=phone,
        status="WAITING_DELAY",
        current_node_id="delay_node_1",
        next_evaluation_at=datetime.utcnow() + timedelta(minutes=5),
        state_data={"last_meta_message_id": outbound_wamid, "message_read": False}
    )
    db.add(sess)
    db.commit()

    # Customer replies via WhatsApp
    inbound_wamid = f"wamid.INBOUND_{int(datetime.utcnow().timestamp())}"
    reply_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": inbound_wamid,
                                    "from": "919876543288",
                                    "type": "text",
                                    "text": {"body": "I want to buy this, what is the price?"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    res = post_meta_webhook(client, reply_payload)
    assert res.status_code == status.HTTP_200_OK

    db.refresh(sess)
    db.refresh(msg_log)
    # Outbound message log marked as READ on customer reply
    assert msg_log.status == "READ"
    # Session state updated to message_read = True
    assert sess.state_data.get("message_read") is True
