import os
import base64
import hashlib
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import config
import models


def derive_key(master_key: Optional[str] = None) -> bytes:
    """
    Derives a 256-bit (32-byte) key for AES-GCM from the configured APP_ENCRYPTION_KEY.
    """
    raw_key = master_key or config.APP_ENCRYPTION_KEY or config.SECRET_KEY or "fallback-dev-secret-key-32bytes!!"
    return hashlib.sha256(raw_key.encode("utf-8")).digest()


def store_secret(
    db: Session,
    secret_ref: str,
    secret_value: str,
    purpose: str = "integration_credential"
) -> str:
    """
    Encrypts a secret using AES-256-GCM and persists it to the integration_secrets table.
    Never stores plaintext in PostgreSQL.
    """
    key = derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # Standard 96-bit nonce for AES-GCM
    
    ciphertext = aesgcm.encrypt(nonce, secret_value.encode("utf-8"), None)
    
    b64_ciphertext = base64.b64encode(ciphertext).decode("ascii")
    b64_nonce = base64.b64encode(nonce).decode("ascii")
    
    existing = db.query(models.IntegrationSecret).filter(
        models.IntegrationSecret.secret_reference == secret_ref
    ).first()
    
    if existing:
        existing.encrypted_value = b64_ciphertext
        existing.nonce = b64_nonce
        existing.updated_at = datetime.utcnow()
    else:
        sec = models.IntegrationSecret(
            secret_reference=secret_ref,
            encrypted_value=b64_ciphertext,
            nonce=b64_nonce,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(sec)
        
    db.commit()
    return secret_ref


def get_secret(db: Session, secret_ref: str) -> Optional[str]:
    """
    Fetches and decrypts the secret value corresponding to the given secret_reference.
    Returns None if not found or decryption fails.
    """
    if not secret_ref:
        return None
        
    rec = db.query(models.IntegrationSecret).filter(
        models.IntegrationSecret.secret_reference == secret_ref
    ).first()
    
    if not rec:
        return None
        
    key = derive_key()
    aesgcm = AESGCM(key)
    try:
        nonce = base64.b64decode(rec.nonce.encode("ascii"))
        ciphertext = base64.b64decode(rec.encrypted_value.encode("ascii"))
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
    except Exception:
        return None


def delete_secret(db: Session, secret_ref: str) -> bool:
    """
    Removes a secret from the integration_secrets table.
    """
    if not secret_ref:
        return False
        
    rec = db.query(models.IntegrationSecret).filter(
        models.IntegrationSecret.secret_reference == secret_ref
    ).first()
    
    if rec:
        db.delete(rec)
        db.commit()
        return True
    return False
