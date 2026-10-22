import pytest
import uuid
import hashlib
from datetime import datetime, timedelta
from fastapi import status
import config
import models
import auth
from auth import (
    create_access_token,
    create_refresh_token_for_user,
    rotate_refresh_token,
    revoke_all_user_sessions,
    get_password_hash
)


def test_legacy_permanent_api_token_rejected(client, db):
    # 1. Create a user with legacy token
    legacy_tok = f"mb_live_{uuid.uuid4().hex}"
    user = models.User(
        username=f"legacy_{uuid.uuid4().hex[:6]}",
        email=f"legacy_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("Pass123!"),
        role="agent",
        is_active=True,
        auth_version=1
    )
    db.add(user)
    db.commit()

    # Attempt to authenticate using the legacy token
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {legacy_tok}"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    # Old api-token routes must be removed (404 Not Found)
    res_route = client.get("/api/auth/api-token", headers={"Authorization": f"Bearer {legacy_tok}"})
    assert res_route.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_404_NOT_FOUND)


def test_access_token_includes_auth_version_and_expires(client, db):
    user = models.User(
        username=f"short_{uuid.uuid4().hex[:6]}",
        email=f"short_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("Pass123!"),
        role="agent",
        is_active=True,
        auth_version=1
    )
    db.add(user)
    db.commit()

    # Expired token (issued with negative delta)
    expired_token = create_access_token(
        data={"sub": user.username, "role": user.role, "auth_version": user.auth_version},
        expires_delta=timedelta(seconds=-10)
    )
    res_exp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_exp.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_token_rotation_lifecycle(client, db):
    user = models.User(
        username=f"rot_{uuid.uuid4().hex[:6]}",
        email=f"rot_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("Pass123!"),
        role="agent",
        is_active=True,
        auth_version=1
    )
    db.add(user)
    db.commit()

    # Initial refresh token creation
    raw_rt1, rec1 = create_refresh_token_for_user(db, user)
    assert raw_rt1 is not None
    assert rec1.family_id is not None
    assert rec1.token_hash == hashlib.sha256(raw_rt1.encode("utf-8")).hexdigest()

    # Rotation 1: exchange rt1 for rt2
    rot1 = rotate_refresh_token(db, raw_rt1)
    assert rot1 is not None
    new_access_token, raw_rt2 = rot1
    assert raw_rt2 != raw_rt1

    # Verify rec1 is marked rotated
    db.refresh(rec1)
    assert rec1.rotated_at is not None

    # Verify new access token works
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access_token}"})
    assert res_me.status_code == status.HTTP_200_OK

    # REUSE ATTACK: Attempt to use the already rotated rt1 again
    with pytest.raises(auth.RefreshTokenReuseError):
        rotate_refresh_token(db, raw_rt1)

    # Verify whole family was revoked and user auth_version incremented
    db.refresh(user)
    assert user.auth_version > 1

    # rt2 should also now fail because family was revoked
    with pytest.raises(auth.RefreshTokenInvalidError):
        rotate_refresh_token(db, raw_rt2)


def test_session_invalidation_on_password_reset_and_role_change(client, db):
    user = models.User(
        username=f"inval_{uuid.uuid4().hex[:6]}",
        email=f"inval_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("Pass123!"),
        role="agent",
        is_active=True,
        auth_version=1
    )
    db.add(user)
    db.commit()

    # Issue access token and refresh token
    access_token = create_access_token(data={"sub": user.username, "role": user.role, "auth_version": user.auth_version})
    raw_rt, rec = create_refresh_token_for_user(db, user)

    # Verify access token works initially
    res_init = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert res_init.status_code == status.HTTP_200_OK

    # Simulate password reset / admin session revocation
    revoke_all_user_sessions(db, user)

    # 1. Previous access token must now be rejected
    res_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert res_after.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Previous refresh token must now be rejected
    with pytest.raises(auth.RefreshTokenInvalidError):
        rotate_refresh_token(db, raw_rt)


def test_refresh_endpoint_api_flow(client, db):
    user = models.User(
        username=f"flow_{uuid.uuid4().hex[:6]}",
        email=f"flow_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("Pass123!"),
        role="agent",
        is_active=True,
        auth_version=1
    )
    db.add(user)
    db.commit()

    raw_rt, rec = create_refresh_token_for_user(db, user)

    # POST to /api/auth/refresh
    res = client.post("/api/auth/refresh", json={"refresh_token": raw_rt})
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data
    # Security requirement: raw refresh token must not be included in API response JSON
    assert data.get("refresh_token") is None
    # Security requirement: rotated token is issued via cookie
    assert "refresh_token" in res.cookies
    assert res.cookies["refresh_token"] != raw_rt

    # Ensure UserResponse never exposes api_token or raw credentials
    res_user = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert res_user.status_code == status.HTTP_200_OK
    user_data = res_user.json()
    assert "api_token" not in user_data
    assert "hashed_password" not in user_data
