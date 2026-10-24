"""
Auth & User Management Router
Handles user registration, login, 2FA setup/enable/disable/verify, profile me,
registration status, and administrative user CRUD operations.
"""

import base64
import io
import logging
import secrets
import hashlib
from datetime import datetime
from typing import List, Optional

import pyotp
import qrcode
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

import auth
import config
import models
import schemas
from database import get_db
from rate_limiter import limiter, get_trusted_client_ip
try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger("auth_router")

router = APIRouter(tags=["auth"])

FAILED_LOGIN_ATTEMPTS = {}
_redis_client = None
if redis and getattr(config, "REDIS_URL", None):
    try:
        _redis_client = redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
            retry_on_timeout=False
        )
    except Exception as err:
        logger.warning(f"Could not initialize Redis client for auth throttling: {err}")


def record_failed_attempt(key: str, lockout_seconds: int = 900) -> int:
    if _redis_client:
        try:
            attempts = _redis_client.incr(f"auth_fail:{key}")
            if attempts == 1:
                _redis_client.expire(f"auth_fail:{key}", lockout_seconds)
            return attempts
        except Exception as err:
            logger.warning(f"Redis auth throttling operation warning: {err}")
    attempts = FAILED_LOGIN_ATTEMPTS.get(key, 0) + 1
    FAILED_LOGIN_ATTEMPTS[key] = attempts
    return attempts


def clear_failed_attempts(key: str) -> None:
    if _redis_client:
        try:
            _redis_client.delete(f"auth_fail:{key}")
        except Exception:
            pass
    FAILED_LOGIN_ATTEMPTS.pop(key, None)


def get_failed_attempts(key: str) -> int:
    if _redis_client:
        try:
            val = _redis_client.get(f"auth_fail:{key}")
            return int(val) if val else 0
        except Exception as err:
            logger.warning(f"Redis get failed attempts warning: {err}")
    return FAILED_LOGIN_ATTEMPTS.get(key, 0)


@router.post("/api/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register_user(
    request: Request,
    payload: schemas.UserCreate,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    max_users = config.MAX_USERS_LIMIT
    current_user_count = db.query(models.User).count()
    if current_user_count >= max_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User registration limit reached ({max_users}/{max_users} users created). No more user accounts can be registered."
        )

    existing = db.query(models.User).filter(
        (models.User.username == payload.username) | (models.User.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    user = models.User(
        username=payload.username.strip(),
        email=payload.email.strip().lower(),
        hashed_password=auth.get_password_hash(payload.password),
        is_active=True,
        role="agent"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/api/auth/login", response_model=schemas.Token)
def login(
    request: Request,
    response: Response,
    payload: schemas.UserLogin,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    client_ip = get_trusted_client_ip(request)
    fail_key = f"{client_ip}:{payload.username.strip().lower()}"

    # Fast in-memory check to prevent external I/O latency on login
    if FAILED_LOGIN_ATTEMPTS.get(fail_key, 0) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Account temporarily locked for 15 minutes."
        )

    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        record_failed_attempt(fail_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # ⚡ Automatic Rehash: upgrade stored hash to fast rounds (rounds=4) on successful login
    try:
        if auth.pwd_context.needs_update(user.hashed_password) or (
            user.hashed_password and not user.hashed_password.startswith("$2b$04$")
        ):
            user.hashed_password = auth.get_password_hash(payload.password)
            db.commit()
    except Exception as rehash_err:
        logger.warning(f"Password rehash skipped: {rehash_err}")

    # Asynchronously clear failed attempts without freezing HTTP response
    background_tasks.add_task(clear_failed_attempts, fail_key)



    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role, "auth_version": user.auth_version}
    )
    raw_rt, _ = auth.create_refresh_token_for_user(db, user)

    # Set HttpOnly Secure cookie for the refresh token (samesite=none required for cross-domain Vercel -> Render)
    is_prod = config.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=raw_rt,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=7 * 24 * 3600,
        path="/api/auth"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "requires_2fa": False,
        "refresh_token": raw_rt
    }


@router.post("/api/auth/2fa/verify", response_model=schemas.Token)
@limiter.limit("10/minute")
def verify_two_factor_code(
    request: Request,
    response: Response,
    payload: schemas.TwoFactorVerifyRequest,
    db: Session = Depends(get_db)
):
    """
    Verifies a 6-digit TOTP Google Authenticator code OR an emergency email recovery code.
    Issues short-lived access token and refresh token upon success.
    """
    client_ip = get_trusted_client_ip(request)
    
    if not payload.temp_token:
        raise HTTPException(status_code=400, detail="Missing 2FA temporary session token")
    
    username = auth.verify_temp_2fa_token(payload.temp_token)
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or deactivated")

    fail_key = f"2fa_{client_ip}:{user.username}"
    if get_failed_attempts(fail_key) >= 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed 2FA verification attempts. Account temporarily locked for 15 minutes."
        )

    code = payload.code.strip().replace(" ", "")
    verified = False

    if user.totp_secret:
        try:
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(code, valid_window=1):
                verified = True
        except Exception as e:
            logger.warning(f"Error in TOTP verification: {e}")

    if not verified and user.email_recovery_code and user.email_recovery_code_expires:
        if datetime.utcnow() <= user.email_recovery_code_expires and user.email_recovery_code == code:
            verified = True
            user.email_recovery_code = None
            user.email_recovery_code_expires = None
            db.commit()

    if not verified:
        record_failed_attempt(fail_key)
        raise HTTPException(status_code=400, detail="Invalid 2FA code or expired recovery code")

    clear_failed_attempts(fail_key)

    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role, "auth_version": user.auth_version}
    )
    raw_rt, _ = auth.create_refresh_token_for_user(db, user)

    is_prod = config.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=raw_rt,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=7 * 24 * 3600,
        path="/api/auth"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "requires_2fa": False,
        "refresh_token": raw_rt
    }


@router.get("/api/auth/2fa/setup", response_model=schemas.TwoFactorSetupResponse)
def setup_two_factor_auth(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    new_secret = pyotp.random_base32()
    current_user.totp_secret = new_secret
    db.commit()

    issuer = "JWL"
    otpauth_url = pyotp.totp.TOTP(new_secret).provisioning_uri(
        name=current_user.username,
        issuer_name=issuer
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(otpauth_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#111827", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    qr_data_uri = f"data:image/png;base64,{qr_b64}"

    return {
        "secret": new_secret,
        "otpauth_url": otpauth_url,
        "qr_code_base64": qr_data_uri
    }


@router.post("/api/auth/2fa/enable")
def enable_two_factor_auth(
    payload: schemas.TwoFactorVerifyRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA setup not initiated. Please request /api/auth/2fa/setup first.")

    totp = pyotp.TOTP(current_user.totp_secret)
    code = payload.code.strip().replace(" ", "")
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid 6-digit verification code. Please check Google Authenticator time and try again.")

    current_user.is_2fa_enabled = True
    db.commit()

    return {
        "status": "success",
        "message": "Two-Factor Authentication (2FA) successfully activated for your account!"
    }


@router.post("/api/auth/2fa/disable")
def disable_two_factor_auth(
    payload: schemas.TwoFactorDisableRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if not auth.verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password. Cannot disable 2FA.")

    current_user.is_2fa_enabled = False
    current_user.totp_secret = None
    current_user.email_recovery_code = None
    current_user.email_recovery_code_expires = None
    db.commit()

    return {
        "status": "success",
        "message": "Two-Factor Authentication (2FA) has been disabled for your account."
    }


@router.get("/api/auth/me", response_model=schemas.UserResponse)
def get_current_user_profile(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@router.get("/api/auth/registration-status")
def get_registration_status(db: Session = Depends(get_db)):
    max_users = config.MAX_USERS_LIMIT
    count = db.query(models.User).count()
    return {
        "current_users": count,
        "max_users": max_users,
        "can_register": count < max_users
    }


@router.get("/api/users", response_model=List[schemas.UserResponse])
def list_system_users(
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    return db.query(models.User).order_by(models.User.id.asc()).all()


@router.post("/api/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_system_user(
    payload: schemas.UserCreate,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    max_users = config.MAX_USERS_LIMIT
    current_user_count = db.query(models.User).count()
    if current_user_count >= max_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User limit reached ({max_users}/{max_users} users created). Cannot register more accounts."
        )

    existing = db.query(models.User).filter(
        (models.User.username == payload.username) | (models.User.email == payload.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    user = models.User(
        username=payload.username.strip(),
        email=payload.email.strip().lower(),
        hashed_password=auth.get_password_hash(payload.password),
        is_active=True,
        role=payload.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/api/users/{user_id}/role", response_model=schemas.UserResponse)
def update_user_role(
    user_id: int,
    payload: schemas.UserRoleUpdate,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found")

    if target_user.id == current_user.id and payload.role != "admin":
        admin_count = db.query(models.User).filter(models.User.role == "admin", models.User.is_active == True).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot demote yourself: system requires at least one active Admin."
            )

    target_user.role = payload.role
    auth.revoke_all_user_sessions(db, target_user)
    db.commit()
    db.refresh(target_user)
    return target_user


@router.put("/api/users/{user_id}/password")
def admin_reset_user_password(
    user_id: int,
    payload: schemas.AdminUserPasswordReset,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found")

    target_user.hashed_password = auth.get_password_hash(payload.new_password)
    auth.revoke_all_user_sessions(db, target_user)
    db.commit()
    return {
        "status": "success",
        "message": f"Password for {target_user.username} has been successfully updated by Admin. All existing sessions revoked."
    }


@router.put("/api/users/{user_id}/2fa")
def admin_toggle_user_2fa(
    user_id: int,
    payload: schemas.AdminToggle2FARequest,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found")

    target_user.is_2fa_enabled = payload.enabled
    if not payload.enabled:
        target_user.totp_secret = None
        target_user.email_recovery_code = None
        target_user.email_recovery_code_expires = None

    auth.revoke_all_user_sessions(db, target_user)
    db.commit()
    action = "enabled" if payload.enabled else "disabled"
    return {
        "status": "success",
        "message": f"2FA has been {action} for {target_user.username}. All existing sessions revoked.",
        "is_2fa_enabled": target_user.is_2fa_enabled
    }


@router.delete("/api/users/{user_id}")
def delete_user_account(
    user_id: int,
    current_user: models.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found")

    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own admin account. Please ask another administrator if you wish to remove your account."
        )

    if target_user.role == "admin":
        raise HTTPException(
            status_code=400,
            detail=f"Security Policy: Admins cannot delete other Admin accounts ({target_user.username}). To delete, demote them to a Team Member first."
        )

    target_username = target_user.username
    auth.revoke_all_user_sessions(db, target_user)
    db.delete(target_user)
    db.commit()

    return {
        "status": "success",
        "message": f"User account '{target_username}' was deleted successfully."
    }


# ============================================================================
# Token Lifecycle & Session Revocation Routes (WP4)
# ============================================================================

@router.post("/api/auth/refresh", response_model=schemas.Token)
@limiter.limit("30/minute")
def refresh_token_endpoint(
    request: Request,
    response: Response,
    payload: Optional[schemas.RefreshTokenRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Rotates a refresh token and returns a new short-lived access token + new refresh token.
    Detects reuse and invalidates the entire family upon reuse attempt.
    """
    raw_rt = None
    if payload and payload.refresh_token:
        raw_rt = payload.refresh_token
    else:
        raw_rt = request.cookies.get("refresh_token")

    if not raw_rt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token required in request body or cookie"
        )

    try:
        new_access_token, new_refresh_token = auth.rotate_refresh_token(db, raw_rt)
    except auth.RefreshTokenReuseError as e:
        logger.warning(f"Security: Refresh token reuse detected: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session compromised: Refresh token reuse detected. All sessions terminated."
        )
    except auth.RefreshTokenInvalidError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

    is_prod = config.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=7 * 24 * 3600,
        path="/api/auth"
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "refresh_token": new_refresh_token
    }


@router.post("/api/auth/logout")
def logout_endpoint(
    request: Request,
    response: Response,
    payload: Optional[schemas.RefreshTokenRequest] = None,
    db: Session = Depends(get_db)
):
    """Revokes the given refresh token session and clears the cookie."""
    raw_rt = None
    if payload and payload.refresh_token:
        raw_rt = payload.refresh_token
    else:
        raw_rt = request.cookies.get("refresh_token")

    if raw_rt:
        token_hash = hashlib.sha256(raw_rt.encode("utf-8")).hexdigest()
        rec = db.query(models.RefreshToken).filter(models.RefreshToken.token_hash == token_hash).first()
        if rec:
            rec.is_revoked = True
            db.commit()

    is_prod = config.ENVIRONMENT == "production"
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
        secure=is_prod,
        samesite="none" if is_prod else "lax"
    )

    return {"status": "success", "message": "Logged out successfully"}

