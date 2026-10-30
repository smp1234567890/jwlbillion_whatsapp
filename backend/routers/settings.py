import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
import auth
import config
from whatsapp_service import OPT_OUT_KEYWORDS

logger = logging.getLogger("settings_router")

router = APIRouter(tags=["Platform & Integration Settings"])


class WhatsAppBusinessProfileUpdate(BaseModel):
    about: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    websites: Optional[List[str]] = None
    vertical: Optional[str] = None


@router.get("/api/whatsapp/profile")
def get_whatsapp_business_profile(
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Fetches the live WhatsApp Business Profile from Meta Graph API.
    """
    token = config.WHATSAPP_API_TOKEN
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    if not token or not phone_id:
        raise HTTPException(status_code=400, detail="WhatsApp API credentials not configured.")

    try:
        # 1. Fetch profile fields
        profile_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{phone_id}/whatsapp_business_profile?fields=about,address,description,email,profile_picture_url,websites,vertical"
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.get(profile_url, headers=headers, timeout=config.HTTP_TIMEOUT_SECONDS)
        
        profile_data = {}
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                profile_data = data[0]
        else:
            logger.warning(f"Failed to fetch profile: {resp.text}")

        # 2. Fetch phone details (verified name, display number, quality rating)
        phone_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{phone_id}?fields=verified_name,code_verification_status,display_phone_number,quality_rating"
        phone_resp = httpx.get(phone_url, headers=headers, timeout=config.HTTP_TIMEOUT_SECONDS)
        phone_data = {}
        if phone_resp.status_code == 200:
            phone_data = phone_resp.json()

        return {
            "status": "success",
            "phone_id": phone_id,
            "verified_name": phone_data.get("verified_name") or config.BRAND_NAME,
            "display_phone_number": phone_data.get("display_phone_number", ""),
            "quality_rating": phone_data.get("quality_rating", "GREEN"),
            "code_verification_status": phone_data.get("code_verification_status", "VERIFIED"),
            "about": profile_data.get("about", ""),
            "address": profile_data.get("address", ""),
            "description": profile_data.get("description", ""),
            "email": profile_data.get("email", ""),
            "profile_picture_url": profile_data.get("profile_picture_url", ""),
            "websites": profile_data.get("websites", []),
            "vertical": profile_data.get("vertical", "RETAIL")
        }
    except Exception as e:
        logger.error(f"Error getting whatsapp business profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/whatsapp/profile")
def update_whatsapp_business_profile(
    payload: WhatsAppBusinessProfileUpdate,
    current_user: models.User = Depends(auth.require_roles("admin", "manager"))
):
    """
    Updates the WhatsApp Business Profile on Meta Graph API.
    """
    token = config.WHATSAPP_API_TOKEN
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    if not token or not phone_id:
        raise HTTPException(status_code=400, detail="WhatsApp API credentials not configured.")

    meta_payload = {"messaging_product": "whatsapp"}
    if payload.about is not None:
        meta_payload["about"] = payload.about.strip()
    if payload.address is not None:
        meta_payload["address"] = payload.address.strip()
    if payload.description is not None:
        meta_payload["description"] = payload.description.strip()
    if payload.email is not None:
        meta_payload["email"] = payload.email.strip()
    if payload.websites is not None:
        meta_payload["websites"] = [w.strip() for w in payload.websites if w.strip()]
    if payload.vertical is not None:
        meta_payload["vertical"] = payload.vertical.strip()

    try:
        url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{phone_id}/whatsapp_business_profile"
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.post(url, headers=headers, json=meta_payload, timeout=config.HTTP_TIMEOUT_SECONDS)
        
        if resp.status_code in [200, 201]:
            return {"status": "success", "message": "WhatsApp Business Profile successfully updated on Meta."}
        else:
            err_json = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = err_json.get("error", {}).get("message") or resp.text
            raise HTTPException(status_code=resp.status_code, detail=f"Meta API error: {err_msg}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating whatsapp business profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/whatsapp/profile/photo")
async def update_whatsapp_profile_photo(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.require_roles("admin", "manager"))
):
    """
    Updates the WhatsApp Business Profile Picture via Meta Resumable Upload session.
    """
    token = config.WHATSAPP_API_TOKEN
    phone_id = config.WHATSAPP_PHONE_NUMBER_ID
    app_id = config.META_APP_ID
    if not token or not phone_id:
        raise HTTPException(status_code=400, detail="WhatsApp API credentials not configured.")

    try:
        file_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"
        file_length = len(file_bytes)

        # 1. Create upload session on App
        create_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{app_id}/uploads"
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "file_length": file_length,
            "file_type": mime_type
        }
        create_resp = httpx.post(create_url, headers=headers, params=params, timeout=config.HTTP_TIMEOUT_SECONDS)
        if create_resp.status_code not in [200, 201]:
            raise HTTPException(status_code=400, detail=f"Failed to start upload session with Meta: {create_resp.text}")
        
        upload_id = create_resp.json().get("id")

        # 2. Upload file bytes to session
        bin_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{upload_id}"
        bin_headers = {
            "Authorization": f"OAuth {token}",
            "file_offset": "0",
            "Content-Type": "application/octet-stream"
        }
        bin_resp = httpx.post(bin_url, headers=bin_headers, content=file_bytes, timeout=config.HTTP_TIMEOUT_SECONDS)
        if bin_resp.status_code not in [200, 201]:
            raise HTTPException(status_code=400, detail=f"Failed to upload photo bytes to Meta: {bin_resp.text}")

        photo_handle = bin_resp.json().get("h")
        if not photo_handle:
            raise HTTPException(status_code=400, detail="Meta did not return a valid photo handle.")

        # 3. Attach handle to WhatsApp Business Profile
        update_url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{phone_id}/whatsapp_business_profile"
        attach_resp = httpx.post(
            update_url,
            headers={"Authorization": f"Bearer {token}"},
            json={"messaging_product": "whatsapp", "profile_picture_handle": photo_handle},
            timeout=config.HTTP_TIMEOUT_SECONDS
        )
        if attach_resp.status_code in [200, 201]:
            return {"status": "success", "message": "Profile picture successfully updated on WhatsApp."}
        else:
            raise HTTPException(status_code=attach_resp.status_code, detail=f"Meta photo attach error: {attach_resp.text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading profile photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/settings")
def get_system_settings(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "quiet_hours_enabled").first()
    quiet_hours_val = False
    if setting is not None:
        quiet_hours_val = str(setting.value).strip().lower() in ["true", "1", "yes", "on"]

    return {
        "daily_limit": 2000,
        "cart_delay_minutes": 0,
        "active_phone_id": config.WHATSAPP_PHONE_NUMBER_ID or "Not Configured (Simulation Mode)",
        "webhook_endpoint": config.WHATSAPP_WEBHOOK_URL or "/api/webhooks/whatsapp",
        "dnd_keywords": list(OPT_OUT_KEYWORDS),
        "quiet_hours_enabled": quiet_hours_val
    }


@router.put("/api/settings/quiet-hours")
def update_quiet_hours_setting(
    payload: dict,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    enabled = bool(payload.get("enabled", False))
    setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "quiet_hours_enabled").first()
    if not setting:
        setting = models.SystemSetting(key="quiet_hours_enabled", value=str(enabled).lower())
        db.add(setting)
    else:
        setting.value = str(enabled).lower()
        setting.updated_at = datetime.utcnow()
    db.commit()

    logger.info(f"User {current_user.username} toggled quiet_hours_enabled to {enabled}")
    return {"status": "success", "quiet_hours_enabled": enabled}


@router.put("/api/settings/daily-limit")
def update_daily_limit_setting(
    payload: schemas.DailyLimitUpdateRequest,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Daily outbound message limit is fixed to 2000 messages per day and cannot be edited."
    )

