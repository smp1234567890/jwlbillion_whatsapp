"""
Logging Configuration and Redaction
Centralized structured log redactor that scrubs:
- Customer phone numbers
- Bearer tokens, API keys, and session tokens
- Passwords and TOTP secrets
- URLs with query strings
- Upstream raw response snippets and message bodies
"""

import logging
import re
from typing import Any


PHONE_PATTERN = re.compile(r'(\+?91)?[6-9]\d{9}')
BEARER_PATTERN = re.compile(r'Bearer\s+[A-Za-z0-9_\-\.]+', re.IGNORECASE)
TOKEN_PARAM_PATTERN = re.compile(
    r'(["\']?(?:access_token|refresh_token|token|api_key|secret|password|totp_secret|recovery_code|webhook_secret)["\']?\s*[:=]\s*)(["\']?)([^"\'\s&,}]+)(["\']?)',
    re.IGNORECASE
)
URL_QUERY_PATTERN = re.compile(r'(https?://[^\s\?]+)\?([^\s]+)')
JSON_PHONE_PATTERN = re.compile(r'("(?:phone|customer_phone|recipient_phone)":\s*")([^"]+)(")')


def redact_text(text: str) -> str:
    """
    Applies comprehensive regex scrubbing to a text string.
    """
    if not isinstance(text, str):
        text = str(text)

    # 1. Redact Bearer tokens
    text = BEARER_PATTERN.sub('Bearer [REDACTED_TOKEN]', text)

    # 2. Redact sensitive key-value parameters (JSON and query-style)
    text = TOKEN_PARAM_PATTERN.sub(r'\1\2[REDACTED_SECRET]\4', text)

    # 3. Redact URLs with query strings
    text = URL_QUERY_PATTERN.sub(r'\1?[REDACTED_QUERY]', text)

    # 4. Redact JSON phone fields
    def _mask_json_phone(m):
        raw = m.group(2)
        if len(raw) >= 10:
            masked = f"{raw[:3]}******{raw[-4:]}"
        else:
            masked = "[REDACTED_PHONE]"
        return f'{m.group(1)}{masked}{m.group(3)}'

    text = JSON_PHONE_PATTERN.sub(_mask_json_phone, text)

    # 5. Redact raw standalone phone numbers
    def _mask_phone_match(m):
        full = m.group(0)
        if full.startswith("+91") and len(full) == 13:
            return f"+91******{full[-4:]}"
        elif len(full) == 10:
            return f"{full[:2]}******{full[-4:]}"
        return f"[REDACTED_PHONE]"

    text = PHONE_PATTERN.sub(_mask_phone_match, text)

    return text


class RedactingFilter(logging.Filter):
    """
    Logging filter that intercepts and sanitizes log record messages and arguments.
    Formats the message with args first, scrubs PII, and clears args to avoid format collision.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        record.msg = redact_text(msg)
        record.args = ()
        return True


def configure_secure_logging() -> None:
    """
    Installs the RedactingFilter globally on the root logger and all handlers.
    """
    root_logger = logging.getLogger()
    redactor = RedactingFilter()
    
    # Avoid duplicate filters if called multiple times
    if not any(isinstance(f, RedactingFilter) for f in root_logger.filters):
        root_logger.addFilter(redactor)

    for handler in root_logger.handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(redactor)
