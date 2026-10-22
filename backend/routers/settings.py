import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
import auth
import config
from whatsapp_service import OPT_OUT_KEYWORDS

logger = logging.getLogger("settings_router")

router = APIRouter(tags=["Platform & Integration Settings"])


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
        "daily_limit": 200,
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
        detail="Daily outbound message limit is fixed to 200 messages per day and cannot be edited."
    )

