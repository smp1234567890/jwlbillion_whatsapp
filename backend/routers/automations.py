"""
Automation Rules Router
Handles automation rules CRUD, manual trigger, 2FA high-volume dispatch approval,
and clean-slate database purging.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db

logger = logging.getLogger("automations_router")

router = APIRouter(tags=["automations"])


@router.post("/api/automations/clean-slate")
def purge_all_sample_automations(
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Admin endpoint to purge all sample workflows, sessions, and rules for a 100% fresh clean slate."""
    db.query(models.WorkflowSession).delete()
    db.query(models.WorkflowFlow).delete()
    db.query(models.AutomationRule).delete()
    db.commit()
    return {"status": "ok", "message": "All automations and sample data purged successfully. Clean slate active."}


@router.get("/api/automation-rules")
def list_automation_rules(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all automation rules. Falls back gracefully if newer columns are missing from DB.
    """
    try:
        rules = db.query(models.AutomationRule).order_by(models.AutomationRule.id.asc()).all()
        return rules
    except Exception:
        db.rollback()
        try:
            sql = text("""
                SELECT
                    id, rule_name, rule_type, trigger_condition,
                    COALESCE(threshold_value, 30)         AS threshold_value,
                    template_name, coupon_code,
                    COALESCE(dedup_days, 7)               AS dedup_days,
                    COALESCE(is_active, true)             AS is_active,
                    COALESCE(total_triggered, 0)          AS total_triggered,
                    COALESCE(approval_status, 'IDLE')     AS approval_status,
                    COALESCE(pending_recipients_count, 0) AS pending_recipients_count,
                    created_at
                FROM automation_rules
                ORDER BY id ASC
            """)
            rows = db.execute(sql).mappings().all()
            return [dict(r) for r in rows]
        except Exception:
            db.rollback()
            sql2 = text("""
                SELECT id, rule_name, rule_type, trigger_condition,
                    COALESCE(threshold_value, 30) AS threshold_value,
                    template_name, coupon_code,
                    COALESCE(dedup_days, 7) AS dedup_days,
                    COALESCE(is_active, true) AS is_active
                FROM automation_rules ORDER BY id ASC
            """)
            rows2 = db.execute(sql2).mappings().all()
            return [
                {**dict(r), "total_triggered": 0, "approval_status": "IDLE",
                 "pending_recipients_count": 0, "created_at": None}
                for r in rows2
            ]


@router.post("/api/automation-rules", status_code=status.HTTP_201_CREATED)
def create_automation_rule(
    payload: schemas.AutomationRuleCreate,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    rule = models.AutomationRule(
        rule_name=payload.rule_name,
        rule_type=payload.rule_type,
        trigger_condition=payload.trigger_condition,
        threshold_value=payload.threshold_value,
        template_name=payload.template_name,
        coupon_code=payload.coupon_code,
        dedup_days=payload.dedup_days,
        variable_mappings=payload.variable_mappings,
        expires_at=payload.expires_at,
        is_active=payload.is_active
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/api/automation-rules/{rule_id}")
def update_automation_rule(
    rule_id: int,
    payload: schemas.AutomationRuleUpdate,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    rule = db.query(models.AutomationRule).filter(models.AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if payload.rule_name is not None:
        rule.rule_name = payload.rule_name
    if payload.trigger_condition is not None:
        rule.trigger_condition = payload.trigger_condition
    if payload.template_name is not None:
        rule.template_name = payload.template_name
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.threshold_value is not None:
        rule.threshold_value = payload.threshold_value
    if payload.coupon_code is not None:
        rule.coupon_code = payload.coupon_code
    if payload.dedup_days is not None:
        rule.dedup_days = payload.dedup_days
    if payload.variable_mappings is not None:
        rule.variable_mappings = payload.variable_mappings
    if payload.expires_at is not None:
        rule.expires_at = payload.expires_at

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/api/automation-rules/{rule_id}")
def delete_automation_rule(
    rule_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    rule = db.query(models.AutomationRule).filter(models.AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(rule)
    db.commit()
    return {"status": "success", "message": f"Rule '{rule.rule_name}' deleted."}


@router.post("/api/automation-rules/{rule_id}/trigger")
def trigger_specific_automation_rule(
    rule_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    rule = db.query(models.AutomationRule).filter(models.AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    from scheduler import run_rule_execution
    res = run_rule_execution(rule.id, force_approved=False)
    return res


@router.post("/api/automation-rules/{rule_id}/approve")
def approve_and_dispatch_automation_rule(
    rule_id: int,
    payload: schemas.RuleApproveRequest,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    🔐 Step-Up 2FA Authorization to release a high-volume automation (> 100 recipients).
    Requires valid password and 2FA code.
    """
    rule = db.query(models.AutomationRule).filter(models.AutomationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    auth.verify_user_stepup_auth(
        user=current_user,
        password=payload.password,
        two_factor_code=payload.two_factor_code,
        db=db
    )

    from scheduler import run_rule_execution
    res = run_rule_execution(rule.id, force_approved=True)
    return {
        "status": "success",
        "message": f"Automation '{rule.rule_name}' approved with 2FA and dispatched to {res.get('messages_dispatched', 0)} recipients!",
        "messages_dispatched": res.get("messages_dispatched", 0),
        "rule": rule.rule_name
    }
