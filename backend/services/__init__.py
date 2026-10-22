# Package marker for backend.services
from services.phone_service import normalize_phone, is_valid_phone, InvalidPhoneNumberError
from services.policy_service import (
    authorize_outbound_message,
    record_consent,
    revoke_consent,
    has_active_consent,
    is_quiet_hours,
    FIXED_DAILY_LIMIT
)
from services.secret_store import store_secret, get_secret, delete_secret
from services.integration_gateway import (
    validate_ssrf_safe_url,
    dispatch_external_request,
    CredentialMode,
    SSRFSecurityError,
    HostNotAllowedError,
    CredentialMismatchError
)
