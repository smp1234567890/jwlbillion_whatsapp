import pytest
from fastapi import status

def test_login_success(client, db):
    # Ensure test user exists
    res = client.post("/api/auth/login", json={
        "username": "test_admin",
        "password": "SecretPassword123!"
    })
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_password(client):
    res = client.post("/api/auth/login", json={
        "username": "test_admin",
        "password": "WrongPassword!"
    })
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

def test_protected_routes_require_jwt(client):
    # Request without header must fail
    res = client.get("/api/campaigns")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

def test_protected_routes_accept_jwt(client, auth_headers):
    # Request with valid bearer token must pass
    res = client.get("/api/campaigns", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK

def test_registration_status_reflects_config(client):
    import config
    res = client.get("/api/auth/registration-status")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["max_users"] == config.MAX_USERS_LIMIT

def test_system_settings_reflects_config(client, auth_headers):
    import config
    res = client.get("/api/settings", headers=auth_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["daily_limit"] == 200


def test_daily_limit_is_fixed_and_cannot_be_edited(client, auth_headers):
    # Attempting to edit daily limit must be rejected with 400 Bad Request
    res = client.put("/api/settings/daily-limit", json={"daily_limit": 500}, headers=auth_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "fixed" in res.json()["detail"].lower()

