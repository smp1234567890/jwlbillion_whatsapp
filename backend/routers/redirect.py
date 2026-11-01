"""
Smart Link Tracking & Attribution Redirect Router.
Generates personalized tracking URLs for WhatsApp campaigns and automations,
tracks clicks with recipient identity and timestamp, and issues instant 302 redirects.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

import models
from database import get_db

logger = logging.getLogger("redirect_router")

router = APIRouter(tags=["Smart Link Tracking & Redirects"])


@router.get("/r/{tracking_code}")
def track_and_redirect(
    tracking_code: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public click-tracking redirect endpoint.
    Example: https://130-210-23-25.sslip.io/r/c3_918780001820
    Records click event in link_clicks table and redirects browser to destination URL.
    """
    # 1. Parse tracking code pattern: e.g. "c{campaign_id}_{phone}" or custom code
    campaign_id = None
    recipient_phone = None
    target_url = "https://jwlbillion.com"

    # Check if this tracking code was pre-registered or if it follows structured convention
    existing_click = db.query(models.LinkClick).filter(models.LinkClick.tracking_code == tracking_code).first()
    if existing_click and existing_click.target_url:
        target_url = existing_click.target_url
        campaign_id = existing_click.campaign_id
        recipient_phone = existing_click.recipient_phone
    else:
        # Structured code parsing: c{campaign_id}_{phone_without_plus}
        # e.g. "c3_918780001820" or "cart_918780001820"
        parts = tracking_code.split("_")
        if len(parts) >= 2:
            prefix = parts[0]
            phone_part = parts[1]
            if phone_part:
                recipient_phone = f"+{phone_part}" if not phone_part.startswith("+") else phone_part
            
            if prefix.startswith("c") and prefix[1:].isdigit():
                campaign_id = int(prefix[1:])
                # Lookup campaign template or default product
                camp = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
                if camp and "pyrite" in (camp.template_name or "").lower():
                    target_url = "https://jwlbillion.com/products/pyrite-anklet-for-womens"
            elif prefix.startswith("cart"):
                target_url = "https://jwlbillion.com/cart"

    # 2. Record click event
    try:
        user_agent = request.headers.get("user-agent", "")[:250]
        client_ip = request.client.host if request.client else None
        
        click_record = models.LinkClick(
            tracking_code=tracking_code,
            recipient_phone=recipient_phone,
            campaign_id=campaign_id,
            source="campaign" if campaign_id else "automation",
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

    # 3. Add UTM parameters for Google Analytics / Shopify attribution if not already present
    sep = "&" if "?" in target_url else "?"
    utm_params = f"{sep}utm_source=whatsapp&utm_medium=broadcast"
    if campaign_id:
        utm_params += f"&utm_campaign=campaign_{campaign_id}"
    if recipient_phone:
        utm_params += f"&w_recipient={recipient_phone.replace('+', '')}"
    
    redirect_destination = f"{target_url}{utm_params}"
    return RedirectResponse(url=redirect_destination, status_code=302)
