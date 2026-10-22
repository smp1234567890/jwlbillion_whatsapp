import pytest
import socket
import ipaddress
import uuid
import httpx
from fastapi import status
import config
import models
from services.secret_store import store_secret, get_secret, delete_secret, derive_key
from services.integration_gateway import (
    validate_ssrf_safe_url,
    dispatch_external_request,
    SSRFSecurityError,
    HostNotAllowedError,
    CredentialMismatchError,
    CredentialMode
)
from auth import create_access_token, get_password_hash
import pyotp


def test_ssrf_rejects_http_scheme():
    with pytest.raises(SSRFSecurityError, match="HTTPS"):
        validate_ssrf_safe_url("http://api.example.com/data")


def test_ssrf_rejects_userinfo():
    with pytest.raises(SSRFSecurityError, match="userinfo"):
        validate_ssrf_safe_url("https://user:password@api.example.com/data")


def test_ssrf_rejects_ip_literals():
    # IPv4 loopback
    with pytest.raises(SSRFSecurityError, match="IP literal"):
        validate_ssrf_safe_url("https://127.0.0.1/api")
    # IPv4 private
    with pytest.raises(SSRFSecurityError, match="IP literal"):
        validate_ssrf_safe_url("https://192.168.1.1/api")
    # IPv4 metadata
    with pytest.raises(SSRFSecurityError, match="IP literal"):
        validate_ssrf_safe_url("https://169.254.169.254/latest/meta-data")


def test_ssrf_rejects_non_443_ports():
    with pytest.raises(SSRFSecurityError, match="443"):
        validate_ssrf_safe_url("https://api.example.com:8080/data")


def test_ssrf_rejects_unallowlisted_public_hosts(monkeypatch):
    monkeypatch.setattr(config, "INTEGRATION_ALLOWED_HOSTS", ["allowed-api.example.com"])
    with pytest.raises(HostNotAllowedError, match="not allowlisted"):
        validate_ssrf_safe_url("https://unallowed.com/data")


def test_ssrf_rejects_loopback_and_private_dns_resolution(monkeypatch):
    monkeypatch.setattr(config, "INTEGRATION_ALLOWED_HOSTS", ["malicious.local"])
    
    # Mock socket.getaddrinfo to simulate malicious domain resolving to 127.0.0.1
    def mock_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
    
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)
    with pytest.raises(SSRFSecurityError, match="forbidden"):
        validate_ssrf_safe_url("https://malicious.local/data")


def test_secret_store_aes_gcm_lifecycle(db):
    secret_ref = f"sec_ref_{uuid.uuid4().hex[:12]}"
    raw_secret = "super-secret-meta-api-token-987"
    
    # Store secret
    stored_ref = store_secret(db, secret_ref=secret_ref, secret_value=raw_secret, purpose="test_api")
    assert stored_ref == secret_ref

    # Verify database record has ciphertext, not raw secret
    sec_rec = db.query(models.IntegrationSecret).filter(models.IntegrationSecret.secret_reference == secret_ref).first()
    assert sec_rec is not None
    assert sec_rec.encrypted_value != raw_secret
    assert raw_secret not in sec_rec.encrypted_value

    # Decrypt and retrieve
    decrypted = get_secret(db, secret_ref)
    assert decrypted == raw_secret

    # Delete secret
    deleted = delete_secret(db, secret_ref)
    assert deleted is True
    assert get_secret(db, secret_ref) is None


def test_dispatch_rejects_credential_host_mismatch(db, monkeypatch):
    monkeypatch.setattr(config, "INTEGRATION_ALLOWED_HOSTS", ["api.store.com", "other.store.com"])
    
    # Attempt to dispatch to other.store.com with a credential bound to api.store.com
    with pytest.raises(CredentialMismatchError, match="bound to approved host"):
        dispatch_external_request(
            endpoint_url="https://other.store.com/lookup",
            approved_hostname="api.store.com",
            credential_mode=CredentialMode.BEARER,
            secret_value="secret-token-123",
            params={"phone": "+919876543210"}
        )


def test_dispatch_treats_redirect_as_safe_failure(monkeypatch):
    monkeypatch.setattr(config, "INTEGRATION_ALLOWED_HOSTS", ["api.store.com"])

    # Mock httpx response to return 302 redirect
    def mock_get(self, url, **kwargs):
        req = httpx.Request("GET", url)
        return httpx.Response(302, headers={"Location": "https://attacker.com"}, request=req)

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    
    # Pre-mock DNS validation to succeed for api.store.com
    def mock_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    result = dispatch_external_request(
        endpoint_url="https://api.store.com/lookup",
        approved_hostname="api.store.com",
        credential_mode=CredentialMode.NONE,
        secret_value=None,
        params={"phone": "+919876543210"}
    )
    assert result["is_success"] is False
    assert result["status_code"] == 302
    assert "redirect" in result["message"].lower()


def test_external_data_source_rbac_and_stepup(client, db, monkeypatch):
    monkeypatch.setattr(config, "INTEGRATION_ALLOWED_HOSTS", ["api.store.com"])

    # Pre-mock DNS validation to succeed for api.store.com
    def mock_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    # 1. Agent gets 403 Forbidden
    agent_user = models.User(
        username=f"agent_{uuid.uuid4().hex[:6]}",
        email=f"agent_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("AgentPass123!"),
        role="agent",
        is_active=True
    )
    db.add(agent_user)

    # 2. Manager gets 403 Forbidden
    mgr_user = models.User(
        username=f"mgr_{uuid.uuid4().hex[:6]}",
        email=f"mgr_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash("MgrPass123!"),
        role="manager",
        is_active=True
    )
    db.add(mgr_user)
    db.commit()

    agent_token = create_access_token(data={"sub": agent_user.username, "role": "agent"})
    res = client.get("/api/external-data-sources", headers={"Authorization": f"Bearer {agent_token}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    manager_token = create_access_token(data={"sub": mgr_user.username, "role": "manager"})
    res = client.get("/api/external-data-sources", headers={"Authorization": f"Bearer {manager_token}"})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    # 3. Create Admin user with password and 2FA
    admin_pw = "AdminPass123!"
    totp_secret = pyotp.random_base32()
    admin_user = models.User(
        username=f"admin_{uuid.uuid4().hex[:6]}",
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash(admin_pw),
        role="admin",
        is_active=True,
        is_2fa_enabled=True,
        totp_secret=totp_secret
    )
    db.add(admin_user)
    db.commit()

    admin_token = create_access_token(data={"sub": admin_user.username, "role": "admin"})

    # Creation without step-up password fails
    create_payload = {
        "name": "Live Store API",
        "endpoint_url": "https://api.store.com/customers",
        "auth_method": "bearer",
        "api_key": "raw_secret_to_encrypt",
        "lookup_param": "phone",
        "approved_hostname": "api.store.com"
    }
    res_no_pw = client.post(
        "/api/external-data-sources",
        json=create_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_no_pw.status_code == status.HTTP_400_BAD_REQUEST
    assert "password is required" in res_no_pw.text

    # Creation with valid password and TOTP succeeds
    totp_code = pyotp.TOTP(totp_secret).now()
    create_payload["password"] = admin_pw
    create_payload["two_factor_code"] = totp_code

    res_ok = client.post(
        "/api/external-data-sources",
        json=create_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_ok.status_code == status.HTTP_201_CREATED
    data = res_ok.json()
    source_id = data["id"]
    assert "api_key" not in data or data["api_key"] is None
    assert data["secret_reference"] is not None

    # Check AuditEvent was created
    audit = db.query(models.AuditEvent).filter(
        models.AuditEvent.action == "CREATE_EXTERNAL_DATA_SOURCE",
        models.AuditEvent.target_id == str(source_id)
    ).first()
    assert audit is not None
    assert audit.actor_user_id == admin_user.id


def test_test_endpoint_sanitized_response(client, db, monkeypatch):
    monkeypatch.setattr(config, "INTEGRATION_ALLOWED_HOSTS", ["api.store.com"])
    
    # Pre-mock DNS validation to succeed
    def mock_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    # Mock httpx to return an upstream response with sensitive body
    def mock_get(self, url, **kwargs):
        req = httpx.Request("GET", url)
        return httpx.Response(200, json={"secret_customer_pii": "confidential", "balance": 9999}, request=req)

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    admin_pw = "AdminPass123!"
    totp_secret = pyotp.random_base32()
    admin_user = models.User(
        username=f"admin_{uuid.uuid4().hex[:6]}",
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        hashed_password=get_password_hash(admin_pw),
        role="admin",
        is_active=True,
        is_2fa_enabled=True,
        totp_secret=totp_secret
    )
    db.add(admin_user)
    db.commit()

    admin_token = create_access_token(data={"sub": admin_user.username, "role": "admin"})

    # Create data source directly
    sec_ref = f"sec_ref_{uuid.uuid4().hex[:8]}"
    store_secret(db, sec_ref, "valid-token-123")
    src = models.ExternalDataSource(
        name="Sanitized Test API",
        endpoint_url="https://api.store.com/customers",
        auth_method="bearer",
        secret_reference=sec_ref,
        approved_hostname="api.store.com",
        purpose="customer_lookup",
        lookup_param="phone",
        is_active=True
    )
    db.add(src)
    db.commit()

    totp_code = pyotp.TOTP(totp_secret).now()
    res = client.post(
        f"/api/external-data-sources/{src.id}/test",
        json={"password": admin_pw, "two_factor_code": totp_code, "test_phone": "+919876543210"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == status.HTTP_200_OK
    res_data = res.json()
    
    # Assert only sanitized fields returned
    assert "status_code" in res_data
    assert "is_success" in res_data
    assert "latency_ms" in res_data
    assert "correlation_id" in res_data
    # Strictly sanitized response: never leaks upstream body, headers, or exceptions
    assert "secret_customer_pii" not in str(res_data)
    assert "confidential" not in str(res_data)


def test_scheduler_fetch_uses_gateway_and_enforces_url_validation(db, monkeypatch):
    from scheduler import fetch_external_api_value
    
    # 1. Configured with a malicious unallowlisted / unsafe endpoint
    monkeypatch.setattr(config, "INTEGRATION_ALLOWED_HOSTS", ["api.store.com"])
    
    sec_ref = f"sec_ref_{uuid.uuid4().hex[:8]}"
    store_secret(db, sec_ref, "token-123")
    bad_src = models.ExternalDataSource(
        name="Bad Source",
        endpoint_url="http://127.0.0.1:8000/internal",
        auth_method="bearer",
        secret_reference=sec_ref,
        approved_hostname="127.0.0.1",
        is_active=True
    )
    db.add(bad_src)
    db.commit()

    # Attempt fetch through scheduler - should return "" and be blocked by SSRF/gateway
    val = fetch_external_api_value("points", "+919876543210", source_id=bad_src.id, db=db)
    assert val == ""

    # 2. Configured with an allowlisted safe host
    good_src = models.ExternalDataSource(
        name="Good Source",
        endpoint_url="https://api.store.com/customers",
        auth_method="bearer",
        secret_reference=sec_ref,
        approved_hostname="api.store.com",
        is_active=True
    )
    db.add(good_src)
    db.commit()

    # Pre-mock DNS and httpx
    def mock_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]
    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo)

    def mock_get(self, url, **kwargs):
        req = httpx.Request("GET", url)
        return httpx.Response(200, json={"points": "450"}, request=req)
    monkeypatch.setattr(httpx.Client, "get", mock_get)

    val = fetch_external_api_value("points", "+919876543210", source_id=good_src.id, db=db)
    assert val == "450"
