"""
Smart Link Tracking & Attribution Redirect Router.
Generates personalized tracking URLs for WhatsApp campaigns and automations,
tracks clicks with recipient identity and timestamp, and issues instant 302 redirects.
"""

import time
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

import models
from database import get_db

logger = logging.getLogger("redirect_router")

router = APIRouter(tags=["Smart Link Tracking & Redirects"])


# Rate-limiting / deduplication cache for link followups to prevent duplicate messages
# Key: (phone, tracking_code), Value: timestamp of last follow-up trigger
_LINK_FOLLOWUP_LOCKS: dict[tuple[str, str], float] = {}
_LINK_FOLLOWUP_COOLDOWN_SECONDS = 3600  # 1 hour per specific link per customer


def _delayed_followup_after_click(phone: str, tracking_code: str, delay_seconds: int = 20):
    """
    Waits 20 seconds after a customer clicks a product link in chat,
    then checks if a human or customer already replied before asking how they liked the jewellery.
    Deduplicated per (phone, tracking_code) so repeated taps on the same link never spam the customer.
    """
    time.sleep(delay_seconds)
    try:
        from database import SessionLocal
        from whatsapp_service import send_whatsapp_free_text
        from services.bot_service import _save_bot_message
        db = SessionLocal()
        try:
            clean_p = phone.replace("+", "").strip()
            # Check if AI is paused for this customer
            contact = db.query(models.Contact).filter(
                models.Contact.phone.in_([phone, clean_p, f"+{clean_p}"])
            ).first()
            if contact and isinstance(contact.custom_attributes, dict):
                if contact.custom_attributes.get("ai_disabled"):
                    logger.info(f"[Link Followup] AI disabled for {phone}. Skipping click follow-up.")
                    return

            # Check recent messages in the last 25 seconds to see if customer or agent already chatted
            cutoff = datetime.utcnow() - __import__('datetime').timedelta(seconds=25)
            recent_msg = db.query(models.ChatMessage).filter(
                models.ChatMessage.customer_phone.in_([phone, clean_p, f"+{clean_p}"]),
                models.ChatMessage.created_at >= cutoff
            ).first()

            if recent_msg:
                logger.info(f"[Link Followup] New message already exchanged with {phone}. Skipping follow-up.")
                return

            followup_text = "Aapko yeh jewellery design kaisa laga? Pasand aaya ya koi aur style dekhna chahenge? 😊"
            res = send_whatsapp_free_text(phone, followup_text, db=db)
            _save_bot_message(db, phone, followup_text, res.get("message_id"))
            logger.info(f"[Link Followup Sent] 20s post-click follow-up delivered to {phone} for code {tracking_code}")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"[Link Followup Error] Failed to send 20s click follow-up: {e}")


@router.get("/r/{tracking_code}")
def track_and_redirect(
    tracking_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Public click-tracking redirect endpoint.
    Example: https://130-210-23-25.sslip.io/r/c3_918780001820
    Records click event in link_clicks table and redirects browser to destination URL.
    """
    # Strip any trailing sentence punctuation that mobile clients or browsers include in tracking_code
    tracking_code = (tracking_code or "").rstrip(".,;:!?")
    # 1. Parse tracking code pattern: e.g. "c{campaign_id}_{phone}" or custom code
    campaign_id = None
    recipient_phone = None
    target_url = "https://jwlbillion.com"

    # Helper to validate and sanitize target URLs so nonexistent, truncated or hallucinated paths never 404
    def _sanitize_destination(raw_target: str) -> str:
        if not raw_target or not raw_target.startswith("http://") and not raw_target.startswith("https://"):
            return "https://jwlbillion.com"
        u_clean = raw_target.rstrip(".,;:!?")
        u_lower = u_clean.lower()
        if "jwlbillion.com" not in u_lower or u_clean.strip() in ["https://", "http://", "https:/", "http:/"]:
            return "https://jwlbillion.com"

        from services.shopify_service import fetch_shopify_products
        try:
            catalog_data = fetch_shopify_products(limit=250)
            valid_handles = {p.get("handle") for p in catalog_data.get("products", []) if p.get("handle")}
        except Exception:
            valid_handles = set()

        import re
        prod_m = re.search(r'/products/([a-zA-Z0-9_-]+)', u_clean)
        if prod_m:
            slug = prod_m.group(1).lower()
            if valid_handles and slug not in valid_handles:
                # 404 product slug fallback to matching collection
                if "earring" in slug:
                    return "https://jwlbillion.com/collections/earrings"
                elif "bangle" in slug:
                    return "https://jwlbillion.com/collections/bangle"
                elif "bracelet" in slug or "kada" in slug:
                    return "https://jwlbillion.com/collections/bracelet"
                elif "chain" in slug:
                    return "https://jwlbillion.com/collections/chains"
                elif "ring" in slug:
                    return "https://jwlbillion.com/collections/rings"
                elif "necklace" in slug or "pendant" in slug:
                    return "https://jwlbillion.com/collections/necklace"
                return "https://jwlbillion.com/collections/all"
            return u_clean

        if "/collections/" in u_clean:
            return u_clean

        # Malformed route like /ladies-earrings/
        if "earring" in u_lower:
            return "https://jwlbillion.com/collections/earrings"
        elif "bangle" in u_lower:
            return "https://jwlbillion.com/collections/bangle"
        elif "bracelet" in u_lower or "kada" in u_lower:
            return "https://jwlbillion.com/collections/bracelet"
        elif "chain" in u_lower:
            return "https://jwlbillion.com/collections/chains"
        elif "ring" in u_lower:
            return "https://jwlbillion.com/collections/rings"
        elif "necklace" in u_lower or "pendant" in u_lower:
            return "https://jwlbillion.com/collections/necklace"
        return "https://jwlbillion.com"

    # Check if this tracking code was pre-registered or if it follows structured convention
    existing_click = db.query(models.LinkClick).filter(models.LinkClick.tracking_code == tracking_code).first()
    if existing_click and existing_click.target_url:
        target_url = _sanitize_destination(existing_click.target_url)
        campaign_id = existing_click.campaign_id
        recipient_phone = existing_click.recipient_phone
    else:
        # Structured code parsing:
        # 1. Base64 URL: u_{phone}_{b64_url} (arbitrary product link in AI/live chat)
        # 2. Campaign link: c{campaign_id}_{phone}
        # 3. Cart link: cart_{phone}
        parts = tracking_code.split("_", 2)
        if len(parts) >= 2:
            prefix = parts[0]
            phone_part = parts[1]
            if phone_part and phone_part != "guest":
                recipient_phone = f"+{phone_part}" if not phone_part.startswith("+") else phone_part

            if prefix == "u" and len(parts) == 3:
                # Arbitrary encoded URL
                try:
                    import base64
                    b64_str = parts[2]
                    padding = 4 - (len(b64_str) % 4)
                    if padding != 4:
                        b64_str += "=" * padding
                    decoded = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
                    target_url = _sanitize_destination(decoded)
                except Exception as dec_err:
                    logger.warning(f"Failed to decode tracking b64: {dec_err}")
            elif prefix.startswith("c") and prefix[1:].isdigit():
                campaign_id = int(prefix[1:])
                # Lookup campaign template or default product
                camp = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
                if camp and "pyrite" in (camp.template_name or "").lower():
                    target_url = "https://jwlbillion.com/products/pyrite-anklet-for-womens"
            elif prefix.startswith("cart"):
                target_url = "https://jwlbillion.com/cart"

    # Determine distinct click source: "chat", "broadcast", or "cart_recovery"
    click_source = "broadcast" if campaign_id else ("cart_recovery" if tracking_code.startswith("cart_") else "chat")

    # 2. Record click event
    try:
        user_agent = request.headers.get("user-agent", "")[:250]
        client_ip = request.client.host if request.client else None
        
        click_record = models.LinkClick(
            tracking_code=tracking_code,
            recipient_phone=recipient_phone,
            campaign_id=campaign_id,
            source=click_source,
            target_url=target_url,
            user_agent=user_agent,
            ip_address=client_ip,
            clicked_at=datetime.utcnow()
        )
        db.add(click_record)
        db.commit()
        logger.info(f"[Link Click Tracked] Code={tracking_code}, Phone={recipient_phone}, Campaign={campaign_id} -> {target_url}")
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to record link click: {e}")

    # 3. If click originated from chat, schedule polite follow-up after 20 seconds
    # Cooldown check: ensures the customer does NOT receive the same follow-up if they tap the same link again within 1 hour
    if click_source == "chat" and recipient_phone:
        now_ts = time.time()
        dedup_key = (recipient_phone.replace("+", "").strip(), tracking_code)
        last_triggered = _LINK_FOLLOWUP_LOCKS.get(dedup_key, 0)
        if (now_ts - last_triggered) >= _LINK_FOLLOWUP_COOLDOWN_SECONDS:
            _LINK_FOLLOWUP_LOCKS[dedup_key] = now_ts
            background_tasks.add_task(_delayed_followup_after_click, recipient_phone, tracking_code, delay_seconds=20)
        else:
            logger.info(f"[Link Followup Skipped] Cooldown active for {recipient_phone} on tracking code {tracking_code}")

    # 4. Add UTM parameters for Google Analytics / Shopify attribution if not already present
    sep = "&" if "?" in target_url else "?"
    utm_params = f"{sep}utm_source=whatsapp&utm_medium=broadcast"
    if campaign_id:
        utm_params += f"&utm_campaign=campaign_{campaign_id}"
    if recipient_phone:
        utm_params += f"&w_recipient={recipient_phone.replace('+', '')}"
    
    redirect_destination = f"{target_url}{utm_params}"
    return RedirectResponse(url=redirect_destination, status_code=302)
