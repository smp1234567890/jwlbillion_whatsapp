"""
Segments Router
Handles Contact Segmentation:
- Predefined Smart Segments (VIP, Frequent, First-Time, Inactive, Leads)
- Custom Segments (created by users based on criteria: min_orders, max_orders, city, tag, inactivity_days)
- Instant filtering and matching contacts retrieval
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

import auth
import models
import schemas
from database import get_db

router = APIRouter(prefix="/api/segments", tags=["Contact Segments"])


def query_contacts_by_criteria(db: Session, criteria: Dict[str, Any]):
    """
    Evaluates dynamic segment criteria against the contacts table.
    Supported criteria keys:
    - min_orders (int): contacts with total_orders >= min_orders
    - max_orders (int): contacts with total_orders <= max_orders
    - order_eq (int): contacts with total_orders == order_eq (e.g. 0 for leads)
    - inactivity_days (int): contacts whose last_order_date is older than N days (or null)
    - active_within_days (int): contacts with an order within past N days
    - city (str): city substring match
    - tag (str): tag substring match
    """
    q = db.query(models.Contact).filter(models.Contact.is_active == True)

    if "order_eq" in criteria and criteria["order_eq"] is not None:
        q = q.filter(models.Contact.total_orders == int(criteria["order_eq"]))

    if "min_orders" in criteria and criteria["min_orders"] is not None:
        q = q.filter(models.Contact.total_orders >= int(criteria["min_orders"]))

    if "max_orders" in criteria and criteria["max_orders"] is not None:
        q = q.filter(models.Contact.total_orders <= int(criteria["max_orders"]))

    if "inactivity_days" in criteria and criteria["inactivity_days"]:
        cutoff = datetime.utcnow() - timedelta(days=int(criteria["inactivity_days"]))
        q = q.filter(
            (models.Contact.last_order_date <= cutoff) | (models.Contact.last_order_date == None)
        )

    if "active_within_days" in criteria and criteria["active_within_days"]:
        cutoff = datetime.utcnow() - timedelta(days=int(criteria["active_within_days"]))
        q = q.filter(models.Contact.last_order_date >= cutoff)

    if "city" in criteria and criteria["city"]:
        city_term = str(criteria["city"]).strip()
        q = q.filter(models.Contact.city.ilike(f"%{city_term}%"))

    if "tag" in criteria and criteria["tag"]:
        tag_term = str(criteria["tag"]).strip()
        q = q.filter(models.Contact.tags.ilike(f"%{tag_term}%"))

    return q


def ensure_predefined_segments(db: Session):
    """
    Seeds default intelligent cohorts if not present.
    """
    defaults = [
        {
            "name": "All Active Customers",
            "description": "Every active customer registered in the CRM directory",
            "icon": "Users",
            "criteria": {},
            "is_predefined": True
        },
        {
            "name": "VIP Customers (3+ Orders)",
            "description": "High-value loyal buyers who have completed 3 or more purchases",
            "icon": "Crown",
            "criteria": {"min_orders": 3},
            "is_predefined": True
        },
        {
            "name": "Repeat Buyers (2 Orders)",
            "description": "Customers who purchased twice and are ripe for VIP loyalty offers",
            "icon": "Sparkles",
            "criteria": {"min_orders": 2, "max_orders": 2},
            "is_predefined": True
        },
        {
            "name": "First-Time Customers (1 Order)",
            "description": "New buyers who placed their first purchase; ideal for onboarding flows",
            "icon": "ShoppingBag",
            "criteria": {"order_eq": 1},
            "is_predefined": True
        },
        {
            "name": "New Inbound Leads (0 Orders)",
            "description": "Leads who contacted via WhatsApp or opted-in but haven't bought yet",
            "icon": "UserPlus",
            "criteria": {"order_eq": 0},
            "is_predefined": True
        },
        {
            "name": "At-Risk Inactive (30+ Days)",
            "description": "Customers with no order in the last 30 days; target with win-back campaigns",
            "icon": "Clock",
            "criteria": {"inactivity_days": 30},
            "is_predefined": True
        }
    ]

    for d in defaults:
        existing = db.query(models.ContactSegment).filter(models.ContactSegment.name == d["name"]).first()
        if not existing:
            seg = models.ContactSegment(
                name=d["name"],
                description=d["description"],
                icon=d["icon"],
                criteria=d["criteria"],
                is_predefined=True
            )
            db.add(seg)
    try:
        db.commit()
    except Exception:
        db.rollback()


@router.get("", response_model=List[schemas.ContactSegmentResponse])
def list_segments(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns all contact segments with dynamic live counts of matching contacts.
    """
    ensure_predefined_segments(db)
    segments = db.query(models.ContactSegment).order_by(
        models.ContactSegment.is_predefined.desc(),
        models.ContactSegment.id.asc()
    ).all()

    results = []
    for s in segments:
        count = query_contacts_by_criteria(db, s.criteria or {}).count()
        results.append({
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "icon": s.icon,
            "criteria": s.criteria or {},
            "is_predefined": s.is_predefined,
            "matching_contacts_count": count,
            "created_at": s.created_at,
            "updated_at": s.updated_at
        })
    return results


@router.post("", response_model=schemas.ContactSegmentResponse)
def create_segment(
    payload: schemas.ContactSegmentCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new custom segment.
    """
    seg = models.ContactSegment(
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        icon=payload.icon or "Users",
        criteria=payload.criteria or {},
        is_predefined=False
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)

    count = query_contacts_by_criteria(db, seg.criteria or {}).count()
    return {
        "id": seg.id,
        "name": seg.name,
        "description": seg.description,
        "icon": seg.icon,
        "criteria": seg.criteria or {},
        "is_predefined": False,
        "matching_contacts_count": count,
        "created_at": seg.created_at,
        "updated_at": seg.updated_at
    }


@router.get("/{segment_id}/contacts")
def get_segment_contacts(
    segment_id: int,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the live contacts belonging to a specific segment.
    """
    seg = db.query(models.ContactSegment).filter(models.ContactSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")

    q = query_contacts_by_criteria(db, seg.criteria or {})
    total = q.count()
    contacts = q.order_by(models.Contact.id.desc()).offset(offset).limit(limit).all()

    return {
        "segment_id": seg.id,
        "segment_name": seg.name,
        "criteria": seg.criteria or {},
        "total_count": total,
        "contacts": [
            {
                "id": c.id,
                "name": c.name or "Unnamed Contact",
                "phone": c.phone,
                "email": c.email,
                "city": c.city,
                "tags": c.tags,
                "total_orders": c.total_orders,
                "last_order_date": c.last_order_date,
                "created_at": c.created_at
            }
            for c in contacts
        ]
    }


@router.delete("/{segment_id}")
def delete_segment(
    segment_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes a custom segment. Predefined segments cannot be deleted.
    """
    seg = db.query(models.ContactSegment).filter(models.ContactSegment.id == segment_id).first()
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    if seg.is_predefined:
        raise HTTPException(status_code=400, detail="Predefined system segments cannot be deleted.")

    db.delete(seg)
    db.commit()
    return {"status": "success", "message": f"Segment '{seg.name}' deleted."}

