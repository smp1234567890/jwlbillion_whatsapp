"""
Analytics Service
Computes CRM funnel metrics, delivery, read, click, and conversion rates without
silently swallowing database errors.
"""

from datetime import datetime, timedelta
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

import config
import models
import whatsapp_service

logger = logging.getLogger("analytics_service")


def compute_analytics_overview(time_range: str, db: Session) -> Dict[str, Any]:
    """
    Calculates detailed metrics for WhatsApp CRM.
    Raises exceptions cleanly so callers can return appropriate HTTP responses.
    """
    now_utc = datetime.utcnow()
    start_date = None
    if time_range == "today":
        # IST is UTC+05:30. Compute midnight of today in IST, then convert back to UTC
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        start_of_day_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = start_of_day_ist - timedelta(hours=5, minutes=30)
    elif time_range == "7d":
        start_date = now_utc - timedelta(days=7)
    elif time_range == "30d":
        start_date = now_utc - timedelta(days=30)

    # 1. Outbound Message Funnel (MessageLog)
    msg_q = db.query(models.MessageLog)
    if start_date:
        msg_q = msg_q.filter(models.MessageLog.created_at >= start_date)
    logs = msg_q.all()

    # 2. Inbound Customer Replies & Clicks (ChatMessage)
    chat_q = db.query(models.ChatMessage)
    if start_date:
        chat_q = chat_q.filter(models.ChatMessage.created_at >= start_date)
    chats = chat_q.all()

    inbound_replies = [c for c in chats if c.sender_type == "CUSTOMER"]
    total_replied = len(inbound_replies)
    replied_phone_set = {c.customer_phone for c in inbound_replies}

    valid_sent_statuses = ("SENT", "DELIVERED", "READ", "SENT_SIMULATED")
    total_sent = sum(1 for m in logs if m.status in valid_sent_statuses)
    total_failed = sum(1 for m in logs if m.status == "FAILED")
    total_delivered = sum(
        1 for m in logs
        if m.status in ("DELIVERED", "READ", "SENT_SIMULATED") or (m.status == "SENT" and m.recipient_phone in replied_phone_set)
    )
    total_delivered = min(total_delivered, total_sent)

    # A message is read if Meta marked it READ, or if simulation/replied
    total_read = sum(
        1 for m in logs
        if m.status in ("READ", "SENT_SIMULATED") or (m.status in ("SENT", "DELIVERED") and m.recipient_phone in replied_phone_set)
    )
    total_read = min(total_read, total_delivered)

    # Interactive button clicks / CTA taps
    total_clicks = sum(
        1 for c in inbound_replies
        if c.message_type in ("button", "interactive")
        or (c.text and any(k in c.text.lower() for k in ["[button", "clicked", "yes", "order", "view"]))
    )

    # 3. Recovered Carts & Revenue (CartEvent)
    cart_q = db.query(models.CartEvent)
    if start_date:
        cart_q = cart_q.filter(models.CartEvent.created_at >= start_date)
    cart_events = cart_q.all()

    recovered_carts = [c for c in cart_events if c.status == "RECOVERED"]
    revenue_recovered = sum(float(c.cart_value or 0.0) for c in recovered_carts)

    # Rates
    delivery_rate = round((total_delivered / total_sent * 100), 1) if total_sent > 0 else 0.0
    read_rate = round((total_read / total_delivered * 100), 1) if total_delivered > 0 else 0.0
    click_rate = round((total_clicks / total_read * 100), 1) if total_read > 0 else 0.0
    reply_rate = round((total_replied / total_delivered * 100), 1) if total_delivered > 0 else 0.0

    # 4. Opt-Out / DND Metrics
    opt_q = db.query(models.OptOut)
    if start_date:
        opt_q = opt_q.filter(models.OptOut.created_at >= start_date)
    total_opt_outs = opt_q.count()
    opt_out_rate = round((total_opt_outs / max(1, total_sent) * 100), 2) if total_sent > 0 else 0.0

    # 5. Meta Account Health & Tier Limits
    quality_rating = "HIGH"
    if opt_out_rate > 3.0:
        quality_rating = "LOW"
    elif opt_out_rate > 1.0:
        quality_rating = "MEDIUM"

    effective_limit = whatsapp_service.get_effective_daily_limit(db)
    is_under_limit, today_sent = whatsapp_service.check_daily_limit(db)

    # 6. Template-Level Breakdown
    tmpl_map = {}
    for m in logs:
        tname = m.template_name or "custom_message"
        if tname not in tmpl_map:
            tmpl_map[tname] = {"sent": 0, "delivered": 0, "read": 0, "failed": 0}
        has_reply = m.recipient_phone in replied_phone_set
        if m.status == "FAILED":
            tmpl_map[tname]["failed"] += 1
            continue

        if m.status in valid_sent_statuses:
            tmpl_map[tname]["sent"] += 1
        if m.status in ("DELIVERED", "READ", "SENT_SIMULATED") or has_reply:
            tmpl_map[tname]["delivered"] += 1
        if m.status in ("READ", "SENT_SIMULATED") or has_reply:
            tmpl_map[tname]["read"] += 1

    template_performance = []
    for tname, tdata in tmpl_map.items():
        t_sent = tdata["sent"]
        t_del = min(tdata["delivered"], t_sent)
        t_read = min(tdata["read"], t_del)
        t_rate = round((t_read / t_del * 100), 1) if t_del > 0 else 0.0
        template_performance.append({
            "template_name": tname,
            "sent": t_sent,
            "delivered": t_del,
            "read": t_read,
            "read_rate": t_rate,
            "failed": tdata["failed"]
        })
    template_performance.sort(key=lambda x: x["sent"], reverse=True)

    # 7. Daily Trends
    trend_days = 7 if time_range in ("today", "7d") else 14
    daily_trends = []
    for i in range(trend_days - 1, -1, -1):
        day_date = (now_utc - timedelta(days=i)).date()
        day_str = day_date.strftime("%b %d")
        day_logs = [m for m in logs if m.created_at and getattr(m.created_at, "date", lambda: None)() == day_date]
        day_replies = [c for c in inbound_replies if c.created_at and getattr(c.created_at, "date", lambda: None)() == day_date]
        day_replied_phones = {c.customer_phone for c in day_replies}
        d_sent = sum(1 for m in day_logs if m.status in valid_sent_statuses)
        d_del = min(d_sent, sum(1 for m in day_logs if m.status in ("DELIVERED", "READ", "SENT_SIMULATED") or (m.status == "SENT" and m.recipient_phone in day_replied_phones)))
        d_read = min(d_del, sum(1 for m in day_logs if m.status in ("READ", "SENT_SIMULATED") or (m.status in ("SENT", "DELIVERED") and m.recipient_phone in day_replied_phones)))
        daily_trends.append({
            "date": day_str,
            "sent": d_sent,
            "delivered": d_del,
            "read": d_read,
            "replied": len(day_replies)
        })

    return {
        "time_range": time_range,
        "funnel": {
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_read": total_read,
            "total_replied": total_replied,
            "total_clicks": total_clicks,
            "total_failed": total_failed,
            "recovered_carts": len(recovered_carts),
            "revenue_recovered": round(revenue_recovered, 2)
        },
        "rates": {
            "delivery_rate": delivery_rate,
            "read_rate": read_rate,
            "click_rate": click_rate,
            "reply_rate": reply_rate,
            "opt_out_rate": opt_out_rate
        },
        "meta_health": {
            "quality_rating": quality_rating,
            "phone_status": "ONLINE",
            "daily_limit": effective_limit,
            "used_today": today_sent,
            "remaining_today": max(0, effective_limit - today_sent),
            "tier_name": "Tier 1 (1,000 / 24h)"
        },
        "template_performance": template_performance,
        "daily_trends": daily_trends
    }


def get_system_performance_noc(db: Session) -> Dict[str, Any]:
    """
    NOC (Network Operations Center) & System Performance Telemetry:
    - Server capacity & load (load averages, memory, disk usage)
    - Database connectivity & pool status
    - Background scheduler heartbeat
    - Campaign pipeline health (in-progress, scheduled, stuck/failed detection)
    - Workflow / Automation health (active sessions, delayed, overdue/stuck detection)
    """
    import os
    import shutil
    import resource
    from sqlalchemy import text
    from scheduler import scheduler

    now_utc = datetime.utcnow()

    # 1. Server Load & Resource Usage
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    cpu_cores = os.cpu_count() or 1
    # 1-min load percentage based on available CPU cores
    cpu_load_pct = min(100.0, round((load_avg[0] / cpu_cores) * 100, 1))

    # Disk usage for current directory
    du = shutil.disk_usage(".")
    disk_total_gb = round(du.total / (1024 ** 3), 2)
    disk_used_gb = round(du.used / (1024 ** 3), 2)
    disk_free_gb = round(du.free / (1024 ** 3), 2)
    disk_pct = round((du.used / du.total) * 100, 1)

    # Process Memory (ru_maxrss is KB on Linux, Bytes on macOS)
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    max_rss = rusage.ru_maxrss
    # On macOS, ru_maxrss is in bytes; on Linux, it is in kilobytes
    import sys
    if sys.platform == "darwin":
        memory_mb = round(max_rss / (1024 * 1024), 1)
    else:
        memory_mb = round(max_rss / 1024, 1)

    # 2. Database Health
    db_status = "HEALTHY"
    db_latency_ms = 0.0
    try:
        t0 = datetime.utcnow()
        db.execute(text("SELECT 1"))
        db_latency_ms = round((datetime.utcnow() - t0).total_seconds() * 1000, 2)
    except Exception as e:
        logger.error(f"[NOC] Database health probe failed: {e}")
        db_status = "DEGRADED"

    # 3. Background Scheduler & Worker Health
    scheduler_running = getattr(scheduler, "running", False)
    scheduler_jobs = []
    try:
        for job in scheduler.get_jobs():
            next_run = job.next_run_time.isoformat() if job.next_run_time else None
            scheduler_jobs.append({
                "id": job.id,
                "name": job.name or job.id,
                "next_run_time": next_run
            })
    except Exception:
        pass

    # 4. Campaign Pipeline & Stuck Detection
    # A campaign is considered "stuck" if:
    # - status == 'IN_PROGRESS' and claimed_until has expired or attempt_count > 3
    # - status == 'IN_PROGRESS' and created/updated > 2 hours ago with successful_sends < total_recipients
    stuck_campaigns = []
    active_campaigns = []
    recent_campaigns = db.query(models.Campaign).order_by(models.Campaign.created_at.desc()).limit(30).all()

    for c in recent_campaigns:
        is_stuck = False
        stuck_reason = ""

        if c.status == "IN_PROGRESS":
            # Check if lease expired or runs unusually long
            if c.claimed_until and c.claimed_until < now_utc:
                is_stuck = True
                stuck_reason = f"Worker lease expired at {c.claimed_until.strftime('%H:%M:%S UTC')}"
            elif c.created_at and (now_utc - c.created_at).total_seconds() > 7200:
                is_stuck = True
                stuck_reason = "In-progress for > 2 hours without completion"
            active_campaigns.append(c)
        elif c.status == "FAILED":
            is_stuck = True
            stuck_reason = c.error_message or "Execution failed"

        if is_stuck:
            stuck_campaigns.append({
                "id": c.id,
                "title": c.title,
                "template_name": c.template_name,
                "status": c.status,
                "progress": f"{c.successful_sends}/{c.total_recipients}",
                "stuck_reason": stuck_reason,
                "attempt_count": getattr(c, "attempt_count", 0),
                "created_at": c.created_at.isoformat() if c.created_at else None
            })

    # 5. Workflow Automations & Stuck Sessions Detection
    # A session is overdue / stuck if status is ACTIVE / WAITING_DELAY and next_evaluation_at was > 15 mins ago
    overdue_cutoff = now_utc - timedelta(minutes=15)
    stuck_sessions_q = db.query(models.WorkflowSession).filter(
        models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"]),
        models.WorkflowSession.next_evaluation_at < overdue_cutoff
    ).limit(20).all()

    stuck_workflow_sessions = []
    for s in stuck_sessions_q:
        delay_mins = round((now_utc - s.next_evaluation_at).total_seconds() / 60, 1)
        stuck_workflow_sessions.append({
            "session_id": s.id,
            "flow_id": s.flow_id,
            "customer_phone": s.customer_phone,
            "status": s.status,
            "current_node_id": s.current_node_id,
            "overdue_by_mins": delay_mins,
            "attempt_count": getattr(s, "attempt_count", 0)
        })

    active_sessions_count = db.query(models.WorkflowSession).filter(
        models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"])
    ).count()

    # Overall system health flag
    overall_status = "HEALTHY"
    if db_status != "HEALTHY" or not scheduler_running:
        overall_status = "CRITICAL"
    elif len(stuck_campaigns) > 0 or len(stuck_workflow_sessions) > 0 or disk_pct > 90 or cpu_load_pct > 85:
        overall_status = "DEGRADED"

    return {
        "overall_status": overall_status,
        "server": {
            "cores": cpu_cores,
            "load_1m": round(load_avg[0], 2),
            "load_5m": round(load_avg[1], 2),
            "load_15m": round(load_avg[2], 2),
            "load_capacity_pct": cpu_load_pct,
            "memory_resident_mb": memory_mb,
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
            "disk_free_gb": disk_free_gb,
            "disk_used_pct": disk_pct,
        },
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms
        },
        "scheduler": {
            "status": "RUNNING" if scheduler_running else "STOPPED",
            "active_jobs_count": len(scheduler_jobs),
            "jobs": scheduler_jobs
        },
        "campaigns_pipeline": {
            "active_count": len(active_campaigns),
            "stuck_count": len(stuck_campaigns),
            "stuck_items": stuck_campaigns
        },
        "automations_pipeline": {
            "active_sessions_count": active_sessions_count,
            "stuck_sessions_count": len(stuck_workflow_sessions),
            "stuck_items": stuck_workflow_sessions
        },
        "timestamp": now_utc.isoformat()
    }

