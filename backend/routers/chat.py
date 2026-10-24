from datetime import datetime, timedelta
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import get_db
import config
import models
import schemas
import auth
from whatsapp_service import send_whatsapp_free_text, check_daily_limit, get_effective_daily_limit
from services.phone_service import normalize_phone, InvalidPhoneNumberError
from services import pii_service

logger = logging.getLogger("chat_router")

router = APIRouter(prefix="/api/chat", tags=["Two-Way Live Chat"])


@router.get("/conversations", response_model=List[schemas.ChatConversationSummary])
def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns active conversation threads grouped by customer phone,
    with unread counts, contact details, and last message snippet.
    Agents can only view conversations for contacts assigned to them.
    """
    # If agent, pre-fetch their assigned contact phones
    agent_assigned_phones = None
    if current_user.role == "agent":
        agent_contacts = db.query(models.Contact.phone).filter(models.Contact.assigned_user_id == current_user.id).all()
        agent_assigned_phones = set(p[0] for p in agent_contacts if p[0])
    # Query distinct customer phones capped by limit
    phones_query = db.query(models.ChatMessage.customer_phone).distinct()
    if agent_assigned_phones is not None:
        phones_query = phones_query.filter(models.ChatMessage.customer_phone.in_(agent_assigned_phones))

    distinct_phones = [p[0] for p in phones_query.all() if p[0]]
    if not distinct_phones:
        return []

    # Batch 1: Contacts map
    contacts = db.query(models.Contact).filter(models.Contact.phone.in_(distinct_phones)).all()
    contacts_map = {c.phone: c for c in contacts}

    # Batch 2: Unread count grouped by customer phone
    unread_counts_raw = (
        db.query(models.ChatMessage.customer_phone, func.count(models.ChatMessage.id))
        .filter(
            models.ChatMessage.customer_phone.in_(distinct_phones),
            models.ChatMessage.sender_type == "CUSTOMER",
            models.ChatMessage.is_read == False
        )
        .group_by(models.ChatMessage.customer_phone)
        .all()
    )
    unread_map = {p: cnt for p, cnt in unread_counts_raw}

    # Batch 3: Fetch recent messages to resolve latest message per phone
    # Subquery: get max id per customer_phone
    latest_ids_subq = (
        db.query(func.max(models.ChatMessage.id).label("max_id"))
        .filter(models.ChatMessage.customer_phone.in_(distinct_phones))
        .group_by(models.ChatMessage.customer_phone)
        .subquery()
    )
    latest_msgs = (
        db.query(models.ChatMessage)
        .join(latest_ids_subq, models.ChatMessage.id == latest_ids_subq.c.max_id)
        .all()
    )
    latest_msg_map = {m.customer_phone: m for m in latest_msgs}

    summaries = []
    for cust_phone in distinct_phones:
        contact = contacts_map.get(cust_phone)
        last_msg = latest_msg_map.get(cust_phone)
        unread = unread_map.get(cust_phone, 0)

        last_order_obj = (contact.custom_attributes or {}).get("last_order") if contact else None

        summaries.append(schemas.ChatConversationSummary(
            customer_phone=cust_phone,
            customer_name=contact.name if contact else "Customer",
            customer_city=contact.city if contact else None,
            total_orders=contact.total_orders if contact else 0,
            unread_count=unread,
            last_message_text=last_msg.text if last_msg else None,
            last_message_time=last_msg.created_at if last_msg else None,
            last_sender=last_msg.sender_type if last_msg else None,
            last_order=last_order_obj
        ))

    # Sort: most recent message first
    summaries.sort(key=lambda s: s.last_message_time or datetime.min, reverse=True)
    capped_limit = min(max(1, limit), 100)
    return summaries[offset:offset + capped_limit]


@router.get("/history/{phone}", response_model=List[schemas.ChatMessageResponse])
@router.get("/messages/{phone}", response_model=List[schemas.ChatMessageResponse])
def get_chat_history(
    phone: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves full chronological message history for a specific customer phone.
    Marks customer messages as read.
    Enforces record-level access check for agents.
    """
    try:
        clean_phone = normalize_phone(phone)
    except InvalidPhoneNumberError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Enforce record scope
    pii_service.verify_conversation_access(db, current_user, clean_phone)

    # Ensure any past marketing template dispatches from MessageLog are present in ChatMessage (batch checked)
    historical_logs = (
        db.query(models.MessageLog)
        .filter(
            models.MessageLog.recipient_phone == clean_phone,
            models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED", "READ"])
        )
        .all()
    )
    ids_to_check = [h.meta_message_id for h in historical_logs if h.meta_message_id]
    existing_ids = set()
    if ids_to_check:
        existing_ids = set(
            row[0] for row in db.query(models.ChatMessage.meta_message_id)
            .filter(models.ChatMessage.meta_message_id.in_(ids_to_check)).all()
        )
    to_add = []
    needed_templates = {h.template_name for h in historical_logs if h.meta_message_id and h.meta_message_id not in existing_ids and h.template_name}
    template_map = {}
    if needed_templates:
        tmpls = db.query(models.Template).filter(models.Template.template_name.in_(needed_templates)).all()
        template_map = {t.template_name: t.body_text for t in tmpls}
    for h_log in historical_logs:
        if h_log.meta_message_id and h_log.meta_message_id not in existing_ids:
            body = template_map.get(h_log.template_name)
            content = body if body else f"📢 WhatsApp Template: {h_log.template_name}"
            to_add.append(models.ChatMessage(
                customer_phone=clean_phone,
                sender_type="AGENT",
                message_type="template",
                text=content,
                meta_message_id=h_log.meta_message_id,
                status=h_log.status,
                is_read=True,
                created_at=h_log.created_at
            ))
    if to_add:
        db.add_all(to_add)
        db.commit()

    # Mark as read
    db.query(models.ChatMessage).filter(
        models.ChatMessage.customer_phone == clean_phone,
        models.ChatMessage.sender_type == "CUSTOMER",
        models.ChatMessage.is_read == False
    ).update({"is_read": True})
    db.commit()

    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.customer_phone == clean_phone)
        .order_by(models.ChatMessage.created_at.asc())
        .limit(200)
        .all()
    )
    return messages


@router.post("/send", response_model=schemas.ChatMessageResponse)
def send_agent_reply(
    payload: schemas.ChatSendMessageRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows authorized support users to send an outbound text reply to a customer's WhatsApp.
    Enforces DND/Opt-Out, Meta's 24-hour customer service window, support_send permission,
    and daily spending guardrails.
    """
    try:
        clean_phone = normalize_phone(payload.customer_phone)
    except InvalidPhoneNumberError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1. Verify support_send capability and record scope
    pii_service.verify_support_send_permission(db, current_user, clean_phone)

    # 2. Strict DND / Opt-Out Check
    is_opted_out = db.query(models.OptOut).filter(models.OptOut.phone == clean_phone).first()
    if is_opted_out:
        logger.warning(f"🚫 [Chat Blocked] Attempted outbound message to opted-out recipient {clean_phone} by '{current_user.username}'.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer {clean_phone} has opted out of WhatsApp messages (DND list). Outbound messages are prohibited."
        )

    # 3. Meta 24-Hour Customer Service Window Check
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    last_inbound_msg = (
        db.query(models.ChatMessage)
        .filter(
            models.ChatMessage.customer_phone == clean_phone,
            models.ChatMessage.sender_type == "CUSTOMER",
            models.ChatMessage.created_at >= twenty_four_hours_ago
        )
        .order_by(models.ChatMessage.created_at.desc())
        .first()
    )

    if config.WHATSAPP_API_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID and not last_inbound_msg:
        logger.warning(f"🚫 [Chat Service Window] Customer {clean_phone} is outside Meta's 24-hour service window.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outside Meta's 24-hour customer service window. Free-form text is prohibited; please initiate contact using an approved WhatsApp template."
        )

    # 4. Daily Send Limit Guardrail
    under_limit, count_today = check_daily_limit(db)
    if not under_limit:
        effective_limit = get_effective_daily_limit(db)
        logger.error(f"🚨 [BUDGET GUARD] Daily send limit ({effective_limit}) reached! Chat blocked.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Daily outbound message limit reached ({count_today}/{effective_limit}). Outbound message blocked."
        )

    # Dispatch via whatsapp_service
    res = send_whatsapp_free_text(clean_phone, payload.text)

    msg_id = res.get("message_id")
    status_str = "SENT" if res.get("status") in ["success", "success_simulated"] else "FAILED"

    chat_entry = models.ChatMessage(
        customer_phone=clean_phone,
        sender_type="AGENT",
        message_type="text",
        text=payload.text,
        meta_message_id=msg_id,
        status=status_str,
        is_read=True,
        assigned_user_id=current_user.id
    )
    db.add(chat_entry)

    # Also log in general message_logs table
    log_entry = models.MessageLog(
        recipient_phone=clean_phone,
        template_name="two_way_custom_chat",
        language="en",
        sender_user=current_user.username,
        status=status_str,
        meta_message_id=msg_id
    )
    db.add(log_entry)
    db.commit()
    db.refresh(chat_entry)

    return chat_entry
