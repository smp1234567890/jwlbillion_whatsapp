"""
Rate Limiter Module — WP7
Redis-backed distributed rate limiting using slowapi.
Trusts X-Forwarded-For only when the immediate peer is a configured trusted proxy.
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi import Request
import config

_TRUSTED_PROXIES: set[str] = set(
    ip.strip() for ip in getattr(config, "TRUSTED_PROXIES_RAW", "127.0.0.1,::1").split(",") if ip.strip()
)


def get_trusted_client_ip(request: Request) -> str:
    """
    Returns the real client IP.
    Trusts X-Forwarded-For only when the immediate TCP peer is a known trusted proxy.
    Prevents clients from spoofing their IP by injecting X-Forwarded-For headers.
    """
    peer_ip = request.client.host if request.client else "127.0.0.1"
    if peer_ip in _TRUSTED_PROXIES:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip
    return peer_ip


def _build_limiter() -> Limiter:
    storage_uri = getattr(config, "REDIS_URL", None)
    if storage_uri:
        return Limiter(key_func=get_trusted_client_ip, storage_uri=storage_uri, default_limits=["200/minute"])
    # Fallback to in-memory (dev/test only — REDIS_URL is mandatory in production)
    return Limiter(key_func=get_trusted_client_ip, default_limits=["200/minute"])


limiter = _build_limiter()
