"""
Templates Router
Handles template listing, creation (Meta sync), live sync from Meta Graph API,
deletion, and variable mapping updates.
"""

from datetime import datetime
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import auth
import config
import models
import schemas
from database import get_db
from whatsapp_service import create_meta_template

logger = logging.getLogger("templates_router")

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.post("/sync-from-meta")
def sync_templates_from_meta(
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Connects to live Meta Graph API using your WABA_ID & ACCESS_TOKEN,
    fetches all approved message templates, and syncs them into your database.
    """
    waba_id = config.WHATSAPP_BUSINESS_ACCOUNT_ID
    access_token = config.WHATSAPP_API_TOKEN

    if not waba_id or not access_token:
        raise HTTPException(
            status_code=400,
            detail="Meta WABA ID or Access Token is missing from environment configuration"
        )

    try:
        url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{waba_id}/message_templates?limit=100"
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = httpx.get(url, headers=headers, timeout=config.HTTP_TIMEOUT_SECONDS)

        if resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Meta API error: {resp.text}"
            )

        data = resp.json().get("data", [])
        synced_count = 0

        for item in data:
            name = item.get("name")
            category = item.get("category", "MARKETING")
            language = item.get("language", "en")
            tmpl_status = item.get("status", "APPROVED")

            # Extract header, body, footer from components
            header_text = ""
            body_text = ""
            footer_text = ""
            for comp in item.get("components", []):
                ctype = comp.get("type")
                if ctype == "HEADER":
                    header_text = comp.get("text", "")
                elif ctype == "BODY":
                    body_text = comp.get("text", "")
                elif ctype == "FOOTER":
                    footer_text = comp.get("text", "")

            # Check existing
            existing = db.query(models.Template).filter(
                models.Template.template_name == name,
                models.Template.language == language
            ).first()

            if existing:
                existing.header_text = header_text
                existing.body_text = body_text
                existing.footer_text = footer_text
                existing.category = category
                existing.status = tmpl_status
            else:
                new_tmpl = models.Template(
                    template_name=name,
                    category=category,
                    language=language,
                    header_text=header_text,
                    body_text=body_text,
                    footer_text=footer_text,
                    status=tmpl_status
                )
                db.add(new_tmpl)
            synced_count += 1

        # Prune local templates that no longer exist in Meta's active catalog
        meta_keys = {(item.get("name"), item.get("language", "en")) for item in data}
        db_templates = db.query(models.Template).all()
        pruned_count = 0
        for dbt in db_templates:
            if (dbt.template_name, dbt.language) not in meta_keys:
                db.delete(dbt)
                pruned_count += 1

        # 📊 META TEMPLATE ANALYTICS / READ INSIGHTS SYNC
        meta_insights_synced = 0
        try:
            now_ts = int(datetime.utcnow().timestamp())
            start_ts = now_ts - (30 * 86400)
            analytics_url = (
                f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{waba_id}"
                f"?fields=template_analytics.start({start_ts}).end({now_ts}).granularity(DAILY)"
            )
            analytics_resp = httpx.get(analytics_url, headers=headers, timeout=config.HTTP_TIMEOUT_SECONDS)
            if analytics_resp.status_code == 200:
                analytics_data = analytics_resp.json().get("template_analytics", {}).get("data", [])
                for t_stat in analytics_data:
                    t_points = t_stat.get("data_points", [])
                    t_read_count = sum(p.get("read", 0) for p in t_points)
                    if t_read_count > 0:
                        meta_insights_synced += t_read_count
            else:
                logger.info(f"Meta template analytics query info: {analytics_resp.status_code} - {analytics_resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Optional Meta template_analytics fetch skipped: {e}")

        # 🚀 CUSTOMER REPLY TO READ BACKFILL
        replied_customers = [
            r[0] for r in db.query(models.ChatMessage.customer_phone)
            .filter(models.ChatMessage.sender_type == "CUSTOMER")
            .distinct().all()
        ]
        backfilled_reads = 0
        for phone in replied_customers:
            out_logs = db.query(models.MessageLog).filter(
                models.MessageLog.recipient_phone == phone,
                models.MessageLog.status.in_(["SENT", "SENT_SIMULATED", "DELIVERED"])
            ).all()
            for log in out_logs:
                log.status = "READ"
                backfilled_reads += 1

        db.commit()
        prune_msg = f" (pruned {pruned_count} deleted/unregistered templates)" if pruned_count > 0 else ""
        backfill_msg = f", synced {backfilled_reads} read events from customer replies" if backfilled_reads > 0 else ""
        return {
            "status": "success",
            "message": f"Successfully synced {synced_count} templates from Meta WhatsApp Business Manager{prune_msg}{backfill_msg}.",
            "synced_count": synced_count,
            "pruned_count": pruned_count,
            "backfilled_reads": backfilled_reads,
            "meta_insights_read_count": meta_insights_synced
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing templates from Meta: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_templates(
    language: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Template)
    if language and language != "ALL":
        query = query.filter(models.Template.language == language)
    return query.order_by(models.Template.template_name.asc()).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(
    payload: schemas.TemplateCreate,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Submits a new WhatsApp template to Meta Graph API and saves it in the database.
    """
    clean_name = payload.template_name.strip().lower().replace(" ", "_")
    meta_result = create_meta_template(
        template_name=clean_name,
        category=payload.category,
        language=payload.language,
        body_text=payload.body_text,
        header_text=payload.header_text,
        footer_text=payload.footer_text
    )

    if "error" in meta_result and meta_result.get("status") == "FAILED":
        raise HTTPException(status_code=400, detail=f"Meta submission error: {meta_result['error']}")

    existing = db.query(models.Template).filter(
        models.Template.template_name == clean_name,
        models.Template.language == payload.language
    ).first()

    status_val = meta_result.get("status", "APPROVED")
    if existing:
        existing.category = payload.category
        existing.body_text = payload.body_text
        existing.header_text = payload.header_text
        existing.footer_text = payload.footer_text
        existing.status = status_val
        if payload.variable_mappings is not None:
            existing.variable_mappings = payload.variable_mappings
        db.commit()
        db.refresh(existing)
        return existing

    new_tmpl = models.Template(
        template_name=clean_name,
        category=payload.category,
        language=payload.language,
        body_text=payload.body_text,
        header_text=payload.header_text,
        footer_text=payload.footer_text,
        status=status_val,
        variable_mappings=payload.variable_mappings or {}
    )
    db.add(new_tmpl)
    db.commit()
    db.refresh(new_tmpl)
    return new_tmpl


@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Deletes a WhatsApp template from the database, and attempts to delete it from Meta Graph API if registered.
    """
    tmpl = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    tmpl_name = tmpl.template_name
    waba_id = config.WHATSAPP_BUSINESS_ACCOUNT_ID
    access_token = config.WHATSAPP_API_TOKEN
    meta_deleted = False

    if waba_id and access_token:
        try:
            url = f"{config.META_GRAPH_BASE_URL}/{config.META_GRAPH_VERSION}/{waba_id}/message_templates?name={tmpl_name}"
            headers = {"Authorization": f"Bearer {access_token}"}
            del_resp = httpx.delete(url, headers=headers, timeout=config.HTTP_TIMEOUT_SECONDS)
            if del_resp.status_code == 200:
                meta_deleted = True
            else:
                logger.info(f"Meta template delete response: {del_resp.status_code} - {del_resp.text}")
        except Exception as e:
            logger.warning(f"Could not delete template on Meta API: {e}")

    db.delete(tmpl)
    db.commit()

    meta_note = " (also removed from Meta)" if meta_deleted else ""
    return {
        "status": "success",
        "message": f"Template '{tmpl_name}' was successfully deleted{meta_note}."
    }


@router.patch("/{template_id}/mappings")
def update_template_mappings(
    template_id: int,
    payload: schemas.TemplateUpdateMappings,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Update only the variable_mappings for an existing template.
    Allows reconfiguring which contact/cart/coupon field maps to each {{N}} placeholder.
    """
    tmpl = db.query(models.Template).filter(models.Template.id == template_id).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    tmpl.variable_mappings = payload.variable_mappings or {}
    db.commit()
    db.refresh(tmpl)
    return {"status": "updated", "id": tmpl.id, "variable_mappings": tmpl.variable_mappings}
