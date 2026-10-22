import pytest
from datetime import datetime, timedelta
from unittest.mock import patch

import models
from scheduler import start_workflow_session, process_workflow_session_step, process_all_active_workflow_sessions


def test_user_numbers_end_to_end_journey(db):
    """
    Simulates the exact user journey from media_1790061612105.png:
    Trigger -> Send abandoned_cart_reminder -> Wait 1m -> Did Customer Purchase?
      -> NO -> Was Message Read?
         -> NO (unread test for 8780001820): Takes NO branch to discount message.
         -> YES (read test for 9638325271): Takes YES branch to appointment_reminder_2 -> Wait 1m -> Exit.
    """
    flow = models.WorkflowFlow(
        name="Abandoned Cart — Analytics Live Test",
        trigger_type="ABANDONED_CART",
        nodes=[
            {"id": "node_trigger", "type": "trigger", "label": "Cart Abandoned", "data": {"trigger_type": "ABANDONED_CART", "min_cart_value": 300}},
            {"id": "node_msg_1", "type": "whatsapp_message", "label": "Send WhatsApp Message (abandoned_cart_reminder)", "data": {"template_name": "abandoned_cart_reminder"}},
            {"id": "node_delay_1", "type": "delay", "label": "Wait 1 Mins", "data": {"delay_minutes": 1}},
            {"id": "node_cond_purchase", "type": "condition", "label": "Did Customer Purchase?", "data": {"condition_type": "ORDER_PLACED"}},
            {"id": "node_cond_read", "type": "condition", "label": "Was Message Read?", "data": {"condition_type": "MESSAGE_READ"}},
            {"id": "node_msg_discount", "type": "whatsapp_message", "label": "Send WhatsApp Message (discount)", "data": {"template_name": "abandoned_cart_reminder_discount"}},
            {"id": "node_msg_reminder2", "type": "whatsapp_message", "label": "Send WhatsApp Message (appointment_reminder_2)", "data": {"template_name": "appointment_reminder_2"}},
            {"id": "node_delay_2", "type": "delay", "label": "Wait 1 Mins", "data": {"delay_minutes": 1}},
            {"id": "node_exit_goal", "type": "goal", "label": "Recovered Patron Goal"},
            {"id": "node_exit_dropout", "type": "exit", "label": "Journey Exit"}
        ],
        edges=[
            {"id": "e1", "source": "node_trigger", "target": "node_msg_1"},
            {"id": "e2", "source": "node_msg_1", "target": "node_delay_1"},
            {"id": "e3", "source": "node_delay_1", "target": "node_cond_purchase"},
            {"id": "e4", "source": "node_cond_purchase", "target": "node_exit_goal", "sourceHandle": "yes"},
            {"id": "e5", "source": "node_cond_purchase", "target": "node_cond_read", "sourceHandle": "no"},
            {"id": "e6", "source": "node_cond_read", "target": "node_msg_reminder2", "sourceHandle": "yes"},
            {"id": "e7", "source": "node_cond_read", "target": "node_msg_discount", "sourceHandle": "no"},
            {"id": "e8", "source": "node_msg_reminder2", "target": "node_delay_2"},
            {"id": "e9", "source": "node_delay_2", "target": "node_exit_dropout"},
            {"id": "e10", "source": "node_msg_discount", "target": "node_exit_dropout"}
        ],
        stats={},
        is_active=True
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)

    # ══════════════════════════════════════════════════════════════════════════
    # TEST 1: User Number 87800 01820 (Recipient does NOT read the message)
    # Expected: Trigger -> Msg 1 -> Delay 1 -> Purchase? NO -> Read? NO -> Discount Msg -> Exit
    # ══════════════════════════════════════════════════════════════════════════
    phone_1 = "+918780001820"
    sess_1 = start_workflow_session(
        flow_id=flow.id,
        customer_phone=phone_1,
        state_data={"cart_token": "cart_87800", "cart_value": 450.0, "simulation": True},
        db=db
    )
    assert sess_1 is not None
    # Step 1: Dispatched initial template and entered Delay 1
    assert sess_1.status == "WAITING_DELAY"
    assert sess_1.current_node_id == "node_delay_1"

    # Fast forward delay 1 minute
    sess_1.next_evaluation_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    # Step 2: Sweeper evaluates delay completion
    res_1 = process_workflow_session_step(sess_1.id, db=db, mock_send=True)
    db.refresh(sess_1)

    # In unread state, it MUST take the NO path on "Was Message Read?"
    history_nodes = [h.get("node_id") for h in sess_1.history]
    assert "node_cond_purchase" in history_nodes
    assert "node_cond_read" in history_nodes
    assert any("Condition evaluated to NO -> Took 'NO' path" in h.get("details", "") for h in sess_1.history if h.get("node_id") == "node_cond_read")
    # Must have dispatched discount template and concluded at exit
    assert "node_msg_discount" in history_nodes
    assert sess_1.status in ["COMPLETED_DROPOUT", "COMPLETED_GOAL"]

    # ══════════════════════════════════════════════════════════════════════════
    # TEST 2: User Number 96383 25271 (Recipient READS the message)
    # Expected: Trigger -> Msg 1 -> Delay 1 -> Read? YES -> appointment_reminder_2 -> Delay 2 -> Exit
    # ══════════════════════════════════════════════════════════════════════════
    phone_2 = "+919638325271"
    sess_2 = start_workflow_session(
        flow_id=flow.id,
        customer_phone=phone_2,
        state_data={"cart_token": "cart_96383", "cart_value": 750.0, "simulation": True},
        db=db
    )
    assert sess_2 is not None
    assert sess_2.status == "WAITING_DELAY"
    assert sess_2.current_node_id == "node_delay_1"

    # Simulate recipient opening and reading WhatsApp message (Meta webhook receipt)
    sent_wamid = sess_2.state_data.get("last_meta_message_id")
    msg_log = models.MessageLog(
        recipient_phone=phone_2,
        meta_message_id=sent_wamid,
        status="READ",
        template_name="abandoned_cart_reminder",
        created_at=datetime.utcnow()
    )
    db.add(msg_log)
    st_2 = dict(sess_2.state_data or {})
    st_2["message_read"] = True
    sess_2.state_data = st_2
    db.commit()

    # Fast forward delay 1 minute
    sess_2.next_evaluation_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    # Step 2: Sweeper evaluates delay completion
    res_2 = process_workflow_session_step(sess_2.id, db=db, mock_send=True)
    db.refresh(sess_2)

    # In read state, it MUST take the YES path on "Was Message Read?"
    history_nodes_2 = [h.get("node_id") for h in sess_2.history]
    assert "node_cond_read" in history_nodes_2
    assert any("Condition evaluated to YES -> Took 'YES' path" in h.get("details", "") for h in sess_2.history if h.get("node_id") == "node_cond_read")
    # Must have dispatched appointment_reminder_2 and moved downstream to Delay 2 (node_delay_2)
    assert "node_msg_reminder2" in history_nodes_2
    assert sess_2.current_node_id == "node_delay_2"
    assert sess_2.status == "WAITING_DELAY"

    # Fast forward delay 2 (1 minute)
    sess_2.next_evaluation_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    res_2_exit = process_workflow_session_step(sess_2.id, db=db, mock_send=True)
    db.refresh(sess_2)

    # Must have finished the journey cleanly without getting stuck
    assert sess_2.status in ["COMPLETED_DROPOUT", "COMPLETED_GOAL"]
    assert sess_2.attempt_count == 0
