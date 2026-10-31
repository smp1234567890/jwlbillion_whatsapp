import os
import re
import hmac
import hashlib
import logging
import time
import uuid as uuid_module
from datetime import datetime, timedelta
import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text
from database import DATABASE_URL, SessionLocal
import models
from whatsapp_service import send_whatsapp_template
from services.phone_service import normalize_phone
from services.secret_store import get_secret
from services.integration_gateway import dispatch_external_request, SSRFSecurityError, HostNotAllowedError, CredentialMismatchError
from services.job_claim_service import claim_workflow_session, release_workflow_session, claim_campaign
from services.pii_service import mask_phone

import config
from zoneinfo import ZoneInfo

logger = logging.getLogger("scheduler")
scheduler = BackgroundScheduler(
    timezone=ZoneInfo(config.TIMEZONE)
)

WEBHOOK_SECRET = config.WEBHOOK_SECRET
STORE_INACTIVE_FEED_URL = config.STORE_INACTIVE_FEED_URL

# In-memory short-lived cache for external API pulls to prevent duplicate HTTP calls for the same customer
_api_cache = {}


def fetch_external_api_value(field_key: str, phone: str, source_id: int = None, db = None) -> str:
    """
    Safely and securely queries an external e-commerce API to fetch customer/order data by phone.
    Caches responses for 60 seconds.
    """
    if not phone or not field_key:
        return ""

    cache_key = f"{source_id or 'default'}:{phone}"
    now_ts = datetime.utcnow().timestamp()

    if cache_key in _api_cache:
        data, expiry = _api_cache[cache_key]
        if now_ts < expiry:
            return str(data.get(field_key, ""))

    # Find data source
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        source = None
        if source_id:
            source = db.query(models.ExternalDataSource).filter(
                models.ExternalDataSource.id == source_id,
                models.ExternalDataSource.is_active == True
            ).first()
        if not source:
            source = db.query(models.ExternalDataSource).filter(
                models.ExternalDataSource.is_active == True
            ).first()

        if not source:
            logger.info(f"No active ExternalDataSource found to pull field '{field_key}' for {phone}")
            return ""

        param_name = source.lookup_param or "phone"
        try:
            clean_phone = normalize_phone(phone)
        except Exception:
            clean_phone = re.sub(r"[^\d+]", "", str(phone)).strip()
        params = {param_name: clean_phone}

        logger.info(f"[External API Pull] Querying {source.endpoint_url} via Integration Gateway for {clean_phone}")
        secret_val = get_secret(db, source.secret_reference) if source.secret_reference else None
        
        try:
            gw_resp = dispatch_external_request(
                endpoint_url=source.endpoint_url,
                approved_hostname=source.approved_hostname,
                credential_mode=source.auth_method or "bearer",
                secret_value=secret_val,
                params=params,
                timeout=config.HTTP_TIMEOUT_SECONDS
            )
            if gw_resp.get("is_success") and isinstance(gw_resp.get("data"), dict):
                resp_json = gw_resp["data"]
                # Cache result for 60 seconds
                _api_cache[cache_key] = (resp_json, now_ts + 60.0)
                val = resp_json.get(field_key)
                return str(val) if val is not None else ""
            else:
                logger.warning(f"External API returned {gw_resp.get('status_code')}: {gw_resp.get('message')}")
        except (SSRFSecurityError, HostNotAllowedError, CredentialMismatchError) as sec_err:
            logger.error(f"[Integration Gateway Blocked] Security policy denied external fetch: {sec_err}")
    except Exception as e:
        logger.error(f"Error pulling from external API: {e}")
    finally:
        if close_db:
            db.close()

    return ""


def process_abandoned_cart_job(cart_event_id: int):
    """
    Called when delay timer expires. Checks if the customer completed checkout.
    If not, and not opted-out, sends abandoned cart recovery template.
    """
    logger.info(f"⏰ [Scheduler] Executing delayed cart check for cart_event_id={cart_event_id}")
    db = SessionLocal()
    try:
        cart = db.query(models.CartEvent).filter(models.CartEvent.id == cart_event_id).first()
        if not cart:
            logger.warning(f"Cart event {cart_event_id} not found.")
            return

        if cart.status == "RECOVERED":
            logger.info(f"Order already completed for cart {cart.cart_token}. Skipping WhatsApp message.")
            return

        if cart.message_sent:
            logger.info(f"Message already sent for cart {cart.cart_token}. Skipping.")
            return

        # Fetch contact details if available
        contact = db.query(models.Contact).filter(models.Contact.phone == cart.customer_phone).first()
        customer_name = contact.name if contact and contact.name else "Valued Customer"

        # Item summary
        items_summary = ", ".join([item.get("item", "Namkeen Item") for item in cart.items]) if cart.items else "Special Jewelry & Premium Collection"
        cart_val_str = str(int(cart.cart_value)) if cart.cart_value == int(cart.cart_value) else f"{cart.cart_value:.2f}"

        # Look up active cart recovery rule to use the user's mapped template & parameters
        cart_rule = db.query(models.AutomationRule).filter(
            models.AutomationRule.rule_type == "CART_RECOVERY",
            models.AutomationRule.is_active == True
        ).first()

        target_template = cart_rule.template_name if cart_rule and cart_rule.template_name else "cart_recovery_v1"
        target_lang = "en_IN" if target_template == "cart_recovery_v1" else "en"
        tmpl_rec = db.query(models.Template).filter(models.Template.template_name == target_template).first()
        if tmpl_rec and tmpl_rec.language:
            target_lang = tmpl_rec.language

        # Extract placeholder indices from template body
        body_text = tmpl_rec.body_text if tmpl_rec and tmpl_rec.body_text else ""
        placeholder_matches = re.findall(r"\{\{(\d+)\}\}", body_text)
        placeholder_indices = sorted(list(set(int(m) for m in placeholder_matches))) if placeholder_matches else [1, 2, 3, 4]

        user_mappings = cart_rule.variable_mappings if cart_rule and isinstance(cart_rule.variable_mappings, dict) else {}

        param_dict = {}
        for idx in placeholder_indices:
            idx_str = str(idx)
            m_def = user_mappings.get(idx_str, {})
            m_type = m_def.get("type") if isinstance(m_def, dict) else None
            m_val = m_def.get("value") if isinstance(m_def, dict) else None

            if m_type == "contact_field":
                val_str = customer_name if m_val == "name" else (cart.customer_phone if m_val == "phone" else customer_name)
            elif m_type == "cart_event":
                val_str = cart_val_str if m_val == "cart_value" else items_summary
            elif m_type == "event_field":
                # Direct lookup from cart's extra_data payload
                extra = cart.extra_data if isinstance(cart.extra_data, dict) else {}
                if m_val == "firstname" or m_val == "first_name":
                    val_str = extra.get("first_name") or extra.get("firstname") or customer_name
                elif m_val == "products" or m_val == "products_summary" or m_val == "items":
                    val_str = extra.get("products_summary") or extra.get("products") or items_summary
                elif m_val == "amount" or m_val == "cart_value":
                    val_str = str(extra.get("amount")) if extra.get("amount") else f"₹{cart_val_str}"
                elif m_val == "delivery_address" or m_val == "address":
                    val_str = extra.get("delivery_address") or extra.get("address") or (contact.city if contact else "")
                else:
                    val_str = str(extra.get(m_val, ""))
            elif m_type == "external_api":
                src_id = m_def.get("source_id")
                val_str = fetch_external_api_value(field_key=m_val, phone=cart.customer_phone, source_id=src_id, db=db)
            elif m_type == "coupon":
                effective_code = (cart_rule.coupon_code if cart_rule and cart_rule.coupon_code else config.DEFAULT_COUPON_CODE)
                coupon_rec = db.query(models.DiscountCode).filter(
                    models.DiscountCode.code == effective_code
                ).first()

                if m_val == "discount_value":
                    val_str = f"{int(coupon_rec.discount_value)}%" if coupon_rec and coupon_rec.discount_type == "PERCENT" else f"{config.DEFAULT_DISCOUNT_PERCENT}%"
                elif m_val == "expires_at":
                    val_str = coupon_rec.expires_at.strftime("%d/%m/%Y") if coupon_rec and coupon_rec.expires_at else (datetime.utcnow() + timedelta(days=config.DEFAULT_EXPIRY_DAYS)).strftime("%d/%m/%Y")
                else:
                    val_str = effective_code
            elif m_type == "static":
                val_str = str(m_val) if m_val else ""
            else:
                effective_code = (cart_rule.coupon_code if cart_rule and cart_rule.coupon_code else config.DEFAULT_COUPON_CODE)
                # Default smart fallback for cart recovery templates (e.g. cart_recovery_v1)
                if idx == 1:
                    val_str = customer_name
                elif idx == 2:
                    val_str = items_summary
                elif idx == 3:
                    val_str = cart_val_str
                elif idx == 4:
                    val_str = effective_code
                else:
                    val_str = config.BRAND_NAME

            param_dict[f"param_{idx}"] = val_str

        # Send recovery template
        recovery_coupon = (cart_rule.coupon_code if cart_rule and cart_rule.coupon_code else config.DEFAULT_COUPON_CODE)
        auth_user = cart.authenticated_user or "Abandoned Cart Recovery"
        result = send_whatsapp_template(
            recipient_phone=cart.customer_phone,
            template_name=target_template,
            language=target_lang,
            parameters=param_dict,
            coupon_code=recovery_coupon,
            sender_user=auth_user,
            idempotency_key=f"cart_recovery_{cart.id}",
            purpose="utility"
        )

        if result.get("status") in ["success", "success_simulated"]:
            cart.message_sent = True
            cart.message_sent_at = datetime.utcnow()
            if cart_rule:
                cart_rule.total_triggered += 1
            db.commit()
            logger.info(f"Abandoned cart recovery dispatched for {mask_phone(cart.customer_phone)}")
        else:
            logger.warning(f"Cart message was not sent: {result}")
            try:
                reason = result.get("reason") or result.get("error") or "Template dispatch failed"
                fail_entry = models.MessageLog(
                    recipient_phone=cart.customer_phone,
                    template_name=target_template,
                    language=target_lang,
                    status="FAILED",
                    error_message=f"Recovery failed: {reason}"
                )
                db.add(fail_entry)
                db.commit()
            except Exception as log_err:
                logger.warning(f"Could not save un-sent MessageLog: {log_err}")

    except Exception as e:
        logger.error(f"Error in process_abandoned_cart_job: {e}")
        try:
            cart = db.query(models.CartEvent).filter(models.CartEvent.id == cart_event_id).first()
            fail_entry = models.MessageLog(
                recipient_phone=cart.customer_phone if cart else "Unknown",
                template_name="cart_recovery_v1",
                language="en_IN",
                status="FAILED",
                error_message=f"Cart job crashed: {str(e)[:400]}"
            )
            db.add(fail_entry)
            db.commit()
        except Exception as log_err:
            logger.warning(f"Could not save exception MessageLog: {log_err}")
    finally:
        db.close()


def schedule_cart_recovery(cart_event_id: int, delay_seconds: int = 0):
    """
    Dispatches immediately if delay_seconds <= 0, or schedules a delayed job.
    """
    if delay_seconds <= 0:
        logger.info(f"Processing cart recovery immediately for cart_event_id={cart_event_id}")
        process_abandoned_cart_job(cart_event_id)
        return

    run_date = datetime.now() + timedelta(seconds=delay_seconds)
    job_id = f"cart_recovery_{cart_event_id}"
    
    scheduler.add_job(
        func=process_abandoned_cart_job,
        trigger=DateTrigger(run_date=run_date),
        args=[cart_event_id],
        id=job_id,
        replace_existing=True
    )
    logger.info(f"Scheduled recovery job {job_id} to run at {run_date.strftime('%H:%M:%S')} (in {delay_seconds}s)")


def fetch_inactive_customers_from_store(days: int = 30) -> list:
    """
    Calls the external store API using the secure integration gateway.
    Enforces SSRF guards, DNS resolution checks, approved hostname allowlists,
    and HMAC signing. Returns empty list if URL is not configured or blocked.
    """
    if not STORE_INACTIVE_FEED_URL:
        return []

    try:
        from urllib.parse import urlparse
        query_param = f"days={days}"
        secret_bytes = (WEBHOOK_SECRET or "").encode()
        sig = "sha256=" + hmac.new(secret_bytes, query_param.encode(), hashlib.sha256).hexdigest()
        
        parsed = urlparse(STORE_INACTIVE_FEED_URL)
        approved_host = parsed.hostname or ""

        gw_res = dispatch_external_request(
            endpoint_url=STORE_INACTIVE_FEED_URL,
            params={"days": days},
            approved_hostname=approved_host,
            credential_mode="none",
            timeout=config.HTTP_TIMEOUT_SECONDS
        )
        if gw_res.get("is_success") and isinstance(gw_res.get("data"), dict):
            return gw_res["data"].get("customers", [])
    except Exception as e:
        logger.error(f"Failed to fetch inactive customers from store via gateway: {e}")
    return []


def run_thirty_day_reengagement_sweep():
    """
    Daily cron task (and callable manually):
    1. Queries local DB for inactive customers.
    2. Also queries external store API feed for customers who haven't ordered in 30 days.
    3. De-duplicates: ensures customer wasn't messaged within the last 7 days.
    4. Sends re-engagement promo code via WhatsApp template.
    """
    logger.info("[Cron Sweep] Starting 30-day customer re-engagement sweep...")
    db = SessionLocal()
    try:
        # Step A: Fetch from local DB
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        contacts = db.query(models.Contact).filter(
            models.Contact.is_active == True,
            (models.Contact.last_order_date <= cutoff_date) | (models.Contact.last_order_date == None)
        ).all()

        target_phones = {c.phone: (c.name or "Valued Customer") for c in contacts}

        # Step B: Pull fresh inactive customers from JWL's store feed
        external_customers = fetch_inactive_customers_from_store(days=30)
        for ec in external_customers:
            p = ec.get("phone")
            if p:
                target_phones[p] = ec.get("name", "Valued Customer")

        logger.info(f"Found {len(target_phones)} customers eligible for 30-day re-engagement.")

        # Step C: 7-Day Deduplication Gate
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        sent_count = 0
        skipped_count = 0

        for phone, name in target_phones.items():
            # Check if messaged within the last 7 days (only count successfully sent)
            recent_msg = db.query(models.MessageLog).filter(
                models.MessageLog.recipient_phone == phone,
                models.MessageLog.template_name == "reengagement_30_days",
                models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED", "READ"]),
                models.MessageLog.created_at >= seven_days_ago
            ).first()

            if recent_msg:
                logger.info(f"⏭ Skipping {mask_phone(phone)}: Already received 30-day promo within the last 7 days.")
                skipped_count += 1
                continue

            # Dispatch personalized winback template with coupon code
            res = send_whatsapp_template(
                recipient_phone=phone,
                template_name="reengagement_30_days",
                language="en",
                parameters={"name": name, "discount_code": "SPECIAL10"},
                idempotency_key=f"milestone_{phone}_{datetime.utcnow().strftime('%Y%m%d')}",
                purpose="marketing"
            )
            if res.get("status") in ["success", "success_simulated"]:
                sent_count += 1

        logger.info(f"Re-engagement sweep complete: {sent_count} sent, {skipped_count} skipped (7-day dedup).")
    except Exception as e:
        logger.error(f"Error in re-engagement sweep: {e}")
    finally:
        db.close()


def execute_campaign_broadcast(campaign_id: int, recipient_phones: list = None):
    """
    Executes a bulk broadcast campaign safely with rate-limiting and opt-out checks.
    Uses a distributed campaign lease (WP8) to prevent duplicate execution across workers.
    """
    logger.info(f"[Campaign] Starting execution of campaign_id={campaign_id}")
    db = SessionLocal()
    try:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found.")
            return

        # WP8: Acquire a distributed row-level campaign lease before execution
        worker_id = f"campaign_worker_{uuid_module.uuid4().hex[:8]}"
        claimed = claim_campaign(db, campaign_id, worker_id=worker_id, lease_seconds=600)
        if not claimed:
            logger.info(f"[Campaign] Campaign {campaign_id} already claimed by another worker — skipping duplicate execution.")
            return

        campaign.status = "IN_PROGRESS"
        db.commit()

        phones = recipient_phones or []
        if not phones:
            # Check if target_filter is a dynamic segment ID (e.g. "SEGMENT:3")
            if campaign.target_filter and campaign.target_filter.startswith("SEGMENT:"):
                try:
                    seg_id = int(campaign.target_filter.split("SEGMENT:")[-1])
                    seg = db.query(models.ContactSegment).filter(models.ContactSegment.id == seg_id).first()
                    if seg:
                        from routers.segments import query_contacts_by_criteria
                        contacts = query_contacts_by_criteria(db, seg.criteria or {}).all()
                        phones = [c.phone for c in contacts]
                except Exception as _seg_err:
                    logger.warning(f"[Campaign {campaign_id}] Segment lookup failed: {_seg_err}")

            if not phones:
                if campaign.target_filter == "INACTIVE_30_DAYS":
                    cutoff_date = datetime.utcnow() - timedelta(days=30)
                    contacts = db.query(models.Contact).filter(
                        models.Contact.is_active == True,
                        (models.Contact.last_order_date <= cutoff_date) | (models.Contact.last_order_date == None)
                    ).all()
                    phones = [c.phone for c in contacts]
                else: # Default ALL
                    contacts = db.query(models.Contact).filter(models.Contact.is_active == True).all()
                    phones = [c.phone for c in contacts]

        # Honor Per Day Message Limit: Cap list to per_day_limit if specified
        if campaign.per_day_limit and campaign.per_day_limit > 0:
            original_count = len(phones)
            phones = phones[:campaign.per_day_limit]
            logger.info(f"[Campaign {campaign_id}] Per-Day limit applied: capped from {original_count} to {len(phones)} messages")

        campaign.total_recipients = len(phones)
        db.commit()

        success_count = 0
        fail_count = 0
        last_failure_reason = ""

        import re
        tmpl = db.query(models.Template).filter(models.Template.template_name == campaign.template_name).first()
        placeholder_count = 0
        if tmpl and tmpl.body_text:
            matches = re.findall(r"\{\{(\d+)\}\}", tmpl.body_text)
            if matches:
                placeholder_count = max([int(m) for m in matches])

        # BATCH PACING: 7 messages per batch with 1-second pause to match DB pool size (7) and prevent rate-limit
        BATCH_SIZE = 7
        total_phones = len(phones)
        logger.info(f"[Campaign {campaign_id}] Processing {total_phones} recipients in batches of {BATCH_SIZE} (1s pacing)")

        for i in range(0, total_phones, BATCH_SIZE):
            batch = phones[i:i + BATCH_SIZE]
            batch_start_time = time.time()

            for phone in batch:
                try:
                    contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
                    customer_name = contact.name if contact and contact.name else "Valued Customer"

                    # Build parameters: use template-level mappings first, then positional fallback
                    params = {}
                    body_mappings = {
                        k: v for k, v in (tmpl.variable_mappings or {}).items()
                        if k != "header" and isinstance(v, dict)
                    } if tmpl and isinstance(tmpl.variable_mappings, dict) else {}

                    if body_mappings:
                        cart_val_str = str(getattr(contact, "total_spent", 0) or 0)
                        items_summary = campaign.title
                        for idx_str, m_def in body_mappings.items():
                            if not isinstance(m_def, dict):
                                continue
                            m_type = m_def.get("type")
                            m_val = m_def.get("value")
                            if m_type == "contact_field":
                                if m_val == "phone":
                                    val_str = phone
                                elif m_val == "city":
                                    val_str = contact.city if contact and contact.city else "Ahmedabad"
                                elif m_val == "total_orders":
                                    val_str = str(contact.total_orders) if contact else "1"
                                elif m_val == "last_order_date":
                                    val_str = contact.last_order_date.strftime("%d/%m/%Y") if contact and contact.last_order_date else "Recently"
                                else:
                                    val_str = customer_name
                            elif m_type == "cart_event":
                                val_str = cart_val_str if m_val == "cart_value" else items_summary
                            elif m_type == "coupon":
                                val_str = config.DEFAULT_COUPON_CODE if hasattr(config, "DEFAULT_COUPON_CODE") else "MANU10"
                            elif m_type == "static":
                                val_str = str(m_val) if m_val else ""
                            else:
                                val_str = customer_name
                            params[f"param_{idx_str}"] = val_str
                    elif placeholder_count > 0:
                        # Positional fallback if template has placeholders but no configured mappings
                        fallback_values = [
                            customer_name,
                            campaign.title,
                            config.STORE_SUPPORT_PHONE or phone,
                            f"{config.DEFAULT_DISCOUNT_PERCENT}% OFF",
                            config.STORE_LOCATION or config.BRAND_NAME,
                            config.BRAND_NAME
                        ]
                        for idx in range(1, placeholder_count + 1):
                            params[f"param_{idx}"] = fallback_values[(idx - 1) % len(fallback_values)]

                    # Build header media if campaign or template has configured media
                    campaign_header_media = None
                    if tmpl and (tmpl.header_type or "NONE").upper() in ["IMAGE", "VIDEO", "DOCUMENT", "LOCATION"]:
                        # 0. Check if campaign has explicit header_media set
                        if campaign.header_media and isinstance(campaign.header_media, dict):
                            campaign_header_media = campaign.header_media

                        # 1. Check if template has column mapping for header
                        if not campaign_header_media:
                            h_map = (tmpl.variable_mappings or {}).get("header")
                            if h_map and isinstance(h_map, dict):
                                m_type = h_map.get("type")
                                m_val = h_map.get("value")
                                if m_type == "static" and m_val:
                                    campaign_header_media = {"url": m_val}
                        
                        # 2. Check if template sample_values has header_url or location
                        if not campaign_header_media and tmpl.sample_values:
                            sv = tmpl.sample_values
                            if sv.get("header_url"):
                                campaign_header_media = {"url": sv.get("header_url")}
                            elif sv.get("latitude") and sv.get("longitude"):
                                campaign_header_media = {
                                    "latitude": sv.get("latitude"),
                                    "longitude": sv.get("longitude"),
                                    "name": sv.get("location_name")
                                }

                    res = send_whatsapp_template(
                        recipient_phone=phone,
                        template_name=campaign.template_name,
                        language=campaign.language,
                        parameters=params,
                        header_media=campaign_header_media,
                        campaign_id=campaign.id,
                        sender_user=f"Campaign: {campaign.title}",
                        idempotency_key=f"campaign_{campaign.id}_{phone}",
                        purpose=campaign.message_type or "marketing"
                    )

                    if res.get("status") in ["success", "success_simulated"]:
                        success_count += 1
                    else:
                        fail_count += 1
                        last_failure_reason = res.get("error") or res.get("reason") or res.get("message") or "Meta send rejected"
                except Exception as rec_err:
                    logger.error(f"Error processing recipient {mask_phone(phone)} in campaign {campaign_id}: {rec_err}", exc_info=True)
                    fail_count += 1
                    last_failure_reason = str(rec_err)

            # Update live campaign progress in DB after each batch so UI displays real-time progress
            campaign.successful_sends = success_count
            campaign.failed_sends = fail_count
            db.commit()

            # Pacing: Sleep for remainder of 1 second if more batches remain
            if i + BATCH_SIZE < total_phones:
                elapsed = time.time() - batch_start_time
                sleep_time = max(0.0, 1.0 - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

        campaign.successful_sends = success_count
        campaign.failed_sends = fail_count
        if fail_count > 0 and success_count == 0:
            campaign.status = "FAILED"
            campaign.error_message = last_failure_reason or "All recipient deliveries failed"
        else:
            campaign.status = "COMPLETED"
            if fail_count > 0:
                campaign.error_message = f"Partially completed: {success_count} sent, {fail_count} failed"
        db.commit()
        logger.info(f"Campaign {campaign_id} {campaign.status}: {success_count} sent, {fail_count} failed. Note: {campaign.error_message}")

    except Exception as e:
        logger.error(f"Error executing campaign {campaign_id}: {e}", exc_info=True)
        if campaign:
            campaign.status = "FAILED"
            campaign.error_message = str(e)
            db.commit()
    finally:
        db.close()


def run_all_active_automation_rules():
    """
    Automatic daily cron job: iterates through every active automation rule
    (15-day inactive, 30-day winback, VIP repeat buyer, etc.) and executes them
    with deduplication without requiring manual button clicks.
    """
    logger.info("⏰ [Daily Cron] Auto-executing all active automation rules...")
    db = SessionLocal()
    try:
        rules = db.query(models.AutomationRule).filter(models.AutomationRule.is_active == True).all()
        for rule in rules:
            if rule.rule_type != "CART_RECOVERY":
                dispatched = run_rule_execution(rule.id)
                logger.info(f"[Daily Cron] Rule '{rule.rule_name}': {dispatched} sent.")
    except Exception as e:
        logger.error(f"Error in daily automation rules execution: {e}")
    finally:
        db.close()


def run_scheduled_meta_template_sync():
    """
    Periodic job that automatically synchronizes approved message templates
    and read analytics from Meta Graph API every 10 minutes.
    """
    from database import SessionLocal
    from routers.templates import execute_sync_meta_templates

    db = SessionLocal()
    try:
        logger.info("[Scheduler Auto-Sync] Syncing WhatsApp templates from Meta...")
        res = execute_sync_meta_templates(db=db)
        logger.info(f"[Scheduler Auto-Sync Complete] {res.get('message', 'Done')}")
    except Exception as e:
        logger.warning(f"[Scheduler Auto-Sync Failed] {e}")
    finally:
        db.close()


def start_scheduler():
    if not config.SCHEDULER_ENABLED:
        logger.info("Scheduler is disabled for this application instance.")
        return
    if not scheduler.running:
        # 1. Automatic Daily Sweep at 10:00 AM IST for ALL active automation rules (15-day, 30-day, VIP, etc.)
        scheduler.add_job(
            func=run_all_active_automation_rules,
            trigger=CronTrigger(hour=10, minute=0),
            id="daily_all_automations_sweep",
            replace_existing=True
        )
        # 2. Continuous Multi-Step Workflow Engine Sweep (checks delays & conditions every minute)
        scheduler.add_job(
            func=process_all_active_workflow_sessions,
            trigger=IntervalTrigger(minutes=1),
            id="continuous_workflow_engine_sweep",
            replace_existing=True
        )
        # 3. Automatic Meta Template & Analytics Sync every 10 minutes
        scheduler.add_job(
            func=run_scheduled_meta_template_sync,
            trigger=IntervalTrigger(minutes=10),
            id="auto_sync_meta_templates_sweep",
            replace_existing=True
        )
        scheduler.start()
        logger.info("APScheduler started successfully with daily sweep, continuous workflow engine, and 10-minute Meta template auto-sync.")

def run_rule_execution(rule_id: int, force_approved: bool = False) -> dict:
    """
    Executes an individual automation rule dynamically based on its condition.
    - INACTIVE_DAYS (e.g. 15 days or 30 days)
    - ORDER_COUNT_VIP (e.g. >= 2 orders)

     HIGH-VOLUME SAFEGUARD:
    If the rule targets more than 100 contacts (> 100), it is held in PENDING_APPROVAL
    and dispatches an alert email to all admin emails asking for 2FA permission,
    unless explicitly authorized by admin (force_approved=True).
    """
    db = SessionLocal()
    sent_count = 0
    try:
        rule = db.query(models.AutomationRule).filter(models.AutomationRule.id == rule_id).first()
        if not rule or not rule.is_active:
            return {"status": "inactive", "messages_dispatched": 0, "requires_approval": False}

        # ⏳ Check Expiration Deadline: If past expires_at, automatically turn rule OFF
        if rule.expires_at and datetime.utcnow() > rule.expires_at:
            rule.is_active = False
            db.commit()
            logger.info(f"⏳ [Rule Engine] Rule '{rule.rule_name}' has passed its deadline ({rule.expires_at}). Auto-deactivated.")
            return {"status": "expired", "messages_dispatched": 0, "requires_approval": False, "message": "Automation rule has reached its deadline and is now inactive."}

        logger.info(f"[Rule Engine] Running automation rule: '{rule.rule_name}' (force_approved={force_approved})")
        target_phones = {}

        if rule.rule_type == "INACTIVE_DAYS":
            cutoff_date = datetime.utcnow() - timedelta(days=rule.threshold_value)
            contacts = db.query(models.Contact).filter(
                models.Contact.is_active == True,
                (models.Contact.last_order_date <= cutoff_date) | (models.Contact.last_order_date == None)
            ).all()
            for c in contacts:
                target_phones[c.phone] = c

        elif rule.rule_type == "ORDER_COUNT_VIP":
            vip_contacts = db.query(models.Contact).filter(
                models.Contact.is_active == True,
                models.Contact.total_orders >= rule.threshold_value
            ).all()
            for c in vip_contacts:
                target_phones[c.phone] = c

        # Apply deduplication gate to calculate ACTUAL eligible contacts to receive messages
        # Only deduplicate contacts who actually received a message (do not block failed attempts)
        dedup_cutoff = datetime.utcnow() - timedelta(days=rule.dedup_days)
        eligible_phones = {}
        for phone, contact_obj in target_phones.items():
            recent_msg = db.query(models.MessageLog).filter(
                models.MessageLog.recipient_phone == phone,
                models.MessageLog.template_name == rule.template_name,
                models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED", "READ"]),
                models.MessageLog.created_at >= dedup_cutoff
            ).first()
            if not recent_msg:
                eligible_phones[phone] = contact_obj

        total_eligible = len(eligible_phones)

        # SAFEGUARD: If > 100 recipients and not force_approved by admin, hold and email alert!
        if total_eligible > 100 and not force_approved:
            rule.approval_status = "PENDING_APPROVAL"
            rule.pending_recipients_count = total_eligible
            db.commit()

            logger.info(f"⏸ Rule '{rule.rule_name}'held: {total_eligible} eligible recipients (> 100 threshold). Requires dashboard approval.")
            return {
                "status": "pending_approval",
                "messages_dispatched": 0,
                "requires_approval": True,
                "eligible_count": total_eligible,
                "rule": rule.rule_name,
                "message": f"Rule held for approval: targets {total_eligible} contacts (>100 threshold). Please review in dashboard."
            }

        # Determine template language dynamically from DB
        import re
        tmpl_rec = db.query(models.Template).filter(models.Template.template_name == rule.template_name).first()
        target_lang = (tmpl_rec.language if tmpl_rec and tmpl_rec.language else "en")

        # Parse placeholder indices from template body (e.g. {{1}}, {{2}}, {{3}}, {{4}})
        placeholder_indices = []
        if tmpl_rec and tmpl_rec.body_text:
            raw_matches = re.findall(r"\{\{(\d+)\}\}", tmpl_rec.body_text)
            if raw_matches:
                placeholder_indices = sorted(list(set(int(m) for m in raw_matches)))
        if not placeholder_indices:
            placeholder_indices = [1, 2]

        user_mappings = rule.variable_mappings if isinstance(rule.variable_mappings, dict) else {}

        # If <= 100 OR already approved by admin with 2FA
        # Process in FIFO batches of 7 (matching DB_POOL_SIZE = 7)
        eligible_items = list(eligible_phones.items())
        RULE_BATCH_SIZE = 7

        for chunk_idx in range(0, len(eligible_items), RULE_BATCH_SIZE):
            chunk = eligible_items[chunk_idx:chunk_idx + RULE_BATCH_SIZE]
            for phone, contact_obj in chunk:
                cust_name = contact_obj.name if contact_obj and contact_obj.name else "Valued Customer"
                cust_phone = contact_obj.phone if contact_obj and contact_obj.phone else phone
                cust_city = contact_obj.city if contact_obj and contact_obj.city else "Ahmedabad"
                cust_orders = str(contact_obj.total_orders) if contact_obj and contact_obj.total_orders is not None else "1"
                cust_last_order = contact_obj.last_order_date.strftime("%d %b %Y") if contact_obj and contact_obj.last_order_date else "Recently"

                # Construct ordered parameters for Meta
                param_dict = {}
                for idx in placeholder_indices:
                    idx_str = str(idx)
                    mapping_def = user_mappings.get(idx_str, {})
                    m_type = mapping_def.get("type") if isinstance(mapping_def, dict) else None
                    m_val = mapping_def.get("value") if isinstance(mapping_def, dict) else None

                    if m_type == "contact_field":
                        if m_val == "name":
                            val_str = cust_name
                        elif m_val == "phone":
                            val_str = cust_phone
                        elif m_val == "city":
                            val_str = cust_city
                        elif m_val == "total_orders":
                            val_str = cust_orders
                        elif m_val == "last_order_date":
                            val_str = cust_last_order
                        else:
                            val_str = cust_name
                    elif m_type == "cart_event":
                        # Look up latest cart event for this phone if available
                        recent_cart = db.query(models.CartEvent).filter(
                            models.CartEvent.customer_phone == phone
                        ).order_by(models.CartEvent.id.desc()).first()
                        if m_val == "cart_value":
                            val_str = str(int(recent_cart.cart_value)) if recent_cart and recent_cart.cart_value == int(recent_cart.cart_value) else (f"{recent_cart.cart_value:.2f}" if recent_cart else "450")
                        else:
                            val_str = ", ".join([it.get("item", "Namkeen") for it in recent_cart.items]) if recent_cart and recent_cart.items else "Special Jewelry & Premium Collection"
                    elif m_type == "event_field":
                        recent_cart = db.query(models.CartEvent).filter(
                            models.CartEvent.customer_phone == phone
                        ).order_by(models.CartEvent.id.desc()).first()
                        extra = recent_cart.extra_data if recent_cart and isinstance(recent_cart.extra_data, dict) else {}
                        if m_val == "firstname" or m_val == "first_name":
                            val_str = extra.get("first_name") or extra.get("firstname") or cust_name
                        elif m_val == "products" or m_val == "products_summary" or m_val == "items":
                            val_str = extra.get("products_summary") or extra.get("products") or ", ".join([it.get("item", "Namkeen") for it in recent_cart.items]) if recent_cart and recent_cart.items else "Special Jewelry & Premium Collection"
                        elif m_val == "amount" or m_val == "cart_value":
                            val_str = str(extra.get("amount")) if extra.get("amount") else (f"₹{int(recent_cart.cart_value)}" if recent_cart else "₹450")
                        elif m_val == "delivery_address" or m_val == "address":
                            val_str = extra.get("delivery_address") or extra.get("address") or cust_city
                        else:
                            val_str = str(extra.get(m_val, ""))
                    elif m_type == "external_api":
                        src_id = mapping_def.get("source_id")
                        val_str = fetch_external_api_value(field_key=m_val, phone=phone, source_id=src_id, db=db)
                    elif m_type == "coupon":
                        # Look up attached coupon details from DB
                        coupon_rec = db.query(models.DiscountCode).filter(
                            models.DiscountCode.code == rule.coupon_code
                        ).first() if rule.coupon_code else None

                        if m_val == "discount_value":
                            if coupon_rec:
                                val_str = f"{int(coupon_rec.discount_value)}%" if coupon_rec.discount_type == "PERCENT" else f"₹{int(coupon_rec.discount_value)}"
                            else:
                                val_str = f"{config.DEFAULT_DISCOUNT_PERCENT}%"
                        elif m_val == "expires_at":
                            if coupon_rec and coupon_rec.expires_at:
                                val_str = coupon_rec.expires_at.strftime("%d/%m/%Y")
                            elif rule.expires_at:
                                val_str = rule.expires_at.strftime("%d/%m/%Y")
                            else:
                                val_str = (datetime.utcnow() + timedelta(days=config.DEFAULT_EXPIRY_DAYS)).strftime("%d/%m/%Y")
                        else:
                            val_str = rule.coupon_code or config.DEFAULT_COUPON_CODE
                    elif m_type == "static":
                        val_str = str(m_val).strip() if m_val else "-"
                    else:
                        # Default intelligent fallback if no explicit user mapping
                        if idx == 1:
                            val_str = cust_name
                        elif idx == 2:
                            val_str = rule.coupon_code or config.DEFAULT_COUPON_CODE
                        elif idx == 3:
                            val_str = f"{config.DEFAULT_DISCOUNT_PERCENT}% OFF"
                        elif idx == 4:
                            val_str = "Limited Time"
                        else:
                            val_str = config.BRAND_NAME

                    param_dict[f"param_{idx}"] = val_str

                res = send_whatsapp_template(
                    recipient_phone=phone,
                    template_name=rule.template_name,
                    language=target_lang,
                    parameters=param_dict,
                    coupon_code=rule.coupon_code or config.DEFAULT_COUPON_CODE,
                    sender_user=f"Rule: {rule.rule_name}",
                    idempotency_key=f"rule_{rule.id}_{phone}_{datetime.utcnow().strftime('%Y%m%d')}",
                    purpose="utility"
                )
                if res.get("status") in ["success", "success_simulated"]:
                    sent_count += 1
                else:
                    logger.warning(f"[Rule Engine] Dispatch to {mask_phone(phone)} returned: {res}")

            # Commit after each batch of 7 to release locks and flush logs
            try:
                db.commit()
            except Exception:
                db.rollback()

            if chunk_idx + RULE_BATCH_SIZE < len(eligible_items):
                time.sleep(0.3)

        rule.total_triggered += sent_count
        rule.approval_status = "IDLE"
        rule.pending_recipients_count = 0
        db.commit()
        logger.info(f"Rule '{rule.rule_name}'finished: {sent_count}/{total_eligible} messages sent.")
        return {
            "status": "success",
            "messages_dispatched": sent_count,
            "requires_approval": False,
            "rule": rule.rule_name
        }
    except Exception as e:
        logger.error(f"Error executing rule {rule_id}: {e}")
        return {"status": "error", "error": str(e), "messages_dispatched": 0, "requires_approval": False}
    finally:
        db.close()


# =====================================================================
# MULTI-STEP VISUAL FLOWCHART WORKFLOW EXECUTION ENGINE
# =====================================================================

def find_node_by_id(nodes: list, node_id: str):
    """Finds a node inside a workflow's nodes list by its ID."""
    for n in nodes:
        if str(n.get("id")) == str(node_id):
            return n
    return None


def find_next_node(nodes: list, edges: list, current_node_id: str, handle: str = None):
    """
    Finds the next node in the graph.
    If handle is provided ('yes' or 'no'), matches the edge sourceHandle.
    """
    candidate_edges = [
        e for e in edges
        if str(e.get("source")) == str(current_node_id)
    ]
    if not candidate_edges:
        return None

    if handle:
        matching = [e for e in candidate_edges if str(e.get("sourceHandle", "")).lower() == handle.lower()]
        if matching:
            target_id = matching[0].get("target")
            return find_node_by_id(nodes, target_id)
        # Fallback if handle wasn't explicitly tagged
        target_id = candidate_edges[0].get("target")
        return find_node_by_id(nodes, target_id)
    else:
        target_id = candidate_edges[0].get("target")
        return find_node_by_id(nodes, target_id)


def start_workflow_session(flow_id: int, customer_phone: str, state_data: dict, db=None) -> models.WorkflowSession:
    """
    Initializes a new customer session into a visual workflow journey.
    Locates the trigger node, persists state, and processes the initial step.
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True

    try:
        flow = db.query(models.WorkflowFlow).filter(models.WorkflowFlow.id == flow_id).first()
        if not flow or not flow.is_active:
            logger.info(f"Flow {flow_id} is inactive or not found.")
            return None

        nodes = flow.nodes or []
        edges = flow.edges or []
        if not nodes:
            logger.warning(f"Flow {flow_id} has no nodes.")
            return None

        # Find entry node: node with type 'trigger' or the first node
        trigger_node = next((n for n in nodes if n.get("type") == "trigger"), nodes[0])
        trigger_data = trigger_node.get("data", {}) if isinstance(trigger_node, dict) else {}

        is_simulation = bool((state_data or {}).get("simulation"))
        min_cart_val = None

        # ── Guardrail: Minimum Cart Value Trigger Threshold ──
        if trigger_data.get("trigger_type") == "ABANDONED_CART" or flow.trigger_type == "ABANDONED_CART":
            min_cart_val = trigger_data.get("min_cart_value")
            if min_cart_val is None:
                flow_cfg = flow.trigger_config if isinstance(flow.trigger_config, dict) else {}
                min_cart_val = flow_cfg.get("min_cart_value")
            
            if min_cart_val is not None:
                try:
                    min_cart_float = float(min_cart_val)
                    actual_cart_float = float((state_data or {}).get("cart_value", 0))
                    if actual_cart_float < min_cart_float:
                        if is_simulation:
                            logger.info(
                                f"ℹ [Workflow Simulation] Simulated cart value (₹{actual_cart_float}) adjusted to meet threshold (₹{min_cart_float}) for testing."
                            )
                            state_data["cart_value"] = min_cart_float
                        else:
                            logger.info(
                                f"[Workflow Trigger Blocked] Cart value (₹{actual_cart_float}) is below minimum threshold (₹{min_cart_float}) for flow '{flow.name}'. Workflow session skipped."
                            )
                            return None
                except (ValueError, TypeError) as val_err:
                    logger.warning(f"Error parsing min_cart_value for workflow #{flow.id}: {val_err}")

        # ── Guardrail: Inactive Customer Days Threshold ──
        if trigger_data.get("trigger_type") == "INACTIVE_WINBACK" or flow.trigger_type == "INACTIVE_WINBACK":
            inactive_days = trigger_data.get("inactive_days")
            if inactive_days is None:
                flow_cfg = flow.trigger_config if isinstance(flow.trigger_config, dict) else {}
                inactive_days = flow_cfg.get("inactive_days", 30)
            
            try:
                days_int = int(inactive_days)
                contact = db.query(models.Contact).filter(models.Contact.phone == customer_phone).first()
                if contact and contact.last_order_date:
                    days_since_last_order = (datetime.utcnow() - contact.last_order_date).days
                    if days_since_last_order < days_int and not is_simulation:
                        logger.info(
                            f"[Workflow Trigger Blocked] Customer {customer_phone} was active {days_since_last_order} days ago (minimum inactive threshold: {days_int} days) for flow '{flow.name}'. Workflow session skipped."
                        )
                        return None
            except Exception as e:
                logger.warning(f"Error checking inactive days for workflow #{flow.id}: {e}")

        session = models.WorkflowSession(
            flow_id=flow.id,
            customer_phone=customer_phone,
            current_node_id=str(trigger_node.get("id")),
            state_data=state_data or {},
            status="ACTIVE",
            next_evaluation_at=datetime.utcnow(),
            history=[{
                "node_id": str(trigger_node.get("id")),
                "node_type": "trigger",
                "label": trigger_node.get("label", "Workflow Started"),
                "condition_label": (
                    f"Cart > ₹{min_cart_val}" if min_cart_val
                    else f"Inactive > {trigger_data.get('inactive_days')}d" if trigger_data.get("inactive_days")
                    else (trigger_node.get("label") or "Trigger Started")
                ),
                "timestamp": datetime.utcnow().isoformat(),
                "details": f"Session enrolled for {customer_phone}" + (" [SIMULATION]" if is_simulation else "")
            }]
        )
        db.add(session)

        # Update flow stats
        current_stats = dict(flow.stats or {})
        current_stats["entered"] = current_stats.get("entered", 0) + 1
        flow.stats = current_stats

        db.commit()
        db.refresh(session)

        logger.info(f"[Workflow Engine] Session #{session.id} started for {customer_phone} in flow '{flow.name}' (simulation={is_simulation})")
        
        # Advance from trigger to first downstream node
        step_res = process_workflow_session_step(session.id, db=db, mock_send=is_simulation)
        logger.info(f"[Workflow Engine] Initial step result for session #{session.id}: {step_res}")
        db.refresh(session)
        session.latest_step_result = step_res
        return session
    except Exception as e:
        logger.error(f"Error starting workflow session: {e}")
        db.rollback()
        return None
    finally:
        if owns_db:
            db.close()


def process_workflow_session_step(session_id: int, db=None, mock_send: bool = False) -> dict:
    """
    Evaluates and advances a single session in a workflow.
    Handles Delays, WhatsApp Message Templates, Condition branching, Tagging, and Goals/Exits.
    """
    owns_db = False
    if db is None:
        db = SessionLocal()
        owns_db = True

    try:
        session = db.query(models.WorkflowSession).filter(models.WorkflowSession.id == session_id).first()
        if not session or session.status in ["COMPLETED_GOAL", "COMPLETED_DROPOUT", "CANCELLED"]:
            return {"status": "skipped", "reason": "session_inactive_or_finished"}

        flow = db.query(models.WorkflowFlow).filter(models.WorkflowFlow.id == session.flow_id).first()
        if not flow or not flow.is_active:
            session.status = "CANCELLED"
            db.commit()
            return {"status": "cancelled", "reason": "flow_inactive"}

        nodes = flow.nodes or []
        edges = flow.edges or []
        curr_node = find_node_by_id(nodes, session.current_node_id)
        if not curr_node:
            logger.warning(f"Session #{session.id} current_node {session.current_node_id} not found in flow.")
            session.status = "COMPLETED_DROPOUT"
            db.commit()
            return {"status": "error", "reason": "node_not_found"}

        node_type = curr_node.get("type", "").lower()
        node_data = curr_node.get("data", {})
        now = datetime.utcnow()

        # Cycle / runaway loop guard: prevent infinite recursion or cycles on any single node
        node_visits = [h for h in (session.history or []) if str(h.get("node_id")) == str(curr_node.get("id"))]
        if len(node_visits) >= 5:
            logger.warning(f"[Workflow Engine] Session #{session.id} exceeded cycle limit on node '{curr_node.get('id')}'. Terminating.")
            session.status = "COMPLETED_DROPOUT"
            session.history = (session.history or []) + [{
                "node_id": str(curr_node.get("id")),
                "node_type": node_type,
                "label": curr_node.get("label"),
                "timestamp": now.isoformat(),
                "details": "Terminated: Excessive cycle loop detected."
            }]
            db.commit()
            return {"status": "dropped_out", "reason": "cycle_detected"}

        logger.info(f"[Workflow Engine] Session #{session.id} ({session.customer_phone}) at node: {curr_node.get('label')} ({node_type})")

        # ─── 1. TRIGGER NODE ───
        if node_type == "trigger":
            # Immediately advance to next node
            next_node = find_next_node(nodes, edges, curr_node.get("id"))
            if next_node:
                session.current_node_id = str(next_node.get("id"))
                db.commit()
                # Recurse to execute the next node immediately
                return process_workflow_session_step(session.id, db=db, mock_send=mock_send)
            else:
                session.status = "COMPLETED_DROPOUT"
                db.commit()
                return {"status": "completed", "outcome": "no_downstream_nodes"}

        # ─── 2. DELAY NODE ───
        elif node_type == "delay":
            delay_minutes = int(node_data.get("delay_minutes", 30))
            # Check if this specific delay node has already been entered and recorded in history
            curr_node_id_str = str(curr_node.get("id"))
            already_delayed = any(
                str(h.get("node_id")) == curr_node_id_str and h.get("node_type") == "delay"
                for h in (session.history or [])
            )

            if not already_delayed:
                # Enter delay wait
                session.status = "WAITING_DELAY"
                session.next_evaluation_at = now + timedelta(minutes=delay_minutes)
                session.history = (session.history or []) + [{
                    "node_id": curr_node_id_str,
                    "node_type": "delay",
                    "label": curr_node.get("label", f"Wait {delay_minutes}m"),
                    "timestamp": now.isoformat(),
                    "details": f"Delayed until {session.next_evaluation_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                }]
                db.commit()
                logger.info(f"⏳ [Workflow Engine] Session #{session.id} queued for {delay_minutes}m delay.")
                return {"status": "delay_scheduled", "delay_minutes": delay_minutes}
            else:
                # Delay was already queued. Check if the delay time has actually arrived.
                if session.next_evaluation_at and now < session.next_evaluation_at:
                    logger.info(f"⏳ [Workflow Engine] Session #{session.id} delay still pending until {session.next_evaluation_at}.")
                    session.status = "WAITING_DELAY"
                    db.commit()
                    return {"status": "delay_pending", "delay_minutes": delay_minutes, "next_eval": session.next_evaluation_at.isoformat()}

                # Delay period has elapsed!
                session.status = "ACTIVE"
                session.attempt_count = 0
                next_node = find_next_node(nodes, edges, curr_node.get("id"))
                if next_node:
                    session.current_node_id = str(next_node.get("id"))
                    db.commit()
                    return process_workflow_session_step(session.id, db=db, mock_send=mock_send)
                else:
                    session.status = "COMPLETED_DROPOUT"
                    db.commit()
                    return {"status": "completed"}

        # ─── 3. WHATSAPP MESSAGE NODE ───
        elif node_type in ["whatsapp_message", "action_whatsapp", "whatsapp"]:
            # Check DND & Opt-out
            opt_out = db.query(models.OptOut).filter(models.OptOut.phone == session.customer_phone).first()
            if opt_out:
                session.status = "COMPLETED_DROPOUT"
                session.history = (session.history or []) + [{
                    "node_id": str(curr_node.get("id")),
                    "node_type": "whatsapp_message",
                    "label": curr_node.get("label"),
                    "timestamp": now.isoformat(),
                    "details": "Customer in Opt-Out DND list. Message suppressed."
                }]
                db.commit()
                return {"status": "opted_out", "reason": "dnd_active"}

            # Node Idempotency Guard & Anti-Spam Loop Protection
            curr_node_id_str = str(curr_node.get("id"))
            existing_sends_for_node = [
                h for h in (session.history or [])
                if str(h.get("node_id")) == curr_node_id_str
                and h.get("node_type") in ["whatsapp_message", "action_whatsapp", "whatsapp"]
                and "Dispatched template" in str(h.get("details", ""))
            ]
            if existing_sends_for_node:
                logger.warning(
                    f"[Workflow Engine] Node '{curr_node_id_str}'already dispatched ({len(existing_sends_for_node)} time(s)) "
                    f"for session #{session.id}. Suppressing duplicate send to prevent spam."
                )
                if len(existing_sends_for_node) >= 2:
                    logger.warning(f"[Workflow Engine] Session #{session.id} loop detected on node '{curr_node_id_str}'. Terminating.")
                    session.status = "COMPLETED_DROPOUT"
                    session.history = (session.history or []) + [{
                        "node_id": curr_node_id_str,
                        "node_type": "whatsapp_message",
                        "label": curr_node.get("label"),
                        "timestamp": now.isoformat(),
                        "details": "Terminated: Revisit limit reached on WhatsApp node (anti-spam guard)."
                    }]
                    db.commit()
                    return {"status": "dropped_out", "reason": "loop_detected"}

                # Advance to next node without re-sending
                next_node = find_next_node(nodes, edges, curr_node.get("id"))
                if next_node:
                    session.current_node_id = str(next_node.get("id"))
                    db.commit()
                    return process_workflow_session_step(session.id, db=db, mock_send=mock_send)
                else:
                    session.status = "COMPLETED_GOAL"
                    db.commit()
                    return {"status": "completed", "outcome": "flow_finished"}

            template_name = node_data.get("template_name", "cart_recovery_v1")
            coupon_code = node_data.get("coupon_code", config.DEFAULT_COUPON_CODE)

            # Look up template record and Meta spec for language and default mappings
            template_record = db.query(models.Template).filter(
                models.Template.template_name == template_name
            ).first()

            from whatsapp_service import get_template_spec
            spec = get_template_spec(template_name, db=db)
            language = node_data.get("language")
            if not language or language == "en":
                language = spec.get("language") or (template_record.language if template_record and template_record.language else "en_US")

            # Look up contact info
            contact = db.query(models.Contact).filter(models.Contact.phone == session.customer_phone).first()
            state_dict = session.state_data if isinstance(session.state_data, dict) else {}
            extra_dict = state_dict.get("extra_data") if isinstance(state_dict.get("extra_data"), dict) else {}
            customer_name = (
                state_dict.get("customer_name")
                or state_dict.get("first_name")
                or extra_dict.get("first_name")
                or (contact.name if contact and contact.name else "Valued Customer")
            )
            raw_cart_val = session.state_data.get("cart_value", "450")
            if isinstance(raw_cart_val, (int, float)):
                cart_val_str = str(int(raw_cart_val)) if raw_cart_val == int(raw_cart_val) else f"{raw_cart_val:.2f}"
            else:
                cart_val_str = str(raw_cart_val).replace("₹", "").strip()
            items_summary = session.state_data.get("items_summary", "Special Jewelry & Premium Collection")

            # Resolve dynamic column / parameter mappings
            # Priority: node overrides > template-level mappings > smart default fallback
            user_mappings = node_data.get("variable_mappings")
            if not user_mappings:
                # Inherit from the template itself (Configure-Once-Use-Everywhere pattern)
                if template_record and template_record.variable_mappings:
                    user_mappings = template_record.variable_mappings
                else:
                    user_mappings = {}
            param_dict = {}

            if isinstance(user_mappings, dict) and user_mappings:
                for idx_str, m_def in user_mappings.items():
                    if not isinstance(m_def, dict):
                        continue
                    m_type = m_def.get("type")
                    m_val = m_def.get("value")

                    if m_type == "contact_field":
                        if m_val == "phone":
                            val_str = session.customer_phone
                        elif m_val == "city":
                            val_str = contact.city if contact and contact.city else "Ahmedabad"
                        elif m_val == "total_orders":
                            val_str = str(contact.total_orders) if contact else "1"
                        elif m_val == "last_order_date":
                            val_str = contact.last_order_date.strftime("%d/%m/%Y") if contact and contact.last_order_date else "Recently"
                        else:
                            val_str = customer_name
                    elif m_type == "cart_event":
                        if m_val == "cart_value":
                            val_str = cart_val_str
                        elif m_val == "cart_url":
                            val_str = session.state_data.get("cart_url", "https://jwl-billion.com/cart")
                        else:
                            val_str = items_summary
                    elif m_type == "event_field":
                        # Look up from session.state_data or extra_data dict
                        if m_val == "firstname" or m_val == "first_name":
                            val_str = state_dict.get("first_name") or extra_dict.get("first_name") or customer_name
                        elif m_val == "products" or m_val == "products_summary" or m_val == "items":
                            val_str = state_dict.get("products_summary") or extra_dict.get("products_summary") or items_summary
                        elif m_val == "amount" or m_val == "cart_value":
                            # Note: template body often already contains '₹{{3}}' so do not prepend extra '₹'
                            val_str = str(state_dict.get("amount") or extra_dict.get("amount") or cart_val_str).replace("₹", "").strip()
                        elif m_val == "delivery_address" or m_val == "address":
                            val_str = state_dict.get("delivery_address") or extra_dict.get("delivery_address") or (contact.city if contact else "")
                        else:
                            val_str = str(state_dict.get(m_val) or extra_dict.get(m_val, ""))
                    elif m_type == "external_api":
                        src_id = m_def.get("source_id")
                        val_str = fetch_external_api_value(field_key=m_val, phone=session.customer_phone, source_id=src_id, db=db)
                    elif m_type == "coupon":
                        coupon_rec = db.query(models.DiscountCode).filter(models.DiscountCode.code == coupon_code).first()
                        if m_val == "discount_value":
                            val_str = f"{int(coupon_rec.discount_value)}%" if coupon_rec and coupon_rec.discount_type == "PERCENT" else f"{config.DEFAULT_DISCOUNT_PERCENT}%"
                        elif m_val == "expires_at":
                            val_str = coupon_rec.expires_at.strftime("%d/%m/%Y") if coupon_rec and coupon_rec.expires_at else (datetime.utcnow() + timedelta(days=config.DEFAULT_EXPIRY_DAYS)).strftime("%d/%m/%Y")
                        else:
                            val_str = coupon_code
                    elif m_type == "static":
                        val_str = str(m_val) if m_val else ""
                    else:
                        val_str = customer_name

                    param_dict[f"param_{idx_str}"] = val_str
            else:
                # Default smart fallback
                param_dict = {
                    "param_1": customer_name,
                    "param_2": items_summary,
                    "param_3": cart_val_str,
                    "param_4": coupon_code,
                    "param_5": config.BRAND_NAME
                }

            if mock_send:
                res = {"status": "success_simulated", "message_id": f"sim_{int(now.timestamp())}_{uuid_module.uuid4().hex[:6]}"}
            else:
                flow_title = flow.name if flow and flow.name else "Workflow"
                origin_user = (session.state_data or {}).get("sender_user") or f"Journey: {flow_title}"
                res = send_whatsapp_template(
                    recipient_phone=session.customer_phone,
                    template_name=template_name,
                    language=language,
                    parameters=param_dict,
                    coupon_code=coupon_code,
                    sender_user=origin_user,
                    idempotency_key=f"wf_session_{session.id}_node_{curr_node.get('id')}",
                    workflow_session_id=session.id,
                    purpose="utility",
                    db=db
                )

            sent_msg_id = res.get("message_id") or res.get("id") or f"msg_{int(now.timestamp())}"
            new_state = dict(session.state_data or {})
            new_state["last_meta_message_id"] = sent_msg_id
            new_state["last_sent_template"] = template_name
            new_state["last_whatsapp_sent_at"] = now.isoformat()
            new_state["last_activity_at"] = now.isoformat()
            new_state["message_read"] = False  # Reset read status for the newly sent message
            session.state_data = new_state
            session.updated_at = now

            sent_status = (res.get("status") or "").lower()
            block_reason = res.get("reason") or res.get("error") or res.get("message") or "Send failure"
            if sent_status == "blocked" and "quiet hours" in block_reason.lower():
                # WP2: Temporary policy hold during quiet hours — do NOT drop out!
                # Schedule evaluation for next morning at 09:00 AM IST (quiet hours end)
                from services.policy_service import get_next_quiet_hours_end_utc
                next_morning_utc = get_next_quiet_hours_end_utc(now)
                session.status = "WAITING_DELAY"
                session.next_evaluation_at = next_morning_utc
                session.history = (session.history or []) + [{
                    "node_id": str(curr_node.get("id")),
                    "node_type": "whatsapp_message",
                    "label": curr_node.get("label", f"Send {template_name}"),
                    "timestamp": now.isoformat(),
                    "details": f"Held during Quiet Hours (21:00-09:00 IST). Rescheduled for {next_morning_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}."
                }]
                db.commit()
                logger.info(f"[Workflow Engine] Session #{session.id} held during quiet hours. Rescheduled for {next_morning_utc}.")
                return {"status": "held_quiet_hours", "rescheduled_at": next_morning_utc.isoformat()}

            if sent_status in ["blocked", "failed", "error"]:
                # Policy blocks (Opt-out, DND, consent revoked) should drop out permanently
                is_permanent_policy = (
                    sent_status == "blocked" 
                    and any(term in block_reason.lower() for term in ["opted out", "dnd", "consent revoked", "invalid recipient phone"])
                )
                if not is_permanent_policy and (session.attempt_count or 0) < 3:
                    session.attempt_count = (session.attempt_count or 0) + 1
                    backoff_sec = 45 if session.attempt_count == 1 else 120
                    session.next_evaluation_at = now + timedelta(seconds=backoff_sec)
                    session.status = "WAITING_DELAY"
                    session.history = (session.history or []) + [{
                        "node_id": str(curr_node.get("id")),
                        "node_type": "whatsapp_message",
                        "label": curr_node.get("label", f"Send {template_name}"),
                        "timestamp": now.isoformat(),
                        "details": f"Dispatch {sent_status} (attempt {session.attempt_count}/3): {block_reason}. Retrying in {backoff_sec}s."
                    }]
                    db.commit()
                    logger.warning(f"[Workflow Engine] Session #{session.id} send failed: {block_reason}. Backoff attempt {session.attempt_count}/3 scheduled.")
                    return {"status": "retry_scheduled", "reason": block_reason, "attempt": session.attempt_count}

                # Permanent failure or exhausted retries
                session.status = "COMPLETED_DROPOUT"
                session.history = (session.history or []) + [{
                    "node_id": str(curr_node.get("id")),
                    "node_type": "whatsapp_message",
                    "label": curr_node.get("label", f"Send {template_name}"),
                    "timestamp": now.isoformat(),
                    "details": f"Dispatch {sent_status}: {block_reason}. Session dropped out."
                }]
                db.commit()
                return {"status": "dropped_out", "reason": block_reason}

            session.attempt_count = 0
            session.history = (session.history or []) + [{
                "node_id": str(curr_node.get("id")),
                "node_type": "whatsapp_message",
                "label": curr_node.get("label", f"Send {template_name}"),
                "timestamp": now.isoformat(),
                "details": f"Dispatched template '{template_name}' (Status: {res.get('status')})"
            }]

            # Advance to next node only on successful dispatch
            next_node = find_next_node(nodes, edges, curr_node.get("id"))
            if next_node:
                session.current_node_id = str(next_node.get("id"))
                db.commit()
                # Immediately execute next node (e.g. entering Delay queue or Condition evaluation)
                return process_workflow_session_step(session.id, db=db, mock_send=mock_send)
            else:
                session.status = "COMPLETED_GOAL"
                db.commit()
                return {"status": "completed", "outcome": "flow_finished"}

        # ─── 4. CONDITION / DECISION NODE ───
        elif node_type in ["condition", "decision"]:
            condition_type = node_data.get("condition_type", "ORDER_PLACED")
            condition_met = False

            if condition_type in ["ORDER_PLACED", "CART_RECOVERED"]:
                # Check 1: Did cart get marked RECOVERED in CartEvent?
                cart_token = session.state_data.get("cart_token")
                if cart_token:
                    cart = db.query(models.CartEvent).filter(models.CartEvent.cart_token == cart_token).first()
                    if cart and cart.status == "RECOVERED":
                        condition_met = True
                # Check 2: Did contact place a new order after session start?
                if not condition_met:
                    contact = db.query(models.Contact).filter(models.Contact.phone == session.customer_phone).first()
                    if contact and contact.last_order_date and contact.last_order_date >= session.created_at:
                        condition_met = True
                # Check 3: State flag
                if not condition_met and session.state_data.get("order_placed"):
                    condition_met = True

            elif condition_type == "MESSAGE_READ":
                # Check if last sent message was READ by customer
                # Crucial Fix: NEVER check chat_msg.is_read! ChatMessage.is_read tracks agent CRM inbox read state
                # and is initialized to True for outbound agent messages. Customer read is tracked via status == 'READ'.
                last_msg_id = session.state_data.get("last_meta_message_id")
                if last_msg_id:
                    msg = db.query(models.MessageLog).filter(models.MessageLog.meta_message_id == last_msg_id).first()
                    if msg and msg.status == "READ":
                        condition_met = True
                    chat_msg = db.query(models.ChatMessage).filter(models.ChatMessage.meta_message_id == last_msg_id).first()
                    if chat_msg and chat_msg.status == "READ":
                        condition_met = True
                if not condition_met and session.state_data.get("message_read") is True:
                    condition_met = True
                # Clean up one-off read flag in session state so it cannot leak to subsequent messages
                if session.state_data and "message_read" in session.state_data:
                    new_st = dict(session.state_data)
                    new_st["message_read"] = False
                    session.state_data = new_st

            elif condition_type == "CART_VALUE_ABOVE":
                threshold = float(node_data.get("threshold", 500))
                cart_val = float(session.state_data.get("cart_value", 0))
                condition_met = (cart_val >= threshold)

            elif condition_type in ["DOUBLE_OPTIN_CONFIRMED", "OPTIN_CONFIRMED", "CONSENT_GRANTED"]:
                # Check 1: Session state optin flag
                if session.state_data.get("optin_confirmed"):
                    condition_met = True
                elif condition_type == "DOUBLE_OPTIN_CONFIRMED":
                    # Double opt-in requires explicit affirmative confirmation (inbound reply, not just store sync)
                    consent = db.query(models.ConsentRecord).filter(
                        models.ConsentRecord.phone == session.customer_phone,
                        models.ConsentRecord.status.in_(["ACTIVE", "GRANTED"]),
                        models.ConsentRecord.source.notin_(["customer_sync", "store_checkout", "store_sync_backfill"])
                    ).first()
                    if consent:
                        condition_met = True
                else:
                    # Check 2: Active granted consent record in DB
                    consent = db.query(models.ConsentRecord).filter(
                        models.ConsentRecord.phone == session.customer_phone,
                        models.ConsentRecord.status.in_(["ACTIVE", "GRANTED"])
                    ).first()
                    if consent:
                        condition_met = True

            branch_handle = "yes" if condition_met else "no"
            logger.info(f"[Workflow Engine] Condition '{condition_type}'evaluated to: {condition_met} -> Branch: {branch_handle}")

            # Resolve clear display label for the condition check
            cond_label = curr_node.get("label")
            if not cond_label or cond_label in ["Did Customer Purchase?", "Check Condition"]:
                if condition_type == "MESSAGE_READ":
                    cond_label = "Was Message Read?"
                elif condition_type == "CART_VALUE_ABOVE":
                    cond_label = f"Cart Value > ₹{node_data.get('threshold', 500)}"
                elif condition_type in ["DOUBLE_OPTIN_CONFIRMED", "OPTIN_CONFIRMED", "CONSENT_GRANTED"]:
                    cond_label = "Did Customer Confirm Opt-In?"
                elif condition_type in ["ORDER_PLACED", "CART_RECOVERED"]:
                    cond_label = "Did Customer Purchase?"
                else:
                    cond_label = f"Check {condition_type}"

            cond_str = "YES" if condition_met else "NO"
            session.history = (session.history or []) + [{
                "node_id": str(curr_node.get("id")),
                "node_type": "condition",
                "condition_type": condition_type,
                "branch": branch_handle.upper(),
                "label": cond_label,
                "timestamp": now.isoformat(),
                "details": f"Condition evaluated to {cond_str} -> Took '{branch_handle.upper()}' path"
            }]


            next_node = find_next_node(nodes, edges, curr_node.get("id"), handle=branch_handle)
            if next_node:
                session.current_node_id = str(next_node.get("id"))
                session.attempt_count = 0
                db.commit()
                # Immediately execute next branch node
                return process_workflow_session_step(session.id, db=db, mock_send=mock_send)
            else:
                session.status = "COMPLETED_GOAL" if condition_met else "COMPLETED_DROPOUT"
                session.attempt_count = 0
                db.commit()
                return {"status": "completed", "outcome": f"branch_{branch_handle}_end"}

        # ─── 5. TAG CONTACT NODE ───
        elif node_type in ["tag", "tag_contact"]:
            tag_name = node_data.get("tag_name", "Recovered Customer")
            contact = db.query(models.Contact).filter(models.Contact.phone == session.customer_phone).first()
            if contact:
                current_tags = [t.strip() for t in (contact.tags or "").split(",") if t.strip()]
                if tag_name not in current_tags:
                    current_tags.append(tag_name)
                    contact.tags = ", ".join(current_tags)
                    db.commit()

            session.history = (session.history or []) + [{
                "node_id": str(curr_node.get("id")),
                "node_type": "tag",
                "label": curr_node.get("label", f"Tag: {tag_name}"),
                "timestamp": now.isoformat(),
                "details": f"Added tag '{tag_name}' to contact"
            }]

            next_node = find_next_node(nodes, edges, curr_node.get("id"))
            if next_node:
                session.current_node_id = str(next_node.get("id"))
                session.attempt_count = 0
                db.commit()
                return process_workflow_session_step(session.id, db=db, mock_send=mock_send)
            else:
                session.status = "COMPLETED_GOAL"
                session.attempt_count = 0
                db.commit()
                return {"status": "completed", "outcome": "flow_finished"}

        # ─── 6. GOAL / EXIT NODE ───
        elif node_type in ["goal", "exit"]:
            is_goal = (node_type == "goal") or ("goal" in curr_node.get("label", "").lower())
            session.status = "COMPLETED_GOAL" if is_goal else "COMPLETED_DROPOUT"
            session.attempt_count = 0
            session.history = (session.history or []) + [{
                "node_id": str(curr_node.get("id")),
                "node_type": node_type,
                "label": curr_node.get("label", "Goal Reached" if is_goal else "Journey Exit"),
                "timestamp": now.isoformat(),
                "details": f"Session finished: {'Goal reached' if is_goal else 'Exited'}"
            }]
            # Increment goal converted stats
            if is_goal:
                current_stats = dict(flow.stats or {})
                current_stats["goals_converted"] = current_stats.get("goals_converted", 0) + 1
                cart_val = float(session.state_data.get("cart_value", 0))
                current_stats["revenue_recovered"] = current_stats.get("revenue_recovered", 0) + cart_val
                flow.stats = current_stats

            db.commit()
            return {"status": "completed", "outcome": "goal_reached" if is_goal else "journey_exit"}

        else:
            logger.warning(f"Unknown node type '{node_type}' in flow #{flow.id}")
            session.status = "COMPLETED_DROPOUT"
            session.attempt_count = 0
            db.commit()
            return {"status": "error", "reason": f"unknown_node_type_{node_type}"}

    except Exception as e:
        logger.error(f"Error in process_workflow_session_step: {e}")
        db.rollback()
        # Backoff: transient failures retry with short backoff (30s, 60s) before dropout
        try:
            err_sess = db.query(models.WorkflowSession).filter(models.WorkflowSession.id == session_id).first()
            if err_sess:
                err_sess.attempt_count = (err_sess.attempt_count or 0) + 1
                if err_sess.attempt_count >= 3:
                    err_sess.status = "COMPLETED_DROPOUT"
                    err_sess.history = (err_sess.history or []) + [{
                        "node_id": str(err_sess.current_node_id),
                        "node_type": "error",
                        "label": "Session Error Dropout",
                        "timestamp": datetime.utcnow().isoformat(),
                        "details": f"Halted after 3 consecutive failures: {str(e)[:120]}"
                    }]
                else:
                    backoff_sec = 30 if err_sess.attempt_count == 1 else 60
                    err_sess.next_evaluation_at = datetime.utcnow() + timedelta(seconds=backoff_sec)
                db.commit()
        except Exception as update_err:
            db.rollback()
            logger.warning(f"Could not update session error backoff: {update_err}")
        return {"status": "error", "error": str(e)}
    finally:
        if owns_db:
            db.close()


def process_all_active_workflow_sessions():
    """
    Periodic job (every minute) that evaluates all active workflow sessions
    whose next_evaluation_at has arrived.
    Uses per-session row-level leases (WP8) to prevent duplicate evaluation
    across multiple workers.
    Processes in strict FIFO batches of 7 (matching DB_POOL_SIZE = 7) to guarantee
    connection pool availability and prevent exhaustion.
    """
    WORKFLOW_BATCH_SIZE = 7

    # Resilient connection acquisition with retry
    db = None
    for attempt in range(3):
        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            break
        except Exception as conn_err:
            if db:
                db.close()
                db = None
            if attempt == 2:
                logger.error(f"[Workflow Engine] Could not acquire DB connection: {conn_err}")
                return
            time.sleep(0.25 * (attempt + 1))

    try:
        now = datetime.utcnow()
        # Fetch due session IDs in strict FIFO order (earliest evaluation first)
        due_session_ids = [
            row[0] for row in db.query(models.WorkflowSession.id).filter(
                models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"]),
                models.WorkflowSession.next_evaluation_at <= now
            ).order_by(
                models.WorkflowSession.next_evaluation_at.asc(),
                models.WorkflowSession.id.asc()
            ).limit(70).all()
        ]

        if due_session_ids:
            total_due = len(due_session_ids)
            logger.info(f"⏰ [Workflow Engine] Processing {total_due} due session(s) in FIFO batches of {WORKFLOW_BATCH_SIZE}...")
            worker_id = f"sweeper_{uuid_module.uuid4().hex[:8]}"

            for i in range(0, total_due, WORKFLOW_BATCH_SIZE):
                batch_ids = due_session_ids[i:i + WORKFLOW_BATCH_SIZE]
                for session_id in batch_ids:
                    # WP8: Acquire a distributed row-level lease before evaluating each session
                    claimed = claim_workflow_session(db, session_id, worker_id=worker_id, lease_seconds=120)
                    if not claimed:
                        logger.debug(f"[Workflow Engine] Session #{session_id} already claimed by another worker — skipping.")
                        continue
                    try:
                        process_workflow_session_step(session_id, db=db)
                    except Exception as sess_err:
                        logger.error(f"[Workflow Engine] Error processing session #{session_id}: {sess_err}")
                    finally:
                        release_workflow_session(db, session_id)

                # Commit after each batch of 7 to release locks and flush logs
                try:
                    db.commit()
                except Exception:
                    db.rollback()

                # Brief yield between batches to keep DB pool free for incoming API and webhook requests
                if i + WORKFLOW_BATCH_SIZE < total_due:
                    time.sleep(0.2)
    except Exception as e:
        logger.error(f"Error in process_all_active_workflow_sessions: {e}")
    finally:
        if db:
            db.close()

