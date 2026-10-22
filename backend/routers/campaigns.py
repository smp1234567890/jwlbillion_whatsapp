"""
Campaigns Router
Handles campaign listing, detail retrieval, creation/scheduling, and cancellation.
"""

from datetime import datetime
import logging
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, status
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

import auth
import config
import models
import schemas
from database import get_db
from rate_limiter import limiter
from scheduler import scheduler, execute_campaign_broadcast
from services import pii_service

logger = logging.getLogger("campaigns_router")

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=schemas.CampaignResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_and_trigger_campaign(
    request: Request,
    payload: schemas.CampaignCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    # 🔐 CRITICAL SECURITY GUARD: Verify Password + 2FA before mass broadcasting
    try:
        auth.verify_user_stepup_auth(
            user=current_user,
            password=payload.password,
            two_factor_code=payload.two_factor_code,
            db=db
        )
    except HTTPException:
        raise
    except Exception as auth_err:
        logger.error(f"Step-up authentication failed: {auth_err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security verification failed: {str(auth_err)}"
        )

    try:
        from services.campaign_service import create_and_schedule_campaign
        return create_and_schedule_campaign(payload=payload, background_tasks=background_tasks, db=db)
    except Exception as e:
        logger.error(f"Failed to create and launch campaign: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Campaign creation failed: {str(e)}"
        )


@router.get("", response_model=List[schemas.CampaignResponse])
def list_campaigns(
    skip: int = 0,
    limit: int = 50,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    try:
        return db.query(models.Campaign).order_by(models.Campaign.created_at.desc()).offset(skip).limit(limit).all()
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}", exc_info=True)
        return []


@router.get("/{campaign_id}", response_model=schemas.CampaignResponse)
def get_campaign(
    campaign_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    try:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching campaign")


@router.delete("/{campaign_id}")
def cancel_campaign(
    campaign_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    try:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        job_id = f"campaign_{campaign.id}"
        try:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                logger.info(f"Removed scheduled job {job_id}")
        except Exception as sj_err:
            logger.warning(f"Note on removing scheduler job {job_id}: {sj_err}")

        campaign.status = "CANCELLED"
        db.commit()
        return {"message": f"Campaign #{campaign_id} cancelled", "id": campaign_id, "status": "CANCELLED"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling campaign {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel campaign")


@router.get("/{campaign_id}/logs")
def get_campaign_logs(
    campaign_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Returns the granular recipient-by-recipient logs and analytics for a specific campaign.
    Features smart backward-compatibility correlation for campaigns created prior to campaign_id logging.
    """
    try:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        # 1. Query logs directly linked by campaign_id
        logs = db.query(models.MessageLog).filter(models.MessageLog.campaign_id == campaign_id).order_by(models.MessageLog.created_at.asc()).all()

        # 2. Smart fallback for campaigns run before campaign_id column addition
        if not logs:
            from datetime import timedelta
            # If scheduled_for or created_at exists, search across a generous +/- 12 hour window
            # to prevent UTC vs IST timezone offset mismatch (5h 30m difference)
            ref_time = campaign.scheduled_for or campaign.created_at
            if ref_time:
                window_start = ref_time - timedelta(hours=12)
                window_end = ref_time + timedelta(hours=12)
                logs = db.query(models.MessageLog).filter(
                    models.MessageLog.template_name == campaign.template_name,
                    models.MessageLog.created_at >= window_start,
                    models.MessageLog.created_at <= window_end
                ).order_by(models.MessageLog.created_at.asc()).all()

            # 3. If still empty, match by template_name ordered closest to the campaign execution
            if not logs:
                logs = db.query(models.MessageLog).filter(
                    models.MessageLog.template_name == campaign.template_name
                ).order_by(models.MessageLog.created_at.desc()).limit(campaign.total_recipients or 50).all()
                logs.reverse()

        # Build contact phone lookup map to fetch recipient names & cities
        phone_list = list(set([l.recipient_phone for l in logs]))
        contacts = db.query(models.Contact).filter(models.Contact.phone.in_(phone_list)).all() if phone_list else []
        contact_map = {c.phone: c for c in contacts}

        # Calculate live delivery breakdown
        sent_count = 0
        delivered_count = 0
        read_count = 0
        failed_count = 0

        recipients_data = []
        for l in logs:
            c = contact_map.get(l.recipient_phone)
            st = (l.status or "UNKNOWN").upper()
            if st in ["SENT", "SENT_SIMULATED"]:
                sent_count += 1
            elif st == "DELIVERED":
                delivered_count += 1
            elif st == "READ":
                read_count += 1
            elif st in ["FAILED", "BLOCKED"]:
                failed_count += 1

            disp_phone = l.recipient_phone if current_user.role == "admin" else pii_service.mask_phone(l.recipient_phone)
            recipients_data.append({
                "id": l.id,
                "phone": disp_phone,
                "name": c.name if c and c.name else "Customer",
                "city": c.city if c and c.city else "-",
                "template_name": l.template_name,
                "status": l.status,
                "meta_message_id": l.meta_message_id,
                "error_message": l.error_message,
                "created_at": l.created_at.isoformat() if l.created_at else None
            })

        return {
            "campaign": {
                "id": campaign.id,
                "title": campaign.title,
                "template_name": campaign.template_name,
                "language": campaign.language,
                "target_filter": campaign.target_filter,
                "status": campaign.status,
                "scheduled_for": campaign.scheduled_for.isoformat() if campaign.scheduled_for else None,
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
                "error_message": campaign.error_message
            },
            "summary": {
                "total_recipients": len(recipients_data),
                "successful_sends": sent_count + delivered_count + read_count,
                "sent": sent_count,
                "delivered": delivered_count,
                "read": read_count,
                "failed": failed_count
            },
            "recipients": recipients_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching campaign logs for {campaign_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error fetching campaign logs")

