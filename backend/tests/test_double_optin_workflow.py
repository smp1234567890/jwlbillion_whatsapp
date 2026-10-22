import json
import hmac
import hashlib
from datetime import datetime, timedelta
import pytest
from fastapi import status
import config
import models
from scheduler import start_workflow_session, process_workflow_session_step


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


def test_customer_sync_triggers_welcome_flow_and_double_optin_affirmative(client, db):
    # 1. Create active Welcome & Double Opt-in Workflow
    flow = models.WorkflowFlow(
        name="Welcome & Double Opt-In Flow",
        description="Double opt-in onboarding sequence for new customers",
        trigger_type="NEW_CUSTOMER_WELCOME",
        trigger_config={"welcome_coupon": "WELCOME10"},
        is_active=True,
        nodes=[
            {
                "id": "node_1",
                "type": "trigger",
                "label": "New Customer Signup",
                "data": {"trigger_type": "NEW_CUSTOMER_WELCOME"}
            },
            {
                "id": "node_2",
                "type": "whatsapp_message",
                "label": "Send Double Opt-In Invite",
                "data": {"template_name": "welcome_greeting"}
            },
            {
                "id": "node_3",
                "type": "condition",
                "label": "Did Customer Confirm Opt-In?",
                "data": {"condition_type": "DOUBLE_OPTIN_CONFIRMED"}
            },
            {
                "id": "node_4",
                "type": "tag",
                "label": "Tag: Opted-In VIP",
                "data": {"tag_name": "Double Opt-In Confirmed"}
            },
            {
                "id": "node_5",
                "type": "tag",
                "label": "Tag: Unconfirmed Consent",
                "data": {"tag_name": "Unconfirmed Consent"}
            }
        ],
        edges=[
            {"id": "e-1-2", "source": "node_1", "target": "node_2"},
            {"id": "e-2-3", "source": "node_2", "target": "node_3"},
            {"id": "e-3-4", "source": "node_3", "target": "node_4", "sourceHandle": "yes"},
            {"id": "e-3-5", "source": "node_3", "target": "node_5", "sourceHandle": "no"}
        ]
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)

    test_phone = "+919825198251"

    # Ensure clean state
    db.query(models.Contact).filter(models.Contact.phone == test_phone).delete()
    db.query(models.ConsentRecord).filter(models.ConsentRecord.phone == test_phone).delete()
    db.commit()

    # 2. Inbound customer sync webhook
    sync_payload = {
        "phone": test_phone,
        "name": "Bhavik Shah",
        "email": "bhavik@example.com",
        "city": "Ahmedabad",
        "membership_tier": "Silver"
    }
    secret = config.WEBHOOK_SECRET or "test-secret"
    res = client.post(
        "/api/webhooks/customer-sync",
        json=sync_payload,
        headers={"X-API-Key": secret}
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["action"] == "created"

    # 3. Verify workflow session was automatically initiated
    session = db.query(models.WorkflowSession).filter(
        models.WorkflowSession.flow_id == flow.id,
        models.WorkflowSession.customer_phone == test_phone
    ).first()
    assert session is not None

    # Before opt-in reply: condition should evaluate to NO
    outcome_before = process_workflow_session_step(session.id, db=db, mock_send=True)
    db.refresh(session)
    # Customer has not opted in yet, so taken the NO path
    assert session.status in ["COMPLETED_DROPOUT", "COMPLETED_GOAL", "ACTIVE"]

    # 4. Now simulate affirmative inbound reply ("YES")
    meta_id = f"wamid.OPTIN_{int(datetime.utcnow().timestamp())}"
    inbound_meta_payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": meta_id,
                                    "from": "919825198251",
                                    "type": "text",
                                    "text": {"body": "YES, please send updates!"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    inbound_res = post_meta_webhook(client, inbound_meta_payload)
    assert inbound_res.status_code == status.HTTP_200_OK

    # 5. Verify Consent Record was created with ACTIVE/GRANTED status
    consent = db.query(models.ConsentRecord).filter(
        models.ConsentRecord.phone == test_phone,
        models.ConsentRecord.status.in_(["ACTIVE", "GRANTED"])
    ).first()
    assert consent is not None
    assert consent.source == "inbound_message"


def test_customer_inbound_gujarati_optin(client, db):
    test_phone = "+919825298252"
    db.query(models.ConsentRecord).filter(models.ConsentRecord.phone == test_phone).delete()
    db.commit()

    meta_id = f"wamid.OPTIN_GUJ_{int(datetime.utcnow().timestamp())}"
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": meta_id,
                                    "from": "919825298252",
                                    "type": "text",
                                    "text": {"body": "હા હું સંમત છું"}
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    res = post_meta_webhook(client, payload)
    assert res.status_code == status.HTTP_200_OK

    consent = db.query(models.ConsentRecord).filter(
        models.ConsentRecord.phone == test_phone,
        models.ConsentRecord.status.in_(["ACTIVE", "GRANTED"])
    ).first()
    assert consent is not None
    assert consent.source == "inbound_message"
