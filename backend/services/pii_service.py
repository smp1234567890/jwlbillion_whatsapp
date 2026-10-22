"""
PII Service
Centralized data protection service providing:
- Dynamic masking for phones and emails in list DTOs
- Role and record-scope authorization checks (agent assignment, manager team scope, admin broad scope)
- PII field encryption/decryption helpers at rest (AES-256-GCM)
- Data retention and cleanup routines
"""

import os
import re
import base64
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import false
from fastapi import HTTPException, status
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import models
from services.secret_store import derive_key


def mask_phone(phone: Optional[str]) -> Optional[str]:
    """
    Masks a phone number for list views, e.g.
    '+919876543210' -> '+91******3210'
    '9876543210'    -> '98******3210'
    """
    if not phone:
        return phone

    clean = phone.strip()
    if clean.startswith("+91") and len(clean) >= 12:
        return f"+91******{clean[-4:]}"
    elif clean.startswith("+") and len(clean) >= 10:
        return f"{clean[:2]}******{clean[-4:]}"
    elif len(clean) >= 10:
        return f"{clean[:2]}******{clean[-4:]}"
    elif len(clean) > 4:
        return f"{clean[0]}***{clean[-1]}"
    else:
        return "***"


def mask_email(email: Optional[str]) -> Optional[str]:
    """
    Masks an email address for list views, e.g.
    'user@example.com' -> 'm***@example.com'
    """
    if not email:
        return email

    clean = email.strip()
    if "@" not in clean:
        return "***"

    local, domain = clean.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def verify_contact_access(current_user: models.User, contact: models.Contact) -> None:
    """
    Verifies that current_user has record-level scope to view or interact with this contact.
    - admin: broad access
    - manager: team scope access
    - agent: access only if contact.assigned_user_id == current_user.id
    """
    if current_user.role in ("admin", "manager"):
        return

    if current_user.role == "agent":
        if contact.assigned_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Contact is not assigned to you."
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Your role does not have permission to access contact records."
    )


def filter_contacts_for_user(query, current_user: models.User):
    """
    Applies record-scope filtering to a Contact query:
    - admin, manager: all contacts
    - agent: only contacts where assigned_user_id == current_user.id
    """
    if current_user.role in ("admin", "manager"):
        return query

    if current_user.role == "agent":
        return query.filter(models.Contact.assigned_user_id == current_user.id)

    return query.filter(false())


def verify_conversation_access(db: Session, current_user: models.User, phone: str) -> None:
    """
    Verifies that current_user has scope to view the chat history for this phone.
    - admin, manager: broad access
    - agent: access only if customer contact exists and contact.assigned_user_id == current_user.id
    """
    if current_user.role in ("admin", "manager"):
        return

    if current_user.role == "agent":
        contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
        if not contact or contact.assigned_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Conversation is not assigned to you."
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Your role does not have permission to access conversations."
    )


def verify_support_send_permission(db: Session, current_user: models.User, phone: Optional[str] = None) -> None:
    """
    Verifies capability to send manual free-text support messages:
    - admin, manager: authorized by default
    - agent: requires explicit `can_support_send=True` AND contact assigned to them
    """
    if current_user.role in ("admin", "manager"):
        return

    if current_user.role == "agent":
        if not getattr(current_user, "can_support_send", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account does not have 'support_send' permission to initiate manual chat replies."
            )
        if phone:
            verify_conversation_access(db, current_user, phone)
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions to send chat messages."
    )


def encrypt_pii(plaintext: Optional[str]) -> Optional[str]:
    """
    Encrypts a sensitive PII field at rest using AES-256-GCM envelope encryption.
    """
    if not plaintext:
        return plaintext

    key = derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    
    # Store combined b64 format: b64(nonce):b64(ciphertext)
    b64_nonce = base64.b64encode(nonce).decode("ascii")
    b64_ct = base64.b64encode(ciphertext).decode("ascii")
    return f"enc:{b64_nonce}:{b64_ct}"


def decrypt_pii(encoded_val: Optional[str]) -> Optional[str]:
    """
    Decrypts an encrypted PII field at rest. If not encrypted, returns original value.
    """
    if not encoded_val or not encoded_val.startswith("enc:"):
        return encoded_val

    try:
        parts = encoded_val.split(":")
        if len(parts) != 3:
            return encoded_val

        _, b64_nonce, b64_ct = parts
        nonce = base64.b64decode(b64_nonce.encode("ascii"))
        ciphertext = base64.b64decode(b64_ct.encode("ascii"))

        key = derive_key()
        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
    except Exception:
        return None


def purge_expired_message_logs(db: Session, retention_days: int = 90) -> int:
    """
    Retention policy: permanently deletes audit logs older than retention_days.
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(models.MessageLog).filter(models.MessageLog.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return deleted


def purge_expired_cart_events(db: Session, retention_days: int = 30) -> int:
    """
    Retention policy: deletes abandoned cart events older than retention_days.
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(models.CartEvent).filter(models.CartEvent.created_at < cutoff).delete(synchronize_session=False)
    db.commit()
    return deleted
