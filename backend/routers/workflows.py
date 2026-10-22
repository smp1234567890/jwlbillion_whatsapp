"""
Visual Workflows Router
Handles listing, creation, retrieval, updating, deleting, status toggling,
session tracking, and interactive simulation for visual flowchart journeys.
"""

from datetime import datetime
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

import auth
import models
import schemas
from database import get_db

logger = logging.getLogger("workflows_router")

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.get("", response_model=List[schemas.WorkflowFlowResponse])
def list_workflow_flows(
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """Lists all visual journey workflows with execution metrics."""
    return db.query(models.WorkflowFlow).order_by(models.WorkflowFlow.id.asc()).all()


@router.post("", response_model=schemas.WorkflowFlowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow_flow(
    payload: schemas.WorkflowFlowCreate,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """Creates a new multi-step visual journey workflow."""
    flow = models.WorkflowFlow(
        name=payload.name,
        description=payload.description,
        trigger_type=payload.trigger_type,
        trigger_config=payload.trigger_config or {},
        nodes=payload.nodes or [],
        edges=payload.edges or [],
        is_active=payload.is_active,
        stats={"entered": 0, "completed": 0, "goals_converted": 0, "revenue_recovered": 0}
    )
    db.add(flow)
    db.commit()
    db.refresh(flow)
    return flow


@router.get("/{flow_id}", response_model=schemas.WorkflowFlowResponse)
def get_workflow_flow(
    flow_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """Retrieves a single workflow with its complete node and edge graph."""
    flow = db.query(models.WorkflowFlow).filter(models.WorkflowFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Workflow flow not found")
    return flow


@router.put("/{flow_id}", response_model=schemas.WorkflowFlowResponse)
def update_workflow_flow(
    flow_id: int,
    payload: schemas.WorkflowFlowUpdate,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """Updates a workflow's details, node positions, connections, and properties."""
    flow = db.query(models.WorkflowFlow).filter(models.WorkflowFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Workflow flow not found")

    if payload.name is not None:
        flow.name = payload.name
    if payload.description is not None:
        flow.description = payload.description
    if payload.trigger_type is not None:
        flow.trigger_type = payload.trigger_type
    if payload.trigger_config is not None:
        flow.trigger_config = payload.trigger_config
    if payload.nodes is not None:
        flow.nodes = payload.nodes
    if payload.edges is not None:
        flow.edges = payload.edges
    if payload.is_active is not None:
        flow.is_active = payload.is_active

    flow.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(flow)
    return flow


@router.delete("/{flow_id}")
def delete_workflow_flow(
    flow_id: int,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """Deletes a workflow and all associated execution sessions."""
    flow = db.query(models.WorkflowFlow).filter(models.WorkflowFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Workflow flow not found")

    db.query(models.WorkflowSession).filter(models.WorkflowSession.flow_id == flow_id).delete()
    db.delete(flow)
    db.commit()
    return {"status": "success", "message": f"Workflow flow #{flow_id} deleted successfully"}


@router.post("/{flow_id}/toggle", response_model=schemas.WorkflowFlowResponse)
def toggle_workflow_status(
    flow_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """Toggles active/paused state for a workflow journey."""
    flow = db.query(models.WorkflowFlow).filter(models.WorkflowFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Workflow flow not found")

    flow.is_active = not flow.is_active
    db.commit()
    db.refresh(flow)
    return flow


def get_session_wa_sort_key(s: models.WorkflowSession):
    """Calculates sorting score: sessions with the most recently dispatched WhatsApp message rank at the top."""
    latest_wa_ts = None
    if s.state_data and isinstance(s.state_data, dict) and s.state_data.get("last_whatsapp_sent_at"):
        latest_wa_ts = s.state_data.get("last_whatsapp_sent_at")

    if not latest_wa_ts and s.history and isinstance(s.history, list):
        for h in reversed(s.history):
            if isinstance(h, dict):
                node_type = str(h.get("node_type", "")).lower()
                label = str(h.get("label", "")).lower()
                if "whatsapp" in node_type or "whatsapp" in label:
                    ts = h.get("timestamp")
                    if ts:
                        latest_wa_ts = ts
                        break

    wa_score = 0.0
    if latest_wa_ts:
        try:
            dt = datetime.fromisoformat(str(latest_wa_ts).replace("Z", "+00:00"))
            wa_score = dt.timestamp()
        except Exception:
            wa_score = 1.0

    upd_score = s.updated_at.timestamp() if s.updated_at else (s.created_at.timestamp() if s.created_at else float(s.id))
    activity_score = max(wa_score, upd_score)
    return (activity_score, s.id)


@router.get("/{flow_id}/sessions", response_model=List[schemas.WorkflowSessionResponse])
def get_workflow_sessions(
    flow_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """Returns the enrolled customer contacts and execution sessions traversing this workflow,
    ordered so whichever contact was sent a WhatsApp message most recently in the automation comes at the top."""
    sessions = (
        db.query(models.WorkflowSession)
        .filter(models.WorkflowSession.flow_id == flow_id)
        .all()
    )
    sessions.sort(key=get_session_wa_sort_key, reverse=True)
    return sessions[:250]


@router.post("/{flow_id}/clear-queue")
def clear_workflow_queue(
    flow_id: int,
    mode: str = Query("cancel_active", pattern="^(cancel_active|delete_all)$"),
    clear_stats: bool = Query(False),
    clear_cart_events: bool = Query(False),
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Clears / empties contacts and queues from a visual workflow:
    - mode="cancel_active": Sets all ACTIVE, WAITING_DELAY, and WAITING_CONDITION sessions to CANCELLED.
    - mode="delete_all": Permanently deletes all enrolled session rows for this workflow.
    - clear_stats: Resets entered, completed, goals_converted, and revenue_recovered counters to 0.
    - clear_cart_events: Deletes stored cart events if this is an abandoned cart flow.
    """
    flow = db.query(models.WorkflowFlow).filter(models.WorkflowFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Workflow flow not found")

    try:
        if mode == "cancel_active":
            cleared_count = (
                db.query(models.WorkflowSession)
                .filter(
                    models.WorkflowSession.flow_id == flow_id,
                    models.WorkflowSession.status.in_(["ACTIVE", "WAITING_DELAY", "WAITING_CONDITION"])
                )
                .update({"status": "CANCELLED"}, synchronize_session=False)
            )
        else:  # delete_all
            session_ids = [
                s[0] for s in db.query(models.WorkflowSession.id)
                .filter(models.WorkflowSession.flow_id == flow_id)
                .all()
            ]
            if session_ids:
                # Disconnect foreign key references from outbound_messages to prevent FK constraint violation
                db.query(models.OutboundMessage).filter(
                    models.OutboundMessage.workflow_session_id.in_(session_ids)
                ).update({"workflow_session_id": None}, synchronize_session=False)

                cleared_count = (
                    db.query(models.WorkflowSession)
                    .filter(models.WorkflowSession.id.in_(session_ids))
                    .delete(synchronize_session=False)
                )
            else:
                cleared_count = 0

        if clear_stats:
            flow.stats = {"entered": 0, "completed": 0, "goals_converted": 0, "revenue_recovered": 0}
            flag_modified(flow, "stats")

        cleared_carts = 0
        if clear_cart_events:
            cleared_carts = db.query(models.CartEvent).delete(synchronize_session=False)

        db.commit()
        logger.info(
            f"🧹 [Workflow Engine] User '{current_user.username}' cleared queue for flow #{flow_id} "
            f"(mode={mode}, sessions={cleared_count}, carts={cleared_carts}, reset_stats={clear_stats})"
        )
        return {
            "status": "success",
            "mode": mode,
            "cleared_count": cleared_count,
            "cleared_cart_events": cleared_carts,
            "stats_reset": clear_stats,
            "message": f"Successfully cleared {cleared_count} session(s)."
        }
    except Exception as e:
        db.rollback()
        logger.error(f"❌ [Workflow Engine] Error clearing queue for flow #{flow_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear queue: {str(e)}"
        )


