import os
import logging
import warnings
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("config")

# ── Environment & Application Settings ──
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
APP_NAME = os.getenv("APP_NAME", "WhatsApp CRM")
BRAND_NAME = os.getenv("BRAND_NAME", "JWL")
DEFAULT_LOCALE = os.getenv("DEFAULT_LOCALE", "en")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "")

# ── Security & Authentication ──
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if ENVIRONMENT == "production":
        raise RuntimeError("FATAL: SECRET_KEY environment variable is mandatory in production!")
    warnings.warn(
        "SECRET_KEY is not set in environment. Falling back to an ephemeral dev key. "
        "Set SECRET_KEY in your .env or host dashboard for production."
    )
    SECRET_KEY = "dev_secret_key_change_in_production_environment"

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

# Webhook secret for HMAC / API Key verification of external e-commerce requests
_raw_webhook_secret = os.getenv("WEBHOOK_SECRET", "").strip()
if (_raw_webhook_secret.startswith('"') and _raw_webhook_secret.endswith('"')) or \
   (_raw_webhook_secret.startswith("'") and _raw_webhook_secret.endswith("'")):
    _raw_webhook_secret = _raw_webhook_secret[1:-1].strip()
WEBHOOK_SECRET = _raw_webhook_secret

META_APP_SECRET = os.getenv("META_APP_SECRET", "")

# Meta Inbound Webhook Verify Token
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

# ── Business Logic Limits & Constants ──
# Subscription / Multi-tenant user limit (e.g. maximum 5 team members)
MAX_USERS_LIMIT = int(os.getenv("MAX_USERS_LIMIT", "5"))

# Daily guardrail on maximum outbound WhatsApp message sends (fixed to 200 per day)
DAILY_MESSAGE_SEND_LIMIT = 2000

# Default promo coupon code and discount terms
DEFAULT_COUPON_CODE = os.getenv("DEFAULT_COUPON_CODE", "WELCOME")
DEFAULT_DISCOUNT_PERCENT = int(os.getenv("DEFAULT_DISCOUNT_PERCENT", "10"))
DEFAULT_EXPIRY_DAYS = int(os.getenv("DEFAULT_EXPIRY_DAYS", "30"))

# External HTTP client timeout (in seconds)
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5.0"))
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"

# ── Reverse Proxy & Trusted Networks ──
TRUSTED_PROXIES_RAW = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1")
TRUSTED_PROXIES = [p.strip() for p in TRUSTED_PROXIES_RAW.split(",") if p.strip()]

# ── Redis (required for distributed rate limiting in production) ──
_raw_redis_url = os.getenv("REDIS_URL", "").strip()
if _raw_redis_url:
    import re
    _match = re.search(r"(rediss?://[^\s]+)", _raw_redis_url)
    if _match:
        _url = _match.group(1)
        if "--tls" in _raw_redis_url and _url.startswith("redis://"):
            _url = _url.replace("redis://", "rediss://", 1)
        REDIS_URL = _url
    else:
        REDIS_URL = _raw_redis_url
else:
    REDIS_URL = None

if not REDIS_URL and ENVIRONMENT == "production":
    raise RuntimeError("FATAL: REDIS_URL is mandatory in production for distributed rate limiting.")

# ── Audit hash salt (defaults to SECRET_KEY; override for key-rotation safety) ──
AUDIT_HASH_SALT = os.getenv("AUDIT_HASH_SALT", SECRET_KEY)

# ── Allowed Origins ──
# Normalize: browsers send Origin header without trailing slash (e.g. 'https://site.vercel.app').
# We strip trailing slashes, and ensure both forms are included for compatibility.
_raw_origins = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]
ALLOWED_ORIGINS = []
for _o in _raw_origins:
    _clean = _o.rstrip("/")
    if _clean:
        if _clean not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(_clean)
        if f"{_clean}/" not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(f"{_clean}/")

# ── Database Connection ──
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if ENVIRONMENT == "production":
        raise RuntimeError("FATAL: DATABASE_URL environment variable is mandatory in production!")
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/whatsapp_crm"

# ── Meta WhatsApp Cloud API ──
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")
WHATSAPP_WEBHOOK_URL = os.getenv("WHATSAPP_WEBHOOK_URL", "")

META_GRAPH_BASE_URL = os.getenv("META_GRAPH_BASE_URL", "https://graph.facebook.com").rstrip("/")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v19.0")
META_APP_ID = os.getenv("META_APP_ID", "1128037383522327")

# ── Store Integration & Feeds ──
STORE_INACTIVE_FEED_URL = os.getenv("STORE_INACTIVE_FEED_URL", "")
STORE_SUPPORT_PHONE = os.getenv("STORE_SUPPORT_PHONE", "")
STORE_LOCATION = os.getenv("STORE_LOCATION", "")

# ── Initial Admin & Service Account Credentials ──
INITIAL_ADMIN_USERNAME = os.getenv("INITIAL_ADMIN_USERNAME", "admin").strip()
INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD")
INITIAL_ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "admin@jwl-billion.com").strip()

ECOM_SERVICE_USERNAME = os.getenv("ECOM_SERVICE_USERNAME", "ecom_service").strip()
ECOM_SERVICE_PASSWORD = os.getenv("ECOM_SERVICE_PASSWORD")
ECOM_SERVICE_EMAIL = os.getenv("ECOM_SERVICE_EMAIL", "ecommerce@jwl-billion.com").strip()

# ── Integration Gateway & Secret Storage ──
INTEGRATION_ALLOWED_HOSTS_RAW = os.getenv("INTEGRATION_ALLOWED_HOSTS", "")
INTEGRATION_ALLOWED_HOSTS = [
    h.strip().lower() for h in INTEGRATION_ALLOWED_HOSTS_RAW.split(",") if h.strip()
]

# ── Shopify Configuration ──
SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "").strip()
SHOPIFY_PUBLIC_DOMAIN = os.getenv("SHOPIFY_PUBLIC_DOMAIN", "jwlbillion.com").strip()
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "").strip()
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "").strip()
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN", "").strip()

APP_ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY")
if not APP_ENCRYPTION_KEY:
    if ENVIRONMENT == "production":
        raise RuntimeError("FATAL: APP_ENCRYPTION_KEY environment variable is mandatory in production!")
    APP_ENCRYPTION_KEY = SECRET_KEY  # Ephemeral development fallback


# ── Fail-Closed Configuration Validation ──

KNOWN_PLACEHOLDERS = {
    "change_me", "changeme", "your_secret", "secret", "placeholder",
    "replace_me", "todo", "dev_secret_key_change_in_production_environment",
    "dummy", "test", "your_token", "your_app_secret", "your_verify_token",
    "123456", "password", "admin", "null", "none", "undefined",
    "your_webhook_secret", "your_encryption_key", "dev_secret_key"
}


def is_placeholder(val) -> bool:
    if not val or not isinstance(val, str) or not val.strip():
        return True
    clean = val.strip().lower()
    if clean in KNOWN_PLACEHOLDERS:
        return True
    for marker in ("change_me", "replace_me", "your_secret", "placeholder", "your_token", "dummy"):
        if marker in clean:
            return True
    return False


def validate_production_config(env_values: dict = None) -> None:
    """
    Validates that all critical settings, secrets, and database credentials
    are present, non-placeholder, and securely configured for production.
    Raises RuntimeError if any check fails.
    """
    vals = env_values if env_values is not None else {}

    secret_key = vals.get("SECRET_KEY", SECRET_KEY)
    if is_placeholder(secret_key) or len(secret_key) < 32:
        raise RuntimeError(
            "FATAL: SECRET_KEY must be a non-placeholder secret of at least 32 characters in production."
        )

    app_enc_key = vals.get("APP_ENCRYPTION_KEY", APP_ENCRYPTION_KEY)
    if is_placeholder(app_enc_key) or len(app_enc_key) < 32:
        raise RuntimeError(
            "FATAL: APP_ENCRYPTION_KEY must be a non-placeholder secret of at least 32 characters in production."
        )

    webhook_sec = vals.get("WEBHOOK_SECRET", WEBHOOK_SECRET)
    if is_placeholder(webhook_sec) or len(webhook_sec) < 16:
        raise RuntimeError(
            "FATAL: WEBHOOK_SECRET must be a non-placeholder secret of at least 16 characters in production."
        )

    meta_secret = vals.get("META_APP_SECRET", META_APP_SECRET)
    if is_placeholder(meta_secret) or len(meta_secret) < 16:
        raise RuntimeError(
            "FATAL: META_APP_SECRET must be a non-placeholder secret of at least 16 characters in production."
        )

    verify_token = vals.get("WHATSAPP_VERIFY_TOKEN", WHATSAPP_VERIFY_TOKEN)
    if is_placeholder(verify_token) or len(verify_token) < 8:
        raise RuntimeError(
            "FATAL: WHATSAPP_VERIFY_TOKEN must be a non-placeholder token of at least 8 characters in production."
        )

    phone_id = vals.get("WHATSAPP_PHONE_NUMBER_ID", WHATSAPP_PHONE_NUMBER_ID)
    if is_placeholder(phone_id):
        raise RuntimeError(
            "FATAL: WHATSAPP_PHONE_NUMBER_ID is mandatory and cannot be a placeholder in production."
        )

    waba_id = vals.get("WHATSAPP_BUSINESS_ACCOUNT_ID", WHATSAPP_BUSINESS_ACCOUNT_ID)
    if is_placeholder(waba_id):
        raise RuntimeError(
            "FATAL: WHATSAPP_BUSINESS_ACCOUNT_ID is mandatory and cannot be a placeholder in production."
        )

    api_tok = vals.get("WHATSAPP_API_TOKEN", WHATSAPP_API_TOKEN)
    if is_placeholder(api_tok):
        raise RuntimeError(
            "FATAL: WHATSAPP_API_TOKEN is mandatory and cannot be a placeholder in production."
        )

    db_url = vals.get("DATABASE_URL", DATABASE_URL)
    if not db_url or is_placeholder(db_url):
        raise RuntimeError(
            "FATAL: DATABASE_URL is mandatory and cannot be empty in production."
        )
    db_lower = db_url.lower()
    if db_lower.startswith("sqlite"):
        raise RuntimeError(
            "FATAL: SQLite is prohibited in production. A production PostgreSQL instance is required."
        )
    if not (db_lower.startswith("postgresql://") or db_lower.startswith("postgres://")):
        raise RuntimeError(
            "FATAL: DATABASE_URL must be a PostgreSQL connection URI in production."
        )
    if "localhost" in db_lower or "127.0.0.1" in db_lower:
        raise RuntimeError(
            "FATAL: DATABASE_URL cannot connect to localhost or 127.0.0.1 in production."
        )
    if "postgres:postgres@" in db_lower:
        raise RuntimeError(
            "FATAL: DATABASE_URL cannot use default postgres:postgres credentials in production."
        )

    raw_origins = vals.get("ALLOWED_ORIGINS", ALLOWED_ORIGINS)
    if isinstance(raw_origins, str):
        origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    else:
        origins = list(raw_origins)
    if not origins:
        raise RuntimeError(
            "FATAL: ALLOWED_ORIGINS is mandatory and cannot be empty in production."
        )
    for origin in origins:
        if origin == "*":
            raise RuntimeError(
                "FATAL: Wildcard '*' is prohibited in ALLOWED_ORIGINS in production."
            )
        if "localhost" in origin or "127.0.0.1" in origin:
            raise RuntimeError(
                f"FATAL: Localhost origin '{origin}' is prohibited in ALLOWED_ORIGINS in production."
            )
        if not (origin.startswith("https://") or origin.startswith("capacitor://")):
            raise RuntimeError(
                f"FATAL: Origin '{origin}' in ALLOWED_ORIGINS must use HTTPS or capacitor:// scheme in production."
            )

    raw_hosts = vals.get("INTEGRATION_ALLOWED_HOSTS", INTEGRATION_ALLOWED_HOSTS)
    if isinstance(raw_hosts, str):
        hosts = [h.strip().lower() for h in raw_hosts.split(",") if h.strip()]
    else:
        hosts = list(raw_hosts)
    if not hosts:
        raise RuntimeError(
            "FATAL: INTEGRATION_ALLOWED_HOSTS is mandatory and cannot be empty in production."
        )
    for host in hosts:
        if host == "*":
            raise RuntimeError(
                "FATAL: Wildcard '*' is prohibited in INTEGRATION_ALLOWED_HOSTS in production."
            )
        if "localhost" in host or "127.0.0.1" in host:
            raise RuntimeError(
                f"FATAL: Localhost '{host}' is prohibited in INTEGRATION_ALLOWED_HOSTS in production."
            )

    redis_url = vals.get("REDIS_URL", REDIS_URL)
    if not redis_url or is_placeholder(str(redis_url)):
        raise RuntimeError(
            "FATAL: REDIS_URL is mandatory in production for distributed rate limiting."
        )


if ENVIRONMENT == "production":
    validate_production_config()

