"""
Tests for Work Package 6: Centralized Structured Log Redaction & Request Correlation Tracking
Covers:
- Phone number scrubbing in logs (+91******3210)
- Bearer tokens, passwords, and API keys redaction
- URLs with query strings redaction
- Correlation ID propagation and header injection
- Error responses contain correlation ID without leaking stack traces or internal secrets
- PII field envelope encryption & decryption helpers at rest
"""

import io
import logging
import uuid
import pytest
from fastapi import status, APIRouter
from main import app
from services.logging_config import redact_text, RedactingFilter
from services import pii_service


def test_redact_phone_numbers():
    sample_text = "Dispatched WhatsApp message to customer phone +919876543210 successfully."
    cleaned = redact_text(sample_text)
    assert "+919876543210" not in cleaned
    assert "+91******3210" in cleaned

    standalone_phone = "Inbound query from 9876543210 received."
    cleaned_standalone = redact_text(standalone_phone)
    assert "9876543210" not in cleaned_standalone
    assert "98******3210" in cleaned_standalone


def test_redact_tokens_and_credentials():
    token_log = "Authorization header: Bearer EAAG1234567890abcdef1234567890"
    cleaned_token = redact_text(token_log)
    assert "EAAG1234567890abcdef1234567890" not in cleaned_token
    assert "Bearer [REDACTED_TOKEN]" in cleaned_token

    cred_log = 'Payload: {"username": "admin", "password": "SecretSuperPassword123!", "api_key": "mb_live_sec_12345"}'
    cleaned_cred = redact_text(cred_log)
    assert "SecretSuperPassword123!" not in cleaned_cred
    assert "mb_live_sec_12345" not in cleaned_cred
    assert '[REDACTED_SECRET]' in cleaned_cred


def test_redact_urls_with_query_strings():
    url_log = "Connecting upstream: https://graph.facebook.com/v19.0/messages?access_token=secret_meta_token_123&phone=919876543210"
    cleaned_url = redact_text(url_log)
    assert "secret_meta_token_123" not in cleaned_url
    assert "https://graph.facebook.com/v19.0/messages?[REDACTED_QUERY]" in cleaned_url


def test_logging_filter_in_action():
    """
    Verifies that the RedactingFilter intercepts LogRecord and scrubs msg and args.
    """
    logger = logging.getLogger("test_redactor_logger")
    logger.setLevel(logging.INFO)
    
    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.addFilter(RedactingFilter())
    logger.addHandler(handler)
    
    logger.info("Attempting send to +919876543210 with secret password=%s", "RawPasswordXYZ")
    
    output = log_stream.getvalue()
    assert "+919876543210" not in output
    assert "+91******3210" in output
    assert "RawPasswordXYZ" not in output
    assert "[REDACTED_SECRET]" in output


def test_correlation_id_header_injected(client):
    """
    Requests receive X-Correlation-ID in response headers (either echoed or generated).
    """
    # 1. Provide custom correlation ID
    custom_id = "test-corr-uuid-123456"
    res1 = client.get("/api/health", headers={"X-Correlation-ID": custom_id})
    assert res1.status_code == status.HTTP_200_OK
    assert res1.headers.get("X-Correlation-ID") == custom_id

    # 2. Omitting correlation ID auto-generates a UUID
    res2 = client.get("/api/health")
    assert res2.status_code == status.HTTP_200_OK
    generated_id = res2.headers.get("X-Correlation-ID")
    assert generated_id is not None
    # Validate UUID format
    val = uuid.UUID(generated_id)
    assert str(val) == generated_id


def test_error_response_contains_correlation_id_and_no_stack_trace(client):
    """
    Error responses contain correlation_id and do not leak stack traces or internal secrets.
    """
    # Trigger 404 or 400
    res = client.get("/api/contacts/99999999", headers={"Authorization": "Bearer invalid_token"})
    assert res.status_code == status.HTTP_401_UNAUTHORIZED
    data = res.json()
    assert "correlation_id" in data
    assert res.headers.get("X-Correlation-ID") == data["correlation_id"]
    # Ensure no python stack trace is returned
    assert "Traceback" not in res.text
    assert "File \"" not in res.text


def test_pii_envelope_encryption_at_rest():
    """
    Verifies AES-256-GCM envelope encryption and decryption for sensitive PII columns.
    """
    plaintext = "+919876543210"
    encrypted = pii_service.encrypt_pii(plaintext)
    assert encrypted is not None
    assert encrypted.startswith("enc:")
    assert plaintext not in encrypted

    decrypted = pii_service.decrypt_pii(encrypted)
    assert decrypted == plaintext
