import socket
import ipaddress
import base64
import time
import uuid
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import httpx
import config

logger = logging.getLogger("integration_gateway")


class CredentialMode(str, Enum):
    BEARER = "bearer"
    X_API_KEY = "x_api_key"
    BASIC = "basic"
    NONE = "none"


class SSRFSecurityError(Exception):
    pass


class HostNotAllowedError(Exception):
    pass


class CredentialMismatchError(Exception):
    pass


def validate_ssrf_safe_url(url: str, allowed_hosts: Optional[List[str]] = None) -> str:
    """
    Validates that a URL is safe against SSRF:
    1. Scheme must be strictly HTTPS.
    2. No userinfo (username:password) in the URL.
    3. Port must be 443 (unless explicitly allowlisted).
    4. Reject direct IP literals (IPv4 and IPv6).
    5. Host must be present in the approved INTEGRATION_ALLOWED_HOSTS list.
    6. DNS resolution (pre-dial): resolves both IPv4 and IPv6 and blocks loopback,
       private, link-local, multicast, unspecified, reserved, or cloud-metadata IPs.
    """
    if not url or not str(url).strip():
        raise SSRFSecurityError("Endpoint URL cannot be empty.")

    cleaned_url = str(url).strip()
    parsed = urlparse(cleaned_url)

    if parsed.scheme.lower() != "https":
        raise SSRFSecurityError("Invalid endpoint URL: Only secure HTTPS endpoints are permitted.")

    if parsed.username or parsed.password:
        raise SSRFSecurityError("Invalid endpoint URL: URLs containing userinfo credentials are prohibited.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("Invalid endpoint URL: Hostname is required.")

    norm_host = hostname.strip().lower().rstrip(".")

    # Reject direct IP literals
    try:
        ipaddress.ip_address(norm_host)
        raise SSRFSecurityError(f"Invalid endpoint URL: Direct IP literal addresses are prohibited ({norm_host}).")
    except ValueError:
        pass  # Hostname is a domain name string, continue

    port = parsed.port or 443
    if port != 443:
        host_with_port = f"{norm_host}:{port}"
        active_allowed = allowed_hosts if allowed_hosts is not None else config.INTEGRATION_ALLOWED_HOSTS
        if host_with_port not in active_allowed:
            raise SSRFSecurityError(f"Invalid endpoint port: Only standard port 443 is permitted ({port}).")

    # Host allowlist verification
    active_allowed = allowed_hosts if allowed_hosts is not None else config.INTEGRATION_ALLOWED_HOSTS
    if active_allowed:
        if norm_host not in active_allowed and f"{norm_host}:{port}" not in active_allowed:
            raise HostNotAllowedError(f"Host '{norm_host}' is not allowlisted in INTEGRATION_ALLOWED_HOSTS.")
    elif config.ENVIRONMENT == "production":
        raise HostNotAllowedError("No INTEGRATION_ALLOWED_HOSTS configured in production environment.")

    # Pre-dial DNS resolution & IP verification
    try:
        addr_info = socket.getaddrinfo(norm_host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SSRFSecurityError(f"Unable to resolve hostname '{norm_host}': {e}") from e

    if not addr_info:
        raise SSRFSecurityError(f"No DNS records resolved for hostname '{norm_host}'.")

    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFSecurityError(f"Invalid resolved IP format '{ip_str}' for host '{norm_host}'.")

        # Check for forbidden ranges
        if (
            ip_obj.is_loopback
            or ip_obj.is_private
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
            or str(ip_obj) == "169.254.169.254"
            or getattr(ip_obj, "is_site_local", False)
        ):
            logger.warning(f"🚨 [SSRF Blocked] Host '{norm_host}' resolved to forbidden IP {ip_str}.")
            raise SSRFSecurityError(f"DNS resolved host '{norm_host}' to forbidden network address {ip_str}.")

    return cleaned_url


def dispatch_external_request(
    endpoint_url: str,
    approved_hostname: Optional[str] = None,
    credential_mode: CredentialMode = CredentialMode.NONE,
    secret_value: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 8.0,
    correlation_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Safely executes an external HTTP GET request through the integration gateway:
    - Enforces SSRF and host allowlisting.
    - Enforces credential host binding (credentials cannot be sent to unauthorized hosts).
    - Owns exact headers according to CredentialMode.
    - follow_redirects=False (redirects treated as safe failures).
    - trust_env=False (ignores local proxy env vars).
    """
    correlation_id = correlation_id or f"gw-{uuid.uuid4().hex[:12]}"

    # 1. Credential Host Binding Check
    req_host = (urlparse(endpoint_url).hostname or "").lower()
    if approved_hostname:
        bound_host = approved_hostname.strip().lower()
        if req_host != bound_host:
            raise CredentialMismatchError(
                f"Requested host '{req_host}' does not match credential bound to approved host '{bound_host}'."
            )

    # 2. SSRF and Host allowlist check
    validate_ssrf_safe_url(endpoint_url)

    # 3. Construct headers strictly by CredentialMode (gateway owns headers)
    headers: Dict[str, str] = {
        "X-Correlation-ID": correlation_id,
        "Accept": "application/json"
    }

    mode = CredentialMode(credential_mode) if isinstance(credential_mode, str) else credential_mode
    if mode == CredentialMode.BEARER and secret_value:
        headers["Authorization"] = f"Bearer {secret_value}"
    elif mode == CredentialMode.X_API_KEY and secret_value:
        headers["X-API-Key"] = secret_value
    elif mode == CredentialMode.BASIC and secret_value:
        b64_val = base64.b64encode(secret_value.encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {b64_val}"
    # mode == NONE: no auth headers added

    start_time = time.time()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            resp = client.get(endpoint_url, params=params or {}, headers=headers)
            elapsed_ms = round((time.time() - start_time) * 1000.0, 2)

            if 300 <= resp.status_code < 400:
                return {
                    "is_success": False,
                    "status_code": resp.status_code,
                    "latency_ms": elapsed_ms,
                    "correlation_id": correlation_id,
                    "message": f"Redirect response ({resp.status_code}) blocked as safe failure."
                }

            is_success = (200 <= resp.status_code < 300)
            data = None
            if is_success:
                try:
                    data = resp.json()
                except Exception:
                    data = None

            return {
                "is_success": is_success,
                "status_code": resp.status_code,
                "latency_ms": elapsed_ms,
                "correlation_id": correlation_id,
                "data": data,
                "message": "Connection verified successfully." if is_success else f"Upstream endpoint responded with status {resp.status_code}."
            }

    except httpx.TimeoutException:
        elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
        return {
            "is_success": False,
            "status_code": 504,
            "latency_ms": elapsed_ms,
            "correlation_id": correlation_id,
            "message": "Gateway connection timed out."
        }
    except Exception as e:
        elapsed_ms = round((time.time() - start_time) * 1000.0, 2)
        return {
            "is_success": False,
            "status_code": 502,
            "latency_ms": elapsed_ms,
            "correlation_id": correlation_id,
            "message": "Upstream communication error occurred."
        }
