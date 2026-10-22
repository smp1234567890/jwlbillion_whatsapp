import os
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Callable, Optional
from dotenv import load_dotenv
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models

import config

SECRET_KEY = config.SECRET_KEY
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class RefreshTokenReuseError(Exception):
    """Raised when an already rotated refresh token is presented, indicating potential theft."""
    pass


class RefreshTokenInvalidError(Exception):
    """Raised when a refresh token is expired, revoked, or non-existent."""
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    if "auth_version" not in to_encode:
        to_encode["auth_version"] = 1
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") == "access":
            return payload
    except Exception:
        pass
    return None


def create_refresh_token_for_user(
    db: Session,
    user: models.User,
    family_id: Optional[str] = None
) -> tuple[str, models.RefreshToken]:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    fam_id = family_id or str(uuid.uuid4())
    expire_days = getattr(config, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    expires_at = datetime.utcnow() + timedelta(days=expire_days)

    db_token = models.RefreshToken(
        user_id=user.id,
        family_id=fam_id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return raw_token, db_token


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[str, str]:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    token_record = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == token_hash).first()

    if not token_record:
        raise RefreshTokenInvalidError("Invalid refresh token")

    user = db.query(models.User).filter(models.User.id == token_record.user_id).first()
    if not user or not user.is_active:
        raise RefreshTokenInvalidError("User inactive or not found")

    if token_record.revoked_at is not None:
        raise RefreshTokenInvalidError("Refresh token has been revoked")

    if token_record.rotated_at is not None:
        # Compromise / replay detected: revoke the entire token family & increment auth_version
        now = datetime.utcnow()
        db.query(models.RefreshToken).filter(
            models.RefreshToken.family_id == token_record.family_id,
            models.RefreshToken.revoked_at.is_(None)
        ).update({"revoked_at": now})
        user.auth_version = (user.auth_version or 1) + 1
        db.commit()
        raise RefreshTokenReuseError("Refresh token reuse detected. Family revoked and all sessions invalidated.")

    if token_record.expires_at < datetime.utcnow():
        token_record.revoked_at = datetime.utcnow()
        db.commit()
        raise RefreshTokenInvalidError("Refresh token has expired")

    # Mark current token as rotated
    token_record.rotated_at = datetime.utcnow()

    # Generate new token in same family
    new_raw_token, _ = create_refresh_token_for_user(db, user, family_id=token_record.family_id)

    # Generate new access token
    new_access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "auth_version": user.auth_version}
    )

    return new_access_token, new_raw_token


def revoke_all_user_sessions(db: Session, user: models.User):
    user.auth_version = (user.auth_version or 1) + 1
    now = datetime.utcnow()
    db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user.id,
        models.RefreshToken.revoked_at.is_(None)
    ).update({"revoked_at": now})
    db.commit()


def create_temp_2fa_token(username: str) -> str:
    """
    Creates a temporary 5-minute token used exclusively for the 2FA verification step.
    Cannot be used to access regular protected endpoints.
    """
    to_encode = {
        "sub": username,
        "type": "2fa_pending",
        "exp": datetime.utcnow() + timedelta(minutes=5)
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_temp_2fa_token(temp_token: str) -> str:
    """
    Validates a temp_token and returns the username if valid.
    """
    try:
        payload = jwt.decode(temp_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "2fa_pending":
            raise HTTPException(status_code=401, detail="Invalid token type for 2FA verification")
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="2FA session expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid 2FA challenge token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = db.query(models.User).filter(models.User.username == username).first()
        if user is None:
            raise credentials_exception
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user account")

        # Session invalidation check: verify token auth_version matches user's current auth_version
        token_auth_version = payload.get("auth_version")
        if token_auth_version is not None and token_auth_version != getattr(user, "auth_version", 1):
            raise credentials_exception

        return user
    except jwt.PyJWTError:
        # Permanent API tokens are strictly rejected
        raise credentials_exception


def require_roles(*allowed_roles: str) -> Callable:
    def role_guard(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account does not have permission to perform this action.",
            )
        return current_user

    return role_guard


def verify_user_stepup_auth(user: models.User, password: Optional[str], two_factor_code: Optional[str], db: Session):
    """
    🔐 Step-Up Authentication Guard for Critical & High-Volume Operations:
    Validates user password and (if 2FA enabled or code provided) verifies 6-digit TOTP / Email OTP.
    """
    if not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account password is required to authorize this high-impact action."
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect account password. Authorization denied."
        )

    # If user has 2FA enabled, 2FA code is mandatory
    if user.is_2fa_enabled or two_factor_code:
        code = (two_factor_code or "").strip().replace(" ", "")
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA verification code is required to authorize this action."
            )

        verified = False
        # 1. TOTP code
        if user.totp_secret:
            try:
                import pyotp
                totp = pyotp.TOTP(user.totp_secret)
                if totp.verify(code, valid_window=1):
                    verified = True
            except Exception as e:
                pass

        # 2. Email recovery OTP
        if not verified and user.email_recovery_code and user.email_recovery_code_expires:
            if datetime.utcnow() <= user.email_recovery_code_expires and user.email_recovery_code == code:
                verified = True
                user.email_recovery_code = None
                user.email_recovery_code_expires = None
                db.commit()

        if not verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired 2FA verification code."
            )

    return True
