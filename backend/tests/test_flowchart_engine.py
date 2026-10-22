import pytest
import json
import hmac
import hashlib
from datetime import datetime, timedelta
import models
import auth
from scheduler import start_workflow_session, process_workflow_session_step


def test_list_and_create_workflow(client, auth_headers, db):
    # 1. Test listing (should include seeded or empty)
    res = client.get("/api/workflows", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # 2. Test creating new custom journey flow
    new_flow_payload = {
        "name": "Custom VIP Test Flow",
        "description": "VIP repeat buyer appreciation journey",
        "trigger_type": "ORDER_COUNT_VIP",
        "trigger_config": {"min_orders": 2},
        "is_active": True,
        "nodes": [
            {
                "id": "t1",
                "type": "trigger",
                "label": "VIP Repeat Trigger",
                "position": {"x": 200, "y": 40},
                "data": {"trigger_type": "ORDER_COUNT_VIP"}
            },
            {
                "id": "a1",
                "type": "whatsapp_message",
                "label": "Send VIP Tasting Invite",
                "position": {"x": 200, "y": 180},
                "data": {"template_name": "vip_exclusive_offer", "coupon_code": "VIPSPECIAL"}
            },
            {
                "id": "e1",
                "type": "exit",
                "label": "VIP Journey Done",
                "position": {"x": 200, "y": 320},
                "data": {"outcome": "GOAL_MET"}
            }
        ],
        "edges": [
            {"id": "e-t1-a1", "source": "t1", "target": "a1"},
            {"id": "e-a1-e1", "source": "a1", "target": "e1"}
        ]
    }
    create_res = client.post("/api/workflows", json=new_flow_payload, headers=auth_headers)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["name"] == "Custom VIP Test Flow"
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2


def test_simulate_workflow_is_removed(client, auth_headers, db):
    flow_id = 1
    # Verify simulation endpoint was completely removed
    res = client.post("/api/workflows/1/simulate", json={}, headers=auth_headers)
    assert res.status_code in [404, 405]

    # Check sessions endpoint
    sess_res = client.get(f"/api/workflows/{flow_id}/sessions", headers=auth_headers)
    assert sess_res.status_code == 200
    assert isinstance(sess_res.json(), list)


def test_workflow_engine_condition_branching(db):
    """
    Tests engine execution with condition branching:
    Trigger -> Delay -> Condition (ORDER_PLACED)
    YES -> Tag (VIP) -> Exit (GOAL_MET)
    NO -> Exit (DROPOUT)
    """
    test_flow = models.WorkflowFlow(
        name="Test Condition Branching Flow",
        trigger_type="ABANDONED_CART",
        is_active=True,
        nodes=[
            {"id": "n1", "type": "trigger", "label": "Start", "data": {}},
            {"id": "n2", "type": "delay", "label": "Wait 15m", "data": {"delay_minutes": 15}},
            {"id": "n3", "type": "condition", "label": "Purchased?", "data": {"condition_type": "ORDER_PLACED"}},
            {"id": "n4_yes", "type": "tag", "label": "Tag VIP", "data": {"tag_name": "Recovered Patron"}},
            {"id": "n5_goal", "type": "exit", "label": "Goal Reached", "data": {"outcome": "GOAL_MET"}},
            {"id": "n6_no", "type": "exit", "label": "Dropout", "data": {"outcome": "DROPOUT"}}
        ],
        edges=[
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3_yes", "source": "n3", "target": "n4_yes", "sourceHandle": "yes"},
            {"id": "e4_goal", "source": "n4_yes", "target": "n5_goal"},
            {"id": "e5_no", "source": "n3", "target": "n6_no", "sourceHandle": "no"}
        ],
        stats={"entered": 0, "completed": 0, "goals_converted": 0, "revenue_recovered": 0}
    )
    db.add(test_flow)
    db.commit()
    db.refresh(test_flow)

    phone = "+919876540000"
    # Ensure contact exists
    contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
    if not contact:
        contact = models.Contact(phone=phone, name="Test Branch Patron")
        db.add(contact)
        db.commit()

    # Scenario A: Order is NOT placed -> Should branch to NO (Dropout)
    sess_no = start_workflow_session(
        flow_id=test_flow.id,
        customer_phone=phone,
        state_data={"cart_token": "cart_no_order", "order_placed": False},
        db=db
    )
    assert sess_no is not None
    # Trigger moved it to delay (n2), status is WAITING_DELAY
    assert sess_no.status == "WAITING_DELAY"
    assert sess_no.current_node_id == "n2"

    # Fast forward delay timer and execute
    sess_no.next_evaluation_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    process_workflow_session_step(sess_no.id, db=db, mock_send=True)
    db.refresh(sess_no)
    # Should have traversed: Delay expired -> Condition n3 -> NO branch -> n6_no Exit (DROPOUT)
    assert sess_no.status == "COMPLETED_DROPOUT"

    # Scenario B: Order IS placed -> Should branch to YES (Tag VIP -> Goal)
    sess_yes = start_workflow_session(
        flow_id=test_flow.id,
        customer_phone=phone,
        state_data={"cart_token": "cart_with_order", "order_placed": True, "cart_value": 600.0},
        db=db
    )
    # Fast forward delay
    sess_yes.next_evaluation_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    process_workflow_session_step(sess_yes.id, db=db, mock_send=True)
    db.refresh(sess_yes)
    assert sess_yes.status == "COMPLETED_GOAL"
    db.refresh(contact)
    assert "Recovered Patron" in (contact.tags or "")


def test_cart_event_webhook_enrolls_workflow(client, db):
    # Ensure service account exists
    svc = db.query(models.User).filter(models.User.username == "ecom_service").first()
    if not svc:
        svc = models.User(
            username="ecom_service",
            email="ecom_service@example.com",
            hashed_password=auth.get_password_hash("ServicePass123!"),
            is_active=True,
            role="service"
        )
        db.add(svc)
        db.commit()

    svc_token = auth.create_access_token(data={"sub": "ecom_service", "role": "service"})
    headers = {"Authorization": f"Bearer {svc_token}"}

    # Ensure an active ABANDONED_CART workflow exists
    active_wf = db.query(models.WorkflowFlow).filter(
        models.WorkflowFlow.trigger_type == "ABANDONED_CART",
        models.WorkflowFlow.is_active == True
    ).first()
    if not active_wf:
        active_wf = models.WorkflowFlow(
            name="Active Cart Recovery Flow",
            trigger_type="ABANDONED_CART",
            is_active=True,
            nodes=[
                {"id": "t1", "type": "trigger", "label": "Trigger", "data": {}},
                {"id": "e1", "type": "exit", "label": "Exit", "data": {"outcome": "GOAL_MET"}}
            ],
            edges=[{"id": "e1", "source": "t1", "target": "e1"}],
            stats={"entered": 0, "completed": 0, "goals_converted": 0, "revenue_recovered": 0}
        )
        db.add(active_wf)
        db.commit()

    cart_payload = {
        "cart_token": f"cart_wf_test_{int(datetime.utcnow().timestamp())}",
        "customer_phone": "+919123456780",
        "cart_value": 850.0,
        "items": [{"item": "Gold Ring"}, {"item": "Diamond Ring"}]
    }

    raw_body = json.dumps(cart_payload).encode()
    signature = "sha256=" + hmac.new(
        b"test-store-webhook-secret", raw_body, hashlib.sha256
    ).hexdigest()
    hmac_headers = {"Content-Type": "application/json", "X-Hub-Signature-256": signature}

    res = client.post("/api/webhooks/cart-event?delay_seconds=1800", content=raw_body, headers=hmac_headers)
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "received"
    assert "workflow_session_id" in data


def test_clear_workflow_queue(client, auth_headers, db):
    # Create test flow
    flow = models.WorkflowFlow(
        name="Clear Queue Test Flow",
        trigger_type="ABANDONED_CART",
        is_active=True,
        nodes=[{"id": "t1", "type": "trigger", "label": "T"}],
        edges=[],
        stats={"entered": 5, "completed": 2, "goals_converted": 1, "revenue_recovered": 500}
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)

    # Add active, waiting, and completed sessions
    s1 = models.WorkflowSession(flow_id=flow.id, customer_phone="+919999900001", status="ACTIVE")
    s2 = models.WorkflowSession(flow_id=flow.id, customer_phone="+919999900002", status="WAITING_DELAY")
    s3 = models.WorkflowSession(flow_id=flow.id, customer_phone="+919999900003", status="COMPLETED_GOAL")
    db.add_all([s1, s2, s3])
    db.commit()

    # Add an outbound message referencing session s1 to verify FK unlinking works without error
    out_msg = models.OutboundMessage(
        idempotency_key="out_msg_test_clear_queue",
        recipient_phone_e164="+919999900001",
        recipient_hash="hash12345",
        message_kind="template",
        purpose="utility",
        workflow_session_id=s1.id,
        status="sent"
    )
    cart_evt = models.CartEvent(
        cart_token="cart_clear_test_token",
        customer_phone="+919999900001",
        cart_value=500.0
    )
    db.add_all([out_msg, cart_evt])
    db.commit()

    # 1. Test mode="cancel_active"
    res = client.post(f"/api/workflows/{flow.id}/clear-queue?mode=cancel_active", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["cleared_count"] == 2  # s1 and s2

    db.refresh(s1)
    db.refresh(s2)
    db.refresh(s3)
    assert s1.status == "CANCELLED"
    assert s2.status == "CANCELLED"
    assert s3.status == "COMPLETED_GOAL"

    # 2. Test mode="delete_all" with clear_stats=True and clear_cart_events=True
    res2 = client.post(
        f"/api/workflows/{flow.id}/clear-queue?mode=delete_all&clear_stats=true&clear_cart_events=true",
        headers=auth_headers
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "success"
    assert data2["cleared_count"] == 3  # all 3 deleted
    assert data2["stats_reset"] is True
    assert data2["cleared_cart_events"] >= 1

    remaining = db.query(models.WorkflowSession).filter(models.WorkflowSession.flow_id == flow.id).count()
    assert remaining == 0
    db.refresh(flow)
    assert flow.stats["entered"] == 0

    # Verify OutboundMessage has been cleanly unlinked (workflow_session_id set to NULL)
    db.refresh(out_msg)
    assert out_msg.workflow_session_id is None


def test_workflow_node_idempotency_and_loop_prevention(db):
    """
    Tests that:
    1. A session does not re-dispatch WhatsApp messages if re-evaluated at the same node.
    2. A looped flow terminates safely when the revisit limit is reached.
    """
    from unittest.mock import patch

    loop_flow = models.WorkflowFlow(
        name="Test Loop Flow",
        trigger_type="ABANDONED_CART",
        is_active=True,
        nodes=[
            {"id": "t1", "type": "trigger", "label": "Start"},
            {"id": "w1", "type": "whatsapp_message", "label": "Send WhatsApp", "data": {"template_name": "appointment_reminder_2"}},
            {"id": "c1", "type": "condition", "label": "Check", "data": {"condition_type": "MESSAGE_READ"}}
        ],
        edges=[
            {"id": "e1", "source": "t1", "target": "w1"},
            {"id": "e2", "source": "w1", "target": "c1"},
            {"id": "e3", "source": "c1", "target": "w1", "sourceHandle": "yes"}
        ],
        stats={}
    )
    db.add(loop_flow)
    db.commit()

    dispatched_count = 0
    def mock_send(*args, **kwargs):
        nonlocal dispatched_count
        dispatched_count += 1
        return {"status": "success", "message_id": f"msg_{dispatched_count}"}

    with patch("scheduler.send_whatsapp_template", side_effect=mock_send):
        sess = start_workflow_session(
            flow_id=loop_flow.id,
            customer_phone="+918780001820",
            state_data={"message_read": True},
            db=db
        )
        assert sess is not None
        # Must have sent at most 1 time on first pass
        assert dispatched_count == 1
        # Loop detection should terminate the session rather than infinite messaging
        assert sess.status == "COMPLETED_DROPOUT"
        assert any("Terminated" in h.get("details", "") for h in sess.history)


def test_message_read_condition_accuracy_and_no_false_positives(db):
    """
    Verifies that 'Was Message Read?' evaluates to:
    - NO when the outbound message is SENT/DELIVERED (even if ChatMessage.is_read is True for agent CRM inbox)
    - YES when MessageLog.status or ChatMessage.status is genuinely 'READ' from Meta webhook
    """
    flow = models.WorkflowFlow(
        name="Test Read Condition Flow",
        trigger_type="ABANDONED_CART",
        nodes=[
            {"id": "t1", "type": "trigger", "label": "Start"},
            {"id": "c1", "type": "condition", "label": "Was Message Read?", "data": {"condition_type": "MESSAGE_READ"}},
            {"id": "g_yes", "type": "goal", "label": "Read Goal"},
            {"id": "e_no", "type": "exit", "label": "Unread Exit"}
        ],
        edges=[
            {"id": "e1", "source": "t1", "target": "c1"},
            {"id": "e2", "source": "c1", "target": "g_yes", "sourceHandle": "yes"},
            {"id": "e3", "source": "c1", "target": "e_no", "sourceHandle": "no"}
        ],
        stats={}
    )
    db.add(flow)
    db.commit()

    phone = "+918780001820"
    msg_id = f"wamid_test_{int(datetime.utcnow().timestamp())}"

    # Scenario 1: Outbound message sent, but customer has NOT read it yet.
    # Note: ChatMessage has is_read=True (agent inbox), but status='SENT'
    msg_log = models.MessageLog(
        recipient_phone=phone,
        template_name="test_tmpl",
        meta_message_id=msg_id,
        status="SENT"
    )
    chat_entry = models.ChatMessage(
        customer_phone=phone,
        sender_type="AGENT",
        message_type="template",
        meta_message_id=msg_id,
        status="SENT",
        is_read=True  # Internal CRM agent view
    )
    db.add(msg_log)
    db.add(chat_entry)
    db.commit()

    sess_unread = start_workflow_session(
        flow_id=flow.id,
        customer_phone=phone,
        state_data={"last_meta_message_id": msg_id},
        db=db
    )
    assert sess_unread is not None
    # Must have branched to NO (Unread Exit) because status is 'SENT', NOT 'READ'
    assert sess_unread.status == "COMPLETED_DROPOUT"
    assert any("Took 'NO' path" in h.get("details", "") for h in sess_unread.history)

    # Scenario 2: Meta webhook delivers read receipt (status becomes 'READ')
    msg_log.status = "READ"
    chat_entry.status = "READ"
    db.commit()

    sess_read = start_workflow_session(
        flow_id=flow.id,
        customer_phone=phone,
        state_data={"last_meta_message_id": msg_id},
        db=db
    )
    assert sess_read is not None
    # Must have branched to YES (Read Goal)
    assert sess_read.status == "COMPLETED_GOAL"
    assert any("Took 'YES' path" in h.get("details", "") for h in sess_read.history)


def test_send_whatsapp_template_idempotency_replay(db):
    """
    Verifies that calling send_whatsapp_template with an existing SENT OutboundMessage
    replays the existing message ID without duplicating calls to Meta.
    """
    from whatsapp_service import send_whatsapp_template

    idemp_key = f"test_idemp_{int(datetime.utcnow().timestamp())}"
    existing_outbound = models.OutboundMessage(
        idempotency_key=idemp_key,
        recipient_phone_e164="+918780001820",
        recipient_hash="dummy_hash",
        message_kind="template",
        purpose="utility",
        template_name="appointment_reminder_2",
        status="SENT",
        policy_decision="authorized",
        meta_message_id="wamid_existing_12345"
    )
    db.add(existing_outbound)
    db.commit()

    # Calling send_whatsapp_template must return existing ID without error
    res = send_whatsapp_template(
        recipient_phone="+918780001820",
        template_name="appointment_reminder_2",
        idempotency_key=idemp_key,
        db=db
    )
    assert res.get("status") == "success"
    assert res.get("message_id") == "wamid_existing_12345"
    assert res.get("idempotent_replay") is True


def test_consecutive_messages_reset_read_status(db):
    """
    Verifies that when a second message is sent in a workflow,
    message_read is reset to False so that subsequent 'Was Message Read?' conditions
    evaluate to NO if the customer has not read the second message.
    """
    flow = models.WorkflowFlow(
        name="Test Multi Message Read Flow",
        trigger_type="ABANDONED_CART",
        nodes=[
            {"id": "t1", "type": "trigger", "label": "Start"},
            {"id": "m1", "type": "whatsapp_message", "label": "Msg 1", "data": {"template_name": "tmpl_1"}},
            {"id": "d1", "type": "delay", "label": "Wait 1m", "data": {"delay_minutes": 1}},
            {"id": "c1", "type": "condition", "label": "Read 1?", "data": {"condition_type": "MESSAGE_READ"}},
            {"id": "m2", "type": "whatsapp_message", "label": "Msg 2", "data": {"template_name": "tmpl_2"}},
            {"id": "d2", "type": "delay", "label": "Wait 1m", "data": {"delay_minutes": 1}},
            {"id": "c2", "type": "condition", "label": "Read 2?", "data": {"condition_type": "MESSAGE_READ"}},
            {"id": "g_yes", "type": "goal", "label": "Success"},
            {"id": "e_no", "type": "exit", "label": "Exit"}
        ],
        edges=[
            {"id": "e1", "source": "t1", "target": "m1"},
            {"id": "e2", "source": "m1", "target": "d1"},
            {"id": "e3", "source": "d1", "target": "c1"},
            {"id": "e4", "source": "c1", "target": "m2", "sourceHandle": "yes"},
            {"id": "e5", "source": "c1", "target": "e_no", "sourceHandle": "no"},
            {"id": "e6", "source": "m2", "target": "d2"},
            {"id": "e7", "source": "d2", "target": "c2"},
            {"id": "e8", "source": "c2", "target": "g_yes", "sourceHandle": "yes"},
            {"id": "e9", "source": "c2", "target": "e_no", "sourceHandle": "no"}
        ],
        stats={}
    )
    db.add(flow)
    db.commit()

    phone = "+919876543210"
    sess = start_workflow_session(flow_id=flow.id, customer_phone=phone, state_data={"simulation": True}, db=db)
    # Session started, sent m1, and paused in delay d1
    assert sess.status == "WAITING_DELAY"
    assert sess.current_node_id == "d1"
    assert sess.state_data.get("message_read") is False
    m1_wamid = sess.state_data.get("last_meta_message_id")

    # Customer reads m1
    msg1 = models.MessageLog(
        recipient_phone=phone,
        meta_message_id=m1_wamid,
        status="READ",
        template_name="tmpl_1"
    )
    db.add(msg1)
    st = dict(sess.state_data)
    st["message_read"] = True
    sess.state_data = st
    db.commit()

    # Fast forward delay d1
    sess.next_evaluation_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    # Step: delay d1 expires -> evaluates c1 (Read 1? -> YES) -> dispatches m2 -> pauses in delay d2
    process_workflow_session_step(sess.id, db=db, mock_send=True)
    db.refresh(sess)

    assert sess.status == "WAITING_DELAY"
    assert sess.current_node_id == "d2"
    # Crucial assertion: message_read MUST be reset to False for m2!
    assert sess.state_data.get("message_read") is False
    m2_wamid = sess.state_data.get("last_meta_message_id")
    assert m2_wamid != m1_wamid

    # Fast forward delay d2 without customer reading m2
    sess.next_evaluation_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    # Step: delay d2 expires -> evaluates c2 (Read 2?) -> customer has NOT read m2, must take NO path!
    process_workflow_session_step(sess.id, db=db, mock_send=True)
    db.refresh(sess)

    # Must take NO path and exit cleanly
    assert sess.status == "COMPLETED_DROPOUT"
    c2_hist = [h for h in sess.history if h.get("node_id") == "c2"]
    assert len(c2_hist) == 1
    assert "Took 'NO' path" in c2_hist[0].get("details", "")



