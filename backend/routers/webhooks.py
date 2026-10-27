"""
Webhooks Router
Handles incoming e-commerce webhooks (cart-event, order-completed) with HMAC security,
and Meta WhatsApp Cloud API webhooks (verification, inbound message processing, DND triggers).
"""

from datetime import datetime
import hashlib
import hmac
import logging
from typing import Optional, Dict, Any
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import config
import models
import schemas
from database import get_db
from rate_limiter import limiter
from scheduler import schedule_cart_recovery
from services.phone_service import normalize_phone, InvalidPhoneNumberError
from services.policy_service import record_consent, revoke_consent
from services.audit_service import record_audit_event, hash_phone
from whatsapp_service import send_whatsapp_template, download_meta_media

logger = logging.getLogger("webhooks_router")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

OPT_OUT_KEYWORDS = {
    "stop", "unsubscribe", "dnd", "cancel",
    "બંધ", "બંધ કરો", "સંદેશા બંધ કરો",  # Gujarati
    "रोको", "बंद करो", "मैसेज बंद करो"      # Hindi
}

OPT_IN_KEYWORDS = {
    "yes", "start", "agree", "subscribe", "y", "haan",
    "હા", "હું સંમત છું", "સંમત",  # Gujarati
    "हाँ", "स्वीकार", "सहमत"      # Hindi
}


import base64

async def get_webhook_authenticated_user(
    request: Request,
    db: Session = Depends(get_db)
) -> models.User:
    """
    Validates e-commerce HMAC signatures for external requests.
    Supports standard X-Hub-Signature-256 (hex) and Shopify X-Shopify-Hmac-Sha256 (base64).
    Missing or invalid signatures are recorded in WebhookEvent and rejected with HTTP 401.
    """
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("x-correlation-id") or str(uuid.uuid4())
    raw_sig = request.headers.get("X-Hub-Signature-256") or request.headers.get("x-hub-signature-256") or ""
    shopify_sig = request.headers.get("X-Shopify-Hmac-Sha256") or request.headers.get("x-shopify-hmac-sha256") or ""

    sig_clean = raw_sig.lower().strip()
    if sig_clean.startswith("sha256="):
        sig_clean = sig_clean[7:].strip()

    # 1. Allow Bearer JWT Token from logged-in user account or webhook secret
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if config.WEBHOOK_SECRET and hmac.compare_digest(token, config.WEBHOOK_SECRET):
            svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
            return svc or models.User(username=config.ECOM_SERVICE_USERNAME, is_active=True)
        try:
            jwt_data = auth.decode_access_token(token)
            if jwt_data and "sub" in jwt_data:
                user = db.query(models.User).filter(models.User.username == jwt_data["sub"]).first()
                if user and user.is_active:
                    return user
        except Exception:
            pass

    # 2. Require valid HMAC signature (Shopify base64 or standard hex)
    def _record_failure():
        try:
            failed_event = models.WebhookEvent(
                source="store",
                event_type="store_auth_failure",
                external_event_id=None,
                idempotency_key=f"auth_failure:{correlation_id}",
                hmac_validated=False,
                correlation_id=correlation_id,
                received_at=datetime.utcnow()
            )
            db.add(failed_event)
            db.commit()
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            logger.warning(f"Note: Webhook audit record could not be persisted: {e}")

    secret = (config.WEBHOOK_SECRET or "").strip()
    if not secret:
        logger.warning("[Webhook Security] Store webhook rejected: WEBHOOK_SECRET is not configured.")
        _record_failure()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook secret not configured on server.",
            headers={"WWW-Authenticate": "HMAC-SHA256"}
        )

    raw_body = await request.body()

    # Check Shopify Base64 HMAC signature first if present
    if shopify_sig:
        computed_b64 = base64.b64encode(
            hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()
        ).decode().strip()
        if hmac.compare_digest(computed_b64, shopify_sig.strip()):
            svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
            return svc or models.User(username=config.ECOM_SERVICE_USERNAME, is_active=True)
        else:
            logger.warning("[Webhook Security] Shopify HMAC signature mismatch.")
            _record_failure()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Shopify HMAC signature",
                headers={"WWW-Authenticate": "Shopify-HMAC-SHA256"}
            )

    # Check Standard Hex HMAC signature
    if sig_clean:
        computed_hex = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest().lower()
        if hmac.compare_digest(computed_hex, sig_clean):
            svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
            return svc or models.User(username=config.ECOM_SERVICE_USERNAME, is_active=True)
        else:
            logger.warning("[Webhook Security] Hex HMAC signature mismatch.")
            _record_failure()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing HMAC signature",
                headers={"WWW-Authenticate": "HMAC-SHA256"}
            )

    logger.warning("[Webhook Security] Store webhook rejected: missing signature or bearer token.")
    _record_failure()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication. Provide 'Authorization: Bearer <token>', 'X-Shopify-Hmac-Sha256', or 'X-Hub-Signature-256'.",
        headers={"WWW-Authenticate": "Bearer, Shopify-HMAC-SHA256, HMAC-SHA256"}
    )


async def get_sync_webhook_authenticated_user(
    request: Request,
    db: Session = Depends(get_db)
) -> models.User:
    """
    Flexible authenticator for inbound external customer sync.
    Accepts:
    1. Header X-API-Key: <WEBHOOK_SECRET>
    2. Query param ?api_key=<WEBHOOK_SECRET>
    3. Header Authorization: Bearer <WEBHOOK_SECRET> or valid JWT Bearer token
    4. Header X-Shopify-Hmac-Sha256 (Base64 HMAC)
    5. Header X-Hub-Signature-256 (Hex HMAC)
    """
    secret = (config.WEBHOOK_SECRET or "").strip()

    # 1. API Key Header
    api_key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
    if api_key and secret and hmac.compare_digest(api_key.strip(), secret):
        svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
        return svc or models.User(username=config.ECOM_SERVICE_USERNAME, role="admin", is_active=True)

    # 2. Query param api_key
    query_key = request.query_params.get("api_key")
    if query_key and secret and hmac.compare_digest(query_key.strip(), secret):
        svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
        return svc or models.User(username=config.ECOM_SERVICE_USERNAME, role="admin", is_active=True)

    # 3. Authorization header
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if secret and hmac.compare_digest(token, secret):
            svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
            return svc or models.User(username=config.ECOM_SERVICE_USERNAME, role="admin", is_active=True)
        try:
            jwt_data = auth.decode_access_token(token)
            if jwt_data and "sub" in jwt_data:
                user = db.query(models.User).filter(models.User.username == jwt_data["sub"]).first()
                if user and user.is_active:
                    return user
        except Exception:
            pass

    # 4. Shopify Base64 HMAC signature
    shopify_sig = request.headers.get("X-Shopify-Hmac-Sha256") or request.headers.get("x-shopify-hmac-sha256")
    if shopify_sig and secret:
        raw_body = await request.body()
        computed_b64 = base64.b64encode(hmac.new(secret.encode(), raw_body, hashlib.sha256).digest()).decode().strip()
        if hmac.compare_digest(computed_b64, shopify_sig.strip()):
            svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
            return svc or models.User(username=config.ECOM_SERVICE_USERNAME, role="admin", is_active=True)

    # 5. Standard Hex HMAC-SHA256 signature
    raw_sig = request.headers.get("X-Hub-Signature-256") or request.headers.get("x-hub-signature-256") or ""
    sig_clean = raw_sig.lower().strip()
    if sig_clean.startswith("sha256="):
        sig_clean = sig_clean[7:].strip()
    if sig_clean and secret:
        raw_body = await request.body()
        computed_hex = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest().lower()
        if hmac.compare_digest(computed_hex, sig_clean):
            svc = db.query(models.User).filter(models.User.username == config.ECOM_SERVICE_USERNAME).first()
            return svc or models.User(username=config.ECOM_SERVICE_USERNAME, role="admin", is_active=True)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized. Provide valid X-API-Key, Bearer token, X-Shopify-Hmac-Sha256, or X-Hub-Signature-256.",
        headers={"WWW-Authenticate": "ApiKey, Bearer, Shopify-HMAC-SHA256, HMAC-SHA256"}
    )


def extract_cart_data(data: Dict[str, Any]) -> schemas.CartEventPayload:
    """
    Extracts CartEventPayload from either our native schema or raw Shopify checkout payloads.
    """
    if "cart_token" in data and "customer_phone" in data:
        return schemas.CartEventPayload(**data)

    # Handle Shopify Checkout payload
    cart_token = str(data.get("token") or data.get("cart_token") or data.get("id") or "")
    customer = data.get("customer") or {}
    billing_addr = data.get("billing_address") or {}
    shipping_addr = data.get("shipping_address") or {}

    phone_raw = (
        data.get("phone")
        or customer.get("phone")
        or billing_addr.get("phone")
        or shipping_addr.get("phone")
        or data.get("customer_phone")
    )

    from services.phone_service import is_valid_phone
    if not phone_raw or not is_valid_phone(str(phone_raw)):
        # Shopify test notifications send dummy phones like '555-555-BILL' or empty
        phone_raw = "+919999999999"

    first_name = (
        customer.get("first_name")
        or billing_addr.get("first_name")
        or data.get("first_name")
    )
    last_name = (
        customer.get("last_name")
        or billing_addr.get("last_name")
        or data.get("last_name")
    )
    name_combo = f"{first_name or ''} {last_name or ''}".strip() or data.get("customer_name")

    total_price = (
        data.get("total_price")
        or data.get("subtotal_price")
        or data.get("cart_value")
        or 0.0
    )
    try:
        cart_value = float(total_price)
    except (ValueError, TypeError):
        cart_value = 0.0

    line_items_raw = data.get("line_items") or []
    items = []
    for item in line_items_raw:
        if isinstance(item, dict):
            items.append({
                "item": item.get("title") or item.get("name") or "Product",
                "quantity": item.get("quantity", 1),
                "price": item.get("price", 0.0)
            })

    delivery_addr = billing_addr.get("address1") or shipping_addr.get("address1") or data.get("delivery_address")

    return schemas.CartEventPayload(
        cart_token=cart_token or str(uuid.uuid4()),
        customer_phone=str(phone_raw),
        cart_value=cart_value,
        items=items,
        customer_name=name_combo or None,
        first_name=first_name or None,
        delivery_address=delivery_addr or None,
        extra_data={"shopify_source": True, "raw_id": data.get("id")}
    )


@router.post("/cart-event", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("60/minute")
async def receive_cart_webhook(
    request: Request,
    raw_payload: Dict[str, Any] = Body(...),
    delay_seconds: Optional[int] = 0,
    current_user: models.User = Depends(get_webhook_authenticated_user),
    db: Session = Depends(get_db)
):
    payload = extract_cart_data(raw_payload)
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    external_event_id = str(payload.cart_token)
    idempotency_key = request.headers.get("X-Idempotency-Key") or f"cart:{payload.cart_token}"

    existing_event = db.query(models.WebhookEvent).filter(
        (models.WebhookEvent.idempotency_key == idempotency_key) |
        ((models.WebhookEvent.source == "store") & (models.WebhookEvent.external_event_id == external_event_id) & (models.WebhookEvent.hmac_validated == True))
    ).first()
    if existing_event:
        return {"status": "duplicate", "message": "Webhook event was already processed."}

    db.add(models.WebhookEvent(
        source="store",
        event_type="cart",
        external_event_id=external_event_id,
        idempotency_key=idempotency_key,
        hmac_validated=True,
        correlation_id=correlation_id,
        received_at=datetime.utcnow()
    ))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "message": "Webhook event was already processed."}

    is_opted_out = db.query(models.OptOut).filter(models.OptOut.phone == payload.customer_phone).first()
    if is_opted_out:
        return {"status": "ignored", "reason": "Customer is on Opt-Out / DND list"}

    extra_payload = dict(payload.extra_data or {})
    if payload.first_name:
        extra_payload.setdefault("first_name", payload.first_name)
    if payload.customer_name:
        extra_payload.setdefault("customer_name", payload.customer_name)
    if payload.delivery_address:
        extra_payload.setdefault("delivery_address", payload.delivery_address)

    resolved_cust_name = payload.first_name or payload.customer_name or "Valued Customer"

    cart_record = models.CartEvent(
        cart_token=payload.cart_token,
        customer_phone=payload.customer_phone,
        cart_value=payload.cart_value,
        items=payload.items,
        extra_data=extra_payload,
        status="PENDING",
        authenticated_user=current_user.username
    )
    db.add(cart_record)
    db.commit()
    db.refresh(cart_record)

    try:
        from services.policy_service import record_consent
        record_consent(
            db=db,
            phone=payload.customer_phone,
            source="store_checkout",
            proof_details=f"Cart event token {payload.cart_token} from store checkout"
        )
    except Exception as consent_err:
        logger.warning(f"Could not record consent for cart event {payload.customer_phone}: {consent_err}")

    active_cart_flow = db.query(models.WorkflowFlow).filter(
        models.WorkflowFlow.trigger_type == "ABANDONED_CART",
        models.WorkflowFlow.is_active == True
    ).first()

    workflow_session_id = None
    wf_sess = None
    skipped_due_to_min_cart = False
    if active_cart_flow:
        flow_nodes = active_cart_flow.nodes or []
        trigger_n = next((n for n in flow_nodes if n.get("type") == "trigger"), None)
        min_thresh = None
        if trigger_n and isinstance(trigger_n.get("data"), dict):
            min_thresh = trigger_n["data"].get("min_cart_value")
        if min_thresh is None and isinstance(active_cart_flow.trigger_config, dict):
            min_thresh = active_cart_flow.trigger_config.get("min_cart_value")

        if min_thresh is not None:
            try:
                if float(payload.cart_value) < float(min_thresh):
                    skipped_due_to_min_cart = True
            except (ValueError, TypeError):
                pass

        if not skipped_due_to_min_cart:
            items_summary = ", ".join([item.get("item", "Namkeen Item") for item in (payload.items or [])]) if payload.items else "Special Jewelry & Premium Collection"
            state_data = {
                "cart_token": payload.cart_token,
                "cart_value": payload.cart_value,
                "customer_name": resolved_cust_name,
                "items_summary": items_summary,
                "extra_data": extra_payload,
                "sender_user": current_user.username
            }
            for k, v in extra_payload.items():
                state_data.setdefault(k, str(v))

            from scheduler import start_workflow_session
            # Anti-duplication guard: check if customer already has an active session in this flow
            existing_sess = db.query(models.WorkflowSession).filter(
                models.WorkflowSession.flow_id == active_cart_flow.id,
                models.WorkflowSession.customer_phone == payload.customer_phone,
                models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"])
            ).first()
            if existing_sess:
                curr_state = dict(existing_sess.state_data or {})
                curr_state.update(state_data)
                existing_sess.state_data = curr_state
                db.commit()
                wf_sess = existing_sess
                workflow_session_id = wf_sess.id
                logger.info(f"[Cart Event] Customer {payload.customer_phone} already enrolled in session #{wf_sess.id} ({wf_sess.status}). State updated.")
            else:
                wf_sess = start_workflow_session(flow_id=active_cart_flow.id, customer_phone=payload.customer_phone, state_data=state_data, db=db)
                if wf_sess:
                    workflow_session_id = wf_sess.id

    eff_delay = delay_seconds if delay_seconds is not None else 0
    if not active_cart_flow and not skipped_due_to_min_cart:
        schedule_cart_recovery(cart_event_id=cart_record.id, delay_seconds=eff_delay)

    if skipped_due_to_min_cart:
        msg_detail = f"Cart event recorded, but recovery workflow skipped: cart value (₹{payload.cart_value}) is below minimum threshold (₹{min_thresh})."
    elif workflow_session_id:
        msg_detail = f"Multi-step journey enrolled (Session #{workflow_session_id})"
    elif eff_delay <= 0:
        msg_detail = "WhatsApp message dispatched immediately"
    else:
        msg_detail = f"WhatsApp message scheduled in {eff_delay}s"

    return {
        "status": "received",
        "cart_event_id": cart_record.id,
        "workflow_session_id": workflow_session_id,
        "session_status": wf_sess.status if wf_sess else None,
        "session_current_node": wf_sess.current_node_id if wf_sess else None,
        "session_history": wf_sess.history if wf_sess else None,
        "step_result": getattr(wf_sess, "latest_step_result", None),
        "skipped_min_cart": skipped_due_to_min_cart,
        "scheduled_in_seconds": eff_delay,
        "authenticated_as": current_user.username,
        "message": msg_detail
    }


@router.post("/order-completed")
@limiter.limit("60/minute")
async def receive_order_completed_webhook(
    request: Request,
    raw_payload: Dict[str, Any] = Body(...),
    cart_token: Optional[str] = None,
    customer_phone: Optional[str] = None,
    current_user: models.User = Depends(get_webhook_authenticated_user),
    db: Session = Depends(get_db)
):
    # Extract token and phone from native payload or Shopify order payload
    customer = raw_payload.get("customer") or {}
    billing_addr = raw_payload.get("billing_address") or {}
    shipping_addr = raw_payload.get("shipping_address") or {}

    token = (
        raw_payload.get("cart_token")
        or raw_payload.get("checkout_token")
        or raw_payload.get("token")
        or str(raw_payload.get("id", ""))
        or cart_token
    )
    raw_phone = (
        raw_payload.get("customer_phone")
        or raw_payload.get("phone")
        or customer.get("phone")
        or billing_addr.get("phone")
        or shipping_addr.get("phone")
        or customer_phone
    )

    from services.phone_service import is_valid_phone
    if not raw_phone or not is_valid_phone(str(raw_phone)):
        # Fallback for Shopify dummy test notifications (e.g. '555-555-BILL')
        raw_phone = "+919999999999"

    if not token:
        token = str(uuid.uuid4())

    try:
        clean_phone = normalize_phone(raw_phone)
    except InvalidPhoneNumberError as pe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid customer_phone: {pe}"
        )

    cart_token = token
    order_id = str(raw_payload.get("id") or cart_token)
    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    external_event_id = f"order:{cart_token}"
    idempotency_key = request.headers.get("X-Idempotency-Key") or f"order:{cart_token}"

    existing_event = db.query(models.WebhookEvent).filter(
        (models.WebhookEvent.idempotency_key == idempotency_key) |
        ((models.WebhookEvent.source == "store") & (models.WebhookEvent.external_event_id == external_event_id) & (models.WebhookEvent.hmac_validated == True))
    ).first()
    if existing_event:
        return {"status": "duplicate", "message": "Webhook event was already processed."}

    db.add(models.WebhookEvent(
        source="store",
        event_type="order",
        external_event_id=external_event_id,
        idempotency_key=idempotency_key,
        hmac_validated=True,
        correlation_id=correlation_id,
        received_at=datetime.utcnow()
    ))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "message": "Webhook event was already processed."}

    # 1. Extract detailed order data (Shopify & native)
    line_items_raw = raw_payload.get("line_items") or []
    ordered_items = []
    item_titles = []
    for item in line_items_raw:
        if isinstance(item, dict):
            title = item.get("title") or item.get("name") or "Product"
            qty = item.get("quantity") or 1
            price = item.get("price") or 0.0
            ordered_items.append({
                "title": title,
                "quantity": qty,
                "price": price,
                "sku": item.get("sku") or ""
            })
            item_titles.append(f"{qty}x {title}" if qty > 1 else title)

    order_number = (
        raw_payload.get("order_number")
        or raw_payload.get("name")
        or raw_payload.get("id")
        or ""
    )
    order_total = (
        raw_payload.get("total_price")
        or raw_payload.get("current_total_price")
        or raw_payload.get("total")
        or 0.0
    )
    currency = raw_payload.get("currency") or "INR"
    order_summary_text = ", ".join(item_titles[:3]) + (f" (+{len(item_titles) - 3} more)" if len(item_titles) > 3 else "")

    # Customer Name / Email fallbacks from order
    order_customer_name = None
    if isinstance(customer, dict):
        first = customer.get("first_name", "")
        last = customer.get("last_name", "")
        order_customer_name = f"{first} {last}".strip() or customer.get("name")
    if not order_customer_name and isinstance(shipping_addr, dict):
        order_customer_name = f"{shipping_addr.get('first_name', '')} {shipping_addr.get('last_name', '')}".strip()

    order_customer_email = customer.get("email") if isinstance(customer, dict) else raw_payload.get("email")

    # Update contact order statistics and order metadata
    contact = db.query(models.Contact).filter(models.Contact.phone == clean_phone).first()
    order_now = datetime.utcnow()
    last_order_info = {
        "order_id": str(order_id),
        "order_number": str(order_number),
        "total_price": float(order_total) if order_total else 0.0,
        "currency": currency,
        "items_summary": order_summary_text or "Order Placed",
        "items": ordered_items,
        "ordered_at": order_now.isoformat()
    }

    if not contact:
        contact = models.Contact(
            phone=clean_phone,
            name=order_customer_name[:100] if order_customer_name else None,
            email=order_customer_email[:120] if order_customer_email else None,
            city=shipping_addr.get("city") if isinstance(shipping_addr, dict) else None,
            total_orders=1,
            last_order_date=order_now,
            custom_attributes={
                "last_order": last_order_info,
                "last_order_items": order_summary_text or "Order Placed",
                "last_order_total": f"{currency} {order_total}" if order_total else ""
            }
        )
        db.add(contact)
    else:
        contact.total_orders = (contact.total_orders or 0) + 1
        contact.last_order_date = order_now
        if order_customer_name and not contact.name:
            contact.name = order_customer_name[:100]
        if order_customer_email and not contact.email:
            contact.email = order_customer_email[:120]
        if isinstance(shipping_addr, dict) and shipping_addr.get("city") and not contact.city:
            contact.city = shipping_addr.get("city")[:100]

        attrs = dict(contact.custom_attributes or {})
        attrs["last_order"] = last_order_info
        attrs["last_order_items"] = order_summary_text or "Order Placed"
        attrs["last_order_total"] = f"{currency} {order_total}" if order_total else ""
        contact.custom_attributes = attrs

    try:
        from services.policy_service import record_consent
        record_consent(
            db=db,
            phone=clean_phone,
            source="store_checkout",
            proof_details=f"Order completed for cart_token {cart_token}"
        )
    except Exception as consent_err:
        logger.warning(f"Could not record consent on order completion for {clean_phone}: {consent_err}")

    # 2. Check Order Milestone (e.g. 5th, 10th order VIP reward)
    milestone_triggered = None
    if contact.total_orders in [5, 10, 20]:
        milestone = contact.total_orders
        coupon = f"VIP{milestone}"
        disc = db.query(models.DiscountCode).filter(models.DiscountCode.code == coupon).first()
        if not disc:
            disc = models.DiscountCode(
                code=coupon,
                discount_type="PERCENT",
                discount_value=15.0 if milestone >= 10 else 10.0,
                max_uses=1000,
                is_active=True
            )
            db.add(disc)

        send_whatsapp_template(
            recipient_phone=clean_phone,
            template_name="milestone_reward_offer",
            language="en",
            parameters={
                "name": contact.name or "Valued Customer",
                "milestone": str(milestone),
                "coupon": coupon
            },
            idempotency_key=f"order_milestone_{clean_phone}_{order_id}",
            purpose="marketing"
        )
        milestone_triggered = f"Milestone {milestone}th order reward dispatched with coupon {coupon}"
        logger.info(f"[MILESTONE REWARD] Customer {clean_phone} reached order #{milestone}! Sent coupon {coupon}")

    # 3. Mark cart as RECOVERED if associated with a pending cart event
    cart = db.query(models.CartEvent).filter(
        models.CartEvent.cart_token == cart_token,
        models.CartEvent.customer_phone.in_([clean_phone, customer_phone or clean_phone])
    ).first()

    if cart:
        cart.status = "RECOVERED"
        db.commit()
        return {
            "status": "success",
            "message": f"Cart {cart_token} marked as RECOVERED. Recovery message cancelled.",
            "milestone": milestone_triggered,
            "total_orders": contact.total_orders
        }
    
    db.commit()
    return {
        "status": "success",
        "message": f"Order completion recorded. Total customer orders: {contact.total_orders}",
        "milestone": milestone_triggered,
        "total_orders": contact.total_orders
    }


def process_customer_sync(payload: Dict[str, Any], current_user: models.User, db: Session) -> Dict[str, Any]:
    """
    Core sync engine to create or update a customer contact from external platforms.
    Extracts standard CRM fields, normalizes phone to canonical E.164, and
    persists all extra arbitrary fields in the custom_attributes JSON dictionary.
    """
    import re
    from services.phone_service import is_valid_phone

    # Log incoming keys to aid debugging
    logger.info(f"[Customer Webhook Received] Payload keys: {list(payload.keys())}")

    # If payload is wrapped under 'customer', unwrap or merge it
    cust = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}

    default_addr = payload.get("default_address") or cust.get("default_address") or {}
    billing_addr = payload.get("billing_address") or cust.get("billing_address") or {}
    shipping_addr = payload.get("shipping_address") or cust.get("shipping_address") or {}
    addresses = payload.get("addresses") or cust.get("addresses") or []

    # 1. Primary phone fields
    phone_candidates = [
        payload.get("phone"),
        payload.get("phone_number"),
        payload.get("mobile"),
        payload.get("customer_phone"),
        payload.get("telephone"),
        payload.get("contact_number"),
        cust.get("phone"),
        cust.get("phone_number"),
        cust.get("mobile"),
        (default_addr.get("phone") if isinstance(default_addr, dict) else None),
        (billing_addr.get("phone") if isinstance(billing_addr, dict) else None),
        (shipping_addr.get("phone") if isinstance(shipping_addr, dict) else None),
    ]

    # 2. Check addresses list
    if isinstance(addresses, list):
        for addr in addresses:
            if isinstance(addr, dict) and addr.get("phone"):
                phone_candidates.append(addr.get("phone"))

    # 3. Check customer note or notes for phone numbers (e.g. from KwikPass or OTP login)
    note_text = str(payload.get("note") or cust.get("note") or "")
    if note_text:
        extracted = re.findall(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\b\d{10,12}\b", note_text)
        phone_candidates.extend(extracted)

    # 4. Check tags for phone numbers
    tags_raw = payload.get("tags") or cust.get("tags")
    if isinstance(tags_raw, str):
        tag_phones = re.findall(r"\b\d{10,12}\b|\+\d{11,13}\b", tags_raw)
        phone_candidates.extend(tag_phones)

    # 5. Check metafields if provided in payload
    metafields = payload.get("metafields") or cust.get("metafields") or []
    if isinstance(metafields, list):
        for mf in metafields:
            if isinstance(mf, dict) and any(term in str(mf.get("key", "")).lower() for term in ["phone", "mobile", "kwikpass"]):
                phone_candidates.append(mf.get("value"))

    phone_raw = None
    for cand in phone_candidates:
        if cand and is_valid_phone(str(cand)):
            phone_raw = str(cand).strip()
            break

    # If test notification or no valid phone found, fall back only for Shopify sample tests
    is_test_sample = (
        "test" in str(payload.get("email", "")).lower()
        or payload.get("name") == "Sini Gos"
        or "example.com" in str(payload.get("email", "")).lower()
        or "loves ice cream" in note_text.lower()
    )
    if not phone_raw:
        if is_test_sample:
            phone_raw = "+919999999999"
        else:
            logger.warning(f"[Customer Sync] No valid phone found in payload. Keys: {list(payload.keys())}, Note: {note_text[:50]}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing phone number. Customer payload must contain a valid phone number in 'phone', 'addresses', note, or tags."
            )

    try:
        clean_phone = normalize_phone(str(phone_raw))
    except InvalidPhoneNumberError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid phone number '{phone_raw}': {e}"
        )

    # Name extraction (handles full name or split first/last names)
    name_val = payload.get("name") or payload.get("full_name") or payload.get("customer_name") or cust.get("name")
    if not name_val:
        first = payload.get("first_name", "") or payload.get("firstname", "") or cust.get("first_name", "")
        last = payload.get("last_name", "") or payload.get("lastname", "") or cust.get("last_name", "")
        combo = f"{first} {last}".strip()
        if combo:
            name_val = combo

    # Email
    email_val = payload.get("email") or payload.get("customer_email") or cust.get("email")

    # City (direct string or nested in address objects)
    city_val = payload.get("city")
    if not city_val and isinstance(default_addr, dict):
        city_val = default_addr.get("city")
    elif not city_val and isinstance(payload.get("address"), dict):
        city_val = payload["address"].get("city")
    elif not city_val and isinstance(billing_addr, dict):
        city_val = billing_addr.get("city")
    elif not city_val and isinstance(shipping_addr, dict):
        city_val = shipping_addr.get("city")

    # Tags (string or list of strings)
    tags_val = payload.get("tags")
    if isinstance(tags_val, list):
        tags_val = ", ".join(str(t).strip() for t in tags_val if t)
    elif tags_val is not None:
        tags_val = str(tags_val).strip()

    # Total orders
    orders_val = payload.get("total_orders") or payload.get("orders_count") or payload.get("order_count")
    total_orders_int = None
    if orders_val is not None:
        try:
            total_orders_int = int(orders_val)
        except (ValueError, TypeError):
            total_orders_int = None

    # Last order date
    last_order_val = payload.get("last_order_date")
    parsed_last_order = None
    if last_order_val:
        if isinstance(last_order_val, datetime):
            parsed_last_order = last_order_val
        elif isinstance(last_order_val, str):
            try:
                parsed_last_order = datetime.fromisoformat(last_order_val.replace("Z", "+00:00"))
            except Exception:
                pass

    # Birthday
    birth_day = payload.get("birth_day")
    birth_month = payload.get("birth_month")

    # Gather arbitrary custom attributes
    RESERVED_KEYS = {
        "phone", "phone_number", "mobile", "customer_phone", "telephone", "contact_number",
        "name", "full_name", "customer_name", "first_name", "last_name", "firstname", "lastname",
        "email", "customer_email",
        "city", "tags",
        "total_orders", "orders_count", "order_count",
        "last_order_date", "birth_day", "birth_month",
        "custom_attributes", "id", "created_at", "updated_at", "is_active"
    }

    custom_attrs: Dict[str, Any] = {}
    if isinstance(payload.get("custom_attributes"), dict):
        custom_attrs.update(payload["custom_attributes"])

    for k, v in payload.items():
        if k not in RESERVED_KEYS:
            custom_attrs[k] = v

    try:
        # Upsert Contact
        contact = db.query(models.Contact).filter(models.Contact.phone == clean_phone).first()
        action = "updated" if contact else "created"

        if contact:
            if name_val:
                contact.name = str(name_val)[:100]
            if email_val:
                contact.email = str(email_val)[:120]
            if city_val:
                contact.city = str(city_val)[:100]
            if tags_val:
                if contact.tags:
                    existing_tags = [t.strip() for t in contact.tags.split(",") if t.strip()]
                    new_tags = [t.strip() for t in tags_val.split(",") if t.strip()]
                    merged = sorted(list(set(existing_tags + new_tags)))
                    contact.tags = ", ".join(merged)[:255]
                else:
                    contact.tags = str(tags_val)[:255]
            if total_orders_int is not None and total_orders_int >= 0:
                contact.total_orders = total_orders_int
            if parsed_last_order:
                contact.last_order_date = parsed_last_order
            if birth_day is not None:
                contact.birth_day = birth_day
            if birth_month is not None:
                contact.birth_month = birth_month

            if custom_attrs:
                merged_attrs = dict(contact.custom_attributes or {})
                merged_attrs.update(custom_attrs)
                contact.custom_attributes = merged_attrs
        else:
            assigned_user = current_user.id if getattr(current_user, "role", None) == "agent" else None
            contact = models.Contact(
                phone=clean_phone,
                name=str(name_val)[:100] if name_val else None,
                email=str(email_val)[:120] if email_val else None,
                city=str(city_val)[:100] if city_val else None,
                tags=str(tags_val)[:255] if tags_val else None,
                total_orders=total_orders_int or 0,
                last_order_date=parsed_last_order,
                birth_day=birth_day,
                birth_month=birth_month,
                assigned_user_id=assigned_user,
                custom_attributes=custom_attrs
            )
            db.add(contact)

        db.commit()
        db.refresh(contact)

        try:
            from services.policy_service import record_consent
            record_consent(
                db=db,
                phone=clean_phone,
                source="customer_sync",
                proof_details=f"Synced via store webhook by {getattr(current_user, 'username', 'system')}"
            )
        except Exception as consent_err:
            logger.warning(f"Could not record consent for synced customer {clean_phone}: {consent_err}")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Customer sync database error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Customer sync database error: {type(e).__name__}: {str(e)}"
        )

    logger.info(f"[Customer Sync] Contact {action}: phone={clean_phone}, name={contact.name}, custom_attrs={list(custom_attrs.keys())}")

    # Check for active New Customer Welcome / Double Opt-In Automation
    if action == "created":
        try:
            from scheduler import start_workflow_session
            welcome_flow = db.query(models.WorkflowFlow).filter(
                models.WorkflowFlow.trigger_type == "NEW_CUSTOMER_WELCOME",
                models.WorkflowFlow.is_active == True
            ).first()
            if welcome_flow:
                start_workflow_session(
                    flow_id=welcome_flow.id,
                    customer_phone=clean_phone,
                    state_data={
                        "customer_name": contact.name or "Valued Customer",
                        "email": contact.email,
                        "city": contact.city,
                        "tags": contact.tags,
                        "source": "customer_sync"
                    },
                    db=db
                )
                logger.info(f"[Welcome Automation] Triggered flow #{welcome_flow.id} for new customer {clean_phone}")
        except Exception as e:
            logger.warning(f"Note: Could not start welcome workflow for {clean_phone}: {e}")

    return {
        "status": "success",
        "action": action,
        "contact": {
            "id": contact.id,
            "phone": contact.phone,
            "name": contact.name,
            "email": contact.email,
            "city": contact.city,
            "tags": contact.tags,
            "total_orders": contact.total_orders,
            "last_order_date": contact.last_order_date.isoformat() if contact.last_order_date else None,
            "birth_day": contact.birth_day,
            "birth_month": contact.birth_month,
            "custom_attributes": contact.custom_attributes or {}
        }
    }


@router.post("/customer-created", status_code=status.HTTP_200_OK)
@router.post("/customer-sync", status_code=status.HTTP_200_OK)
@limiter.limit("120/minute")
async def sync_customer_webhook(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    current_user: models.User = Depends(get_sync_webhook_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Inbound webhook for external software (e-commerce, CRM, ERP, POS, Zapier)
    to automatically sync customer contacts into the WhatsApp contact book.
    Supports any custom columns, which are preserved in custom_attributes.
    """
    return process_customer_sync(payload=payload, current_user=current_user, db=db)


@router.get("/whatsapp")
def verify_whatsapp_webhook(
    request: Request
):
    """
    Required by Meta to verify webhook endpoint URL.
    Checks hub.verify_token and echoes back hub.challenge.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if not config.WHATSAPP_VERIFY_TOKEN:
        logger.error("WHATSAPP_VERIFY_TOKEN is not configured in environment variables.")
        raise HTTPException(status_code=500, detail="Webhook verify token not configured on server")

    if mode == "subscribe" and token == config.WHATSAPP_VERIFY_TOKEN:
        return int(challenge) if challenge and challenge.isdigit() else challenge
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/whatsapp")
async def receive_inbound_whatsapp_message(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Receives incoming customer messages/replies from Meta WhatsApp Cloud API.
    1. If customer types 'STOP', 'બંધ કરો', or 'रोको', added to opt_outs DND table.
    2. Incoming messages saved into ChatMessage for real-time 2-Way Chat.
    """
    signature = request.headers.get("X-Hub-Signature-256", "")
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    raw_body = await request.body()
    payload_hash = hashlib.sha256(raw_body).hexdigest()

    if config.ENVIRONMENT == "production" or config.META_APP_SECRET:
        if not config.META_APP_SECRET:
            logger.error("[Meta Webhook Security] META_APP_SECRET is not configured in production!")
            raise HTTPException(status_code=500, detail="Server webhook security configuration error")
        expected_signature = "sha256=" + hmac.new(
            config.META_APP_SECRET.encode(), raw_body, hashlib.sha256
        ).hexdigest()
        if not signature or not hmac.compare_digest(expected_signature, signature):
            failed_event = models.WebhookEvent(
                source="meta",
                event_type="meta_auth_failure",
                external_event_id=None,
                idempotency_key=f"meta_auth_failure:{correlation_id}",
                hmac_validated=False,
                correlation_id=correlation_id,
                received_at=datetime.utcnow()
            )
            db.add(failed_event)
            try:
                db.commit()
            except Exception:
                db.rollback()
            raise HTTPException(status_code=401, detail="Invalid Meta webhook signature")

    try:
        import json
        data = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        return {"status": "ignored", "reason": "invalid json"}

    entries = data.get("entry", [])
    if not entries:
        return {"status": "ok"}

    processed_messages_count = 0
    processed_statuses_count = 0
    any_opt_out = False

    for entry in entries:
        changes = entry.get("changes", [])
        for chg in changes:
            value = chg.get("value", {})
            if not isinstance(value, dict):
                continue

            # 1. Process Status Updates (DELIVERED, READ, FAILED, SENT)
            statuses = value.get("statuses", [])
            for st in statuses:
                wamid = st.get("id")
                new_status = st.get("status", "").upper()
                if not wamid:
                    continue

                status_event_id = f"meta_status:{wamid}:{new_status}"
                existing_status_event = db.query(models.InboundWebhookEvent).filter(
                    models.InboundWebhookEvent.provider == "meta",
                    models.InboundWebhookEvent.provider_event_id == status_event_id
                ).first()
                if existing_status_event:
                    continue

                status_record = models.InboundWebhookEvent(
                    provider="meta",
                    provider_event_id=status_event_id,
                    event_type="status_update",
                    payload_hash=payload_hash,
                    correlation_id=correlation_id,
                    processed_at=datetime.utcnow()
                )
                db.add(status_record)

                chat_msg = db.query(models.ChatMessage).filter(models.ChatMessage.meta_message_id == wamid).first()
                if chat_msg:
                    chat_msg.status = new_status

                msg_log = db.query(models.MessageLog).filter(models.MessageLog.meta_message_id == wamid).first()
                if msg_log:
                    msg_log.status = new_status
                    errors = st.get("errors", [])
                    if errors:
                        msg_log.error_message = str(errors)

                if new_status == "READ":
                    # WP8: Update any active/waiting workflow sessions holding this message ID to message_read=True
                    try:
                        waiting_ws = db.query(models.WorkflowSession).filter(
                            models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"])
                        ).all()
                        for ws in waiting_ws:
                            if isinstance(ws.state_data, dict) and ws.state_data.get("last_meta_message_id") == wamid:
                                new_st = dict(ws.state_data)
                                new_st["message_read"] = True
                                ws.state_data = new_st
                                # CRUCIAL: Do NOT overwrite next_evaluation_at if session is in WAITING_DELAY!
                                # A delay node (e.g. Wait 5 mins) must finish its full scheduled duration.
                                # Only advance immediately if session is specifically waiting on a condition.
                                if ws.status == "WAITING_CONDITION":
                                    ws.next_evaluation_at = datetime.utcnow()
                    except Exception as ws_wake_err:
                        logger.warning(f"Could not update workflow session read state: {ws_wake_err}")

                try:
                    db.commit()
                    processed_statuses_count += 1
                except IntegrityError:
                    db.rollback()
                    logger.info(f"Duplicate Meta status update skipped: {status_event_id}")
                except Exception as e:
                    db.rollback()
                    logger.warning(f"Error updating status for {wamid}: {e}")

            # 2. Process Messages (Inbound customer messages & DND requests)
            messages = value.get("messages", [])
            for msg in messages:
                raw_meta_id = msg.get("id")
                meta_id = raw_meta_id or f"inbound_{uuid.uuid4().hex}"

                # Deduplicate: check InboundWebhookEvent
                existing_inbound = db.query(models.InboundWebhookEvent).filter(
                    models.InboundWebhookEvent.provider == "meta",
                    models.InboundWebhookEvent.provider_event_id == meta_id
                ).first()
                if existing_inbound:
                    logger.info(f"Duplicate Meta message replay skipped: {meta_id}")
                    continue

                # Deduplicate: check existing ChatMessage
                existing_chat = db.query(models.ChatMessage).filter(
                    models.ChatMessage.meta_message_id == meta_id
                ).first()
                if existing_chat:
                    logger.info(f"ChatMessage already exists for meta_id: {meta_id}")
                    continue

                db.add(models.InboundWebhookEvent(
                    provider="meta",
                    provider_event_id=meta_id,
                    event_type="inbound_message",
                    payload_hash=payload_hash,
                    correlation_id=correlation_id,
                    processed_at=datetime.utcnow()
                ))
                db.add(models.WebhookEvent(
                    source="meta",
                    event_type="inbound_message",
                    external_event_id=meta_id,
                    idempotency_key=f"meta_msg:{meta_id}",
                    hmac_validated=True,
                    correlation_id=correlation_id,
                    received_at=datetime.utcnow()
                ))

                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    logger.info(f"Duplicate Meta message skipped on flush: {meta_id}")
                    continue

                raw_from = msg.get("from", "")
                try:
                    sender_phone = normalize_phone(raw_from)
                except ValueError:
                    sender_phone = "+" + raw_from.strip("+")

                msg_type = msg.get("type", "text")
                raw_body = ""
                inbound_media_url = None
                inbound_filename = None

                if msg_type == "text":
                    raw_body = msg.get("text", {}).get("body", "").strip()
                elif msg_type == "button":
                    raw_body = msg.get("button", {}).get("text", "")
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    raw_body = interactive.get("button_reply", {}).get("title") or interactive.get("list_reply", {}).get("title") or "Interactive Response"
                elif msg_type in ["image", "document", "video", "audio", "voice"]:
                    media_payload = msg.get(msg_type, {})
                    media_id = media_payload.get("id")
                    caption = media_payload.get("caption") or ""
                    inbound_filename = media_payload.get("filename") or f"{msg_type}_{media_id}"
                    raw_body = caption or f"[{msg_type.upper()}]"

                    # Normalize voice to audio for unified handling
                    if msg_type == "voice":
                        msg_type = "audio"

                    if media_id:
                        dl_info = download_meta_media(media_id)
                        if dl_info:
                            inbound_media_url = dl_info.get("relative_url")
                            if "filename" in dl_info and not media_payload.get("filename"):
                                inbound_filename = dl_info["filename"]
                elif msg_type == "location":
                    loc = msg.get("location", {})
                    lat, lng = loc.get("latitude"), loc.get("longitude")
                    name = loc.get("name") or loc.get("address") or "Location"
                    raw_body = f"📍 {name} ({lat}, {lng})"
                elif msg_type == "contacts":
                    contacts_list = msg.get("contacts", [])
                    c_name = contacts_list[0].get("name", {}).get("formatted_name", "Contact Card") if contacts_list else "Contact Card"
                    raw_body = f"👤 {c_name}"
                elif msg_type == "reaction":
                    emoji = msg.get("reaction", {}).get("emoji", "👍")
                    raw_body = f"Reacted {emoji}"
                else:
                    raw_body = f"[{msg_type.upper()} message received]"

                # Only exact or word-bounded match for opt-out to avoid false positives
                words_lower = [w.strip() for w in raw_body.lower().replace(",", " ").replace(".", " ").replace("!", " ").split()]
                is_opt_out = any(keyword in words_lower or keyword == raw_body.strip().lower() for keyword in OPT_OUT_KEYWORDS)

                if is_opt_out:
                    any_opt_out = True
                    revoke_consent(db, sender_phone, reason="INBOUND_STOP_COMMAND")
                    logger.info(f"[AUTO-DND] Customer opted out via inbound message. Added to Opt-Out DND list and consent revoked.")
                else:
                    words = [w.strip() for w in raw_body.lower().replace(",", " ").replace(".", " ").replace("!", " ").split()]
                    is_opt_in = any(keyword in words or keyword == raw_body.strip().lower() for keyword in OPT_IN_KEYWORDS)
                    if is_opt_in:
                        record_consent(
                            db=db,
                            phone=sender_phone,
                            source="inbound_message",
                            proof_details=f"Inbound affirmative double opt-in reply: {raw_body[:60]}"
                        )
                        logger.info(f"[DOUBLE OPT-IN] Customer {sender_phone} confirmed consent via reply '{raw_body}'.")
                        # Advance any waiting double opt-in workflow sessions
                        waiting_sessions = db.query(models.WorkflowSession).filter(
                            models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"])
                        ).all()
                        for ws in waiting_sessions:
                            if ws.customer_phone == sender_phone:
                                ws.next_evaluation_at = datetime.utcnow()
                                if isinstance(ws.state_data, dict):
                                    ws.state_data["optin_confirmed"] = True

                new_chat_msg = models.ChatMessage(
                    customer_phone=sender_phone,
                    sender_type="CUSTOMER",
                    message_type=msg_type,
                    text=raw_body,
                    media_url=inbound_media_url,
                    filename=inbound_filename,
                    meta_message_id=meta_id,
                    status="RECEIVED",
                    is_read=False
                )
                db.add(new_chat_msg)

                # Reply-based read tracking: When a customer sends an inbound message/reply,
                # it proves affirmative customer engagement and that previous messages in the thread were read,
                # which is especially vital for contacts who have WhatsApp read receipts (blue ticks) disabled.
                try:
                    active_ws_list = db.query(models.WorkflowSession).filter(
                        models.WorkflowSession.customer_phone == sender_phone,
                        models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"])
                    ).all()
                    for ws in active_ws_list:
                        if isinstance(ws.state_data, dict):
                            new_st = dict(ws.state_data)
                            new_st["message_read"] = True
                            ws.state_data = new_st
                            if ws.status == "WAITING_CONDITION":
                                ws.next_evaluation_at = datetime.utcnow()

                    recent_outbound_log = db.query(models.MessageLog).filter(
                        models.MessageLog.recipient_phone == sender_phone,
                        models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED"])
                    ).order_by(models.MessageLog.id.desc()).first()
                    if recent_outbound_log:
                        recent_outbound_log.status = "READ"

                    recent_outbound_chat = db.query(models.ChatMessage).filter(
                        models.ChatMessage.customer_phone == sender_phone,
                        models.ChatMessage.sender_type != "CUSTOMER",
                        models.ChatMessage.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED"])
                    ).order_by(models.ChatMessage.id.desc()).first()
                    if recent_outbound_chat:
                        recent_outbound_chat.status = "READ"
                except Exception as read_track_err:
                    logger.warning(f"Could not update session read state on reply: {read_track_err}")

                existing_contact = db.query(models.Contact).filter(models.Contact.phone == sender_phone).first()
                if not existing_contact:
                    contacts_list = value.get("contacts") or []
                    profile_name = "New WhatsApp Lead"
                    if isinstance(contacts_list, list) and len(contacts_list) > 0 and isinstance(contacts_list[0], dict):
                        profile_name = contacts_list[0].get("profile", {}).get("name") or "New WhatsApp Lead"

                    new_contact = models.Contact(
                        phone=sender_phone,
                        name=profile_name,
                        total_orders=0,
                        tags="Inbound Lead",
                        city="WhatsApp"
                    )
                    db.add(new_contact)

                try:
                    db.commit()
                    processed_messages_count += 1
                except IntegrityError:
                    db.rollback()
                    logger.info(f"Duplicate ChatMessage skipped on commit: {meta_id}")

    if any_opt_out:
        return {"status": "opted_out", "messages_processed": processed_messages_count, "statuses_processed": processed_statuses_count}
    if processed_messages_count > 0:
        return {"status": "message_processed", "messages_processed": processed_messages_count, "statuses_processed": processed_statuses_count}
    if processed_statuses_count > 0:
        return {"status": "status_update_acknowledged", "statuses_processed": processed_statuses_count}
    return {"status": "ok"}


# ============================================================================
# Webhook Simulation Routes (WP1) - Admin-only, step-up auth, audit logged
# ============================================================================

@router.post("/simulate/cart-event", status_code=status.HTTP_202_ACCEPTED)
def simulate_cart_event(
    request: Request,
    payload: schemas.CartEventPayload,
    password: Optional[str] = None,
    two_factor_code: Optional[str] = None,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """
    Simulates a cart-event webhook without HMAC signatures.
    Strictly restricted to Admin role with step-up authentication.
    Generates an immutable AuditEvent and idempotency ledger entry.
    """
    auth.verify_user_stepup_auth(current_user, password, two_factor_code, db)

    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    idempotency_key = f"sim_cart:{payload.cart_token}:{int(datetime.utcnow().timestamp())}"

    # Record AuditEvent
    record_audit_event(
        db=db,
        action="SIMULATE_CART_WEBHOOK",
        actor_user_id=current_user.id,
        target_type="cart_event",
        target_id=payload.cart_token,
        correlation_id=correlation_id,
        metadata={"recipient_hash": hash_phone(payload.customer_phone)}
    )

    # Record WebhookEvent audit record
    sim_event = models.WebhookEvent(
        source="internal_sim",
        event_type="cart",
        external_event_id=str(payload.cart_token),
        idempotency_key=idempotency_key,
        hmac_validated=True,
        correlation_id=correlation_id,
        received_at=datetime.utcnow()
    )
    db.add(sim_event)
    db.commit()

    return {
        "status": "simulation_accepted",
        "cart_token": payload.cart_token,
        "customer_phone": payload.customer_phone,
        "correlation_id": correlation_id
    }


@router.post("/simulate/order-completed")
def simulate_order_completed(
    request: Request,
    payload: schemas.OrderCompletedPayload,
    password: Optional[str] = None,
    two_factor_code: Optional[str] = None,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """
    Simulates an order-completed webhook without HMAC signatures.
    Strictly restricted to Admin role with step-up authentication.
    Generates an immutable AuditEvent.
    """
    auth.verify_user_stepup_auth(current_user, password, two_factor_code, db)

    correlation_id = request.headers.get("X-Correlation-ID") or request.headers.get("X-Request-ID") or str(uuid.uuid4())
    idempotency_key = f"sim_order:{payload.cart_token}:{int(datetime.utcnow().timestamp())}"

    record_audit_event(
        db=db,
        action="SIMULATE_ORDER_WEBHOOK",
        actor_user_id=current_user.id,
        target_type="order_completed",
        target_id=payload.cart_token,
        correlation_id=correlation_id,
        metadata={"recipient_hash": hash_phone(payload.customer_phone)}
    )

    sim_event = models.WebhookEvent(
        source="internal_sim",
        event_type="order",
        external_event_id=f"order:{payload.cart_token}",
        idempotency_key=idempotency_key,
        hmac_validated=True,
        correlation_id=correlation_id,
        received_at=datetime.utcnow()
    )
    db.add(sim_event)
    db.commit()

    return {
        "status": "simulation_accepted",
        "cart_token": payload.cart_token,
        "customer_phone": payload.customer_phone,
        "correlation_id": correlation_id
    }

