"""
Webhook Service
Handles e-commerce store HMAC signature verification, cart events, and order completion processing.
"""

from datetime import datetime
import hashlib
import hmac
import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import config
import models
import schemas
from scheduler import schedule_cart_recovery

logger = logging.getLogger("webhook_service")


async def verify_webhook_request(request: Request, db: Session) -> models.User:
    """
    Authenticates incoming webhook requests via HMAC signature (X-Hub-Signature-256)
    or authorized Bearer token (admin/service role).
    """
    auth_header = request.headers.get("Authorization", "").strip()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if config.WEBHOOK_SECRET and signature:
        raw_body = await request.body()
        expected = "sha256=" + hmac.new(
            config.WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
        svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
        return svc or models.User(username=config.ECOM_SERVICE_USERNAME, is_active=True)

    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            user = auth.get_current_user(token=token, db=db)
            if user.role in {"admin", "service"}:
                return user
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook access requires a service account")
        except HTTPException as he:
            raise he
        except Exception:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: webhook requires a valid HMAC signature or service-account token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def process_cart_event(
    payload: schemas.CartEventPayload,
    idempotency_key: str,
    delay_seconds: int,
    db: Session
) -> dict:
    """
    Registers an abandoned cart event, idempotently records it, and schedules recovery.
    """
    existing_event = db.query(models.WebhookEvent).filter(
        models.WebhookEvent.idempotency_key == idempotency_key
    ).first()
    if existing_event:
        return {"status": "duplicate", "message": "Webhook event was already processed."}

    db.add(models.WebhookEvent(event_type="cart", idempotency_key=idempotency_key))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "message": "Webhook event was already processed."}

    is_opted_out = db.query(models.OptOut).filter(models.OptOut.phone == payload.customer_phone).first()
    if is_opted_out:
        db.commit()
        return {"status": "skipped", "message": "Customer is on Opt-Out / DND registry."}

    cart_ev = db.query(models.CartEvent).filter(models.CartEvent.cart_token == payload.cart_token).first()
    if not cart_ev:
        cart_ev = models.CartEvent(
            cart_token=payload.cart_token,
            customer_phone=payload.customer_phone,
            customer_name=payload.customer_name,
            cart_value=payload.cart_value,
            checkout_url=str(payload.checkout_url) if payload.checkout_url else None,
            items_summary=payload.items_summary,
            extra_data=payload.extra_data,
            status="ABANDONED"
        )
        db.add(cart_ev)
    else:
        cart_ev.customer_name = payload.customer_name or cart_ev.customer_name
        cart_ev.cart_value = payload.cart_value or cart_ev.cart_value
        cart_ev.checkout_url = str(payload.checkout_url) if payload.checkout_url else cart_ev.checkout_url
        cart_ev.items_summary = payload.items_summary or cart_ev.items_summary
        if payload.extra_data:
            cart_ev.extra_data = payload.extra_data
    db.commit()
    db.refresh(cart_ev)

    # Schedule standard 30-min recovery job
    schedule_cart_recovery(
        cart_token=payload.cart_token,
        customer_phone=payload.customer_phone,
        cart_value=payload.cart_value,
        cart_url=str(payload.checkout_url) if payload.checkout_url else None,
        customer_name=payload.customer_name,
        delay_seconds=delay_seconds
    )
    return {"status": "success", "message": "Cart event registered and recovery job scheduled."}
