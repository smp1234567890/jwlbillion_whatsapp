"""
Campaign Service
Encapsulates business logic for campaign scheduling, IST timezone calculation,
and execution dispatch.
"""

from datetime import datetime
import logging
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo
from apscheduler.triggers.date import DateTrigger
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

import config
import models
import schemas
from scheduler import scheduler, execute_campaign_broadcast

logger = logging.getLogger("campaign_service")


def parse_scheduled_time(scheduled_for_raw: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parses a date string (ISO 8601 or naive) into an IST-aware datetime object
    and a naive UTC/database datetime representation.
    """
    if not scheduled_for_raw:
        return None, None

    try:
        tz_kolkata = ZoneInfo(config.TIMEZONE)
        raw = str(scheduled_for_raw).strip()
        if raw.endswith("Z"):
            dt_obj = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        elif "+" in raw or "-" in raw[10:]:
            dt_obj = datetime.fromisoformat(raw)
        else:
            clean_str = raw.replace("T", " ")
            naive_dt = datetime.fromisoformat(clean_str)
            dt_obj = naive_dt.replace(tzinfo=tz_kolkata)

        scheduled_dt_tz = dt_obj.astimezone(tz_kolkata)
        scheduled_dt = scheduled_dt_tz.replace(tzinfo=None)
        return scheduled_dt, scheduled_dt_tz
    except Exception as parse_err:
        logger.warning(f"Failed to parse scheduled_for '{scheduled_for_raw}': {parse_err}")
        return None, None


def create_and_schedule_campaign(
    payload: schemas.CampaignCreate,
    background_tasks: BackgroundTasks,
    db: Session
) -> models.Campaign:
    """
    Creates a campaign in the database and queues it for either immediate
    asynchronous background broadcast or schedules it via APScheduler.
    """
    scheduled_dt, scheduled_dt_tz = parse_scheduled_time(payload.scheduled_for)

    now_ist = datetime.now(ZoneInfo(config.TIMEZONE))
    is_future = scheduled_dt_tz and scheduled_dt_tz > now_ist

    campaign = models.Campaign(
        title=payload.title,
        template_name=payload.template_name,
        language=payload.language or "en",
        target_filter=payload.target_filter or "ALL",
        per_day_limit=payload.per_day_limit,
        status="SCHEDULED" if is_future else "IN_PROGRESS",
        scheduled_for=scheduled_dt
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    if is_future:
        job_id = f"campaign_{campaign.id}"
        scheduler.add_job(
            func=execute_campaign_broadcast,
            trigger=DateTrigger(run_date=scheduled_dt_tz, timezone=ZoneInfo(config.TIMEZONE)),
            args=[campaign.id, payload.custom_phones],
            id=job_id,
            replace_existing=True
        )
        logger.info(f"📅 Campaign {campaign.id} scheduled to execute at {scheduled_dt_tz} (IST)")
    else:
        logger.info(f"🚀 Queueing immediate broadcast for Campaign #{campaign.id} via BackgroundTasks")
        background_tasks.add_task(execute_campaign_broadcast, campaign.id, payload.custom_phones)

    return campaign


def cancel_scheduled_campaign(campaign_id: int, db: Session) -> bool:
    """
    Cancels a scheduled or draft campaign and unschedules any pending APScheduler job.
    """
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if not campaign:
        return False

    job_id = f"campaign_{campaign_id}"
    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled job '{job_id}' from scheduler")
    except Exception as job_err:
        logger.warning(f"Could not remove job {job_id}: {job_err}")

    campaign.status = "CANCELLED"
    db.commit()
    return True
