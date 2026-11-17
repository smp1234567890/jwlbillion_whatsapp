import os
import uuid
from datetime import datetime, timedelta
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from database import get_db
import config
import models
import schemas
import auth
from whatsapp_service import (
    send_whatsapp_free_text,
    send_whatsapp_media,
    send_whatsapp_reaction,
    upload_media_to_meta,
    check_daily_limit,
    get_effective_daily_limit
)
from services.phone_service import normalize_phone, InvalidPhoneNumberError
from services import pii_service

logger = logging.getLogger("chat_router")

router = APIRouter(prefix="/api/chat", tags=["Two-Way Live Chat"])


@router.get("/conversations", response_model=List[schemas.ChatConversationSummary])
def list_conversations(
    limit: Optional[int] = Query(None, ge=1),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    support_only: bool = Query(False),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    High-performance paginated conversation threads query.
    Extracts the latest message per customer thread, contact info, and unread counts
    using single-pass database execution and composite indexes.
    """
    from sqlalchemy import text

    # Base filtering for agents (assigned contacts only)
    where_clauses = []
    params = {"offset": offset}

    if current_user.role == "agent":
        where_clauses.append("c.assigned_user_id = :agent_id")
        params["agent_id"] = current_user.id

    if unread_only:
        where_clauses.append("COALESCE(u.unread_count, 0) > 0")

    support_phone_clean = normalize_phone(config.SUPPORT_WHATSAPP_PHONE) if config.SUPPORT_WHATSAPP_PHONE else "+918888478888"

    if support_only:
        # Show conversations that belong to the dedicated customer support channel
        # or where customer_phone is the support phone itself
        where_clauses.append("(lm.channel = 'support' OR lm.customer_phone = :support_phone)")
        params["support_phone"] = support_phone_clean
    else:
        # Regular marketing live chat inbox excludes customer support and social channels (fb, ig)
        where_clauses.append("(lm.channel IS NULL OR lm.channel != 'support')")
        where_clauses.append("lm.customer_phone NOT LIKE 'fb_%'")
        where_clauses.append("lm.customer_phone NOT LIKE 'ig_%'")
        if support_phone_clean:
            where_clauses.append("lm.customer_phone != :support_phone")
            params["support_phone"] = support_phone_clean

    if search and search.strip():
        where_clauses.append("(c.name ILIKE :search OR lm.customer_phone ILIKE :search OR lm.text ILIKE :search)")
        params["search"] = f"%{search.strip()}%"

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    limit_sql = "LIMIT :limit" if limit is not None else ""
    if limit is not None:
        params["limit"] = limit

    query_str = f"""
    SELECT 
        lm.customer_phone,
        COALESCE(c.name, 'Customer') as customer_name,
        c.city as customer_city,
        COALESCE(c.total_orders, 0) as total_orders,
        COALESCE(u.unread_count, 0) as unread_count,
        lm.text as last_message_text,
        lm.created_at as last_message_time,
        lm.sender_type as last_sender,
        c.custom_attributes->'last_order' as last_order
    FROM (
        SELECT DISTINCT ON (customer_phone) 
            customer_phone, text, sender_type, created_at, id, channel
        FROM chat_messages
        ORDER BY customer_phone, created_at DESC, id DESC
    ) lm
    LEFT JOIN contacts c ON c.phone = lm.customer_phone
    LEFT JOIN (
        SELECT customer_phone, COUNT(*) as unread_count 
        FROM chat_messages 
        WHERE sender_type = 'CUSTOMER' AND is_read = false 
        GROUP BY customer_phone
    ) u ON u.customer_phone = lm.customer_phone
    {where_sql}
    ORDER BY lm.created_at DESC
    {limit_sql} OFFSET :offset;
    """

    rows = db.execute(text(query_str), params).fetchall()

    import json
    from services.lead_intent_service import analyze_conversation_interest

    # Fetch messages for all retrieved phones in a single batch query for fast analysis
    customer_phones = [r[0] for r in rows if r[0]]
    phone_messages_map = {p: [] for p in customer_phones}
    if customer_phones:
        all_msgs = (
            db.query(models.ChatMessage.customer_phone, models.ChatMessage.sender_type, models.ChatMessage.text, models.ChatMessage.created_at)
            .filter(models.ChatMessage.customer_phone.in_(customer_phones))
            .order_by(models.ChatMessage.customer_phone, models.ChatMessage.created_at.asc())
            .all()
        )
        for msg in all_msgs:
            phone_messages_map[msg[0]].append({
                "sender_type": msg[1],
                "text": msg[2],
                "created_at": msg[3]
            })

    summaries = []
    for r in rows:
        phone = r[0]
        last_order = r[8]
        if isinstance(last_order, str):
            try:
                last_order = json.loads(last_order)
            except Exception:
                last_order = None

        thread_msgs = phone_messages_map.get(phone, [])
        analysis = analyze_conversation_interest(thread_msgs)

        summaries.append(schemas.ChatConversationSummary(
            customer_phone=r[0],
            customer_name=r[1],
            customer_city=r[2],
            total_orders=r[3],
            unread_count=r[4],
            last_message_text=r[5],
            last_message_time=r[6],
            last_sender=r[7],
            last_order=last_order,
            is_client_initiated=analysis["is_client_initiated"],
            interest_level=analysis["interest_level"],
            interest_score=analysis["interest_score"],
            detected_signals=analysis["detected_signals"],
            inbound_count=analysis["inbound_count"]
        ))

    return summaries


@router.get("/analysis/{phone}")
def get_conversation_analysis(
    phone: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Detailed lead interest and conversation analysis for a specific chat thread.
    """
    if phone.startswith("fb_") or phone.startswith("ig_"):
        clean_phone = phone
    else:
        try:
            clean_phone = normalize_phone(phone)
        except InvalidPhoneNumberError as e:
            raise HTTPException(status_code=400, detail=str(e))

    pii_service.verify_conversation_access(db, current_user, clean_phone)
    from services.lead_intent_service import analyze_conversation_interest

    msgs = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.customer_phone == clean_phone)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    raw_msgs = [
        {"sender_type": m.sender_type, "text": m.text, "created_at": m.created_at}
        for m in msgs
    ]
    analysis = analyze_conversation_interest(raw_msgs)
    return {
        "customer_phone": clean_phone,
        **analysis
    }


@router.get("/lead-interest-report")
def get_lead_interest_report(
    interest: Optional[str] = Query(None, description="ALL, HIGHLY_INTERESTED, INTERESTED, CLIENT_LEADS"),
    called: Optional[str] = Query(None, description="ALL, YES, NO"),
    search: Optional[str] = Query(None),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dedicated reporting query for all chats analyzed for lead interest,
    initiation type, called status, and timestamps.
    """
    from sqlalchemy import text
    from services.lead_intent_service import analyze_conversation_interest

    # 1. Fetch all customer threads with messages
    query_str = """
    SELECT 
        lm.customer_phone,
        COALESCE(c.name, 'Customer') as customer_name,
        c.city as customer_city,
        c.total_orders,
        c.custom_attributes,
        c.created_at as contact_created_at,
        c.id as contact_id,
        lm.text as last_message_text,
        lm.created_at as last_message_time,
        lm.sender_type as last_sender
    FROM (
        SELECT DISTINCT ON (customer_phone) 
            customer_phone, text, sender_type, created_at, id
        FROM chat_messages
        ORDER BY customer_phone, created_at DESC, id DESC
    ) lm
    LEFT JOIN contacts c ON c.phone = lm.customer_phone
    ORDER BY lm.created_at DESC;
    """
    rows = db.execute(text(query_str)).fetchall()
    customer_phones = [r[0] for r in rows if r[0]]

    # 2. Batch fetch messages for thread analysis
    phone_messages_map = {p: [] for p in customer_phones}
    if customer_phones:
        all_msgs = (
            db.query(models.ChatMessage.customer_phone, models.ChatMessage.sender_type, models.ChatMessage.text, models.ChatMessage.created_at)
            .filter(models.ChatMessage.customer_phone.in_(customer_phones))
            .order_by(models.ChatMessage.customer_phone, models.ChatMessage.created_at.asc())
            .all()
        )
        for msg in all_msgs:
            phone_messages_map[msg[0]].append({
                "sender_type": msg[1],
                "text": msg[2],
                "created_at": msg[3]
            })

    results = []
    total_highly_interested = 0
    total_interested = 0
    total_client_initiated = 0
    total_called = 0

    for r in rows:
        phone = r[0]
        name = r[1]
        city = r[2]
        total_orders = r[3] or 0
        custom_attrs = r[4] or {}
        contact_created_at = r[5]
        contact_id = r[6]
        last_msg_text = r[7]
        last_msg_time = r[8]
        last_sender = r[9]

        thread_msgs = phone_messages_map.get(phone, [])
        analysis = analyze_conversation_interest(thread_msgs)

        called_info = custom_attrs.get("called_status") if isinstance(custom_attrs, dict) else {}
        is_called = bool(called_info.get("called")) if isinstance(called_info, dict) else False
        called_by = called_info.get("called_by") if isinstance(called_info, dict) else None
        called_at = called_info.get("called_at") if isinstance(called_info, dict) else None

        if analysis["interest_level"] == "HIGHLY_INTERESTED":
            total_highly_interested += 1
        elif analysis["interest_level"] == "INTERESTED":
            total_interested += 1

        if analysis["is_client_initiated"]:
            total_client_initiated += 1

        if is_called:
            total_called += 1

        # Apply Filters
        if interest and interest != "ALL":
            if interest == "HIGHLY_INTERESTED" and analysis["interest_level"] != "HIGHLY_INTERESTED":
                continue
            if interest == "INTERESTED" and analysis["interest_level"] != "INTERESTED":
                continue
            if interest == "CLIENT_LEADS" and not analysis["is_client_initiated"]:
                continue

        if called and called != "ALL":
            if called == "YES" and not is_called:
                continue
            if called == "NO" and is_called:
                continue

        if search and search.strip():
            s = search.strip().lower()
            match_name = name and s in name.lower()
            match_phone = phone and s in phone.lower()
            match_city = city and s in city.lower()
            match_signals = any(s in str(sig).lower() for sig in analysis["detected_signals"])
            if not (match_name or match_phone or match_city or match_signals):
                continue

        results.append({
            "contact_id": contact_id,
            "phone": phone,
            "name": name,
            "city": city,
            "total_orders": total_orders,
            "contact_created_at": contact_created_at.isoformat() if contact_created_at else None,
            "last_message_text": last_msg_text,
            "last_message_time": last_msg_time.isoformat() if last_msg_time else None,
            "last_sender": last_sender,
            "is_client_initiated": analysis["is_client_initiated"],
            "interest_level": analysis["interest_level"],
            "interest_score": analysis["interest_score"],
            "detected_signals": analysis["detected_signals"],
            "inbound_count": analysis["inbound_count"],
            "is_called": is_called,
            "called_by": called_by,
            "called_at": called_at
        })

    # Sort results:
    # If viewing ALL intents, sort strictly chronological by latest message received on top.
    # If filtered to specific interest (e.g. HIGHLY_INTERESTED or INTERESTED), prioritize highest interest score, then newest message.
    if not interest or interest == "ALL":
        results.sort(key=lambda x: (x["last_message_time"] or ""), reverse=True)
    else:
        results.sort(key=lambda x: (x["interest_score"], x["last_message_time"] or ""), reverse=True)

    return {
        "summary": {
            "total_leads": len(rows),
            "total_highly_interested": total_highly_interested,
            "total_interested": total_interested,
            "total_client_initiated": total_client_initiated,
            "total_called": total_called,
            "total_uncalled": max(0, len(rows) - total_called)
        },
        "records": results
    }


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
    if phone.startswith("fb_") or phone.startswith("ig_"):
        clean_phone = phone
    else:
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
    carousel_map = {}
    if needed_templates:
        tmpls = db.query(models.Template).filter(models.Template.template_name.in_(needed_templates)).all()
        template_map = {t.template_name: t.body_text for t in tmpls}
        carousel_map = {t.template_name: t.carousel_cards for t in tmpls if t.carousel_cards}
    for h_log in historical_logs:
        if h_log.meta_message_id and h_log.meta_message_id not in existing_ids:
            body = template_map.get(h_log.template_name)
            content = body if body else f"WhatsApp Template: {h_log.template_name}"
            cards = carousel_map.get(h_log.template_name)
            to_add.append(models.ChatMessage(
                customer_phone=clean_phone,
                sender_type="AGENT",
                message_type="template",
                text=content,
                carousel_cards=cards,
                meta_message_id=h_log.meta_message_id,
                status=h_log.status,
                is_read=True,
                created_at=h_log.created_at
            ))
    if to_add:
        db.add_all(to_add)
        db.commit()

    # Mark as read only if there are actually unread customer messages
    updated_count = db.query(models.ChatMessage).filter(
        models.ChatMessage.customer_phone == clean_phone,
        models.ChatMessage.sender_type == "CUSTOMER",
        models.ChatMessage.is_read == False
    ).update({"is_read": True}, synchronize_session=False)
    if updated_count > 0:
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
    Allows authorized support users to send an outbound text reply to a customer's WhatsApp or Facebook Messenger.
    Enforces DND/Opt-Out, Meta's 24-hour customer service window, support_send permission,
    and daily spending guardrails.
    """
    raw_phone = payload.customer_phone
    is_social = raw_phone.startswith("fb_") or raw_phone.startswith("ig_")

    if is_social:
        clean_phone = raw_phone
        recipient_id = raw_phone.replace("fb_", "").replace("ig_", "")
        from services.facebook_service import send_facebook_text_message
        res = send_facebook_text_message(recipient_id, payload.text)
        msg_id = res.get("message_id")
        status_str = "SENT" if res.get("status") == "success" else "FAILED"
    else:
        try:
            clean_phone = normalize_phone(raw_phone)
        except InvalidPhoneNumberError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 1. Verify support_send capability and record scope
        pii_service.verify_support_send_permission(db, current_user, clean_phone)

        # 2. Strict DND / Opt-Out Check
        is_opted_out = db.query(models.OptOut).filter(models.OptOut.phone == clean_phone).first()
        if is_opted_out:
            logger.warning(f"[Chat Blocked] Attempted outbound message to opted-out recipient {clean_phone} by '{current_user.username}'.")
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

        # Determine if this message is routed to/from the dedicated Support number
        support_phone_clean = normalize_phone(config.SUPPORT_WHATSAPP_PHONE) if config.SUPPORT_WHATSAPP_PHONE else "+918888478888"
        
        # Check if destination phone is support OR if channel is explicitly 'support' OR if latest message in thread was support
        latest_thread_msg = db.query(models.ChatMessage).filter(models.ChatMessage.customer_phone == clean_phone).order_by(models.ChatMessage.id.desc()).first()
        is_support_chat = (
            payload.channel == "support" or
            clean_phone == support_phone_clean or
            (latest_thread_msg and getattr(latest_thread_msg, "channel", None) == "support")
        )

        active_token = config.SUPPORT_WHATSAPP_API_TOKEN if (is_support_chat and config.SUPPORT_WHATSAPP_API_TOKEN) else config.WHATSAPP_API_TOKEN
        active_phone_id = config.SUPPORT_WHATSAPP_PHONE_NUMBER_ID if (is_support_chat and config.SUPPORT_WHATSAPP_PHONE_NUMBER_ID) else config.WHATSAPP_PHONE_NUMBER_ID

        if active_token and active_phone_id and not last_inbound_msg:
            logger.warning(f"[Chat Service Window] Customer {clean_phone} is outside Meta's 24-hour service window.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Outside Meta's 24-hour customer service window. Free-form text is prohibited; please initiate contact using an approved WhatsApp template."
            )

        # 4. Daily Send Limit Guardrail
        under_limit, count_today = check_daily_limit(db)
        if not under_limit:
            effective_limit = get_effective_daily_limit(db)
            logger.error(f"[BUDGET GUARD] Daily send limit ({effective_limit}) reached! Chat blocked.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Daily outbound message limit reached ({count_today}/{effective_limit}). Outbound message blocked."
            )

        # Dispatch via whatsapp_service using the dedicated credentials if support
        res = send_whatsapp_free_text(
            clean_phone,
            payload.text,
            sender_user=current_user.username,
            db=db,
            phone_number_id=active_phone_id,
            api_token=active_token
        )
        msg_id = res.get("message_id")
        status_str = "SENT" if res.get("status") in ["success", "success_simulated"] else "FAILED"

    chat_entry = models.ChatMessage(
        customer_phone=clean_phone,
        sender_type="AGENT",
        message_type="text",
        text=payload.text,
        meta_message_id=msg_id,
        channel="support" if is_support_chat else "general",
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


@router.post("/send-media", response_model=schemas.ChatMessageResponse)
async def send_chat_media_message(
    customer_phone: str = Form(...),
    media_type: str = Form(...),  # "image", "document", "video", "audio"
    caption: Optional[str] = Form(None),
    channel: Optional[str] = Form("general"),
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Uploads and sends media (document, image, video, audio) to a customer's WhatsApp.
    Enforces DND/Opt-Out, Meta's 24-hour customer service window, support_send permission,
    and daily spending guardrails.
    """
    try:
        clean_phone = normalize_phone(customer_phone)
    except InvalidPhoneNumberError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 1. Verify support_send capability and record scope
    pii_service.verify_support_send_permission(db, current_user, clean_phone)

    # 2. Strict DND / Opt-Out Check
    is_opted_out = db.query(models.OptOut).filter(models.OptOut.phone == clean_phone).first()
    if is_opted_out:
        logger.warning(f"[Chat Media Blocked] Attempted outbound media to opted-out recipient {clean_phone} by '{current_user.username}'.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer {clean_phone} has opted out of WhatsApp messages (DND list). Outbound media is prohibited."
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

    # Determine if this message is routed to/from the dedicated Support number
    support_phone_clean = normalize_phone(config.SUPPORT_WHATSAPP_PHONE) if config.SUPPORT_WHATSAPP_PHONE else "+918888478888"
    latest_thread_msg = db.query(models.ChatMessage).filter(models.ChatMessage.customer_phone == clean_phone).order_by(models.ChatMessage.id.desc()).first()
    is_support_chat = (
        channel == "support" or
        clean_phone == support_phone_clean or
        (latest_thread_msg and getattr(latest_thread_msg, "channel", None) == "support")
    )

    active_token = config.SUPPORT_WHATSAPP_API_TOKEN if (is_support_chat and config.SUPPORT_WHATSAPP_API_TOKEN) else config.WHATSAPP_API_TOKEN
    active_phone_id = config.SUPPORT_WHATSAPP_PHONE_NUMBER_ID if (is_support_chat and config.SUPPORT_WHATSAPP_PHONE_NUMBER_ID) else config.WHATSAPP_PHONE_NUMBER_ID

    if active_token and active_phone_id and not last_inbound_msg:
        logger.warning(f"[Chat Media Service Window] Customer {clean_phone} is outside Meta's 24-hour service window.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outside Meta's 24-hour customer service window. Free-form media is prohibited; please initiate contact using an approved WhatsApp template."
        )

    # 4. Daily Send Limit Guardrail
    under_limit, count_today = check_daily_limit(db)
    if not under_limit:
        effective_limit = get_effective_daily_limit(db)
        logger.error(f"[BUDGET GUARD] Daily send limit ({effective_limit}) reached! Chat media blocked.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Daily outbound message limit reached ({count_today}/{effective_limit}). Outbound media blocked."
        )

    # Normalize media type
    media_type_clean = media_type.lower().strip()
    if media_type_clean not in ["image", "document", "video", "audio"]:
        raise HTTPException(status_code=400, detail="Invalid media_type. Must be image, document, video, or audio.")

    # Read file contents and save locally to uploads
    file_bytes = await file.read()
    orig_filename = file.filename or f"upload_{uuid.uuid4().hex}"
    mime_type = file.content_type or "application/octet-stream"

    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    # Content-hash deduplication: check if identical file was already uploaded
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
    ext = os.path.splitext(orig_filename)[1].lower()
    existing_match = None
    try:
        for fname in os.listdir(upload_dir):
            if f"_{file_hash}" in fname or fname.startswith(f"hash_{file_hash}"):
                existing_match = fname
                break
    except Exception:
        pass

    if existing_match:
        saved_filename = existing_match
        logger.info(f"[Chat Media Deduplication] Reused existing upload: {saved_filename}")
    else:
        clean_base = os.path.splitext(orig_filename)[0].replace(" ", "_")[:24]
        saved_filename = f"hash_{file_hash}_{clean_base}{ext}"
        local_path = os.path.join(upload_dir, saved_filename)
        with open(local_path, "wb") as f_out:
            f_out.write(file_bytes)

    relative_media_url = f"/uploads/{saved_filename}"

    # Upload to Meta Cloud API to obtain media_id
    upload_res = upload_media_to_meta(
        file_bytes,
        mime_type,
        orig_filename,
        phone_number_id=active_phone_id,
        api_token=active_token
    )
    meta_media_id = upload_res.get("media_id")

    # Dispatch to customer via WhatsApp
    res = send_whatsapp_media(
        recipient_phone=clean_phone,
        media_type=media_type_clean,
        media_id=meta_media_id,
        caption=caption,
        filename=orig_filename,
        sender_user=current_user.username,
        db=db,
        phone_number_id=active_phone_id,
        api_token=active_token
    )

    msg_id = res.get("message_id")
    status_str = "SENT" if res.get("status") in ["success", "success_simulated"] else "FAILED"

    chat_entry = models.ChatMessage(
        customer_phone=clean_phone,
        sender_type="AGENT",
        message_type=media_type_clean,
        text=caption or f"[{media_type_clean.upper()}] {orig_filename}",
        media_url=relative_media_url,
        filename=orig_filename,
        meta_message_id=msg_id,
        channel="support" if is_support_chat else "general",
        status=status_str,
        is_read=True,
        assigned_user_id=current_user.id
    )
    db.add(chat_entry)

    log_entry = models.MessageLog(
        recipient_phone=clean_phone,
        template_name=f"media_{media_type_clean}",
        language="en",
        sender_user=current_user.username,
        status=status_str,
        meta_message_id=msg_id
    )
    db.add(log_entry)
    db.commit()
    db.refresh(chat_entry)

    return chat_entry


@router.post("/reaction")
def react_to_chat_message(
    payload: schemas.ChatReactionRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Applies or removes a reaction (thumbs up 👍 / thumbs down 👎) on a message in the chat.
    If the message has a Meta message ID, sends the reaction to WhatsApp via Meta Cloud API.
    """
    msg = db.query(models.ChatMessage).filter(models.ChatMessage.id == payload.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    target_emoji = (payload.emoji or "").strip()
    # Toggle off if same emoji was already clicked
    if msg.reaction == target_emoji:
        target_emoji = ""

    msg.reaction = target_emoji or None
    db.commit()
    db.refresh(msg)

    # If the message has an active WhatsApp wamid, send reaction to Meta API
    meta_result = None
    if msg.meta_message_id:
        support_phone_clean = normalize_phone(config.SUPPORT_WHATSAPP_PHONE) if config.SUPPORT_WHATSAPP_PHONE else "+918888478888"
        is_support_chat = (msg.customer_phone == support_phone_clean)
        active_token = config.SUPPORT_WHATSAPP_API_TOKEN if (is_support_chat and config.SUPPORT_WHATSAPP_API_TOKEN) else config.WHATSAPP_API_TOKEN
        active_phone_id = config.SUPPORT_WHATSAPP_PHONE_NUMBER_ID if (is_support_chat and config.SUPPORT_WHATSAPP_PHONE_NUMBER_ID) else config.WHATSAPP_PHONE_NUMBER_ID
        try:
            meta_result = send_whatsapp_reaction(
                recipient_phone=msg.customer_phone,
                target_meta_message_id=msg.meta_message_id,
                emoji=target_emoji,
                phone_number_id=active_phone_id,
                api_token=active_token
            )
        except Exception as e:
            logger.warning(f"Failed to sync reaction to Meta for message {msg.id}: {e}")

    return {
        "status": "success",
        "message_id": msg.id,
        "reaction": msg.reaction,
        "meta_result": meta_result
    }


@router.delete("/conversations/{phone}")
def delete_conversation(
    phone: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes all chat messages and historical logs for the given customer phone number.
    Only accessible by authorized users.
    """
    if phone.startswith("fb_") or phone.startswith("ig_"):
        clean_phone = phone
    else:
        try:
            clean_phone = normalize_phone(phone)
        except InvalidPhoneNumberError as e:
            raise HTTPException(status_code=400, detail=str(e))

    pii_service.verify_conversation_access(db, current_user, clean_phone)

    deleted_chat_count = db.query(models.ChatMessage).filter(
        models.ChatMessage.customer_phone == clean_phone
    ).delete(synchronize_session=False)

    deleted_log_count = db.query(models.MessageLog).filter(
        models.MessageLog.recipient_phone == clean_phone
    ).delete(synchronize_session=False)

    db.commit()
    return {
        "status": "success",
        "deleted_messages": deleted_chat_count,
        "deleted_logs": deleted_log_count,
        "phone": clean_phone
    }


@router.get("/stream")
async def chat_events_stream(
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events (SSE) endpoint for live two-way chat.
    Pushes instant incoming messages, status updates, and reactions directly to the browser
    eliminating the need for high-frequency polling.
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")
    try:
        user = auth.get_current_user(token=token, db=db)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

    from services.chat_broadcaster import chat_broadcaster
    import json

    async def event_generator():
        q = chat_broadcaster.subscribe()
        try:
            # Send initial connected ping
            yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15.0)
                    evt_name = payload.get("event", "message")
                    evt_data = json.dumps(payload.get("data", {}))
                    yield f"event: {evt_name}\ndata: {evt_data}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat comment to prevent proxy timeout
                    yield ": ping\n\n"
        finally:
            chat_broadcaster.unsubscribe(q)

    from starlette.responses import StreamingResponse
    import asyncio
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/register-device-token")
def register_device_token_endpoint(
    req: schemas.DeviceTokenRegisterRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registers or updates an FCM device token for push notifications.
    Associates the token with the authenticated agent/admin user.
    """
    from services.fcm_service import register_device_token
    token_record = register_device_token(
        db=db,
        token=req.token,
        user_id=current_user.id,
        platform=req.platform or "android"
    )
    return {"status": "ok", "message": "Device token registered successfully", "id": token_record.id if token_record else None}


@router.get("/analytics")
def get_chat_inbox_analytics(
    start_date: Optional[str] = Query(None, description="ISO timestamp or YYYY-MM-DD or YYYY-MM-DDTHH:MM"),
    end_date: Optional[str] = Query(None, description="ISO timestamp or YYYY-MM-DD or YYYY-MM-DDTHH:MM"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Live Chat / Inbox Analytics based on date and time range:
    - How many people sent us a message (unique inbound customers).
    - How many received an interactive template/menu.
    - How many received our reply (manual agent reply or quick reply).
    - Response rate, unreplied count, and detailed activity log.
    """
    from sqlalchemy import text

    now = datetime.utcnow()
    # Default: today 00:00:00 UTC to now if not provided
    def parse_datetime_safe(val, default_val):
        if not val:
            return default_val
        try:
            # ISO format: 2026-11-15T00:00:00.000Z or 2026-11-15T00:00 or 2026-11-15
            clean_val = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_val)
            # convert to naive UTC if offset-aware
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except Exception:
            return default_val

    start_dt = parse_datetime_safe(start_date, now.replace(hour=0, minute=0, second=0, microsecond=0))
    end_dt = parse_datetime_safe(end_date, now)

    params = {
        "start_dt": start_dt,
        "end_dt": end_dt
    }

    # Query 1: Find all unique inbound customer conversations within [start_dt, end_dt]
    # and accurately compute automated response time, manual response time, and customer turnaround time
    query_str = """
    WITH inbound_inquiries AS (
        SELECT 
            m.customer_phone,
            MIN(m.created_at) as first_inbound_time,
            MAX(m.created_at) as last_inbound_time,
            COUNT(*) as inbound_messages_count,
            (ARRAY_AGG(m.text ORDER BY m.created_at ASC))[1] as first_message_preview
        FROM chat_messages m
        WHERE m.sender_type = 'CUSTOMER'
          AND m.created_at >= :start_dt
          AND m.created_at <= :end_dt
        GROUP BY m.customer_phone
    ),
    outbound_after AS (
        SELECT 
            ii.customer_phone,
            -- First interactive message sent after or near the customer inquiry
            MIN(CASE 
                WHEN m.sender_type = 'AGENT' 
                 AND (m.text ILIKE '%Sent interactive%' OR m.message_type = 'interactive' OR m.text ILIKE '%interactive%')
                 AND m.created_at >= ii.first_inbound_time - INTERVAL '2 minutes'
                THEN m.created_at 
                ELSE NULL 
            END) as first_interactive_time,
            -- First reply sent by our team/bot (text, image, quick reply)
            MIN(CASE 
                WHEN m.sender_type = 'AGENT' 
                 AND (m.text NOT ILIKE '%Sent interactive%' AND m.message_type != 'interactive')
                 AND m.created_at >= ii.first_inbound_time
                THEN m.created_at 
                ELSE NULL 
            END) as first_reply_time,
            -- Any reply sent by our team/bot
            COUNT(CASE 
                WHEN m.sender_type = 'AGENT' 
                 AND (m.text NOT ILIKE '%Sent interactive%' AND m.message_type != 'interactive')
                 AND m.created_at >= ii.first_inbound_time
                THEN 1 
                ELSE NULL 
            END) as reply_count,
            -- Latest reply preview
            (ARRAY_AGG(m.text ORDER BY m.created_at DESC) FILTER (
                WHERE m.sender_type = 'AGENT' AND m.created_at >= ii.first_inbound_time
            ))[1] as last_reply_preview
        FROM inbound_inquiries ii
        JOIN chat_messages m ON m.customer_phone = ii.customer_phone
        GROUP BY ii.customer_phone
    ),
    turnaround_calc AS (
        -- Automated response time: bot menu or bot reply without assigned_user_id
        SELECT 
            cm.customer_phone,
            MIN(am.created_at - cm.created_at) as min_latency,
            MIN(CASE 
                WHEN am.assigned_user_id IS NULL OR am.text ILIKE '%Sent interactive%' OR am.message_type = 'interactive'
                THEN am.created_at - cm.created_at 
                ELSE NULL 
            END) as auto_latency,
            MIN(CASE 
                WHEN am.assigned_user_id IS NOT NULL AND am.text NOT ILIKE '%Sent interactive%' AND am.message_type != 'interactive'
                THEN am.created_at - cm.created_at 
                ELSE NULL 
            END) as manual_latency
        FROM chat_messages cm
        JOIN chat_messages am 
          ON am.customer_phone = cm.customer_phone 
         AND am.sender_type = 'AGENT' 
         AND am.created_at >= cm.created_at
        WHERE cm.sender_type = 'CUSTOMER'
          AND cm.created_at >= :start_dt
          AND cm.created_at <= :end_dt
        GROUP BY cm.customer_phone
    ),
    cust_wait_calc AS (
        -- Customer response time: how long customer took to respond after an agent/bot message
        SELECT 
            am.customer_phone,
            MIN(cm.created_at - am.created_at) as customer_reply_latency
        FROM chat_messages am
        JOIN chat_messages cm 
          ON cm.customer_phone = am.customer_phone 
         AND cm.sender_type = 'CUSTOMER' 
         AND cm.created_at >= am.created_at
        WHERE am.sender_type = 'AGENT'
          AND am.created_at >= (:start_dt - INTERVAL '24 hours')
          AND cm.created_at >= :start_dt
          AND cm.created_at <= :end_dt
        GROUP BY am.customer_phone
    )
    SELECT 
        ii.customer_phone,
        COALESCE(c.name, 'Customer') as customer_name,
        c.city as customer_city,
        ii.first_inbound_time,
        ii.last_inbound_time,
        ii.inbound_messages_count,
        ii.first_message_preview,
        oa.first_interactive_time,
        oa.first_reply_time,
        COALESCE(oa.reply_count, 0) as reply_count,
        oa.last_reply_preview,
        ROUND(EXTRACT(EPOCH FROM tc.min_latency) / 60.0, 1) as accurate_turnaround_mins,
        ROUND(EXTRACT(EPOCH FROM tc.auto_latency) / 60.0, 2) as auto_response_mins,
        ROUND(EXTRACT(EPOCH FROM tc.manual_latency) / 60.0, 1) as manual_response_mins,
        ROUND(EXTRACT(EPOCH FROM cwc.customer_reply_latency) / 60.0, 1) as customer_response_mins
    FROM inbound_inquiries ii
    LEFT JOIN contacts c ON c.phone = ii.customer_phone
    LEFT JOIN outbound_after oa ON oa.customer_phone = ii.customer_phone
    LEFT JOIN turnaround_calc tc ON tc.customer_phone = ii.customer_phone
    LEFT JOIN cust_wait_calc cwc ON cwc.customer_phone = ii.customer_phone
    ORDER BY ii.last_inbound_time DESC;
    """

    rows = db.execute(text(query_str), params).fetchall()

    total_inbound_people = len(rows)
    interactive_count = 0
    replied_count = 0
    total_response_time_seconds = 0
    measured_replies = 0

    items = []
    for r in rows:
        got_interactive = bool(r.first_interactive_time)
        got_reply = bool(r.first_reply_time or r.reply_count > 0)

        if got_interactive:
            interactive_count += 1
        if got_reply:
            replied_count += 1

        response_time_minutes = None
        if r.accurate_turnaround_mins is not None:
            response_time_minutes = float(r.accurate_turnaround_mins)
            total_response_time_seconds += (response_time_minutes * 60.0)
            measured_replies += 1
        elif r.first_reply_time and r.first_inbound_time:
            diff_secs = (r.first_reply_time - r.first_inbound_time).total_seconds()
            if diff_secs >= 0:
                response_time_minutes = round(diff_secs / 60.0, 1)
                total_response_time_seconds += diff_secs
                measured_replies += 1

        items.append({
            "customer_phone": r.customer_phone,
            "customer_name": r.customer_name,
            "customer_city": r.customer_city,
            "first_inbound_time": r.first_inbound_time.isoformat() if r.first_inbound_time else None,
            "last_inbound_time": r.last_inbound_time.isoformat() if r.last_inbound_time else None,
            "inbound_messages_count": r.inbound_messages_count,
            "first_message_preview": r.first_message_preview,
            "got_interactive": got_interactive,
            "interactive_time": r.first_interactive_time.isoformat() if r.first_interactive_time else None,
            "got_reply": got_reply,
            "reply_time": r.first_reply_time.isoformat() if r.first_reply_time else None,
            "reply_count": r.reply_count,
            "response_time_minutes": response_time_minutes,
            "auto_response_time_minutes": float(r.auto_response_mins) if r.auto_response_mins is not None else None,
            "manual_response_time_minutes": float(r.manual_response_mins) if r.manual_response_mins is not None else None,
            "customer_response_time_minutes": float(r.customer_response_mins) if r.customer_response_mins is not None else None,
            "last_reply_preview": r.last_reply_preview
        })

    unreplied_count = total_inbound_people - replied_count
    response_rate = round((replied_count / total_inbound_people * 100), 1) if total_inbound_people > 0 else 0.0
    interactive_rate = round((interactive_count / total_inbound_people * 100), 1) if total_inbound_people > 0 else 0.0
    avg_response_time_minutes = round((total_response_time_seconds / measured_replies / 60.0), 1) if measured_replies > 0 else 0.0

    return {
        "time_range": {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat()
        },
        "summary": {
            "total_inbound_people": total_inbound_people,
            "interactive_count": interactive_count,
            "interactive_rate": interactive_rate,
            "replied_count": replied_count,
            "unreplied_count": unreplied_count,
            "response_rate": response_rate,
            "avg_response_time_minutes": avg_response_time_minutes
        },
        "contacts": items
    }




