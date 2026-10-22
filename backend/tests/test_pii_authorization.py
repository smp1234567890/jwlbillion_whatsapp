"""
Tests for Work Package 6: PII Authorization and Record-Level Access Scoping
Covers:
- Agents cannot list all contacts (only assigned contacts).
- Unassigned contact detail returns 403 for agents; assigned contact detail returns 200 unmasked.
- Admin can access any contact detail unmasked.
- List DTOs mask phone and email (+91******3210 and m***@domain.com).
- Agents cannot access restricted resources (/api/cart-events, /api/message-logs, /api/workflows).
- Agents cannot access unassigned conversations or chat history.
- Agents without support_send cannot send free-text chat replies (403).
- Agents with support_send can send to assigned contact within service window.
- Contact assignment requires admin/manager and generates an AuditEvent.
- Contact and message-log exports require admin step-up auth, reason, and create an AuditEvent.
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi import status
import models
import auth


@pytest.fixture
def agent_user(db):
    user = db.query(models.User).filter(models.User.username == "test_agent_1").first()
    if not user:
        user = models.User(
            username="test_agent_1",
            email="agent1@example.com",
            hashed_password=auth.get_password_hash("AgentPass123!"),
            role="agent",
            is_active=True,
            can_support_send=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def agent_headers(agent_user):
    token = auth.create_access_token(data={"sub": agent_user.username, "role": agent_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manager_user(db):
    user = db.query(models.User).filter(models.User.username == "test_manager_1").first()
    if not user:
        user = models.User(
            username="test_manager_1",
            email="manager1@example.com",
            hashed_password=auth.get_password_hash("ManagerPass123!"),
            role="manager",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def manager_headers(manager_user):
    token = auth.create_access_token(data={"sub": manager_user.username, "role": manager_user.role})
    return {"Authorization": f"Bearer {token}"}


def test_agent_cannot_list_all_contacts(client, agent_headers, agent_user, auth_headers, db):
    """
    Agents only see contacts assigned to them; unassigned contacts are hidden.
    """
    # Seed one assigned contact and one unassigned contact
    phone_assigned = "+919811111111"
    phone_unassigned = "+919822222222"

    c1 = db.query(models.Contact).filter(models.Contact.phone == phone_assigned).first()
    if not c1:
        c1 = models.Contact(phone=phone_assigned, name="Assigned Customer", assigned_user_id=agent_user.id)
        db.add(c1)
    else:
        c1.assigned_user_id = agent_user.id

    c2 = db.query(models.Contact).filter(models.Contact.phone == phone_unassigned).first()
    if not c2:
        c2 = models.Contact(phone=phone_unassigned, name="Other Customer", assigned_user_id=None)
        db.add(c2)
    else:
        c2.assigned_user_id = None
    db.commit()

    # Agent query
    res = client.get("/api/contacts", headers=agent_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    returned_phones = [item["phone"] for item in data]
    # Phone should be masked in list view
    assert any("1111" in p for p in returned_phones)
    assert not any("2222" in p for p in returned_phones)

    # Admin query should see all
    admin_res = client.get("/api/contacts", headers=auth_headers)
    assert admin_res.status_code == status.HTTP_200_OK
    admin_data = admin_res.json()
    admin_phones = [item["phone"] for item in admin_data]
    assert any("1111" in p for p in admin_phones)
    assert any("2222" in p for p in admin_phones)


def test_list_dtos_mask_phone_and_email(client, agent_headers, agent_user, auth_headers, db):
    """
    List DTOs return unmasked PII for admin/manager, and mask phone/email for non-privileged agents.
    """
    test_phone = "+919876543210"
    test_email = "customer.vip@jwl-billion.com"

    c = db.query(models.Contact).filter(models.Contact.phone == test_phone).first()
    if not c:
        c = models.Contact(phone=test_phone, name="VIP Test", email=test_email, assigned_user_id=agent_user.id)
        db.add(c)
    else:
        c.email = test_email
        c.assigned_user_id = agent_user.id
    db.commit()

    # Admin gets full unmasked phone and email
    res_admin = client.get("/api/contacts?limit=100", headers=auth_headers)
    assert res_admin.status_code == status.HTTP_200_OK
    items_admin = res_admin.json()
    target_admin = next((item for item in items_admin if "3210" in item["phone"]), None)
    assert target_admin is not None
    assert target_admin["phone"] == test_phone
    assert target_admin["email"] == test_email

    # Non-privileged agent gets masked phone and email
    res_agent = client.get("/api/contacts?limit=100", headers=agent_headers)
    assert res_agent.status_code == status.HTTP_200_OK
    items_agent = res_agent.json()
    target_agent = next((item for item in items_agent if "3210" in item["phone"]), None)
    assert target_agent is not None
    assert target_agent["phone"] == "+91******3210"
    assert target_agent["email"] == "c***@jwl-billion.com"


def test_contact_detail_record_scope(client, agent_headers, agent_user, auth_headers, db):
    """
    Detail endpoint returns unmasked PII only to authorized users with record scope.
    """
    phone_assigned = "+919833333333"
    phone_unassigned = "+919844444444"

    c1 = db.query(models.Contact).filter(models.Contact.phone == phone_assigned).first()
    if not c1:
        c1 = models.Contact(phone=phone_assigned, name="Scope Assigned", email="assigned@example.com", assigned_user_id=agent_user.id)
        db.add(c1)
        db.commit()
        db.refresh(c1)

    c2 = db.query(models.Contact).filter(models.Contact.phone == phone_unassigned).first()
    if not c2:
        c2 = models.Contact(phone=phone_unassigned, name="Scope Other", email="other@example.com", assigned_user_id=None)
        db.add(c2)
        db.commit()
        db.refresh(c2)

    # 1. Agent accessing assigned contact -> 200 with full unmasked phone & email
    res1 = client.get(f"/api/contacts/{c1.id}", headers=agent_headers)
    assert res1.status_code == status.HTTP_200_OK
    assert res1.json()["phone"] == phone_assigned
    assert res1.json()["email"] == "assigned@example.com"

    # 2. Agent accessing unassigned contact -> 403 Forbidden
    res2 = client.get(f"/api/contacts/{c2.id}", headers=agent_headers)
    assert res2.status_code == status.HTTP_403_FORBIDDEN
    assert "access denied" in res2.json()["detail"].lower()

    # 3. Admin accessing unassigned contact -> 200 with full unmasked phone & email
    res3 = client.get(f"/api/contacts/{c2.id}", headers=auth_headers)
    assert res3.status_code == status.HTTP_200_OK
    assert res3.json()["phone"] == phone_unassigned
    assert res3.json()["email"] == "other@example.com"


def test_agent_cannot_list_restricted_resources(client, agent_headers):
    """
    Agents cannot list carts, message logs, or workflows.
    """
    # 1. Cart events
    res_cart = client.get("/api/cart-events", headers=agent_headers)
    assert res_cart.status_code == status.HTTP_403_FORBIDDEN

    # 2. Message logs
    res_logs = client.get("/api/message-logs", headers=agent_headers)
    assert res_logs.status_code == status.HTTP_403_FORBIDDEN

    # 3. Workflows
    res_wf = client.get("/api/workflows", headers=agent_headers)
    assert res_wf.status_code == status.HTTP_403_FORBIDDEN


def test_agent_conversation_scoping(client, agent_headers, agent_user, db):
    """
    Agents can only list and read chat messages for contacts assigned to them.
    """
    assigned_phone = "+919855555555"
    unassigned_phone = "+919866666666"

    # Setup contacts
    c_assigned = db.query(models.Contact).filter(models.Contact.phone == assigned_phone).first()
    if not c_assigned:
        c_assigned = models.Contact(phone=assigned_phone, name="Chat Cust 1", assigned_user_id=agent_user.id)
        db.add(c_assigned)
    else:
        c_assigned.assigned_user_id = agent_user.id

    c_unassigned = db.query(models.Contact).filter(models.Contact.phone == unassigned_phone).first()
    if not c_unassigned:
        c_unassigned = models.Contact(phone=unassigned_phone, name="Chat Cust 2", assigned_user_id=None)
        db.add(c_unassigned)
    else:
        c_unassigned.assigned_user_id = None

    # Setup chat messages
    db.add(models.ChatMessage(customer_phone=assigned_phone, sender_type="CUSTOMER", text="Help 1"))
    db.add(models.ChatMessage(customer_phone=unassigned_phone, sender_type="CUSTOMER", text="Help 2"))
    db.commit()

    # 1. Conversation list for agent should only include assigned customer
    res_conv = client.get("/api/chat/conversations", headers=agent_headers)
    assert res_conv.status_code == status.HTTP_200_OK
    conv_phones = [c["customer_phone"] for c in res_conv.json()]
    assert assigned_phone in conv_phones
    assert unassigned_phone not in conv_phones

    # 2. Agent accessing assigned customer history -> 200
    res_hist1 = client.get(f"/api/chat/history/{assigned_phone}", headers=agent_headers)
    assert res_hist1.status_code == status.HTTP_200_OK

    # 3. Agent accessing unassigned customer history -> 403
    res_hist2 = client.get(f"/api/chat/history/{unassigned_phone}", headers=agent_headers)
    assert res_hist2.status_code == status.HTTP_403_FORBIDDEN


def test_support_send_capability_enforcement(client, agent_headers, agent_user, db, monkeypatch):
    """
    Agents without can_support_send get 403 on /api/chat/send.
    Agents with can_support_send can send within the service window.
    """
    test_phone = "+919877777777"
    contact = db.query(models.Contact).filter(models.Contact.phone == test_phone).first()
    if not contact:
        contact = models.Contact(phone=test_phone, name="Support Send Cust", assigned_user_id=agent_user.id)
        db.add(contact)
    else:
        contact.assigned_user_id = agent_user.id

    # Recent customer message for 24h window
    db.add(models.ChatMessage(
        customer_phone=test_phone,
        sender_type="CUSTOMER",
        text="Need help with my order",
        created_at=datetime.utcnow() - timedelta(minutes=10)
    ))
    db.commit()

    # 1. Agent has can_support_send=False by default -> 403 Forbidden
    agent_user.can_support_send = False
    db.commit()

    res1 = client.post("/api/chat/send", json={
        "customer_phone": test_phone,
        "text": "Hello, how can I assist you today?"
    }, headers=agent_headers)
    assert res1.status_code == status.HTTP_403_FORBIDDEN
    assert "support_send" in res1.json()["detail"].lower()

    # 2. Grant can_support_send to agent -> 200 OK
    agent_user.can_support_send = True
    db.commit()

    monkeypatch.setattr("routers.chat.send_whatsapp_free_text", lambda phone, text: {"status": "success", "message_id": "wamid.agent123"})

    res2 = client.post("/api/chat/send", json={
        "customer_phone": test_phone,
        "text": "Hello, how can I assist you today?"
    }, headers=agent_headers)
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["status"] == "SENT"


def test_contact_assignment_and_audit(client, manager_headers, agent_user, db):
    """
    Manager or Admin can assign a contact to an agent, recording an AuditEvent.
    """
    phone = "+919888888888"
    c = db.query(models.Contact).filter(models.Contact.phone == phone).first()
    if not c:
        c = models.Contact(phone=phone, name="Assign Me", assigned_user_id=None)
        db.add(c)
        db.commit()
        db.refresh(c)

    res = client.post(f"/api/contacts/{c.id}/assign", json={
        "assigned_user_id": agent_user.id
    }, headers=manager_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["assigned_user_id"] == agent_user.id

    # Verify AuditEvent was persisted
    audit = db.query(models.AuditEvent).filter(
        models.AuditEvent.action == "assign_contact",
        models.AuditEvent.target_id == str(c.id)
    ).first()
    assert audit is not None
    assert audit.metadata_json.get("assigned_user_id") == agent_user.id


def test_exports_require_admin_stepup_and_audit(client, auth_headers, agent_headers, db):
    """
    Contact and log exports require admin role + password step-up + justification reason.
    """
    # 1. Agent attempted export -> 403
    res_agent = client.post("/api/contacts/export", json={
        "password": "AnyPassword",
        "reason": "Unauthorized export attempt"
    }, headers=agent_headers)
    assert res_agent.status_code == status.HTTP_403_FORBIDDEN

    # 2. Admin with wrong password -> 401
    res_wrong_pw = client.post("/api/contacts/export", json={
        "password": "WrongPassword123!",
        "reason": "Legitimate audit reason"
    }, headers=auth_headers)
    assert res_wrong_pw.status_code == status.HTTP_401_UNAUTHORIZED

    # 3. Admin with short/empty reason -> 422
    res_no_reason = client.post("/api/contacts/export", json={
        "password": "SecretPassword123!",
        "reason": "bad"
    }, headers=auth_headers)
    assert res_no_reason.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # 4. Admin with valid password & reason -> 200 + creates AuditEvent
    res_ok = client.post("/api/contacts/export", json={
        "password": "SecretPassword123!",
        "reason": "Annual GDPR compliance data backup"
    }, headers=auth_headers)
    assert res_ok.status_code == status.HTTP_200_OK
    assert res_ok.json()["status"] == "success"

    # Verify AuditEvent
    audit = db.query(models.AuditEvent).filter(
        models.AuditEvent.action == "export_contacts"
    ).order_by(models.AuditEvent.id.desc()).first()
    assert audit is not None
    assert audit.metadata_json.get("reason") == "Annual GDPR compliance data backup"
