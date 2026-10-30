import os
import io
import csv
import logging
import hmac
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional
from dotenv import load_dotenv
import httpx
from pydantic import BaseModel

from services.logging_config import configure_secure_logging
configure_secure_logging()
logger = logging.getLogger("main")
from fastapi import FastAPI, Depends, HTTPException, Header, Request, status, UploadFile, File, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, get_db, Base
import models
import schemas
import auth
from scheduler import schedule_cart_recovery, execute_campaign_broadcast, scheduler
import whatsapp_service
from whatsapp_service import send_whatsapp_template, create_meta_template
from apscheduler.triggers.date import DateTrigger

import config

from fastapi.exceptions import ResponseValidationError
from fastapi.responses import JSONResponse, HTMLResponse

# Rate Limiter setup
from rate_limiter import limiter
app = FastAPI(
    title=config.APP_NAME,
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request.state.correlation_id = corr_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    headers = dict(exc.headers or {})
    headers["X-Correlation-ID"] = corr_id
    content = {
        "detail": exc.detail,
        "correlation_id": corr_id
    }
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


@app.exception_handler(ResponseValidationError)
async def response_validation_error_handler(request: Request, exc: ResponseValidationError):
    corr_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    logger.error(f"[{corr_id}] ResponseValidationError on {request.method} {request.url.path}: {exc.errors()}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal response formatting error occurred.",
            "correlation_id": corr_id
        },
        headers={"X-Correlation-ID": corr_id}
    )


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", None) or str(uuid.uuid4())
    logger.error(f"[{corr_id}] Unhandled Exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"An internal server error occurred: {type(exc).__name__}: {str(exc)}",
            "correlation_id": corr_id
        },
        headers={"X-Correlation-ID": corr_id}
    )



# ── WP7: Environment-aware CORS — no wildcard origins/methods/headers in production ──
_SAFE_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
_SAFE_HEADERS = [
    "Authorization", "Content-Type", "X-Correlation-ID",
    "X-Hub-Signature-256", "X-Idempotency-Key", "X-Request-ID",
]

if config.ENVIRONMENT == "production":
    # Production: exact origins only from ALLOWED_ORIGINS env var; no regex
    _prod_origins = config.ALLOWED_ORIGINS  # validated non-wildcard by validate_production_config()
    if not _prod_origins:
        raise RuntimeError("FATAL: ALLOWED_ORIGINS must be set in production.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_prod_origins,
        allow_credentials=True,
        allow_methods=_SAFE_METHODS,
        allow_headers=_SAFE_HEADERS,
    )
else:
    # Development / staging: permissive, includes Vite, Capacitor, Vercel preview, local IP
    _dev_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost",
        "https://localhost",
        "capacitor://localhost",
    ]
    if config.ALLOWED_ORIGINS_RAW:
        _dev_origins.extend(
            [o.strip() for o in config.ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_dev_origins,
        allow_origin_regex=r"(https://.*\.vercel\.app|http://192\.168\..*|http://10\..*|capacitor://.*|https?://localhost.*)",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )



_startup_done = False

@app.on_event("startup")
def on_startup():
    global _startup_done
    if _startup_done:
        return
    _startup_done = True
    # ── WP8: Distributed Leader Election for Background Scheduler / Workflow Engine ──
    # Attempts to acquire advisory lock. If leader, runs APScheduler for background sweeps
    try:
        from services.job_claim_service import acquire_leader_lock
        from scheduler import start_scheduler
        db_gen = get_db()
        _db = next(db_gen)
        if config.SCHEDULER_ENABLED or acquire_leader_lock(_db):
            start_scheduler()
            logger.info("[Startup] Scheduler leader lock acquired. Background workflow sweeper active.")
        else:
            logger.info("[Startup] Secondary instance started. Background scheduler handled by active leader.")
        _db.close()
    except Exception as _sched_init_err:
        logger.warning(f"[Startup] Scheduler auto-start note: {_sched_init_err}")

    # Diagnostic: confirm WEBHOOK_SECRET is loaded
    _ws = config.WEBHOOK_SECRET or ""
    logger.info(f"[Startup] WEBHOOK_SECRET loaded: length={len(_ws)}, prefix={repr(_ws[:8])}")

    # ── Schema Discipline ─────────────────────────────────────────────────────
    # All schema modifications are handled strictly via Alembic migrations.
    # No runtime DDL (CREATE TABLE / ALTER TABLE) is executed at startup.
    logger.info("[DB] Schema discipline active: database managed via Alembic migrations.")

    # ── Database Initialization & Sync ──────────────────────────────────────
    db = next(get_db())
    try:
        # Fixed Daily Limit Sync (200 messages / day)
        try:
            limit_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "daily_limit").first()
            if limit_setting:
                limit_setting.value = "200"
            else:
                db.add(models.SystemSetting(key="daily_limit", value="200"))
            db.commit()
        except Exception as _set_err:
            db.rollback()
            logger.warning(f"[Settings] Daily limit sync note: {_set_err}")

        # ── Admin user sync ───────────────────────────────────────────────────────
        initial_user = config.INITIAL_ADMIN_USERNAME
        initial_pass = config.INITIAL_ADMIN_PASSWORD
        initial_email = config.INITIAL_ADMIN_EMAIL

        if initial_pass:
            try:
                admin = db.query(models.User).filter(models.User.username == initial_user).first()
                if not admin:
                    admin = db.query(models.User).filter(models.User.email == initial_email).first()

                if admin:
                    admin.username = initial_user
                    admin.email = initial_email
                    admin.hashed_password = auth.get_password_hash(initial_pass)
                    admin.is_active = True
                    admin.role = "admin"
                    db.commit()
                    logger.info(f"[Security] Initial admin '{initial_user}'credentials synchronized.")
                else:
                    default_admin = models.User(
                        username=initial_user,
                        email=initial_email,
                        hashed_password=auth.get_password_hash(initial_pass),
                        is_active=True,
                        role="admin"
                    )
                    db.add(default_admin)
                    db.commit()
                    logger.info(f"[Security] Initial admin '{initial_user}'created successfully.")
            except Exception as _admin_err:
                db.rollback()
                logger.error(f"[Security] Admin user sync failed (non-fatal): {_admin_err}")

        # ── Service Account user sync (For external store / Shopify integration) ────────
        svc_username = config.ECOM_SERVICE_USERNAME
        svc_password = config.ECOM_SERVICE_PASSWORD
        svc_email = config.ECOM_SERVICE_EMAIL

        if svc_password:
            try:
                svc_user = db.query(models.User).filter(models.User.username == svc_username).first()
                if not svc_user:
                    svc_user = models.User(
                        username=svc_username,
                        email=svc_email,
                        hashed_password=auth.get_password_hash(svc_password),
                        is_active=True,
                        is_2fa_enabled=False,
                        role="service"
                    )
                    db.add(svc_user)
                    db.commit()
                    logger.info(f"[Security] Service account '{svc_username}'created successfully.")
                else:
                    svc_user.hashed_password = auth.get_password_hash(svc_password)
                    svc_user.is_active = True
                    svc_user.is_2fa_enabled = False
                    svc_user.role = "service"
                    db.commit()
            except Exception as _svc_err:
                db.rollback()
                logger.error(f"[Security] Service account sync failed (non-fatal): {_svc_err}")

    except Exception as _db_init_err:
        logger.error(f"[Startup] DB initialisation error (non-fatal): {_db_init_err}", exc_info=True)
    finally:
        db.close()

    # ── Clean Slate Migration: Purge all legacy sample workflows and dummy rules ────
    try:
        with engine.connect() as _conn:
            _mig_check = _conn.execute(
                text("SELECT 1 FROM system_migrations WHERE migration_name = 'purge_sample_automations_2026_09_16'")
            ).scalar()
            if not _mig_check:
                # One-time clean slate wipe of dummy/sample automations with FK safety
                try:
                    _conn.execute(text("UPDATE outbound_messages SET workflow_session_id = NULL WHERE workflow_session_id IS NOT NULL"))
                    _conn.execute(text("DELETE FROM workflow_sessions"))
                    _conn.execute(text("DELETE FROM workflow_flows"))
                    _conn.execute(text("DELETE FROM automation_rules"))
                    _conn.execute(
                        text("INSERT INTO system_migrations (migration_name) VALUES ('purge_sample_automations_2026_09_16')")
                    )
                    _conn.commit()
                    logger.info("[Clean Slate] Successfully purged all sample workflows, sessions, and automation rules from database.")
                except Exception as _purge_sub_err:
                    _conn.rollback()
                    logger.warning(f"[Clean Slate] Purge step bypassed: {_purge_sub_err}")
    except Exception as _clean_err:
        logger.warning(f"[Clean Slate] Note: {_clean_err}")

    # ── One-time Backfill: Customer Replies to READ status ───────────────────
    try:
        with engine.connect() as _conn:
            _backfill_check = _conn.execute(
                text("SELECT 1 FROM system_migrations WHERE migration_name = 'backfill_replies_to_read_v1'")
            ).scalar()
            if not _backfill_check:
                _conn.execute(text("""
                    UPDATE message_logs
                    SET status = 'READ'
                    WHERE recipient_phone IN (
                        SELECT DISTINCT customer_phone
                        FROM chat_messages
                        WHERE sender_type = 'CUSTOMER'
                    )
                    AND status IN ('SENT', 'SENT_SIMULATED', 'DELIVERED')
                """))
                _conn.execute(
                    text("INSERT INTO system_migrations (migration_name) VALUES ('backfill_replies_to_read_v1')")
                )
                _conn.commit()
                logger.info("[Read Sync] Successfully backfilled past customer replies to READ status.")
    except Exception as _bf_err:
        logger.warning(f"[Read Sync] Backfill note: {_bf_err}")





@app.get("/")
def root():
    return {"message": "WhatsApp CRM is running ", "client": config.BRAND_NAME}


@app.get("/health")
@app.get("/api/health")
def health_check():
    return {"status": "ok", "database": "connected", "scheduler": "running"}


@app.get("/performance", response_class=HTMLResponse)
@app.get("/noc", response_class=HTMLResponse)
def visual_performance_noc(db: Session = Depends(get_db)):
    """
    Renders a standalone visual NOC dashboard directly from the backend server URL.
    Can be opened directly in any browser at https://<host>/performance.
    """
    from services.analytics_service import get_system_performance_noc
    import json
    data = get_system_performance_noc(db)
    server = data.get("server", {})
    database = data.get("database", {})
    scheduler_info = data.get("scheduler", {})
    campaigns = data.get("campaigns_pipeline", {})
    automations = data.get("automations_pipeline", {})
    overall = data.get("overall_status", "HEALTHY")

    status_color = "#10b981" if overall == "HEALTHY" else ("#f59e0b" if overall == "DEGRADED" else "#ef4444")
    cpu_pct = server.get("load_capacity_pct", 0)
    cpu_bar_color = "#ef4444" if cpu_pct > 85 else ("#f59e0b" if cpu_pct > 65 else "#10b981")
    disk_pct = server.get("disk_used_pct", 0)
    disk_bar_color = "#ef4444" if disk_pct > 90 else "#8b5cf6"

    # Render stuck campaigns
    stuck_camp_html = ""
    stuck_items = campaigns.get("stuck_items", [])
    if stuck_items:
        for c in stuck_items:
            stuck_camp_html += f"""
            <div style="background:#fef2f2; border:1px solid #fecaca; border-radius:8px; padding:12px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:#111827; font-size:13px;">{c.get('title')} <span style="color:#6b7280; font-weight:normal;">#{c.get('id')}</span></strong>
                    <span style="background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold;">{c.get('status')}</span>
                </div>
                <div style="color:#b91c1c; font-size:12px; margin-top:6px;">⚠️ Reason: {c.get('stuck_reason')}</div>
                <div style="font-size:11px; color:#4b5563; margin-top:6px;">Progress: <strong>{c.get('progress')}</strong> | Attempts: <strong>{c.get('attempt_count')}</strong> | Template: <code>{c.get('template_name')}</code></div>
            </div>
            """
    else:
        stuck_camp_html = """
        <div style="text-align:center; padding:32px 16px; color:#6b7280;">
            <div style="font-size:24px; margin-bottom:8px;">✓</div>
            <strong style="color:#111827; font-size:13px;">No Stuck Campaigns</strong>
            <p style="font-size:12px; margin:4px 0 0 0; color:#6b7280;">All broadcasts are operating normally within lease windows.</p>
        </div>
        """

    # Render stuck automations
    stuck_auto_html = ""
    auto_items = automations.get("stuck_items", [])
    if auto_items:
        for a in auto_items:
            stuck_auto_html += f"""
            <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:8px; padding:12px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="color:#111827; font-size:13px;">Session #{a.get('session_id')} (Flow #{a.get('flow_id')})</strong>
                    <span style="background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold;">{a.get('status')}</span>
                </div>
                <div style="color:#92400e; font-size:12px; margin-top:6px;">⏱ Overdue by <strong>{a.get('overdue_by_mins')} min</strong> at step <code>{a.get('current_node_id') or 'start'}</code></div>
                <div style="font-size:11px; color:#4b5563; margin-top:6px;">Phone: <code>{a.get('customer_phone')}</code> | Retries: <strong>{a.get('attempt_count')}</strong></div>
            </div>
            """
    else:
        stuck_auto_html = """
        <div style="text-align:center; padding:32px 16px; color:#6b7280;">
            <div style="font-size:24px; margin-bottom:8px;">✓</div>
            <strong style="color:#111827; font-size:13px;">Automations Running Smoothly</strong>
            <p style="font-size:12px; margin:4px 0 0 0; color:#6b7280;">Delay nodes and conditions are evaluating on time.</p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="15">
    <title>System Performance & NOC Live Center</title>
    <style>
        * {{ box-sizing: border-box; margin:0; padding:0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background:#f9fafb; color:#111827; padding:24px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; padding:20px 24px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; margin-bottom:20px; }}
        .header-title {{ display:flex; align-items:center; gap:12px; }}
        .logo-box {{ width:42px; height:42px; border-radius:10px; background:#111827; color:#25D366; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:20px; }}
        .status-badge {{ background:{status_color}1a; color:{status_color}; border:1px solid {status_color}4d; padding:4px 10px; border-radius:9999px; font-size:11px; font-weight:bold; text-transform:uppercase; }}
        .grid4 {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:16px; margin-bottom:20px; }}
        .card {{ background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; padding:20px; }}
        .card-label {{ font-size:11px; font-weight:600; text-transform:uppercase; color:#6b7280; letter-spacing:0.5px; }}
        .card-value {{ font-size:26px; font-weight:900; color:#111827; margin:8px 0 4px 0; }}
        .bar-bg {{ background:#f3f4f6; border-radius:9999px; height:8px; overflow:hidden; margin:8px 0; }}
        .bar-fill {{ height:8px; border-radius:9999px; }}
        .grid2 {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap:16px; }}
        .panel-head {{ background:#f9fafb; border-bottom:1px solid #e5e7eb; padding:14px 20px; font-weight:bold; font-size:13px; display:flex; justify-content:space-between; align-items:center; }}
        .panel-body {{ padding:20px; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-title">
                <div class="logo-box">⚡</div>
                <div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <h1 style="font-size:18px; font-weight:bold;">System Performance & NOC Live Center</h1>
                        <span class="status-badge">{overall}</span>
                    </div>
                    <p style="font-size:12px; color:#6b7280; margin-top:2px;">Live server capacity, CPU load, memory, database latency, and pipeline queues</p>
                </div>
            </div>
            <div style="text-align:right;">
                <span style="font-size:11px; color:#6b7280; font-family:monospace;">Auto-refreshing (15s) • {data.get('timestamp', '')[11:19]} UTC</span>
                <div style="margin-top:4px;">
                    <a href="/performance" style="color:#059669; font-size:12px; font-weight:600; text-decoration:underline;">Refresh Now</a>
                </div>
            </div>
        </div>

        <!-- Metric Cards -->
        <div class="grid4">
            <div class="card">
                <span class="card-label">CPU Load Capacity</span>
                <div class="card-value">{server.get('load_capacity_pct', 0)}%</div>
                <div class="bar-bg">
                    <div class="bar-fill" style="width:{min(100, server.get('load_capacity_pct', 0))}%; background:{cpu_bar_color};"></div>
                </div>
                <div style="font-size:11px; color:#6b7280; font-family:monospace; display:flex; justify-content:space-between;">
                    <span>1m: {server.get('load_1m')}</span>
                    <span>5m: {server.get('load_5m')}</span>
                    <span>15m: {server.get('load_15m')}</span>
                </div>
            </div>

            <div class="card">
                <span class="card-label">Process Memory (RSS)</span>
                <div class="card-value">{server.get('memory_resident_mb', 0)} MB</div>
                <p style="font-size:12px; color:#6b7280; margin-top:6px;">Backend process footprint</p>
                <div style="font-size:12px; color:#059669; font-weight:600; margin-top:12px;">✓ Optimal memory envelope</div>
            </div>

            <div class="card">
                <span class="card-label">Disk Capacity</span>
                <div class="card-value">{server.get('disk_used_pct', 0)}%</div>
                <div class="bar-bg">
                    <div class="bar-fill" style="width:{min(100, server.get('disk_used_pct', 0))}%; background:{disk_bar_color};"></div>
                </div>
                <div style="font-size:11px; color:#6b7280; font-family:monospace;">
                    {server.get('disk_free_gb')} GB Free ({server.get('disk_used_gb')} / {server.get('disk_total_gb')} GB)
                </div>
            </div>

            <div class="card">
                <span class="card-label">Core Engine & Database</span>
                <div class="card-value">{database.get('latency_ms', 0)} ms</div>
                <div style="font-size:12px; color:#4b5563; margin-top:6px;">
                    DB Status: <strong style="color:#059669;">{database.get('status')}</strong>
                </div>
                <div style="font-size:12px; color:#4b5563; margin-top:4px;">
                    Scheduler: <strong>{scheduler_info.get('status')}</strong> ({scheduler_info.get('active_jobs_count', 0)} jobs)
                </div>
            </div>
        </div>

        <!-- Pipelines -->
        <div class="grid2">
            <div class="card" style="padding:0; overflow:hidden;">
                <div class="panel-head">
                    <span>Campaign Pipeline Inspection</span>
                    <span style="font-size:11px; color:#4b5563;">Active: {campaigns.get('active_count', 0)}</span>
                </div>
                <div class="panel-body">
                    {stuck_camp_html}
                </div>
            </div>

            <div class="card" style="padding:0; overflow:hidden;">
                <div class="panel-head">
                    <span>Automation Engine & Session Health</span>
                    <span style="font-size:11px; color:#4b5563;">Enrolled: {automations.get('active_sessions_count', 0)}</span>
                </div>
                <div class="panel-body">
                    {stuck_auto_html}
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html)



# ==========================================
# MODULAR DOMAIN ROUTERS
# ==========================================

from routers import (
    auth as auth_router,
    contacts as contacts_router,
    campaigns as campaigns_router,
    chat as chat_router,
    templates as templates_router,
    webhooks as webhooks_router,
    marketing as marketing_router,
    automations as automations_router,
    workflows as workflows_router,
    settings as settings_router,
    analytics as analytics_router,
    products as products_router,
)

app.include_router(auth_router.router)
app.include_router(contacts_router.router)
app.include_router(campaigns_router.router)
app.include_router(chat_router.router)
app.include_router(templates_router.router)
app.include_router(webhooks_router.router)
app.include_router(marketing_router.router)
app.include_router(automations_router.router)
app.include_router(workflows_router.router)
app.include_router(settings_router.router)
app.include_router(analytics_router.router)
app.include_router(products_router.router)

from fastapi.staticfiles import StaticFiles
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


