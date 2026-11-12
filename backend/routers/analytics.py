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


@router.get("/storage/files")
def get_storage_files(
    limit: int = Query(500, ge=1, le=1000),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Lists uploaded template and message media files from the uploads directory
    with metadata (size, dimensions, date, file type) for storage management.
    """
    import os
    import time
    from datetime import datetime

    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        return {"total_files": 0, "total_mb": 0.0, "files": []}

    files = []
    total_bytes = 0
    now_ts = time.time()

    try:
        entries = os.listdir(upload_dir)
    except Exception as e:
        logger.error(f"Failed to list upload dir: {e}")
        return {"total_files": 0, "total_mb": 0.0, "files": []}

    for fname in entries:
        if fname.startswith("."):
            continue
        fpath = os.path.join(upload_dir, fname)
        if not os.path.isfile(fpath):
            continue

        try:
            stat = os.stat(fpath)
            size = stat.st_size
            total_bytes += size
            mtime = stat.st_mtime
            ext = os.path.splitext(fname)[1].lower()
            is_image = ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]
            is_video = ext in [".mp4", ".3gp", ".mov", ".mkv", ".avi"]

            files.append({
                "name": fname,
                "url": f"/uploads/{fname}",
                "size_bytes": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "is_image": is_image,
                "is_video": is_video,
                "extension": ext.replace(".", "").upper(),
                "modified_at": datetime.fromtimestamp(mtime).isoformat(),
                "days_old": round((now_ts - mtime) / 86400, 1)
            })
        except Exception:
            continue

    # Sort newest first
    files.sort(key=lambda x: x["modified_at"], reverse=True)

    return {
        "total_files": len(files),
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "files": files[:limit]
    }


@router.delete("/storage/files/{filename}")
def delete_storage_file(
    filename: str,
    current_user: models.User = Depends(auth.require_roles("admin", "manager"))
):
    """Deletes a single uploaded media file permanently to reclaim server disk space."""
    import os
    safe_name = os.path.basename(filename)
    fpath = os.path.join("uploads", safe_name)
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        os.remove(fpath)
        return {"status": "success", "deleted": safe_name}
    except Exception as e:
        logger.error(f"Failed to delete {fpath}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


@router.post("/storage/files/bulk-delete")
def bulk_delete_storage_files(
    payload: dict,
    current_user: models.User = Depends(auth.require_roles("admin", "manager"))
):
    """
    Bulk deletes uploaded media files by list of filenames OR older_than_days.
    """
    import os
    import time

    upload_dir = "uploads"
    deleted_count = 0
    freed_bytes = 0

    filenames = payload.get("filenames", [])
    older_than_days = payload.get("older_than_days")

    if older_than_days is not None:
        cutoff = time.time() - (float(older_than_days) * 86400)
        try:
            for fname in os.listdir(upload_dir):
                if fname.startswith("."):
                    continue
                fpath = os.path.join(upload_dir, fname)
                if os.path.isfile(fpath) and os.stat(fpath).st_mtime < cutoff:
                    sz = os.stat(fpath).st_size
                    os.remove(fpath)
                    deleted_count += 1
                    freed_bytes += sz
        except Exception as e:
            logger.error(f"Error purging older files: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    elif filenames:
        for fname in filenames:
            safe_name = os.path.basename(fname)
            fpath = os.path.join(upload_dir, safe_name)
            if os.path.exists(fpath) and os.path.isfile(fpath):
                try:
                    sz = os.stat(fpath).st_size
                    os.remove(fpath)
                    deleted_count += 1
                    freed_bytes += sz
                except Exception:
                    pass

    return {
        "status": "success",
        "deleted_count": deleted_count,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2)
    }


