"""
Contacts Router
Handles contact listing, creation, updates, deletion, assignment, and CSV import/export.
Enforces PII record-scope authorization (agents only access assigned contacts),
masked list DTOs, strict pagination bounds, and admin step-up authentication for exports.
"""

import csv
import io
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

import auth
import models
import schemas
from database import get_db
from services.phone_service import normalize_phone, InvalidPhoneNumberError
from services.policy_service import record_consent
from services import pii_service

logger = logging.getLogger("contacts_router")

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.post("", response_model=schemas.ContactResponse, status_code=status.HTTP_201_CREATED)
def create_or_get_contact(
    payload: schemas.ContactCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        clean_phone = normalize_phone(payload.phone)
    except InvalidPhoneNumberError as e:
        raise HTTPException(status_code=400, detail=str(e))

    contact = db.query(models.Contact).filter(models.Contact.phone == clean_phone).first()
    if contact:
        pii_service.verify_contact_access(current_user, contact)
        if payload.name:
            contact.name = payload.name
        if payload.email:
            contact.email = payload.email
        if payload.city:
            contact.city = payload.city
        if payload.tags:
            contact.tags = payload.tags
        if payload.total_orders is not None and payload.total_orders > 0:
            contact.total_orders = payload.total_orders
        if payload.last_order_date:
            contact.last_order_date = payload.last_order_date
        if payload.birth_day:
            contact.birth_day = payload.birth_day
        if payload.birth_month:
            contact.birth_month = payload.birth_month
        if payload.custom_attributes:
            existing_attrs = dict(contact.custom_attributes or {})
            existing_attrs.update(payload.custom_attributes)
            contact.custom_attributes = existing_attrs
        db.commit()
        db.refresh(contact)
        return contact
    
    # If agent creates contact, automatically assign to them
    assigned_user = current_user.id if current_user.role == "agent" else None

    new_contact = models.Contact(
        phone=clean_phone,
        name=payload.name,
        email=payload.email,
        city=payload.city,
        tags=payload.tags,
        total_orders=payload.total_orders or 0,
        last_order_date=payload.last_order_date,
        birth_day=payload.birth_day,
        birth_month=payload.birth_month,
        assigned_user_id=assigned_user,
        custom_attributes=payload.custom_attributes or {}
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


@router.get("", response_model=List[schemas.ContactListItemResponse])
def list_contacts(
    search: Optional[str] = None,
    tag: Optional[str] = None,
    skip: int = 0,
    limit: int = 5000,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists contacts with enforced pagination (supports up to 10,000 for directory and broadcast campaigns).
    Non-admin list DTOs mask phones (+91******3210) and emails (m***@domain.com).
    Agents can only list contacts assigned to their account.
    """
    effective_limit = min(max(1, limit), 10000)
    query = db.query(models.Contact)
    
    # Enforce agent record scope
    query = pii_service.filter_contacts_for_user(query, current_user)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.Contact.phone.ilike(search_pattern)) |
            (models.Contact.name.ilike(search_pattern)) |
            (models.Contact.email.ilike(search_pattern)) |
            (models.Contact.city.ilike(search_pattern))
        )
    if tag:
        query = query.filter(models.Contact.tags.ilike(f"%{tag}%"))

    contacts = query.order_by(models.Contact.id.desc()).offset(skip).limit(effective_limit).all()

    is_privileged = current_user.role in ("admin", "manager")
    return [
        schemas.ContactListItemResponse(
            id=c.id,
            phone=c.phone if is_privileged else pii_service.mask_phone(c.phone),
            name=c.name,
            email=c.email if is_privileged else pii_service.mask_email(c.email),
            total_orders=c.total_orders or 0,
            last_order_date=c.last_order_date,
            city=c.city,
            tags=c.tags,
            birth_day=c.birth_day,
            birth_month=c.birth_month,
            is_active=c.is_active,
            assigned_user_id=c.assigned_user_id,
            custom_attributes=c.custom_attributes or {}
        )
        for c in contacts
    ]


@router.get("/{contact_id}", response_model=schemas.ContactResponse)
def get_contact_detail(
    contact_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns full unmasked contact details only if the user has record-level scope
    (admin, manager, or the agent assigned to this contact).
    """
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    pii_service.verify_contact_access(current_user, contact)
    return contact


@router.put("/{contact_id}", response_model=schemas.ContactResponse)
def update_contact(
    contact_id: int,
    payload: schemas.ContactUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    pii_service.verify_contact_access(current_user, contact)

    # Re-assignment restricted to admin and manager
    if payload.assigned_user_id is not None:
        if current_user.role not in ("admin", "manager"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and managers can reassign contacts."
            )
        if payload.assigned_user_id != contact.assigned_user_id:
            assigned_user = db.query(models.User).filter(models.User.id == payload.assigned_user_id).first()
            if not assigned_user:
                raise HTTPException(status_code=400, detail="Target user for assignment does not exist.")
            contact.assigned_user_id = payload.assigned_user_id

    if payload.phone:
        try:
            clean_phone = normalize_phone(payload.phone)
        except InvalidPhoneNumberError as e:
            raise HTTPException(status_code=400, detail=str(e))
        # Check if phone is taken by another contact
        existing = db.query(models.Contact).filter(models.Contact.phone == clean_phone, models.Contact.id != contact_id).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Phone {clean_phone} is already registered to another contact")
        contact.phone = clean_phone

    if payload.name is not None:
        contact.name = payload.name
    if payload.email is not None:
        contact.email = payload.email
    if payload.city is not None:
        contact.city = payload.city
    if payload.tags is not None:
        contact.tags = payload.tags
    if payload.total_orders is not None:
        contact.total_orders = max(0, payload.total_orders)
    if payload.last_order_date is not None:
        contact.last_order_date = payload.last_order_date
    if payload.custom_attributes is not None:
        existing_attrs = dict(contact.custom_attributes or {})
        existing_attrs.update(payload.custom_attributes)
        contact.custom_attributes = existing_attrs

    db.commit()
    db.refresh(contact)
    return contact


@router.post("/{contact_id}/assign", response_model=schemas.ContactResponse)
def assign_contact(
    contact_id: int,
    payload: schemas.ContactAssignRequest,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Explicit assignment endpoint for managers/admins to map a contact to a support agent.
    Creates an immutable AuditEvent record.
    """
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if payload.assigned_user_id is not None:
        target_user = db.query(models.User).filter(models.User.id == payload.assigned_user_id).first()
        if not target_user:
            raise HTTPException(status_code=400, detail=f"User ID {payload.assigned_user_id} does not exist.")

    contact.assigned_user_id = payload.assigned_user_id
    db.commit()
    db.refresh(contact)

    audit = models.AuditEvent(
        actor_user_id=current_user.id,
        action="assign_contact",
        target_type="contact",
        target_id=str(contact_id),
        metadata_json={"assigned_user_id": payload.assigned_user_id}
    )
    db.add(audit)
    db.commit()

    return contact


@router.delete("/{contact_id}")
def delete_contact(
    contact_id: int,
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.delete(contact)
    db.commit()
    return {"status": "success", "message": f"Contact {contact.phone} deleted successfully"}


@router.post("/import-csv")
async def import_contacts_csv(
    file: UploadFile = File(...),
    column_mapping: Optional[str] = Form(None),
    current_user: models.User = Depends(auth.require_roles("admin", "manager")),
    db: Session = Depends(get_db)
):
    """
    Imports contacts from a CSV file with optional custom column mappings.
    Restricted to admin/manager.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 Megabytes (supports 100,000+ contacts)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds 100MB limit (File size: {len(content) / (1024 * 1024):.2f}MB). Please upload a smaller file."
        )

    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = content.decode("latin-1")

    # Parse column mapping if supplied as JSON string
    custom_map = {}
    if column_mapping:
        try:
            custom_map = json.loads(column_mapping)
        except Exception:
            custom_map = {}

    reader = csv.DictReader(io.StringIO(decoded))
    
    queue_contacts = {}
    for row in reader:
        # Preserve original trimmed mapping and lowercased mapping
        clean_row = {str(k).strip(): str(v).strip() for k, v in row.items() if k is not None}
        norm_row = {k.lower(): v for k, v in clean_row.items()}

        # 1. Resolve phone number
        raw_phone = None
        if custom_map.get("phone") and custom_map["phone"] in clean_row:
            raw_phone = clean_row[custom_map["phone"]]
        elif custom_map.get("phone") and custom_map["phone"].lower() in norm_row:
            raw_phone = norm_row[custom_map["phone"].lower()]
        else:
            for key, val in norm_row.items():
                if any(k in key for k in ["phone", "mobile", "contact", "number", "tel"]):
                    raw_phone = val
                    break

        if not raw_phone:
            continue

        try:
            phone = normalize_phone(raw_phone)
        except InvalidPhoneNumberError:
            continue

        # 2. Resolve Name (support first_name + last_name combination or single name field)
        name = None
        if custom_map.get("first_name") or custom_map.get("last_name"):
            fn = clean_row.get(custom_map.get("first_name", ""), "") if custom_map.get("first_name") else ""
            ln = clean_row.get(custom_map.get("last_name", ""), "") if custom_map.get("last_name") else ""
            comb = f"{fn} {ln}".strip()
            if comb:
                name = comb
        elif custom_map.get("name") and custom_map["name"] in clean_row:
            name = clean_row[custom_map["name"]]

        if not name:
            name = (
                norm_row.get("name")
                or norm_row.get("full_name")
                or f"{norm_row.get('first_name', '')} {norm_row.get('last_name', '')}".strip()
                or None
            )

        # 3. Resolve Email
        email = None
        if custom_map.get("email") and custom_map["email"] in clean_row:
            email = clean_row[custom_map["email"]]
        else:
            email = norm_row.get("email")

        # 4. Resolve City
        city = None
        if custom_map.get("city") and custom_map["city"] in clean_row:
            city = clean_row[custom_map["city"]]
        else:
            city = norm_row.get("city")

        # 5. Resolve Tags
        tags = None
        if custom_map.get("tags") and custom_map["tags"] in clean_row:
            tags = clean_row[custom_map["tags"]]
        else:
            tags = norm_row.get("tags")

        # 6. Resolve Total Orders
        orders_str = "0"
        if custom_map.get("total_orders") and custom_map["total_orders"] in clean_row:
            orders_str = clean_row[custom_map["total_orders"]]
        else:
            orders_str = norm_row.get("total_orders") or norm_row.get("orders") or "0"
        try:
            total_orders = int(orders_str)
        except ValueError:
            total_orders = 0

        # 7. Resolve Last Order Date
        last_order_raw = None
        if custom_map.get("last_order_date") and custom_map["last_order_date"] in clean_row:
            last_order_raw = clean_row[custom_map["last_order_date"]]
        else:
            last_order_raw = norm_row.get("last_order_date") or norm_row.get("last_order") or norm_row.get("order_date")

        parsed_last_order = None
        if last_order_raw:
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    parsed_last_order = datetime.strptime(last_order_raw.strip(), fmt)
                    break
                except ValueError:
                    pass

        queue_contacts[phone] = {
            "name": name,
            "email": email,
            "city": city,
            "tags": tags,
            "total_orders": total_orders,
            "last_order_date": parsed_last_order
        }

    imported_count = 0
    updated_count = 0
    BATCH_SIZE = 500

    phone_keys = list(queue_contacts.keys())
    for i in range(0, len(phone_keys), BATCH_SIZE):
        batch_chunk = phone_keys[i:i + BATCH_SIZE]
        
        # Prepare bulk records for Postgres ON CONFLICT DO UPDATE
        insert_values = []
        for phone in batch_chunk:
            item = queue_contacts[phone]
            insert_values.append({
                "phone": phone,
                "name": item["name"],
                "email": item["email"],
                "city": item["city"],
                "tags": item["tags"],
                "total_orders": item["total_orders"],
                "last_order_date": item["last_order_date"]
            })

        if insert_values:
            stmt = pg_insert(models.Contact).values(insert_values)
            # On conflict on unique phone, update fields if provided
            stmt = stmt.on_conflict_do_update(
                index_elements=["phone"],
                set_={
                    "name": stmt.excluded.name,
                    "email": stmt.excluded.email,
                    "city": stmt.excluded.city,
                    "tags": stmt.excluded.tags,
                    "total_orders": stmt.excluded.total_orders,
                    "last_order_date": stmt.excluded.last_order_date
                }
            )
            res = db.execute(stmt)
            db.commit()
            imported_count += len(insert_values)

    return {
        "status": "success",
        "imported": imported_count,
        "total_queued": len(queue_contacts),
        "message": f"Successfully processed {imported_count} contacts across {max(1, len(phone_keys)//BATCH_SIZE + (1 if len(phone_keys)%BATCH_SIZE else 0))} batches of 500."
    }


@router.post("/export")
def export_contacts(
    payload: schemas.ContactExportRequest,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    """
     Step-Up Auth Protected Contact Export:
    Strictly restricted to admin. Requires password, 2FA code, and valid business justification.
    Records an immutable AuditEvent.
    """
    auth.verify_user_stepup_auth(current_user, payload.password, payload.two_factor_code, db)

    contacts = db.query(models.Contact).order_by(models.Contact.id.asc()).limit(1000).all()

    audit = models.AuditEvent(
        actor_user_id=current_user.id,
        action="export_contacts",
        target_type="contacts",
        metadata_json={
            "reason": payload.reason,
            "record_count": len(contacts)
        }
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "total": len(contacts),
        "contacts": [
            {
                "id": c.id,
                "phone": c.phone,
                "name": c.name,
                "email": c.email,
                "city": c.city,
                "total_orders": c.total_orders,
                "tags": c.tags,
                "assigned_user_id": c.assigned_user_id,
                "custom_attributes": c.custom_attributes or {}
            }
            for c in contacts
        ]
    }


@router.post("/sync", status_code=status.HTTP_200_OK)
async def sync_contact_api(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    """
    Direct API endpoint to sync/upsert a customer contact.
    Accepts X-API-Key header, Authorization Bearer token, or active user session.
    """
    from routers.webhooks import process_customer_sync, get_sync_webhook_authenticated_user
    current_user = await get_sync_webhook_authenticated_user(request=request, db=db)
    return process_customer_sync(payload=payload, current_user=current_user, db=db)
