"""
Marketing & Promotions Router
Handles discount codes, external e-commerce data sources, opt-out management,
direct test WhatsApp messages, and 30-day customer re-engagement sweep trigger.
"""

import ipaddress
import logging
import re
import socket
import time
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth
import config
import models
import schemas
from database import get_db
from rate_limiter import limiter
from scheduler import run_thirty_day_reengagement_sweep
from whatsapp_service import send_whatsapp_template
import uuid
from services.phone_service import normalize_phone, InvalidPhoneNumberError
from services.policy_service import record_consent, revoke_consent
from services.secret_store import store_secret, get_secret, delete_secret
from services.integration_gateway import (
    validate_ssrf_safe_url,
    dispatch_external_request,
    SSRFSecurityError,
    HostNotAllowedError,
    CredentialMismatchError,
    CredentialMode
)

logger = logging.getLogger("marketing_router")

router = APIRouter(tags=["marketing"])


# ==========================================
# 🏷️ DISCOUNT CODES
# ==========================================

@router.get("/api/discount-codes", response_model=List[schemas.DiscountCodeResponse])
def list_discount_codes(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(models.DiscountCode).order_by(models.DiscountCode.id.desc()).all()


@router.post("/api/discount-codes", response_model=schemas.DiscountCodeResponse, status_code=status.HTTP_201_CREATED)
def create_discount_code(
    payload: schemas.DiscountCodeCreate,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    clean_code = payload.code.strip().upper()
    existing = db.query(models.DiscountCode).filter(models.DiscountCode.code == clean_code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Discount code '{clean_code}' already exists.")

    disc = models.DiscountCode(
        code=clean_code,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_order_value=payload.min_order_value or 0.0,
        max_uses=payload.max_uses or 1000,
        expires_at=payload.expires_at,
        is_active=payload.is_active if payload.is_active is not None else True
    )
    db.add(disc)
    db.commit()
    db.refresh(disc)
    return disc


@router.delete("/api/discount-codes/{code_id}")
def delete_discount_code(
    code_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    disc = db.query(models.DiscountCode).filter(models.DiscountCode.id == code_id).first()
    if not disc:
        raise HTTPException(status_code=404, detail="Discount code not found")
    db.delete(disc)
    db.commit()
    return {"status": "success", "message": f"Discount code {disc.code} deleted."}


# ==========================================
# 🌐 EXTERNAL DATA SOURCES
# ==========================================

# ==========================================
# 🌐 SECURE INTEGRATION GATEWAY & DATA SOURCES
# ==========================================

@router.get("/api/external-data-sources", response_model=List[schemas.ExternalDataSourceResponse])
def list_external_data_sources(
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Lists all configured external e-commerce REST API data sources (admin only, secrets hidden)."""
    try:
        return db.query(models.ExternalDataSource).order_by(models.ExternalDataSource.id.asc()).all()
    except Exception as e:
        logger.warning(f"Note: external_data_sources query fallback: {e}")
        return []


@router.post("/api/external-data-sources", response_model=schemas.ExternalDataSourceResponse, status_code=status.HTTP_201_CREATED)
def create_external_data_source(
    payload: schemas.ExternalDataSourceCreate,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Registers a new external API endpoint with mandatory HTTPS, SSRF check, host allowlisting, and step-up auth."""
    clean_url = payload.endpoint_url.strip()
    try:
        validate_ssrf_safe_url(clean_url)
    except (SSRFSecurityError, HostNotAllowedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    auth.verify_user_stepup_auth(current_user, payload.password, payload.two_factor_code, db)

    parsed_host = (urlparse(clean_url).hostname or "").strip().lower()
    approved_host = (payload.approved_hostname or parsed_host).strip().lower()

    secret_ref = None
    if payload.api_key and payload.api_key.strip():
        secret_ref = f"sec_ref_{uuid.uuid4().hex[:12]}"
        store_secret(db, secret_ref, payload.api_key.strip(), purpose=payload.purpose or "customer_lookup")

    src = models.ExternalDataSource(
        name=payload.name.strip(),
        endpoint_url=clean_url,
        auth_method=payload.auth_method or "bearer",
        secret_reference=secret_ref,
        approved_hostname=approved_host,
        purpose=payload.purpose or "customer_lookup",
        lookup_param=payload.lookup_param.strip() if payload.lookup_param else "phone",
        is_active=payload.is_active if payload.is_active is not None else True
    )
    db.add(src)
    db.flush()

    # Audit log
    db.add(models.AuditEvent(
        actor_user_id=current_user.id,
        action="CREATE_EXTERNAL_DATA_SOURCE",
        target_type="external_data_source",
        target_id=str(src.id),
        correlation_id=f"audit-{uuid.uuid4().hex[:8]}",
        metadata_json={"name": src.name, "approved_hostname": src.approved_hostname, "auth_method": src.auth_method}
    ))
    db.commit()
    db.refresh(src)
    return src


@router.patch("/api/external-data-sources/{source_id}", response_model=schemas.ExternalDataSourceResponse)
def update_external_data_source(
    source_id: int,
    payload: schemas.ExternalDataSourceUpdate,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Updates an external API endpoint with step-up verification and audit logging."""
    auth.verify_user_stepup_auth(current_user, payload.password, payload.two_factor_code, db)

    src = db.query(models.ExternalDataSource).filter(models.ExternalDataSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Data source not found")

    if payload.endpoint_url is not None:
        clean_url = payload.endpoint_url.strip()
        try:
            validate_ssrf_safe_url(clean_url)
        except (SSRFSecurityError, HostNotAllowedError) as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        src.endpoint_url = clean_url
        if not payload.approved_hostname:
            src.approved_hostname = (urlparse(clean_url).hostname or "").strip().lower()

    if payload.name is not None:
        src.name = payload.name.strip()
    if payload.auth_method is not None:
        src.auth_method = payload.auth_method
    if payload.approved_hostname is not None:
        src.approved_hostname = payload.approved_hostname.strip().lower()
    if payload.purpose is not None:
        src.purpose = payload.purpose.strip()
    if payload.lookup_param is not None:
        src.lookup_param = payload.lookup_param.strip()
    if payload.is_active is not None:
        src.is_active = payload.is_active

    if payload.api_key is not None and payload.api_key.strip():
        if src.secret_reference:
            store_secret(db, src.secret_reference, payload.api_key.strip(), purpose=src.purpose or "customer_lookup")
        else:
            sec_ref = f"sec_ref_{uuid.uuid4().hex[:12]}"
            store_secret(db, sec_ref, payload.api_key.strip(), purpose=src.purpose or "customer_lookup")
            src.secret_reference = sec_ref

    db.add(models.AuditEvent(
        actor_user_id=current_user.id,
        action="UPDATE_EXTERNAL_DATA_SOURCE",
        target_type="external_data_source",
        target_id=str(src.id),
        correlation_id=f"audit-{uuid.uuid4().hex[:8]}",
        metadata_json={"name": src.name, "approved_hostname": src.approved_hostname}
    ))
    db.commit()
    db.refresh(src)
    return src


@router.delete("/api/external-data-sources/{source_id}")
def delete_external_data_source(
    source_id: int,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Deletes an external data source, cleans up its encrypted secret, and logs audit record."""
    src = db.query(models.ExternalDataSource).filter(models.ExternalDataSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Data source not found")

    if src.secret_reference:
        delete_secret(db, src.secret_reference)

    source_name = src.name
    db.delete(src)

    db.add(models.AuditEvent(
        actor_user_id=current_user.id,
        action="DELETE_EXTERNAL_DATA_SOURCE",
        target_type="external_data_source",
        target_id=str(source_id),
        correlation_id=f"audit-{uuid.uuid4().hex[:8]}",
        metadata_json={"name": source_name}
    ))
    db.commit()
    return {"status": "success", "message": f"External data source '{source_name}' removed."}


@router.post("/api/external-data-sources/{source_id}/test", response_model=schemas.ExternalDataSourceTestResponse)
def test_external_data_source(
    source_id: int,
    payload: schemas.ExternalDataSourceTestRequest = schemas.ExternalDataSourceTestRequest(),
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Tests external API connectivity through the secure integration gateway. Upstream payload is sanitized."""
    auth.verify_user_stepup_auth(current_user, payload.password, payload.two_factor_code, db)

    src = db.query(models.ExternalDataSource).filter(models.ExternalDataSource.id == source_id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Data source not found")

    secret_val = get_secret(db, src.secret_reference) if src.secret_reference else None
    corr_id = f"test-{uuid.uuid4().hex[:8]}"

    try:
        gw_res = dispatch_external_request(
            endpoint_url=src.endpoint_url,
            approved_hostname=src.approved_hostname,
            credential_mode=src.auth_method or "bearer",
            secret_value=secret_val,
            params={src.lookup_param or "phone": payload.test_phone or "+919876543210"},
            correlation_id=corr_id
        )
    except (SSRFSecurityError, HostNotAllowedError, CredentialMismatchError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    # Audit log test attempt
    db.add(models.AuditEvent(
        actor_user_id=current_user.id,
        action="TEST_EXTERNAL_DATA_SOURCE",
        target_type="external_data_source",
        target_id=str(src.id),
        correlation_id=corr_id,
        metadata_json={"status_code": gw_res["status_code"], "is_success": gw_res["is_success"]}
    ))
    db.commit()

    # Strictly sanitized response: never leaks upstream body, headers, or exceptions
    return schemas.ExternalDataSourceTestResponse(
        status_code=gw_res["status_code"],
        is_success=gw_res["is_success"],
        latency_ms=gw_res["latency_ms"],
        correlation_id=corr_id,
        message=gw_res["message"]
    )



# ==========================================
# 🛑 OPT-OUT / DND MANAGEMENT
# ==========================================

@router.post("/api/opt-out")
@limiter.limit("30/minute")
def register_opt_out(
    request: Request,
    payload: schemas.OptOutRequest,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    revoke_consent(db, payload.phone, reason=payload.reason or "ADMIN_REVOKED")
    db.commit()
    return {"status": "success", "message": f"{payload.phone} added to DND list."}


@router.get("/api/opt-outs")
def list_opt_outs(
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(models.OptOut).order_by(models.OptOut.created_at.desc()).limit(limit).all()


@router.delete("/api/opt-outs/{phone}")
def remove_opt_out(
    phone: str,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    try:
        clean_phone = normalize_phone(phone)
    except InvalidPhoneNumberError:
        clean_phone = phone.strip()

    record = db.query(models.OptOut).filter(models.OptOut.phone == clean_phone).first()
    if not record:
        raise HTTPException(status_code=404, detail="Opt-out record not found")
    db.delete(record)
    db.commit()
    return {"status": "success", "message": f"{clean_phone} removed from DND list. Note: affirmative marketing consent must be separately collected."}


# ==========================================
# 🛒 CART EVENTS & MESSAGE LOGS
# ==========================================

@router.get("/api/cart-events")
def list_cart_events(
    limit: int = 50,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    effective_limit = min(max(1, limit), 100)
    return db.query(models.CartEvent).order_by(models.CartEvent.created_at.desc()).limit(effective_limit).all()


@router.get("/api/message-logs")
def get_message_logs(
    limit: int = 50,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """Returns the WhatsApp message audit trail ordered by most recent (max 100)."""
    effective_limit = min(max(1, limit), 100)
    logs = db.query(models.MessageLog).order_by(models.MessageLog.created_at.desc()).limit(effective_limit).all()
    return logs


@router.delete("/api/message-logs")
def delete_message_logs(
    older_than_days: Optional[int] = None,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Deletes WhatsApp audit logs:
    - If older_than_days is provided (e.g. 90, 120, 175): deletes logs older than that threshold.
    - If older_than_days is None: deletes all message logs.
    """
    from datetime import datetime, timedelta
    query = db.query(models.MessageLog)
    if older_than_days is not None and older_than_days > 0:
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        deleted_count = query.filter(models.MessageLog.created_at < cutoff_date).delete(synchronize_session=False)
        message = f"Successfully purged {deleted_count} logs older than {older_than_days} days."
    else:
        deleted_count = query.delete(synchronize_session=False)
        message = f"Successfully cleared all {deleted_count} message logs."

    db.commit()
    remaining_count = db.query(models.MessageLog).count()
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "remaining_count": remaining_count,
        "message": message
    }


@router.get("/api/message-logs/download")
def download_message_logs(
    password: str = Query(..., description="Admin account password for step-up verification"),
    reason: str = Query(..., min_length=5, description="Business justification for exporting message logs"),
    two_factor_code: Optional[str] = Query(None, description="2FA OTP code if enabled"),
    format: str = Query("csv"),
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """
    🔐 Step-Up Auth Protected Message Log Export:
    Strictly restricted to admin. Requires password, 2FA code, and valid business justification.
    Records an immutable AuditEvent.
    """
    auth.verify_user_stepup_auth(current_user, password, two_factor_code, db)

    import csv
    import io
    from fastapi.responses import Response, JSONResponse

    logs = db.query(models.MessageLog).order_by(models.MessageLog.created_at.desc()).limit(1000).all()

    audit = models.AuditEvent(
        actor_user_id=current_user.id,
        action="export_message_logs",
        target_type="message_logs",
        metadata_json={
            "reason": reason,
            "format": format,
            "record_count": len(logs)
        }
    )
    db.add(audit)
    db.commit()

    if format.lower() == "json":
        data = [
            {
                "id": l.id,
                "sender_user": l.sender_user or "System",
                "recipient_phone": l.recipient_phone,
                "template_name": l.template_name,
                "campaign_id": l.campaign_id,
                "status": l.status,
                "meta_message_id": l.meta_message_id,
                "error_message": l.error_message,
                "created_at": l.created_at.isoformat() if l.created_at else None
            }
            for l in logs
        ]
        return JSONResponse(
            content=data,
            headers={
                "Content-Disposition": f"attachment; filename=whatsapp_logs_{datetime.utcnow().strftime('%Y%m%d')}.json"
            }
        )

    # CSV format
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Log ID", "Initiated By / User", "Recipient Phone",
        "Template", "Status", "Meta Message ID", "Error Details", "Timestamp (UTC)"
    ])
    for l in logs:
        writer.writerow([
            l.id,
            l.sender_user or "System",
            l.recipient_phone,
            l.template_name,
            l.status,
            l.meta_message_id or "-",
            l.error_message or "",
            l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else ""
        ])

    csv_content = output.getvalue()
    filename = f"whatsapp_logs_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ==========================================
# 🎯 RE-ENGAGEMENT SWEEPS & TEST MESSAGES
# ==========================================

@router.get("/api/mock-store-feed/inactive-customers")
def mock_store_inactive_feed(
    days: int = 30,
    current_user: models.User = Depends(auth.require_roles("admin"))
):
    if config.ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mock endpoints are disabled in production environments."
        )
    return {
        "status": "success",
        "days_threshold": days,
        "customers": [
            {
                "phone": "+919000000001",
                "name": "Dev Test Patron 1",
                "email": "test1@example.invalid",
                "total_orders": 4
            },
            {
                "phone": "+919000000002",
                "name": "Dev Test Patron 2",
                "email": "test2@example.invalid",
                "total_orders": 2
            }
        ]
    }



@router.post("/api/triggers/reengagement-sweep")
def trigger_manual_reengagement_sweep(
    current_user: models.User = Depends(auth.get_current_user)
):
    run_thirty_day_reengagement_sweep()
    return {
        "status": "completed",
        "message": "30-day inactive customer sweep executed successfully"
    }


class DirectTestMessageRequest(BaseModel):
    phone: str
    template_name: str = "abandoned_cart_recovery"
    language: str = "en"
    parameters: Optional[dict] = None


@router.post("/api/messages/send-test")
def send_direct_test_message(
    payload: DirectTestMessageRequest,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    try:
        clean_phone = normalize_phone(payload.phone)
    except InvalidPhoneNumberError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tmpl = db.query(models.Template).filter(models.Template.template_name == payload.template_name).first()
    lang = payload.language
    if tmpl and tmpl.language:
        lang = tmpl.language

    params = payload.parameters
    if not params:
        if tmpl and tmpl.body_text:
            matches = re.findall(r"\{\{(\d+)\}\}", tmpl.body_text)
            if matches:
                sample_vals = [
                    current_user.username or "Customer",
                    config.BRAND_NAME,
                    "100",
                    config.DEFAULT_COUPON_CODE,
                    config.STORE_LOCATION or config.BRAND_NAME
                ]
                params = {f"param_{m}": sample_vals[int(m)-1] if int(m)-1 < len(sample_vals) else f"Val{m}" for m in matches}
        if not params:
            params = {}

    res = send_whatsapp_template(
        recipient_phone=clean_phone,
        template_name=payload.template_name,
        language=lang,
        parameters=params,
        sender_user=current_user.username
    )
    return res
