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

    # Ensure broadcast recipients from MessageLog have chat records
    recent_broadcast_phones = (
        db.query(models.MessageLog.recipient_phone)
        .distinct()
        .order_by(desc(models.MessageLog.recipient_phone))
        .limit(100)
        .all()
    )
    for (b_phone,) in recent_broadcast_phones:
        if not b_phone:
            continue
        exists = db.query(models.ChatMessage).filter(models.ChatMessage.customer_phone == b_phone).first()
        if not exists:
            last_log = (
                db.query(models.MessageLog)
                .filter(models.MessageLog.recipient_phone == b_phone)
                .order_by(models.MessageLog.created_at.desc())
                .first()
            )
            if last_log:
                db.add(models.ChatMessage(
                    customer_phone=b_phone,
                    sender_type="AGENT",
                    message_type="TEMPLATE",
                    text=f"[Template: {last_log.template_name}]",
                    meta_message_id=last_log.meta_message_id,
                    status=last_log.status,
                    is_read=True,
                    created_at=last_log.created_at
                ))
    db.commit()

    # Query all distinct customer phones
    phones = (
        db.query(models.ChatMessage.customer_phone)
        .distinct()
        .all()
    )

    summaries = []
    for (cust_phone,) in phones:
        if not cust_phone:
            continue

        # Enforce agent scope: skip if not assigned to this agent
        if agent_assigned_phones is not None and cust_phone not in agent_assigned_phones:
            continue

        # Get contact info if available
        contact = db.query(models.Contact).filter(models.Contact.phone == cust_phone).first()

        # Unread incoming messages count
        unread = (
            db.query(func.count(models.ChatMessage.id))
            .filter(
                models.ChatMessage.customer_phone == cust_phone,
                models.ChatMessage.sender_type == "CUSTOMER",
                models.ChatMessage.is_read == False
            )
            .scalar()
        ) or 0

        # Latest message
        last_msg = (
            db.query(models.ChatMessage)
            .filter(models.ChatMessage.customer_phone == cust_phone)
            .order_by(desc(models.ChatMessage.created_at))
            .first()
        )

        summaries.append(schemas.ChatConversationSummary(
            customer_phone=cust_phone,
            customer_name=contact.name if contact else "Customer",
            customer_city=contact.city if contact else None,
            total_orders=contact.total_orders if contact else 0,
            unread_count=unread,
            last_message_text=last_msg.text if last_msg else None,
            last_message_time=last_msg.created_at if last_msg else None,
            last_sender=last_msg.sender_type if last_msg else None
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

    # Ensure any past marketing template dispatches from MessageLog are present in ChatMessage
    historical_logs = (
        db.query(models.MessageLog)
        .filter(
            models.MessageLog.recipient_phone == clean_phone,
            models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED", "READ"])
        )
        .all()
    )
    for h_log in historical_logs:
        if h_log.meta_message_id:
            exists = (
                db.query(models.ChatMessage)
                .filter(models.ChatMessage.meta_message_id == h_log.meta_message_id)
                .first()
            )
            if not exists:
                tmpl = db.query(models.Template).filter(models.Template.template_name == h_log.template_name).first()
                content = tmpl.body_text if tmpl and tmpl.body_text else f"📢 WhatsApp Template: {h_log.template_name}"
                db.add(models.ChatMessage(
                    customer_phone=clean_phone,
                    sender_type="AGENT",
                    message_type="template",
                    text=content,
                    meta_message_id=h_log.meta_message_id,
                    status=h_log.status,
                    is_read=True,
                    created_at=h_log.created_at
                ))
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
