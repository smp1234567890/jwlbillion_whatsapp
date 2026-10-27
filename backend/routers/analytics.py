import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
import models
import auth
from services.analytics_service import compute_analytics_overview, get_system_performance_noc

logger = logging.getLogger("analytics_router")

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview")
def get_analytics_overview(
    time_range: str = Query("30d", enum=["today", "7d", "30d", "all"]),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Computes comprehensive WhatsApp CRM funnel metrics, delivery & read rates,
    click engagement, customer replies, recovered cart revenue, and template breakdown.
    Delegates to services.analytics_service.
    """
    try:
        return compute_analytics_overview(time_range=time_range, db=db)
    except Exception as e:
        logger.error(f"Error generating analytics overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analytics overview: {str(e)}"
        )


@router.get("/system-performance")
def get_system_performance(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns live NOC & platform performance metrics:
    - Server CPU load average, RAM usage, Disk capacity
    - Database latency and operational status
    - Scheduler status and active jobs
    - Stuck or stalled campaigns
    - Stuck or delayed workflow automation sessions
    """
    try:
        return get_system_performance_noc(db=db)
    except Exception as e:
        logger.error(f"Error checking platform performance: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch system performance: {str(e)}"
        )

