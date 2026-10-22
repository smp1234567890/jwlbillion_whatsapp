"""
Phone Service
Strict phone number normalization and validation to canonical E.164 format.
"""

from typing import Optional
import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


class InvalidPhoneNumberError(ValueError):
    """Raised when a phone number cannot be parsed or is invalid."""
    pass


def normalize_phone(phone_raw: Optional[str], default_region: str = "IN") -> str:
    """
    Normalizes a phone number to strict E.164 format (+[country_code][national_number]).
    
    Accepts raw strings such as:
      - '9876543210' -> '+919876543210'
      - '09876543210' -> '+919876543210'
      - '919876543210' -> '+919876543210'
      - '+91 98765-43210' -> '+919876543210'
      - '+1 (415) 555-2671' -> '+14155552671'

    Raises InvalidPhoneNumberError if the number is empty, cannot be parsed,
    or is not a possible/valid phone number.
    """
    if not phone_raw or not str(phone_raw).strip():
        raise InvalidPhoneNumberError("Phone number cannot be empty.")

    cleaned = str(phone_raw).strip()

    # Pre-clean common separators and handle leading zeros or prefixes if not starting with +
    # Note: if a user passes '919876543210' without '+' for IN region, phonenumbers might parse
    # it as a local number or fail if region is IN, or if '+' is added it parses as country code 91.
    # We test parsing as-is, and if it fails or parses with leading zeros / 91, handle gracefully.
    try:
        # If user passed "919876543210" (12 digits starting with 91, no +), adding '+' allows proper E.164 parse
        if not cleaned.startswith("+") and cleaned.startswith("91") and len(cleaned) == 12:
            parsed = phonenumbers.parse("+" + cleaned, None)
        else:
            parsed = phonenumbers.parse(cleaned, default_region)
    except NumberParseException as e:
        raise InvalidPhoneNumberError(f"Cannot parse phone number '{cleaned}': {e.args[0]}") from e

    if not phonenumbers.is_possible_number(parsed):
        raise InvalidPhoneNumberError(f"Phone number '{cleaned}' is not a possible phone number.")

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError(f"Phone number '{cleaned}' is not a valid phone number for region {default_region}.")

    formatted = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    return formatted


def is_valid_phone(phone_raw: Optional[str], default_region: str = "IN") -> bool:
    """Returns True if the phone number can be successfully normalized to E.164, False otherwise."""
    try:
        normalize_phone(phone_raw, default_region)
        return True
    except (InvalidPhoneNumberError, Exception):
        return False
